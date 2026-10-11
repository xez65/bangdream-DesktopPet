"""Entry point: ``python run.py [--smoke|--once]``."""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
import time
from datetime import date

from petcore import clip_manifest as cm

PROJECT = pathlib.Path(__file__).resolve().parents[2]
AUTOSAVE_SECONDS = 30.0


def asset_root() -> pathlib.Path:
    """A onefile build unpacks next to its data, not next to the source tree."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return pathlib.Path(bundle) / "assets"
    return PROJECT / "assets"


def dev_dir() -> pathlib.Path:
    """Where evidence PNGs go. Frozen builds have no writable project dir, so honour the env."""
    override = os.environ.get("DESKTOPPET_DEV_DIR")
    out = pathlib.Path(override) if override else (
        pathlib.Path(os.environ.get("TEMP", str(pathlib.Path.home()))) / "DesktopPetShots")
    out.mkdir(parents=True, exist_ok=True)
    return out


def load_catalog():
    from petcore.clips import ClipCatalog
    path = asset_root() / "clips.json"
    if not path.exists():
        raise SystemExit(f"missing {path} - run tools/build_clips.py first")
    return ClipCatalog.load(path)


def _apply_offline(state, elapsed: float):
    """Catch up decay, and credit one affection bump per new calendar day."""
    from petcore.stats import apply_delta
    stats = state.stats.decayed(elapsed)
    today = date.today().isoformat()
    bumped = False
    if state.last_day and state.last_day != today:
        stats = apply_delta(stats, "new_day")
        bumped = True
    return stats, today, bumped


def smoke(app, catalog) -> int:
    from petapp.frames import FrameStore
    store = FrameStore(catalog)
    store.set_target_height(120)
    checked, bad = 0, []
    for slug, spec in catalog.clips.items():
        for frame in range(min(5, spec.frames)):
            pm = store.pixmap(slug, frame)
            checked += 1
            if pm is None or pm.isNull() or pm.width() <= 0:
                bad.append(f"{slug}#{frame}")
    print(f"SMOKE clips={len(catalog.clips)} frames={checked} bad={len(bad)} | {store.report()}")
    if bad:
        print("  first bad:", bad[:5])
    return 0 if not bad else 1


def once(app, catalog, seed) -> int:
    from PIL import Image, ImageGrab
    from petapp.window import PetWindow
    win = PetWindow(catalog, seed=seed)
    win.show()
    win.start()
    deadline = time.perf_counter() + 2.5
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.02)
    DEV = dev_dir()
    win.grab().save(str(DEV / "once_window.png"))
    scr = app.primaryScreen()
    dpr = float(scr.devicePixelRatio())
    origin = scr.geometry().topLeft()
    g = win.geometry()
    box = (int((g.x() - origin.x()) * dpr), int((g.y() - origin.y()) * dpr),
           int((g.x() - origin.x() + g.width()) * dpr), int((g.y() - origin.y() + g.height()) * dpr))
    shot = ImageGrab.grab(bbox=box, all_screens=False)
    shot.save(DEV / "once_desktop.png")
    w, h = min(shot.width, 220), min(shot.height, 220)
    shot.crop((0, 0, w, h)).resize((w * 3, h * 3), Image.NEAREST).save(DEV / "once_edge_zoom.png")
    p95 = sorted(win.tick_ms)[max(0, int(len(win.tick_ms) * 0.95) - 1)] if win.tick_ms else 0.0
    print(f"ONCE rect={box} dpr={dpr} ticks={len(win.tick_ms)} p95={p95:.2f}ms")
    print(f"ONCE {win.store.report()}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="petapp")
    ap.add_argument("--smoke", action="store_true", help="decode frames headlessly and exit")
    ap.add_argument("--once", action="store_true", help="show briefly, write evidence PNGs, exit")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args(argv)

    if args.smoke:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("DesktopPetSakiko")
    catalog = load_catalog()
    if args.smoke:
        return smoke(app, catalog)
    if args.once:
        return once(app, catalog, args.seed)

    from petapp import store as store_mod
    from petapp import tray as tray_mod
    from petapp.instance import InstanceGuard
    from petapp.lines import Lines
    from petapp.window import PetWindow

    guard = InstanceGuard()
    if not guard.acquire():
        print("another 凤川祥模拟器 is already running; this instance exits")
        return 0
    app.aboutToQuit.connect(guard.close)
    dev_mode = os.environ.get("DESKTOPPET_DEV") == "1"

    settings = store_mod.load_settings()
    saved, elapsed = store_mod.load_state()
    stats, today, bumped = _apply_offline(saved, elapsed)
    saved.stats, saved.last_day = stats, today
    win = PetWindow(catalog, settings=settings, state=saved,
                    lines=Lines.load(asset_root() / "text" / "lines.json"),
                    seed=args.seed, on_save=_make_saver(store_mod))
    win.tray = tray_mod.build_tray(win)
    if bumped:
        win.show_bubble("startup")
    win.show()
    win.start()

    autosave = _Autosaver(win, AUTOSAVE_SECONDS)
    app.aboutToQuit.connect(lambda: win.save())
    timer = _Ticker(autosave)
    timer.start()
    if dev_mode:
        guard.attach(_dev_handler(win, app))
    return app.exec()


def _self_cpu_percent() -> str:
    """Lifetime CPU share of this very process, so the number cannot be misattributed to a
    launcher stub. Both sides come from the OS clock, so no wall-clock guess is involved."""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        FT = ctypes.c_uint64
        creation, exit_, kernel, user, now = FT(), FT(), FT(), FT(), FT()
        current = ctypes.c_void_p(-1)
        if not kernel32.GetProcessTimes(current, ctypes.byref(creation), ctypes.byref(exit_),
                                        ctypes.byref(kernel), ctypes.byref(user)):
            return "unavailable"
        kernel32.GetSystemTimeAsFileTime(ctypes.byref(now))
        lifetime = (now.value - creation.value) / 1e7
        used = (kernel.value + user.value) / 1e7
        if lifetime <= 0:
            return "n/a"
        return f"{used / lifetime * 100:.2f}"
    except Exception as exc:
        return f"error {type(exc).__name__}"


def _capture_scenes(win, arg: str, app) -> str:
    """Render each scene into the widget's own bitmap.

    This deliberately does not grab the desktop: a locked or dimmed session returns black
    frames and can suspend the process, which would make the evidence worthless. ``QWidget.grab``
    goes through Qt's raster paint, so it records what the pet actually draws.
    """
    import json

    scenes = (
        ("01_idle", None, None),
        ("02_clip_smile", "clip", "sakiko_smile01"),
        ("03_clip_angry", "clip", "sakiko_angry01"),
        ("04_clip_thinking", "clip", "sakiko_thinking01"),
        ("05_clip_bye", "clip", "sakiko_bye01"),
        ("06_clip_surprised", "clip", "sakiko_surprised01"),
        ("07_bubble", "bubble", "poked"),
        ("08_feed", "feed", "dessert"),
        ("09_quiet", "pomodoro_start", None),
        ("10_stats_panel", "stats_panel", "on"),
        ("11_scale_300", "scale", "300"),
        ("12_scale_150", "scale", "150"),
    )
    out = dev_dir()
    manifest = {"scenes": [], "dpr": float(win._dpr()),
                "idle_frames": win.catalog.get(cm.IDLE).frames}

    def apply(verb, value):
        if verb == "clip":
            win.play_clip(value)
        elif verb == "bubble":
            win.show_bubble(value)
        elif verb == "feed":
            win.feed(value)
        elif verb == "pomodoro_start":
            win.start_pomodoro()
        elif verb == "stats_panel":
            win.set_show_stats(value == "on")
        elif verb == "scale":
            win.set_scale(int(value))

    for name, verb, value in scenes:
        if verb:
            apply(verb, value)
        for _ in range(12):
            app.processEvents()
            time.sleep(0.02)
        path = out / f"{name}.png"
        win.grab().save(str(path))
        manifest["scenes"].append({"scene": name, "file": path.name,
                                   "slug": win.timeline.spec.slug,
                                   "frame": win.timeline.frame,
                                   "window": [win.width(), win.height()]})
    (out / "scenes_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return f"OK shots {len(manifest['scenes'])} -> {out}"


def _dev_handler(win, app):
    """Text commands used by tools/accept_shots.py. Only installed when DESKTOPPET_DEV=1."""

    def handle(command: str) -> str:
        parts = command.split()
        if not parts:
            return "ERR empty"
        verb, arg = parts[0], (parts[1] if len(parts) > 1 else "")
        if verb == "clip" and win.play_clip(arg):
            return f"OK clip {arg}"
        if verb == "walk_left":
            win.core.push("wall")
            win.core.state = "walk"
            win.core.walk_dir = -1
            win.core._play(win.core._walk_slug())
            return "OK walk_left"
        if verb == "walk_right":
            win.core.push("wall")
            win.core.state = "walk"
            win.core.walk_dir = 1
            win.core._play(win.core._walk_slug())
            return "OK walk_right"
        if verb == "bubble":
            win.show_bubble(arg or "poked")
            return f"OK bubble {arg}"
        if verb == "feed":
            win.feed(arg or "tea")
            return f"OK feed {arg}"
        if verb == "pet":
            win.pet_now()
            return "OK pet"
        if verb == "poke":
            win.poke()
            return "OK poke"
        if verb == "pomodoro_start":
            win.start_pomodoro()
            return "OK pomodoro_start"
        if verb == "pomodoro_stop":
            win.stop_pomodoro()
            return "OK pomodoro_stop"
        if verb == "stats_panel":
            win.set_show_stats(arg == "on")
            return f"OK stats_panel {arg}"
        if verb == "scale":
            win.set_scale(int(arg or 220))
            return f"OK scale {arg}"
        if verb == "shots":
            return _capture_scenes(win, arg, app)
        if verb == "current":
            return (f"OK current {win.timeline.spec.slug} frame={win.timeline.frame} "
                    f"state={win.core.state} pinned={win.core.pinned}")
        if verb == "resume":
            win.resume_autonomy()
            return "OK resume"
        if verb == "pid":
            return f"OK pid {os.getpid()} parent {os.getppid()}"
        if verb == "perf":
            s = sorted(win.tick_ms)
            p95 = s[max(0, int(len(s) * 0.95) - 1)] if s else 0.0
            cpu = _self_cpu_percent()
            return (f"OK perf ticks={len(s)} p95_ms={p95:.2f} "
                    f"max_ms={s[-1] if s else 0:.2f} self_cpu_percent={cpu}")
        if verb == "quit":
            app.quit()
            return "OK quit"
        return f"ERR unknown {verb}"

    return handle


def _make_saver(store_mod):
    def save(state, settings) -> None:
        store_mod.save_state(state)
        store_mod.save_settings(settings)
    return save


class _Autosaver:
    def __init__(self, win, every: float):
        self.win = win
        self.every = every
        self._t = time.perf_counter()

    def tick(self) -> None:
        if time.perf_counter() - self._t >= self.every:
            self._t = time.perf_counter()
            self.win.save()


class _Ticker:
    """Keeps autosave alive without blocking the Qt loop."""

    def __init__(self, saver: _Autosaver):
        from PySide6.QtCore import QTimer
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(saver.tick)

    def start(self) -> None:
        self.timer.start()


if __name__ == "__main__":
    sys.exit(main())
