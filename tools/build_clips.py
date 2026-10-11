"""Build the runtime frame pack from the pre-baked sequence frames in this repository.

    python tools/build_clips.py --dry-run     # frames + projected bytes, writes nothing
    python tools/build_clips.py --jobs 8      # real build

Source of truth for what exists is ``unity_index.json``; source of truth for what the pet
*uses* it for is ``clip_manifest.py``. Coordinates follow the repo convention in
``凤川祥/_bake/stats.mjs``: alpha threshold ``a > 10`` and **inclusive** box corners, which is
one pixel wider than Pillow's ``getbbox()``.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import pathlib
import shutil
import sys
import time

import PIL
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# 凤川祥, built from code points so this file stays ASCII-only (repo convention).
FENG_DIR = "\u51e4\u5ddd\u7965"
HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parent
REPO = PROJECT.parent
SRC_ROOT = REPO / FENG_DIR / "_bake" / "out" / "frames" / "batch"
INDEX_PATH = REPO / FENG_DIR / "_bake" / "out" / "unity_index.json"
ASSET_DIR = PROJECT / "assets"
DEV_DIR = PROJECT / "dev"
CHECKPOINT = DEV_DIR / "build_checkpoint.json"

sys.path.insert(0, str(PROJECT / "src"))
from petcore import clip_manifest  # noqa: E402  (path set up just above)

ALPHA_THRESHOLD = 10
PAD = 8
CANVAS = 1024
BUDGET_BYTES = 130 * 1024 * 1024
FPS = 30


def log(msg: str) -> None:
    print(msg, flush=True)


def source_frames() -> dict[str, int]:
    data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    by_slug = {g["slug"]: int(g["frames"]) for g in data["motionGroups"]}
    missing = [c.slug for c in clip_manifest.CLIPS if c.slug not in by_slug]
    if missing:
        raise SystemExit(f"clips absent from unity_index.json: {missing}")
    empty = [c.slug for c in clip_manifest.CLIPS
             if not (SRC_ROOT / c.slug / "0000.png").exists()]
    if empty:
        raise SystemExit(f"clip frame dirs missing on disk: {empty}")
    return by_slug


def index_sha256() -> str:
    return hashlib.sha256(INDEX_PATH.read_bytes()).hexdigest()


def config_fingerprint(crop_box, height, quality, method) -> dict:
    return {
        "cropBox": list(crop_box),
        "internalHeight": height,
        "quality": quality,
        "method": method,
        "pad": PAD,
        "alphaThreshold": ALPHA_THRESHOLD,
        "sourceIndexSha256": index_sha256(),
        "pillow": PIL.__version__,
        "builderVersion": "1",
    }


def _scan_one(args):
    """Alpha box for one frame, in the repo's convention: threshold a>10, inclusive corners.

    Thresholding then handing the mask to Pillow's C getbbox() is both faster and simpler than
    scanning pixels in Python; Pillow returns an exclusive box, so the far corners come back
    one pixel.
    """
    slug, idx = args
    path = SRC_ROOT / slug / f"{idx:04d}.png"
    a = Image.open(path).getchannel("A")
    mask = a.point(lambda v: 255 if v > ALPHA_THRESHOLD else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return slug, (0, 0, -1, -1), False
    x0, y0, x1, y1 = bbox[0], bbox[1], bbox[2] - 1, bbox[3] - 1
    edge = x0 <= 1 or y0 <= 1 or x1 >= CANVAS - 2 or y1 >= CANVAS - 2
    return slug, (x0, y0, x1, y1), edge


def scan_union(slugs, jobs) -> tuple[tuple, int]:
    """Full scan of every frame: union box (inclusive corners) + edge-touching count."""
    work = [(s, i) for s in slugs for i in range(source_frames()[s])]
    union = None
    edge = 0
    done = 0
    t0 = time.perf_counter()
    with cf.ProcessPoolExecutor(max_workers=jobs) as pool:
        for _slug, box, is_edge in pool.map(_scan_one, work, chunksize=32):
            union = box if union is None else (
                min(union[0], box[0]), min(union[1], box[1]),
                max(union[2], box[2]), max(union[3], box[3]))
            edge += int(is_edge)
            done += 1
            if done % 2000 == 0:
                log(f"  scanned {done}/{len(work)} union={union} edge={edge}")
    log(f"  scanned {done}/{len(work)} in {time.perf_counter() - t0:.1f}s -> union={union} edge={edge}")
    return union, edge


def make_crop_box(union) -> tuple:
    cx0 = max(0, union[0] - PAD)
    cy0 = max(0, union[1] - PAD)
    cx1 = min(CANVAS, union[2] + 1 + PAD)
    cy1 = min(CANVAS, union[3] + 1 + PAD)
    return (cx0, cy0, cx1, cy1)


def make_anchor(union, crop_box, height) -> tuple:
    scale = height / (crop_box[3] - crop_box[1])
    ax = ((union[0] + union[2]) / 2 - crop_box[0]) * scale
    ay = (union[3] + 1 - crop_box[1]) * scale
    return round(ax, 2), round(ay, 2)


def target_width(crop_box, height) -> int:
    w, h = crop_box[2] - crop_box[0], crop_box[3] - crop_box[1]
    return round(w * height / h)


def _encode_one(args):
    slug, idx, crop_box, height, quality, method, out_root = args
    src = SRC_ROOT / slug / f"{idx:04d}.png"
    im = Image.open(src).convert("RGBA").crop(crop_box)
    im = im.resize((target_width(crop_box, height), height), Image.LANCZOS)
    dst = pathlib.Path(out_root) / slug / f"{idx:03d}.webp"
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".webp.tmp")
    im.save(tmp, "WEBP", quality=quality, method=method)
    size = tmp.stat().st_size
    tmp.replace(dst)
    return slug, idx, size


def dry_run(slugs, crop_box, height, quality, method, per_clip=5) -> dict:
    frames = source_frames()
    probe = DEV_DIR / "_probe"
    shutil.rmtree(probe, ignore_errors=True)
    probe.mkdir(parents=True, exist_ok=True)
    report = {}
    for slug in slugs:
        n = frames[slug]
        picks = sorted({0, n // 4, n // 2, (3 * n) // 4, n - 1})[:per_clip]
        sizes = [_encode_one((slug, i, crop_box, height, quality, method, probe))[2] for i in picks]
        avg = sum(sizes) / len(sizes)
        report[slug] = {"frames": n, "meanBytes": round(avg), "projectedBytes": round(avg * n)}
        log(f"  {slug:26s} frames={n:4d} mean={avg / 1024:5.1f} KB -> {avg * n / 1048576:5.1f} MB")
    shutil.rmtree(probe, ignore_errors=True)
    return report


def load_checkpoint(fp) -> dict:
    if CHECKPOINT.exists():
        try:
            old = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"config": fp, "clips": {}}
        if old.get("config") == fp:
            return old
        log("  checkpoint config changed -> full rebuild")
    return {"config": fp, "clips": {}}


def build(slugs, crop_box, height, quality, method, jobs, force) -> tuple[dict, int]:
    frames = source_frames()
    fp = config_fingerprint(crop_box, height, quality, method)
    ck = load_checkpoint(fp)
    if force:
        ck["clips"] = {}
    out_root = ASSET_DIR / "clips"
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / ".gitkeep").write_text("", encoding="utf-8")
    per_clip: dict[str, dict] = {}
    skipped = 0
    failures: list[str] = []
    t0 = time.perf_counter()
    for slug in slugs:
        n = frames[slug]
        dst_dir = out_root / slug
        done = ck["clips"].get(slug, {})
        if done.get("status") == "done" and len(list(dst_dir.glob("*.webp"))) == n:
            per_clip[slug] = {"frames": n, "bytes": done["bytes"]}
            skipped += 1
            continue
        dst_dir.mkdir(parents=True, exist_ok=True)
        work = [(slug, i, crop_box, height, quality, method, out_root) for i in range(n)]
        total = 0
        try:
            if jobs > 1:
                with cf.ProcessPoolExecutor(max_workers=jobs) as pool:
                    for _s, _i, size in pool.map(_encode_one, work, chunksize=8):
                        total += size
            else:
                for item in work:
                    total += _encode_one(item)[2]
        except Exception as exc:  # a single bad clip must not void the whole pack
            failures.append(slug)
            log(f"  FAILED {slug}: {type(exc).__name__}: {exc}")
            ck["clips"][slug] = {"status": "failed", "framesDone": 0, "bytes": 0}
            continue
        ck["clips"][slug] = {"status": "done", "framesDone": n, "bytes": total}
        per_clip[slug] = {"frames": n, "bytes": total}
        log(f"  built {slug:26s} frames={n:4d} bytes={total / 1048576:5.2f} MB")
    DEV_DIR.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(json.dumps(ck, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8", newline="\n")
    log(f"  {len(slugs) - skipped - len(failures)} built, {skipped} reused, {len(failures)} failed "
        f"in {time.perf_counter() - t0:.1f}s")
    if clip_manifest.FALLBACK_SLUG in failures or not per_clip.get(clip_manifest.FALLBACK_SLUG):
        raise SystemExit("fallback clip sakiko_idle01 is not usable -> abort")
    return per_clip, skipped


def write_manifest(slugs, per_clip, crop_box, height, anchor, quality, method) -> int:
    frames = source_frames()
    by = clip_manifest.by_slug()
    total = 0
    entries = []
    for slug in sorted(slugs):
        c = by[slug]
        b = per_clip[slug]["bytes"]
        total += b
        entries.append({
            "slug": slug, "label": c.label, "kind": c.kind, "loop_mode": c.loop_mode,
            "pools": list(c.pools), "frames": frames[slug], "fps": FPS, "bytes": b,
        })
    payload = {
        "character": clip_manifest.CHARACTER,
        "sourceIndexSha256": index_sha256(),
        "sourceFramesRoot": str(SRC_ROOT),
        "internalHeight": height,
        "cropBox": list(crop_box),
        "anchor": {"ax": anchor[0], "ay": anchor[1]},
        "fps": FPS,
        "webp": {"quality": quality, "method": method, "alphaThreshold": ALPHA_THRESHOLD, "pad": PAD},
        "pillow": PIL.__version__,
        "builderVersion": "1",
        "frameTotal": sum(frames[s] for s in slugs),
        "bytesTotal": total,
        "clips": entries,
    }
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    (ASSET_DIR / "clips.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return total


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--quality", type=int, default=82)
    ap.add_argument("--method", type=int, default=4, help="WebP method 0-6; 6 costs ~90x time for ~1 KB")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--out-dir", default=None, help="override assets dir (determinism reruns)")
    args = ap.parse_args(argv)

    global ASSET_DIR
    if args.out_dir:
        ASSET_DIR = pathlib.Path(args.out_dir)

    slugs = [c.slug for c in clip_manifest.CLIPS]
    DEV_DIR.mkdir(parents=True, exist_ok=True)
    log(f"clips={len(slugs)} frames={sum(source_frames()[s] for s in slugs)} jobs={args.jobs}")

    log("PASS1 alpha union (a>10, inclusive corners)")
    union, edge = scan_union(slugs, args.jobs)
    crop_box = make_crop_box(union)
    anchor = make_anchor(union, crop_box, args.height)
    log(f"  union={union} cropBox={crop_box} "
        f"size={crop_box[2] - crop_box[0]}x{crop_box[3] - crop_box[1]} edgeFrames={edge}")
    log(f"  internal={target_width(crop_box, args.height)}x{args.height} anchor=({anchor[0]}, {anchor[1]})")

    if args.dry_run:
        log("PASS2 dry-run byte projection")
        rep = dry_run(slugs, crop_box, args.height, args.quality, args.method)
        projected = sum(v["projectedBytes"] for v in rep.values())
        log(f"  projected {projected / 1048576:.1f} MB (budget {BUDGET_BYTES / 1048576:.0f} MB)")
        if projected > BUDGET_BYTES:
            log("  BUDGET EXCEEDED -> would degrade: loop window, then fps 20, then height")
        return 0

    log("PASS2 encode")
    per_clip, _skipped = build(slugs, crop_box, args.height, args.quality, args.method, args.jobs, args.force)
    total = write_manifest(slugs, per_clip, crop_box, args.height, anchor, args.quality, args.method)
    log(f"  clips.json written, bytesTotal={total / 1048576:.1f} MB")
    if total > BUDGET_BYTES:
        log("  BUDGET EXCEEDED after build -> rerun with --height 440 or trim loop windows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
