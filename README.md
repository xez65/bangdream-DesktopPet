# 丰川祥子桌宠模拟器 · Windows Desktop Pet

A Windows desktop pet rendered from **pre-baked Live2D sequence frames** — no Live2D runtime, no
model SDK, just 2,166 WebP frames plus a small behaviour state machine. The character stands on the
taskbar, can be dragged and thrown, reacts to clicks, keeps feeding/mood/affection stats, and runs
wall-clock widgets (hourly chime, sedentary reminder, pomodoro).

Windows 10/11 x64 only — the click-through and idle-detection paths call Win32 through `ctypes`.

| 久坐提醒气泡 | 台词气泡 | 状态数值条 | 300 px 体型 |
|---|---|---|---|
| ![remind](docs/screenshots/01_idle.png) | ![bubble](docs/screenshots/07_bubble.png) | ![stats](docs/screenshots/10_stats_panel.png) | ![scale300](docs/screenshots/11_scale_300.png) |

These are `QWidget.grab()` captures of the real transparent window, so the character shows on a flat
background here but composites over your wallpaper when it is running.

## Features

- **Drag / grab / throw** — gravity landing, bodies clamped back into the screen, and a 0.12 s
  stillness test before release, so slowing down means "put her down", not "throw her".
- **Click** left button to poke, double-click for a bigger reaction, right button for the menu.
- **17 motion groups**, laid out in the menu as idle / walking / expressions / closers. A manual
  choice enters `STATE_MANUAL` and is **pinned**: a looping motion keeps playing until your next
  action instead of being reclaimed by the autonomous state machine. `行为 → 恢复自主行动` hands
  control back.
- **Scroll wheel** cycles three body sizes: 150 / 220 / 300 px (default 220).
- **Raising stats** — fullness, mood, affection, decaying on real elapsed time; four foods in the
  feed menu with different effects; bars drawn above her head inside the same transparent window.
- **Widgets** — hourly chime, sedentary reminder (reads `GetLastInputInfo`, so it stays quiet while
  you are typing), pomodoro (the pet goes into a quiet state instead of stealing focus from your work).
- **Persistence** — `%APPDATA%\DesktopPetSakiko\`, saved on close and re-read on start; offline decay
  is capped at 12 h; a corrupt save is renamed to `.bad-<timestamp>` instead of being overwritten.
- **Single instance** via a named kernel mutex (`Local\DesktopPetSakiko`), which the OS releases even
  when the process is killed hard. The `QLocalServer` pipe under the same name is only the dev control
  channel: `QLocalServer.listen()` is *not* an exclusivity test on Windows (measured on Qt 6.12, two
  live processes both got `listen=True` for the same name and two pets came up), so ownership is never
  decided by the pipe. `DESKTOPPET_GUARD_DEBUG=1` prints which side of each check a process took.
- **System tray** — show/hide, click-through, quit. Click-through is set with `WS_EX_TRANSPARENT`
  through `ctypes` (Qt's own `WindowTransparentForInput` does not work on this window path), so while
  it is on the tray menu is the only way back.
- **Byte-capped LRU** for decoded frames (120 MB default); measured peak working set 82.6 MB.

## Quick start

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

`run.py` puts `src` on `sys.path`, so nothing has to be installed beyond `requirements.txt`, and
`assets/clips/` is committed, so the pet runs the moment you clone.

| command | what it does |
|---|---|
| `.venv\Scripts\python.exe -m pytest -q` | unit, asset-integrity and offscreen Qt tests |
| `.venv\Scripts\python.exe run.py --once` | start, render, write evidence PNGs to `%TEMP%\DesktopPetShots`, exit |
| `.venv\Scripts\python.exe run.py --smoke` | headless start/stop (set `QT_QPA_PLATFORM=offscreen`) |
| `set DESKTOPPET_PERF=1 && .venv\Scripts\python.exe -m pytest -q -k tick` | the wall-clock tick budget gate |
| `.venv\Scripts\python.exe tools\measure_perf.py --seconds 30` | tick / RSS / CPU sampling against the running app |
| `.venv\Scripts\python.exe tools\accept_shots.py --out dev\shots-src` | drive the running pet and capture 12 scenes |

## Build the exe

```bat
.venv\Scripts\python.exe tools\build_exe.py --launch
```

PyInstaller onefile, `--windowed`, icon from `assets/app.ico`. Output is `dist/DesktopPetSakiko.exe`,
renamed afterwards to `凤川祥模拟器.exe` and relaunched under that name to prove the Chinese file name
survives onefile extraction. `dist/BUILD_INFO.json` records size, sha256, frame count, the
`clips.json` hash and the commit the build came from.

On the build machine, the current artifact: **113,500,786 B**, sha256 `8755c847db278ff3…`, exit code 0
in 6.09 s start-to-exit from an empty `%TEMP%` directory with Python stripped from `PATH`
(tick p95 inside that run: 7.73 ms).

That is over GitHub's 100 MB per-file hard limit for commits, so the exe is not in this repo. Either
build it locally with the command above (~40 s) or attach it to a GitHub Release, where the limit is
2 GB per file.

## Layout

```
src/petcore/   pure logic: timeline, physics, behaviour, stats, timers, LRU, clip manifest.
               Never imports PySide6 / PIL / ctypes; tests/test_scaffold.py enforces that with ast.
