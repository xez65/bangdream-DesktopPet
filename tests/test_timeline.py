from petcore import clip_manifest as cm
from petcore.clips import ClipSpec
from petcore.timeline import MAX_CATCH_UP, Timeline


def spec(frames=10, fps=10, loop="loop"):
    return ClipSpec("s", "S", "idle", frames, fps, loop, dir=None)


def test_loop_wraps_back_to_zero():
    t = Timeline(spec(8, 8))
    # 0.125 s is exact in binary, so eight ticks land precisely on the one-second seam.
    assert [t.advance(0.125) for _ in range(8)] == [1, 2, 3, 4, 5, 6, 7, 0]


def test_loop_wraps_modulo():
    t = Timeline(spec(10, 10))
    t._t = 1.00                          # exactly one second = 10 frames -> wraps
    assert t.frame == 0
    t._t = 1.15
    assert t.frame == 1


def test_once_holds_last_frame_and_reports_finished():
    t = Timeline(spec(10, 10, "once"))
    assert not t.finished
    t._t = 0.85
    assert t.frame == 8 and not t.finished
    t._t = 1.2
    assert t.frame == 9 and t.finished


def test_catch_up_is_clamped():
    t = Timeline(spec(100, 30))
    before = t.frame
    t.advance(10.0)                      # a frozen window must not jump 300 frames
    assert t._t == MAX_CATCH_UP
    assert t.frame - before == int(MAX_CATCH_UP * 30)


def test_speed_scales_progress():
    t = Timeline(spec(100, 30), speed=0.5)
    t.advance(0.10)
    assert t._t == 0.05                       # half speed -> half the wall clock accumulates
    assert t.frame == 1                       # int(0.05 * 30)


def test_switch_restarts_and_takes_new_spec():
    t = Timeline(spec(10, 10))
    t._t = 0.5
    t.switch(spec(20, 30, "once"), speed=2.0)
    assert t._t == 0.0 and t.spec.frames == 20 and t.speed == 2.0


def test_negative_dt_is_ignored():
    t = Timeline(spec(10, 10))
    t.advance(-5)
    assert t._t == 0.0


def test_empty_clip_never_crashes():
    t = Timeline(spec(0, 30))
    assert t.advance(0.1) == 0
    assert t.progress == 0.0
