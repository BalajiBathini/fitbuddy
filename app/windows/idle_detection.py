"""
Windows idle-time detection (Section 10).

Uses GetLastInputInfo via pywin32/ctypes to find seconds-since-last-input,
which is the correct, low-overhead way to distinguish "laptop powered on"
from "user actually touching the keyboard/mouse" - we deliberately do NOT
hook individual keys or record what was typed (Section 26 privacy rule).

On non-Windows platforms (this dev sandbox, CI, macOS/Linux contributors)
this falls back to a manual `SimulatedIdleSource` so the rest of the agent
remains fully testable without Windows.
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod


class IdleTimeSource(ABC):
    """Abstraction over 'how many seconds since the user last touched input'."""

    @abstractmethod
    def get_idle_seconds(self) -> float:
        ...


class WindowsIdleTimeSource(IdleTimeSource):
    """Real implementation using the Win32 GetLastInputInfo API."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        self._ctypes = ctypes
        self._LASTINPUTINFO = LASTINPUTINFO

    def get_idle_seconds(self) -> float:
        ctypes = self._ctypes
        info = self._LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(self._LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):  # type: ignore[attr-defined]
            # Fall back to "assume active" if the API call fails; never let
            # idle-detection failure block the whole agent (Section 32).
            return 0.0
        millis_since_boot = ctypes.windll.kernel32.GetTickCount()  # type: ignore[attr-defined]
        idle_millis = millis_since_boot - info.dwTime
        return max(0.0, idle_millis / 1000.0)


class SimulatedIdleTimeSource(IdleTimeSource):
    """
    Test/dev-only source. Call `touch()` to simulate user input, or
    `set_idle_seconds()` to directly force a value. Used on non-Windows
    platforms and in unit tests.
    """

    def __init__(self) -> None:
        self._idle_seconds = 0.0

    def touch(self) -> None:
        self._idle_seconds = 0.0

    def set_idle_seconds(self, seconds: float) -> None:
        self._idle_seconds = seconds

    def advance(self, seconds: float) -> None:
        self._idle_seconds += seconds

    def get_idle_seconds(self) -> float:
        return self._idle_seconds


def get_idle_time_source() -> IdleTimeSource:
    """Factory: real Win32 source on Windows, simulated source elsewhere."""
    if sys.platform == "win32":
        try:
            return WindowsIdleTimeSource()
        except Exception:
            # Graceful fallback per Section 32: never crash the agent because
            # a platform API is unavailable on some Windows configuration.
            return SimulatedIdleTimeSource()
    return SimulatedIdleTimeSource()


def is_session_locked() -> bool:
    """
    Best-effort lock-state check (Section 33). Uses the WTSGetActiveConsoleSessionId
    / WTSQuerySessionInformation pattern via ctypes. Returns False (assume
    unlocked) if the platform or API is unavailable, which is the safe
    default (we'd rather occasionally track a locked session briefly than
    silently stop tracking a legitimately active one).
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        # OpenInputDesktop fails while the workstation is locked because the
        # secure desktop is active; this is a common, lightweight heuristic.
        desktop = user32.OpenInputDesktop(0, False, 0)
        if desktop == 0:
            return True
        user32.CloseDesktop(desktop)
        return False
    except Exception:
        return False
