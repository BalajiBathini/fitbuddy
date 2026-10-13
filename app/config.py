"""
Central configuration for FitBuddy.

Resolves platform-appropriate data/log directories and defines the default
settings values used the very first time the app runs (before any user
customization is stored in the database).

Design note: on Windows this resolves to %LOCALAPPDATA%\\FitBuddy\\.
On non-Windows platforms (used for local development / CI / this sandbox)
it falls back to ~/.local/share/FitBuddy so the whole codebase remains
importable and testable without a Windows machine.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


APP_NAME = "FitBuddy"


def get_app_data_dir() -> Path:
    """Return the per-user application data directory, creating it if needed."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            base = str(Path.home() / "AppData" / "Local")
        path = Path(base) / APP_NAME
    else:
        # Non-Windows fallback (dev/test environments).
        base = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
        path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_log_dir() -> Path:
    path = get_app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path() -> Path:
    return get_app_data_dir() / "fitbuddy.db"


# ---------------------------------------------------------------------------
# Default settings. These seed the `settings` table on first launch and are
# then user-editable via app/ui/settings.py. Keys mirror Section 25 of the
# spec (General / Fitness / Notifications / Creature / Privacy / Startup).
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS: dict[str, object] = {
    # General
    "start_with_windows": True,
    "language": "en",
    "theme": "light",
    # Fitness
    "break_interval_minutes": 50,
    "break_duration_minutes": 5,
    "water_interval_minutes": 60,
    "water_goal_ml": 2500,
    "idle_threshold_minutes": 5,
    # Notifications
    "notifications_enabled": True,
    "notification_sound": True,
    "quiet_hours_start": "22:30",
    "quiet_hours_end": "07:00",
    "pause_on_fullscreen": True,
    "min_notification_gap_minutes": 10,
    # Creature
    "creature_enabled": True,
    "movement_frequency": "normal",  # low | normal | high
    "movement_speed": "normal",      # slow | normal | fast
    "creature_size_px": 110,
    "idle_animations_enabled": True,
    # Privacy / misc
    "first_launch_complete": False,
    "evening_summary_time": "20:00",
}


@dataclass
class RuntimeConfig:
    """Non-user-facing runtime configuration (not stored in the DB)."""

    app_data_dir: Path = field(default_factory=get_app_data_dir)
    log_dir: Path = field(default_factory=get_log_dir)
    db_path: Path = field(default_factory=get_db_path)
    is_windows: bool = sys.platform == "win32"


RUNTIME = RuntimeConfig()
