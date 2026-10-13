"""
Attractive notification popups (Section 9/12/13/15). Implemented as a
small frameless, rounded QWidget positioned near the bottom-right of the
screen (a native Windows toast is an alternative, but a custom widget gives
us full control over the button actions Section 12/13/15 require, like
"Start Break" / "Remind Later" / "Skip" or the water amount buttons).
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class NotificationPopup(QWidget):
    def __init__(
        self,
        title: str,
        body: str,
        buttons: list[tuple[str, Callable[[], None]]],
        auto_dismiss_ms: Optional[int] = None,
    ) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(
            """
            QWidget#card {
                background-color: rgba(255, 255, 255, 245);
                border-radius: 14px;
                border: 1px solid #DDEDE8;
            }
            QLabel#title { color: #3E8E7E; font-weight: 600; font-size: 12px; letter-spacing: 1px; }
            QLabel#body { color: #333333; font-size: 13px; }
            QPushButton {
                background-color: #8BD6C8;
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                color: white;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #6FBFAF; }
            QPushButton#secondary { background-color: #EEEEEE; color: #555555; }
            QPushButton#secondary:hover { background-color: #DDDDDD; }
            """
        )

        card = QWidget(self)
        card.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        if title:
            title_label = QLabel(title)
            title_label.setObjectName("title")
            layout.addWidget(title_label)

        body_label = QLabel(body)
        body_label.setObjectName("body")
        body_label.setWordWrap(True)
        layout.addWidget(body_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        for i, (label, callback) in enumerate(buttons):
            btn = QPushButton(label)
            if i > 0:
                btn.setObjectName("secondary")

            def make_handler(cb: Callable[[], None]) -> Callable[[], None]:
                def handler() -> None:
                    cb()
                    self.close()

                return handler

            btn.clicked.connect(make_handler(callback))
            button_row.addWidget(btn)
        layout.addLayout(button_row)

        self.setFixedWidth(320)
        self.adjustSize()
        self._position_bottom_right()

        if auto_dismiss_ms:
            QTimer.singleShot(auto_dismiss_ms, self.close)

    def _position_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        margin = 24
        x = geo.right() - self.width() - margin
        y = geo.bottom() - self.height() - margin
        self.move(x, y)

    def show_popup(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
