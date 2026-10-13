import datetime as dt

import pytest

from app.database.database import Database
from app.database.repositories import (
    ActivityRepository,
    BreakRepository,
    DailySummaryRepository,
    SessionRepository,
    SettingsRepository,
    WaterRepository,
)
from app.fitness.activity_service import EXERCISE_CATALOG, ActivityService
from app.fitness.statistics_service import StatisticsService
from app.fitness.water_service import WaterService


@pytest.fixture()
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_exercise_catalog_has_required_entries():
    required = {
        "pushups", "squats", "situps", "lunges", "plank",
        "stretching", "walking", "eye_break", "deep_breathing",
    }
    assert required.issubset(EXERCISE_CATALOG.keys())
    for key, ex in EXERCISE_CATALOG.items():
        assert ex.default_target > 0
        assert ex.unit
        assert ex.difficulty in ("easy", "medium", "hard")


def test_complete_activity_logs_with_catalog_defaults(db):
    service = ActivityService(ActivityRepository(db))
    activity_id = service.complete_activity("pushups", 10)
    assert activity_id is not None

    now = dt.datetime.utcnow()
    logs = service.repo.activities_between(
        now.replace(hour=0, minute=0, second=0), now + dt.timedelta(minutes=1)
    )
    assert len(logs) == 1
    assert logs[0].unit == "reps"
    assert logs[0].completed == 10


def test_skip_activity_marks_skipped(db):
    service = ActivityService(ActivityRepository(db))
    service.skip_activity("squats")
    now = dt.datetime.utcnow()
    logs = service.repo.activities_between(
        now.replace(hour=0, minute=0, second=0), now + dt.timedelta(minutes=1)
    )
    assert logs[0].skipped is True


def test_had_any_exercise_today(db):
    service = ActivityService(ActivityRepository(db))
    assert service.had_any_exercise_today() is False
    service.complete_activity("squats", 15)
    assert service.had_any_exercise_today() is True


def test_water_totals_and_goal(db):
    settings = SettingsRepository(db)
    settings.set("water_goal_ml", 2000)
    service = WaterService(WaterRepository(db), settings)
    service.log_water(250)
    service.log_water(500)
    assert service.today_total_ml() == 750
    assert service.progress_fraction() == pytest.approx(0.375)


def test_water_rejects_nonpositive_amount(db):
    settings = SettingsRepository(db)
    service = WaterService(WaterRepository(db), settings)
    with pytest.raises(ValueError):
        service.log_water(0)


def test_minutes_since_last_drink(db):
    settings = SettingsRepository(db)
    repo = WaterRepository(db)
    service = WaterService(repo, settings)
    assert service.minutes_since_last_drink() is None
    now = dt.datetime.utcnow()
    repo.log_water(250, timestamp=now - dt.timedelta(minutes=30))
    minutes = service.minutes_since_last_drink(now)
    assert minutes == pytest.approx(30, abs=0.5)


def test_daily_score_is_never_punitive_below_zero(db):
    settings = SettingsRepository(db)
    settings.set("water_goal_ml", 2500)
    stats_service = StatisticsService(
        SessionRepository(db),
        ActivityRepository(db),
        WaterRepository(db),
        BreakRepository(db),
        DailySummaryRepository(db),
        water_goal_ml_provider=lambda: 2500,
    )
    stats = stats_service.compute_daily_stats(dt.date(2026, 8, 23))
    assert 0 <= stats.daily_score <= 100


def test_daily_score_improves_with_activity(db):
    activity_repo = ActivityRepository(db)
    water_repo = WaterRepository(db)
    break_repo = BreakRepository(db)
    stats_service = StatisticsService(
        SessionRepository(db),
        activity_repo,
        water_repo,
        break_repo,
        DailySummaryRepository(db),
        water_goal_ml_provider=lambda: 2500,
    )
    day = dt.date(2026, 8, 23)
    day_dt = dt.datetime(2026, 8, 23, 12, 0)

    baseline = stats_service.compute_daily_stats(day)

    water_repo.log_water(2500, timestamp=day_dt)
    activity_repo.log_activity("pushups", 10, 10, "reps", timestamp=day_dt)

    improved = stats_service.compute_daily_stats(day)
    assert improved.daily_score > baseline.daily_score
