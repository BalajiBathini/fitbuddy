"""
Exercise catalog (Section 14) and the service that logs completed/skipped
activities (Section 16), including breaks logged through the same table
family for the "workout" style activities.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from app.database.repositories import ActivityRepository


@dataclass(frozen=True)
class ExerciseDefinition:
    name: str
    description: str
    default_target: float
    unit: str
    difficulty: str  # "easy" | "medium" | "hard"
    estimated_duration_seconds: int


EXERCISE_CATALOG: dict[str, ExerciseDefinition] = {
    "pushups": ExerciseDefinition(
        "Push-ups", "Classic upper-body strength move.", 10, "reps", "medium", 40
    ),
    "squats": ExerciseDefinition(
        "Squats", "Great for legs and gets the blood moving.", 15, "reps", "easy", 40
    ),
    "situps": ExerciseDefinition(
        "Sit-ups", "Core strengthening exercise.", 12, "reps", "medium", 40
    ),
    "lunges": ExerciseDefinition(
        "Lunges", "Alternating lunges for legs and balance.", 10, "reps", "medium", 40
    ),
    "plank": ExerciseDefinition(
        "Plank", "Hold a straight-body plank position.", 30, "seconds", "medium", 30
    ),
    "stretching": ExerciseDefinition(
        "Stretching", "Loosen up your shoulders, neck, and back.", 60, "seconds", "easy", 60
    ),
    "walking": ExerciseDefinition(
        "Walking", "Step away and walk around for a bit.", 3, "minutes", "easy", 180
    ),
    "eye_break": ExerciseDefinition(
        "Eye break", "Look at something 20 feet away for 20 seconds.", 20, "seconds", "easy", 20
    ),
    "deep_breathing": ExerciseDefinition(
        "Deep breathing", "A few slow, deep breaths to reset.", 5, "breaths", "easy", 30
    ),
}


class ActivityService:
    """Facade used by the agent/UI to record fitness activity."""

    def __init__(self, activity_repo: ActivityRepository) -> None:
        self.repo = activity_repo

    def get_exercise(self, key: str) -> ExerciseDefinition:
        if key not in EXERCISE_CATALOG:
            raise KeyError(f"Unknown exercise: {key}")
        return EXERCISE_CATALOG[key]

    def list_exercises(self) -> dict[str, ExerciseDefinition]:
        return dict(EXERCISE_CATALOG)

    def complete_activity(
        self,
        activity_type: str,
        completed_amount: float,
        source: str = "manual",
        duration_seconds: int | None = None,
    ) -> int:
        exercise = EXERCISE_CATALOG.get(activity_type)
        target = exercise.default_target if exercise else completed_amount
        unit = exercise.unit if exercise else "reps"
        duration = duration_seconds if duration_seconds is not None else (
            exercise.estimated_duration_seconds if exercise else 0
        )
        return self.repo.log_activity(
            activity_type=activity_type,
            target=target,
            completed=completed_amount,
            unit=unit,
            duration_seconds=duration,
            source=source,
            skipped=False,
        )

    def skip_activity(self, activity_type: str, source: str = "manual") -> int:
        exercise = EXERCISE_CATALOG.get(activity_type)
        target = exercise.default_target if exercise else 0
        unit = exercise.unit if exercise else "reps"
        return self.repo.log_activity(
            activity_type=activity_type,
            target=target,
            completed=0,
            unit=unit,
            duration_seconds=0,
            source=source,
            skipped=True,
        )

    def had_any_exercise_today(self, now: dt.datetime | None = None) -> bool:
        now = now or dt.datetime.utcnow()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        exercise_keys = set(EXERCISE_CATALOG.keys()) - {"eye_break", "deep_breathing"}
        activities = self.repo.activities_between(start_of_day, now)
        return any(a.activity_type in exercise_keys and not a.skipped for a in activities)
