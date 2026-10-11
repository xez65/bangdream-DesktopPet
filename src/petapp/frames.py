"""Decode + cache clip frames. The only module where PIL and Qt meet.

Frames are decoded from WebP, premultiplied by hand (``ImageChops.multiply`` is exactly
``a*b/255``, which is what premultiplication is), then scaled once to the current display size
and cached as a QPixmap. Scaling on decode rather than on paint keeps the 30 fps tick cheap.
"""

from __future__ import annotations

import io
import pathlib

from PIL import Image, ImageChops
from PySide6.QtGui import QImage, QPixmap
from petcore.clips import ClipCatalog
from petcore.lru import LruCache

CACHE_BYTES = 120 * 1024 * 1024


def _premultiply(im: Image.Image) -> Image.Image:
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    r, g, b, a = im.split()
    return Image.merge("RGBA", (ImageChops.multiply(r, a), ImageChops.multiply(g, a),
                                ImageChops.multiply(b, a), a))


class FrameStore:
    def __init__(self, catalog: ClipCatalog, max_bytes: int = CACHE_BYTES):
        self.catalog = catalog
        self.target_h = catalog.internal_height
        self._cache = LruCache(capacity=400, max_bytes=max_bytes, weigh=self._weigh)
        self._failures: list[str] = []

    @staticmethod
    def _weigh(pm: QPixmap) -> int:
        return pm.width() * pm.height() * 4

    def set_target_height(self, height: int) -> None:
        if height != self.target_h:
            self.target_h = height
            self._cache = LruCache(capacity=400, max_bytes=self._cache.max_bytes, weigh=self._weigh)

    def _source_path(self, slug: str, frame: int) -> pathlib.Path:
        spec = self.catalog.get(slug)
        return spec.dir / f"{frame % spec.frames:03d}.webp"

    def pixmap(self, slug: str, frame: int) -> QPixmap | None:
        key = (slug, frame, self.target_h)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        path = self._source_path(slug, frame)
        try:
            im = Image.open(io.BytesIO(path.read_bytes()))
            im.load()
        except (OSError, ValueError) as exc:
            if self._cache.note_failure((slug, frame)):
                self._failures.append(f"{path.name}: {type(exc).__name__}")
            return None
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        w, h = im.size
        if h != self.target_h:
            im = im.resize((max(1, round(w * self.target_h / h)), self.target_h), Image.LANCZOS)
        img = _premultiply(im)
        q = QImage(img.tobytes(), img.width, img.height, QImage.Format_RGBA8888_Premultiplied)
        pm = QPixmap.fromImage(q.copy())
        self._cache.put(key, pm)
        return pm

    def report(self) -> str:
        return f"target_h={self.target_h} cache[{self._cache.report()}] failures={self._failures[:3]}"
