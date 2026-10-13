"""
Daily/weekly statistics rollup (Sections 18-19). Reads raw logs and produces
the summarized numbers the dashboard and evening-summary notification need.
Also writes precomputed rows into daily_summaries so the dashboard loads
fast without re-scanning raw logs every time.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from app.database.repositories import (
    ActivityRepository,
    BreakRepository,
    DailySummaryRepository,
    SessionRepository,
    WaterRepository,
)
from app.fitness.activity_service import EXERCISE_CATALOG

EXERCISE_ONLY_KEYS = set(EXERCISE_CATALOG.keys()) - {"walking", "eye_break", "deep_breathing"}


@dataclass
class DailyStats:
    date: str
    active_seconds: int
    idle_seconds: int
    breaks_count: int
    break_seconds: int
    water_ml: int
    water_goal_ml: int
    exercise_reps: int
    walking_minutes: int
    daily_score: float


class StatisticsService:
    def __init__(
        self,
        session_repo: SessionRepository,
        activity_repo: ActivityRepository,
        water_repo: WaterRepository,
        break_repo: BreakRepository,
        summary_repo: DailySummaryRepository,
        water_goal_ml_provider,
    ) -> None:
        self.sessions = session_repo
        self.activities = activity_repo
        self.water = water_repo
        self.breaks = break_repo
        self.summaries = summary_repo
        self._water_goal_ml_provider = water_goal_ml_provider

    def _day_bounds(self, day: dt.date) -> tuple[dt.datetime, dt.datetime]:
        start = dt.datetime.combine(day, dt.time.min)
        end = start + dt.timedelta(days=1)
        return start, end

    def compute_daily_stats(self, day: dt.date | None = None) -> DailyStats:
        day = day or dt.date.today()
        start, end = self._day_bounds(day)

        sessions = self.sessions.sessions_between(start, end)
        active_seconds = sum(s.active_seconds for s in sessions)
        idle_seconds = sum(s.idle_seconds for s in sessions)

        breaks = self.breaks.breaks_between(start, end)
        breaks_count = sum(1 for b in breaks if b.completed)
        break_seconds = sum(b.actual_duration_seconds for b in breaks)

        water_ml = self.water.total_between(start, end)
        water_goal = self._water_goal_ml_provider()

        activities = self.activities.activities_between(start, end)
        exercise_reps = sum(
            a.completed for a in activities
            if a.activity_type in EXERCISE_ONLY_KEYS and not a.skipped and a.unit == "reps"
        )
        walking_minutes = sum(
            a.completed for a in activities
            if a.activity_type == "walking" and not a.skipped
        )

        score = self._daily_score(
            active_seconds=active_seconds,
            breaks_count=breaks_count,
            water_ml=water_ml,
            water_goal=water_goal,
            exercise_reps=exercise_reps,
        )

        stats = DailyStats(
            date=day.isoformat(),
            active_seconds=active_seconds,
            idle_seconds=idle_seconds,
            breaks_count=breaks_count,
            break_seconds=break_seconds,
            water_ml=water_ml,
            water_goal_ml=water_goal,
            exercise_reps=int(exercise_reps),
            walking_minutes=int(walking_minutes),
            daily_score=score,
        )

        self.summaries.upsert(
            stats.date,
            active_seconds=stats.active_seconds,
            idle_seconds=stats.idle_seconds,
            breaks_count=stats.breaks_count,
            break_seconds=stats.break_seconds,
            water_ml=stats.water_ml,
            exercise_reps=stats.exercise_reps,
            walking_minutes=stats.walking_minutes,
            daily_score=stats.daily_score,
        )
        return stats

    @staticmethod
    def _daily_score(
        *, active_seconds: int, breaks_count: int, water_ml: int, water_goal: int, exercise_reps: float
    ) -> float:
        """
        A gentle, non-punitive 0-100 composite score (Section 41: "do not
        shame the user"). Each component contributes up to 25 points and
        caps out rather than penalizing beyond the goal.
        """
        break_score = min(25.0, breaks_count * 5.0)
        water_score = min(25.0, (water_ml / water_goal) * 25.0) if water_goal else 0.0
        exercise_score = min(25.0, (exercise_reps / 30.0) * 25.0)
        # Being active at all (vs. the computer sitting idle all day) is worth credit too.
        activity_score = min(25.0, (active_seconds / (4 * 3600)) * 25.0)
        return round(break_score + water_score + exercise_score + activity_score, 1)

    def weekly_stats(self, end_day: dt.date | None = None) -> list[DailyStats]:
        end_day = end_day or dt.date.today()
        start_day = end_day - dt.timedelta(days=6)
        results = []
        d = start_day
        while d <= end_day:
            results.append(self.compute_daily_stats(d))
            d += dt.timedelta(days=1)
        return results
