"""
Best-effort full-screen application detection (Section 22).

Heuristic: the foreground window's bounding rect exactly matches a monitor's
bounding rect, and it isn't the desktop/shell itself. This catches most
full-screen games, video players, and presentation software without needing
per-app integration. It is intentionally conservative (a false "not
fullscreen" just means a reminder might appear during actual fullscreen
sometimes, which is the safer failure mode than incorrectly suppressing
everything).
"""

from __future__ import annotations

import sys


def is_foreground_window_fullscreen() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False

        # Ignore the desktop / shell windows.
        class_name_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name_buf, 256)
        if class_name_buf.value in ("Progman", "WorkerW", "Shell_TrayWnd"):
            return False

        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False

        monitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        if not monitor:
            return False

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return False

        m = info.rcMonitor
        return (
            rect.left <= m.left
            and rect.top <= m.top
            and rect.right >= m.right
            and rect.bottom >= m.bottom
        )
    except Exception:
        # Never let fullscreen detection failure crash the agent (Section 32).
        return False
