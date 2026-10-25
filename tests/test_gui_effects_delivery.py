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


"""Classic scene graph checks: no ShowBase, graphics context or display needed."""

from types import SimpleNamespace

import pytest

panda = pytest.importorskip("panda3d.core")

from core.board import Board
from core.constants import Action, Orientation
from core.rules import apply_action, is_goal
from core.state import State
from gui.scene import BoardScene


@pytest.fixture
def scene():
    render = panda.NodePath(panda.PandaNode("test-render"))
    camera = render.attachNewNode(panda.Camera("test-camera"))
    base = SimpleNamespace(render=render, camera=camera, camNode=camera.node())
    result = BoardScene(base)
    yield result
    result.effects.clear()
    render.removeNode()


def arena():
    return Board.from_dict({"grid": [
        ".........", ".........", ".........", "....S....",
        ".........", ".........", "........G",
    ]})


def assert_block_matches_state(scene, state):
    block = scene.blocks.find("**/block")
    expected_center = (
        sum(p[1] for p in state.positions) / len(state.positions),
        -sum(p[0] for p in state.positions) / len(state.positions),
        1 if state.orientation == Orientation.STANDING else .5,
    )
    expected_size = {
        Orientation.STANDING: (1, 1, 2),
        Orientation.HORIZONTAL: (2, 1, 1),
        Orientation.VERTICAL: (1, 2, 1),
    }[state.orientation]
    assert tuple(block.getPos(scene.base.render)) == pytest.approx(expected_center, abs=1e-5)
    low, high = block.getTightBounds(scene.base.render)
    assert tuple(high - low) == pytest.approx(expected_size, abs=1e-5)


def test_multi_axis_rolls_preserve_engine_position_and_geometry(scene):
    board = arena()
    state = board.initial_state()
    scene.set_board(board, state, intro=False)
    for action in (Action.UP, Action.RIGHT, Action.DOWN, Action.RIGHT, Action.UP, Action.LEFT):
        next_state = apply_action(board, state, action)
        assert next_state is not None
        scene.transition(state, next_state, action=action)
        scene.update(.24)
        assert scene.state == next_state and not scene.busy
        assert_block_matches_state(scene, next_state)
        state = next_state


def test_goal_roll_chains_to_sink_and_reset_restores_visible_snapshot(scene):
    board = Board.from_dict({"grid": ["S..G"]})
    initial = board.initial_state()
    before_goal = apply_action(board, initial, Action.RIGHT)
    goal = apply_action(board, before_goal, Action.RIGHT)
    scene.set_board(board, before_goal, intro=False)
    scene.transition(before_goal, goal, action=Action.RIGHT)
    scene.update(.1)
    assert not scene.blocks.isHidden() and scene.busy
    scene.update(.3)
    assert scene.state == goal and is_goal(board, scene.state)
    assert scene.animation["kind"] == "goal"
    assert not scene.blocks.isHidden()
    scene.update(1)
    assert scene.blocks.isHidden() and not scene.busy
    scene.set_state(initial)
    scene.update(3)
    assert not scene.blocks.isHidden() and scene.state == initial and not scene.busy
    assert_block_matches_state(scene, initial)


def test_undo_snapshot_cancels_queued_goal_callback(scene):
    board = Board.from_dict({"grid": ["S..G"]})
    initial = board.initial_state()
    before_goal = apply_action(board, initial, Action.RIGHT)
    goal = apply_action(board, before_goal, Action.RIGHT)
    scene.set_board(board, before_goal, intro=False)
    scene.transition(before_goal, goal, action=Action.RIGHT)
    scene.update(.1)
    scene.set_state(initial)
    scene.update(2)
    assert scene.state == initial and not scene.busy
    assert not scene.blocks.isHidden()
    assert_block_matches_state(scene, initial)


def test_failed_split_move_drops_only_the_selected_cube(scene):
    board = arena()
    state = State.make([(3, 0), (3, 4)], Orientation.SPLIT)
    action = Action.SPLIT_0_LEFT
    assert apply_action(board, state, action) is None
    scene.set_board(board, state, (3, 0), intro=False)
    moving, stationary = scene._block_nodes[(3, 0)], scene._block_nodes[(3, 4)]
    stationary_center = stationary.find("**/split-cube").getPos(scene.base.render)
    scene.fall(state, action)
    scene.update(1.1)
    assert moving.isHidden() and not stationary.isHidden()
    assert tuple(stationary.find("**/split-cube").getPos(scene.base.render)) == pytest.approx(tuple(stationary_center))
    assert scene.state == state and not scene.busy
    scene.set_state(state, (3, 0))
    scene.update(2)
    assert all(not node.isHidden() for node in scene._block_nodes.values())


def test_bridge_tweens_then_snapshot_cancels_it_without_stale_motion(scene):
    board = Board.from_dict({
        "grid": ["S.oB..G"],
        "switches": [{"pos": [0, 2], "behavior": "TOGGLE", "targets": [[0, 3]]}],
    })
    initial = board.initial_state()
    opened = apply_action(board, initial, Action.RIGHT)
    scene.set_board(board, initial, intro=False)
    bridge = scene.bridge_nodes[(0, 3)]
    assert bridge.getR() == pytest.approx(90)
    scene.transition(initial, opened, action=Action.RIGHT)
    scene.update(.25)
    assert 0 < bridge.getR() < 90 and scene.busy
    scene.set_state(initial)
    scene.update(1)
    assert scene.bridge_nodes[(0, 3)] == bridge
    assert bridge.getR() == pytest.approx(90)
    assert scene.switch_nodes[(0, 2)].getZ() == pytest.approx(.035)
    assert scene.state == initial and not scene.busy
    scene.transition(initial, opened, action=Action.RIGHT)
    scene.update(1)
    assert bridge.getR() == pytest.approx(0)
    assert scene.switch_nodes[(0, 2)].getZ() == pytest.approx(-.035)
    assert scene.state == opened and not scene.busy


