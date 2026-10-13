import datetime as dt

from app.notifications.notification_manager import (
    NotificationKind,
    NotificationManager,
    NotificationManagerConfig,
)


def make_manager(**overrides):
    cfg = NotificationManagerConfig(
        min_gap_minutes=10,
        quiet_hours_start="22:30",
        quiet_hours_end="07:00",
        pause_on_fullscreen=True,
        notifications_enabled=True,
        skip_backoff_threshold=3,
        skip_backoff_minutes=60,
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return NotificationManager(cfg)


def test_first_notification_allowed():
    mgr = make_manager()
    now = dt.datetime(2026, 8, 23, 12, 0)
    allowed, reason = mgr.can_send(NotificationKind.BREAK, now)
    assert allowed
    assert reason == "ok"


def test_min_gap_enforced():
    mgr = make_manager()
    now = dt.datetime(2026, 8, 23, 12, 0)
    assert mgr.try_send(NotificationKind.BREAK, {}, now)
    mgr.record_dismissed(NotificationKind.BREAK)

    soon = now + dt.timedelta(minutes=5)
    allowed, reason = mgr.can_send(NotificationKind.WATER, soon)
    assert not allowed
    assert reason == "min_gap_not_elapsed"

    later = now + dt.timedelta(minutes=11)
    allowed, reason = mgr.can_send(NotificationKind.WATER, later)
    assert allowed


def test_only_one_active_notification_at_a_time():
    mgr = make_manager()
    now = dt.datetime(2026, 8, 23, 12, 0)
    assert mgr.try_send(NotificationKind.BREAK, {}, now)
    # Still "active" (not dismissed) - a second kind should be blocked
    allowed, reason = mgr.can_send(NotificationKind.WATER, now)
    assert not allowed
    assert reason == "another_notification_active"

    mgr.record_dismissed(NotificationKind.BREAK)
    later = now + dt.timedelta(minutes=11)
    allowed, reason = mgr.can_send(NotificationKind.WATER, later)
    assert allowed


def test_quiet_hours_wraps_midnight():
    mgr = make_manager()
    late_night = dt.datetime(2026, 8, 23, 23, 0)
    allowed, reason = mgr.can_send(NotificationKind.BREAK, late_night)
    assert not allowed and reason == "quiet_hours"

    early_morning = dt.datetime(2026, 8, 23, 6, 0)
    allowed, reason = mgr.can_send(NotificationKind.BREAK, early_morning)
    assert not allowed and reason == "quiet_hours"

    daytime = dt.datetime(2026, 8, 23, 14, 0)
    allowed, reason = mgr.can_send(NotificationKind.BREAK, daytime)
    assert allowed


def test_pause_mode_blocks_notifications():
    mgr = make_manager()
    now = dt.datetime(2026, 8, 23, 12, 0)
    mgr.pause_for(30, now)
    allowed, reason = mgr.can_send(NotificationKind.BREAK, now + dt.timedelta(minutes=10))
    assert not allowed and reason == "paused"

    after_pause = now + dt.timedelta(minutes=31)
    allowed, reason = mgr.can_send(NotificationKind.BREAK, after_pause)
    assert allowed


def test_fullscreen_suppression():
    mgr = make_manager()
    mgr.set_fullscreen_active(True)
    now = dt.datetime(2026, 8, 23, 12, 0)
    allowed, reason = mgr.can_send(NotificationKind.BREAK, now)
    assert not allowed and reason == "fullscreen_active"

    mgr.set_fullscreen_active(False)
    allowed, reason = mgr.can_send(NotificationKind.BREAK, now)
    assert allowed


def test_info_notifications_bypass_gating():
    mgr = make_manager()
    now = dt.datetime(2026, 8, 23, 23, 0)  # quiet hours
    mgr.pause_for(60, now)
    allowed, reason = mgr.can_send(NotificationKind.INFO, now)
    assert allowed  # INFO (e.g. "good morning") is never gated


def test_adaptive_backoff_after_repeated_skips():
    mgr = make_manager(min_gap_minutes=0)
    now = dt.datetime(2026, 8, 23, 12, 0)

    for i in range(3):
        t = now + dt.timedelta(minutes=i)
        allowed, _ = mgr.can_send(NotificationKind.WATER, t)
        assert allowed
        mgr.try_send(NotificationKind.WATER, {}, t)
        mgr.record_skipped(NotificationKind.WATER, t)

    # After 3 consecutive skips, backoff kicks in
    soon_after = now + dt.timedelta(minutes=5)
    allowed, reason = mgr.can_send(NotificationKind.WATER, soon_after)
    assert not allowed and reason == "adaptive_backoff"

    much_later = now + dt.timedelta(minutes=65)
    allowed, reason = mgr.can_send(NotificationKind.WATER, much_later)
    assert allowed


def test_acknowledgement_resets_backoff():
    mgr = make_manager(min_gap_minutes=0, skip_backoff_threshold=2)
    now = dt.datetime(2026, 8, 23, 12, 0)
    mgr.try_send(NotificationKind.EXERCISE, {}, now)
    mgr.record_skipped(NotificationKind.EXERCISE, now)
    mgr.try_send(NotificationKind.EXERCISE, {}, now + dt.timedelta(minutes=1))
    mgr.record_acknowledged(NotificationKind.EXERCISE)  # user did it -> reset

    tracker = mgr._skip_trackers[NotificationKind.EXERCISE]
    assert tracker.consecutive_skips == 0
    assert tracker.backoff_until is None


def test_notifications_disabled_blocks_everything():
    mgr = make_manager(notifications_enabled=False)
    now = dt.datetime(2026, 8, 23, 12, 0)
    allowed, reason = mgr.can_send(NotificationKind.BREAK, now)
    assert not allowed and reason == "notifications_disabled"
