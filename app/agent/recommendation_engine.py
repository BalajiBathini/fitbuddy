"""
Recommendation engine (Section 27-28). Defines the abstract interface plus
the MVP rule-based implementation. A future AIRecommendationEngine can
implement the same interface using only the summarized `RecommendationContext`
below - never raw computer-activity data - and must still route its output
through NotificationManager, so it can never bypass quiet hours, pause mode,
or cooldowns (Section 27: "AI should never independently override safety
settings").
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class RecommendationContext:
    active_minutes_today: float
    breaks_today: int
    water_ml_today: int
    water_goal_ml: int
    exercise_reps_today: int
    minutes_since_last_break: Optional[float]
    minutes_since_last_water: Optional[float]
    is_evening: bool
    consecutive_skips_by_kind: dict[str, int]


@dataclass
class Recommendation:
    kind: str  # "break" | "water" | "exercise" | "none"
    reason: str
    exercise_key: Optional[str] = None


class RecommendationEngine(ABC):
    @abstractmethod
    def get_recommendation(self, context: RecommendationContext) -> Recommendation:
        ...


class RuleBasedRecommendationEngine(RecommendationEngine):
    """
    MVP implementation. Pure, deterministic rules per Section 28:

        IF active_time >= break_interval: recommend_break
        IF time_since_water >= water_interval: recommend_water
        IF no_exercise_today AND evening: recommend_light_exercise
        IF user_skipped_three_reminders: reduce notification frequency
           (handled by NotificationManager's adaptive backoff, not here)
        IF user completed many exercises: avoid excessive additional reminders
    """

    def __init__(
        self,
        break_interval_minutes: int = 50,
        water_interval_minutes: int = 60,
        exercise_reps_ceiling: int = 60,
    ) -> None:
        self.break_interval_minutes = break_interval_minutes
        self.water_interval_minutes = water_interval_minutes
        self.exercise_reps_ceiling = exercise_reps_ceiling

    def get_recommendation(self, context: RecommendationContext) -> Recommendation:
        if (
            context.minutes_since_last_break is not None
            and context.minutes_since_last_break >= self.break_interval_minutes
        ):
            return Recommendation(kind="break", reason="active_time_exceeded_interval")

        if (
            context.minutes_since_last_water is None
            or context.minutes_since_last_water >= self.water_interval_minutes
        ):
            return Recommendation(kind="water", reason="water_interval_elapsed")

        if (
            context.is_evening
            and context.exercise_reps_today == 0
            and context.exercise_reps_today < self.exercise_reps_ceiling
        ):
            return Recommendation(kind="exercise", reason="no_exercise_today_evening", exercise_key="stretching")

        if context.exercise_reps_today >= self.exercise_reps_ceiling:
            return Recommendation(kind="none", reason="exercise_goal_already_generous")

        return Recommendation(kind="none", reason="nothing_due")
