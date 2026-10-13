"""Break countdown overlay (Section 12: "BREAK TIME" countdown screen)."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget


class BreakCountdownWidget(QWidget):
    def __init__(self, duration_seconds: int, on_done: Callable[[bool], None]) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.on_done = on_done
        self.remaining = duration_seconds

        self.setStyleSheet(
            """
            QWidget#card { background-color: rgba(70, 130, 118, 235); border-radius: 18px; }
            QLabel#heading { color: white; font-size: 16px; font-weight: 700; letter-spacing: 2px; }
            QLabel#timer { color: white; font-size: 40px; font-weight: 700; }
            QLabel#tips { color: #EAF7F3; font-size: 12px; }
            QPushButton { background-color: white; color: #3E8E7E; border-radius: 8px; padding: 8px 16px; font-weight: 600; }
            QPushButton:hover { background-color: #EAF7F3; }
            """
        )

        card = QWidget(self)
        card.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        heading = QLabel("BREAK TIME \U0001F9D8")
        heading.setObjectName("heading")
        heading.setAlignment(Qt.AlignCenter)
        layout.addWidget(heading)

        self.timer_label = QLabel(self._format_time(self.remaining))
        self.timer_label.setObjectName("timer")
        self.timer_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.timer_label)

        tips = QLabel("Walk around. Drink water. Relax your eyes.\n\U0001F43E Bobo is taking a break with you!")
        tips.setObjectName("tips")
        tips.setAlignment(Qt.AlignCenter)
        layout.addWidget(tips)

        done_btn = QPushButton("Done")
        done_btn.clicked.connect(lambda: self._finish(True))
        layout.addWidget(done_btn)

        self.setFixedSize(280, 220)
        self._center_on_screen()

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(1000)

    @staticmethod
    def _format_time(seconds: int) -> str:
        m, s = divmod(max(0, seconds), 60)
        return f"{m}:{s:02d}"

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)

    def _tick(self) -> None:
        self.remaining -= 1
        self.timer_label.setText(self._format_time(self.remaining))
        if self.remaining <= 0:
            self._tick_timer.stop()
            self._finish(True)

    def _finish(self, completed: bool) -> None:
        self._tick_timer.stop()
        self.on_done(completed)
        self.close()
