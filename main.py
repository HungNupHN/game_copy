"""
PC Reviewer Deployer - Main Application Entry Point
Production-ready Windows Desktop Application for PC Reviewers.
Compilable into a single .exe via PyInstaller (--onefile --noconsole --uac-admin).
"""

import sys
from pathlib import Path

# Ensure application directory is in Python module search path
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from auth import cleanup_old_exe
from ui import App


def main() -> None:
    """Main application lifecycle controller."""
    # 1. Cleanup any .exe.old left behind from previous self-update
    cleanup_old_exe()

    # 2. Launch GUI Application
    try:
        app = App()
        app.mainloop()
    except KeyboardInterrupt:
        print("\n[Application] Terminated by user.")
        sys.exit(0)
    except Exception as e:
        print(f"[Application] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
