"""Shared fixtures: a synthetic catalog so behaviour tests never read the real frame pack."""

from __future__ import annotations

import json
import pathlib

import pytest
from petcore import clip_manifest as cm
from petcore.clips import ClipCatalog


def build_catalog(tmp: pathlib.Path, frames: int = 30, fps: int = 30) -> ClipCatalog:
    payload = {
        "character": cm.CHARACTER,
        "sourceIndexSha256": "00" * 32,
        "internalHeight": 480,
        "cropBox": [219, 33, 818, 997],
        "anchor": {"ax": 149.0, "ay": 476.0},
        "fps": fps,
        "clips": [
            {"slug": c.slug, "label": c.label, "kind": c.kind, "loop_mode": c.loop_mode,
             "pools": list(c.pools), "frames": frames, "fps": fps, "bytes": 0}
            for c in cm.CLIPS
        ],
    }
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "clips.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return ClipCatalog.load(tmp / "clips.json")


@pytest.fixture
def catalog(tmp_path) -> ClipCatalog:
    return build_catalog(tmp_path / "assets")
