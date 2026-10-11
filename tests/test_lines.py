import json
import pathlib

from petapp.lines import CATEGORIES, Lines

REAL = pathlib.Path(__file__).resolve().parents[1] / "assets" / "text" / "lines.json"


def test_shipped_table_covers_every_category():
    assert REAL.exists(), "assets/text/lines.json must ship"
    lines = Lines.load(REAL)
    assert lines.missing_categories() == []
    for key in CATEGORIES:
        assert len(lines.table[key]) >= 3, key


def test_pick_is_stable_for_a_seeded_rng():
    import random
    lines = Lines.load(REAL)
    a = [lines.pick(k, random.Random(7)) for k in CATEGORIES]
    b = [lines.pick(k, random.Random(7)) for k in CATEGORIES]
    assert a == b and all(a)


def test_missing_file_falls_back(tmp_path):
    lines = Lines.load(tmp_path / "nope.json")
    assert lines.missing_categories() == []
    assert lines.pick("poked")


def test_empty_category_falls_back(tmp_path):
    p = tmp_path / "lines.json"
    p.write_text(json.dumps({"poked": []}), encoding="utf-8")
    lines = Lines.load(p)
    assert lines.pick("poked")
    assert lines.missing_categories() == []


def test_custom_lines_win(tmp_path):
    p = tmp_path / "lines.json"
    p.write_text(json.dumps({"poked": ["\u522b\u78b0\u6211"]}), encoding="utf-8")
    lines = Lines.load(p)
    assert lines.pick("poked") == "\u522b\u78b0\u6211"
