"""
Build script to compile PC Reviewer Deployer into a standalone Windows .exe
using PyInstaller with --onefile, --noconsole, and --uac-admin flags.
"""

import sys
import subprocess
from pathlib import Path
import customtkinter


def build_executable() -> None:
    """Run PyInstaller with all required flags and bundled assets."""
    print("=" * 70)
    print("PC Reviewer Deployer - PyInstaller Executable Build")
    print("=" * 70)

    project_dir = Path(__file__).resolve().parent
    main_script = project_dir / "main.py"

    ctk_path = Path(customtkinter.__file__).resolve().parent

    target_name = "GameDeployer"
    idx = 2
    while (project_dir / "dist" / f"{target_name}.exe").exists():
        try:
            with open(project_dir / "dist" / f"{target_name}.exe", "r+b"):
                break
        except PermissionError:
            print(f"[Build] Note: {target_name}.exe is currently running/locked.")
            target_name = f"GameDeployer_v{idx}"
            idx += 1

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--noconsole",
        "--uac-admin",
        f"--name={target_name}",
        f"--add-data={ctk_path};customtkinter",
        "--collect-all=customtkinter",
        str(main_script),
    ]

    print("\n[Build Command]:")
    print(" ".join(cmd))
    print("\nStarting PyInstaller build process...\n")

    result = subprocess.run(cmd, cwd=str(project_dir))

    if result.returncode == 0:
        exe_output = project_dir / "dist" / f"{target_name}.exe"
        print("\n" + "=" * 70)
        print(f"BUILD SUCCESSFUL!")
        print(f"Standalone executable generated at:\n{exe_output}")
        if exe_output.exists():
            print(f"File size: {exe_output.stat().st_size / (1024*1024):.2f} MB")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print(f"BUILD FAILED with exit code: {result.returncode}")
        print("=" * 70)
        sys.exit(result.returncode)


if __name__ == "__main__":
    build_executable()
