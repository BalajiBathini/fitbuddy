"""
FitBuddy entry point.

Composition root: creates the QApplication, the Database + FitBuddyAgent
(backend), and the Qt-facing pieces (creature window, tray, dashboard,
settings, popups), then wires them together via the AgentCallbacks hooks
so the agent itself never imports Qt.

Run with:  python -m app.main
"""

from __future__ import annotations

import logging
import logging.handlers
import random
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from app.agent.agent import AgentCallbacks, FitBuddyAgent
from app.config import RUNTIME, get_log_dir
from app.creature.animation_controller import AnimationState
from app.creature.creature_window import CreatureWindow
from app.creature.movement_controller import MovementController, Rect
from app.database.database import get_database
from app.fitness.activity_service import EXERCISE_CATALOG
from app.notifications import notification_templates as templates
from app.notifications.notification_manager import NotificationKind
from app.ui.break_widget import BreakCountdownWidget
from app.ui.creature_menu import show_creature_menu
from app.ui.dashboard import Dashboard
from app.ui.first_launch_wizard import FirstLaunchWizard
from app.ui.notification_popup import NotificationPopup
from app.ui.settings import SettingsDialog
from app.ui.system_tray import SystemTray


def _setup_logging() -> None:
    log_dir = get_log_dir()
    handler = logging.handlers.RotatingFileHandler(
        log_dir / "fitbuddy.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("fitbuddy")
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    # Never crash on unhandled exceptions in Qt callbacks - log and continue,
    # per Section 32/35 (never show raw exceptions, never crash the agent).
    sys.excepthook = _log_unhandled_exception


def _log_unhandled_exception(exc_type, exc_value, exc_tb) -> None:
    logging.getLogger("fitbuddy").exception(
        "Unhandled exception", exc_info=(exc_type, exc_value, exc_tb)
    )


class FitBuddyApplication:
    def __init__(self) -> None:
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.db = get_database(RUNTIME.db_path)
        self.agent = FitBuddyAgent(
            self.db,
            AgentCallbacks(
                on_break_due=self._on_break_due,
                on_water_due=self._on_water_due,
                on_exercise_due=self._on_exercise_due,
                on_evening_summary=self._on_evening_summary,
                on_morning_greeting=self._on_morning_greeting,
            ),
        )

        self.dashboard: Dashboard | None = None
        self.creature: CreatureWindow | None = None
        self.movement: MovementController | None = None
        self._active_popup: NotificationPopup | None = None
        self._creature_move_timer: QTimer | None = None
        self._creature_paint_timer: QTimer | None = None
        self._lock_poll_timer: QTimer | None = None
        self._was_locked = False

    # -- startup ---------------------------------------------------------
    def run(self) -> int:
        if not self.agent.settings_repo.get("first_launch_complete", False):
            wizard = FirstLaunchWizard(self.agent.settings_repo)
            wizard.exec()

        if self.agent.settings_repo.get("creature_enabled", True):
            self._create_creature()

        self.tray = SystemTray(
            on_open_dashboard=self.show_dashboard,
            on_todays_progress=self.show_dashboard,
            on_take_break_now=self._start_break_now,
            on_drink_water=lambda: self._log_water(250),
            on_pause_30=lambda: self.agent.pause_for(30),
            on_pause_60=lambda: self.agent.pause_for(60),
            on_settings=self.show_settings,
            on_about=self._show_about,
            on_exit=self.quit,
        )
        self.tray.show()

        self.agent.start()
        self._start_lock_watcher()

        return self.app.exec()

    def _create_creature(self) -> None:
        size = int(self.agent.settings_repo.get("creature_size_px", 110))
        speed = str(self.agent.settings_repo.get("movement_speed", "normal"))
        safe_area = self._compute_safe_area()

        self.movement = MovementController(safe_area, creature_size=size, speed_key=speed)
        self.creature = CreatureWindow(size)
        self.creature.clicked.connect(self._on_creature_clicked)
        x, y = self.movement.position()
        self.creature.move_to_position(x, y - self.creature.bubble_area_h)
        self.creature.show()

        self._creature_paint_timer = QTimer()
        self._creature_paint_timer.timeout.connect(self._tick_creature_movement)
        self._creature_paint_timer.start(1000 // 30)

        frequency = str(self.agent.settings_repo.get("movement_frequency", "normal"))
        interval_ms = {"low": 90_000, "normal": 45_000, "high": 20_000}.get(frequency, 45_000)
        self._creature_move_timer = QTimer()
        self._creature_move_timer.timeout.connect(self._wander)
        self._creature_move_timer.start(interval_ms)

    def _compute_safe_area(self) -> Rect:
        """Multi-monitor-aware safe area using the primary screen's available
        geometry (already excludes the taskbar on Windows)."""
        screen = self.app.primaryScreen()
        geo = screen.availableGeometry() if screen else None
        if geo is None:
            return Rect(0, 0, 1920, 1040)
        return Rect(geo.left(), geo.top(), geo.right(), geo.bottom())

    # -- creature movement/animation ticks --------------------------------
    def _tick_creature_movement(self) -> None:
        if not self.movement or not self.creature:
            return
        was_moving = self.movement.is_moving
        self.movement.update(1.0 / 30.0)
        x, y = self.movement.position()
        self.creature.move_to_position(x, y - self.creature.bubble_area_h)

        if self.movement.is_moving:
            state = AnimationState.WALK_RIGHT if self.movement.facing_right else AnimationState.WALK_LEFT
            self.creature.set_animation_state(state)
        elif was_moving:
            self.creature.set_animation_state(AnimationState.IDLE)

    def _wander(self) -> None:
        if not self.movement:
            return
        choice = random.choice(["left_to_right", "right_to_left", "random"])
        if choice == "left_to_right":
            self.movement.walk_left_to_right()
        elif choice == "right_to_left":
            self.movement.walk_right_to_left()
        else:
            self.movement.walk_to_random_position()

    def _on_creature_clicked(self) -> None:
        show_creature_menu(
            on_drink_water=lambda: self._log_water(250),
            on_exercise=self._show_quick_exercise,
            on_progress=self.show_dashboard,
            on_settings=self.show_settings,
            on_pause=lambda: self.agent.pause_for(30),
        )

    # -- lock/sleep handling (Section 33) ---------------------------------
    def _start_lock_watcher(self) -> None:
        """
        Polls session-lock state every few seconds. A real production build
        would additionally subscribe to WM_WTSSESSION_CHANGE via a native
        event filter for instant notification; polling is the documented,
        always-safe fallback (Section 32: graceful fallback when a feature
        isn't reliable on all Windows configurations).
        """
        from app.windows.idle_detection import is_session_locked

        self._lock_poll_timer = QTimer()

        def check() -> None:
            locked = is_session_locked()
            if locked and not self._was_locked:
                self.agent.on_system_locked()
            elif not locked and self._was_locked:
                self.agent.on_system_resumed()
            self._was_locked = locked

        self._lock_poll_timer.timeout.connect(check)
        self._lock_poll_timer.start(10_000)

    # -- agent callback handlers (backend -> UI) ---------------------------
    def _on_break_due(self) -> None:
        content = templates.break_notification()
        if self.creature:
            self.creature.show_speech_bubble(content.body)
            self.creature.set_animation_state(AnimationState.NOTIFICATION)

        def start_break() -> None:
            self.agent.notification_manager.record_acknowledged(NotificationKind.BREAK)
            self._start_break_now()

        def remind_later() -> None:
            self.agent.notification_manager.record_dismissed(NotificationKind.BREAK)

        def skip() -> None:
            self.agent.skip_break()

        self._show_popup(content.title, content.body, [
            ("Start Break", start_break),
            ("Remind Later", remind_later),
            ("Skip", skip),
        ])

    def _on_water_due(self) -> None:
        content = templates.water_notification()
        if self.creature:
            self.creature.show_speech_bubble("Water time! \U0001F4A7")

        self._show_popup(content.title, content.body, [
            ("250 ml", lambda: self._log_water(250)),
            ("500 ml", lambda: self._log_water(500)),
            ("Skip", self.agent.skip_water),
        ])

    def _on_exercise_due(self, exercise_key: str) -> None:
        exercise = EXERCISE_CATALOG[exercise_key]
        content = templates.exercise_notification(exercise.name, exercise.default_target, exercise.unit)
        if self.creature:
            self.creature.show_speech_bubble(f"{exercise.name} time!")

        self._show_popup(content.title, content.body, [
            ("Start", lambda: self._complete_exercise(exercise_key, exercise.default_target)),
            ("Skip", lambda: self.agent.skip_exercise(exercise_key)),
        ])

    def _on_evening_summary(self) -> None:
        stats = self.agent.statistics_service.compute_daily_stats()
        from app.notifications.notification_templates import evening_summary
        from app.fitness.statistics_service import DailyStats

        content = evening_summary(
            active_hm=f"{stats.active_seconds // 3600}h {(stats.active_seconds % 3600) // 60}m",
            breaks_count=stats.breaks_count,
            water_ml=stats.water_ml,
            water_goal_ml=stats.water_goal_ml,
            exercise_reps=stats.exercise_reps,
            score=stats.daily_score,
        )
        self._show_popup(content.title, content.body, [("Nice!", lambda: None)], auto_dismiss_ms=8000)

    def _on_morning_greeting(self) -> None:
        if self.creature:
            self.creature.show_speech_bubble(templates.MORNING_GREETING, duration_ms=3500)

    # -- user actions -----------------------------------------------------
    def _start_break_now(self) -> None:
        self.agent.start_break_now()

        def on_done(completed: bool) -> None:
            self.agent.finish_break(completed=completed)
            if self.creature and completed:
                self.creature.set_animation_state(AnimationState.HAPPY)
                self.creature.show_speech_bubble(templates.celebration_message(), duration_ms=2500)

        duration_seconds = int(self.agent.settings_repo.get("break_duration_minutes", 5)) * 60
        widget = BreakCountdownWidget(duration_seconds, on_done)
        widget.show()
        self._break_widget = widget  # keep a reference alive

    def _log_water(self, amount_ml: int) -> None:
        self.agent.log_water(amount_ml)
        if self.creature:
            self.creature.set_animation_state(AnimationState.DRINKING)
            self.creature.show_speech_bubble("Thanks for the water! \U0001F4A7", duration_ms=2000)
            QTimer.singleShot(2200, lambda: self.creature.set_animation_state(AnimationState.IDLE))

    def _complete_exercise(self, key: str, amount: float) -> None:
        self.agent.complete_exercise(key, amount)
        if self.creature:
            self.creature.set_animation_state(AnimationState.HAPPY)
            self.creature.show_speech_bubble(templates.celebration_message(), duration_ms=2500)
            QTimer.singleShot(2600, lambda: self.creature.set_animation_state(AnimationState.IDLE))

    def _show_quick_exercise(self) -> None:
        key = random.choice(["squats", "pushups", "stretching"])
        exercise = EXERCISE_CATALOG[key]
        self._show_popup(
            "QUICK FITNESS BREAK",
            f"Let's do {exercise.default_target:g} {exercise.unit} of {exercise.name.lower()}!",
            [
                ("Start", lambda: self._complete_exercise(key, exercise.default_target)),
                ("Skip", lambda: self.agent.skip_exercise(key)),
            ],
        )

    def show_dashboard(self) -> None:
        if self.dashboard is None:
            self.dashboard = Dashboard(
                self.agent.statistics_service,
                self.agent.activity_repo,
                self.agent.water_repo,
                self.agent.break_repo,
            )
        self.dashboard.refresh()
        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()

    def show_settings(self) -> None:
        dialog = SettingsDialog(self.agent.settings_repo, on_saved=self._apply_settings_changes)
        dialog.exec()

    def _apply_settings_changes(self) -> None:
        # Re-apply the settings that affect already-constructed objects.
        self.agent.activity_monitor.set_idle_threshold_minutes(
            self.agent.settings_repo.get("idle_threshold_minutes", 5)
        )
        self.agent.break_manager.config.break_interval_minutes = self.agent.settings_repo.get(
            "break_interval_minutes", 50
        )
        self.agent.break_manager.config.break_duration_minutes = self.agent.settings_repo.get(
            "break_duration_minutes", 5
        )
        self.agent.notification_manager.config.quiet_hours_start = self.agent.settings_repo.get(
            "quiet_hours_start", "22:30"
        )
        self.agent.notification_manager.config.quiet_hours_end = self.agent.settings_repo.get(
            "quiet_hours_end", "07:00"
        )
        self.agent.notification_manager.config.notifications_enabled = self.agent.settings_repo.get(
            "notifications_enabled", True
        )
        self.agent.notification_manager.config.pause_on_fullscreen = self.agent.settings_repo.get(
            "pause_on_fullscreen", True
        )

    def _show_about(self) -> None:
        QMessageBox.information(
            None,
            "About FitBuddy",
            "FitBuddy \U0001F43E\n\nA cute desktop fitness companion.\nAll your data stays on this computer.",
        )

    def _show_popup(self, title, body, buttons, auto_dismiss_ms=None) -> None:
        if self._active_popup is not None:
            self._active_popup.close()
        popup = NotificationPopup(title, body, buttons, auto_dismiss_ms=auto_dismiss_ms)
        popup.show_popup()
        self._active_popup = popup

    def quit(self) -> None:
        self.agent.stop()
        self.app.quit()


def main() -> int:
    _setup_logging()
    try:
        app = FitBuddyApplication()
        return app.run()
    except Exception:
        logging.getLogger("fitbuddy").exception("Fatal error during startup")
        raise


if __name__ == "__main__":
    sys.exit(main())
