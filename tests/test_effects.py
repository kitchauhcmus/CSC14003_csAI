"""Animation math and timing tests require Panda3D, but no graphics window."""

import math

import pytest
from panda3d.core import Quat, Vec3

from gui.effects import Effects, EffectTrack, falling_offset, rigid_pivot_offset, roll_quat, smoothstep


def xyz(vector):
    return tuple(vector)


def test_smoothstep_clamps_and_has_slow_endpoints():
    assert [smoothstep(t) for t in (-1, 0, .5, 1, 2)] == [0, 0, .5, 1, 1]
    assert smoothstep(.01) < .001
    assert smoothstep(.99) > .999


def test_rigid_roll_keeps_contact_edge_fixed_and_preserves_distances():
    pivot, center = Vec3(.5, 0, 0), Vec3(0, 0, 1)
    axis = Vec3(0, 7, 0)
    rotation = roll_quat(90, axis)
    offset = rigid_pivot_offset(pivot, rotation)
    assert xyz(rotation.xform(pivot) + offset) == pytest.approx(xyz(pivot))
    assert xyz(rotation.xform(center) + offset) == pytest.approx((1.5, 0, .5), abs=1e-6)
    assert (rotation.xform(center) + offset - pivot).length() == pytest.approx((center - pivot).length())
    assert xyz(axis) == (0, 7, 0)


def test_reverse_quarter_turn_and_identity_translation():
    pivot = Vec3(2, -3, 0)
    assert xyz(rigid_pivot_offset(pivot, roll_quat(0, Vec3(1, 0, 0)))) == pytest.approx((0, 0, 0))
    forward = roll_quat(90, Vec3(0, 1, 0))
    backward = roll_quat(-90, Vec3(0, 1, 0))
    point = Vec3(1, 2, 3)
    assert xyz(backward.xform(forward.xform(point))) == pytest.approx(xyz(point), abs=1e-6)


def test_falling_offset_is_ballistic_and_zero_direction_drops_straight():
    direction = Vec3(3, 4, 99)
    assert xyz(falling_offset(0, direction)) == (0, 0, 0)
    assert xyz(falling_offset(1, direction)) == pytest.approx((.54, .72, -9), abs=1e-6)
    assert xyz(falling_offset(2, Vec3(0))) == pytest.approx((0, 0, -36))
    assert xyz(direction) == (3, 4, 99)


def test_delay_boundary_and_overshoot_complete_exactly_once():
    updates, completions = [], []
    track = EffectTrack(2, updates.append, lambda: completions.append("done"), delay=1)
    assert not track.advance(.5)
    assert updates == []
    assert not track.advance(.5)
    assert updates == [0]
    assert not track.advance(.5)
    assert updates == [0, .25]
    assert track.advance(9)
    assert updates == [0, .25, 1]
    assert track.advance(100)
    assert completions == ["done"] and updates == [0, .25, 1]


def test_zero_duration_waits_for_delay_then_completes_at_one():
    updates, completions = [], []
    track = EffectTrack(0, updates.append, lambda: completions.append(True), delay=.5)
    assert not track.advance(.25)
    assert track.advance(.25)
    assert updates == [1] and completions == [True]
    immediate = EffectTrack(0, updates.append)
    assert immediate.advance(0)
    assert updates == [1, 1]


def test_completion_is_safe_if_callback_advances_same_track():
    updates, completions = [], []
    track = None

    def complete():
        completions.append(True)
        assert track.advance(10)

    track = EffectTrack(1, updates.append, complete)
    assert track.advance(1)
    assert updates == [1] and completions == [True]


def test_clear_cancels_pending_effects_without_callbacks():
    effects, updates, completions = Effects(), [], []
    first = effects.add(EffectTrack(1, updates.append, lambda: completions.append(True)))
    second = effects.add(EffectTrack(1, updates.append, delay=2))
    assert effects.busy
    effects.update(.25)
    assert updates == [.25]
    effects.clear()
    assert first.cancelled and second.cancelled and not effects.busy
    effects.update(10)
    assert updates == [.25] and completions == []


def test_callbacks_can_clear_and_replace_effects_without_advancing_new_track():
    effects, events = Effects(), []

    def replace():
        effects.clear()
        effects.add(EffectTrack(1, lambda t: events.append(("new", t))))

    effects.add(EffectTrack(1, lambda t: events.append(("first", t)), replace))
    cancelled = effects.add(EffectTrack(1, lambda t: events.append(("cancelled", t))))
    effects.update(2)
    assert events == [("first", 1)]
    assert cancelled.cancelled and effects.busy
    effects.update(.5)
    assert events == [("first", 1), ("new", .5)]
    effects.update(.5)
    assert not effects.busy


def test_adding_a_track_twice_does_not_double_its_speed():
    effects, updates = Effects(), []
    track = EffectTrack(1, updates.append)
    assert effects.add(track) is track
    effects.add(track)
    effects.update(.25)
    assert updates == [.25]


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), True, "1"])
def test_invalid_timing_never_calls_callbacks(bad):
    updates = []
    track = EffectTrack(1, updates.append)
    with pytest.raises(ValueError):
        track.advance(bad)
    with pytest.raises(ValueError):
        EffectTrack(bad, updates.append)
    with pytest.raises(ValueError):
        EffectTrack(1, updates.append, delay=bad)
    with pytest.raises(ValueError):
        Effects().update(bad)
    assert updates == []


def test_rejects_invalid_geometry_and_callback_inputs():
    with pytest.raises(ValueError):
        roll_quat(90, Vec3(0))
    with pytest.raises(ValueError):
        roll_quat(math.inf, Vec3(1, 0, 0))
    with pytest.raises(ValueError):
        rigid_pivot_offset(Vec3(0), Quat(0, 0, 0, 0))
    with pytest.raises(ValueError):
        falling_offset(1, Vec3(math.nan, 0, 0))
    with pytest.raises(ValueError):
        falling_offset(1, Vec3(0), gravity=-1)
    with pytest.raises(ValueError):
        smoothstep(math.nan)
    with pytest.raises(ValueError):
        EffectTrack(1, None)
    with pytest.raises(ValueError):
        EffectTrack(1, lambda t: None, on_complete=False)
