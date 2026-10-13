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


@pytest.fixture()
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_database_creates_schema_and_version(db):
    with db.session() as s:
        from app.database.models import SchemaVersion

        row = s.get(SchemaVersion, 1)
        assert row is not None
        assert row.version == 1


def test_settings_roundtrip(db):
    repo = SettingsRepository(db)
    repo.set("break_interval_minutes", 45)
    assert repo.get("break_interval_minutes") == 45
    assert repo.get("nonexistent_key", "fallback") == "fallback"


def test_settings_seed_defaults_does_not_overwrite(db):
    repo = SettingsRepository(db)
    repo.set("water_goal_ml", 3000)
    repo.seed_defaults({"water_goal_ml": 2500, "theme": "light"})
    assert repo.get("water_goal_ml") == 3000  # untouched
    assert repo.get("theme") == "light"  # newly seeded


def test_session_lifecycle(db):
    repo = SessionRepository(db)
    start = dt.datetime(2026, 8, 23, 9, 0, 0)
    sid = repo.start_session(start)
    assert repo.get_open_session() is not None

    end = start + dt.timedelta(minutes=50)
    repo.end_session(sid, end, active_seconds=3000, idle_seconds=0, end_reason="idle_timeout")
    assert repo.get_open_session() is None

    sessions = repo.sessions_between(start - dt.timedelta(hours=1), start + dt.timedelta(hours=1))
    assert len(sessions) == 1
    assert sessions[0].active_seconds == 3000


def test_activity_log_and_query(db):
    repo = ActivityRepository(db)
    now = dt.datetime(2026, 8, 23, 10, 0, 0)
    repo.log_activity("pushups", target=10, completed=10, unit="reps", timestamp=now)
    repo.log_activity("squats", target=15, completed=15, unit="reps", timestamp=now + dt.timedelta(minutes=5))

    day_start = now.replace(hour=0, minute=0, second=0)
    day_end = day_start + dt.timedelta(days=1)
    logs = repo.activities_between(day_start, day_end)
    assert len(logs) == 2
    assert {l.activity_type for l in logs} == {"pushups", "squats"}


def test_water_totals(db):
    repo = WaterRepository(db)
    now = dt.datetime.utcnow()
    repo.log_water(250, timestamp=now)
    repo.log_water(500, timestamp=now)
    total = repo.total_between(now - dt.timedelta(hours=1), now + dt.timedelta(hours=1))
    assert total == 750


def test_break_lifecycle(db):
    repo = BreakRepository(db)
    bid = repo.start_break(planned_duration_minutes=5)
    repo.finish_break(bid, actual_duration_seconds=300, completed=True)
    last = repo.last_break_time()
    assert last is not None


def test_daily_summary_upsert(db):
    repo = DailySummaryRepository(db)
    repo.upsert("2026-08-23", active_seconds=100, water_ml=500)
    row = repo.get("2026-08-23")
    assert row.active_seconds == 100
    repo.upsert("2026-08-23", active_seconds=200)
    row = repo.get("2026-08-23")
    assert row.active_seconds == 200
    assert row.water_ml == 500  # unspecified fields preserved
