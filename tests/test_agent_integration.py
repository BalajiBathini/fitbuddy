"""
Integration-level tests for FitBuddyAgent, exercising the wiring between
activity monitor, break manager, recommendation engine, and notification
manager without touching the scheduler (we call the tick methods directly
rather than starting APScheduler, keeping tests fast and deterministic).
"""

import datetime as dt

import pytest

from app.agent.agent import AgentCallbacks, FitBuddyAgent
from app.database.database import Database
from app.notifications.notification_manager import NotificationKind


@pytest.fixture()
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_agent_seeds_default_settings(db):
    agent = FitBuddyAgent(db)
    assert agent.settings_repo.get("break_interval_minutes") == 50
    assert agent.settings_repo.get("water_goal_ml") == 2500


def test_agent_water_logging_updates_totals(db):
    agent = FitBuddyAgent(db)
    agent.log_water(500)
    assert agent.water_service.today_total_ml() == 500


def test_agent_break_flow_resets_break_timer(db):
    agent = FitBuddyAgent(db)
    agent.activity_monitor._active_seconds_accum = 3000  # simulate 50 min active
    agent.start_break_now()
    agent.finish_break(completed=True)
    assert agent.activity_monitor.active_seconds_in_current_session() == 0


def test_agent_pause_blocks_reminder_evaluation(db):
    received = []
    callbacks = AgentCallbacks(on_water_due=lambda: received.append("water"))
    agent = FitBuddyAgent(db)
    agent.callbacks = callbacks
    agent.pause_for(30)

    agent._evaluate_water_and_exercise()
    assert received == []


def test_agent_exercise_completion_recorded(db):
    agent = FitBuddyAgent(db)
    agent.complete_exercise("squats", 15)
    assert agent.activity_service.had_any_exercise_today() is True


def test_agent_skip_water_triggers_backoff_after_repeats(db):
    agent = FitBuddyAgent(db)
    agent.notification_manager.config.min_gap_minutes = 0
    daytime = dt.datetime(2026, 8, 23, 14, 0)  # fixed, in-quiet-hours-safe clock
    for i in range(3):
        t = daytime + dt.timedelta(minutes=i)
        agent.notification_manager.try_send(NotificationKind.WATER, {}, t)
        agent.notification_manager.record_skipped(NotificationKind.WATER, t)

    allowed, reason = agent.notification_manager.can_send(NotificationKind.WATER, daytime + dt.timedelta(minutes=5))
    assert not allowed
    assert reason == "adaptive_backoff"
