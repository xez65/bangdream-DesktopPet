"""Build the single-file exe, rename it to the shipping name, and prove the rename works.

    .venv\\Scripts\\python.exe tools\\build_exe.py            # build only
    .venv\\Scripts\\python.exe tools\\build_exe.py --launch    # + cold-start proof
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

PROJECT = pathlib.Path(__file__).resolve().parents[1]
ENTRY = PROJECT / "tools" / "_exe_entry.py"
ASSETS = PROJECT / "assets"
DIST = PROJECT / "dist"
BUILD = PROJECT / "build"
ASCII_NAME = "DesktopPetSakiko"
# 丰川祥子桌宠模拟器. 祥 is U+7965, as in FengFrameLibrary.cs:116-118; the first character is
# 丰 U+4E30, not the 凤 U+51E4 that opens the bake folder name. tests/test_scaffold.py pins this
# to petapp.tray.APP_NAME so a rename cannot half-land the way it did on 2026-10-11.
SHIP_NAME = "\u4e30\u5ddd\u7965\u5b50\u684c\u5ba0\u6a21\u62df\u5668"

EXCLUDES = (
    "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQml", "PySide6.QtNetworkAuth",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtPositioning",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSensors", "PySide6.QtSerialPort",
    "PySide6.QtSql", "PySide6.QtSvgWidgets", "PySide6.QtTest", "PySide6.QtTextToSpeech",
    "PySide6.QtUiTools", "PySide6.QtXml",
)


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "-C", str(PROJECT.parent), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=20)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def build_exe(extra_args=()) -> pathlib.Path:
    pyinstaller = pathlib.Path(sys.executable).with_name("pyinstaller.exe")
    if not pyinstaller.exists():
        pyinstaller = pathlib.Path(sys.executable).with_name("pyinstaller")
    cmd = [
        str(pyinstaller), "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", ASCII_NAME,
        "--icon", str(ASSETS / "app.ico"),
        "--add-data", f"{ASSETS}{os.pathsep}assets",
        "--paths", str(PROJECT / "src"),
        *[f"--exclude-module={m}" for m in EXCLUDES],
        *extra_args,
        str(ENTRY),
    ]
    print("pyinstaller:", " ".join(cmd[:8]), "...", flush=True)
    t0 = time.perf_counter()
    res = subprocess.run(cmd, cwd=str(PROJECT), capture_output=True, text=True)
    print(f"pyinstaller rc={res.returncode} in {time.perf_counter() - t0:.0f}s")
    tail = (res.stdout or "")[-1500:] + (res.stderr or "")[-1500:]
    (PROJECT / "dev").mkdir(exist_ok=True)
    (PROJECT / "dev" / "pyinstaller.log").write_text(tail, encoding="utf-8", errors="replace")
    produced = DIST / f"{ASCII_NAME}.exe"
    if res.returncode != 0 or not produced.exists():
        raise SystemExit(f"build failed; see dev/pyinstaller.log\n{tail[-800:]}")
    return produced


def rename(exe: pathlib.Path) -> pathlib.Path:
    target = exe.with_name(f"{SHIP_NAME}.exe")
    if target.exists():
        target.unlink()
    exe.rename(target)
    return target


def cold_start(exe: pathlib.Path) -> dict:
    """Run the renamed exe from a clean temp dir with Python stripped from PATH.

    ``--once`` shows the pet for a moment, writes an evidence PNG and exits, which makes the
    whole thing measurable without a manual click.
    """
    run_dir = pathlib.Path(os.environ.get("TEMP", ".")) / "desktoppet_coldstart"
    shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)
    copy = run_dir / exe.name
    shutil.copy2(exe, copy)
    env = dict(os.environ)
    env["PATH"] = ";".join(p for p in env.get("PATH", "").split(";")
                           if p and "python" not in p.lower() and "desktoppet" not in p.lower())
    env["DESKTOPPET_DEV_DIR"] = str(run_dir)
    t0 = time.perf_counter()
    proc = subprocess.run([str(copy), "--once"], env=env, cwd=str(run_dir),
                          capture_output=True, text=True, timeout=90)
    elapsed = time.perf_counter() - t0
    shots = sorted(p.name for p in run_dir.glob("*.png"))
    return {"exe": exe.name, "python_left_on_path": any("python" in p.lower() for p in env["PATH"].split(";")),
            "exitCode": proc.returncode, "seconds": round(elapsed, 2),
            "stdout": (proc.stdout or "").strip()[-400:],
            "stderr": (proc.stderr or "").strip()[-400:], "shots": shots}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--launch", action="store_true", help="also cold-start the renamed exe")
    ap.add_argument("--extra", nargs="*", default=[])
    args = ap.parse_args(argv)

    exe = build_exe(args.extra)
    shipped = rename(exe)
    info = {
        "exe": shipped.name,
        "exeBytes": shipped.stat().st_size,
        "exeSha256": sha256(shipped),
        "assetFrames": sum(len(list(p.glob("*.webp"))) for p in (ASSETS / "clips").iterdir() if p.is_dir()),
        "assetBytes": sum(f.stat().st_size for f in (ASSETS / "clips").rglob("*.webp")),
        "clipsManifestSha256": sha256(ASSETS / "clips.json"),
        "sourceIndexSha256": json.loads((ASSETS / "clips.json").read_text(encoding="utf-8"))["sourceIndexSha256"],
        "gitCommit": git_commit(),
        "builtAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pyinstaller": "onefile",
    }
    if args.launch:
        info["coldStart"] = cold_start(shipped)
    (DIST / "BUILD_INFO.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8", newline="\n")
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
