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
