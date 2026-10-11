"""Wall-clock driven reminders: hour chime, sedentary nudge, pomodoro.

Every method takes its time from the caller so the tests can move the clock arbitrarily.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

POMODORO_WORK_MIN = 25
POMODORO_BREAK_MIN = 5
SEDENTARY_DEFAULT_MIN = 45
IDLE_BEFORE_SLEEP_SECONDS = 300


@dataclass
class HourChime:
    """Fires once per calendar hour, on the first tick that observes the new hour."""

    enabled: bool = True
    last_key: str = ""

    def tick(self, now: datetime) -> int | None:
        if not self.enabled:
            return None
        key = now.strftime("%Y-%m-%d-%H")
        if key == self.last_key:
            return None
        self.last_key = key
        return now.hour


@dataclass
class Sedentary:
    """Nags about sitting too long, but stays quiet when nobody is at the keyboard."""

    enabled: bool = True
    interval_min: float = SEDENTARY_DEFAULT_MIN
    elapsed: float = 0.0

    def tick(self, dt: float, idle_seconds: float) -> bool:
        if not self.enabled:
            return False
        if idle_seconds > IDLE_BEFORE_SLEEP_SECONDS:
            return False
        self.elapsed += max(0.0, dt)
        if self.elapsed >= self.interval_min * 60:
            self.elapsed = 0.0
            return True
        return False

    def reset(self) -> None:
        self.elapsed = 0.0


@dataclass
class Pomodoro:
    state: str = "off"          # off | work | break
    remaining: float = 0.0
    completed: int = 0
    work_min: float = POMODORO_WORK_MIN
    break_min: float = POMODORO_BREAK_MIN

    def start(self) -> None:
        self.state = "work"
        self.remaining = self.work_min * 60

    def stop(self) -> None:
        self.state = "off"
        self.remaining = 0.0

    def tick(self, dt: float) -> str | None:
        """Returns "work_done" / "break_done" on a transition."""
        if self.state == "off" or dt <= 0:
            return None
        self.remaining -= dt
        if self.remaining > 0:
            return None
        if self.state == "work":
            self.completed += 1
            self.state = "break"
            self.remaining = self.break_min * 60
            return "work_done"
        self.state = "off"
        self.remaining = 0.0
        return "break_done"

    @property
    def quiet(self) -> bool:
        return self.state == "work"
