"""
Configuration Management Module for PC Reviewer Deployer.
Handles local persistence of user paths, license keys, and app settings.
"""

import os
import sys
import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigManager:
    """Thread-safe configuration manager with atomic file persistence."""

    def __init__(self, config_path: Optional[Path] = None):
        self._lock = threading.Lock()
        self._defaults: Dict[str, Any] = {
            "steam_source": "",
            "steam_dest": "C:/Program Files (x86)/Steam",
            "riot_source": "",
            "riot_dest": "C:/Riot Games",
            "app_source": "",
            "license_key": "",
            "app_version": "1.0",
            "theme": "dark",
        }
        self._data: Dict[str, Any] = {}

        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = self._resolve_config_path()

        self._ensure_loaded()

    def _resolve_config_path(self) -> Path:
        """Resolve a writable path for configuration."""
        # 1. Try APPDATA
        appdata_dir = os.environ.get("APPDATA")
        if appdata_dir:
            candidate = Path(appdata_dir) / "GameDeployer" / "config.json"
            try:
                candidate.parent.mkdir(parents=True, exist_ok=True)
                # Test write permission
                test_file = candidate.parent / ".perm_test"
                test_file.touch()
                test_file.unlink()
                return candidate
            except Exception:
                pass

        # 2. Try adjacent to executable or script
        try:
            exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
            candidate = exe_dir / "config.json"
            test_file = candidate.parent / ".perm_test"
            test_file.touch()
            test_file.unlink()
            return candidate
        except Exception:
            pass

        # 3. Fallback to current working directory
        return Path.cwd() / "config.json"

    def _ensure_loaded(self) -> None:
        """Create directories and load or create config file."""
        with self._lock:
            try:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                if self.config_path.exists():
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        self._data = {**self._defaults, **loaded}
                else:
                    self._data = dict(self._defaults)
                    self._save_internal()
            except Exception as e:
                print(f"[Config] Error initializing config at {self.config_path}: {e}")
                self._data = dict(self._defaults)

    def _save_internal(self) -> None:
        """Internal save method without acquiring lock (assumes caller holds it)."""
        temp_file = self.config_path.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            temp_file.replace(self.config_path)
        except Exception as e:
            print(f"[Config] Failed to save config to {self.config_path}: {e}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        with self._lock:
            return self._data.get(key, default if default is not None else self._defaults.get(key))

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value and save to disk."""
        with self._lock:
            self._data[key] = value
            self._save_internal()

    def update(self, mapping: Dict[str, Any]) -> None:
        """Update multiple configuration values and save to disk."""
        with self._lock:
            self._data.update(mapping)
            self._save_internal()

    # Convenience properties
    @property
    def steam_source(self) -> str:
        return self.get("steam_source", "")

    @steam_source.setter
    def steam_source(self, val: str) -> None:
        self.set("steam_source", val)

    @property
    def steam_dest(self) -> str:
        return self.get("steam_dest", "C:/Program Files (x86)/Steam")

    @steam_dest.setter
    def steam_dest(self, val: str) -> None:
        self.set("steam_dest", val)

    @property
    def riot_source(self) -> str:
        return self.get("riot_source", "")

    @riot_source.setter
    def riot_source(self, val: str) -> None:
        self.set("riot_source", val)

    @property
    def riot_dest(self) -> str:
        return self.get("riot_dest", "C:/Riot Games")

    @riot_dest.setter
    def riot_dest(self, val: str) -> None:
        self.set("riot_dest", val)

    @property
    def app_source(self) -> str:
        return self.get("app_source", "")

    @app_source.setter
    def app_source(self, val: str) -> None:
        self.set("app_source", val)

    @property
    def license_key(self) -> str:
        return self.get("license_key", "")

    @license_key.setter
    def license_key(self, val: str) -> None:
        self.set("license_key", val.strip())
