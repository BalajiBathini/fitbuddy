import datetime as dt

import pytest

from app.agent.activity_monitor import ActivityMonitor, ActivityState
from app.database.database import Database
from app.database.repositories import SessionRepository
from app.windows.idle_detection import SimulatedIdleTimeSource


class ClockStub:
    def __init__(self, start: dt.datetime):
        self.now = start

    def advance(self, seconds: float) -> None:
        self.now += dt.timedelta(seconds=seconds)

    def __call__(self) -> dt.datetime:
        return self.now


@pytest.fixture()
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture()
def monitor(db):
    idle_source = SimulatedIdleTimeSource()
    clock = ClockStub(dt.datetime(2026, 8, 23, 9, 0, 0))
    repo = SessionRepository(db)
    mon = ActivityMonitor(idle_source, repo, idle_threshold_seconds=300, now_fn=clock)
    return mon, idle_source, clock, repo


def test_starts_idle(monitor):
    mon, idle_source, clock, repo = monitor
    assert mon.state == ActivityState.IDLE


def test_transitions_to_active_on_input(monitor):
    mon, idle_source, clock, repo = monitor
    idle_source.touch()  # idle=0, below threshold
    snap = mon.poll()
    assert snap.state == ActivityState.ACTIVE
    assert snap.session_id is not None


def test_accumulates_active_time_across_polls(monitor):
    mon, idle_source, clock, repo = monitor
    idle_source.touch()
    mon.poll()  # session starts

    clock.advance(60)
    idle_source.touch()
    snap = mon.poll()
    assert snap.active_seconds_current_session == pytest.approx(60, abs=1)

    clock.advance(30)
    idle_source.touch()
    snap = mon.poll()
    assert snap.active_seconds_current_session == pytest.approx(90, abs=1)


def test_goes_idle_after_threshold_and_closes_session(monitor):
    mon, idle_source, clock, repo = monitor
    idle_source.touch()
    mon.poll()
    clock.advance(60)
    idle_source.touch()
    mon.poll()

    # Now simulate 301 seconds of no input.
    clock.advance(301)
    idle_source.set_idle_seconds(301)
    snap = mon.poll()
    assert snap.state == ActivityState.IDLE
    assert snap.session_id is None

    # Verify the session was persisted with active_seconds recorded.
    sessions = repo.sessions_between(
        dt.datetime(2026, 8, 23), dt.datetime(2026, 8, 24)
    )
    assert len(sessions) == 1
    assert sessions[0].ended_at is not None
    assert sessions[0].end_reason == "idle_timeout"
    assert sessions[0].active_seconds == pytest.approx(60, abs=1)


def test_reset_break_timer_does_not_end_session(monitor):
    mon, idle_source, clock, repo = monitor
    idle_source.touch()
    mon.poll()
    # Advance in realistic ~20s polling increments (matching the real
    # scheduler's ACTIVITY_POLL_SECONDS) rather than one giant jump, since
    # single-poll deltas are intentionally capped at 300s (clock-jump guard).
    for _ in range(150):  # 150 * 20s = 3000s = 50 minutes
        clock.advance(20)
        idle_source.touch()
        mon.poll()
    assert mon.active_seconds_in_current_session() == pytest.approx(3000, abs=1)

    mon.reset_break_timer()
    assert mon.active_seconds_in_current_session() == 0
    assert mon.state == ActivityState.ACTIVE  # session itself continues


def test_force_end_session_on_lock(monitor):
    mon, idle_source, clock, repo = monitor
    idle_source.touch()
    mon.poll()
    clock.advance(120)
    idle_source.touch()
    mon.poll()

    mon.force_end_session(reason="lock")
    assert mon.state == ActivityState.IDLE

    sessions = repo.sessions_between(dt.datetime(2026, 8, 23), dt.datetime(2026, 8, 24))
    assert sessions[0].end_reason == "lock"


def test_clock_jump_does_not_explode_active_time(monitor):
    """Regression guard for Section 32: handle system clock changes reasonably."""
    mon, idle_source, clock, repo = monitor
    idle_source.touch()
    mon.poll()

    # Simulate a huge clock jump (e.g. NTP resync) between polls.
    clock.advance(999999)
    idle_source.touch()
    snap = mon.poll()
    # Should be capped, not a huge spurious active-time credit.
    assert snap.active_seconds_current_session <= 300
