"""
System tray integration (Section 20). The tray icon is drawn procedurally
(a small paw-print glyph) to match the no-binary-assets approach used for
Bobo, and stays functional even if the user closes the dashboard or hides
the creature (Section 20: "app must continue working when the dashboard is
closed").
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def _build_tray_icon() -> QIcon:
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(QColor("#8BD6C8")))
    painter.drawEllipse(14, 24, 36, 30)
    painter.drawEllipse(10, 10, 14, 14)
    painter.drawEllipse(26, 4, 14, 14)
    painter.drawEllipse(42, 10, 14, 14)
    painter.end()
    return QIcon(pixmap)


class SystemTray(QSystemTrayIcon):
    def __init__(
        self,
        on_open_dashboard: Callable[[], None],
        on_todays_progress: Callable[[], None],
        on_take_break_now: Callable[[], None],
        on_drink_water: Callable[[], None],
        on_pause_30: Callable[[], None],
        on_pause_60: Callable[[], None],
        on_settings: Callable[[], None],
        on_about: Callable[[], None],
        on_exit: Callable[[], None],
        parent: Optional[object] = None,
    ) -> None:
        super().__init__(_build_tray_icon(), parent)
        self.setToolTip("FitBuddy - running")

        menu = QMenu()
        title_action = menu.addAction("\U0001F43E FitBuddy")
        title_action.setEnabled(False)
        status_action = menu.addAction("\u25CF Running")
        status_action.setEnabled(False)
        menu.addSeparator()

        menu.addAction("Open Dashboard", on_open_dashboard)
        menu.addAction("Today's Progress", on_todays_progress)
        menu.addSeparator()
        menu.addAction("Take a Break Now", on_take_break_now)
        menu.addAction("Drink Water", on_drink_water)
        menu.addSeparator()
        menu.addAction("Pause for 30 minutes", on_pause_30)
        menu.addAction("Pause for 1 hour", on_pause_60)
        menu.addSeparator()
        menu.addAction("Settings", on_settings)
        menu.addAction("About", on_about)
        menu.addSeparator()
        menu.addAction("Exit", on_exit)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)
        self._on_open_dashboard = on_open_dashboard

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._on_open_dashboard()

    def set_status_running(self, running: bool) -> None:
        self.setToolTip("FitBuddy - running" if running else "FitBuddy - paused")
