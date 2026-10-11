"""Task 3 acceptance: the clip manifest is consistent with the baked index, and the
catalog reader round-trips a clips.json."""

import json
import pathlib
import sys

import pytest
from petcore import clip_manifest
from petcore import clips as clipsmod

# 凤川祥 in the repo root; built from code points so this source file stays pure ASCII.
FENG_DIR = "\u51e4\u5ddd\u7965"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
INDEX_PATH = REPO_ROOT / FENG_DIR / "_bake" / "out" / "unity_index.json"


def _index():
    if not INDEX_PATH.exists():
        pytest.skip(f"source index not present: {INDEX_PATH}")
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def test_manifest_shape():
    assert len(clip_manifest.CLIPS) == 17
    slugs = [c.slug for c in clip_manifest.CLIPS]
    assert len(set(slugs)) == len(slugs), "duplicate slug in manifest"
    assert clip_manifest.FALLBACK_SLUG in slugs
    for c in clip_manifest.CLIPS:
        assert c.slug.startswith(clip_manifest.CHARACTER + "_"), c.slug
        assert c.loop_mode in ("loop", "once"), c
        assert c.label and c.kind


def test_manifest_frames_total_matches_measurement():
    expected = _expected_frames()
    assert sum(expected[c.slug] for c in clip_manifest.CLIPS) == 2166


def _expected_frames():
    data = _index()
    return {g["slug"]: int(g["frames"]) for g in data["motionGroups"]}


def test_every_clip_exists_in_unity_index_with_same_frames():
    expected = _expected_frames()
    for c in clip_manifest.CLIPS:
        assert c.slug in expected, f"{c.slug} not a motionGroup in unity_index.json"


def test_pools_and_bindings_reference_known_slugs():
    known = {c.slug for c in clip_manifest.CLIPS}
    for name in ("idle", "walk", "small", "low"):
        assert clip_manifest.pool(name), f"pool {name} is empty"
        assert set(clip_manifest.pool(name)) <= known
    for attr in ("POKED", "POKED_ANNOYED", "PET", "FEED", "THROWN",
                 "CHIME", "SEDENTARY", "QUIET", "LOW_STATS"):
        bound = getattr(clip_manifest, attr)
        assert bound and set(bound) <= known, attr
    for named in ("IDLE", "HELD", "LAND", "WALK_LEFT", "WALK_RIGHT"):
        assert getattr(clip_manifest, named) in known, named
    assert set(clip_manifest.by_slug()) == known


def test_walk_clips_are_the_directional_pair():
    assert clip_manifest.by_slug()["sakiko_nf_left01"].kind == "walk_left"
    assert clip_manifest.by_slug()["sakiko_nf_right01"].kind == "walk_right"
    # spec 3.3: nf_* is a weight shift, not a stride -> the pet glides while playing it
    for slug in ("sakiko_nf_left01", "sakiko_nf_right01"):
        assert clip_manifest.by_slug()[slug].loop_mode == "loop"


def test_catalog_round_trip(tmp_path):
    frames = _expected_frames()
    payload = {
        "sourceIndexSha256": "ab" * 32,
        "internalHeight": 480,
        "cropBox": [219, 33, 818, 997],
        "anchor": {"ax": 149.5, "ay": 456.0},
        "fps": 30,
        "clips": [
            {"slug": c.slug, "label": c.label, "kind": c.kind, "frames": frames[c.slug],
             "fps": 30, "loop_mode": c.loop_mode}
            for c in clip_manifest.CLIPS
        ],
    }
    p = tmp_path / "clips.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    cat = clipsmod.ClipCatalog.load(p)
    assert len(cat.clips) == 17
    assert cat.get("sakiko_idle01").frames == frames["sakiko_idle01"] == 210
    assert cat.crop_box == (219, 33, 818, 997)
    assert cat.internal_height == 480
    assert abs(cat.anchor_y - 456.0) < 1e-6
    spec = cat.get("sakiko_idle01")
    assert spec.duration == pytest.approx(spec.frames / 30)
    assert cat.frame_path("sakiko_idle01", 999).name == f"{999 % spec.frames:03d}.webp"
    assert cat.usable().keys() == {c.slug for c in clip_manifest.CLIPS} - {clip_manifest.FALLBACK_SLUG}
    assert "clips=17" in cat.report()


def test_catalog_rejects_empty(tmp_path):
    p = tmp_path / "clips.json"
    p.write_text(json.dumps({"internalHeight": 480, "cropBox": [0, 0, 1, 1], "anchor": {"ax": 0, "ay": 0},
                             "fps": 30, "clips": []}), encoding="utf-8")
    with pytest.raises(clipsmod.ClipCatalogError):
        clipsmod.ClipCatalog.load(p)
