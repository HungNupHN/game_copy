"""
Utilities and Helper Functions for PC Reviewer Deployer.
Provides chunked file copying with progress & cancellation,
path formatting, size calculations, and system helpers.
"""

import os
import sys
import time
import shutil
import ctypes
import threading
from pathlib import Path
from typing import Callable, Optional, Tuple, List, Dict, Any

# 4MB chunks for fast I/O while maintaining responsive cancellation
COPY_CHUNK_SIZE = 4 * 1024 * 1024


def is_admin() -> bool:
    """Check if the current process has Windows administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def to_forward_slashes(path: Any) -> str:
    """Convert any file path into forward slashes format (e.g., C:/Games/...)."""
    return str(path).replace("\\", "/")


def format_bytes(num_bytes: int) -> str:
    """Format bytes into human-readable string (B, KB, MB, GB, TB)."""
    if num_bytes < 0:
        num_bytes = 0
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024.0 or unit == "TB":
            if unit in ["B", "KB"]:
                return f"{num_bytes:.0f} {unit}"
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} GB"


def format_speed(bytes_per_sec: float) -> str:
    """Format transfer speed in MB/s or KB/s."""
    if bytes_per_sec <= 0:
        return "0.0 MB/s"
    mb_s = bytes_per_sec / (1024.0 * 1024.0)
    if mb_s >= 0.1:
        return f"{mb_s:.1f} MB/s"
    kb_s = bytes_per_sec / 1024.0
    return f"{kb_s:.1f} KB/s"


def format_eta(seconds: float) -> str:
    """Format remaining seconds into mm:ss or hh:mm:ss."""
    if seconds <= 0 or seconds > 86400 * 7:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_dir_size(path: Path, cancel_event: Optional[threading.Event] = None) -> int:
    """Calculate the total size of a directory in bytes."""
    total = 0
    try:
        if not path.exists():
            return 0
        if path.is_file():
            return path.stat().st_size

        for root, dirs, files in os.walk(path):
            if cancel_event and cancel_event.is_set():
                break
            for f in files:
                fp = os.path.join(root, f)
                try:
                    if not os.path.islink(fp):
                        total += os.path.getsize(fp)
                except (OSError, FileNotFoundError):
                    continue
    except Exception as e:
        print(f"[Utils] Error calculating size for {path}: {e}")
    return total


class SpeedTracker:
    """Tracks moving average transfer speed and estimated time remaining."""

    def __init__(self, window_seconds: float = 1.5):
        self.window_seconds = window_seconds
        self.samples: List[Tuple[float, int]] = []
        self._lock = threading.Lock()

    def add_sample(self, total_bytes_copied: int) -> None:
        now = time.time()
        with self._lock:
            self.samples.append((now, total_bytes_copied))
            # Prune older than window
            cutoff = now - self.window_seconds
            while len(self.samples) > 2 and self.samples[0][0] < cutoff:
                self.samples.pop(0)

    def get_speed(self) -> float:
        """Returns bytes/sec."""
        with self._lock:
            if len(self.samples) < 2:
                return 0.0
            dt = self.samples[-1][0] - self.samples[0][0]
            if dt <= 0:
                return 0.0
            db = self.samples[-1][1] - self.samples[0][1]
            return max(0.0, db / dt)


def copy_file_chunked(
    src: Path,
    dst: Path,
    progress_callback: Optional[Callable[[int, int, str, float], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    overall_copied: int = 0,
    overall_total: int = 0,
    speed_tracker: Optional[SpeedTracker] = None,
) -> Tuple[bool, int]:
    """
    Copy a single file in chunks with thread-safe cancellation and progress reporting.

    Returns:
        (success: bool, bytes_copied_in_this_file: int)
    """
    if cancel_event and cancel_event.is_set():
        return False, 0

    dst.parent.mkdir(parents=True, exist_ok=True)
    bytes_this_file = 0

    try:
        file_size = src.stat().st_size
    except Exception:
        file_size = 0

    try:
        with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
            while True:
                if cancel_event and cancel_event.is_set():
                    # Abort: delete incomplete file
                    fdst.close()
                    fsrc.close()
                    try:
                        dst.unlink()
                    except Exception:
                        pass
                    return False, bytes_this_file

                buf = fsrc.read(COPY_CHUNK_SIZE)
                if not buf:
                    break

                fdst.write(buf)
                bytes_this_file += len(buf)

                if speed_tracker:
                    speed_tracker.add_sample(overall_copied + bytes_this_file)
                    speed = speed_tracker.get_speed()
                else:
                    speed = 0.0

                if progress_callback:
                    progress_callback(
                        overall_copied + bytes_this_file,
                        overall_total,
                        src.name,
                        speed,
                    )

        # Copy timestamps / stats
        try:
            shutil.copystat(src, dst)
        except Exception:
            pass

        return True, bytes_this_file

    except Exception as e:
        print(f"[Utils] Error copying {src} -> {dst}: {e}")
        try:
            if dst.exists():
                dst.unlink()
        except Exception:
            pass
        return False, bytes_this_file


def copy_tree_with_progress(
    src_dir: Path,
    dst_dir: Path,
    progress_callback: Optional[Callable[[int, int, str, float], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    initial_copied: int = 0,
    overall_total: int = 0,
) -> Tuple[bool, int]:
    """
    Copy an entire directory tree recursively with chunked copying,
    granular progress updates, and responsive cancellation.

    Returns:
        (success: bool, total_bytes_copied: int)
    """
    if cancel_event and cancel_event.is_set():
        return False, 0

    src_dir = Path(src_dir)
    dst_dir = Path(dst_dir)

    if not src_dir.exists():
        if log_callback:
            log_callback(f"Source directory does not exist: {src_dir}")
        return False, 0

    # Collect all files to copy
    file_list: List[Tuple[Path, Path]] = []
    tree_size = 0

    for root, dirs, files in os.walk(src_dir):
        if cancel_event and cancel_event.is_set():
            return False, 0
        rel_path = Path(root).relative_to(src_dir)
        target_dir = dst_dir / rel_path
        target_dir.mkdir(parents=True, exist_ok=True)

        for f in files:
            source_file = Path(root) / f
            dest_file = target_dir / f
            file_list.append((source_file, dest_file))
            try:
                tree_size += source_file.stat().st_size
            except Exception:
                pass

    total_bytes = overall_total if overall_total > 0 else tree_size
    current_copied = initial_copied
    speed_tracker = SpeedTracker()

    for src_file, dst_file in file_list:
        if cancel_event and cancel_event.is_set():
            if log_callback:
                log_callback(f"Copy cancelled: {src_file.name}")
            return False, current_copied - initial_copied

        success, copied_in_file = copy_file_chunked(
            src=src_file,
            dst=dst_file,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
            overall_copied=current_copied,
            overall_total=total_bytes,
            speed_tracker=speed_tracker,
        )

        if not success:
            if cancel_event and cancel_event.is_set():
                return False, current_copied - initial_copied
            if log_callback:
                log_callback(f"Failed to copy file: {src_file}")

        current_copied += copied_in_file

    return True, current_copied - initial_copied
