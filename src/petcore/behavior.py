"""Behaviour state machine (spec section 6.2). Pure logic, seeded RNG, no Qt and no PIL."""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random

from petcore import clip_manifest as cm
from petcore.clips import ClipCatalog
from petcore.stats import Stats

IDLE_MIN, IDLE_MAX = 8.0, 20.0
WALK_MIN, WALK_MAX = 3.0, 8.0
WALK_SPEED = 40.0                 # px/s along the taskbar top edge
SLEEP_SPEED = 0.5
POKE_ANNOY_AFTER = 3
POKE_STREAK_WINDOW = 2.0
IDLE_BEFORE_SLEEP_BIAS = 300.0

STATE_IDLE = "idle"
STATE_WALK = "walk"
STATE_CARRIED = "carried"
STATE_FALL = "fall"
STATE_REACT = "react"
STATE_SLEEP = "sleep"
STATE_QUIET = "quiet"
STATE_MANUAL = "manual"          # the user asked for this clip; do not second-guess it
BLOCKING = (STATE_CARRIED, STATE_FALL)


@dataclass(frozen=True)
class WorldCtx:
    stats: Stats
    idle_seconds: float = 0.0
    quiet: bool = False


@dataclass(frozen=True)
class Decision:
    slug: str
    speed: float
    bubble_key: str | None
    walk_dir: int
    state: str


