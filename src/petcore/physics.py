"""Feet-anchored 2-D body: gravity, ground line, screen edges, throw velocity."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

GRAVITY = 1800.0          # px/s^2
THROW_SPEED_CAP = 2600.0  # px/s, keeps a fling from launching the pet off-screen
HARD_LAND_VY = 900.0      # px/s, above this the landing plays the flustered clip and costs mood


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True)
class Sample:
    x: float
    y: float
    t: float


@dataclass
class Body:
    x: float          # feet, screen coordinates (y grows downwards)
    y: float          # feet
    vx: float = 0.0
    vy: float = 0.0
    on_ground: bool = True


@dataclass(frozen=True)
class StepResult:
    body: Body
    landed: bool
    hard_landing: bool
    hit_wall: bool


def step(body: Body, dt: float, floor_y: float, bounds: Rect) -> StepResult:
    """Integrate one tick. The floor is the taskbar top edge, not the screen bottom."""
    if dt <= 0:
        return StepResult(body, False, False, False)
    # A body resting on the floor must not accumulate gravity, otherwise every tick would
    # report a "landing" and the pet would twitch on the taskbar.
    vy = body.vy + (0.0 if body.on_ground else GRAVITY * dt)
    x = body.x + body.vx * dt
    y = body.y + vy * dt
    hit_wall = False
    if x < bounds.left:
        x, hit_wall = bounds.left, True
    elif x > bounds.right:
        x, hit_wall = bounds.right, True
    landed = False
    hard = False
    if y >= floor_y:
        hard = (not body.on_ground) and vy > HARD_LAND_VY
        landed = (not body.on_ground) and vy > 1.0
        y = floor_y
        vy = 0.0
        vx = 0.0
        on_ground = True
    else:
        on_ground = False
    new = replace(body, x=x, y=y, vx=body.vx if not on_ground and not landed else 0.0,
                  vy=vy, on_ground=on_ground)
    return StepResult(new, landed, hard, hit_wall)


def throw_velocity(samples: list[Sample], cap: float = THROW_SPEED_CAP) -> tuple[float, float]:
    """Differentiate the last <=8 drag samples; the release velocity is what makes a throw feel real."""
    pts = [s for s in samples if s.t > 0]
    if len(pts) < 2:
        return 0.0, 0.0
    a, b = pts[-2], pts[-1]
    if b.t - a.t > 0.12:  # the pointer sat still before release -> a drop, not a throw
        return 0.0, 0.0
    span = b.t - pts[max(0, len(pts) - 8)].t
    if span <= 0:
        return 0.0, 0.0
    first = pts[max(0, len(pts) - 8)]
    vx = (b.x - first.x) / span
    vy = (b.y - first.y) / span
    mag = math.hypot(vx, vy)
    if mag > cap:
        k = cap / mag
        vx, vy = vx * k, vy * k
    return vx, vy


def clamp_into_screen(body: Body, bounds: Rect, floor_y: float) -> Body:
    """Used after a resolution/DPI change or a monitor unplug."""
    x = min(max(body.x, bounds.left), bounds.right)
    y = min(body.y, floor_y)
    return replace(body, x=x, y=y, on_ground=y >= floor_y)
