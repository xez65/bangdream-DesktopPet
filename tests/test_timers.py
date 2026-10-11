import pytest
from datetime import datetime, timedelta

from petcore.timers import (IDLE_BEFORE_SLEEP_SECONDS, HourChime, Pomodoro,
                            POMODORO_BREAK_MIN, POMODORO_WORK_MIN, Sedentary)


def test_hour_chime_fires_once_per_hour():
    c = HourChime()
    assert c.tick(datetime(2026, 10, 11, 9, 0, 5)) == 9
    assert c.tick(datetime(2026, 10, 11, 9, 30)) is None
    assert c.tick(datetime(2026, 10, 11, 10, 0)) == 10


def test_hour_chime_crosses_midnight():
    c = HourChime()
    assert c.tick(datetime(2026, 10, 11, 23, 59)) == 23
    assert c.tick(datetime(2026, 10, 12, 0, 1)) == 0


def test_hour_chime_can_be_disabled():
    c = HourChime(enabled=False)
    assert c.tick(datetime(2026, 10, 11, 9, 0)) is None
    assert c.last_key == ""


def test_sedentary_fires_after_interval_and_resets():
    s = Sedentary(interval_min=45)
    assert s.tick(44 * 60, 0) is False
    assert s.tick(2 * 60, 0) is True
    assert s.elapsed == 0.0
    assert s.tick(10, 0) is False
    assert s.elapsed == 10.0


def test_sedentary_stays_quiet_when_nobody_is_at_the_keyboard():
    s = Sedentary(interval_min=1)
    assert s.tick(120, IDLE_BEFORE_SLEEP_SECONDS + 1) is False
    assert s.elapsed == 0.0


def test_sedentary_disabled_never_fires():
    s = Sedentary(enabled=False, interval_min=1)
    assert s.tick(3600, 0) is False


def test_pomodoro_work_then_break_then_off():
    p = Pomodoro()
    p.start()
    assert p.quiet and p.remaining == POMODORO_WORK_MIN * 60
    assert p.tick(POMODORO_WORK_MIN * 60 + 1) == "work_done"
    assert p.state == "break" and not p.quiet and p.completed == 1
    assert p.tick(POMODORO_BREAK_MIN * 60 + 1) == "break_done"
    assert p.state == "off" and p.remaining == 0.0


def test_pomodoro_stop_is_immediate():
    p = Pomodoro()
    p.start()
    p.tick(60)
    p.stop()
    assert p.state == "off"
    assert p.tick(10_000) is None


def test_pomodoro_tick_does_nothing_when_off():
    assert Pomodoro().tick(60) is None


def test_sedentary_reset_clears_the_clock():
    s = Sedentary(interval_min=45)
    s.tick(600, 0)
    s.reset()
    assert s.elapsed == 0.0
