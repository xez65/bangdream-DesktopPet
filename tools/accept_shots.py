"""Acceptance capture: drive the RUNNING pet and collect its own rendered bitmaps.

The pet is driven through the same ``QLocalServer`` channel that guards single-instance, so the
capture never reaches into the app's internals. Commands are only honoured when the process was
started with ``DESKTOPPET_DEV=1``.

    .venv\\Scripts\\python.exe tools\\accept_shots.py --out dev/shots-20261011

A desktop grab is attempted too, but it is only trusted when the frame is not uniform: a locked
or dimmed session yields a black screen and the process is suspended, which would otherwise
produce worthless "evidence" that looks like a pass.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

from build_exe import SHIP_NAME          # one shipping name, shared with the packager

PROJECT = pathlib.Path(__file__).resolve().parents[1]
EXE = PROJECT / "dist" / f"{SHIP_NAME}.exe"
RUN_SCRIPT = PROJECT / "run.py"


def _uniform(path: pathlib.Path) -> bool:
    from PIL import Image
    im = Image.open(path).convert("RGB").resize((64, 36))
    px = list(im.getdata())
    return len(set(px)) <= 3


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, default=PROJECT / "dev" / f"shots-{time.strftime('%Y%m%d-%H%M%S')}")
    ap.add_argument("--python", default=str(PROJECT / ".venv" / "Scripts" / "python.exe"))
    ap.add_argument("--exe", action="store_true", help="capture against the packaged exe instead of the sources")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(PROJECT / "src"))

    env = dict(os.environ)
    env["DESKTOPPET_DEV"] = "1"
    env["DESKTOPPET_DEV_DIR"] = str(args.out)
    target = [str(EXE)] if args.exe else [args.python, str(RUN_SCRIPT)]
    proc = subprocess.Popen(target, env=env)
    time.sleep(3.0)

    from petapp.instance import send_command
    manifest = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "target": target, "scenes": []}
    rc = 0
    try:
        reply = send_command("DesktopPetSakiko", "shots", timeout_ms=30000)
        print("shots reply:", reply)
        src = args.out / "scenes_manifest.json"
        if src.exists():
            manifest["scenes"] = json.loads(src.read_text(encoding="utf-8")).get("scenes", [])
        desktop = args.out / "desktop.png"
        from PIL import ImageGrab
        ImageGrab.grab(all_screens=True).save(desktop)
        manifest["desktop_capture"] = {"file": desktop.name, "uniform_black": _uniform(desktop)}
        if not manifest["scenes"]:
            rc = 1
    finally:
        send_command("DesktopPetSakiko", "quit")
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"captured {len(manifest['scenes'])} scenes -> {args.out}")
    print("desktop frame uniform (session locked?):", manifest["desktop_capture"]["uniform_black"])
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