@dataclass
class BehaviorCore:
    catalog: ClipCatalog
    seed: int | None = None
    state: str = field(default=STATE_IDLE, init=False)
    slug: str = field(default="", init=False)
    speed: float = field(default=1.0, init=False)
    walk_dir: int = field(default=0, init=False)
    bubble_key: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.rng = Random(self.seed)
        self._timer = 0.0
        self._clip_elapsed = 0.0
        self._poke_streak = 0
        self._poke_age = 0.0
        self._pending_bubble: str | None = None
        self._pinned = False
        self._pinned_slug = cm.IDLE
        fallback = self.catalog.get(cm.IDLE)
        if fallback is None:
            raise ValueError(f"catalog has no {cm.IDLE}")
        self._spec = fallback
        self.slug = fallback.slug
        self._timer = self.rng.uniform(IDLE_MIN, IDLE_MAX)

    # ---------------------------------------------------------------- helpers
    def _available(self, slug: str) -> bool:
        spec = self.catalog.get(slug)
        return spec is not None and spec.frames > 0

    def _pick(self, slugs) -> str:
        ok = [s for s in slugs if self._available(s)]
        return self.rng.choice(ok) if ok else cm.IDLE

    def _play(self, slug: str, speed: float = 1.0) -> None:
        spec = self.catalog.get(slug)
        if spec is None:
            return
        self._spec = spec
        self.slug = spec.slug
        self.speed = speed
        self._clip_elapsed = 0.0

    def _walk_slug(self) -> str:
        return cm.WALK_RIGHT if self.walk_dir >= 0 else cm.WALK_LEFT

    def _react(self, slug: str, bubble: str | None, priority: str = "behaviour",
               releases_pin: bool = False) -> bool:
        if self.state in BLOCKING or not self._available(slug):
            return False
        if priority == "behaviour" and self.state in (STATE_REACT, STATE_QUIET):
            return False
        self.state = STATE_REACT
        self._play(slug)
        self._pending_bubble = bubble
        if releases_pin:
            # the user did something *to* the pet; its own routine comes back
            self._pinned = False
            self._pinned_slug = cm.IDLE
        return True

    # ---------------------------------------------------------------- events
    def request(self, slug: str, priority: str = "behaviour") -> bool:
        """A clip the user asked for by hand.

        It is pinned, not queued as a reaction: a loop clip keeps playing until the user does
        something else, and a one-shot falls back to a pinned idle rather than straight back to
        the random machine. Without this, picking 待机 in the menu lasts exactly one cycle
        (7 s) before the dice can send the pet off walking.
        """
        spec = self.catalog.get(slug)
        if self.state in BLOCKING or spec is None or spec.frames <= 0:
            return False
        if priority == "behaviour" and self.state in (STATE_REACT, STATE_QUIET, STATE_MANUAL):
            return False
        self.state = STATE_MANUAL
        self._pinned = True
        self._pinned_slug = slug
        self.walk_dir = 0
        self._play(slug)
        return True

    def resume_autonomy(self) -> None:
        """Hand control back to the random machine, starting from a fresh idle window."""
        self._pinned = False
        self._pinned_slug = cm.IDLE
        self.state = STATE_IDLE
        self._play(cm.IDLE)
        self._timer = self.rng.uniform(IDLE_MIN, IDLE_MAX)

    @property
    def pinned(self) -> bool:
        return self._pinned

    def push(self, kind: str, **payload) -> bool:
        if kind == "grab":
            self.state = STATE_CARRIED
            self._pinned = False
            self._pinned_slug = cm.IDLE
            self.walk_dir = 0
            self._play(cm.HELD)
            return True
        if kind == "release":
            self.state = STATE_FALL
            return True
        if kind == "landed":
            self.state = STATE_IDLE
            self.walk_dir = 0
            self._play(cm.IDLE)
            self._timer = self.rng.uniform(IDLE_MIN, IDLE_MAX)
            if payload.get("hard"):
                return self._react(cm.LAND, "thrown", priority="reminder")
            return True
        if kind == "poke":
            self._poke_streak = self._poke_streak + 1 if self._poke_age < POKE_STREAK_WINDOW else 1
            self._poke_age = 0.0
            if self._poke_streak >= POKE_ANNOY_AFTER:
                return self._react(self._pick(cm.POKED_ANNOYED), None, priority="reminder", releases_pin=True)
            return self._react(self._pick(cm.POKED), "poked", priority="reminder", releases_pin=True)
        if kind == "pet":
            self._poke_streak = 0
            return self._react(self._pick(cm.PET), "poked", priority="reminder", releases_pin=True)
        if kind == "feed":
            self._poke_streak = 0
            return self._react(self._pick(cm.FEED), None, priority="reminder", releases_pin=True)
        if kind == "chime":
            key = "hungry" if payload.get("hungry") else "hour_chime"
            return self._react(cm.CHIME[0], key, priority="reminder")
        if kind == "sedentary":
            return self._react(cm.SEDENTARY[0], "sedentary", priority="reminder")
        if kind == "pomodoro_start":
            self.state = STATE_QUIET
            self._pinned = False
            self._pinned_slug = cm.IDLE
            self._play(self._pick(cm.QUIET))
            self._timer = self.rng.uniform(IDLE_MIN, IDLE_MAX)
            return True
        if kind == "pomodoro_stop":
            self.state = STATE_IDLE
            self.walk_dir = 0
            self._timer = self.rng.uniform(IDLE_MIN, IDLE_MAX)
            return True
        if kind == "pomodoro_done":
            self.state = STATE_IDLE
            self._pending_bubble = "pomodoro_done"
            self._timer = self.rng.uniform(IDLE_MIN, IDLE_MAX)
            return True
        if kind == "wall":
            self.walk_dir = -self.walk_dir if self.walk_dir else 1
            if self.state == STATE_WALK:
                self._play(self._walk_slug())
            return True
        if kind == "activity":
            self._poke_streak = 0
            if self.state == STATE_SLEEP:
                self.state = STATE_IDLE
                self._play(cm.IDLE)
                self._timer = self.rng.uniform(IDLE_MIN, IDLE_MAX)
            return True
        if kind == "startup":
            self._pending_bubble = "startup"
            return True
        return False

    # ---------------------------------------------------------------- ticking
    def _roll(self, ctx: WorldCtx) -> None:
        weights = {"idle": 50.0, "walk": 30.0, "small": 15.0, "sleep": 5.0}
        if ctx.idle_seconds > IDLE_BEFORE_SLEEP_BIAS:
            weights["sleep"] *= 2
            weights["idle"] -= 5
        if ctx.stats.hungry:
            weights["small"] += 5
            weights["walk"] -= 5
        pick = self.rng.choices(list(weights), weights=list(weights.values()), k=1)[0]
        if pick == "walk":
            self.state = STATE_WALK
            self.walk_dir = self.rng.choice((-1, 1))
            self._play(self._walk_slug())
            self._timer = self.rng.uniform(WALK_MIN, WALK_MAX)
        elif pick == "small":
            pool = cm.LOW_STATS if (ctx.stats.hungry or ctx.stats.sad) else cm.SMALL
            self.state = STATE_REACT
            self._play(self._pick(pool))
            self._timer = 0.0
        elif pick == "sleep":
            self.state = STATE_SLEEP
            self._play(cm.IDLE, SLEEP_SPEED)
            self._timer = self.rng.uniform(IDLE_MIN, IDLE_MAX)
        else:
            self.state = STATE_IDLE
            self._play(cm.IDLE)
            self._timer = self.rng.uniform(IDLE_MIN, IDLE_MAX)

    def tick(self, dt: float, ctx: WorldCtx) -> Decision:
        dt = max(0.0, dt)
        self._clip_elapsed += dt * self.speed
        self._poke_age += dt
        if self._poke_age >= POKE_STREAK_WINDOW:
            self._poke_streak = 0

        if ctx.quiet and self.state not in (STATE_QUIET, *BLOCKING):
            self._pinned = False
            self._pinned_slug = cm.IDLE
            self.state = STATE_QUIET
            self._play(self._pick(cm.QUIET))
            self._timer = self.rng.uniform(IDLE_MIN, IDLE_MAX)

        if self.state == STATE_MANUAL:
            spec = self._spec
            if spec.loop_mode != "loop" and self._clip_elapsed >= spec.duration:
                self._pinned_slug = cm.IDLE
                self._play(cm.IDLE)
        elif self.state in (STATE_IDLE, STATE_WALK, STATE_SLEEP, STATE_QUIET):
            self._timer -= dt
            if self._timer <= 0:
                if self.state == STATE_QUIET:
                    self._play(self._pick(cm.QUIET))
                    self._timer = self.rng.uniform(IDLE_MIN, IDLE_MAX)
                else:
                    self._roll(ctx)
        elif self.state == STATE_REACT:
            if self._clip_elapsed >= self._spec.duration:
                if self._pinned:
                    self.state = STATE_MANUAL
                    self._play(self._pinned_slug)
                else:
                    self.state = STATE_IDLE
                    self._play(cm.IDLE)
                    self._timer = self.rng.uniform(IDLE_MIN, IDLE_MAX)

        bubble, self._pending_bubble = self._pending_bubble, None
        return Decision(
            slug=self.slug,
            speed=self.speed,
            bubble_key=bubble,
            walk_dir=self.walk_dir if self.state == STATE_WALK else 0,
            state=self.state,
        )
