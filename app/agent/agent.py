"""
FitBuddyAgent: the composition root for the background agent (Section 3
architecture diagram). Owns the scheduler and wires activity monitoring,
break/water/exercise reminders, and the notification gate together.

This module is UI-framework-agnostic: it exposes callback hooks
(on_break_due, on_water_due, on_exercise_due, on_creature_react, etc.) that
app/main.py connects to Qt slots (system tray, creature speech bubbles,
notification popups). This keeps the agent testable without a display and
keeps Qt out of the business logic.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Callable, Optional

from app.agent.activity_monitor import ActivityMonitor, ActivityState
from app.agent.break_manager import BreakManager, BreakManagerConfig
from app.agent.recommendation_engine import RecommendationContext, RuleBasedRecommendationEngine
from app.agent.scheduler import (
    ACTIVITY_POLL_SECONDS,
    FULLSCREEN_CHECK_SECONDS,
    REMINDER_EVALUATION_SECONDS,
    FitBuddyScheduler,
)
from app.database.database import Database
from app.database.repositories import (
    ActivityRepository,
    BreakRepository,
    DailySummaryRepository,
    SessionRepository,
    SettingsRepository,
    WaterRepository,
)
from app.fitness.activity_service import ActivityService
from app.fitness.statistics_service import StatisticsService
from app.fitness.water_service import WaterService
from app.notifications.notification_manager import (
    NotificationKind,
    NotificationManager,
    NotificationManagerConfig,
)
from app.windows.fullscreen import is_foreground_window_fullscreen
from app.windows.idle_detection import get_idle_time_source

logger = logging.getLogger("fitbuddy.agent")


@dataclass
class AgentCallbacks:
    on_break_due: Optional[Callable[[], None]] = None
    on_water_due: Optional[Callable[[], None]] = None
    on_exercise_due: Optional[Callable[[str], None]] = None
    on_evening_summary: Optional[Callable[[], None]] = None
    on_morning_greeting: Optional[Callable[[], None]] = None


class FitBuddyAgent:
    def __init__(self, db: Database, callbacks: Optional[AgentCallbacks] = None) -> None:
        self.db = db
        self.callbacks = callbacks or AgentCallbacks()

        self.settings_repo = SettingsRepository(db)
        self.session_repo = SessionRepository(db)
        self.activity_repo = ActivityRepository(db)
        self.water_repo = WaterRepository(db)
        self.break_repo = BreakRepository(db)
        self.summary_repo = DailySummaryRepository(db)

        from app.config import DEFAULT_SETTINGS

        self.settings_repo.seed_defaults(DEFAULT_SETTINGS)

        self.activity_service = ActivityService(self.activity_repo)
        self.water_service = WaterService(self.water_repo, self.settings_repo)
        self.statistics_service = StatisticsService(
            self.session_repo,
            self.activity_repo,
            self.water_repo,
            self.break_repo,
            self.summary_repo,
            water_goal_ml_provider=self.water_service.daily_goal_ml,
        )

        self.activity_monitor = ActivityMonitor(
            idle_source=get_idle_time_source(),
            session_repo=self.session_repo,
            idle_threshold_seconds=self.settings_repo.get("idle_threshold_minutes", 5) * 60,
        )
        self.break_manager = BreakManager(
            self.break_repo,
            BreakManagerConfig(
                break_interval_minutes=self.settings_repo.get("break_interval_minutes", 50),
                break_duration_minutes=self.settings_repo.get("break_duration_minutes", 5),
            ),
        )
        self.recommendation_engine = RuleBasedRecommendationEngine(
            break_interval_minutes=self.settings_repo.get("break_interval_minutes", 50),
            water_interval_minutes=self.settings_repo.get("water_interval_minutes", 60),
        )
        self.notification_manager = NotificationManager(
            NotificationManagerConfig(
                min_gap_minutes=self.settings_repo.get("min_notification_gap_minutes", 10),
                quiet_hours_start=self.settings_repo.get("quiet_hours_start", "22:30"),
                quiet_hours_end=self.settings_repo.get("quiet_hours_end", "07:00"),
                pause_on_fullscreen=self.settings_repo.get("pause_on_fullscreen", True),
                notifications_enabled=self.settings_repo.get("notifications_enabled", True),
            )
        )

        self.scheduler = FitBuddyScheduler()

    # -- lifecycle -----------------------------------------------------
    def start(self) -> None:
        self.scheduler.add_interval_job(self._tick_activity, ACTIVITY_POLL_SECONDS, "activity_poll")
        self.scheduler.add_interval_job(self._tick_fullscreen, FULLSCREEN_CHECK_SECONDS, "fullscreen_check")
        self.scheduler.add_interval_job(self._tick_reminders, REMINDER_EVALUATION_SECONDS, "reminder_eval")

        evening_time = str(self.settings_repo.get("evening_summary_time", "20:00"))
        hour, minute = (int(x) for x in evening_time.split(":"))
        self.scheduler.add_daily_job(self._fire_evening_summary, hour, minute, "evening_summary")

        self.scheduler.start()
        logger.info("FitBuddyAgent started")
        if self.callbacks.on_morning_greeting:
            self.callbacks.on_morning_greeting()

    def stop(self) -> None:
        self.activity_monitor.force_end_session(reason="shutdown")
        self.scheduler.shutdown()
        logger.info("FitBuddyAgent stopped")

    # -- OS lifecycle events (Section 33) --------------------------------
    def on_system_locked(self) -> None:
        self.activity_monitor.force_end_session(reason="lock")

    def on_system_sleeping(self) -> None:
        self.activity_monitor.force_end_session(reason="sleep")

    def on_system_resumed(self) -> None:
        # Recalculate rather than assume continuous activity - the next
        # poll will naturally start a fresh session once input resumes.
        logger.info("System resumed from sleep/unlock; monitor will resync on next poll")

    # -- scheduled ticks -------------------------------------------------
    def _tick_activity(self) -> None:
        try:
            self.activity_monitor.poll()
        except Exception:
            logger.exception("activity poll failed")

    def _tick_fullscreen(self) -> None:
        try:
            self.notification_manager.set_fullscreen_active(is_foreground_window_fullscreen())
        except Exception:
            logger.exception("fullscreen check failed")

    def _tick_reminders(self) -> None:
        try:
            self._evaluate_break()
            self._evaluate_water_and_exercise()
        except Exception:
            logger.exception("reminder evaluation failed")

    def _evaluate_break(self) -> None:
        active_seconds = self.activity_monitor.active_seconds_in_current_session()
        if self.break_manager.is_break_due(active_seconds):
            sent = self.notification_manager.try_send(NotificationKind.BREAK, {})
            if sent and self.callbacks.on_break_due:
                self.callbacks.on_break_due()

    def _evaluate_water_and_exercise(self) -> None:
        now = dt.datetime.utcnow()
        minutes_since_water = self.water_service.minutes_since_last_drink(now)
        last_break = self.break_repo.last_break_time()
        minutes_since_break = (
            (now - last_break).total_seconds() / 60.0 if last_break else None
        )
        context = RecommendationContext(
            active_minutes_today=self.activity_monitor.active_seconds_in_current_session() / 60.0,
            breaks_today=0,
            water_ml_today=self.water_service.today_total_ml(now),
            water_goal_ml=self.water_service.daily_goal_ml(),
            exercise_reps_today=0,
            minutes_since_last_break=minutes_since_break,
            minutes_since_last_water=minutes_since_water,
            is_evening=now.hour >= 18,
            consecutive_skips_by_kind={},
        )
        recommendation = self.recommendation_engine.get_recommendation(context)

        if recommendation.kind == "water":
            sent = self.notification_manager.try_send(NotificationKind.WATER, {})
            if sent and self.callbacks.on_water_due:
                self.callbacks.on_water_due()
        elif recommendation.kind == "exercise" and recommendation.exercise_key:
            sent = self.notification_manager.try_send(
                NotificationKind.EXERCISE, {"exercise_key": recommendation.exercise_key}
            )
            if sent and self.callbacks.on_exercise_due:
                self.callbacks.on_exercise_due(recommendation.exercise_key)

    def _fire_evening_summary(self) -> None:
        stats = self.statistics_service.compute_daily_stats()
        self.notification_manager.try_send(NotificationKind.SUMMARY, stats)
        if self.callbacks.on_evening_summary:
            self.callbacks.on_evening_summary()

    # -- user-initiated actions (creature menu / tray / notification buttons) --
    def start_break_now(self) -> int:
        break_id = self.break_manager.start_break()
        self.notification_manager.record_acknowledged(NotificationKind.BREAK)
        return break_id

    def finish_break(self, completed: bool = True) -> None:
        self.break_manager.finish_break(completed=completed)
        self.activity_monitor.reset_break_timer()

    def skip_break(self) -> None:
        self.break_manager.skip_break()
        self.notification_manager.record_skipped(NotificationKind.BREAK)

    def log_water(self, amount_ml: int) -> None:
        self.water_service.log_water(amount_ml, source="reminder")
        self.notification_manager.record_acknowledged(NotificationKind.WATER)

    def skip_water(self) -> None:
        self.notification_manager.record_skipped(NotificationKind.WATER)

    def complete_exercise(self, key: str, amount: float) -> None:
        self.activity_service.complete_activity(key, amount, source="reminder")
        self.notification_manager.record_acknowledged(NotificationKind.EXERCISE)

    def skip_exercise(self, key: str) -> None:
        self.activity_service.skip_activity(key, source="reminder")
        self.notification_manager.record_skipped(NotificationKind.EXERCISE)

    def pause_for(self, minutes: int) -> None:
        self.notification_manager.pause_for(minutes)

    def pause_until_tomorrow(self) -> None:
        self.notification_manager.pause_until_tomorrow()

    def resume_notifications(self) -> None:
        self.notification_manager.resume()
