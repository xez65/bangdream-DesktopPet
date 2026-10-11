"""Performance sampling without psutil (not installed here, and adding it would bloat the exe).

CPU comes from ``GetProcessTimes`` deltas, memory from ``K32GetProcessMemoryInfo``, and the
frame-tick distribution from the app's own ring buffer over the dev control channel.

    .venv\\Scripts\\python.exe tools\\measure_perf.py --seconds 30
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import pathlib
import subprocess
import sys
import time
from ctypes import wintypes

PROJECT = pathlib.Path(__file__).resolve().parents[1]
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_QUERY_INFORMATION = 0x0400
FILETIME = ctypes.c_uint64


class _Cnt(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def _handles(pid: int):
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = wintypes.HANDLE
    # GetProcessTimes needs PROCESS_QUERY_INFORMATION; the LIMITED right is enough for the
    # working-set query but silently yields zero CPU times.
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        raise OSError(f"OpenProcess({pid}) failed")
    return h


def _cpu_times(h) -> tuple[int, int]:
    kernel32 = ctypes.windll.kernel32
    # Without argtypes ctypes passes the handle as a C int and the 64-bit HANDLE is truncated,
    # which makes GetProcessTimes "succeed" with all-zero times.
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(FILETIME),
                                         ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME),
                                         ctypes.POINTER(FILETIME)]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    creation, exit_, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
    if not kernel32.GetProcessTimes(h, ctypes.byref(creation), ctypes.byref(exit_),
                                    ctypes.byref(kernel), ctypes.byref(user)):
        raise OSError("GetProcessTimes failed")
    return kernel.value, user.value


def _rss_bytes(h) -> int:
    """K32GetProcessMemoryInfo lives in kernel32 on this box; psapi only has the old name."""
    kernel32 = ctypes.windll.kernel32
    cnt = _Cnt()
    cnt.cb = ctypes.sizeof(cnt)
    fn = getattr(kernel32, "K32GetProcessMemoryInfo", None)
    if fn is not None and fn(h, ctypes.byref(cnt), cnt.cb):
        return int(cnt.WorkingSetSize)
    try:
        psapi = ctypes.windll.psapi
        cnt.cb = ctypes.sizeof(cnt)
        if psapi.GetProcessMemoryInfo(h, ctypes.byref(cnt), cnt.cb):
            return int(cnt.WorkingSetSize)
    except (AttributeError, OSError):
        pass
    raise OSError("no working-set API available")


def sample(pid: int, seconds: float, interval: float = 1.0) -> dict:
    h = _handles(pid)
    k0, u0 = _cpu_times(h)
    t0 = time.perf_counter()
    rss: list[int] = []
    for _ in range(max(1, int(seconds / interval))):
        time.sleep(interval)
        rss.append(_rss_bytes(h))
    k1, u1 = _cpu_times(h)
    wall_100ns = (time.perf_counter() - t0) * 1e7
    cpu_pct = ((k1 - k0) + (u1 - u0)) / wall_100ns * 100.0
    return {"cpu_percent": round(cpu_pct, 2), "rss_bytes_max": max(rss), "rss_samples_mb": [
        round(x / 1048576, 1) for x in rss], "sampled_seconds": round(time.perf_counter() - t0, 1)}


EXE_NAME = "\u51e4\u5ddd\u7965\u6a21\u62df\u5668.exe"     # built from code points, never argv


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--exe", action="store_true", help="measure the packaged exe instead of the sources")
    ap.add_argument("--python", default=str(PROJECT / ".venv" / "Scripts" / "python.exe"))
    ap.add_argument("--out", type=pathlib.Path, default=PROJECT / "dev")
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["DESKTOPPET_DEV"] = "1"
    env["DESKTOPPET_DEV_DIR"] = str(args.out)
    if args.exe:
        exe = PROJECT / "dist" / EXE_NAME
        if not exe.exists():
            raise SystemExit(f"missing {exe}")
        target = [str(exe)]
    else:
        target = [args.python, str(PROJECT / "run.py")]
    proc = subprocess.Popen(target, env=env)
    time.sleep(3.0)
    sys.path.insert(0, str(PROJECT / "src"))
    from petapp.instance import send_command
    result = {"target": target, "launcher_pid": proc.pid, "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    # The launcher pid is not necessarily the pid that renders: measure the process that
    # answers the control channel, otherwise CPU reads 0% against an idle stub.
    reply = send_command("DesktopPetSakiko", "pid")
    app_pid = None
    if "pid" in reply:
        try:
            app_pid = int(reply.split("pid")[1].split()[0])
        except (IndexError, ValueError):
            app_pid = None
    result["pid_reply"] = reply
    result["pid"] = app_pid or proc.pid
    try:
        result.update(sample(result["pid"], args.seconds))
        result["app_ticks"] = send_command("DesktopPetSakiko", "perf")
    finally:
        send_ok = False
        try:
            send_command("DesktopPetSakiko", "quit")
            send_ok = True
        except Exception:
            pass
        if proc.poll() is None and not send_ok:
            proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    result["exitCode"] = proc.poll()
    result["gates"] = {
        "cpu_le_5": result["cpu_percent"] <= 5.0,
        "rss_le_350mb": result["rss_bytes_max"] <= 350 * 1048576,
    }
    path = args.out / f"perf-{time.strftime('%Y%m%d-%H%M')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