def test_intro_and_restart_can_be_cancelled_by_immediate_snapshot(scene):
    board = arena()
    initial = board.initial_state()
    snapshot = apply_action(board, initial, Action.RIGHT)
    scene.set_board(board, initial, intro=True)
    assert scene.busy and scene.blocks.getZ() == pytest.approx(3)
    scene.update(.2)
    scene.set_state(snapshot)
    scene.update(2)
    assert scene.state == snapshot and not scene.busy
    assert all(node.getZ() == pytest.approx(0) for node in scene.tile_nodes.values())
    assert_block_matches_state(scene, snapshot)
    scene.restart(initial)
    scene.update(.2)
    assert scene.blocks.isHidden() and scene.busy
    scene.set_state(snapshot)
    scene.update(2)
    assert scene.state == snapshot and not scene.busy and not scene.blocks.isHidden()
    assert all(node.getZ() == pytest.approx(0) for node in scene.tile_nodes.values())
    assert_block_matches_state(scene, snapshot)


def test_large_time_step_finishes_restart_and_following_intro(scene):
    board = arena()
    initial = board.initial_state()
    scene.set_board(board, initial, intro=False)
    scene.restart(initial)
    scene.update(2)
    assert scene.state == initial and not scene.busy and not scene.blocks.isHidden()
    assert all(node.getZ() == pytest.approx(0) for node in scene.tile_nodes.values())
    assert_block_matches_state(scene, initial)


def test_fragile_engine_hint_breaks_orange_tile_then_reset_restores_it(scene):
    from core.constants import MoveResult
    board = Board.from_dict({"grid": ["S..F..G"]})
    before = State.make([(0, 1), (0, 2)], Orientation.HORIZONTAL)
    attempted = State.make([(0, 3)], Orientation.STANDING)
    scene.set_board(board, before, intro=False)
    tile = scene.tile_nodes[(0, 3)]
    scene.fall(before, Action.RIGHT, reason=MoveResult.FRAGILE_BROKE, target=attempted)
    scene.update(.3)
    assert tile.isHidden()
    assert scene.debris.getNumChildren() == 9
    assert scene.busy
    scene.update(1)
    assert scene.blocks.isHidden() and not scene.busy
    assert all(piece.isHidden() for piece in scene.debris.getChildren())
    scene.set_state(board.initial_state())
    assert not tile.isHidden() and scene.debris.getNumChildren() == 0
    assert not scene.blocks.isHidden()


def test_split_switch_uses_parentheses_and_selected_cube_outline(scene):
    board = Board.from_dict({
        "grid": ["S..(..G", ".......", "......."],
        "split_switches": [{"pos": [0, 3], "spawn_positions": [[1, 1], [1, 4]]}],
    })
    split = State.make([(1, 1), (1, 4)], Orientation.SPLIT)
    scene.set_board(board, split, (1, 4), intro=False)
    marker = scene.switch_nodes[(0, 3)]
    assert marker.findAllMatches("**/split-parenthesis-*").getNumPaths() == 24
    assert scene._block_nodes[(1, 1)].findAllMatches("**/selected-cube").getNumPaths() == 0
    assert scene._block_nodes[(1, 4)].findAllMatches("**/selected-cube").getNumPaths() == 4


def test_closing_switch_drops_stationary_cube_on_bridge_not_supported_mover(scene):
    from core.constants import MoveResult
    from core.rules import evaluate_action
    board = Board.from_dict({
        "grid": ["S..G......", "..B...o..."],
        "initial_bridges": [[1, 2]],
        "switches": [{"pos": [1, 6], "behavior": "PERMANENT_CLOSE", "targets": [[1, 2]]}],
    })
    state = State.make([(1, 2), (1, 5)], Orientation.SPLIT, [(1, 2)])
    action = Action.SPLIT_1_RIGHT
    outcome = evaluate_action(board,state,action)
    assert outcome.reason == MoveResult.BRIDGE_CLOSED and outcome.state is None
    scene.set_board(board,state,(1, 5),intro=False)
    unsupported = scene._block_nodes[(1, 2)]
    supported = scene._block_nodes[(1, 5)]
    scene.fall(state,action,reason=outcome.reason,target=outcome.attempted_state)
    scene.update(1.2)
    assert unsupported.isHidden() and not supported.isHidden()
    low,high = supported.find("**/split-cube").getTightBounds(scene.root)
    assert tuple((low+high)*.5) == pytest.approx((6,-1,.5),abs=1e-5)
    assert scene.bridge_nodes[(1, 2)].isHidden()
    assert scene.state == state and not scene.busy
    scene.set_state(state,(1, 5))
    assert not scene.bridge_nodes[(1, 2)].isHidden()
    assert all(not node.isHidden() for node in scene._block_nodes.values())
