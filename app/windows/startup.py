"""
Windows "start with Windows" registration (Section 21).

Uses the per-user registry Run key (HKEY_CURRENT_USER\\...\\Run), which:
    - requires no administrator privileges (Section 37: least privilege)
    - is the standard, Microsoft-documented mechanism for per-user autostart
    - is easy to cleanly remove on uninstall/opt-out

This intentionally does NOT use the Startup folder or a Scheduled Task,
though a Scheduled Task is noted as a reasonable alternative if finer
control (e.g. "run at logon with a delay") is needed later.
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger("fitbuddy.startup")

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REGISTRY_NAME = "FitBuddy"


def _winreg():
    import winreg  # noqa: F401  (import lazily; unavailable off-Windows)

    return winreg


def enable_startup(executable_path: str) -> bool:
    """Register FitBuddy to launch at Windows logon. Returns success bool."""
    if sys.platform != "win32":
        logger.info("enable_startup no-op on non-Windows platform")
        return False
    try:
        winreg = _winreg()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_REGISTRY_NAME, 0, winreg.REG_SZ, f'"{executable_path}"')
        logger.info("Registered FitBuddy for startup: %s", executable_path)
        return True
    except OSError:
        logger.exception("Failed to register startup entry")
        return False


def disable_startup() -> bool:
    if sys.platform != "win32":
        return False
    try:
        winreg = _winreg()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_REGISTRY_NAME)
        logger.info("Removed FitBuddy startup entry")
        return True
    except FileNotFoundError:
        return True  # already absent, that's fine
    except OSError:
        logger.exception("Failed to remove startup entry")
        return False


def is_startup_enabled() -> bool:
    if sys.platform != "win32":
        return False
    try:
        winreg = _winreg()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_REGISTRY_NAME)
            return True
    except (OSError, FileNotFoundError):
        return False
