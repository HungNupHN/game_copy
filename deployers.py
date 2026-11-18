"""
PC Reviewer Deployer Modules:
1. Steam Game Deployer: Scans .acf files, checks common folders, copies games & manifests.
2. Riot Games Deployer: Scans LoL & Valorant, copies game folders, creates/patches YAML configs.
3. Silent App Installer: Scans .exe/.msi, runs sequential silent installs with cancellation.
"""

import os
import re
import sys
import time
import subprocess
import threading
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Callable, Any

from utils import (
    copy_file_chunked,
    copy_tree_with_progress,
    get_dir_size,
    format_bytes,
    to_forward_slashes,
)


# ==============================================================================
# Module 1: Steam Game Deployer
# ==============================================================================

class SteamDeployer:
    """Handles Steam game detection, metadata extraction from ACF files, and deployment."""

    @staticmethod
    def parse_acf(acf_path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse Valve KeyValues (ACF) format to extract game details.
        Extracts: appid, name, installdir, SizeOnDisk.
        """
        try:
            content = acf_path.read_text(encoding="utf-8", errors="ignore")

            name_match = re.search(r'"name"\s+"([^"]+)"', content)
            installdir_match = re.search(r'"installdir"\s+"([^"]+)"', content)
            size_match = re.search(r'"SizeOnDisk"\s+"([^"]+)"', content)
            appid_match = re.search(r'"appid"\s+"([^"]+)"', content)

            if not name_match or not installdir_match:
                return None

            name = name_match.group(1).strip()
            installdir = installdir_match.group(1).strip()
            appid = appid_match.group(1).strip() if appid_match else acf_path.stem.replace("appmanifest_", "")

            size_bytes = 0
            if size_match:
                try:
                    size_bytes = int(size_match.group(1).strip())
                except ValueError:
                    size_bytes = 0

            return {
                "name": name,
                "installdir": installdir,
                "size_bytes": size_bytes,
                "size_gb": round(size_bytes / (1024 ** 3), 2),
                "appid": appid,
                "acf_path": acf_path,
            }
        except Exception as e:
            print(f"[SteamDeployer] Failed to parse {acf_path}: {e}")
            return None

    @classmethod
    def scan(cls, source_dir: Path, cancel_event: Optional[threading.Event] = None) -> List[Dict[str, Any]]:
        """
        Scan source directory for Steam games.
        Supports both library root (containing steamapps/) or direct steamapps/ folder.
        Verifies steamapps/common/<installdir> exists.
        """
        source_dir = Path(source_dir)
        if not source_dir.exists():
            return []

        # Locate steamapps folder
        if source_dir.name.lower() == "steamapps":
            steamapps_dir = source_dir
        elif (source_dir / "steamapps").is_dir():
            steamapps_dir = source_dir / "steamapps"
        else:
            steamapps_dir = source_dir

        common_dir = steamapps_dir / "common"
        acf_files = list(steamapps_dir.glob("*.acf"))
        games: List[Dict[str, Any]] = []

        for acf in acf_files:
            if cancel_event and cancel_event.is_set():
                break

            data = cls.parse_acf(acf)
            if not data:
                continue

            installdir = data["installdir"]
            game_common_path = common_dir / installdir

            # Verify common/<installdir> exists
            if not game_common_path.exists():
                # Some games might be directly in common without exact case match
                matched = False
                if common_dir.exists():
                    for item in common_dir.iterdir():
                        if item.name.lower() == installdir.lower():
                            game_common_path = item
                            matched = True
                            break
                if not matched:
                    # Skip games whose common folder is missing
                    continue

            # If SizeOnDisk was 0 or missing, calculate actual size
            if data["size_bytes"] == 0 and game_common_path.exists():
                actual_bytes = get_dir_size(game_common_path, cancel_event=cancel_event)
                data["size_bytes"] = actual_bytes
                data["size_gb"] = round(actual_bytes / (1024 ** 3), 2)

            data["common_path"] = game_common_path
            games.append(data)

        # Sort alphabetically by default
        games.sort(key=lambda g: g["name"].lower())
        return games

    @staticmethod
    def deploy_single_game(
        game: Dict[str, Any],
        dest_dir: Path,
        progress_callback: Optional[Callable[[int, int, str, float], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
        initial_copied: int = 0,
        overall_total: int = 0,
    ) -> Tuple[bool, int]:
        """
        Deploy a single Steam game:
        1. Copy appmanifest_*.acf to dest_dir/steamapps/
        2. Copy common/<installdir> to dest_dir/steamapps/common/<installdir>
        """
        dest_dir = Path(dest_dir)
        dest_steamapps = dest_dir / "steamapps"
        dest_common = dest_steamapps / "common" / game["installdir"]

        dest_steamapps.mkdir(parents=True, exist_ok=True)
        dest_common.mkdir(parents=True, exist_ok=True)

        acf_src: Path = game["acf_path"]
        acf_dst = dest_steamapps / acf_src.name

        if log_callback:
            log_callback(f"[Steam] Deploying {game['name']} ({format_bytes(game['size_bytes'])}) to {dest_common}...")

        # 1. Copy ACF file
        ok, acf_bytes = copy_file_chunked(
            src=acf_src,
            dst=acf_dst,
            cancel_event=cancel_event,
        )
        if not ok:
            if log_callback:
                log_callback(f"[Steam] Cancelled or failed to copy manifest {acf_src.name}")
            return False, 0

        # 2. Copy game folder
        src_common: Path = game["common_path"]
        ok, folder_bytes = copy_tree_with_progress(
            src_dir=src_common,
            dst_dir=dest_common,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
            log_callback=log_callback,
            initial_copied=initial_copied + acf_bytes,
            overall_total=overall_total,
        )

        total_game_copied = acf_bytes + folder_bytes
        if ok and log_callback:
            log_callback(f"[Steam] Successfully deployed {game['name']}!")

        return ok, total_game_copied


# ==============================================================================
# Module 2: Riot Games Deployer
# ==============================================================================

class RiotDeployer:
    """
    Handles scanning for League of Legends and VALORANT, copying folders,
    and creating/patching Riot client metadata YAML configuration files.
    """

    METADATA_BASE = Path(r"C:\ProgramData\Riot Games\Metadata")

    @classmethod
    def scan(cls, source_dir: Path, cancel_event: Optional[threading.Event] = None) -> List[Dict[str, Any]]:
        """
        Scan source folder for League of Legends and VALORANT folders.
        Calculates size on disk in GB.
        """
        source_dir = Path(source_dir)
        if not source_dir.exists():
            return []

        games: List[Dict[str, Any]] = []

        # Check candidate folders
        candidates: List[Path] = []
        if source_dir.is_dir():
            # Check source directory itself
            candidates.append(source_dir)
            # Check direct subfolders
            try:
                for item in source_dir.iterdir():
                    if item.is_dir():
                        candidates.append(item)
            except Exception:
                pass

        found_lol = False
        found_val = False

        for folder in candidates:
            if cancel_event and cancel_event.is_set():
                break

            folder_name = folder.name.lower()

            # Detect League of Legends
            if not found_lol and ("league of legends" in folder_name or folder_name == "lol"):
                size = get_dir_size(folder, cancel_event=cancel_event)
                games.append({
                    "id": "league_of_legends",
                    "name": "League of Legends",
                    "path": folder,
                    "target_subfolder": "League of Legends",
                    "size_bytes": size,
                    "size_gb": round(size / (1024 ** 3), 2),
                })
                found_lol = True

            # Detect VALORANT
            elif not found_val and "valorant" in folder_name:
                size = get_dir_size(folder, cancel_event=cancel_event)
                games.append({
                    "id": "valorant",
                    "name": "VALORANT",
                    "path": folder,
                    "target_subfolder": "VALORANT",
                    "size_bytes": size,
                    "size_gb": round(size / (1024 ** 3), 2),
                })
                found_val = True

        return games

    @classmethod
    def patch_yaml_config(
        cls,
        game_id: str,
        dest_root: Path,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """
        Create or patch YAML config at:
        C:\\ProgramData\\Riot Games\\Metadata\\<game>.live\\<game>.live.product_settings.yaml
        Updates product_install_full_path (append /live for VALORANT) and product_install_root using forward slashes.
        """
        game_id_clean = game_id.lower()
        metadata_dir = cls.METADATA_BASE / f"{game_id_clean}.live"
        yaml_file = metadata_dir / f"{game_id_clean}.live.product_settings.yaml"

        # Format paths with forward slashes
        dest_fwd = to_forward_slashes(dest_root).rstrip("/")

        if game_id_clean == "valorant":
            # For VALORANT:
            # product_install_root: "C:/Riot Games/"
            # product_install_full_path: "C:/Riot Games/VALORANT/live"
            product_install_root = f"{dest_fwd}/"
            product_install_full_path = f"{dest_fwd}/VALORANT/live"
        else:
            # For League of Legends:
            # product_install_root: "C:/Riot Games/League of Legends/"
            # product_install_full_path: "C:/Riot Games/League of Legends/League of Legends"
            product_install_root = f"{dest_fwd}/League of Legends/"
            product_install_full_path = f"{dest_fwd}/League of Legends/League of Legends"

        try:
            metadata_dir.mkdir(parents=True, exist_ok=True)

            if yaml_file.exists():
                content = yaml_file.read_text(encoding="utf-8", errors="ignore")

                # Update product_install_full_path
                if re.search(r"^product_install_full_path:\s*.*$", content, flags=re.MULTILINE):
                    content = re.sub(
                        r"^product_install_full_path:\s*.*$",
                        f'product_install_full_path: "{product_install_full_path}"',
                        content,
                        flags=re.MULTILINE,
                    )
                else:
                    content += f'\nproduct_install_full_path: "{product_install_full_path}"'

                # Update product_install_root
                if re.search(r"^product_install_root:\s*.*$", content, flags=re.MULTILINE):
                    content = re.sub(
                        r"^product_install_root:\s*.*$",
                        f'product_install_root: "{product_install_root}"',
                        content,
                        flags=re.MULTILINE,
                    )
                else:
                    content += f'\nproduct_install_root: "{product_install_root}"'

                yaml_file.write_text(content, encoding="utf-8")
                if log_callback:
                    log_callback(f"[Riot] Patched existing metadata YAML at {yaml_file}")

            else:
                # Generate standard Riot YAML template
                if game_id_clean == "valorant":
                    new_yaml = f"""auto_patching_enabled_by_player: false
dependencies:
    DirectX:
        hash: "57c765aa8e8e03249aa3c11cc1ea611fe4fffe2364ccabc81ce467eb0c12b3d1"
        phase: "Succeeded"
        version: "1.0.0"
    vanguard: true
locale_data:
    available_locales:
    - "en_US"
    - "vi_VN"
    default_locale: "en_US"
patching_policy: "manual"
patchline_patching_ask_policy: "ask"
product_install_full_path: "{product_install_full_path}"
product_install_root: "{product_install_root}"
settings:
    create_shortcut: true
    create_uninstall_key: true
    locale: "en_US"
shortcut_name: "VALORANT.lnk"
should_repair: false
"""
                else:
                    new_yaml = f"""auto_patching_enabled_by_player: false
dependencies:
    Direct X 9:
        hash: ""
        phase: "Imported"
        version: "1.0.0"
    Microsoft Visual C++ Redistributable x64:
        hash: ""
        phase: "NotInstalled"
        version: ""
    vanguard: true
locale_data:
    available_locales:
    - "en_US"
    - "vi_VN"
    default_locale: "en_US"
patching_policy: "manual"
patchline_patching_ask_policy: "ask"
product_dependency: "teamfighttactics.live"
product_install_full_path: "{product_install_full_path}"
product_install_root: "{product_install_root}"
settings:
    create_uninstall_key: true
    locale: "en_US"
should_repair: false
"""
                yaml_file.write_text(new_yaml, encoding="utf-8")
                if log_callback:
                    log_callback(f"[Riot] Created new metadata YAML at {yaml_file}")

            return True

        except Exception as e:
            if log_callback:
                log_callback(f"[Riot] Warning: Failed to patch Riot YAML config: {e}")
            return False

    @classmethod
    def deploy_single_game(
        cls,
        game: Dict[str, Any],
        dest_dir: Path,
        progress_callback: Optional[Callable[[int, int, str, float], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
        initial_copied: int = 0,
        overall_total: int = 0,
    ) -> Tuple[bool, int]:
        """Deploy Riot game folder and update metadata YAML."""
        dest_dir = Path(dest_dir)
        target_folder = dest_dir / game["target_subfolder"]
        src_folder: Path = game["path"]

        if log_callback:
            log_callback(f"[Riot] Copying {game['name']} ({format_bytes(game['size_bytes'])}) to {target_folder}...")

        ok, copied_bytes = copy_tree_with_progress(
            src_dir=src_folder,
            dst_dir=target_folder,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
            log_callback=log_callback,
            initial_copied=initial_copied,
            overall_total=overall_total,
        )

        if not ok:
            return False, copied_bytes

        # Patch YAML
        cls.patch_yaml_config(game["id"], dest_dir, log_callback=log_callback)

        if log_callback:
            log_callback(f"[Riot] Successfully deployed {game['name']}!")

        return True, copied_bytes


# ==============================================================================
# Module 3: Silent App Installer
# ==============================================================================

class SilentAppInstaller:
    """
    Scans for .exe and .msi installers and performs sequential silent installations.
    Parameters:
      - .msi: msiexec.exe /i "<file>" /qn /norestart
      - .exe: "<file>" /S
    """

    @staticmethod
    def scan(source_dir: Path) -> List[Dict[str, Any]]:
        """Scan directory for .exe and .msi files."""
        source_dir = Path(source_dir)
        if not source_dir.exists():
            return []

        installers: List[Dict[str, Any]] = []

        for item in source_dir.iterdir():
            if item.is_file():
                ext = item.suffix.lower()
                if ext in [".exe", ".msi"]:
                    size_bytes = item.stat().st_size
                    size_mb = round(size_bytes / (1024 * 1024), 2)
                    file_type = "MSI" if ext == ".msi" else "EXE"

                    cmd_preview = (
                        f'msiexec.exe /i "{item.name}" /qn /norestart'
                        if ext == ".msi"
                        else f'"{item.name}" /S'
                    )

                    installers.append({
                        "name": item.name,
                        "path": item,
                        "type": file_type,
                        "size_bytes": size_bytes,
                        "size_mb": size_mb,
                        "cmd_preview": cmd_preview,
                    })

        installers.sort(key=lambda x: x["name"].lower())
        return installers

    @staticmethod
    def run_single_installer(
        item: Dict[str, Any],
        log_callback: Optional[Callable[[str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Tuple[bool, str]:
        """
        Run a single installer silently with process termination support on cancel.
        """
        if cancel_event and cancel_event.is_set():
            return False, "Cancelled"

        installer_path: Path = item["path"]
        ext = installer_path.suffix.lower()

        if ext == ".msi":
            cmd = ["msiexec.exe", "/i", str(installer_path), "/qn", "/norestart"]
        else:
            cmd = [str(installer_path), "/S"]

        cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        if log_callback:
            log_callback(f"[Installer] Executing: {cmd_str}")

        try:
            # Launch without console window
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            # Wait with cancel polling
            while proc.poll() is None:
                if cancel_event and cancel_event.is_set():
                    if log_callback:
                        log_callback(f"[Installer] Terminating {installer_path.name}...")
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    return False, "Installation cancelled by user."
                time.sleep(0.3)

            exit_code = proc.returncode
            if exit_code in [0, 3010]:  # 3010 is ERROR_SUCCESS_REBOOT_REQUIRED in MSI
                msg = f"Completed successfully (Exit code: {exit_code})"
                if log_callback:
                    log_callback(f"[Installer] ✓ {installer_path.name}: {msg}")
                return True, msg
            else:
                msg = f"Failed with exit code {exit_code}"
                if log_callback:
                    log_callback(f"[Installer] ✗ {installer_path.name}: {msg}")
                return False, msg

        except Exception as e:
            msg = f"Execution error: {e}"
            if log_callback:
                log_callback(f"[Installer] ✗ {installer_path.name}: {msg}")
            return False, msg
