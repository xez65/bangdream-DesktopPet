"""Bubble text. The table lives in ``assets/text/lines.json`` so it can be edited without code."""

from __future__ import annotations

import json
import pathlib
import random

FALLBACK: dict[str, tuple[str, ...]] = {
    "hour_chime": ("\u5230\u70b9\u4e86\u3002",),
    "hungry": ("\u6709\u70b9\u997f\u4e86\u2026\u2026",),
    "poked": ("\u5657\uff1f",),
    "thrown": ("\u522b\u6254\u6211\u554a\uff01",),
    "sedentary": ("\u8d77\u6765\u52a8\u4e00\u52a8\u3002",),
    "pomodoro_done": ("\u4e00\u8f6e\u5b8c\u6210\u3002",),
    "startup": ("\u6211\u6765\u4e86\u3002",),
    "feed": ("\u8c22\u8c22\u3002",),
}

CATEGORIES = tuple(FALLBACK)


class Lines:
    def __init__(self, table: dict[str, list[str]]):
        self.table = {k: [str(x) for x in v if str(x).strip()] for k, v in table.items() if v}

    @staticmethod
    def load(path: pathlib.Path) -> "Lines":
        try:
            data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        merged = {k: list(data.get(k) or v) for k, v in FALLBACK.items()}
        for k, v in data.items():
            merged.setdefault(k, list(v))
        return Lines(merged)

    def pick(self, key: str, rng: random.Random | None = None) -> str:
        options = self.table.get(key) or FALLBACK.get(key) or ("",)
        return (rng or random).choice(list(options))

    def missing_categories(self) -> list[str]:
        return [k for k in CATEGORIES if not self.table.get(k)]
