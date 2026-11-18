# ⚡ PC Reviewer Deployer

A production-ready, thread-safe Windows Desktop GUI application built with Python and **CustomTkinter** for PC Reviewers to deploy games and silent software quickly.

---

## 🌟 Key Features

### 1. Local Config & Persistence
- Automatically persists and reloads last used Source and Destination paths for Steam, Riot Games, and Silent App Installer.
- Persists user's license key locally in `%APPDATA%\GameDeployer\config.json` (with automatic fallback to local directory).
- Default Steam Destination: `C:/Program Files (x86)/Steam`.
- Default Riot Destination: `C:/Riot Games`.

### 2. Online Authentication & Seamless Self-Update
- **Bypass Cache**: Fetches remote `auth.json` from `https://raw.githubusercontent.com/HungNupHN/Gamecopy/refs/heads/main/auth.json` with cache-busting headers (`Cache-Control: no-cache`) and timestamp query parameter.
- **Kill Switch**: If `global_status != "active"`, displays server message dialog and immediately exits.
- **Seamless Self-Update**:
  - Compares `CURRENT_VERSION = "1.0"` with remote `latest_version`.
  - If newer, prompts user (Yes/No).
  - If Yes: downloads new `.exe` with visual progress bar $\rightarrow$ renames running `.exe` to `.exe.old` $\rightarrow$ renames new file to original `.exe` $\rightarrow$ restarts app $\rightarrow$ cleans up `.exe.old` on next launch.
  - If No: proceeds normally.
- **License Validation**: Verifies entered/saved license key against `valid_keys` array (`["23092000", "512239"]`).

### 3. Core Engine & UI Controls
- **Non-blocking Multi-threading**: All heavy I/O tasks (folder scanning, size calculation, file copying, silent installation) execute in background daemon threads.
- **Global Bottom Status & Progress Bar**: Smooth percentage progress, status text, real-time speed in MB/s, and estimated time remaining (ETA).
- **Functional Cancel / Stop Button**: Immediately and safely aborts ongoing chunked file copies (removing incomplete destination files) and terminates active installer processes.

### 4. Module 1 — Steam Game Deployer
- Select Source directory and Destination directory (default `C:/Program Files (x86)/Steam`).
- Scans `steamapps/*.acf` to extract Game Name, `installdir`, and `SizeOnDisk` (in GB).
- Verifies `steamapps/common/<installdir>` directory exists.
- Sortable table by Name and Size.
- Copies selected `.acf` files to `Dest/steamapps/` and game folders to `Dest/steamapps/common/<installdir>`.

### 5. Module 2 — Riot Games Deployer
- Select Source directory and Destination directory (default `C:/Riot Games`).
- Scans Source for `League of Legends` and `VALORANT` folders, calculates exact sizes on disk.
- Sortable table by Name and Size.
- Copies selected folders to Destination directory.
- Creates or patches Metadata YAML configs at `C:\ProgramData\Riot Games\Metadata\<game>.live\<game>.live.product_settings.yaml`:
  - `product_install_root` with forward slashes (`/`)
  - `product_install_full_path` with forward slashes (`/`), appending `/live` for VALORANT.

### 6. Module 3 — Silent App Installer
- Select Source folder containing `.exe` and `.msi` installers.
- Scans and displays in a sortable table with Name, Size (MB), Type, and command preview.
- Runs sequential silent installations:
  - `.msi`: `msiexec.exe /i "<file>" /qn /norestart`
  - `.exe`: `"<file>" /S`
- Real-time logging of exit codes and progress.
- Functional Cancel button to abort between installers or terminate running installer process.

---

## 📁 Project Architecture

```
game_copy/
├── config.py             # ConfigManager: loads/saves settings in %APPDATA%/GameDeployer/config.json
├── auth.py               # AuthManager & SelfUpdater: online auth, kill switch, self-update, license check
├── utils.py              # Chunked file copy engine, cancellation token, speed & size formatting
├── deployers.py          # SteamDeployer, RiotDeployer, SilentAppInstaller logic
├── ui.py                 # CustomTkinter GUI: dark theme, tabs, sortable tables, progress controls
├── main.py               # Entry point: startup cleanup, GUI initialization, lifecycle
├── build.py              # PyInstaller build automation script
├── requirements.txt      # Python dependencies
└── dist/
    └── GameDeployer.exe  # Standalone single-file executable (--onefile --noconsole --uac-admin)
```

---

## 🚀 How to Run & Build

### Run from Python:
```bash
python main.py
```

### Build Standalone `.exe` via PyInstaller:
```bash
python build.py
```
Or directly with PyInstaller:
```bash
pyinstaller --clean --noconfirm --onefile --noconsole --uac-admin --name=GameDeployer --collect-all=customtkinter main.py
```
The compiled single `.exe` will be located in `dist/GameDeployer.exe`.
