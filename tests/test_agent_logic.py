import datetime as dt

import pytest

from app.agent.break_manager import BreakManager, BreakManagerConfig, BreakPhase
from app.agent.recommendation_engine import RecommendationContext, RuleBasedRecommendationEngine
from app.database.database import Database
from app.database.repositories import BreakRepository


@pytest.fixture()
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_break_due_after_interval():
    mgr = BreakManager(BreakRepository, BreakManagerConfig(break_interval_minutes=50))
    assert mgr.is_break_due(49 * 60) is False
    assert mgr.is_break_due(50 * 60) is True


def test_break_lifecycle_start_countdown_finish(db):
    repo = BreakRepository(db)
    mgr = BreakManager(repo, BreakManagerConfig(break_interval_minutes=50, break_duration_minutes=5))
    now = dt.datetime(2026, 8, 23, 12, 0, 0)
    mgr.start_break(now)
    assert mgr.phase == BreakPhase.IN_PROGRESS
    # is_break_due should be False while a break is already in progress,
    # even if active time nominally exceeds the interval.
    assert mgr.is_break_due(9999) is False

    remaining = mgr.remaining_seconds(now + dt.timedelta(minutes=2))
    assert remaining == pytest.approx(180, abs=1)

    mgr.finish_break(now + dt.timedelta(minutes=5), completed=True)
    assert mgr.phase == BreakPhase.NONE


def test_break_skip(db):
    repo = BreakRepository(db)
    mgr = BreakManager(repo, BreakManagerConfig())
    mgr.start_break()
    mgr.skip_break()
    assert mgr.phase == BreakPhase.NONE


def test_recommendation_break_takes_priority():
    engine = RuleBasedRecommendationEngine(break_interval_minutes=50, water_interval_minutes=60)
    context = RecommendationContext(
        active_minutes_today=60,
        breaks_today=0,
        water_ml_today=0,
        water_goal_ml=2500,
        exercise_reps_today=0,
        minutes_since_last_break=55,
        minutes_since_last_water=5,  # water not due yet
        is_evening=False,
        consecutive_skips_by_kind={},
    )
    rec = engine.get_recommendation(context)
    assert rec.kind == "break"


def test_recommendation_water_when_no_break_due():
    engine = RuleBasedRecommendationEngine(break_interval_minutes=50, water_interval_minutes=60)
    context = RecommendationContext(
        active_minutes_today=20,
        breaks_today=1,
        water_ml_today=500,
        water_goal_ml=2500,
        exercise_reps_today=0,
        minutes_since_last_break=10,
        minutes_since_last_water=65,
        is_evening=False,
        consecutive_skips_by_kind={},
    )
    rec = engine.get_recommendation(context)
    assert rec.kind == "water"


def test_recommendation_exercise_in_evening_with_no_exercise():
    engine = RuleBasedRecommendationEngine(break_interval_minutes=50, water_interval_minutes=60)
    context = RecommendationContext(
        active_minutes_today=20,
        breaks_today=1,
        water_ml_today=2500,
        water_goal_ml=2500,
        exercise_reps_today=0,
        minutes_since_last_break=10,
        minutes_since_last_water=5,
        is_evening=True,
        consecutive_skips_by_kind={},
    )
    rec = engine.get_recommendation(context)
    assert rec.kind == "exercise"
    assert rec.exercise_key is not None


def test_recommendation_none_when_everything_satisfied():
    engine = RuleBasedRecommendationEngine(break_interval_minutes=50, water_interval_minutes=60)
    context = RecommendationContext(
        active_minutes_today=20,
        breaks_today=1,
        water_ml_today=2500,
        water_goal_ml=2500,
        exercise_reps_today=5,
        minutes_since_last_break=10,
        minutes_since_last_water=5,
        is_evening=False,
        consecutive_skips_by_kind={},
    )
    rec = engine.get_recommendation(context)
    assert rec.kind == "none"


def test_recommendation_avoids_more_exercise_when_already_generous():
    engine = RuleBasedRecommendationEngine(
        break_interval_minutes=50, water_interval_minutes=60, exercise_reps_ceiling=60
    )
    context = RecommendationContext(
        active_minutes_today=20,
        breaks_today=1,
        water_ml_today=2500,
        water_goal_ml=2500,
        exercise_reps_today=80,
        minutes_since_last_break=10,
        minutes_since_last_water=5,
        is_evening=True,
        consecutive_skips_by_kind={},
    )
    rec = engine.get_recommendation(context)
    assert rec.kind == "none"
