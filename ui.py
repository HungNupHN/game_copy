"""
User Interface Module for PC Reviewer Deployer.
Built with CustomTkinter for a modern, sleek, dark-themed Windows desktop application.
Fully thread-safe with non-blocking workers and global progress/cancel controls.
"""

import os
import sys
import time
import threading
from pathlib import Path
from typing import List, Dict, Optional, Any
from tkinter import filedialog, messagebox

import customtkinter as ctk

from config import ConfigManager
from auth import AuthManager, SelfUpdater, CURRENT_VERSION
from deployers import (
    SteamDeployer,
    RiotDeployer,
    DeltaForceDeployer,
    SilentAppInstaller,
    check_installed_clients,
)
from utils import format_bytes, format_speed, format_eta, is_admin

# Theme setup
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    """Main Application Window for PC Reviewer Deployer."""

    def __init__(self):
        super().__init__()

        self.title(f"PC Reviewer Deployer v{CURRENT_VERSION}")
        self.geometry("1160x760")
        self.minsize(960, 640)

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

        self.delta_games: List[Dict[str, Any]] = []
        self.delta_checkboxes: Dict[str, ctk.CTkCheckBox] = {}

        self.app_installers: List[Dict[str, Any]] = []
        self.app_checkboxes: Dict[str, ctk.CTkCheckBox] = {}
        self.app_sort_col = "name"
        self.app_sort_asc = True

        # Build UI layout
        self._build_header()
        self._build_tabview()
        self._build_bottom_bar()

        # Start background auth & client check after UI is shown
        self.after(200, self._start_auth_and_update_check)
        self.after(300, self._refresh_client_status)

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
            text="Silent Software Installer & High-Speed Game Deployment Suite",
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
        """Build tabbed workspace: Silent App Installer first, then Game Copy."""
        self.tabview = ctk.CTkTabview(self, corner_radius=8)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(4, 0))

        # Tab 1: Silent App Installer (First Tab)
        self.tab_apps = self.tabview.add("Silent App Installer")
        # Tab 2: Game Copy (Steam + Riot + Delta Force)
        self.tab_games = self.tabview.add("Game Copy")
        # Tab 3: Activity Logs
        self.tab_logs = self.tabview.add("Activity Logs")
        # Tab 4: Settings & License
        self.tab_settings = self.tabview.add("Settings & License")

        self._build_apps_tab()
        self._build_game_copy_tab()
        self._build_logs_tab()
        self._build_settings_tab()

    # --------------------------------------------------------------------------
    # Tab 1: Silent App Installer
    # --------------------------------------------------------------------------

    def _build_apps_tab(self) -> None:
        """Module 3 UI: Silent App Installer (First Tab)."""
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

        # Table Header (grid layout so Type & Size never shift)
        header_table = ctk.CTkFrame(self.tab_apps, height=32, corner_radius=4, fg_color=("gray80", "#24272C"))
        header_table.pack(fill="x", padx=10, pady=(4, 0))
        header_table.columnconfigure(1, weight=1)

        self.apps_select_all_var = ctk.BooleanVar(value=True)
        cb_all = ctk.CTkCheckBox(header_table, text="", variable=self.apps_select_all_var, width=24, command=self._toggle_apps_select_all)
        cb_all.grid(row=0, column=0, padx=(10, 5), pady=4)

        btn_sort_name = ctk.CTkButton(
            header_table,
            text="Installer File Name ⬍",
            command=lambda: self._sort_apps_table("name"),
            fg_color="transparent",
            hover_color=("gray75", "#333740"),
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        btn_sort_name.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

        lbl_type = ctk.CTkLabel(header_table, text="Type", width=65, font=ctk.CTkFont(size=12, weight="bold"), anchor="center")
        lbl_type.grid(row=0, column=2, padx=5, pady=2)

        btn_sort_size = ctk.CTkButton(
            header_table,
            text="Size (MB) ⬍",
            command=lambda: self._sort_apps_table("size_mb"),
            fg_color="transparent",
            hover_color=("gray75", "#333740"),
            width=95,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        btn_sort_size.grid(row=0, column=3, padx=5, pady=2)

        lbl_cmd = ctk.CTkLabel(header_table, text="Silent Flags", width=185, font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
        lbl_cmd.grid(row=0, column=4, padx=(5, 12), pady=2)

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
            row.columnconfigure(1, weight=1)

            cb_var = ctk.BooleanVar(value=self.apps_select_all_var.get())
            cb = ctk.CTkCheckBox(row, text="", variable=cb_var, width=24)
            cb.grid(row=0, column=0, padx=(8, 4), pady=4)
            self.app_checkboxes[item["name"]] = cb

            name_txt = item["name"]
            if len(name_txt) > 52:
                name_txt = name_txt[:49] + "..."
            lbl_name = ctk.CTkLabel(row, text=name_txt, anchor="w", font=ctk.CTkFont(size=12))
            lbl_name.grid(row=0, column=1, sticky="ew", padx=4, pady=4)

            type_color = "#8E44AD" if item["type"] == "MSI" else "#2980B9"
            lbl_type = ctk.CTkLabel(row, text=item["type"], width=65, fg_color=type_color, text_color="#FFFFFF", corner_radius=4, font=ctk.CTkFont(size=10, weight="bold"))
            lbl_type.grid(row=0, column=2, padx=5, pady=4)

            lbl_size = ctk.CTkLabel(row, text=f"{item['size_mb']:.1f} MB", width=95, anchor="e", font=ctk.CTkFont(size=12, weight="bold"))
            lbl_size.grid(row=0, column=3, padx=5, pady=4)

            cmd_txt = item["cmd_preview"]
            if len(cmd_txt) > 26:
                cmd_txt = cmd_txt[:23] + "..."
            lbl_cmd = ctk.CTkLabel(row, text=cmd_txt, width=185, anchor="w", text_color="gray60", font=ctk.CTkFont(size=11))
            lbl_cmd.grid(row=0, column=4, padx=(5, 10), pady=4)

    def _start_scan_apps(self) -> None:
        if self.is_busy:
            return

        src = self.apps_src_entry.get().strip()
        if not src:
            messagebox.showwarning("Warning", "Please select an installer source folder.")
            return

        self.config.app_source = src
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
    # Tab 2: Unified Game Copy (Top: Source/Dest Buttons + Client Check; Bottom: 2-Column Split)
    # --------------------------------------------------------------------------

    def _build_game_copy_tab(self) -> None:
        """Build the unified Game Copy tab with Top Controls & Client Check and Bottom 2-Column Layout."""
        # --- TOP SECTION: Path Buttons + Scan All + Client Installation Check ---
        top_section = ctk.CTkFrame(self.tab_games, corner_radius=6)
        top_section.pack(fill="x", padx=8, pady=(6, 4))

        # Row 0: Source button, Destination button, Scan All button
        btn_row = ctk.CTkFrame(top_section, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(8, 4))

        ctk.CTkButton(
            btn_row,
            text="📁 Source Paths",
            command=self._open_sources_dialog,
            width=145,
            fg_color="#2D3748",
            hover_color="#4A5568",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="📂 Destination Paths",
            command=self._open_destinations_dialog,
            width=165,
            fg_color="#2D3748",
            hover_color="#4A5568",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=(0, 14))

        self.btn_scan_all = ctk.CTkButton(
            btn_row,
            text="🔍 Scan Games",
            command=self._start_scan_all_games,
            width=140,
            fg_color="#1F6AA5",
            hover_color="#144870",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.btn_scan_all.pack(side="left", padx=(0, 8))

        self.btn_deploy_all = ctk.CTkButton(
            btn_row,
            text="🚀 Deploy Selected",
            command=self._start_deploy_all_games,
            width=155,
            fg_color="#2EA043",
            hover_color="#238636",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.btn_deploy_all.pack(side="left", padx=(0, 8))

        self.paths_summary_label = ctk.CTkLabel(
            btn_row,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray65",
            anchor="e",
        )
        self.paths_summary_label.pack(side="right", fill="x", expand=True)
        self._update_paths_summary()

        # Row 1: Installed Clients Check Bar
        client_row = ctk.CTkFrame(top_section, fg_color=("gray82", "#1B1E23"), corner_radius=5)
        client_row.pack(fill="x", padx=10, pady=(2, 8))

        ctk.CTkLabel(
            client_row,
            text="Installed Clients:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="gray75",
        ).pack(side="left", padx=(10, 8), pady=5)

        self.client_steam_badge = ctk.CTkLabel(
            client_row,
            text="Steam: Checking...",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2D3139",
            corner_radius=4,
            padx=8,
            pady=2,
        )
        self.client_steam_badge.pack(side="left", padx=4, pady=4)

        self.client_riot_badge = ctk.CTkLabel(
            client_row,
            text="Riot Client: Checking...",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2D3139",
            corner_radius=4,
            padx=8,
            pady=2,
        )
        self.client_riot_badge.pack(side="left", padx=4, pady=4)

        self.client_delta_badge = ctk.CTkLabel(
            client_row,
            text="Delta Force (Garena): Checking...",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2D3139",
            corner_radius=4,
            padx=8,
            pady=2,
        )
        self.client_delta_badge.pack(side="left", padx=4, pady=4)

        ctk.CTkButton(
            client_row,
            text="🔄 Recheck",
            width=80,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color="#3A4149",
            hover_color="#4E5761",
            command=self._refresh_client_status,
        ).pack(side="right", padx=8, pady=4)

        # --- BOTTOM SECTION: 2-Column Split ---
        bottom_grid = ctk.CTkFrame(self.tab_games, fg_color="transparent")
        bottom_grid.pack(fill="both", expand=True, padx=8, pady=(2, 6))
        bottom_grid.columnconfigure(0, weight=1, uniform="col")
        bottom_grid.columnconfigure(1, weight=1, uniform="col")
        bottom_grid.rowconfigure(0, weight=1)

        # LEFT COLUMN: Steam
        self.steam_panel = ctk.CTkFrame(bottom_grid, corner_radius=6)
        self.steam_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=0)
        self._build_steam_panel(self.steam_panel)

        # RIGHT COLUMN: 2 Rows (Top = Riot, Bottom = Delta Force)
        right_col = ctk.CTkFrame(bottom_grid, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=0)
        right_col.columnconfigure(0, weight=1)
        right_col.rowconfigure(0, weight=1, uniform="rrow")
        right_col.rowconfigure(1, weight=1, uniform="rrow")

        self.riot_panel = ctk.CTkFrame(right_col, corner_radius=6)
        self.riot_panel.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 4))
        self._build_riot_panel(self.riot_panel)

        self.delta_panel = ctk.CTkFrame(right_col, corner_radius=6)
        self.delta_panel.grid(row=1, column=0, sticky="nsew", padx=0, pady=(4, 0))
        self._build_delta_panel(self.delta_panel)

    def _update_paths_summary(self) -> None:
        summary = (
            f"Steam: {self.config.steam_source} → {self.config.steam_dest}  |  "
            f"Riot: {self.config.riot_source} → {self.config.riot_dest}  |  "
            f"Delta Force: {self.config.delta_source} → {self.config.delta_dest}"
        )
        if len(summary) > 105:
            summary = summary[:102] + "..."
        self.paths_summary_label.configure(text=summary)

    def _open_sources_dialog(self) -> None:
        """Open modal dialog with 3 lines for Steam, Riot, and Delta Force source paths."""
        self._open_paths_modal(
            title="Configure Source Paths",
            fields=[
                ("Steam Source:", "steam_source", self.config.steam_source),
                ("Riot Games Source:", "riot_source", self.config.riot_source),
                ("Delta Force Source:", "delta_source", self.config.delta_source),
            ],
        )

    def _open_destinations_dialog(self) -> None:
        """Open modal dialog with 3 lines for Steam, Riot, and Delta Force destination paths."""
        self._open_paths_modal(
            title="Configure Destination Paths",
            fields=[
                ("Steam Destination:", "steam_dest", self.config.steam_dest),
                ("Riot Games Destination:", "riot_dest", self.config.riot_dest),
                ("Delta Force Destination:", "delta_dest", self.config.delta_dest),
            ],
        )

    def _open_paths_modal(self, title: str, fields: List[tuple]) -> None:
        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.geometry("620x250")
        dlg.grab_set()
        dlg.resizable(False, False)

        # Center on parent
        x = self.winfo_x() + (self.winfo_width() - 620) // 2
        y = self.winfo_y() + (self.winfo_height() - 250) // 2
        dlg.geometry(f"+{x}+{y}")

        ctk.CTkLabel(dlg, text=title, font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(12, 8))

        form = ctk.CTkFrame(dlg, fg_color="transparent")
        form.pack(fill="x", padx=18, pady=4)
        form.columnconfigure(1, weight=1)

        entries: Dict[str, ctk.CTkEntry] = {}

        def make_browser(ent: ctk.CTkEntry, lbl_txt: str):
            def browse():
                chosen = filedialog.askdirectory(title=f"Select {lbl_txt}", initialdir=ent.get().strip() or "C:/")
                if chosen:
                    ent.delete(0, "end")
                    ent.insert(0, chosen)
            return browse

        for row_idx, (label_text, cfg_key, initial_val) in enumerate(fields):
            ctk.CTkLabel(form, text=label_text, font=ctk.CTkFont(size=12, weight="bold"), anchor="w", width=155).grid(
                row=row_idx, column=0, sticky="w", pady=6, padx=(0, 8)
            )
            entry = ctk.CTkEntry(form)
            entry.insert(0, initial_val)
            entry.grid(row=row_idx, column=1, sticky="ew", pady=6, padx=(0, 8))
            ctk.CTkButton(form, text="Browse", width=75, command=make_browser(entry, label_text)).grid(
                row=row_idx, column=2, pady=6
            )
            entries[cfg_key] = entry

        btn_box = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_box.pack(pady=(12, 10))

        def on_save():
            updates = {k: ent.get().strip() for k, ent in entries.items()}
            self.config.update(updates)
            self._update_paths_summary()
            self._refresh_client_status()
            dlg.destroy()

        ctk.CTkButton(btn_box, text="Save Paths", width=120, fg_color="#2EA043", hover_color="#238636", command=on_save).pack(side="left", padx=8)
        ctk.CTkButton(btn_box, text="Cancel", width=90, fg_color="#555555", hover_color="#444444", command=dlg.destroy).pack(side="left", padx=8)

    def _refresh_client_status(self) -> None:
        """Check if Steam, Riot Client, and Delta Force Garena Client are installed."""
        def worker():
            res = check_installed_clients(
                steam_dest=self.config.steam_dest,
                riot_dest=self.config.riot_dest,
                delta_dest=self.config.delta_dest,
            )
            self.after(0, lambda: self._apply_client_status(res))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_client_status(self, res: Dict[str, Dict[str, Any]]) -> None:
        def style_badge(badge: ctk.CTkLabel, name: str, info: Dict[str, Any]):
            if info["installed"]:
                badge.configure(
                    text=f"● {name}: Installed",
                    fg_color="#1E4620",
                    text_color="#2ECC71",
                )
            else:
                badge.configure(
                    text=f"○ {name}: Not Installed",
                    fg_color="#4A2020",
                    text_color="#E74C3C",
                )

        style_badge(self.client_steam_badge, "Steam", res["steam"])
        style_badge(self.client_riot_badge, "Riot Client", res["riot"])
        style_badge(self.client_delta_badge, "Delta Force (Garena)", res["delta_garena"])

    # --- Left Column: Steam Panel ---

    def _build_steam_panel(self, parent: ctk.CTkFrame) -> None:
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(top, text="🎮 Steam Games", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        # Filter + Count
        filter_bar = ctk.CTkFrame(parent, fg_color="transparent")
        filter_bar.pack(fill="x", padx=8, pady=2)

        self.steam_search_entry = ctk.CTkEntry(filter_bar, placeholder_text="Filter Steam games...", height=28)
        self.steam_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.steam_search_entry.bind("<KeyRelease>", lambda e: self._render_steam_table())

        self.steam_count_label = ctk.CTkLabel(filter_bar, text="0 games", text_color="gray60", font=ctk.CTkFont(size=11))
        self.steam_count_label.pack(side="right")

        # Table Header
        header_table = ctk.CTkFrame(parent, height=28, corner_radius=4, fg_color=("gray80", "#24272C"))
        header_table.pack(fill="x", padx=8, pady=(4, 0))

        self.steam_select_all_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(header_table, text="", variable=self.steam_select_all_var, width=22, command=self._toggle_steam_select_all).pack(side="left", padx=(8, 4))

        ctk.CTkButton(
            header_table, text="Game Name ⬍", command=lambda: self._sort_steam_table("name"),
            fg_color="transparent", hover_color=("gray75", "#333740"), anchor="w", height=24,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left", fill="x", expand=True, padx=2)

        ctk.CTkButton(
            header_table, text="Size (GB) ⬍", command=lambda: self._sort_steam_table("size_gb"),
            fg_color="transparent", hover_color=("gray75", "#333740"), width=85, height=24,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left", padx=2)

        ctk.CTkLabel(header_table, text="App ID", width=65, font=ctk.CTkFont(size=11, weight="bold"), anchor="center").pack(side="left", padx=(2, 8))

        self.steam_scroll = ctk.CTkScrollableFrame(parent, corner_radius=6)
        self.steam_scroll.pack(fill="both", expand=True, padx=8, pady=(2, 8))

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
            cb.select() if val else cb.deselect()

    def _render_steam_table(self) -> None:
        for child in self.steam_scroll.winfo_children():
            child.destroy()
        self.steam_checkboxes.clear()

        query = self.steam_search_entry.get().strip().lower()
        filtered = [g for g in self.steam_games if not query or query in g["name"].lower() or query in g["installdir"].lower()]

        if self.steam_sort_col == "name":
            filtered.sort(key=lambda x: x["name"].lower(), reverse=not self.steam_sort_asc)
        elif self.steam_sort_col == "size_gb":
            filtered.sort(key=lambda x: x["size_bytes"], reverse=not self.steam_sort_asc)

        self.steam_count_label.configure(text=f"{len(filtered)} / {len(self.steam_games)} games")

        if not filtered:
            ctk.CTkLabel(self.steam_scroll, text="No Steam games found.\nClick 'Scan' or check Source Paths.", text_color="gray50").pack(pady=35)
            return

        for idx, game in enumerate(filtered):
            row_bg = ("#F2F2F2", "#1E2024") if idx % 2 == 0 else ("#E8E8E8", "#24272C")
            row = ctk.CTkFrame(self.steam_scroll, fg_color=row_bg, corner_radius=4, height=32)
            row.pack(fill="x", padx=2, pady=2)

            cb_var = ctk.BooleanVar(value=self.steam_select_all_var.get())
            cb = ctk.CTkCheckBox(row, text="", variable=cb_var, width=22)
            cb.pack(side="left", padx=(6, 4))
            self.steam_checkboxes[game["appid"]] = cb

            ctk.CTkLabel(row, text=game["name"], anchor="w", font=ctk.CTkFont(size=11)).pack(side="left", fill="x", expand=True, padx=2)
            ctk.CTkLabel(row, text=f"{game['size_gb']:.2f} GB", width=85, anchor="e", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=2)
            ctk.CTkLabel(row, text=game["appid"], width=65, anchor="center", text_color="gray60", font=ctk.CTkFont(size=10)).pack(side="left", padx=(2, 6))

    # --- Right Column Top: Riot Games Panel ---

    def _build_riot_panel(self, parent: ctk.CTkFrame) -> None:
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(top, text="⚔️ Riot Games (LoL / VALORANT)", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        header_table = ctk.CTkFrame(parent, height=28, corner_radius=4, fg_color=("gray80", "#24272C"))
        header_table.pack(fill="x", padx=8, pady=(2, 0))

        self.riot_select_all_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(header_table, text="", variable=self.riot_select_all_var, width=22, command=self._toggle_riot_select_all).pack(side="left", padx=(8, 4))

        ctk.CTkButton(
            header_table, text="Game Name ⬍", command=lambda: self._sort_riot_table("name"),
            fg_color="transparent", hover_color=("gray75", "#333740"), anchor="w", height=24,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left", fill="x", expand=True, padx=2)

        ctk.CTkButton(
            header_table, text="Size (GB) ⬍", command=lambda: self._sort_riot_table("size_gb"),
            fg_color="transparent", hover_color=("gray75", "#333740"), width=85, height=24,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left", padx=2)

        ctk.CTkLabel(header_table, text="YAML", width=75, font=ctk.CTkFont(size=11, weight="bold"), anchor="center").pack(side="left", padx=(2, 8))

        self.riot_scroll = ctk.CTkScrollableFrame(parent, corner_radius=6)
        self.riot_scroll.pack(fill="both", expand=True, padx=8, pady=(2, 8))

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
            cb.select() if val else cb.deselect()

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
            ctk.CTkLabel(self.riot_scroll, text="No Riot Games found.\nClick 'Scan' or check Source Paths.", text_color="gray50").pack(pady=20)
            return

        for idx, game in enumerate(sorted_games):
            row_bg = ("#F2F2F2", "#1E2024") if idx % 2 == 0 else ("#E8E8E8", "#24272C")
            row = ctk.CTkFrame(self.riot_scroll, fg_color=row_bg, corner_radius=4, height=32)
            row.pack(fill="x", padx=2, pady=2)

            cb_var = ctk.BooleanVar(value=self.riot_select_all_var.get())
            cb = ctk.CTkCheckBox(row, text="", variable=cb_var, width=22)
            cb.pack(side="left", padx=(6, 4))
            self.riot_checkboxes[game["id"]] = cb

            ctk.CTkLabel(row, text=game["name"], anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", fill="x", expand=True, padx=2)
            ctk.CTkLabel(row, text=f"{game['size_gb']:.2f} GB", width=85, anchor="e", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=2)
            ctk.CTkLabel(row, text="YAML Live", width=75, fg_color="#1F6AA5", text_color="#FFFFFF", corner_radius=4, font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=(4, 6))

    # --- Right Column Bottom: Delta Force Panel ---

    def _build_delta_panel(self, parent: ctk.CTkFrame) -> None:
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(top, text="🪖 Delta Force", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        header_table = ctk.CTkFrame(parent, height=28, corner_radius=4, fg_color=("gray80", "#24272C"))
        header_table.pack(fill="x", padx=8, pady=(2, 0))

        self.delta_select_all_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(header_table, text="", variable=self.delta_select_all_var, width=22, command=self._toggle_delta_select_all).pack(side="left", padx=(8, 4))

        ctk.CTkLabel(header_table, text="Package Name", anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", fill="x", expand=True, padx=2)
        ctk.CTkLabel(header_table, text="Size (GB)", width=85, anchor="e", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=2)
        ctk.CTkLabel(header_table, text="Target", width=95, anchor="center", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(2, 8))

        self.delta_scroll = ctk.CTkScrollableFrame(parent, corner_radius=6)
        self.delta_scroll.pack(fill="both", expand=True, padx=8, pady=(2, 8))

    def _toggle_delta_select_all(self) -> None:
        val = self.delta_select_all_var.get()
        for cb in self.delta_checkboxes.values():
            cb.select() if val else cb.deselect()

    def _render_delta_table(self) -> None:
        for child in self.delta_scroll.winfo_children():
            child.destroy()
        self.delta_checkboxes.clear()

        if not self.delta_games:
            ctk.CTkLabel(self.delta_scroll, text="No Delta Force files found.\nClick 'Scan' or check Source Paths.", text_color="gray50").pack(pady=20)
            return

        for idx, game in enumerate(self.delta_games):
            row_bg = ("#F2F2F2", "#1E2024") if idx % 2 == 0 else ("#E8E8E8", "#24272C")
            row = ctk.CTkFrame(self.delta_scroll, fg_color=row_bg, corner_radius=4, height=32)
            row.pack(fill="x", padx=2, pady=2)

            cb_var = ctk.BooleanVar(value=self.delta_select_all_var.get())
            cb = ctk.CTkCheckBox(row, text="", variable=cb_var, width=22)
            cb.pack(side="left", padx=(6, 4))
            self.delta_checkboxes[game["id"]] = cb

            ctk.CTkLabel(row, text=game["name"], anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", fill="x", expand=True, padx=2)
            ctk.CTkLabel(row, text=f"{game['size_gb']:.2f} GB", width=85, anchor="e", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=2)
            ctk.CTkLabel(row, text=self.config.delta_dest, width=95, anchor="center", text_color="gray70", font=ctk.CTkFont(size=10)).pack(side="left", padx=(2, 6))

    # --- Game Copy Scanning & Deployment Workers ---

    def _start_scan_all_games(self) -> None:
        if self.is_busy:
            return

        self._set_busy(True, "Scanning Steam, Riot Games, and Delta Force...")
        self.cancel_event.clear()

        def worker():
            try:
                steam_res = SteamDeployer.scan(Path(self.config.steam_source), cancel_event=self.cancel_event)
                riot_res = RiotDeployer.scan(Path(self.config.riot_source), cancel_event=self.cancel_event)
                delta_res = DeltaForceDeployer.scan(Path(self.config.delta_source), cancel_event=self.cancel_event)
                self.after(0, lambda: self._on_scan_all_complete(steam_res, riot_res, delta_res))
            except Exception as e:
                self.after(0, lambda: self._on_operation_error(f"Scan all error: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_all_complete(self, steam_res, riot_res, delta_res) -> None:
        self.steam_games = steam_res
        self.riot_games = riot_res
        self.delta_games = delta_res
        self._render_steam_table()
        self._render_riot_table()
        self._render_delta_table()
        msg = f"Scan complete: {len(steam_res)} Steam, {len(riot_res)} Riot, {len(delta_res)} Delta Force."
        self._set_busy(False, msg)
        self.log(msg)

    def _start_deploy_all_games(self) -> None:
        """Deploy all selected games across Steam, Riot Games, and Delta Force."""
        if self.is_busy:
            return

        sel_steam = [g for g in self.steam_games if self.steam_checkboxes.get(g["appid"]) and self.steam_checkboxes[g["appid"]].get()]
        sel_riot = [g for g in self.riot_games if self.riot_checkboxes.get(g["id"]) and self.riot_checkboxes[g["id"]].get()]
        sel_delta = [g for g in self.delta_games if self.delta_checkboxes.get(g["id"]) and self.delta_checkboxes[g["id"]].get()]

        total_count = len(sel_steam) + len(sel_riot) + len(sel_delta)
        if total_count == 0:
            messagebox.showinfo("Select Games", "Please check at least one game (Steam, Riot, or Delta Force) to deploy.")
            return

        steam_dst = self.config.steam_dest.strip()
        riot_dst = self.config.riot_dest.strip()
        delta_dst = self.config.delta_dest.strip()

        if sel_steam and not steam_dst:
            messagebox.showwarning("Warning", "Please configure Steam Destination path.")
            return
        if sel_riot and not riot_dst:
            messagebox.showwarning("Warning", "Please configure Riot Games Destination path.")
            return
        if sel_delta and not delta_dst:
            messagebox.showwarning("Warning", "Please configure Delta Force Destination path.")
            return

        total_bytes = (
            sum(g["size_bytes"] for g in sel_steam)
            + sum(g["size_bytes"] for g in sel_riot)
            + sum(g["size_bytes"] for g in sel_delta)
        )

        summary_lines = []
        if sel_steam:
            summary_lines.append(f"• Steam: {len(sel_steam)} game(s) → {steam_dst}")
        if sel_riot:
            summary_lines.append(f"• Riot: {len(sel_riot)} game(s) → {riot_dst}")
        if sel_delta:
            summary_lines.append(f"• Delta Force: {len(sel_delta)} package(s) → {delta_dst}")

        if not messagebox.askyesno(
            "Confirm Deployment",
            f"Deploy {total_count} selected item(s) ({format_bytes(total_bytes)}):\n\n" + "\n".join(summary_lines) + "\n\nProceed?",
        ):
            return

        self._set_busy(True, "Starting game deployment...")
        self.cancel_event.clear()

        def worker():
            copied_total = 0
            deployed_count = 0

            def prog(c, t, filename, sp):
                pct = (c / total_bytes) if total_bytes > 0 else 0.0
                rem_sec = (total_bytes - c) / sp if sp > 0 else 0
                msg = f"Copying: {filename} ({format_bytes(c)} / {format_bytes(total_bytes)})"
                self.after(0, lambda: self._update_progress_bar(pct, msg, sp, rem_sec))

            for g in sel_steam:
                if self.cancel_event.is_set():
                    break
                self.after(0, lambda name=g["name"]: self.log(f"Deploying Steam: {name}..."))
                ok, b = SteamDeployer.deploy_single_game(
                    game=g,
                    dest_dir=Path(steam_dst),
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

            for g in sel_riot:
                if self.cancel_event.is_set():
                    break
                self.after(0, lambda name=g["name"]: self.log(f"Deploying Riot: {name}..."))
                ok, b = RiotDeployer.deploy_single_game(
                    game=g,
                    dest_dir=Path(riot_dst),
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

            for g in sel_delta:
                if self.cancel_event.is_set():
                    break
                self.after(0, lambda name=g["name"]: self.log(f"Deploying Delta Force: {name}..."))
                ok, b = DeltaForceDeployer.deploy_single_game(
                    game=g,
                    dest_dir=Path(delta_dst),
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
                self.after(0, lambda: self._on_operation_cancelled("Game deployment cancelled by user."))
            else:
                self.after(0, lambda: self._on_operation_finished(f"Successfully deployed {deployed_count}/{total_count} item(s)."))

        threading.Thread(target=worker, daemon=True).start()

    def _start_scan_steam(self) -> None:
        if self.is_busy:
            return
        src = self.config.steam_source.strip()
        if not src:
            messagebox.showwarning("Warning", "Please configure Steam Source path first.")
            return
        self._set_busy(True, "Scanning Steam library...")
        self.cancel_event.clear()

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
        self._set_busy(False, f"Found {len(games)} Steam game(s).")
        self.log(f"Steam scan completed: {len(games)} game(s) detected.")

    def _start_deploy_steam(self) -> None:
        if self.is_busy:
            return
        selected = [g for g in self.steam_games if self.steam_checkboxes.get(g["appid"]) and self.steam_checkboxes[g["appid"]].get()]
        if not selected:
            messagebox.showinfo("Select Games", "Please check at least one Steam game to deploy.")
            return
        dst = self.config.steam_dest.strip()
        if not dst:
            messagebox.showwarning("Warning", "Please configure Steam Destination path.")
            return

        total_bytes = sum(g["size_bytes"] for g in selected)
        if not messagebox.askyesno("Confirm Steam Deployment", f"Deploy {len(selected)} Steam game(s) ({format_bytes(total_bytes)}) to:\n{dst}\n\nProceed?"):
            return

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
                self.after(0, lambda name=g["name"]: self.log(f"Deploying Steam: {name}..."))
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

    def _start_scan_riot(self) -> None:
        if self.is_busy:
            return
        src = self.config.riot_source.strip()
        if not src:
            messagebox.showwarning("Warning", "Please configure Riot Games Source path first.")
            return
        self._set_busy(True, "Scanning for League of Legends & VALORANT...")
        self.cancel_event.clear()

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
        self.log(f"Riot Games scan finished: {len(games)} title(s) detected.")

    def _start_deploy_riot(self) -> None:
        if self.is_busy:
            return
        selected = [g for g in self.riot_games if self.riot_checkboxes.get(g["id"]) and self.riot_checkboxes[g["id"]].get()]
        if not selected:
            messagebox.showinfo("Select Games", "Please check at least one Riot game to deploy.")
            return
        dst = self.config.riot_dest.strip()
        if not dst:
            messagebox.showwarning("Warning", "Please configure Riot Games Destination path.")
            return

        total_bytes = sum(g["size_bytes"] for g in selected)
        if not messagebox.askyesno("Confirm Riot Deployment", f"Deploy {len(selected)} Riot game(s) ({format_bytes(total_bytes)}) to:\n{dst}\nand patch metadata YAML configs?\n\nProceed?"):
            return

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
                self.after(0, lambda name=g["name"]: self.log(f"Deploying Riot: {name}..."))
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

    def _start_scan_delta(self) -> None:
        if self.is_busy:
            return
        src = self.config.delta_source.strip()
        if not src:
            messagebox.showwarning("Warning", "Please configure Delta Force Source path first.")
            return
        self._set_busy(True, "Scanning Delta Force folder...")
        self.cancel_event.clear()

        def worker():
            try:
                games = DeltaForceDeployer.scan(Path(src), cancel_event=self.cancel_event)
                self.after(0, lambda: self._on_delta_scan_complete(games))
            except Exception as e:
                self.after(0, lambda: self._on_operation_error(f"Delta Force scan error: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_delta_scan_complete(self, games: List[Dict[str, Any]]) -> None:
        self.delta_games = games
        self._render_delta_table()
        self._set_busy(False, f"Found {len(games)} Delta Force package(s).")
        self.log(f"Delta Force scan finished: {len(games)} item(s) detected.")

    def _start_deploy_delta(self) -> None:
        if self.is_busy:
            return
        selected = [g for g in self.delta_games if self.delta_checkboxes.get(g["id"]) and self.delta_checkboxes[g["id"]].get()]
        if not selected:
            messagebox.showinfo("Select Package", "Please check Delta Force package to deploy.")
            return
        dst = self.config.delta_dest.strip()
        if not dst:
            messagebox.showwarning("Warning", "Please configure Delta Force Destination path.")
            return

        total_bytes = sum(g["size_bytes"] for g in selected)
        if not messagebox.askyesno("Confirm Delta Force Deployment", f"Deploy Delta Force ({format_bytes(total_bytes)}) to:\n{dst}\n\nProceed?"):
            return

        self._set_busy(True, "Deploying Delta Force...")
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
                self.after(0, lambda name=g["name"]: self.log(f"Deploying Delta Force: {name}..."))
                ok, b = DeltaForceDeployer.deploy_single_game(
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
                self.after(0, lambda: self._on_operation_cancelled("Delta Force deployment cancelled by user."))
            else:
                self.after(0, lambda: self._on_operation_finished(f"Successfully deployed Delta Force to {dst}."))

        threading.Thread(target=worker, daemon=True).start()

    # --------------------------------------------------------------------------
    # Tab 3: Activity Logs
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
    # Tab 4: Settings & License
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
        self.settings_key_entry = ctk.CTkEntry(lic_row, width=240, placeholder_text="Enter license key...", show="*")
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

        ctk.CTkLabel(card_paths, text="📁 Default Game Paths", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))

        defaults_info = [
            ("Default Steam:", "D:/test/Steam  →  C:/Program Files (x86)/Steam"),
            ("Default Riot:", "D:/test/Riot Games  →  C:/Riot Games"),
            ("Default Delta Force:", "D:/test/Delta Force  →  C:/Delta Force"),
        ]
        for lbl, val in defaults_info:
            row = ctk.CTkFrame(card_paths, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(row, text=lbl, width=140, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=val, text_color="gray70").pack(side="left")

        btn_reset = ctk.CTkButton(card_paths, text="Restore Default Paths", width=200, fg_color="#C0392B", hover_color="#962D22", command=self._restore_defaults)
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
        self.config.update({
            "steam_source": "D:/test/Steam",
            "steam_dest": "C:/Program Files (x86)/Steam",
            "riot_source": "D:/test/Riot Games",
            "riot_dest": "C:/Riot Games",
            "delta_source": "D:/test/Delta Force",
            "delta_dest": "C:/Delta Force",
        })
        self._update_paths_summary()
        self._refresh_client_status()
        messagebox.showinfo("Defaults Restored", "Default source and destination paths restored.")

    # --------------------------------------------------------------------------
    # Global Bottom Progress & Control Bar
    # --------------------------------------------------------------------------

    def _build_bottom_bar(self) -> None:
        """Global Bottom Control Bar with Progress Bar, Percentage, Speed & Cancel Button."""
        self.bottom_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray85", "#1A1C1E"))
        self.bottom_frame.pack(fill="x", side="bottom", padx=0, pady=0)

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
        self._refresh_client_status()
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
        self.status_badge.configure(text="● Inactive / Blocked", fg_color="#5A1A1A", text_color="#E74C3C")
        messagebox.showerror("Service Notice", f"Application Notice:\n\n{message}")
        self.destroy()
        sys.exit(0)

    def _on_auth_network_failure(self, err_msg: str) -> None:
        self.status_badge.configure(text="● Offline / Error", fg_color="#5A1A1A", text_color="#E74C3C")
        self.log(f"Failed to connect to authentication server: {err_msg}")
        retry = messagebox.askretrycancel(
            "Connection Error",
            f"Could not connect to online authentication server.\n\nError: {err_msg}\n\nWould you like to retry?",
        )
        if retry:
            self.after(100, self._start_auth_and_update_check)

    def _prompt_auto_update(self, latest_ver: str, download_url: str, auth_data: Dict[str, Any]) -> None:
        ans = messagebox.askyesno(
            "Update Available",
            f"A newer version (v{latest_ver}) is available!\n(Installed: v{CURRENT_VERSION})\n\nWould you like to update automatically now?",
        )
        if ans:
            self._run_self_update(download_url)
        else:
            self._check_license_flow(auth_data)

    def _run_self_update(self, download_url: str) -> None:
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
        saved_key = self.config.license_key
        if saved_key and self.auth_mgr.validate_key(saved_key, auth_data):
            self.status_badge.configure(text="● Active", fg_color="#1E4620", text_color="#2ECC71")
            self.log("License authenticated successfully.")
        else:
            self._show_login_dialog(auth_data)

    def _show_login_dialog(self, auth_data: Dict[str, Any]) -> None:
        dlg = ctk.CTkToplevel(self)
        dlg.title("License Activation")
        dlg.geometry("450x260")
        dlg.grab_set()
        dlg.resizable(False, False)

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

        key_entry = ctk.CTkEntry(dlg, width=320, placeholder_text="Enter license key...", show="*")
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
                self.log("License key activated.")
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

        key_entry.bind("<Return>", lambda e: on_activate())
        dlg.protocol("WM_DELETE_WINDOW", on_exit)


def main() -> None:
    """Run the desktop application."""
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
