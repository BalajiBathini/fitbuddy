"""First-launch onboarding wizard (Section 39)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QLabel,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.database.repositories import SettingsRepository


class FirstLaunchWizard(QDialog):
    def __init__(self, settings_repo: SettingsRepository) -> None:
        super().__init__(None)
        self.setWindowTitle("Welcome to FitBuddy")
        self.setFixedSize(380, 340)
        self.repo = settings_repo
        self.chosen_break_interval = 50
        self.chosen_water_goal = 2500

        self.stack = QStackedWidget()
        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

        self.stack.addWidget(self._build_intro_page())
        self.stack.addWidget(self._build_break_page())
        self.stack.addWidget(self._build_water_page())
        self.stack.addWidget(self._build_ready_page())

    def _page_shell(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)
        label = QLabel(title)
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 14px;")
        layout.addWidget(label)
        return page, layout

    def _build_intro_page(self) -> QWidget:
        page, layout = self._page_shell(
            "\U0001F43E Hi! I'm Bobo.\n\n"
            "I'm your little desktop fitness buddy. I'll help you:\n"
            "\U0001F4A7 Drink water\n\U0001F9D8 Take breaks\n\U0001F4AA Move more\n"
            "\U0001F4CA Track your progress\n\nLet's set up your routine."
        )
        next_btn = QPushButton("Next")
        next_btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        layout.addWidget(next_btn)
        return page

    def _build_break_page(self) -> QWidget:
        page, layout = self._page_shell("How often should I remind you to take a break?")
        group = QButtonGroup(page)
        for minutes in (45, 50, 60):
            btn = QRadioButton(f"{minutes} min")
            if minutes == 50:
                btn.setChecked(True)
            btn.toggled.connect(lambda checked, m=minutes: checked and setattr(self, "chosen_break_interval", m))
            group.addButton(btn)
            layout.addWidget(btn)
        next_btn = QPushButton("Next")
        next_btn.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        layout.addWidget(next_btn)
        return page

    def _build_water_page(self) -> QWidget:
        page, layout = self._page_shell("What's your daily water goal?")
        group = QButtonGroup(page)
        for ml in (2000, 2500, 3000):
            btn = QRadioButton(f"{ml} ml")
            if ml == 2500:
                btn.setChecked(True)
            btn.toggled.connect(lambda checked, m=ml: checked and setattr(self, "chosen_water_goal", m))
            group.addButton(btn)
            layout.addWidget(btn)
        next_btn = QPushButton("Next")
        next_btn.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        layout.addWidget(next_btn)
        return page

    def _build_ready_page(self) -> QWidget:
        page, layout = self._page_shell("Ready! \U0001F43E\n\nI'll quietly run in the background.")
        start_btn = QPushButton("Start FitBuddy")
        start_btn.clicked.connect(self._finish)
        layout.addWidget(start_btn)
        return page

    def _finish(self) -> None:
        self.repo.set_many(
            {
                "break_interval_minutes": self.chosen_break_interval,
                "water_goal_ml": self.chosen_water_goal,
                "first_launch_complete": True,
            }
        )
        self.accept()
