"""
Cute, motivational copy for FitBuddy's notifications (Section 2 personality
rules: encouraging, never commanding, never shaming). Kept as plain data so
non-English locales can eventually replace this module wholesale.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationContent:
    title: str
    body: str
    actions: tuple[str, ...] = ()


BREAK_MESSAGES = [
    "Hey! \U0001F43E You've been at it for a while. Let's move for a few minutes!",
    "Psst \U0001F43E your legs called - they'd like a stretch break.",
    "\U0001F43E Bobo thinks you've earned a little break!",
]

WATER_MESSAGES = [
    "\U0001F43E Bobo notices you've been focused for a while. How about some water? \U0001F4A7",
    "Hydration check! \U0001F4A7 Your body will appreciate a sip.",
    "\U0001F43E Quick water break? Just a little sip goes a long way.",
]

EXERCISE_MESSAGES = [
    "\U0001F43E Quick fitness break - let's do {target} {name}!",
    "\U0001F43E Feeling up for {target} {name}? Only takes a moment.",
]

BACK_OFF_MESSAGE = "\U0001F43E I'll leave you alone for a little while \U0001F634"

CELEBRATION_MESSAGES = [
    "\U0001F389 Nice job!",
    "\U0001F43E Woohoo, way to go!",
    "\U0001F4AA Look at you go!",
]

MORNING_GREETING = "\U0001F43E Good morning! Let's have a great day."


def break_notification() -> NotificationContent:
    return NotificationContent(
        title="BOBO SAYS",
        body=random.choice(BREAK_MESSAGES),
        actions=("Start Break", "Remind Later", "Skip"),
    )


def water_notification() -> NotificationContent:
    return NotificationContent(
        title="WATER TIME \U0001F4A7",
        body=random.choice(WATER_MESSAGES),
        actions=("250 ml", "500 ml", "Custom", "Skip"),
    )


def exercise_notification(exercise_name: str, target: float, unit: str) -> NotificationContent:
    template = random.choice(EXERCISE_MESSAGES)
    body = template.format(target=f"{target:g} {unit}", name=exercise_name.lower())
    return NotificationContent(
        title="QUICK FITNESS BREAK",
        body=body,
        actions=("Start", "Skip"),
    )


def back_off_notification() -> NotificationContent:
    return NotificationContent(title="", body=BACK_OFF_MESSAGE)


def celebration_message() -> str:
    return random.choice(CELEBRATION_MESSAGES)


def evening_summary(
    active_hm: str,
    breaks_count: int,
    water_ml: int,
    water_goal_ml: int,
    exercise_reps: int,
    score: float,
) -> NotificationContent:
    body = (
        f"Great work today! \U0001F389\n\n"
        f"\U0001F4BB Active computer time: {active_hm}\n"
        f"\U0001F9D8 Breaks: {breaks_count}\n"
        f"\U0001F4A7 Water: {water_ml / 1000:.1f} / {water_goal_ml / 1000:.1f} L\n"
        f"\U0001F4AA Exercise: {exercise_reps} reps\n"
        f"\U0001F525 Daily score: {score:.0f}%"
    )
    return NotificationContent(title="TODAY'S SUMMARY \U0001F43E", body=body)
