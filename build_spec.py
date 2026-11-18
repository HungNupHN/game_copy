"""
Build Specification for PC Reviewer Deployer

This script generates PyInstaller batch files for building standalone .exe executables.

Prerequisites:
- Python 3.11+ installed on Windows
- pyinstaller package installed (pip install pyinstaller)

To build the application:
1. Run this script or copy its content to a .bat file
2. Build will output exe files in the root project directory
"""

import os
import subprocess


def build_exe_onefile():
    """Build a single-file executable with no console output and admin privileges."""
    
    print("=" * 60)
    print("PC Reviewer Deployer - Building Standalone .exe")
    print("=" * 60)
    print()
    
    # Project files to include in the build
    project_files = [
        "main.py",
        "utils.py",
        "config.py", 
        "auth.py",
        "deployers.py",
        "ui.py"
    ]
    
    for file in project_files:
        if not os.path.exists(file):
            print(f"Warning: {file} not found, skipping...")


def build_exe_command_onefile():
    """Generate and run PyInstaller command for single-file .exe."""
    
    print("Building executable with PyInstaller (onefile mode)...")
    print()
    
    # Run PyInstaller command
    pyinstaller_cmd = [
        "pyinstaller",
        "--clean",                    # Clean up intermediate files
        "--onefile",                  # Single-file output
        "--noconsole",                # No console window
        "--uac-admin",                # Request admin privileges
        "--target-platform=x86_64",  # Build for Windows 64-bit
        "build_exe",                  # Entry point script name
    ]
    
    try:
        print("Executing:", " ".join(pyinstaller_cmd))
        result = subprocess.run(
            pyinstaller_cmd,
            capture_output=False,
            shell=True,
            text=True
        )
        
        if result.returncode == 0:
            print()
            print("=" * 60)
            print("Build completed successfully!")
            print("Output location:", os.path.dirname(__file__))
            print("=" * 60)
        else:
            print()
            print("=" * 60)
            print("Build failed. Check output above for errors.")
            print("=" * 60)
            
    except Exception as e:
        print(f"Error during build: {e}")


def create_batch_file():
    """Create a batch file that users can run to build the exe."""
    
    batch_content = '''@echo off
REM PC Reviewer Deployer - Build Script
REM Builds standalone .exe with single-file, no-console, and admin privileges

setlocal enabledelayedexpansion

echo ============================================================
echo PC Reviewer Deployer - Build Process
echo ============================================================
echo.

REM Check if PyInstaller is installed
where pyinstaller >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: PyInstaller not found!
    echo Please install it with: pip install pyinstaller
    pause
    exit /b 1
)

REM Run PyInstaller build
echo Running PyInstaller...
pyinstaller --clean --onefile --noconsole --uac-admin --target-platform=x86_64 main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo ============================================================
    echo Build FAILED! Check the output above for errors.
    echo ============================================================
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Build completed successfully!
echo ============================================================
echo Output location: %CD%
echo.
echo To run the application, use the following command:
echo   .\dist\build_exe.exe
pause
exit /b 0
'''
    
    batch_path = Path(__file__).parent / "build_batch.bat"
    with open(batch_path, 'w', encoding='utf-8') as f:
        f.write(batch_content)
    
    print(f"Build batch file created at: {batch_path}")


def create_manual_build_script():
    """Create a Python script that users can use to manually build."""
    
    manual_script = '''"""
Manual Build Script for PC Reviewer Deployer

Run this script to build the standalone .exe executable.
"""

import subprocess
import sys

def main():
    print("=" * 60)
    print("PC Reviewer Deployer - Manual Build Process")
    print("=" * 60)
    print()
    
    # Run PyInstaller command for single-file executable
    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",                  # Clean intermediate files
        "--onefile",                # Single-file output
        "--noconsole",              # No console window
        "--uac-admin",              # Request admin privileges
        "--target-platform=x86_64",  # Build for Windows 64-bit
    ]
    
    try:
        print("Running:", " ".join(pyinstaller_cmd))
        subprocess.run(pyinstaller_cmd, capture_output=False, shell=True)
        
        print()
        print("=" * 60)
        print("Build completed successfully!")
        print("Output location:", __file__)
        print("=" * 60)
        print()
        print("To run the application:")
        print("  .\\dist\\build_exe.exe")
        
    except Exception as e:
        print(f"Error during build: {e}")


if __name__ == "__main__":
    main()
'''
    
    script_path = Path(__file__).parent / "manual_build.py"
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(manual_script)
    
    print(f"Manual build script created at: {script_path}")


def main():
    """Main build orchestration."""
    create_batch_file()
    create_manual_build_script()
    print()
    print("Build scripts created!")
    print("You can now:")
    print("  1. Run 'build_batch.bat' to build the executable")
    print("  2. Run 'manual_build.py' to build with a single command")
    print()


if __name__ == "__main__":
    main()
