from conftest import build_catalog
from petcore import clip_manifest as cm
from petcore.behavior import (STATE_CARRIED, STATE_FALL, STATE_IDLE, STATE_QUIET,
                              STATE_REACT, STATE_SLEEP, STATE_WALK, BehaviorCore, WorldCtx)
from petcore.stats import Stats

CTX = WorldCtx(stats=Stats())


def core(tmp_path, seed=42):
    return BehaviorCore(catalog=build_catalog(tmp_path / "assets"), seed=seed)


def run(b, seconds, dt=0.1, ctx=CTX):
    out = []
    for _ in range(int(seconds / dt)):
        out.append(b.tick(dt, ctx))
    return out


def test_same_seed_replays_the_same_decisions(tmp_path):
    a = [d for d in run(core(tmp_path / "a", 42), 120)]
    b = [d for d in run(core(tmp_path / "b", 42), 120)]
    assert [(d.slug, d.state, d.walk_dir, d.bubble_key) for d in a] == \
           [(d.slug, d.state, d.walk_dir, d.bubble_key) for d in b]
    assert len({d.state for d in a}) > 1, "the machine never left one state"


def test_different_seeds_diverge(tmp_path):
    a = [d.slug for d in run(core(tmp_path / "a", 1), 60)]
    b = [d.slug for d in run(core(tmp_path / "b", 9999), 60)]
    assert a != b


def test_grab_blocks_everything_until_release(tmp_path):
    b = core(tmp_path)
    assert b.push("grab")
    assert b.state == STATE_CARRIED
    assert b.tick(0.1, CTX).slug == cm.HELD
    assert b.request(cm.CHIME[0], priority="reminder") is False
    assert b.push("poke") is False
    b.push("release")
    assert b.state == STATE_FALL
    assert b.request(cm.SEDENTARY[0], priority="reminder") is False
    b.push("landed")
    assert b.state == STATE_IDLE


def test_hard_landing_plays_the_flustered_clip(tmp_path):
    b = core(tmp_path)
    b.push("grab")
    b.push("release")
    b.push("landed", hard=True)
    d = b.tick(0.1, CTX)
    assert d.slug == cm.LAND and d.bubble_key == "thrown" and d.state == STATE_REACT


def test_soft_landing_does_not_react(tmp_path):
    b = core(tmp_path)
    b.push("grab")
    b.push("release")
    b.push("landed", hard=False)
    assert b.tick(0.1, CTX).slug == cm.IDLE


def test_third_poke_in_a_row_gets_a_rebuke(tmp_path):
    b = core(tmp_path)
    assert b.tick(0.1, CTX).bubble_key is None
    b.push("poke")
    assert b.tick(0.1, CTX).slug in cm.POKED
    b.push("poke")
    assert b.tick(0.1, CTX).slug in cm.POKED
    b.push("poke")
    assert b.tick(0.1, CTX).slug in cm.POKED_ANNOYED


def test_poke_streak_expires(tmp_path):
    b = core(tmp_path)
    b.push("poke")
    b.push("poke")
    run(b, 3.0)                      # window is 2 s
    b.push("poke")
    assert b.tick(0.1, CTX).slug in cm.POKED


def test_reminders_outrank_an_ongoing_reaction(tmp_path):
    b = core(tmp_path)
    b.push("poke")
    assert b.state == STATE_REACT
    assert b.push("chime", hungry=False)
    d = b.tick(0.1, CTX)
    assert d.slug == cm.CHIME[0] and d.bubble_key == "hour_chime"


def test_hungry_chime_uses_the_hungry_line(tmp_path):
    b = core(tmp_path)
    b.push("chime", hungry=True)
    assert b.tick(0.1, CTX).bubble_key == "hungry"


def test_pomodoro_holds_a_quiet_pose(tmp_path):
    b = core(tmp_path)
    b.push("pomodoro_start")
    assert b.state == STATE_QUIET
    for d in run(b, 30):
        assert d.slug in cm.QUIET
    b.push("pomodoro_done")
    assert b.state == STATE_IDLE
    assert b.tick(0.1, CTX).bubble_key == "pomodoro_done"


def test_quiet_ctx_flag_also_enters_quiet(tmp_path):
    b = core(tmp_path)
    b.tick(0.1, CTX)
    b.tick(0.1, WorldCtx(stats=Stats(), quiet=True))
    assert b.state == STATE_QUIET


