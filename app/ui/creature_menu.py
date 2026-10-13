"""Small popup menu shown when the user clicks Bobo (Section 9)."""

from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu


def show_creature_menu(
    on_drink_water: Callable[[], None],
    on_exercise: Callable[[], None],
    on_progress: Callable[[], None],
    on_settings: Callable[[], None],
    on_pause: Callable[[], None],
) -> None:
    menu = QMenu()
    menu.addAction("\U0001F43E Bobo").setEnabled(False)
    menu.addSeparator()
    menu.addAction("\U0001F4A7 Drink Water", on_drink_water)
    menu.addAction("\U0001F4AA Exercise", on_exercise)
    menu.addAction("\U0001F4CA Today's Progress", on_progress)
    menu.addAction("\u2699 Settings", on_settings)
    menu.addAction("\U0001F634 Pause Reminders", on_pause)
    menu.exec(QCursor.pos())