src/petapp/    Qt shell: window, frame decoding, bubble, menu, tray, store, Win32 glue.
assets/        clips.json, text/lines.json, app.ico, clips/<slug>/NNN.webp  (all committed)
tools/         build_clips.py, make_icon.py, build_exe.py, accept_shots.py, measure_perf.py
docs/          ACCEPTANCE-20261011.md (measured gate table) and screenshots/
tests/         116 items: petcore units, the Qt shell offscreen, the shipped frame pack, and the
               single-instance guard across two real interpreters
```

## The frame pack

`assets/clips/` holds 2,166 WebP frames in 17 groups, 63.0 MB. `assets/clips.json` records the crop
box `(219, 33, 818, 997)` (inclusive corners, 8 px pad), the internal working height of 480, 30 fps,
`quality=82 / method=4`, the `a > 10` alpha threshold used for the union bbox, and the sha256 of the
source index it was built from.

The frames were baked from Live2D motion and expression sets by an offline Unity/Cubism pipeline that
is **not** part of this repository, and the 1024² PNGs sit at the absolute path recorded in
`clips.json` (`sourceFramesRoot`). `tools/build_clips.py` therefore only runs where those originals
exist — point `SRC_ROOT` / `INDEX_PATH` at your own frames to rebuild. Everything the app needs is in
git, and the derivation is reproducible: two independent 8-job builds produced byte-identical output
for all 2,166 files.

`tests/test_assets.py` verifies the pack against `clips.json` — declared frame counts, no filename
gaps, every frame inside the crop box, the idle-loop seam, the byte budget. The tests that need the
1024² originals skip when that path is absent, so a fresh clone is green either way:

| run | result |
|---|---|
| `pytest -q` where the 1024² originals are reachable | 112 passed, 4 skipped |
| `pytest -q` in a scratch copy with `sourceFramesRoot` pointed at a missing path | 109 passed, 7 skipped |

The second row was rehearsed by driving a scratch copy with another project's interpreter, so that run
*also* deselected `test_scaffold.py`'s "interpreter must be inside this project's `.venv`" guard; in a
real clone the guard passes, hence 109 rather than the 108 observed.

The four standing skips in row one are the wall-clock tick gate plus three `test_clips.py` checks that
compare the manifest against `unity_index.json`, which lives with the bake pipeline rather than here;
row two adds the three `test_assets.py` checks that read the 1024² PNGs.

The tick gate is skipped by default on purpose: it asserts a wall-clock budget, and an offscreen
`QTest::qWait` loop reads 8–9 ms on the build box whenever the desktop is busy, while the packaged
exe measured 6.68 ms. `tools/measure_perf.py` is the measurement; `DESKTOPPET_PERF=1 pytest -k tick`
is the in-suite assertion.



## Measured numbers

From `docs/ACCEPTANCE-20261011.md` (2026-10-11; Windows 11 10.0.26200, 2560×1440, DPR 1.0, screen on
and session active — that record also notes the trap: with the session locked, desktop captures read
all-black and the working set was trimmed to 4.9 MB, so those numbers were discarded and re-measured):

- tick p95 **6.68 ms** over 540 ticks; RSS peak **82.6 MB**; CPU **0.06 %** by external
  `GetProcessTimes` differencing over 25 s, 1.16 % self-reported across the process lifetime
- 12 self-rendered scenes, each with a distinct sha256
- 2,166 frames / 63.0 MB pack, byte-reproducible across two independent builds

Not measured, stated plainly: first-frame latency has no instrumentation, so "cold start" here means
process start → clean exit. Interaction *feel* — grab tracking, throw strength, the 3.2 s bubble, the
8–20 s idle rhythm — still needs a human eye.

Auto-start on login and system monitoring were deliberately excluded from scope, so they are not gaps.

## Credits and asset notice

The frames, the motion set and the window icon are derived from **Bang Dream! It's MyGO!!!!! / Ave
Mujica** character artwork and Live2D models that belong to their respective rights holders; they are
not original art. The motion/expression source sets and the icon photograph were taken from
third-party redistributions on the author's machine, and one of those folders carried a request to
credit **冲矢明逸** when the motions are used in video.

The MIT license below covers the **code** only. It does not license the character art, the baked
frames or the icon for reuse, redistribution, monetisation or republishing as your own asset pack —
see [NOTICE.md](NOTICE.md). If you want this chassis for your own character, replace
`assets/clips/`, `assets/clips.json` and `assets/app.ico` with material you have the right to ship;
`src/petcore/clip_manifest.py` and `assets/text/lines.json` are the only places that name a character.

## License

Code: MIT — see [LICENSE](LICENSE). Assets: [NOTICE.md](NOTICE.md).
