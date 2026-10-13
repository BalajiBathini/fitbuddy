"""
Build script: produces dist/FitBuddy/FitBuddy.exe via PyInstaller.

Run on a Windows machine with the project's virtualenv active:

    python build.py

This is a --onedir build (not --onefile): startup is faster and it's the
form the Inno Setup script in installer/fitbuddy.iss expects to package.
Switch to --onefile below if you'd rather trade startup time for a single
binary; both work fine with PyInstaller + PySide6.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"


def clean() -> None:
    for d in (DIST_DIR, BUILD_DIR):
        if d.exists():
            shutil.rmtree(d)
    spec_file = ROOT / "FitBuddy.spec"
    if spec_file.exists():
        spec_file.unlink()


def build() -> None:
    if sys.platform != "win32":
        print(
            "WARNING: PyInstaller is being run on a non-Windows platform.\n"
            "This will NOT produce a usable Windows .exe - PyInstaller cross-\n"
            "compilation is not supported. Run this script on Windows 10/11\n"
            "with the project's virtualenv active to get a real FitBuddy.exe.\n"
        )

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "FitBuddy",
        "--windowed",  # no console window - this is a background GUI agent
        "--onedir",
        "--noconfirm",
        "--clean",
        "--collect-all",
        "PySide6",
        str(ROOT / "app" / "main.py"),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)
    print(f"\nBuild complete: {DIST_DIR / 'FitBuddy' / 'FitBuddy.exe'}")
    print("Next: run installer/build_installer.bat (requires Inno Setup) to")
    print("produce 'FitBuddy Setup.exe'.")


if __name__ == "__main__":
    clean()
    build()
