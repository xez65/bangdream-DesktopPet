"""Settings and save-file persistence under ``%APPDATA%\\DesktopPetSakiko``.

Writes go to a temp file and then ``os.replace`` so a crash mid-write cannot leave a
half-written JSON behind. An unreadable file is renamed ``.bad-<stamp>`` rather than deleted.
"""

from __future__ import annotations

import json
import os
import pathlib
import time
from dataclasses import asdict, dataclass, field, replace

from petcore import stats as statsmod
from petcore.stats import Stats

APP_DIRNAME = "DesktopPetSakiko"
SETTINGS_SCHEMA = 1
STATE_SCHEMA = 1


def data_dir() -> pathlib.Path:
    base = os.environ.get("APPDATA") or str(pathlib.Path.home())
    return pathlib.Path(base) / APP_DIRNAME


@dataclass
class Settings:
    schema: int = SETTINGS_SCHEMA
    scale_index: int = 1
    click_through: bool = False
    topmost: bool = True
    paused: bool = False
    chime_enabled: bool = True
    sedentary_enabled: bool = True
    sedentary_min: float = 45.0
    pomodoro_work_min: float = 25.0
    pomodoro_break_min: float = 5.0


@dataclass
class SaveState:
    schema: int = STATE_SCHEMA
    stats: Stats = field(default_factory=Stats)
    x: float = 0.0
    y: float = 0.0
    saved_at: float = 0.0
    last_day: str = ""


def _read(path: pathlib.Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        bad = path.with_name(f"{path.name}.bad-{time.strftime('%Y%m%d%H%M%S')}")
        try:
            path.replace(bad)
        except OSError:
            pass
        return None


def _write(path: pathlib.Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_settings(directory: pathlib.Path | None = None) -> Settings:
    d = _read((directory or data_dir()) / "settings.json") or {}
    known = {f for f in Settings.__dataclass_fields__}
    return Settings(**{k: v for k, v in d.items() if k in known})


def save_settings(s: Settings, directory: pathlib.Path | None = None) -> None:
    _write((directory or data_dir()) / "settings.json", asdict(s))


def load_state(directory: pathlib.Path | None = None, now: float | None = None) -> tuple[SaveState, float]:
    """Returns the state plus how many seconds elapsed since it was written (capped by Stats)."""
    d = _read((directory or data_dir()) / "state.json")
    now = time.time() if now is None else now
    if not d or int(d.get("schema", 0)) != STATE_SCHEMA:
        return SaveState(saved_at=now), 0.0
    try:
        raw = d.get("stats")
        stats = statsmod.from_dict(raw if isinstance(raw, dict) else d)
    except (KeyError, TypeError, ValueError):
        return SaveState(saved_at=now), 0.0
    saved_at = float(d.get("saved_at", 0.0)) or now
    elapsed = max(0.0, now - saved_at)
    state = SaveState(stats=stats, x=float(d.get("x", 0.0)), y=float(d.get("y", 0.0)),
                      saved_at=saved_at, last_day=str(d.get("last_day", "")))
    return state, elapsed


def save_state(state: SaveState, directory: pathlib.Path | None = None,
               now: float | None = None) -> None:
    now = time.time() if now is None else now
    payload = asdict(state)
    payload["saved_at"] = now
    payload["stats"] = statsmod.to_dict(state.stats)
    _write((directory or data_dir()) / "state.json", payload)


def with_position(state: SaveState, x: float, y: float, stats: Stats | None = None,
                  day: str | None = None) -> SaveState:
    return replace(state, x=x, y=y, stats=stats if stats is not None else state.stats,
                   last_day=day if day is not None else state.last_day)
