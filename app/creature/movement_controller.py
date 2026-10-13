"""
Movement controller (Section 7-8): smooth lerp-based movement between
points on the desktop, constrained to valid screen area and aware of
multiple monitors. Framework-agnostic (works in pixel coordinates handed to
it) so it's unit-testable without Qt/a display.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


class MovementDirection(str, Enum):
    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"
    RANDOM = "random"


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


SPEED_PRESETS_PX_PER_SEC = {
    "slow": 60.0,
    "normal": 110.0,
    "fast": 180.0,
}


class MovementController:
    """
    Tracks the creature's current (x, y) and a target (x, y), advancing
    smoothly toward the target each tick via `update(dt_seconds)`.

    Bottom-of-screen bias (Section 7: "creature should normally stay near
    the bottom portion of the screen") is implemented by biasing random Y
    targets toward the lower band of the safe area rather than uniform
    sampling across the whole height.
    """

    def __init__(
        self,
        safe_area: Rect,
        creature_size: int = 110,
        speed_key: str = "normal",
        start_pos: Optional[tuple[float, float]] = None,
    ) -> None:
        self.safe_area = safe_area
        self.creature_size = creature_size
        self.speed = SPEED_PRESETS_PX_PER_SEC.get(speed_key, 110.0)
        self.x, self.y = start_pos or self._default_start()
        self.target_x, self.target_y = self.x, self.y
        self.is_moving = False
        self.facing_right = True

    def _default_start(self) -> tuple[float, float]:
        x = self.safe_area.left + self.safe_area.width * 0.5
        y = self._bottom_band_y()
        return x, y

    def _bottom_band_y(self) -> float:
        # Bottom 20% band of the safe area, keeping clear of the very edge.
        band_top = self.safe_area.top + self.safe_area.height * 0.78
        band_bottom = self.safe_area.bottom - self.creature_size
        band_bottom = max(band_top, band_bottom)
        return random.uniform(band_top, band_bottom)

    def set_safe_area(self, safe_area: Rect) -> None:
        """Called when monitor configuration changes (Section 8)."""
        self.safe_area = safe_area
        self.x = min(max(self.x, safe_area.left), safe_area.right - self.creature_size)
        self.y = min(max(self.y, safe_area.top), safe_area.bottom - self.creature_size)

    def move_to(self, x: float, y: float) -> None:
        max_x = self.safe_area.right - self.creature_size
        max_y = self.safe_area.bottom - self.creature_size
        self.target_x = min(max(x, self.safe_area.left), max_x)
        self.target_y = min(max(y, self.safe_area.top), max_y)
        self.facing_right = self.target_x >= self.x
        self.is_moving = True

    def walk_left_to_right(self) -> None:
        self.move_to(self.safe_area.right - self.creature_size, self._bottom_band_y())

    def walk_right_to_left(self) -> None:
        self.move_to(self.safe_area.left, self._bottom_band_y())

    def walk_to_random_position(self) -> None:
        max_x = self.safe_area.right - self.creature_size
        x = random.uniform(self.safe_area.left, max_x)
        y = self._bottom_band_y()
        self.move_to(x, y)

    def update(self, dt_seconds: float) -> bool:
        """
        Advance position toward target. Returns True while still moving,
        False once arrived (so callers can trigger an idle animation).
        """
        if not self.is_moving:
            return False

        remaining_x = self.target_x - self.x
        remaining_y = self.target_y - self.y
        distance = (remaining_x**2 + remaining_y**2) ** 0.5

        if distance < 1.0:
            self.x, self.y = self.target_x, self.target_y
            self.is_moving = False
            return False

        step = self.speed * dt_seconds
        t = min(1.0, step / distance)
        self.x = lerp(self.x, self.target_x, t)
        self.y = lerp(self.y, self.target_y, t)
        return True

    def position(self) -> tuple[int, int]:
        return int(self.x), int(self.y)
