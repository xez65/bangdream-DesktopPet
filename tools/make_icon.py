"""Turn the chosen artwork into a Windows .ico, keeping the watermark border out.

Source is 2642x1555 RGBA but fully opaque, with a light-grey frame the measured row/column
means put at y<47, y>=1388, x<50, x>=2600. The photo area is therefore about 2550x1341, so the
largest usable square is ~1335 on a side. Candidates are written next to the .ico so the choice
can be revisited after the fact.
"""

from __future__ import annotations

import argparse
import pathlib

from PIL import Image

DEFAULT_SOURCE = pathlib.Path(r"C:/Users/Administrator/Pictures/NevernessToEverness") / "26_09_27_13_43_30.png"
PHOTO = (50, 47, 2600, 1388)          # inside the watermark frame, measured
ICO_SIZES = (256, 128, 64, 48, 32)
SIDE = PHOTO[3] - PHOTO[1]            # 1341 -> clamp to 1335 below
SIDE = min(SIDE, 1335)


def candidates(source: Image.Image) -> dict[str, tuple[int, int, int, int]]:
    """Two horizontal choices; the crop always spans the full photo height, so the moon and the
    city are in every variant and a vertical shift is not possible."""
    px = source.width
    centre_subject = 1400             # the two figures sit right of centre (vision probe)
    mid = (PHOTO[0] + PHOTO[2]) // 2
    out = {}
    for name, cx in (("subject", centre_subject), ("centred", mid)):
        x0 = min(max(cx - SIDE // 2, PHOTO[0]), PHOTO[2] - SIDE)
        out[name] = (x0, PHOTO[1], x0 + SIDE, PHOTO[1] + SIDE)
    return out


def build(source_path: pathlib.Path, out_dir: pathlib.Path, which: str = "subject") -> pathlib.Path:
    src = Image.open(source_path).convert("RGBA")
    boxes = candidates(src)
    if which not in boxes:
        raise SystemExit(f"unknown crop {which!r}; pick one of {sorted(boxes)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, box in boxes.items():
        src.crop(box).resize((256, 256), Image.LANCZOS).save(out_dir / f"icon_candidate_{name}.png")
    img = src.crop(boxes[which]).resize((256, 256), Image.LANCZOS)
    ico = out_dir / "app.ico"
    img.save(ico, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    for size in ICO_SIZES:
        img.resize((size, size), Image.LANCZOS).save(out_dir / f"app_{size}.png")
    print(f"icon from {source_path.name} crop={boxes[which]} sizes={list(ICO_SIZES)} -> {ico}")
    return ico


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=pathlib.Path, default=DEFAULT_SOURCE)
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1] / "assets")
    ap.add_argument("--crop", default="subject", choices=("subject", "centred"))
    args = ap.parse_args(argv)
    if not args.source.exists():
        raise SystemExit(f"source artwork missing: {args.source}")
    build(args.source, args.out, args.crop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
