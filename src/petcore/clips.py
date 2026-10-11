"""Read-only view over the generated clip pack (`assets/clips.json`)."""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

FALLBACK_SLUG = "sakiko_idle01"


@dataclass(frozen=True)
class ClipSpec:
    slug: str
    label: str
    kind: str
    frames: int
    fps: int
    loop_mode: str
    dir: pathlib.Path

    @property
    def duration(self) -> float:
        return self.frames / self.fps


class ClipCatalogError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClipCatalog:
    internal_height: int
    crop_box: tuple[int, int, int, int]
    anchor_x: float
    anchor_y: float
    fps: int
    clips: dict
    source_index_sha256: str
    root: pathlib.Path

    @staticmethod
    def load(path: pathlib.Path) -> "ClipCatalog":
        p = pathlib.Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        root = p.parent
        clips = {}
        for entry in data["clips"]:
            clips[entry["slug"]] = ClipSpec(
                slug=entry["slug"],
                label=entry.get("label", entry["slug"]),
                kind=entry["kind"],
                frames=int(entry["frames"]),
                fps=int(entry["fps"]),
                loop_mode=entry["loop_mode"],
                dir=root / "clips" / entry["slug"],
            )
        if not clips:
            raise ClipCatalogError("clips.json lists no clips")
        box = tuple(int(v) for v in data["cropBox"])
        anchor = data["anchor"]
        return ClipCatalog(
            internal_height=int(data["internalHeight"]),
            crop_box=box,
            anchor_x=float(anchor["ax"]),
            anchor_y=float(anchor["ay"]),
            fps=int(data["fps"]),
            clips=clips,
            source_index_sha256=data.get("sourceIndexSha256", ""),
            root=root,
        )

    def get(self, slug: str) -> ClipSpec | None:
        return self.clips.get(slug)

    def usable(self) -> dict:
        return {s: c for s, c in self.clips.items() if s != FALLBACK_SLUG and c.frames > 0}

    def frame_path(self, slug: str, frame: int) -> pathlib.Path:
        spec = self.clips[slug]
        return spec.dir / f"{frame % spec.frames:03d}.webp"

    def report(self) -> str:
        return (
            f"clips={len(self.clips)} frames={sum(c.frames for c in self.clips.values())} "
            f"h={self.internal_height} box={self.crop_box} anchor=({self.anchor_x:.1f},{self.anchor_y:.1f}) "
            f"src={self.source_index_sha256[:12]}"
        )
