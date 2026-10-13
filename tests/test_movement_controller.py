from app.creature.movement_controller import MovementController, Rect


def make_controller(**kwargs):
    area = Rect(left=0, top=0, right=1920, bottom=1040)  # e.g. taskbar-excluded work area
    return MovementController(area, creature_size=110, start_pos=(100, 900), **kwargs)


def test_starts_stationary():
    mc = make_controller()
    assert mc.is_moving is False


def test_walk_left_to_right_sets_target_near_right_edge():
    mc = make_controller()
    mc.walk_left_to_right()
    assert mc.is_moving is True
    assert mc.target_x == 1920 - 110
    assert mc.facing_right is True


def test_walk_right_to_left_sets_target_near_left_edge():
    mc = make_controller()
    mc.x = 1000
    mc.walk_right_to_left()
    assert mc.target_x == 0
    assert mc.facing_right is False


def test_update_moves_toward_target_and_stops_on_arrival():
    mc = make_controller()
    mc.move_to(1000, 900)
    start_x = mc.x
    still_moving = mc.update(1.0)  # 1 second at "normal" speed (110px/s)
    assert mc.x > start_x
    assert still_moving is True

    # Run enough ticks to arrive.
    for _ in range(200):
        if not mc.update(1.0):
            break
    assert mc.is_moving is False
    assert mc.position() == (1000, 900)


def test_never_moves_outside_safe_area():
    mc = make_controller()
    mc.move_to(-500, -500)  # way outside
    assert mc.target_x >= 0
    assert mc.target_y >= 0

    mc.move_to(99999, 99999)
    assert mc.target_x <= 1920 - 110
    assert mc.target_y <= 1040 - 110


def test_random_position_stays_in_bottom_band():
    mc = make_controller()
    for _ in range(20):
        mc.walk_to_random_position()
        assert mc.target_y >= 1040 * 0.78 - 1  # allow tiny float slack
        assert 0 <= mc.target_x <= 1920 - 110


def test_set_safe_area_clamps_current_position():
    mc = make_controller()
    mc.x, mc.y = 1800, 1000
    smaller_area = Rect(left=0, top=0, right=800, bottom=600)
    mc.set_safe_area(smaller_area)
    assert mc.x <= 800 - 110
    assert mc.y <= 600 - 110


def test_speed_presets_affect_travel_time():
    slow = make_controller(speed_key="slow")
    fast = make_controller(speed_key="fast")
    assert fast.speed > slow.speed
