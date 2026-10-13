"""
Active/idle session tracking (Section 10, Section 33).

This is a small state machine, polled periodically (e.g. every 15-30s by
the scheduler - NOT a tight busy loop, per Section 31 performance rules):

    ACTIVE  --(idle_seconds >= idle_threshold)-->  IDLE
    IDLE    --(user input detected again)      -->  ACTIVE (new session)
    ACTIVE  --(lock/sleep detected)             -->  IDLE (session closed, reason recorded)

`active_seconds_in_current_session()` is what break_manager polls to decide
whether a break reminder is due. Time is injected via a `now` callable and
the idle source is injected, so this whole module is testable without
Windows or wall-clock sleeps.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from app.database.repositories import SessionRepository
from app.windows.idle_detection import IdleTimeSource

logger = logging.getLogger("fitbuddy.activity_monitor")


class ActivityState(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"


@dataclass
class MonitorSnapshot:
    state: ActivityState
    active_seconds_current_session: float
    idle_seconds: float
    session_id: Optional[int]


class ActivityMonitor:
    def __init__(
        self,
        idle_source: IdleTimeSource,
        session_repo: SessionRepository,
        idle_threshold_seconds: float = 300.0,
        now_fn: Callable[[], dt.datetime] = dt.datetime.utcnow,
    ) -> None:
        self.idle_source = idle_source
        self.session_repo = session_repo
        self.idle_threshold_seconds = idle_threshold_seconds
        self._now_fn = now_fn

        self.state = ActivityState.IDLE
        self._current_session_id: Optional[int] = None
        self._session_started_at: Optional[dt.datetime] = None
        self._last_poll_at: Optional[dt.datetime] = None
        self._active_seconds_accum: float = 0.0

    def set_idle_threshold_minutes(self, minutes: float) -> None:
        self.idle_threshold_seconds = minutes * 60.0

    def poll(self) -> MonitorSnapshot:
        """
        Called periodically by the scheduler. Reads current idle seconds and
        advances the state machine. Cheap: one Win32 call + light bookkeeping.
        """
        now = self._now_fn()
        idle_seconds = self.idle_source.get_idle_seconds()
        is_idle_now = idle_seconds >= self.idle_threshold_seconds

        if self.state == ActivityState.IDLE and not is_idle_now:
            self._start_session(now)
        elif self.state == ActivityState.ACTIVE and is_idle_now:
            self._end_session(now, reason="idle_timeout")
        elif self.state == ActivityState.ACTIVE and not is_idle_now:
            self._accumulate_active_time(now)

        self._last_poll_at = now
        return MonitorSnapshot(
            state=self.state,
            active_seconds_current_session=self._active_seconds_accum,
            idle_seconds=idle_seconds,
            session_id=self._current_session_id,
        )

    def _start_session(self, now: dt.datetime) -> None:
        self.state = ActivityState.ACTIVE
        self._session_started_at = now
        self._active_seconds_accum = 0.0
        self._current_session_id = self.session_repo.start_session(now)
        self._last_poll_at = now
        logger.info("Active session started (id=%s)", self._current_session_id)

    def _accumulate_active_time(self, now: dt.datetime) -> None:
        if self._last_poll_at is None:
            return
        delta = (now - self._last_poll_at).total_seconds()
        # Guard against clock jumps (Section 32: handle system clock changes
        # reasonably) - never let a single poll add a wildly large or
        # negative amount of active time.
        delta = max(0.0, min(delta, 300.0))
        self._active_seconds_accum += delta

    def _end_session(self, now: dt.datetime, reason: str) -> None:
        if self._current_session_id is not None:
            self.session_repo.end_session(
                self._current_session_id,
                ended_at=now,
                active_seconds=int(self._active_seconds_accum),
                idle_seconds=0,
                end_reason=reason,
            )
            logger.info(
                "Session %s ended (%ds active, reason=%s)",
                self._current_session_id,
                int(self._active_seconds_accum),
                reason,
            )
        self.state = ActivityState.IDLE
        self._current_session_id = None
        self._session_started_at = None
        self._active_seconds_accum = 0.0

    def force_end_session(self, reason: str) -> None:
        """Called on lock/sleep/shutdown so we never lose an open session."""
        if self.state == ActivityState.ACTIVE:
            self._end_session(self._now_fn(), reason=reason)

    def reset_break_timer(self) -> None:
        """
        Called by break_manager once a break is acknowledged - the "50
        minutes active" clock restarts without ending the underlying
        session (the user is still working today, just took a break).
        """
        self._active_seconds_accum = 0.0

    def active_seconds_in_current_session(self) -> float:
        return self._active_seconds_accum
