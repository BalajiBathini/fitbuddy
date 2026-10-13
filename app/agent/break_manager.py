"""
Break reminder logic (Section 11-12). Decides *when* a break is due based on
active time in the current session, and manages the lifecycle of an
in-progress break (start / countdown / finish / skip).

Kept separate from NotificationManager: this module owns "is a break due
and what state is the current break in", while NotificationManager owns
"are we currently allowed to interrupt the user at all". agent.py wires
the two together.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.database.repositories import BreakRepository


class BreakPhase(str, Enum):
    NONE = "none"
    IN_PROGRESS = "in_progress"


@dataclass
class BreakManagerConfig:
    break_interval_minutes: int = 50
    break_duration_minutes: int = 5


class BreakManager:
    def __init__(self, break_repo: BreakRepository, config: BreakManagerConfig) -> None:
        self.repo = break_repo
        self.config = config
        self.phase = BreakPhase.NONE
        self._current_break_id: Optional[int] = None
        self._break_started_at: Optional[dt.datetime] = None

    def is_break_due(self, active_seconds_current_session: float) -> bool:
        if self.phase == BreakPhase.IN_PROGRESS:
            return False
        return active_seconds_current_session >= self.config.break_interval_minutes * 60

    def start_break(self, now: Optional[dt.datetime] = None) -> int:
        now = now or dt.datetime.utcnow()
        self._current_break_id = self.repo.start_break(self.config.break_duration_minutes)
        self._break_started_at = now
        self.phase = BreakPhase.IN_PROGRESS
        return self._current_break_id

    def remaining_seconds(self, now: Optional[dt.datetime] = None) -> float:
        if self.phase != BreakPhase.IN_PROGRESS or self._break_started_at is None:
            return 0.0
        now = now or dt.datetime.utcnow()
        elapsed = (now - self._break_started_at).total_seconds()
        total = self.config.break_duration_minutes * 60
        return max(0.0, total - elapsed)

    def finish_break(self, now: Optional[dt.datetime] = None, completed: bool = True) -> None:
        if self._current_break_id is None or self._break_started_at is None:
            self.phase = BreakPhase.NONE
            return
        now = now or dt.datetime.utcnow()
        actual = int((now - self._break_started_at).total_seconds())
        self.repo.finish_break(self._current_break_id, actual_duration_seconds=actual, completed=completed)
        self._reset()

    def skip_break(self) -> None:
        if self._current_break_id is not None:
            self.repo.skip_break(self._current_break_id)
        self._reset()

    def _reset(self) -> None:
        self.phase = BreakPhase.NONE
        self._current_break_id = None
        self._break_started_at = None
