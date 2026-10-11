import pytest
from petcore import stats as S


def test_decay_rates_match_spec():
    s = S.Stats(satiety=100, mood=100)
    one_hour = s.decayed(3600)
    assert one_hour.satiety == pytest.approx(100 - 5 * 2)      # -5 per 30 min
    assert one_hour.mood == pytest.approx(100 - 3)             # -3 per 60 min


def test_offline_catch_up_is_capped_at_twelve_hours():
    week = S.Stats(satiety=100, mood=100).decayed(7 * 24 * 3600)
    capped = S.Stats(satiety=100, mood=100).decayed(S.OFFLINE_CAP_SECONDS)
    assert (week.satiety, week.mood) == (capped.satiety, capped.mood)
    assert capped.satiety == 0.0                       # 12 h of -5/30min empties the bowl
    assert capped.mood == pytest.approx(100 - 3 * 12)  # ...but mood only loses 36


def test_values_never_leave_zero_to_hundred():
    s = S.Stats(satiety=1, mood=1)
    assert s.decayed(9 * 3600).satiety == 0.0
    assert s.decayed(9 * 3600).mood == 0.0
    fed = S.feed(S.Stats(satiety=99, mood=99, affection=99), "bento")
    assert fed.satiety == 100.0 and fed.mood == 100.0 and fed.affection == 100.0


def test_interaction_deltas():
    s = S.Stats(satiety=50, mood=50, affection=10)
    assert S.apply_delta(s, "pet").mood == 56 and S.apply_delta(s, "pet").affection == 11
    assert S.apply_delta(s, "thrown").mood == 46
    assert S.apply_delta(s, "poke_annoyed").mood == 48
    assert S.apply_delta(s, "pomodoro_done").mood == 55


def test_hungry_and_sad_flags():
    assert S.Stats(satiety=29, mood=70).hungry
    assert not S.Stats(satiety=30, mood=70).hungry
    assert S.Stats(satiety=70, mood=29).sad
    assert S.Stats(satiety=70, mood=70).is_happy()


def test_save_round_trip_is_lossless():
    s = S.Stats(satiety=41.5, mood=88.25, affection=12.0, saved_at=1234.5, last_day="2026-10-11")
    assert S.from_dict(S.to_dict(s)) == s


def test_unknown_schema_is_rejected():
    d = S.to_dict(S.Stats())
    d["schema"] = 99
    with pytest.raises(ValueError):
        S.from_dict(d)


def test_negative_elapsed_is_clamped():
    s = S.Stats(satiety=50, mood=50)
    assert s.decayed(-100) == s
