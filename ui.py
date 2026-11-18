"""
User Interface Module for PC Reviewer Deployer.
Built with CustomTkinter for a modern, sleek, dark-themed Windows desktop application.
Fully thread-safe with non-blocking workers and global progress/cancel controls.
"""

import os
import sys
import time
import queue
import threading
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from tkinter import filedialog, messagebox

import customtkinter as ctk

from config import ConfigManager
from auth import AuthManager, SelfUpdater, CURRENT_VERSION
from deployers import SteamDeployer, RiotDeployer, SilentAppInstaller
from utils import format_bytes, format_speed, format_eta, is_admin

# Theme setup
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    """Main Application Window for PC Reviewer Deployer."""

    def __init__(self):
        super().__init__()

        self.title(f"PC Reviewer Deployer v{CURRENT_VERSION}")
        self.geometry("1024x720")
        self.minsize(880, 600)

        # Core state
        self.config = ConfigManager()
        self.auth_mgr = AuthManager()
        self.cancel_event = threading.Event()
        self.is_busy = False

        # Data caches for UI tables
        self.steam_games: List[Dict[str, Any]] = []
        self.steam_checkboxes: Dict[str, ctk.CTkCheckBox] = {}
        self.steam_sort_col = "name"
        self.steam_sort_asc = True

        self.riot_games: List[Dict[str, Any]] = []
        self.riot_checkboxes: Dict[str, ctk.CTkCheckBox] = {}
        self.riot_sort_col = "name"
        self.riot_sort_asc = True

        self.app_installers: List[Dict[str, Any]] = []
        self.app_checkboxes: Dict[str, ctk.CTkCheckBox] = {}
        self.app_sort_col = "name"
        self.app_sort_asc = True

        # Build UI layout
        self._build_header()
        self._build_tabview()
        self._build_bottom_bar()

        # Start background auth & update check after UI is shown
        self.after(200, self._start_auth_and_update_check)

    # --------------------------------------------------------------------------
    # UI Building Blocks
    # --------------------------------------------------------------------------

    def _build_header(self) -> None:
        """Build top navigation header with title and status badges."""
        self.header_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray85", "#1A1C1E"))
        self.header_frame.pack(fill="x", padx=0, pady=0)

        # Left title
        title_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_box.pack(side="left", padx=16, pady=10)

        main_title = ctk.CTkLabel(
            title_box,
            text="⚡ PC Reviewer Deployer",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=("gray10", "#FFFFFF"),
        )
        main_title.pack(anchor="w")

        sub_title = ctk.CTkLabel(
            title_box,
            text="Fast Game & Silent Software Deployment Suite",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "#A0A0A0"),
        )
        sub_title.pack(anchor="w")

        # Right badges
        badge_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        badge_box.pack(side="right", padx=16, pady=10)

        self.version_badge = ctk.CTkLabel(
            badge_box,
            text=f"v{CURRENT_VERSION}",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("gray75", "#2D3139"),
            corner_radius=6,
            padx=10,
            pady=4,
        )
        self.version_badge.pack(side="right", padx=5)

        self.status_badge = ctk.CTkLabel(
            badge_box,
            text="● Connecting...",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("gray75", "#3A3520"),
            text_color="#F1C40F",
            corner_radius=6,
            padx=10,
            pady=4,
        )
        self.status_badge.pack(side="right", padx=5)

        if is_admin():
            admin_badge = ctk.CTkLabel(
                badge_box,
                text="ADMIN",
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#2E7D32",
                text_color="#FFFFFF",
                corner_radius=4,
                padx=6,
                pady=2,
            )
            admin_badge.pack(side="right", padx=5)

    def _build_tabview(self) -> None:
        """Build tabbed workspace containing all deployer modules."""
        self.tabview = ctk.CTkTabview(self, corner_radius=8)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(4, 0))

        # Add tabs
        self.tab_steam = self.tabview.add("Steam Deployer")
        self.tab_riot = self.tabview.add("Riot Games Deployer")
        self.tab_apps = self.tabview.add("Silent App Installer")
        self.tab_logs = self.tabview.add("Activity Logs")
        self.tab_settings = self.tabview.add("Settings & License")

        self._build_steam_tab()
        self._build_riot_tab()
        self._build_apps_tab()
        self._build_logs_tab()
        self._build_settings_tab()

    # --------------------------------------------------------------------------
    # Tab 1: Steam Game Deployer
    # --------------------------------------------------------------------------

    def _build_steam_tab(self) -> None:
        """Module 1 UI: Steam Game Deployer."""
        # Top Path Controls
        path_frame = ctk.CTkFrame(self.tab_steam, corner_radius=6)
        path_frame.pack(fill="x", padx=10, pady=8)

        # Source
        ctk.CTkLabel(path_frame, text="Source Library / steamapps:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        self.steam_src_entry = ctk.CTkEntry(path_frame, placeholder_text="Select Steam folder or drive with steamapps/...")
        self.steam_src_entry.insert(0, self.config.steam_source)
        self.steam_src_entry.grid(row=0, column=1, sticky="ew", padx=10, pady=(8, 2))
        ctk.CTkButton(path_frame, text="Browse", width=80, command=self._browse_steam_source).grid(row=0, column=2, padx=10, pady=(8, 2))

        # Dest
        ctk.CTkLabel(path_frame, text="Destination Steam Path:", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, sticky="w", padx=10, pady=(2, 8))
        self.steam_dst_entry = ctk.CTkEntry(path_frame)
        self.steam_dst_entry.insert(0, self.config.steam_dest)
        self.steam_dst_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=(2, 8))
        ctk.CTkButton(path_frame, text="Browse", width=80, command=self._browse_steam_dest).grid(row=1, column=2, padx=10, pady=(2, 8))

        path_frame.columnconfigure(1, weight=1)

        # Action & Filter Bar
        action_bar = ctk.CTkFrame(self.tab_steam, fg_color="transparent")
        action_bar.pack(fill="x", padx=10, pady=4)

        self.btn_steam_scan = ctk.CTkButton(
            action_bar,
            text="🔍 Scan Steam Games",
            command=self._start_scan_steam,
            width=150,
            fg_color="#1F6AA5",
            hover_color="#144870",
        )
        self.btn_steam_scan.pack(side="left", padx=(0, 8))

        self.btn_steam_deploy = ctk.CTkButton(
            action_bar,
            text="🚀 Deploy Selected Games",
            command=self._start_deploy_steam,
            width=180,
            fg_color="#2EA043",
            hover_color="#238636",
        )
        self.btn_steam_deploy.pack(side="left", padx=(0, 8))

        self.steam_search_entry = ctk.CTkEntry(action_bar, placeholder_text="Filter games by name...", width=200)
        self.steam_search_entry.pack(side="right")
        self.steam_search_entry.bind("<KeyRelease>", lambda e: self._render_steam_table())

        self.steam_count_label = ctk.CTkLabel(action_bar, text="0 games found", text_color="gray60")
        self.steam_count_label.pack(side="right", padx=12)

        # Table Header
        header_table = ctk.CTkFrame(self.tab_steam, height=32, corner_radius=4, fg_color=("gray80", "#24272C"))
        header_table.pack(fill="x", padx=10, pady=(4, 0))

        self.steam_select_all_var = ctk.BooleanVar(value=True)
        cb_all = ctk.CTkCheckBox(header_table, text="", variable=self.steam_select_all_var, width=24, command=self._toggle_steam_select_all)
        cb_all.pack(side="left", padx=(10, 5))

        btn_sort_name = ctk.CTkButton(
            header_table,
            text="Game Name ⬍",
            command=lambda: self._sort_steam_table("name"),
            fg_color="transparent",
            hover_color=("gray75", "#333740"),
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        btn_sort_name.pack(side="left", fill="x", expand=True, padx=5)

        btn_sort_size = ctk.CTkButton(
            header_table,
            text="Size (GB) ⬍",
            command=lambda: self._sort_steam_table("size_gb"),
            fg_color="transparent",
            hover_color=("gray75", "#333740"),
            width=100,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        btn_sort_size.pack(side="left", padx=5)

        lbl_dir = ctk.CTkLabel(header_table, text="Install Directory", width=180, font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
        lbl_dir.pack(side="left", padx=5)

        lbl_id = ctk.CTkLabel(header_table, text="App ID", width=80, font=ctk.CTkFont(size=12, weight="bold"), anchor="center")
        lbl_id.pack(side="left", padx=(5, 15))

        # Scrollable rows container
        self.steam_scroll = ctk.CTkScrollableFrame(self.tab_steam, corner_radius=6)
        self.steam_scroll.pack(fill="both", expand=True, padx=10, pady=(2, 8))

    def _browse_steam_source(self) -> None:
        path = filedialog.askdirectory(title="Select Steam Library or steamapps Directory", initialdir=self.config.steam_source or "C:/")
        if path:
            self.steam_src_entry.delete(0, "end")
            self.steam_src_entry.insert(0, path)
            self.config.steam_source = path
            self._start_scan_steam()

    def _browse_steam_dest(self) -> None:
        path = filedialog.askdirectory(title="Select Destination Steam Directory", initialdir=self.config.steam_dest or "C:/Program Files (x86)/Steam")
        if path:
            self.steam_dst_entry.delete(0, "end")
            self.steam_dst_entry.insert(0, path)
            self.config.steam_dest = path

    def _sort_steam_table(self, col: str) -> None:
        if self.steam_sort_col == col:
            self.steam_sort_asc = not self.steam_sort_asc
        else:
            self.steam_sort_col = col
            self.steam_sort_asc = True
        self._render_steam_table()

    def _toggle_steam_select_all(self) -> None:
        val = self.steam_select_all_var.get()
        for cb in self.steam_checkboxes.values():
            if val:
                cb.select()
            else:
                cb.deselect()

    def _render_steam_table(self) -> None:
        """Render Steam table rows based on current cache and filter."""
        # Clear existing rows
        for child in self.steam_scroll.winfo_children():
            child.destroy()
        self.steam_checkboxes.clear()

        query = self.steam_search_entry.get().strip().lower()
        filtered = [g for g in self.steam_games if not query or query in g["name"].lower() or query in g["installdir"].lower()]

        # Sort
        if self.steam_sort_col == "name":
            filtered.sort(key=lambda x: x["name"].lower(), reverse=not self.steam_sort_asc)
        elif self.steam_sort_col == "size_gb":
            filtered.sort(key=lambda x: x["size_bytes"], reverse=not self.steam_sort_asc)

        self.steam_count_label.configure(text=f"{len(filtered)} / {len(self.steam_games)} games")

        if not filtered:
            empty_lbl = ctk.CTkLabel(self.steam_scroll, text="No Steam games found. Select source and click 'Scan Steam Games'.", text_color="gray50")
            empty_lbl.pack(pady=40)
            return

        for idx, game in enumerate(filtered):
            row_bg = ("#F2F2F2", "#1E2024") if idx % 2 == 0 else ("#E8E8E8", "#24272C")
            row = ctk.CTkFrame(self.steam_scroll, fg_color=row_bg, corner_radius=4, height=36)
            row.pack(fill="x", padx=2, pady=2)

            cb_var = ctk.BooleanVar(value=self.steam_select_all_var.get())
            cb = ctk.CTkCheckBox(row, text="", variable=cb_var, width=24)
            cb.pack(side="left", padx=(8, 4))
            self.steam_checkboxes[game["appid"]] = cb

            # Name
            lbl_name = ctk.CTkLabel(row, text=game["name"], anchor="w", font=ctk.CTkFont(size=12))
            lbl_name.pack(side="left", fill="x", expand=True, padx=4)

            # Size
            lbl_size = ctk.CTkLabel(row, text=f"{game['size_gb']:.2f} GB", width=100, anchor="e", font=ctk.CTkFont(size=12, weight="bold"))
            lbl_size.pack(side="left", padx=4)

            # Directory
            lbl_dir = ctk.CTkLabel(row, text=game["installdir"], width=180, anchor="w", text_color="gray70", font=ctk.CTkFont(size=11))
            lbl_dir.pack(side="left", padx=4)

            # App ID
            lbl_id = ctk.CTkLabel(row, text=game["appid"], width=80, anchor="center", text_color="gray60", font=ctk.CTkFont(size=11))
            lbl_id.pack(side="left", padx=(4, 10))

    def _start_scan_steam(self) -> None:
        """Scan Steam library in a background worker."""
        if self.is_busy:
            return

        src = self.steam_src_entry.get().strip()
        if not src:
            messagebox.showwarning("Warning", "Please select a valid Steam source folder.")
            return

        self._set_busy(True, "Scanning Steam library for games...")
        self.btn_steam_scan.configure(state="disabled")

        def worker():
            try:
                games = SteamDeployer.scan(Path(src), cancel_event=self.cancel_event)
                self.after(0, lambda: self._on_steam_scan_complete(games))
            except Exception as e:
                self.after(0, lambda: self._on_operation_error(f"Steam scan error: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_steam_scan_complete(self, games: List[Dict[str, Any]]) -> None:
        self.steam_games = games
        self._render_steam_table()
        self._set_busy(False, f"Found {len(games)} Steam games ready to deploy.")
        self.btn_steam_scan.configure(state="normal")
        self.log(f"Steam scan completed: {len(games)} games detected.")

    def _start_deploy_steam(self) -> None:
        """Deploy selected Steam games in a background worker."""
        if self.is_busy:
            return

        selected = [g for g in self.steam_games if self.steam_checkboxes.get(g["appid"]) and self.steam_checkboxes[g["appid"]].get()]
        if not selected:
            messagebox.showinfo("Select Games", "Please check at least one game to deploy.")
            return

        dst = self.steam_dst_entry.get().strip()
        if not dst:
            messagebox.showwarning("Warning", "Please specify a destination Steam path.")
            return

        # Confirm
        total_bytes = sum(g["size_bytes"] for g in selected)
        if not messagebox.askyesno("Confirm Deployment", f"Deploy {len(selected)} game(s) ({format_bytes(total_bytes)}) to:\n{dst}\n\nProceed?"):
            return

        self.config.steam_dest = dst
        self._set_busy(True, "Starting Steam deployment...")
        self.cancel_event.clear()

        def worker():
            copied_total = 0
            deployed_count = 0

            def prog(c, t, filename, sp):
                pct = (c / total_bytes) if total_bytes > 0 else 0.0
                rem_sec = (total_bytes - c) / sp if sp > 0 else 0
                msg = f"Copying: {filename} ({format_bytes(c)} / {format_bytes(total_bytes)})"
                self.after(0, lambda: self._update_progress_bar(pct, msg, sp, rem_sec))

            for g in selected:
                if self.cancel_event.is_set():
                    break

                self.after(0, lambda name=g["name"]: self.log(f"Deploying {name}..."))
                ok, b = SteamDeployer.deploy_single_game(
                    game=g,
                    dest_dir=Path(dst),
                    progress_callback=prog,
                    log_callback=lambda m: self.after(0, lambda msg=m: self.log(msg)),
                    cancel_event=self.cancel_event,
                    initial_copied=copied_total,
                    overall_total=total_bytes,
                )
                if ok:
                    deployed_count += 1
                    copied_total += b
                else:
                    break

            if self.cancel_event.is_set():
                self.after(0, lambda: self._on_operation_cancelled("Steam deployment cancelled by user."))
            else:
                self.after(0, lambda: self._on_operation_finished(f"Successfully deployed {deployed_count}/{len(selected)} Steam games."))

        threading.Thread(target=worker, daemon=True).start()

    # --------------------------------------------------------------------------
    # Tab 2: Riot Games Deployer
    # --------------------------------------------------------------------------

    def _build_riot_tab(self) -> None:
        """Module 2 UI: Riot Games Deployer."""
        path_frame = ctk.CTkFrame(self.tab_riot, corner_radius=6)
        path_frame.pack(fill="x", padx=10, pady=8)

        # Source
        ctk.CTkLabel(path_frame, text="Source Riot Games Folder:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        self.riot_src_entry = ctk.CTkEntry(path_frame, placeholder_text="Select folder containing League of Legends or VALORANT...")
        self.riot_src_entry.insert(0, self.config.riot_source)
        self.riot_src_entry.grid(row=0, column=1, sticky="ew", padx=10, pady=(8, 2))
        ctk.CTkButton(path_frame, text="Browse", width=80, command=self._browse_riot_source).grid(row=0, column=2, padx=10, pady=(8, 2))

        # Dest
        ctk.CTkLabel(path_frame, text="Destination Path (default C:/Riot Games):", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, sticky="w", padx=10, pady=(2, 8))
        self.riot_dst_entry = ctk.CTkEntry(path_frame)
        self.riot_dst_entry.insert(0, self.config.riot_dest)
        self.riot_dst_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=(2, 8))
        ctk.CTkButton(path_frame, text="Browse", width=80, command=self._browse_riot_dest).grid(row=1, column=2, padx=10, pady=(2, 8))

        path_frame.columnconfigure(1, weight=1)

        # Action Bar & Notice
        action_bar = ctk.CTkFrame(self.tab_riot, fg_color="transparent")
        action_bar.pack(fill="x", padx=10, pady=4)

        self.btn_riot_scan = ctk.CTkButton(
            action_bar,
            text="🔍 Scan Riot Games",
            command=self._start_scan_riot,
            width=150,
            fg_color="#1F6AA5",
            hover_color="#144870",
        )
        self.btn_riot_scan.pack(side="left", padx=(0, 8))

        self.btn_riot_deploy = ctk.CTkButton(
            action_bar,
            text="🚀 Deploy & Patch Configs",
            command=self._start_deploy_riot,
            width=200,
            fg_color="#2EA043",
            hover_color="#238636",
        )
        self.btn_riot_deploy.pack(side="left", padx=(0, 8))

        info_lbl = ctk.CTkLabel(
            action_bar,
            text="ℹ️ Patches C:\\ProgramData\\Riot Games\\Metadata with forward-slash paths (/live for VALORANT).",
            text_color="gray60",
            font=ctk.CTkFont(size=11),
        )
        info_lbl.pack(side="right")

        # Table Header
        header_table = ctk.CTkFrame(self.tab_riot, height=32, corner_radius=4, fg_color=("gray80", "#24272C"))
        header_table.pack(fill="x", padx=10, pady=(4, 0))

        self.riot_select_all_var = ctk.BooleanVar(value=True)
        cb_all = ctk.CTkCheckBox(header_table, text="", variable=self.riot_select_all_var, width=24, command=self._toggle_riot_select_all)
        cb_all.pack(side="left", padx=(10, 5))

        btn_sort_name = ctk.CTkButton(
            header_table,
            text="Game Name ⬍",
            command=lambda: self._sort_riot_table("name"),
            fg_color="transparent",
            hover_color=("gray75", "#333740"),
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        btn_sort_name.pack(side="left", fill="x", expand=True, padx=5)

        btn_sort_size = ctk.CTkButton(
            header_table,
            text="Size (GB) ⬍",
            command=lambda: self._sort_riot_table("size_gb"),
            fg_color="transparent",
            hover_color=("gray75", "#333740"),
            width=100,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        btn_sort_size.pack(side="left", padx=5)

        lbl_target = ctk.CTkLabel(header_table, text="Target Subfolder", width=180, font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
        lbl_target.pack(side="left", padx=5)

        lbl_status = ctk.CTkLabel(header_table, text="Metadata Patch", width=120, font=ctk.CTkFont(size=12, weight="bold"), anchor="center")
        lbl_status.pack(side="left", padx=(5, 15))

        # Scrollable rows
        self.riot_scroll = ctk.CTkScrollableFrame(self.tab_riot, corner_radius=6)
        self.riot_scroll.pack(fill="both", expand=True, padx=10, pady=(2, 8))

    def _browse_riot_source(self) -> None:
        path = filedialog.askdirectory(title="Select Riot Games Source Folder", initialdir=self.config.riot_source or "C:/")
        if path:
            self.riot_src_entry.delete(0, "end")
            self.riot_src_entry.insert(0, path)
            self.config.riot_source = path
            self._start_scan_riot()

    def _browse_riot_dest(self) -> None:
        path = filedialog.askdirectory(title="Select Riot Games Destination Folder", initialdir=self.config.riot_dest or "C:/Riot Games")
        if path:
            self.riot_dst_entry.delete(0, "end")
            self.riot_dst_entry.insert(0, path)
            self.config.riot_dest = path

    def _sort_riot_table(self, col: str) -> None:
        if self.riot_sort_col == col:
            self.riot_sort_asc = not self.riot_sort_asc
        else:
            self.riot_sort_col = col
            self.riot_sort_asc = True
        self._render_riot_table()

    def _toggle_riot_select_all(self) -> None:
        val = self.riot_select_all_var.get()
        for cb in self.riot_checkboxes.values():
            if val:
                cb.select()
            else:
                cb.deselect()

    def _render_riot_table(self) -> None:
        for child in self.riot_scroll.winfo_children():
            child.destroy()
        self.riot_checkboxes.clear()

        sorted_games = list(self.riot_games)
        if self.riot_sort_col == "name":
            sorted_games.sort(key=lambda x: x["name"].lower(), reverse=not self.riot_sort_asc)
        elif self.riot_sort_col == "size_gb":
            sorted_games.sort(key=lambda x: x["size_bytes"], reverse=not self.riot_sort_asc)

        if not sorted_games:
            empty_lbl = ctk.CTkLabel(self.riot_scroll, text="No Riot Games found. Select source and click 'Scan Riot Games'.", text_color="gray50")
            empty_lbl.pack(pady=40)
            return

        for idx, game in enumerate(sorted_games):
            row_bg = ("#F2F2F2", "#1E2024") if idx % 2 == 0 else ("#E8E8E8", "#24272C")
            row = ctk.CTkFrame(self.riot_scroll, fg_color=row_bg, corner_radius=4, height=36)
            row.pack(fill="x", padx=2, pady=2)

            cb_var = ctk.BooleanVar(value=self.riot_select_all_var.get())
            cb = ctk.CTkCheckBox(row, text="", variable=cb_var, width=24)
            cb.pack(side="left", padx=(8, 4))
            self.riot_checkboxes[game["id"]] = cb

            # Name
            lbl_name = ctk.CTkLabel(row, text=game["name"], anchor="w", font=ctk.CTkFont(size=12, weight="bold"))
            lbl_name.pack(side="left", fill="x", expand=True, padx=4)

            # Size
            lbl_size = ctk.CTkLabel(row, text=f"{game['size_gb']:.2f} GB", width=100, anchor="e", font=ctk.CTkFont(size=12, weight="bold"))
            lbl_size.pack(side="left", padx=4)

            # Target
            lbl_target = ctk.CTkLabel(row, text=game["target_subfolder"], width=180, anchor="w", text_color="gray70", font=ctk.CTkFont(size=11))
            lbl_target.pack(side="left", padx=4)

            # Patch badge
            badge_text = "YAML Live"
            lbl_patch = ctk.CTkLabel(row, text=badge_text, width=120, fg_color="#1F6AA5", text_color="#FFFFFF", corner_radius=4, font=ctk.CTkFont(size=10, weight="bold"))
            lbl_patch.pack(side="left", padx=(4, 10))

    def _start_scan_riot(self) -> None:
        if self.is_busy:
            return

        src = self.riot_src_entry.get().strip()
        if not src:
            messagebox.showwarning("Warning", "Please select a Riot Games source folder.")
            return

        self._set_busy(True, "Scanning for League of Legends & VALORANT...")
        self.btn_riot_scan.configure(state="disabled")

        def worker():
            try:
                games = RiotDeployer.scan(Path(src), cancel_event=self.cancel_event)
                self.after(0, lambda: self._on_riot_scan_complete(games))
            except Exception as e:
                self.after(0, lambda: self._on_operation_error(f"Riot scan error: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_riot_scan_complete(self, games: List[Dict[str, Any]]) -> None:
        self.riot_games = games
        self._render_riot_table()
        self._set_busy(False, f"Found {len(games)} Riot Game(s).")
        self.btn_riot_scan.configure(state="normal")
        self.log(f"Riot Games scan finished: {len(games)} title(s) detected.")

    def _start_deploy_riot(self) -> None:
        if self.is_busy:
            return

        selected = [g for g in self.riot_games if self.riot_checkboxes.get(g["id"]) and self.riot_checkboxes[g["id"]].get()]
        if not selected:
            messagebox.showinfo("Select Games", "Please check at least one Riot game to deploy.")
            return

        dst = self.riot_dst_entry.get().strip()
        if not dst:
            messagebox.showwarning("Warning", "Please specify a destination path for Riot Games.")
            return

        total_bytes = sum(g["size_bytes"] for g in selected)
        if not messagebox.askyesno("Confirm Riot Deployment", f"Deploy {len(selected)} Riot game(s) ({format_bytes(total_bytes)}) to:\n{dst}\nand update metadata YAML configs?\n\nProceed?"):
            return

        self.config.riot_dest = dst
        self._set_busy(True, "Deploying Riot Games and patching YAML...")
        self.cancel_event.clear()

        def worker():
            copied_total = 0
            deployed_count = 0

            def prog(c, t, filename, sp):
                pct = (c / total_bytes) if total_bytes > 0 else 0.0
                rem_sec = (total_bytes - c) / sp if sp > 0 else 0
                msg = f"Copying: {filename} ({format_bytes(c)} / {format_bytes(total_bytes)})"
                self.after(0, lambda: self._update_progress_bar(pct, msg, sp, rem_sec))

            for g in selected:
                if self.cancel_event.is_set():
                    break

                self.after(0, lambda name=g["name"]: self.log(f"Deploying {name}..."))
                ok, b = RiotDeployer.deploy_single_game(
                    game=g,
                    dest_dir=Path(dst),
                    progress_callback=prog,
                    log_callback=lambda m: self.after(0, lambda msg=m: self.log(msg)),
                    cancel_event=self.cancel_event,
                    initial_copied=copied_total,
                    overall_total=total_bytes,
                )
                if ok:
                    deployed_count += 1
                    copied_total += b
                else:
                    break

            if self.cancel_event.is_set():
                self.after(0, lambda: self._on_operation_cancelled("Riot deployment cancelled by user."))
            else:
                self.after(0, lambda: self._on_operation_finished(f"Successfully deployed and patched {deployed_count}/{len(selected)} Riot games."))

        threading.Thread(target=worker, daemon=True).start()

    # --------------------------------------------------------------------------
    # Tab 3: Silent App Installer
    # --------------------------------------------------------------------------

    def _build_apps_tab(self) -> None:
        """Module 3 UI: Silent App Installer."""
        path_frame = ctk.CTkFrame(self.tab_apps, corner_radius=6)
        path_frame.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(path_frame, text="Source Installer Folder:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=10, pady=8)
        self.apps_src_entry = ctk.CTkEntry(path_frame, placeholder_text="Select folder containing .exe and .msi setup files...")
        self.apps_src_entry.insert(0, self.config.app_source)
        self.apps_src_entry.grid(row=0, column=1, sticky="ew", padx=10, pady=8)
        ctk.CTkButton(path_frame, text="Browse", width=80, command=self._browse_apps_source).grid(row=0, column=2, padx=10, pady=8)

        path_frame.columnconfigure(1, weight=1)

        # Action Bar & Search
        action_bar = ctk.CTkFrame(self.tab_apps, fg_color="transparent")
        action_bar.pack(fill="x", padx=10, pady=4)

        self.btn_apps_scan = ctk.CTkButton(
            action_bar,
            text="🔍 Scan Installers",
            command=self._start_scan_apps,
            width=150,
            fg_color="#1F6AA5",
            hover_color="#144870",
        )
        self.btn_apps_scan.pack(side="left", padx=(0, 8))

        self.btn_apps_install = ctk.CTkButton(
            action_bar,
            text="⚡ Run Silent Installs",
            command=self._start_install_apps,
            width=180,
            fg_color="#2EA043",
            hover_color="#238636",
        )
        self.btn_apps_install.pack(side="left", padx=(0, 8))

        self.apps_search_entry = ctk.CTkEntry(action_bar, placeholder_text="Filter installers...", width=200)
        self.apps_search_entry.pack(side="right")
        self.apps_search_entry.bind("<KeyRelease>", lambda e: self._render_apps_table())

        self.apps_count_label = ctk.CTkLabel(action_bar, text="0 installers found", text_color="gray60")
        self.apps_count_label.pack(side="right", padx=12)

        # Table Header
        header_table = ctk.CTkFrame(self.tab_apps, height=32, corner_radius=4, fg_color=("gray80", "#24272C"))
        header_table.pack(fill="x", padx=10, pady=(4, 0))

        self.apps_select_all_var = ctk.BooleanVar(value=True)
        cb_all = ctk.CTkCheckBox(header_table, text="", variable=self.apps_select_all_var, width=24, command=self._toggle_apps_select_all)
        cb_all.pack(side="left", padx=(10, 5))

        btn_sort_name = ctk.CTkButton(
            header_table,
            text="Installer File Name ⬍",
            command=lambda: self._sort_apps_table("name"),
            fg_color="transparent",
            hover_color=("gray75", "#333740"),
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        btn_sort_name.pack(side="left", fill="x", expand=True, padx=5)

        lbl_type = ctk.CTkLabel(header_table, text="Type", width=70, font=ctk.CTkFont(size=12, weight="bold"), anchor="center")
        lbl_type.pack(side="left", padx=5)

        btn_sort_size = ctk.CTkButton(
            header_table,
            text="Size (MB) ⬍",
            command=lambda: self._sort_apps_table("size_mb"),
            fg_color="transparent",
            hover_color=("gray75", "#333740"),
            width=100,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        btn_sort_size.pack(side="left", padx=5)

        lbl_cmd = ctk.CTkLabel(header_table, text="Silent Flags", width=200, font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
        lbl_cmd.pack(side="left", padx=(5, 15))

        # Scrollable rows
        self.apps_scroll = ctk.CTkScrollableFrame(self.tab_apps, corner_radius=6)
        self.apps_scroll.pack(fill="both", expand=True, padx=10, pady=(2, 8))

    def _browse_apps_source(self) -> None:
        path = filedialog.askdirectory(title="Select Installer Folder", initialdir=self.config.app_source or "C:/")
        if path:
            self.apps_src_entry.delete(0, "end")
            self.apps_src_entry.insert(0, path)
            self.config.app_source = path
            self._start_scan_apps()

    def _sort_apps_table(self, col: str) -> None:
        if self.app_sort_col == col:
            self.app_sort_asc = not self.app_sort_asc
        else:
            self.app_sort_col = col
            self.app_sort_asc = True
        self._render_apps_table()

    def _toggle_apps_select_all(self) -> None:
        val = self.apps_select_all_var.get()
        for cb in self.app_checkboxes.values():
            if val:
                cb.select()
            else:
                cb.deselect()

    def _render_apps_table(self) -> None:
        for child in self.apps_scroll.winfo_children():
            child.destroy()
        self.app_checkboxes.clear()

        query = self.apps_search_entry.get().strip().lower()
        filtered = [a for a in self.app_installers if not query or query in a["name"].lower()]

        if self.app_sort_col == "name":
            filtered.sort(key=lambda x: x["name"].lower(), reverse=not self.app_sort_asc)
        elif self.app_sort_col == "size_mb":
            filtered.sort(key=lambda x: x["size_mb"], reverse=not self.app_sort_asc)

        self.apps_count_label.configure(text=f"{len(filtered)} / {len(self.app_installers)} installers")

        if not filtered:
            empty_lbl = ctk.CTkLabel(self.apps_scroll, text="No .exe or .msi files found. Select folder and click 'Scan Installers'.", text_color="gray50")
            empty_lbl.pack(pady=40)
            return

        for idx, item in enumerate(filtered):
            row_bg = ("#F2F2F2", "#1E2024") if idx % 2 == 0 else ("#E8E8E8", "#24272C")
            row = ctk.CTkFrame(self.apps_scroll, fg_color=row_bg, corner_radius=4, height=36)
            row.pack(fill="x", padx=2, pady=2)

            cb_var = ctk.BooleanVar(value=self.apps_select_all_var.get())
            cb = ctk.CTkCheckBox(row, text="", variable=cb_var, width=24)
            cb.pack(side="left", padx=(8, 4))
            self.app_checkboxes[item["name"]] = cb

            # Name
            lbl_name = ctk.CTkLabel(row, text=item["name"], anchor="w", font=ctk.CTkFont(size=12))
            lbl_name.pack(side="left", fill="x", expand=True, padx=4)

            # Type Badge
            type_color = "#8E44AD" if item["type"] == "MSI" else "#2980B9"
            lbl_type = ctk.CTkLabel(row, text=item["type"], width=60, fg_color=type_color, text_color="#FFFFFF", corner_radius=4, font=ctk.CTkFont(size=10, weight="bold"))
            lbl_type.pack(side="left", padx=4)

            # Size
            lbl_size = ctk.CTkLabel(row, text=f"{item['size_mb']:.1f} MB", width=100, anchor="e", font=ctk.CTkFont(size=12, weight="bold"))
            lbl_size.pack(side="left", padx=4)

            # Flags
            lbl_cmd = ctk.CTkLabel(row, text=item["cmd_preview"], width=200, anchor="w", text_color="gray60", font=ctk.CTkFont(size=11))
            lbl_cmd.pack(side="left", padx=(4, 10))

    def _start_scan_apps(self) -> None:
        if self.is_busy:
            return

        src = self.apps_src_entry.get().strip()
        if not src:
            messagebox.showwarning("Warning", "Please select an installer source folder.")
            return

        self._set_busy(True, "Scanning directory for installers...")
        self.btn_apps_scan.configure(state="disabled")

        def worker():
            try:
                items = SilentAppInstaller.scan(Path(src))
                self.after(0, lambda: self._on_apps_scan_complete(items))
            except Exception as e:
                self.after(0, lambda: self._on_operation_error(f"Installer scan error: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_apps_scan_complete(self, items: List[Dict[str, Any]]) -> None:
        self.app_installers = items
        self._render_apps_table()
        self._set_busy(False, f"Found {len(items)} setup file(s).")
        self.btn_apps_scan.configure(state="normal")
        self.log(f"Installer scan finished: {len(items)} item(s) found.")

    def _start_install_apps(self) -> None:
        if self.is_busy:
            return

        selected = [a for a in self.app_installers if self.app_checkboxes.get(a["name"]) and self.app_checkboxes[a["name"]].get()]
        if not selected:
            messagebox.showinfo("Select Installers", "Please select at least one application to install.")
            return

        if not messagebox.askyesno("Confirm Silent Installation", f"Run silent installation for {len(selected)} application(s) sequentially?\n\nProceed?"):
            return

        self._set_busy(True, "Running silent installations...")
        self.cancel_event.clear()

        def worker():
            installed_count = 0
            total = len(selected)

            for idx, item in enumerate(selected):
                if self.cancel_event.is_set():
                    break

                pct = idx / total
                status_msg = f"Installing ({idx + 1}/{total}): {item['name']}..."
                self.after(0, lambda p=pct, m=status_msg: self._update_progress_bar(p, m, 0, 0))

                self.after(0, lambda name=item["name"]: self.log(f"Starting silent installation: {name}"))
                ok, res_msg = SilentAppInstaller.run_single_installer(
                    item=item,
                    log_callback=lambda m: self.after(0, lambda msg=m: self.log(msg)),
                    cancel_event=self.cancel_event,
                )

                if ok:
                    installed_count += 1
                else:
                    if self.cancel_event.is_set():
                        break

            if self.cancel_event.is_set():
                self.after(0, lambda: self._on_operation_cancelled("Silent installations cancelled by user."))
            else:
                self.after(0, lambda: self._on_operation_finished(f"Installed {installed_count}/{total} application(s) successfully."))

        threading.Thread(target=worker, daemon=True).start()

    # --------------------------------------------------------------------------
    # Tab 4: Activity Logs
    # --------------------------------------------------------------------------

    def _build_logs_tab(self) -> None:
        """Terminal-like activity log viewer."""
        top_bar = ctk.CTkFrame(self.tab_logs, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(8, 4))

        ctk.CTkLabel(top_bar, text="Console Output & Activity Stream:", font=ctk.CTkFont(weight="bold")).pack(side="left")

        ctk.CTkButton(top_bar, text="Clear Logs", width=90, fg_color="#4A5568", hover_color="#2D3748", command=self._clear_logs).pack(side="right", padx=(5, 0))
        ctk.CTkButton(top_bar, text="Copy to Clipboard", width=120, fg_color="#4A5568", hover_color="#2D3748", command=self._copy_logs).pack(side="right")

        self.log_textbox = ctk.CTkTextbox(self.tab_logs, corner_radius=6, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(4, 8))

    def log(self, message: str) -> None:
        """Append timestamped message to log view."""
        timestamp = time.strftime("[%H:%M:%S] ")
        self.log_textbox.insert("end", timestamp + message + "\n")
        self.log_textbox.see("end")

    def _clear_logs(self) -> None:
        self.log_textbox.delete("1.0", "end")

    def _copy_logs(self) -> None:
        content = self.log_textbox.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("Copied", "Logs copied to clipboard.")

    # --------------------------------------------------------------------------
    # Tab 5: Settings & License
    # --------------------------------------------------------------------------

    def _build_settings_tab(self) -> None:
        """Settings, license management, and self-update check."""
        scroll = ctk.CTkScrollableFrame(self.tab_settings, corner_radius=6)
        scroll.pack(fill="both", expand=True, padx=10, pady=8)

        # License Frame
        card_lic = ctk.CTkFrame(scroll, corner_radius=6)
        card_lic.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(card_lic, text="🔑 License & Authentication", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))

        lic_row = ctk.CTkFrame(card_lic, fg_color="transparent")
        lic_row.pack(fill="x", padx=12, pady=(4, 10))

        ctk.CTkLabel(lic_row, text="Active License Key:").pack(side="left", padx=(0, 10))
        self.settings_key_entry = ctk.CTkEntry(lic_row, width=240, placeholder_text="Enter license key...")
        self.settings_key_entry.insert(0, self.config.license_key)
        self.settings_key_entry.pack(side="left", padx=(0, 10))

        ctk.CTkButton(lic_row, text="Verify & Save Key", width=130, command=self._verify_and_save_key).pack(side="left")

        # Updates Frame
        card_upd = ctk.CTkFrame(scroll, corner_radius=6)
        card_upd.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(card_upd, text="🔄 Software Updates", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))

        upd_row = ctk.CTkFrame(card_upd, fg_color="transparent")
        upd_row.pack(fill="x", padx=12, pady=(4, 10))

        ctk.CTkLabel(upd_row, text=f"Installed Version: v{CURRENT_VERSION}").pack(side="left", padx=(0, 15))
        ctk.CTkButton(upd_row, text="Check for Updates", width=140, command=lambda: self._check_updates_manual()).pack(side="left")

        # Defaults Frame
        card_paths = ctk.CTkFrame(scroll, corner_radius=6)
        card_paths.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(card_paths, text="📁 Default Deployment Destinations", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))

        p_row1 = ctk.CTkFrame(card_paths, fg_color="transparent")
        p_row1.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(p_row1, text="Default Steam:", width=120, anchor="w").pack(side="left")
        ctk.CTkLabel(p_row1, text="C:/Program Files (x86)/Steam", text_color="gray70").pack(side="left")

        p_row2 = ctk.CTkFrame(card_paths, fg_color="transparent")
        p_row2.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(p_row2, text="Default Riot:", width=120, anchor="w").pack(side="left")
        ctk.CTkLabel(p_row2, text="C:/Riot Games", text_color="gray70").pack(side="left")

        # Reset button
        btn_reset = ctk.CTkButton(card_paths, text="Restore Default Destinations", width=200, fg_color="#C0392B", hover_color="#962D22", command=self._restore_defaults)
        btn_reset.pack(anchor="w", padx=12, pady=(8, 12))

    def _verify_and_save_key(self) -> None:
        key = self.settings_key_entry.get().strip()
        if not key:
            messagebox.showwarning("Warning", "Please enter a license key.")
            return

        self._set_busy(True, "Verifying license key with server...")

        def worker():
            try:
                auth_data = self.auth_mgr.fetch_auth_data(force_refresh=True)
                valid = self.auth_mgr.validate_key(key, auth_data)
                if valid:
                    self.config.license_key = key
                    self.after(0, lambda: self._on_key_valid())
                else:
                    self.after(0, lambda: self._on_key_invalid())
            except Exception as e:
                self.after(0, lambda: self._on_operation_error(f"License check failed: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_key_valid(self) -> None:
        self._set_busy(False, "License key verified and active!")
        self.status_badge.configure(text="● Active", fg_color="#1E4620", text_color="#2ECC71")
        messagebox.showinfo("Success", "License key verified and saved successfully!")

    def _on_key_invalid(self) -> None:
        self._set_busy(False, "Invalid license key.")
        messagebox.showerror("Activation Failed", "The provided license key is not valid.")

    def _restore_defaults(self) -> None:
        self.steam_dst_entry.delete(0, "end")
        self.steam_dst_entry.insert(0, "C:/Program Files (x86)/Steam")
        self.config.steam_dest = "C:/Program Files (x86)/Steam"

        self.riot_dst_entry.delete(0, "end")
        self.riot_dst_entry.insert(0, "C:/Riot Games")
        self.config.riot_dest = "C:/Riot Games"

        messagebox.showinfo("Defaults Restored", "Default destination paths restored.")

    # --------------------------------------------------------------------------
    # Global Bottom Progress & Control Bar
    # --------------------------------------------------------------------------

    def _build_bottom_bar(self) -> None:
        """Global Bottom Control Bar with Progress Bar, Percentage, Speed & Cancel Button."""
        self.bottom_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray85", "#1A1C1E"))
        self.bottom_frame.pack(fill="x", side="bottom", padx=0, pady=0)

        # Status row
        status_row = ctk.CTkFrame(self.bottom_frame, fg_color="transparent")
        status_row.pack(fill="x", padx=16, pady=(8, 2))

        self.status_text = ctk.CTkLabel(
            status_row,
            text="Ready",
            font=ctk.CTkFont(size=12),
            anchor="w",
            text_color=("gray20", "#CCCCCC"),
        )
        self.status_text.pack(side="left", fill="x", expand=True)

        self.speed_text = ctk.CTkLabel(
            status_row,
            text="",
            font=ctk.CTkFont(size=11, family="Consolas"),
            anchor="e",
            text_color="gray60",
        )
        self.speed_text.pack(side="right")

        # Progress row
        progress_row = ctk.CTkFrame(self.bottom_frame, fg_color="transparent")
        progress_row.pack(fill="x", padx=16, pady=(2, 10))

        self.progress_bar = ctk.CTkProgressBar(progress_row, height=14)
        self.progress_bar.set(0.0)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.pct_label = ctk.CTkLabel(
            progress_row,
            text="0%",
            width=45,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="center",
        )
        self.pct_label.pack(side="left", padx=(0, 10))

        self.btn_cancel = ctk.CTkButton(
            progress_row,
            text="⏹ Cancel / Stop",
            command=self._on_cancel_clicked,
            width=110,
            height=28,
            fg_color="#D32F2F",
            hover_color="#B71C1C",
            state="disabled",
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.btn_cancel.pack(side="right")

    def _update_progress_bar(self, percentage: float, message: str, speed_bytes: float = 0.0, eta_sec: float = 0.0) -> None:
        """Update global progress controls (called safely on main thread)."""
        clamped_pct = max(0.0, min(1.0, percentage))
        self.progress_bar.set(clamped_pct)
        self.pct_label.configure(text=f"{int(clamped_pct * 100)}%")
        self.status_text.configure(text=message)

        if speed_bytes > 0:
            speed_str = format_speed(speed_bytes)
            eta_str = format_eta(eta_sec)
            self.speed_text.configure(text=f"{speed_str} | ETA: {eta_str}")
        else:
            self.speed_text.configure(text="")

    def _set_busy(self, busy: bool, message: str = "") -> None:
        """Set app busy state and toggle cancel button."""
        self.is_busy = busy
        self.status_text.configure(text=message)
        if busy:
            self.btn_cancel.configure(state="normal")
            self.progress_bar.set(0.0)
            self.pct_label.configure(text="0%")
        else:
            self.btn_cancel.configure(state="disabled")
            self.speed_text.configure(text="")

    def _on_cancel_clicked(self) -> None:
        """Handle user clicking the Cancel button."""
        if not self.is_busy:
            return
        self.cancel_event.set()
        self.status_text.configure(text="Cancelling operation... please wait.")
        self.log("Cancellation signal sent by user.")

    def _on_operation_cancelled(self, message: str) -> None:
        self._set_busy(False, message)
        self.progress_bar.set(0.0)
        self.pct_label.configure(text="0%")
        self.log(f"Operation stopped: {message}")
        messagebox.showinfo("Cancelled", message)

    def _on_operation_finished(self, message: str) -> None:
        self._set_busy(False, message)
        self.progress_bar.set(1.0)
        self.pct_label.configure(text="100%")
        self.log(f"Operation finished: {message}")
        messagebox.showinfo("Complete", message)

    def _on_operation_error(self, message: str) -> None:
        self._set_busy(False, f"Error: {message}")
        self.log(f"Error encountered: {message}")
        messagebox.showerror("Operation Error", message)

    # --------------------------------------------------------------------------
    # Startup Online Auth, Kill Switch, Self-Update & Login
    # --------------------------------------------------------------------------

    def _start_auth_and_update_check(self) -> None:
        """Run initial online checks in background worker."""
        self.status_badge.configure(text="● Checking auth...")

        def worker():
            try:
                auth_data = self.auth_mgr.fetch_auth_data()

                # 1. Kill Switch Check
                is_active, ks_msg = self.auth_mgr.check_kill_switch(auth_data)
                if not is_active:
                    self.after(0, lambda: self._handle_kill_switch(ks_msg))
                    return

                # 2. Auto-Update Check
                is_newer, latest_ver, download_url = self.auth_mgr.check_update(auth_data)
                if is_newer:
                    self.after(0, lambda: self._prompt_auto_update(latest_ver, download_url, auth_data))
                    return

                # 3. License Check
                self.after(0, lambda: self._check_license_flow(auth_data))

            except Exception as e:
                print(f"[Auth] Initial check failed: {e}")
                self.after(0, lambda: self._on_auth_network_failure(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_kill_switch(self, message: str) -> None:
        """Show kill switch message and terminate app."""
        self.status_badge.configure(text="● Inactive / Blocked", fg_color="#5A1A1A", text_color="#E74C3C")
        messagebox.showerror("Service Notice", f"Application Notice:\n\n{message}")
        self.destroy()
        sys.exit(0)

    def _on_auth_network_failure(self, err_msg: str) -> None:
        """Handle network error on auth."""
        self.status_badge.configure(text="● Offline / Error", fg_color="#5A1A1A", text_color="#E74C3C")
        self.log(f"Failed to connect to authentication server: {err_msg}")
        retry = messagebox.askretrycancel(
            "Connection Error",
            f"Could not connect to online authentication server.\n\nError: {err_msg}\n\nWould you like to retry?",
        )
        if retry:
            self.after(100, self._start_auth_and_update_check)

    def _prompt_auto_update(self, latest_ver: str, download_url: str, auth_data: Dict[str, Any]) -> None:
        """Prompt user to update when a newer version is detected."""
        ans = messagebox.askyesno(
            "Update Available",
            f"A newer version (v{latest_ver}) is available!\n(Installed: v{CURRENT_VERSION})\n\nWould you like to update automatically now?",
        )
        if ans:
            self._run_self_update(download_url)
        else:
            # User chose No, proceed normally to license check
            self._check_license_flow(auth_data)

    def _run_self_update(self, download_url: str) -> None:
        """Download new version with dedicated progress window and restart."""
        # Create Update Dialog
        dlg = ctk.CTkToplevel(self)
        dlg.title("Downloading Self-Update")
        dlg.geometry("420x180")
        dlg.grab_set()
        dlg.resizable(False, False)

        lbl = ctk.CTkLabel(dlg, text="Downloading update, please wait...", font=ctk.CTkFont(size=13, weight="bold"))
        lbl.pack(pady=(20, 10))

        pbar = ctk.CTkProgressBar(dlg, width=360)
        pbar.set(0.0)
        pbar.pack(pady=10)

        pct_lbl = ctk.CTkLabel(dlg, text="0%")
        pct_lbl.pack(pady=5)

        def worker():
            def prog(downloaded, total, msg):
                pct = (downloaded / total) if total > 0 else 0.0
                dlg.after(0, lambda: pbar.set(pct))
                dlg.after(0, lambda: pct_lbl.configure(text=f"{int(pct * 100)}% ({format_bytes(downloaded)} / {format_bytes(total)})"))

            ok, res_msg = SelfUpdater.download_and_apply_update(
                download_url=download_url,
                progress_callback=prog,
            )
            if not ok:
                dlg.after(0, lambda: messagebox.showerror("Update Failed", res_msg))
                dlg.after(0, dlg.destroy)

        threading.Thread(target=worker, daemon=True).start()

    def _check_updates_manual(self) -> None:
        """Manual update check button in settings."""
        self._set_busy(True, "Checking for software updates...")

        def worker():
            try:
                auth_data = self.auth_mgr.fetch_auth_data(force_refresh=True)
                is_newer, latest_ver, download_url = self.auth_mgr.check_update(auth_data)
                if is_newer:
                    self.after(0, lambda: self._prompt_auto_update(latest_ver, download_url, auth_data))
                else:
                    self.after(0, lambda: messagebox.showinfo("Up to Date", f"You are running the latest version (v{CURRENT_VERSION})."))
                self.after(0, lambda: self._set_busy(False, "Ready"))
            except Exception as e:
                self.after(0, lambda: self._on_operation_error(f"Update check failed: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _check_license_flow(self, auth_data: Dict[str, Any]) -> None:
        """Verify saved license or prompt activation dialog."""
        saved_key = self.config.license_key
        if saved_key and self.auth_mgr.validate_key(saved_key, auth_data):
            # Valid license
            self.status_badge.configure(text="● Active", fg_color="#1E4620", text_color="#2ECC71")
            self.log("License authenticated successfully.")
        else:
            # Need user to input key
            self._show_login_dialog(auth_data)

    def _show_login_dialog(self, auth_data: Dict[str, Any]) -> None:
        """Modal login dialog prompting user for valid license key."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("License Activation")
        dlg.geometry("450x260")
        dlg.grab_set()
        dlg.resizable(False, False)

        # Center on parent
        x = self.winfo_x() + (self.winfo_width() - 450) // 2
        y = self.winfo_y() + (self.winfo_height() - 260) // 2
        dlg.geometry(f"+{x}+{y}")

        title = ctk.CTkLabel(dlg, text="🔑 PC Reviewer Deployer Activation", font=ctk.CTkFont(size=16, weight="bold"))
        title.pack(pady=(20, 8))

        desc = ctk.CTkLabel(
            dlg,
            text="Please enter your reviewer license key to activate the software.",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
        )
        desc.pack(pady=(0, 15))

        key_entry = ctk.CTkEntry(dlg, width=320, placeholder_text="Enter license key...")
        key_entry.insert(0, self.config.license_key)
        key_entry.pack(pady=(0, 15))
        key_entry.focus()

        err_lbl = ctk.CTkLabel(dlg, text="", text_color="#E74C3C", font=ctk.CTkFont(size=11))
        err_lbl.pack(pady=(0, 10))

        btn_box = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_box.pack(pady=5)

        def on_activate():
            k = key_entry.get().strip()
            if not k:
                err_lbl.configure(text="Please enter a license key.")
                return

            if self.auth_mgr.validate_key(k, auth_data):
                self.config.license_key = k
                self.settings_key_entry.delete(0, "end")
                self.settings_key_entry.insert(0, k)
                self.status_badge.configure(text="● Active", fg_color="#1E4620", text_color="#2ECC71")
                self.log(f"License key activated: {k}")
                dlg.destroy()
                messagebox.showinfo("Activated", "Software activated successfully!")
            else:
                err_lbl.configure(text="Invalid license key. Please check and try again.")

        def on_exit():
            dlg.destroy()
            self.destroy()
            sys.exit(0)

        ctk.CTkButton(btn_box, text="Activate", width=120, command=on_activate, fg_color="#2EA043", hover_color="#238636").pack(side="left", padx=8)
        ctk.CTkButton(btn_box, text="Exit App", width=100, command=on_exit, fg_color="#555555", hover_color="#444444").pack(side="left", padx=8)

        # Allow pressing Enter to submit
        key_entry.bind("<Return>", lambda e: on_activate())
        dlg.protocol("WM_DELETE_WINDOW", on_exit)


def main() -> None:
    """Run the desktop application."""
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
