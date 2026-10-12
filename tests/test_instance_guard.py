"""The single-instance guard, across two interpreters.

Ownership cannot be proven inside one process: the question is whether a *different* process already
holds the right to run, and the mechanism that answers it (a named mutex) is released by the kernel
when a process dies. So the child is a real second interpreter, hard-killed when needed.
"""

import os
import pathlib
import subprocess
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from petapp.instance import InstanceGuard

pytest.importorskip("PySide6")

NAME = "DesktopPetGuardProbe"
CHILD = pathlib.Path(__file__).resolve().parent / "guard_child.py"


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv[:1])


def _start_holder(seconds: int = 25):
    child = subprocess.Popen(
        [sys.executable, str(CHILD), NAME, str(seconds)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    verdict, seen = "", []
    for _ in range(8):
        verdict = (child.stdout.readline() or "").strip()
        seen.append(verdict)
        if verdict in ("ACQUIRED", "DENIED"):
            break
    assert verdict == "ACQUIRED", f"holder said {verdict!r} (lines so far: {seen})"
    return child


def test_second_process_defers_to_the_holder(app):
    child = _start_holder()
    try:
        time.sleep(0.4)
        probe = InstanceGuard(NAME)
        assert probe.acquire() is False, "second process claimed primary while a live one held the name"
        assert probe.server is None, "a denied process must not own the control channel"
        assert probe.mutex == 0, "a denied process must not keep a mutex handle"
    finally:
        child.terminate()
        child.wait(timeout=10)


def test_a_hard_killed_holder_does_not_block_the_next_launch(app):
    """taskkill leaves the Qt pipe registration behind, but the kernel takes the mutex back.

    This is the case that made the pipe do double duty: a corpse that still accepts connections read
    as "live primary" to a socket probe, so the next launch refused to run or two pets came up at once.
    """
    child = _start_holder(60)
    child.terminate()
    child.wait(timeout=10)
    time.sleep(0.3)

    probe = InstanceGuard(NAME)
    try:
        assert probe.acquire() is True, "a dead holder must not keep the name"
        assert probe.server is not None, "the new primary should own a working control channel"
    finally:
        probe.close()
