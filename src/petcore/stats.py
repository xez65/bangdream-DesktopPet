"""Satiety / mood / affection, their decay, and the save-file shape."""

from __future__ import annotations

from dataclasses import dataclass, replace

SATIETY_DECAY_PER_MIN = 5 / 30
MOOD_DECAY_PER_MIN = 3 / 60
OFFLINE_CAP_SECONDS = 12 * 3600
HUNGRY_BELOW = 30
SAD_BELOW = 30

SCHEMA = 1


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


@dataclass(frozen=True)
class Stats:
    satiety: float = 70.0
    mood: float = 70.0
    affection: float = 0.0
    saved_at: float = 0.0
    last_day: str = ""

    def decayed(self, elapsed_seconds: float) -> "Stats":
        """Offline catch-up is capped so a weekend away does not zero everything out."""
        secs = max(0.0, min(elapsed_seconds, OFFLINE_CAP_SECONDS))
        mins = secs / 60
        return replace(
            self,
            satiety=_clamp(self.satiety - SATIETY_DECAY_PER_MIN * mins),
            mood=_clamp(self.mood - MOOD_DECAY_PER_MIN * mins),
        )

    @property
    def hungry(self) -> bool:
        return self.satiety < HUNGRY_BELOW

    @property
    def sad(self) -> bool:
        return self.mood < SAD_BELOW

    def is_happy(self) -> bool:
        return self.mood >= 60 and self.satiety >= 40


# (satiety, mood, affection) deltas per interaction, from spec section 7.
DELTAS = {
    "poke": (0.0, 2.0, 0.0),
    "poke_annoyed": (0.0, -2.0, 0.0),
    "pet": (0.0, 6.0, 1.0),
    "thrown": (0.0, -4.0, 0.0),
    "chime": (0.0, 0.5, 0.0),
    "pomodoro_done": (0.0, 5.0, 0.0),
    "new_day": (0.0, 0.0, 5.0),
}
FOODS = {
    "tea": (15.0, 4.0, 3.0),
    "coffee": (12.0, 6.0, 3.0),
    "dessert": (25.0, 8.0, 3.0),
    "bento": (30.0, 5.0, 3.0),
}


def apply_delta(stats: Stats, key: str, amount: float | None = None) -> Stats:
    ds, dm, da = DELTAS[key]
    if amount is not None:
        ds, dm, da = amount
    return replace(
        stats,
        satiety=_clamp(stats.satiety + ds),
        mood=_clamp(stats.mood + dm),
        affection=_clamp(stats.affection + da),
    )


def feed(stats: Stats, food: str) -> Stats:
    ds, dm, da = FOODS[food]
    return replace(
        stats,
        satiety=_clamp(stats.satiety + ds),
        mood=_clamp(stats.mood + dm),
        affection=_clamp(stats.affection + da),
    )


def to_dict(s: Stats) -> dict:
    return {"schema": SCHEMA, "satiety": s.satiety, "mood": s.mood,
            "affection": s.affection, "saved_at": s.saved_at, "last_day": s.last_day}


def from_dict(d: dict) -> Stats:
    if int(d.get("schema", 0)) != SCHEMA:
        raise ValueError(f"unsupported save schema {d.get('schema')!r}")
    return Stats(
        satiety=_clamp(float(d["satiety"])),
        mood=_clamp(float(d["mood"])),
        affection=_clamp(float(d["affection"])),
        saved_at=float(d.get("saved_at", 0.0)),
        last_day=str(d.get("last_day", "")),
    )
