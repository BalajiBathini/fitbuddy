"""Water intake tracking service (Section 13)."""

from __future__ import annotations

import datetime as dt

from app.database.repositories import SettingsRepository, WaterRepository

PRESET_AMOUNTS_ML = (250, 500, 750)


class WaterService:
    def __init__(self, water_repo: WaterRepository, settings_repo: SettingsRepository) -> None:
        self.repo = water_repo
        self.settings = settings_repo

    def log_water(self, amount_ml: int, source: str = "manual") -> int:
        if amount_ml <= 0:
            raise ValueError("amount_ml must be positive")
        return self.repo.log_water(amount_ml, source=source)

    def today_total_ml(self, now: dt.datetime | None = None) -> int:
        now = now or dt.datetime.utcnow()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return self.repo.total_between(start_of_day, now)

    def daily_goal_ml(self) -> int:
        return int(self.settings.get("water_goal_ml", 2500))

    def progress_fraction(self, now: dt.datetime | None = None) -> float:
        goal = self.daily_goal_ml()
        if goal <= 0:
            return 0.0
        return min(1.0, self.today_total_ml(now) / goal)

    def minutes_since_last_drink(self, now: dt.datetime | None = None) -> float | None:
        now = now or dt.datetime.utcnow()
        last = self.repo.last_entry_time()
        if last is None:
            return None
        return (now - last).total_seconds() / 60.0
