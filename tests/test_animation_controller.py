from app.creature.animation_controller import AnimationController, AnimationState


def test_default_state_is_idle():
    ac = AnimationController()
    assert ac.state == AnimationState.IDLE


def test_set_state_resets_elapsed_time():
    ac = AnimationController()
    ac.tick(1.0)
    ac.set_state(AnimationState.WALK_LEFT)
    assert ac._elapsed_in_state == 0.0
    assert ac.state == AnimationState.WALK_LEFT


def test_is_walking():
    ac = AnimationController()
    assert ac.is_walking() is False
    ac.set_state(AnimationState.WALK_RIGHT)
    assert ac.is_walking() is True


def test_idle_micro_behaviors_only_trigger_while_idle():
    ac = AnimationController()
    ac.set_state(AnimationState.WALK_LEFT)
    ac._next_micro_behavior_at = 0.0  # force it to be "due"
    ac.tick(0.1)
    assert ac.current_micro_behavior is None  # suppressed while walking


def test_idle_micro_behavior_eventually_triggers_when_idle():
    ac = AnimationController()
    ac._next_micro_behavior_at = 0.0
    ac.tick(0.1)
    assert ac.current_micro_behavior is not None


def test_idle_animations_can_be_disabled():
    ac = AnimationController(idle_animations_enabled=False)
    ac._next_micro_behavior_at = 0.0
    ac.tick(0.1)
    assert ac.current_micro_behavior is None


def test_blink_cycles_over_time():
    ac = AnimationController()
    ac._next_blink_at = 0.0
    ac.tick(0.01)
    assert ac.blink_phase is True
    ac.tick(0.2)  # past the 0.15s blink duration
    assert ac.blink_phase is False
