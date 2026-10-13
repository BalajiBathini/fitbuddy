"""
The desktop creature window (Section 6-9).

Design decision: Bobo is drawn procedurally with QPainter rather than
shipping PNG/sprite-sheet binary assets. This keeps the whole app as
readable, diffable source code (no opaque binary art files to review),
avoids any risk of accidentally reusing someone else's copyrighted
artwork, and is trivial to re-skin/re-theme later. It satisfies the
"transparent background, ~80-140px, rounded body, big eyes, tiny feet,
soft cartoon look" brief in Section 6. If real sprite artwork is produced
later, this class's `paintEvent` is the only place that needs to change -
swap it for QPixmap frame blits and the rest of the app (movement,
animation state machine, notifications) is untouched.

Window flags implement Section 6's requirements:
    - Qt.FramelessWindowHint          -> no title bar / border
    - Qt.WindowStaysOnTopHint         -> always-on-desktop
    - Qt.Tool                         -> no taskbar entry
    - WA_TranslucentBackground        -> transparent background
Click-through vs. clickable is toggled via WA_TransparentForMouseEvents:
Bobo is normally clickable (Section 9 interaction menu), but the app can
flip this on to let clicks pass through during full-screen apps if desired.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from app.creature.animation_controller import AnimationController, AnimationState


BODY_COLOR = QColor("#8BD6C8")
BODY_SHADOW = QColor("#6FBFAF")
EYE_WHITE = QColor("#FFFFFF")
EYE_PUPIL = QColor("#2B2B2B")
CHEEK_COLOR = QColor(255, 170, 170, 140)
EAR_COLOR = QColor("#79C6B6")
FOOT_COLOR = QColor("#5FA895")


class CreatureWindow(QWidget):
    clicked = Signal()

    def __init__(self, size_px: int = 110) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.size_px = size_px
        self.bubble_area_h = 60  # reserved space above Bobo for the speech bubble
        self.resize(size_px, int(size_px * 1.05) + self.bubble_area_h)

        self.animation = AnimationController()
        self._speech_bubble_text: str | None = None
        self._speech_bubble_timer = QTimer(self)
        self._speech_bubble_timer.setSingleShot(True)
        self._speech_bubble_timer.timeout.connect(self.hide_speech_bubble)

        self._paint_timer = QTimer(self)
        self._paint_timer.timeout.connect(self._on_tick)
        self._paint_timer.start(1000 // 24)  # ~24fps, cheap for a small window
        self._last_tick_ms = 0

    # -- public API used by app/main.py / agent callbacks -----------------
    def set_animation_state(self, state: AnimationState) -> None:
        self.animation.set_state(state)

    def show_speech_bubble(self, text: str, duration_ms: int = 4000) -> None:
        self._speech_bubble_text = text
        self.update()
        self._speech_bubble_timer.start(duration_ms)

    def hide_speech_bubble(self) -> None:
        self._speech_bubble_text = None
        self.update()

    def move_to_position(self, x: int, y: int) -> None:
        self.move(QPoint(x, y))

    # -- Qt event plumbing ------------------------------------------------
    def _on_tick(self) -> None:
        self.animation.tick(1.0 / 24.0)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height() - self.bubble_area_h

        painter.save()
        painter.translate(0, self.bubble_area_h)
        facing_right = self.animation.state != AnimationState.WALK_LEFT
        if self.animation.state in (AnimationState.WALK_LEFT, AnimationState.WALK_RIGHT):
            painter.save()
            if not facing_right:
                painter.translate(w, 0)
                painter.scale(-1, 1)
            self._draw_bobo(painter, w, h)
            painter.restore()
        else:
            self._draw_bobo(painter, w, h)
        painter.restore()

        if self._speech_bubble_text:
            self._draw_speech_bubble(painter, w, self.bubble_area_h, self._speech_bubble_text)

    def _draw_bobo(self, painter: QPainter, w: int, h: int) -> None:
        body_top = h * 0.30
        body_h = h * 0.60
        body_w = w * 0.78
        body_left = (w - body_w) / 2

        bob_offset = 0.0
        if self.animation.state == AnimationState.SLEEPING:
            body_top += h * 0.08
        elif self.animation.is_walking():
            bob_offset = 3.0 if int(self.animation._elapsed_in_state * 6) % 2 == 0 else -3.0

        # Feet
        painter.setBrush(QBrush(FOOT_COLOR))
        painter.setPen(Qt.NoPen)
        foot_w, foot_h = w * 0.16, h * 0.09
        painter.drawEllipse(int(body_left + body_w * 0.18), int(body_top + body_h - foot_h * 0.5 + bob_offset), int(foot_w), int(foot_h))
        painter.drawEllipse(int(body_left + body_w * 0.62), int(body_top + body_h - foot_h * 0.5 - bob_offset), int(foot_w), int(foot_h))

        # Ears
        painter.setBrush(QBrush(EAR_COLOR))
        ear_w, ear_h = w * 0.16, h * 0.16
        painter.drawEllipse(int(body_left + body_w * 0.05), int(body_top - ear_h * 0.45), int(ear_w), int(ear_h))
        painter.drawEllipse(int(body_left + body_w * 0.80), int(body_top - ear_h * 0.45), int(ear_w), int(ear_h))

        # Body (rounded, with a soft shadow at the base for depth)
        path = QPainterPath()
        path.addRoundedRect(body_left, body_top + bob_offset, body_w, body_h, body_w * 0.4, body_h * 0.4)
        painter.setBrush(QBrush(BODY_COLOR))
        painter.drawPath(path)

        # Cheeks
        painter.setBrush(QBrush(CHEEK_COLOR))
        cheek_r = w * 0.07
        cheek_y = body_top + body_h * 0.55 + bob_offset
        painter.drawEllipse(int(body_left + body_w * 0.08), int(cheek_y), int(cheek_r), int(cheek_r))
        painter.drawEllipse(int(body_left + body_w * 0.78), int(cheek_y), int(cheek_r), int(cheek_r))

        # Eyes (big + expressive; closed line if blinking or sleeping)
        eye_y = body_top + body_h * 0.32 + bob_offset
        eye_r = w * 0.13
        eye_gap = body_w * 0.28
        eye_cx1 = body_left + body_w * 0.5 - eye_gap / 2
        eye_cx2 = body_left + body_w * 0.5 + eye_gap / 2

        closed = self.animation.blink_phase or self.animation.state == AnimationState.SLEEPING
        if closed:
            pen = QPen(EYE_PUPIL, 3)
            painter.setPen(pen)
            painter.drawLine(int(eye_cx1 - eye_r / 2), int(eye_y), int(eye_cx1 + eye_r / 2), int(eye_y))
            painter.drawLine(int(eye_cx2 - eye_r / 2), int(eye_y), int(eye_cx2 + eye_r / 2), int(eye_y))
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(EYE_WHITE))
            painter.drawEllipse(int(eye_cx1 - eye_r / 2), int(eye_y - eye_r / 2), int(eye_r), int(eye_r))
            painter.drawEllipse(int(eye_cx2 - eye_r / 2), int(eye_y - eye_r / 2), int(eye_r), int(eye_r))
            painter.setBrush(QBrush(EYE_PUPIL))
            pupil_r = eye_r * 0.5
            painter.drawEllipse(int(eye_cx1 - pupil_r / 2), int(eye_y - pupil_r / 2), int(pupil_r), int(pupil_r))
            painter.drawEllipse(int(eye_cx2 - pupil_r / 2), int(eye_y - pupil_r / 2), int(pupil_r), int(pupil_r))

        # Mouth: bigger smile for HAPPY, small smile otherwise
        mouth_y = body_top + body_h * 0.62 + bob_offset
        mouth_w = body_w * (0.30 if self.animation.state == AnimationState.HAPPY else 0.18)
        painter.setPen(QPen(EYE_PUPIL, 2))
        painter.setBrush(Qt.NoBrush)
        rect_x = body_left + body_w * 0.5 - mouth_w / 2
        painter.drawArc(int(rect_x), int(mouth_y), int(mouth_w), int(mouth_w * 0.7), 190 * 16, 160 * 16)

    def _draw_speech_bubble(self, painter: QPainter, w: int, bubble_area_h: int, text: str) -> None:
        painter.setPen(QPen(QColor("#444444"), 1.5))
        painter.setBrush(QBrush(QColor(255, 255, 255, 235)))
        bubble_w = min(w + 40, max(140, 9 * len(text)))
        bubble_h = bubble_area_h - 8
        bx = int(w / 2 - bubble_w / 2)
        by = 2
        painter.drawRoundedRect(bx, by, bubble_w, bubble_h, 10, 10)
        painter.setPen(QColor("#222222"))
        painter.drawText(bx + 8, by, bubble_w - 16, bubble_h, Qt.AlignCenter | Qt.TextWordWrap, text)
