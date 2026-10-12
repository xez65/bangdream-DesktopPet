"""Scaffold guard: the two-layer split is the project's central constraint, so it is tested."""

import ast
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BANNED_TOP_LEVELS = {"PySide6", "PyQt5", "PyQt6", "PIL", "tkinter", "ctypes", "win32gui", "win32api"}


def test_both_packages_import():
    import petapp
    import petcore

    assert petcore.__name__ == "petcore"
    assert petapp.__name__ == "petapp"


def test_petcore_imports_nothing_gui_or_platform():
    offenders = []
    for path in sorted((ROOT / "src" / "petcore").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in BANNED_TOP_LEVELS:
                        offenders.append(f"{path.name}:{node.lineno}:{alias.name}")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in BANNED_TOP_LEVELS:
                    offenders.append(f"{path.name}:{node.lineno}:{node.module}")
    assert offenders == [], f"petcore must stay Qt/PIL/win32 free: {offenders}"


def test_qt_available_offscreen():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    assert (QApplication.instance() or QApplication([])) is not None


def test_ship_name_and_display_name_are_the_same_string():
    """Two literals held the product name, and a half-applied rename shipped a stale exe once.
    tools/build_exe.py only runs PyInstaller under __main__, so importing it here is side-effect free.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import build_exe
    from petapp.tray import APP_NAME

    assert build_exe.SHIP_NAME == APP_NAME, (build_exe.SHIP_NAME, APP_NAME)
    assert APP_NAME == "\u4e30\u5ddd\u7965\u5b50\u684c\u5ba0\u6a21\u62df\u5668", repr(APP_NAME)


def test_python_runtime_is_inside_the_project_venv():
    exe = pathlib.Path(sys.executable).resolve()
    assert ROOT in exe.parents, exe
    assert ".venv" in exe.parts, exe
    out = subprocess.run(
        [sys.executable, "-c", "import PySide6, PIL; print(PySide6.__version__)"],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0 and out.stdout.strip(), out.stderr
