"""
Animation state machine (Section 6): idle / walk_left / walk_right / happy /
sleeping / drinking / stretching / exercise / notification.

Framework-agnostic: it just tracks "which animation is active" and a
frame-progress float, plus randomized idle micro-behaviors (blink, look
around, stretch) per Section 7/30. app/creature/creature_window.py reads
`current_state` and `blink` each paint tick and draws Bobo accordingly with
QPainter (no sprite sheet required, see creature_window.py docstring).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum


class AnimationState(str, Enum):
    IDLE = "idle"
    WALK_LEFT = "walk_left"
    WALK_RIGHT = "walk_right"
    HAPPY = "happy"
    SLEEPING = "sleeping"
    DRINKING = "drinking"
    STRETCHING = "stretching"
    EXERCISE = "exercise"
    NOTIFICATION = "notification"


IDLE_MICRO_BEHAVIORS = ("blink", "look_around", "sit", "stretch", "wave")


@dataclass
class AnimationController:
    state: AnimationState = AnimationState.IDLE
    idle_animations_enabled: bool = True

    def __post_init__(self) -> None:
        self._elapsed_in_state: float = 0.0
        self._next_micro_behavior_at: float = self._random_micro_interval()
        self.current_micro_behavior: str | None = None
        self._micro_behavior_remaining: float = 0.0
        self.blink_phase: bool = False
        self._next_blink_at: float = random.uniform(2.0, 5.0)
        self._blink_timer: float = 0.0

    @staticmethod
    def _random_micro_interval() -> float:
        return random.uniform(15.0, 45.0)

    def set_state(self, state: AnimationState) -> None:
        if state != self.state:
            self.state = state
            self._elapsed_in_state = 0.0

    def is_walking(self) -> bool:
        return self.state in (AnimationState.WALK_LEFT, AnimationState.WALK_RIGHT)

    def is_interruptible(self) -> bool:
        """Idle micro-behaviors should only trigger while not mid-walk/exercise."""
        return self.state == AnimationState.IDLE

    def tick(self, dt_seconds: float) -> None:
        self._elapsed_in_state += dt_seconds

        # Blink cycling, independent of state (a creature can blink while idle).
        self._blink_timer += dt_seconds
        if self._blink_timer >= self._next_blink_at:
            self.blink_phase = True
            self._blink_timer = 0.0
            self._next_blink_at = random.uniform(2.0, 5.0)
        elif self.blink_phase and self._blink_timer > 0.15:
            self.blink_phase = False

        if not self.idle_animations_enabled or not self.is_interruptible():
            self.current_micro_behavior = None
            return

        if self.current_micro_behavior is not None:
            self._micro_behavior_remaining -= dt_seconds
            if self._micro_behavior_remaining <= 0:
                self.current_micro_behavior = None
            return

        self._next_micro_behavior_at -= dt_seconds
        if self._next_micro_behavior_at <= 0:
            self.current_micro_behavior = random.choice(IDLE_MICRO_BEHAVIORS)
            self._micro_behavior_remaining = random.uniform(1.5, 3.0)
            self._next_micro_behavior_at = self._random_micro_interval()
