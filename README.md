# FitBuddy \U0001F43E

A cute animated desktop fitness companion for Windows 10/11. Bobo lives on
your desktop, notices when you've been at the computer a while, and gently
nudges you to take breaks, drink water, and move — all tracked locally in
SQLite, with a native dashboard, no cloud, no camera, no keylogging.

## Status

This is a working, tested MVP implementation of the full spec:

- **Backend (fully implemented, 63 passing automated tests):** SQLite
  persistence, active/idle session tracking, break/water/exercise reminder
  logic, the notification cooldown/quiet-hours/pause/fullscreen gating
  rules, a rule-based recommendation engine, and Windows integration
  (idle detection, startup registration, fullscreen detection) with safe
  fallbacks on non-Windows platforms.
- **UI (implemented and verified via offscreen rendering):** the desktop
  creature (drawn procedurally with QPainter — see "About Bobo's art"
  below), notification popups, break countdown screen, system tray, native
  dashboard with weekly charts, settings dialog, and first-launch wizard.
- **Not yet done for you:** an actual compiled `.exe` and installer. This
  was built in a Linux sandbox, which can produce and test all the Python
  above but cannot run PyInstaller for Windows or verify tray/registry/
  lock-screen behavior on real Windows. `build.py` and `installer/` are
  ready to go — see "Building the Windows executable" below.

## About Bobo's art

Bobo is drawn procedurally with `QPainter` in `app/creature/creature_window.py`
rather than shipped as PNG/sprite-sheet assets. This was a deliberate choice:
it keeps 100% of the app as readable, diffable source code, avoids any risk
of inadvertently reusing someone else's artwork, and is trivial to re-skin.
If you'd rather use real hand-drawn sprite art later, `_draw_bobo()` and
`paintEvent()` are the only places that need to change — swap them for
`QPixmap` frame blits keyed by `AnimationState`, and nothing else in the
app (movement, notifications, agent logic) needs to know the difference.

## Project layout

```
fitbuddy/
├── app/
│   ├── main.py                  # composition root / entry point
│   ├── config.py                # paths, default settings
│   ├── agent/                   # activity monitor, break manager,
│   │                             recommendation engine, scheduler
│   ├── creature/                # movement + animation controllers, the
│   │                             creature window itself
│   ├── notifications/           # notification gating rules + copy
│   ├── fitness/                 # exercise catalog, water & stats services
│   ├── database/                # SQLAlchemy models, engine, repositories
│   ├── ui/                      # tray, dashboard, settings, popups, wizard
│   └── windows/                 # idle detection, startup registration,
│                                   fullscreen detection (Win32 via ctypes)
├── tests/                       # 63 pytest tests, all platform-independent
├── installer/                   # Inno Setup script + build batch file
├── build.py                     # PyInstaller build script
└── requirements.txt
```

## Running it (development / any platform)

```bash
python -m venv .venv
source .venv/bin/activate        # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m app.main
```

On non-Windows platforms, idle detection, startup registration, and
fullscreen detection automatically fall back to safe no-ops/simulated
sources (see `app/windows/`), so the app runs and is fully testable, but
"start with Windows" and true idle tracking only work on actual Windows.

## Running the tests

```bash
pip install -r requirements.txt
PYTHONPATH=. pytest tests/ -v
```

All 63 tests are pure-logic (database, activity monitor, notification
rules, break/recommendation logic, movement/animation math) and run
without a display. No Windows machine or GUI needed.

## Building the Windows executable

This must be done **on a Windows 10/11 machine** (PyInstaller does not
cross-compile):

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python build.py
```

This produces `dist\FitBuddy\FitBuddy.exe` (a `--onedir` build — faster
startup than `--onefile`; edit `build.py` if you'd rather have a single
file). Test it by double-clicking; it should show no console window, put
an icon in the system tray, and (on first launch) show the onboarding
wizard.

## Building the installer

Requires [Inno Setup 6](https://jrsoftware.org/isinfo.php):

```powershell
cd installer
build_installer.bat
```

This produces `installer\Output\FitBuddy Setup.exe`, which:
- installs to `%LOCALAPPDATA%\Programs\FitBuddy` by default (no admin
  rights required — `PrivilegesRequired=lowest` in `fitbuddy.iss`)
- creates a Start Menu shortcut and an optional desktop shortcut
- offers to register FitBuddy for startup via the per-user registry Run
  key (the same mechanism `app/windows/startup.py` uses at runtime, so the
  installer checkbox and the in-app Settings toggle stay consistent)
- launches FitBuddy immediately after install
- on uninstall, removes the application files and asks separately whether
  to also delete your activity history/settings under
  `%LOCALAPPDATA%\FitBuddy\`

## Data & privacy

Everything lives in `%LOCALAPPDATA%\FitBuddy\`:
- `fitbuddy.db` — SQLite database (settings, sessions, activity/water/break
  logs, daily summaries)
- `logs\fitbuddy.log` — rotating application log (5 x 2MB)

FitBuddy never records keystrokes, captures screenshots, or accesses the
camera/microphone. Idle detection uses only `GetLastInputInfo` (seconds
since last input), never *what* was typed or clicked. Nothing leaves your
machine — there is no network code in this app at all.

## Extending toward the roadmap items

The architecture leaves clean seams for the Section 45 "future version"
items without needing rework:
- **AI recommendations:** implement `RecommendationEngine`
  (`app/agent/recommendation_engine.py`) with an `AIRecommendationEngine`
  that receives only the summarized `RecommendationContext` — never raw
  activity data — and still routes everything through
  `NotificationManager`, so it can't bypass quiet hours/pause/cooldowns.
- **Computer-vision rep counting:** `ActivityService.complete_activity()`
  already accepts a `source` field (`"manual"` / `"reminder"` /
  `"creature_menu"`); a `"cv_camera"` source and a rep-counting module
  could plug in without touching the database schema.
- **Real sprite art:** see "About Bobo's art" above.

## Known simplifications (documented, not hidden)

- Lock-state detection (`app/windows/idle_detection.is_session_locked`)
  polls every 10s via `OpenInputDesktop` rather than subscribing to
  `WM_WTSSESSION_CHANGE` natively — simpler and reliable, at the cost of
  a small detection delay. Noted in `main.py`'s `_start_lock_watcher`.
- Full-screen detection is a foreground-window-vs-monitor-bounds heuristic
  (`app/windows/fullscreen.py`), not a per-application allowlist — it
  covers the common cases (games, video players, presentations) but isn't
  exhaustive.
- The weekly dashboard charts are simple `QPainter` bar charts rather than
  a charting library dependency — kept intentionally lightweight for the
  MVP.
