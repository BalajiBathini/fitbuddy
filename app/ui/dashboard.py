"""
Local desktop dashboard (Section 19). A native QWidget window (not a
browser UI, per Section 4) with three sections: today's overview cards,
an activity timeline, and a simple weekly bar chart drawn with QPainter
(no charting library dependency needed for the MVP).
"""

from __future__ import annotations

import datetime as dt

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.database.models import WaterLog
from app.database.repositories import ActivityRepository, BreakRepository, WaterRepository
from app.fitness.statistics_service import StatisticsService


def _seconds_to_hm(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m = rem // 60
    return f"{h}h {m}m" if h else f"{m}m"


class StatCard(QFrame):
    def __init__(self, emoji: str, label: str, value: str) -> None:
        super().__init__()
        self.setObjectName("statCard")
        self.setStyleSheet(
            """
            QFrame#statCard { background-color: #F5FBFA; border-radius: 12px; border: 1px solid #E3F1EE; }
            QLabel#value { font-size: 22px; font-weight: 700; color: #3E8E7E; }
            QLabel#label { font-size: 12px; color: #666666; }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        emoji_label = QLabel(f"{emoji} {label}")
        emoji_label.setObjectName("label")
        value_label = QLabel(value)
        value_label.setObjectName("value")
        layout.addWidget(emoji_label)
        layout.addWidget(value_label)


class WeeklyChart(QWidget):
    """Simple bar chart for one metric across the last 7 days."""

    def __init__(self, values: list[float], labels: list[str], max_value: float, color: str) -> None:
        super().__init__()
        self.values = values
        self.labels = labels
        self.max_value = max(max_value, 1.0)
        self.color = QColor(color)
        self.setMinimumHeight(120)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        n = max(1, len(self.values))
        bar_area_h = h - 24
        bar_w = w / n * 0.5
        gap = w / n

        for i, (val, label) in enumerate(zip(self.values, self.labels)):
            bar_h = (val / self.max_value) * bar_area_h
            x = i * gap + (gap - bar_w) / 2
            y = bar_area_h - bar_h
            painter.setBrush(QBrush(self.color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(int(x), int(y), int(bar_w), int(bar_h), 4, 4)
            painter.setPen(QPen(QColor("#888888")))
            painter.drawText(int(x - 10), int(bar_area_h + 16), int(bar_w + 20), 16, Qt.AlignCenter, label)


class Dashboard(QWidget):
    def __init__(
        self,
        statistics_service: StatisticsService,
        activity_repo: ActivityRepository,
        water_repo: WaterRepository,
        break_repo: BreakRepository,
    ) -> None:
        super().__init__(None)
        self.setWindowTitle("FitBuddy Dashboard")
        self.resize(640, 700)
        self.setMinimumWidth(600)
        self.stats = statistics_service
        self.activity_repo = activity_repo
        self.water_repo = water_repo
        self.break_repo = break_repo

        self.setStyleSheet(
            """
            QWidget { background-color: #FFFFFF; font-family: 'Segoe UI', sans-serif; }
            QLabel#sectionTitle { font-size: 14px; font-weight: 700; color: #333333; margin-top: 8px; }
            QLabel#timelineItem { font-size: 12px; color: #444444; padding: 3px 0; }
            """
        )

        outer_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        self.layout_ = QVBoxLayout(content)
        self.layout_.setContentsMargins(20, 20, 20, 20)
        self.layout_.setSpacing(10)

        self.refresh()

    def refresh(self) -> None:
        while self.layout_.count():
            item = self.layout_.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        today = self.stats.compute_daily_stats()

        header = QLabel("\U0001F43E Today's Overview")
        header.setObjectName("sectionTitle")
        self.layout_.addWidget(header)

        cards_row = QHBoxLayout()
        cards_row.addWidget(StatCard("\U0001F4BB", "Screen Time", _seconds_to_hm(today.active_seconds)))
        cards_row.addWidget(StatCard("\U0001F9D8", "Breaks", str(today.breaks_count)))
        cards_row.addWidget(
            StatCard("\U0001F4A7", "Water", f"{today.water_ml / 1000:.1f} / {today.water_goal_ml / 1000:.1f} L")
        )
        cards_row.addWidget(StatCard("\U0001F4AA", "Exercise", f"{today.exercise_reps} reps"))
        self.layout_.addLayout(cards_row)

        score_label = QLabel(f"\U0001F525 Daily score: {today.daily_score:.0f}%")
        score_label.setStyleSheet("font-size: 13px; color: #555555; margin-top: 4px;")
        self.layout_.addWidget(score_label)

        timeline_title = QLabel("\U0001F4CB Activity Timeline")
        timeline_title.setObjectName("sectionTitle")
        self.layout_.addWidget(timeline_title)
        for line in self._build_timeline():
            item = QLabel(line)
            item.setObjectName("timelineItem")
            self.layout_.addWidget(item)

        weekly_title = QLabel("\U0001F4C8 Weekly Progress")
        weekly_title.setObjectName("sectionTitle")
        self.layout_.addWidget(weekly_title)

        weekly = self.stats.weekly_stats()
        labels = [dt.date.fromisoformat(d.date).strftime("%a") for d in weekly]

        self.layout_.addWidget(QLabel("Active screen time (hours)"))
        self.layout_.addWidget(
            WeeklyChart([d.active_seconds / 3600 for d in weekly], labels, max_value=8, color="#8BD6C8")
        )
        self.layout_.addWidget(QLabel("Water (mL)"))
        self.layout_.addWidget(
            WeeklyChart([d.water_ml for d in weekly], labels, max_value=3000, color="#79C6E8")
        )
        self.layout_.addWidget(QLabel("Exercise (reps)"))
        self.layout_.addWidget(
            WeeklyChart([d.exercise_reps for d in weekly], labels, max_value=60, color="#F4B183")
        )
        self.layout_.addStretch(1)

    def _build_timeline(self, limit: int = 12) -> list[str]:
        now = dt.datetime.utcnow()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        events: list[tuple[dt.datetime, str]] = []
        for a in self.activity_repo.activities_between(start_of_day, now):
            if not a.skipped:
                events.append((a.timestamp, f"\U0001F4AA {a.completed:g} {a.activity_type}"))

        with self.water_repo.db.session() as s:
            rows = s.query(WaterLog).filter(WaterLog.timestamp >= start_of_day).all()
            for r in rows:
                events.append((r.timestamp, f"\U0001F4A7 {r.amount_ml} ml"))

        for b in self.break_repo.breaks_between(start_of_day, now):
            if b.completed:
                events.append((b.started_at, "\U0001F9D8 Break"))

        events.sort(key=lambda e: e[0])
        lines = [f"{ts.strftime('%H:%M')}  {label}" for ts, label in events[-limit:]]
        return lines or ["No activity logged yet today."]