def test_wall_reverses_walk_direction(tmp_path):
    b = core(tmp_path)
    b.state = STATE_WALK
    b.walk_dir = 1
    b._play(b._walk_slug())
    b.push("wall")
    assert b.walk_dir == -1 and b.slug == cm.WALK_LEFT


def test_sleep_wakes_on_activity(tmp_path):
    b = core(tmp_path)
    b.state = STATE_SLEEP
    b._play(cm.IDLE, 0.5)
    assert b.tick(0.1, CTX).speed == 0.5
    b.push("activity")
    assert b.state == STATE_IDLE


def test_walk_dir_is_reported_only_while_walking(tmp_path):
    b = core(tmp_path)
    b.state = STATE_WALK
    b.walk_dir = -1
    assert b.tick(0.1, CTX).walk_dir == -1
    b.state = STATE_IDLE
    assert b.tick(0.1, CTX).walk_dir == 0


def test_unknown_event_is_rejected(tmp_path):
    assert core(tmp_path).push("teleport") is False


def test_hungry_stats_steal_the_small_pool(tmp_path):
    b = core(tmp_path, seed=7)
    hungry = WorldCtx(stats=Stats(satiety=5))
    seen = set()
    for _ in range(200):
        b._roll(hungry)
        if b.state == STATE_REACT:
            seen.add(b.slug)
    assert seen and seen <= set(cm.LOW_STATS)


def test_idle_seconds_double_the_sleep_odds(tmp_path):
    b = core(tmp_path, seed=3)
    awake = sum(1 for _ in range(400) if (b._roll(CTX) or b.state) == STATE_SLEEP)
    c = core(tmp_path / "s", seed=3)
    away = WorldCtx(stats=Stats(), idle_seconds=600)
    asleep = sum(1 for _ in range(400) if (c._roll(away) or c.state) == STATE_SLEEP)
    assert asleep > awake


def test_missing_clip_in_catalog_degrades_to_idle(tmp_path):
    cat = build_catalog(tmp_path / "assets")
    b = BehaviorCore(cat, seed=1)
    assert b.request("nope_not_here") is False
    assert b.state == STATE_IDLE


# ---------------------------------------------------------------- manual selection (pinned)
def hold(b, seconds, dt=0.1, ctx=CTX):
    seen = set()
    for _ in range(int(seconds / dt)):
        seen.add(b.tick(dt, ctx).slug)
    return seen


def test_manual_loop_clip_is_held_instead_of_cut_after_one_cycle(tmp_path):
    b = core(tmp_path)
    assert b.request("sakiko_thinking01", priority="reminder")
    assert hold(b, 60) == {"sakiko_thinking01"}


def test_manual_walk_clip_does_not_start_walking_the_pet(tmp_path):
    b = core(tmp_path)
    b.request("sakiko_nf_right01", priority="reminder")
    for _ in range(100):
        d = b.tick(0.1, CTX)
        assert d.walk_dir == 0 and d.state == "manual"


def test_manual_one_shot_falls_back_to_pinned_idle(tmp_path):
    b = core(tmp_path)
    b.request("sakiko_smile01", priority="reminder")
    assert hold(b, 60) == {"sakiko_smile01", "sakiko_idle01"}


def test_reminder_while_pinned_returns_to_the_pinned_clip(tmp_path):
    b = core(tmp_path)
    b.request("sakiko_thinking01", priority="reminder")
    b.push("chime")
    assert hold(b, 60) == {"sakiko_thinking01", "sakiko_bye01"}


def test_poke_releases_the_pin_and_autonomy_resumes(tmp_path):
    b = core(tmp_path)
    b.request("sakiko_thinking01", priority="reminder")
    b.push("poke")
    assert b.pinned is False
    assert len(hold(b, 180)) > 2


def test_resume_autonomy_restarts_rolling(tmp_path):
    b = core(tmp_path)
    b.request("sakiko_thinking01", priority="reminder")
    hold(b, 30)
    b.resume_autonomy()
    assert b.pinned is False and b.state == STATE_IDLE
    assert len(hold(b, 240)) > 2


def test_grab_during_pin_does_not_resume_the_pin(tmp_path):
    b = core(tmp_path)
    b.request("sakiko_thinking01", priority="reminder")
    b.push("grab")
    b.push("release")
    b.push("landed")
    assert b.pinned is False
    assert len(hold(b, 180)) > 2
