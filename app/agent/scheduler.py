"""
Thin wrapper around APScheduler's BackgroundScheduler (Section 31: use
timers/events, never busy-poll). Centralizing job registration here makes it
easy to see every periodic job FitBuddy runs and their intervals at a glance.
"""

from __future__ import annotations

import logging
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger("fitbuddy.scheduler")

# Poll intervals chosen to keep background CPU usage negligible (Section 31)
# while still feeling responsive.
ACTIVITY_POLL_SECONDS = 20
FULLSCREEN_CHECK_SECONDS = 15
REMINDER_EVALUATION_SECONDS = 30
CREATURE_IDLE_TICK_SECONDS = 8


class FitBuddyScheduler:
    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler(daemon=True)
        self._job_ids: list[str] = []

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("Scheduler started")

    def shutdown(self, wait: bool = False) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=wait)
            logger.info("Scheduler stopped")

    def add_interval_job(self, func: Callable[[], None], seconds: int, job_id: str) -> None:
        self._scheduler.add_job(
            func,
            "interval",
            seconds=seconds,
            id=job_id,
            replace_existing=True,
            max_instances=1,  # never let a slow run pile up concurrent calls
            coalesce=True,
            misfire_grace_time=30,
        )
        self._job_ids.append(job_id)
        logger.debug("Registered job %s every %ds", job_id, seconds)

    def add_daily_job(self, func: Callable[[], None], hour: int, minute: int, job_id: str) -> None:
        self._scheduler.add_job(
            func,
            "cron",
            hour=hour,
            minute=minute,
            id=job_id,
            replace_existing=True,
            misfire_grace_time=3600,
        )
        self._job_ids.append(job_id)
        logger.debug("Registered daily job %s at %02d:%02d", job_id, hour, minute)

    def remove_job(self, job_id: str) -> None:
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass
