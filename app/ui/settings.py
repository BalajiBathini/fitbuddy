"""Settings dialog (Section 25). Reads/writes via SettingsRepository."""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QTabWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QTime

from app.database.repositories import SettingsRepository


class SettingsDialog(QDialog):
    def __init__(self, settings_repo: SettingsRepository, on_saved: Callable[[], None] | None = None) -> None:
        super().__init__(None)
        self.setWindowTitle("FitBuddy Settings")
        self.resize(420, 480)
        self.repo = settings_repo
        self.on_saved = on_saved

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_fitness_tab(), "Fitness")
        tabs.addTab(self._build_notifications_tab(), "Notifications")
        tabs.addTab(self._build_creature_tab(), "Creature")
        tabs.addTab(self._build_privacy_tab(), "Privacy")

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.start_with_windows = QCheckBox("Start FitBuddy with Windows")
        self.start_with_windows.setChecked(bool(self.repo.get("start_with_windows", True)))
        form.addRow(self.start_with_windows)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["light", "dark"])
        self.theme_combo.setCurrentText(str(self.repo.get("theme", "light")))
        form.addRow("Theme:", self.theme_combo)

        return w

    def _build_fitness_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.break_interval = QSpinBox()
        self.break_interval.setRange(15, 180)
        self.break_interval.setSuffix(" min")
        self.break_interval.setValue(int(self.repo.get("break_interval_minutes", 50)))
        form.addRow("Break interval:", self.break_interval)

        self.break_duration = QSpinBox()
        self.break_duration.setRange(1, 30)
        self.break_duration.setSuffix(" min")
        self.break_duration.setValue(int(self.repo.get("break_duration_minutes", 5)))
        form.addRow("Break duration:", self.break_duration)

        self.water_interval = QSpinBox()
        self.water_interval.setRange(15, 240)
        self.water_interval.setSuffix(" min")
        self.water_interval.setValue(int(self.repo.get("water_interval_minutes", 60)))
        form.addRow("Water reminder interval:", self.water_interval)

        self.water_goal = QSpinBox()
        self.water_goal.setRange(500, 6000)
        self.water_goal.setSingleStep(250)
        self.water_goal.setSuffix(" ml")
        self.water_goal.setValue(int(self.repo.get("water_goal_ml", 2500)))
        form.addRow("Daily water goal:", self.water_goal)

        self.idle_threshold = QSpinBox()
        self.idle_threshold.setRange(1, 30)
        self.idle_threshold.setSuffix(" min")
        self.idle_threshold.setValue(int(self.repo.get("idle_threshold_minutes", 5)))
        form.addRow("Idle threshold:", self.idle_threshold)

        return w

    def _build_notifications_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.notifications_enabled = QCheckBox("Enable notifications")
        self.notifications_enabled.setChecked(bool(self.repo.get("notifications_enabled", True)))
        form.addRow(self.notifications_enabled)

        self.notification_sound = QCheckBox("Notification sound")
        self.notification_sound.setChecked(bool(self.repo.get("notification_sound", True)))
        form.addRow(self.notification_sound)

        self.quiet_start = QTimeEdit()
        self.quiet_start.setDisplayFormat("HH:mm")
        self.quiet_start.setTime(QTime.fromString(str(self.repo.get("quiet_hours_start", "22:30")), "HH:mm"))
        form.addRow("Quiet hours start:", self.quiet_start)

        self.quiet_end = QTimeEdit()
        self.quiet_end.setDisplayFormat("HH:mm")
        self.quiet_end.setTime(QTime.fromString(str(self.repo.get("quiet_hours_end", "07:00")), "HH:mm"))
        form.addRow("Quiet hours end:", self.quiet_end)

        self.pause_fullscreen = QCheckBox("Pause notifications during full-screen apps")
        self.pause_fullscreen.setChecked(bool(self.repo.get("pause_on_fullscreen", True)))
        form.addRow(self.pause_fullscreen)

        return w

    def _build_creature_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.creature_enabled = QCheckBox("Show Bobo on the desktop")
        self.creature_enabled.setChecked(bool(self.repo.get("creature_enabled", True)))
        form.addRow(self.creature_enabled)

        self.movement_frequency = QComboBox()
        self.movement_frequency.addItems(["low", "normal", "high"])
        self.movement_frequency.setCurrentText(str(self.repo.get("movement_frequency", "normal")))
        form.addRow("Movement frequency:", self.movement_frequency)

        self.movement_speed = QComboBox()
        self.movement_speed.addItems(["slow", "normal", "fast"])
        self.movement_speed.setCurrentText(str(self.repo.get("movement_speed", "normal")))
        form.addRow("Movement speed:", self.movement_speed)

        self.creature_size = QSpinBox()
        self.creature_size.setRange(80, 140)
        self.creature_size.setSuffix(" px")
        self.creature_size.setValue(int(self.repo.get("creature_size_px", 110)))
        form.addRow("Creature size:", self.creature_size)

        self.idle_animations = QCheckBox("Enable idle animations")
        self.idle_animations.setChecked(bool(self.repo.get("idle_animations_enabled", True)))
        form.addRow(self.idle_animations)

        return w

    def _build_privacy_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        text = QLabel(
            "FitBuddy processes activity information locally on this computer.\n\n"
            "It does NOT record keystrokes, capture screenshots, access your "
            "camera or microphone, or upload anything anywhere.\n\n"
            "Only the following is stored, entirely on this device:\n"
            "  \u2022 Active/idle timestamps (not what you typed or clicked)\n"
            "  \u2022 Fitness activity logs you complete or skip\n"
            "  \u2022 Water intake logs\n"
            "  \u2022 Your app settings\n"
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        layout.addStretch(1)
        return w

    def _save(self) -> None:
        self.repo.set_many(
            {
                "start_with_windows": self.start_with_windows.isChecked(),
                "theme": self.theme_combo.currentText(),
                "break_interval_minutes": self.break_interval.value(),
                "break_duration_minutes": self.break_duration.value(),
                "water_interval_minutes": self.water_interval.value(),
                "water_goal_ml": self.water_goal.value(),
                "idle_threshold_minutes": self.idle_threshold.value(),
                "notifications_enabled": self.notifications_enabled.isChecked(),
                "notification_sound": self.notification_sound.isChecked(),
                "quiet_hours_start": self.quiet_start.time().toString("HH:mm"),
                "quiet_hours_end": self.quiet_end.time().toString("HH:mm"),
                "pause_on_fullscreen": self.pause_fullscreen.isChecked(),
                "creature_enabled": self.creature_enabled.isChecked(),
                "movement_frequency": self.movement_frequency.currentText(),
                "movement_speed": self.movement_speed.currentText(),
                "creature_size_px": self.creature_size.value(),
                "idle_animations_enabled": self.idle_animations.isChecked(),
            }
        )

        from app.windows.startup import disable_startup, enable_startup
        import sys

        if sys.platform == "win32":
            if self.start_with_windows.isChecked():
                enable_startup(sys.executable)
            else:
                disable_startup()

        if self.on_saved:
            self.on_saved()
        self.accept()
