import json
import time

import pytest
from petapp import store
from petapp.store import SaveState, Settings, load_settings, load_state, save_settings, save_state
from petcore.stats import Stats


def test_round_trip(tmp_path):
    s = Settings(scale_index=2, click_through=True, sedentary_min=60)
    save_settings(s, tmp_path)
    assert load_settings(tmp_path) == s


def test_state_round_trip_keeps_position_and_stats(tmp_path):
    st = SaveState(stats=Stats(satiety=42, mood=66, affection=9), x=120.5, y=980.0,
                   saved_at=time.time(), last_day="2026-10-11")
    save_state(st, tmp_path, now=st.saved_at)
    got, elapsed = load_state(tmp_path, now=st.saved_at + 5)
    assert elapsed == pytest.approx(5)
    assert got.x == 120.5 and got.y == 980.0
    assert got.stats.satiety == 42 and got.stats.affection == 9
    assert got.last_day == "2026-10-11"


def test_corrupt_file_is_quarantined_not_deleted(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{not json", encoding="utf-8")
    assert load_settings(tmp_path) == Settings()
    quarantined = [f.name for f in tmp_path.iterdir() if ".bad-" in f.name]
    assert len(quarantined) == 1


def test_unknown_keys_are_dropped(tmp_path):
    (tmp_path / "settings.json").write_text(
        json.dumps({"schema": 1, "scale_index": 2, "made_up": 7}), encoding="utf-8")
    got = load_settings(tmp_path)
    assert got.scale_index == 2 and not hasattr(got, "made_up")


def test_state_with_wrong_schema_starts_fresh(tmp_path):
    (tmp_path / "state.json").write_text(json.dumps({"schema": 99, "x": 5}), encoding="utf-8")
    st, elapsed = load_state(tmp_path)
    assert st.x == 0.0 and elapsed == 0.0


def test_missing_state_reports_zero_elapsed(tmp_path):
    st, elapsed = load_state(tmp_path)
    assert elapsed == 0.0 and st.stats == Stats()


def test_write_is_atomic_and_utf8(tmp_path):
    save_state(SaveState(stats=Stats(mood=50), x=1.0, y=2.0), tmp_path, now=100.0)
    raw = (tmp_path / "state.json").read_text(encoding="utf-8")
    assert "stats" in raw
    assert not list(tmp_path.glob("*.tmp"))


def test_data_dir_uses_appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert store.data_dir() == tmp_path / store.APP_DIRNAME
