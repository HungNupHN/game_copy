"""
Authentication, Authorization, and Self-Update Module for PC Reviewer Deployer.
Handles remote JSON fetching, kill switch enforcement, license key validation,
and seamless executable self-updating on Windows.
"""

import os
import sys
import time
import subprocess
import threading
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Callable
import requests

CURRENT_VERSION = "1.0"
AUTH_URL = "https://raw.githubusercontent.com/HungNupHN/Gamecopy/refs/heads/main/auth.json"


def parse_version(ver_str: str) -> Tuple[int, ...]:
    """Parse version string like '1.0' or '1.2.3' into a comparable tuple of integers."""
    if not ver_str:
        return (0,)
    parts = []
    for p in ver_str.strip().split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def cleanup_old_exe() -> None:
    """Cleanup any .exe.old left behind from a previous self-update on startup."""
    try:
        exe_path = Path(sys.executable)
        old_exe = exe_path.with_suffix(".exe.old")
        if old_exe.exists():
            # Give OS file handles a quick moment if freshly launched
            for _ in range(3):
                try:
                    old_exe.unlink()
                    print(f"[Auth] Cleaned up old executable: {old_exe}")
                    break
                except Exception:
                    time.sleep(0.5)
    except Exception as e:
        print(f"[Auth] Warning: Could not clean up old executable: {e}")


class AuthManager:
    """Manages online authentication, kill-switch checks, and license verification."""

    def __init__(self, auth_url: str = AUTH_URL):
        self.auth_url = auth_url
        self._lock = threading.Lock()
        self.cached_auth_data: Optional[Dict[str, Any]] = None

    def fetch_auth_data(self, force_refresh: bool = False, max_retries: int = 3) -> Dict[str, Any]:
        """
        Fetch remote auth JSON with cache-busting headers and query parameters.
        Includes exponential backoff retry.
        """
        with self._lock:
            if self.cached_auth_data and not force_refresh:
                return self.cached_auth_data

            last_error: Optional[Exception] = None
            headers = {
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "User-Agent": "PC-Reviewer-Deployer/1.0",
            }
            params = {"_nocache": int(time.time() * 1000)}

            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        time.sleep(1.5 * (attempt ** 1.5))

                    resp = requests.get(
                        self.auth_url,
                        headers=headers,
                        params=params,
                        timeout=12,
                        verify=True,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    self.cached_auth_data = data
                    return data

                except Exception as e:
                    last_error = e
                    print(f"[Auth] Attempt {attempt + 1}/{max_retries} failed: {e}")

            raise RuntimeError(f"Unable to reach authentication server: {last_error}")

    def check_kill_switch(self, auth_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Check if global_status is active.

        Returns:
            (is_active: bool, message: str)
            If is_active is False, app must terminate immediately.
        """
        if auth_data is None:
            auth_data = self.fetch_auth_data()

        status = auth_data.get("global_status", "").lower()
        msg = auth_data.get("message", "App is currently unavailable.")

        if status != "active":
            return False, msg
        return True, "Active"

    def check_update(self, auth_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, str]:
        """
        Check if a newer version is available.

        Returns:
            (is_newer: bool, latest_version: str, download_url: str)
        """
        if auth_data is None:
            auth_data = self.fetch_auth_data()

        latest_version = str(auth_data.get("latest_version", CURRENT_VERSION)).strip()
        download_url = str(auth_data.get("download_url", "")).strip()

        is_newer = parse_version(latest_version) > parse_version(CURRENT_VERSION)
        return is_newer, latest_version, download_url

    def validate_key(self, license_key: str, auth_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validate license key against valid_keys in remote JSON.
        """
        if not license_key or not license_key.strip():
            return False

        if auth_data is None:
            auth_data = self.fetch_auth_data()

        valid_keys = auth_data.get("valid_keys", [])
        if isinstance(valid_keys, list):
            valid_keys_str = [str(k).strip() for k in valid_keys]
            return license_key.strip() in valid_keys_str
        elif isinstance(valid_keys, str):
            return license_key.strip() == valid_keys.strip()

        return False


class SelfUpdater:
    """Handles downloading and applying self-updates seamlessly on Windows."""

    @staticmethod
    def normalize_download_url(url: str) -> str:
        """Ensure GitHub URLs link to raw binary rather than the HTML viewer."""
        if "github.com" in url and "/blob/" in url:
            # Replace /blob/ with /raw/
            url = url.replace("/blob/", "/raw/")
        return url

    @classmethod
    def download_and_apply_update(
        cls,
        download_url: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Tuple[bool, str]:
        """
        Download new .exe from download_url with progress reporting,
        rename running .exe to .exe.old, rename new file to original .exe,
        restart app, and cleanup .exe.old on next launch.

        Returns:
            (success: bool, status_message: str)
        """
        url = cls.normalize_download_url(download_url)
        is_frozen = getattr(sys, "frozen", False)
        exe_path = Path(sys.executable).resolve()

        if is_frozen:
            dest_dir = exe_path.parent
            temp_new_file = dest_dir / f"{exe_path.stem}_update_{int(time.time())}.exe"
            old_exe_file = exe_path.with_suffix(".exe.old")
        else:
            dest_dir = Path.cwd()
            temp_new_file = dest_dir / f"update_test_{int(time.time())}.exe"
            old_exe_file = dest_dir / "update_test.exe.old"

        try:
            # Stream download
            headers = {"User-Agent": "PC-Reviewer-Deployer-Updater/1.0"}
            resp = requests.get(url, stream=True, headers=headers, timeout=30, allow_redirects=True)
            resp.raise_for_status()

            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 64 * 1024

            with open(temp_new_file, "wb") as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if cancel_event and cancel_event.is_set():
                        f.close()
                        temp_new_file.unlink(missing_ok=True)
                        return False, "Update cancelled by user."

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size, "Downloading update...")

            # If running in development (not frozen as PyInstaller executable)
            if not is_frozen:
                temp_new_file.unlink(missing_ok=True)
                return True, "Development mode: executable replacement skipped."

            # Windows Executable Replacement:
            # 1. Clean existing .old if present
            if old_exe_file.exists():
                try:
                    old_exe_file.unlink()
                except Exception as e:
                    print(f"[Updater] Warning: could not remove existing old exe: {e}")

            # 2. Rename running .exe to .exe.old
            try:
                exe_path.rename(old_exe_file)
            except Exception as e:
                temp_new_file.unlink(missing_ok=True)
                return False, f"Failed to rename running executable: {e}"

            # 3. Rename new file to original .exe
            try:
                temp_new_file.rename(exe_path)
            except Exception as e:
                # Rollback
                try:
                    old_exe_file.rename(exe_path)
                except Exception:
                    pass
                temp_new_file.unlink(missing_ok=True)
                return False, f"Failed to place new executable: {e}"

            # 4. Restart app
            try:
                subprocess.Popen([str(exe_path)] + sys.argv[1:])
            except Exception as e:
                return False, f"Failed to restart application: {e}"

            # 5. Terminate current process
            sys.exit(0)

        except Exception as e:
            if temp_new_file.exists():
                try:
                    temp_new_file.unlink()
                except Exception:
                    pass
            return False, f"Update failed: {e}"
