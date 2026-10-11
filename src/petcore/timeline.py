"""Frame advancement for a single clip.

``MAX_CATCH_UP`` mirrors ``Assets/FengChuanXiangFrames/Runtime/FengFrameSequencer.cs:55``: a
pet window gets frozen by Windows (fullscreen apps, sleep, dragging another window) and must not
then jump dozens of frames at once when it wakes up.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from petcore.clips import ClipSpec

MAX_CATCH_UP = 0.15


@dataclass
class Timeline:
    spec: ClipSpec
    speed: float = 1.0
    _t: float = field(default=0.0, init=False)

    def switch(self, spec: ClipSpec, speed: float = 1.0) -> None:
        self.spec = spec
        self.speed = speed
        self._t = 0.0

    def restart(self) -> None:
        self._t = 0.0

    def advance(self, dt: float) -> int:
        """Advance by ``dt`` seconds (clamped) and return the frame index to show."""
        if dt > MAX_CATCH_UP:
            dt = MAX_CATCH_UP
        if dt < 0:
            dt = 0.0
        self._t += dt * self.speed
        return self.frame

    @property
    def frame(self) -> int:
        n = self.spec.frames
        if n <= 0:
            return 0
        idx = int(self._t * self.spec.fps)
        if self.spec.loop_mode == "loop":
            return idx % n
        return min(idx, n - 1)

    @property
    def finished(self) -> bool:
        return self.spec.loop_mode != "loop" and self._t * self.spec.fps >= self.spec.frames - 1

    @property
    def elapsed(self) -> float:
        return self._t

    @property
    def progress(self) -> float:
        d = self.spec.duration
        return 0.0 if d <= 0 else min(1.0, self._t / d)
