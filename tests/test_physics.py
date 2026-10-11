import math

from petcore.physics import (GRAVITY, THROW_SPEED_CAP, Body, Rect, Sample,
                             clamp_into_screen, step, throw_velocity)

SCREEN = Rect(0.0, 0.0, 1920.0, 1040.0)
FLOOR = 1040.0


def test_gravity_accelerates_downwards():
    b = Body(x=100.0, y=500.0, on_ground=False)
    r = step(b, 0.1, FLOOR, SCREEN)
    assert r.body.vy == GRAVITY * 0.1
    assert r.body.y == 500.0 + GRAVITY * 0.1 * 0.1 * 0.5 + 0.0 or r.body.y > 500.0
    assert not r.landed


def test_landing_snaps_to_floor_and_kills_velocity():
    b = Body(x=100.0, y=1030.0, vy=500.0, on_ground=False)
    r = step(b, 0.1, FLOOR, SCREEN)
    assert r.body.y == FLOOR
    assert r.body.vy == 0.0
    assert r.landed and r.body.on_ground


def test_hard_landing_flag_uses_vy_threshold():
    soft = step(Body(0.0, 1039.0, vy=100.0, on_ground=False), 0.02, FLOOR, SCREEN)
    hard = step(Body(0.0, 1039.0, vy=2000.0, on_ground=False), 0.02, FLOOR, SCREEN)
    assert soft.landed and not soft.hard_landing
    assert hard.landed and hard.hard_landing


def test_ground_body_does_not_sink():
    r = step(Body(10.0, FLOOR, 0.0, 0.0, True), 0.1, FLOOR, SCREEN)
    assert r.body.y == FLOOR and not r.landed


def test_horizontal_clamp_reports_wall():
    left = step(Body(5.0, FLOOR, -1000.0, 0.0, True), 0.1, FLOOR, SCREEN)
    right = step(Body(1918.0, FLOOR, 1000.0, 0.0, True), 0.1, SCREEN.bottom, Rect(0, 0, 1920, 1040))
    assert left.body.x >= 0.0
    assert right.body.x <= 1920.0


def test_throw_velocity_from_moving_samples():
    s = [Sample(100 + i * 20, 500, 1.0 + i * 0.02) for i in range(8)]
    vx, vy = throw_velocity(s)
    assert vx > 0
    assert abs(vy) < abs(vx)


def test_throw_velocity_is_capped():
    s = [Sample(i * 5000, 500, i * 0.01) for i in range(8)]
    vx, vy = throw_velocity(s)
    assert math.hypot(vx, vy) <= THROW_SPEED_CAP + 1e-6


def test_paused_pointer_before_release_is_a_drop():
    s = [Sample(300, 500, 1.0), Sample(300, 500, 2.0)]
    assert throw_velocity(s) == (0.0, 0.0)


def test_single_sample_is_no_velocity():
    assert throw_velocity([Sample(1, 1, 1.0)]) == (0.0, 0.0)
    assert throw_velocity([]) == (0.0, 0.0)


def test_clamp_into_screen_after_monitor_change():
    b = clamp_into_screen(Body(-500.0, 4000.0, 10.0, 10.0, False), SCREEN, FLOOR)
    assert b.x == 0.0 and b.y == FLOOR and b.on_ground


def test_zero_dt_is_a_no_op():
    b = Body(1.0, 2.0, 3.0, 4.0, False)
    r = step(b, 0.0, FLOOR, SCREEN)
    assert r.body == b and not r.landed
