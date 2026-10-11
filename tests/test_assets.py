"""Task 6: the shipped frame pack must match what clips.json promises."""

import concurrent.futures as cf
import hashlib
import json
import pathlib

import pytest
from PIL import Image
from petcore import clip_manifest as cm
from petcore.clips import ClipCatalog

Image.MAX_IMAGE_PIXELS = None
PROJECT = pathlib.Path(__file__).resolve().parents[1]
ASSETS = PROJECT / "assets"
CLIPS_JSON = ASSETS / "clips.json"
BUDGET_BYTES = 130 * 1024 * 1024
ALPHA_THRESHOLD = 10

needs_pack = pytest.mark.skipif(not CLIPS_JSON.exists(), reason="run tools/build_clips.py first")


@pytest.fixture(scope="module")
def cat():
    return ClipCatalog.load(CLIPS_JSON)


@pytest.fixture(scope="module")
def src_root():
    """Where the 1024^2 originals came from, as recorded by the builder."""
    data = json.loads(CLIPS_JSON.read_text(encoding="utf-8"))
    root = pathlib.Path(data["sourceFramesRoot"])
    if not root.exists():
        pytest.skip(f"source frames absent: {root}")
    return root


@needs_pack
def test_manifest_matches_the_pack(cat):
    assert cat.internal_height == 480
    assert cat.crop_box == (219, 33, 818, 997)
    assert len(cat.clips) == 17
    assert set(cat.clips) == {c.slug for c in cm.CLIPS}
    data = json.loads(CLIPS_JSON.read_text(encoding="utf-8"))
    assert data["frameTotal"] == 2166
    assert sum(c["frames"] for c in data["clips"]) == data["frameTotal"]
    assert 0 < data["bytesTotal"] < BUDGET_BYTES


@needs_pack
def test_every_declared_frame_is_on_disk(cat):
    for slug, spec in cat.clips.items():
        files = sorted((spec.dir).glob("*.webp"))
        assert len(files) == spec.frames, f"{slug}: {len(files)} != {spec.frames}"
        assert [f.name for f in files] == [f"{i:03d}.webp" for i in range(spec.frames)]


def _check_one(args):
    src, box = args
    with Image.open(src) as im:
        a = im.getchannel("A")
        bb = a.point(lambda v: 255 if v > ALPHA_THRESHOLD else 0).getbbox()
    if bb is None:
        return str(src), None
    return str(src), (bb[0] >= box[0], bb[1] >= box[1], bb[2] <= box[2], bb[3] <= box[3])


@needs_pack
def test_every_frame_fits_the_crop_box(cat, src_root):
    """Per frame, not just the first: sakiko_angry01 leans 33 px outside the old sampled box."""
    work = [(src_root / slug / f"{i:04d}.png", cat.crop_box)
            for slug, spec in cat.clips.items() for i in range(spec.frames)]
    assert len(work) == 2166
    bad = []
    with cf.ProcessPoolExecutor(max_workers=8) as pool:
        for path, flags in pool.map(_check_one, work, chunksize=32):
            if flags is None or not all(flags):
                bad.append(path)
    assert not bad, f"{len(bad)} frames stick out of cropBox, e.g. {bad[:3]}"


@needs_pack
def test_idle_loop_seam_is_invisible(cat, src_root):
    """Regression for the measured 0.035 mean-abs difference between first and last frame."""
    from PIL import ImageChops, ImageStat
    d = src_root / cm.IDLE
    n = cat.get(cm.IDLE).frames
    with Image.open(d / "0000.png") as a, Image.open(d / f"{n - 1:04d}.png") as b:
        stat = ImageStat.Stat(ImageChops.difference(a.convert("RGB"), b.convert("RGB")))
    assert sum(stat.mean) / 3 < 1.0


@needs_pack
def test_source_index_hash_still_points_at_the_same_index(cat, src_root):
    index = src_root.parent.parent / "unity_index.json"
    assert hashlib.sha256(index.read_bytes()).hexdigest() == cat.source_index_sha256


@needs_pack
def test_labels_are_readable_chinese(cat):
    assert cat.get(cm.IDLE).label == "\u5f85\u673a"          # 待机
    assert all(c.label and c.kind for c in cat.clips.values())
