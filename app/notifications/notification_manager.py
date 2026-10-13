"""
Notification manager: the gatekeeper for every reminder FitBuddy wants to
show (Sections 23, 24, 29). This module is intentionally pure Python (no Qt,
no Windows APIs) so its rules can be unit tested precisely:

    * Never more than one active fitness notification at a time.
    * Minimum gap between notifications (default 10 min).
    * Respect quiet hours (default 22:30 - 07:00, wraps midnight).
    * Respect pause mode (30 min / 1 hour / until tomorrow).
    * Respect full-screen suppression.
    * Adaptive backoff: after N consecutive skips of a given kind, go quiet
      on that kind for a cooldown window rather than repeating immediately.

The actual on-screen rendering (toast/balloon/custom Qt popup) is injected
as a callable so this class stays platform-agnostic and testable without a
display. app/agent/agent.py wires a real Qt/Windows-toast callback in.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger("fitbuddy.notifications")


class NotificationKind(str, Enum):
    BREAK = "break"
    WATER = "water"
    EXERCISE = "exercise"
    SUMMARY = "summary"
    INFO = "info"  # low-priority, e.g. "good morning" - never gated by cooldown


@dataclass
class PauseState:
    paused_until: Optional[dt.datetime] = None

    def is_paused(self, now: dt.datetime) -> bool:
        return self.paused_until is not None and now < self.paused_until

    def clear_if_expired(self, now: dt.datetime) -> None:
        if self.paused_until is not None and now >= self.paused_until:
            self.paused_until = None


@dataclass
class _SkipTracker:
    consecutive_skips: int = 0
    backoff_until: Optional[dt.datetime] = None


@dataclass
class NotificationManagerConfig:
    min_gap_minutes: int = 10
    quiet_hours_start: str = "22:30"
    quiet_hours_end: str = "07:00"
    pause_on_fullscreen: bool = True
    notifications_enabled: bool = True
    skip_backoff_threshold: int = 3
    skip_backoff_minutes: int = 60


class NotificationManager:
    """
    Stateful gatekeeper. Call `can_send(kind, now)` before showing anything,
    then call `record_sent(kind, now)` once it's actually shown. Call
    `record_skipped(kind)` / `record_acknowledged(kind)` after the user
    responds so adaptive backoff and cooldown-reset logic can react.
    """

    def __init__(
        self,
        config: NotificationManagerConfig,
        send_callback: Optional[Callable[[NotificationKind, object], None]] = None,
    ) -> None:
        self.config = config
        self.send_callback = send_callback
        self.pause_state = PauseState()
        self.is_fullscreen_active: bool = False
        self._last_sent_at: Optional[dt.datetime] = None
        self._active_notification: Optional[NotificationKind] = None
        self._skip_trackers: dict[NotificationKind, _SkipTracker] = {
            kind: _SkipTracker() for kind in NotificationKind
        }

    # -- Pause mode -----------------------------------------------------
    def pause_for(self, minutes: int, now: Optional[dt.datetime] = None) -> None:
        now = now or dt.datetime.utcnow()
        self.pause_state.paused_until = now + dt.timedelta(minutes=minutes)
        logger.info("Notifications paused until %s", self.pause_state.paused_until)

    def pause_until_tomorrow(self, now: Optional[dt.datetime] = None) -> None:
        now = now or dt.datetime.utcnow()
        tomorrow = (now + dt.timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
        self.pause_state.paused_until = tomorrow

    def resume(self) -> None:
        self.pause_state.paused_until = None

    # -- Full-screen ------------------------------------------------------
    def set_fullscreen_active(self, active: bool) -> None:
        self.is_fullscreen_active = active

    # -- Quiet hours -------------------------------------------------------
    def _in_quiet_hours(self, now: dt.datetime) -> bool:
        start = _parse_hhmm(self.config.quiet_hours_start)
        end = _parse_hhmm(self.config.quiet_hours_end)
        current = now.time()
        if start <= end:
            return start <= current < end
        # Wraps midnight, e.g. 22:30 -> 07:00
        return current >= start or current < end

    # -- Core gate -----------------------------------------------------
    def can_send(self, kind: NotificationKind, now: Optional[dt.datetime] = None) -> tuple[bool, str]:
        """Returns (allowed, reason). reason is human-readable for logging/tests."""
        now = now or dt.datetime.utcnow()
        self.pause_state.clear_if_expired(now)

        if not self.config.notifications_enabled:
            return False, "notifications_disabled"

        if kind != NotificationKind.INFO:
            if self.pause_state.is_paused(now):
                return False, "paused"

            if self.is_fullscreen_active and self.config.pause_on_fullscreen:
                return False, "fullscreen_active"

            if self._in_quiet_hours(now):
                return False, "quiet_hours"

            if self._active_notification is not None:
                return False, "another_notification_active"

            if self._last_sent_at is not None:
                elapsed = (now - self._last_sent_at).total_seconds() / 60.0
                if elapsed < self.config.min_gap_minutes:
                    return False, "min_gap_not_elapsed"

            tracker = self._skip_trackers[kind]
            if tracker.backoff_until is not None and now < tracker.backoff_until:
                return False, "adaptive_backoff"

        return True, "ok"

    def try_send(
        self, kind: NotificationKind, payload: object, now: Optional[dt.datetime] = None
    ) -> bool:
        allowed, reason = self.can_send(kind, now)
        if not allowed:
            logger.debug("Suppressed %s notification: %s", kind.value, reason)
            return False
        now = now or dt.datetime.utcnow()
        self._last_sent_at = now
        if kind != NotificationKind.INFO:
            self._active_notification = kind
        if self.send_callback:
            self.send_callback(kind, payload)
        logger.info("Sent %s notification", kind.value)
        return True

    # -- Post-response bookkeeping --------------------------------------
    def record_dismissed(self, kind: NotificationKind) -> None:
        """Call once the notification/popup is closed (any outcome)."""
        if self._active_notification == kind:
            self._active_notification = None

    def record_acknowledged(self, kind: NotificationKind) -> None:
        """User engaged positively (started break, drank water, did exercise)."""
        self._skip_trackers[kind] = _SkipTracker()
        self.record_dismissed(kind)

    def record_skipped(self, kind: NotificationKind, now: Optional[dt.datetime] = None) -> None:
        now = now or dt.datetime.utcnow()
        tracker = self._skip_trackers[kind]
        tracker.consecutive_skips += 1
        if tracker.consecutive_skips >= self.config.skip_backoff_threshold:
            tracker.backoff_until = now + dt.timedelta(minutes=self.config.skip_backoff_minutes)
            logger.info(
                "%s skipped %d times in a row; backing off until %s",
                kind.value,
                tracker.consecutive_skips,
                tracker.backoff_until,
            )
        self.record_dismissed(kind)


def _parse_hhmm(value: str) -> dt.time:
    hour, minute = value.split(":")
    return dt.time(hour=int(hour), minute=int(minute))
