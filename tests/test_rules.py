from collections import deque
from contextlib import nullcontext
from pathlib import Path

import pytest

from core.board import Board
from core.constants import Action, Orientation, TileType
from core.rules import apply_action, is_goal, successors
from core.state import State


def arena(overrides=(), switches=(), split_switches=(), initial_bridges=()):
    grid = [list("...........") for _ in range(9)]
    grid[0][0], grid[0][10] = "S", "G"
    for r, c, tile in overrides:
        grid[r][c] = tile
    return Board.from_dict({
        "grid": ["".join(row) for row in grid],
        "switches": list(switches),
        "split_switches": list(split_switches),
        "initial_bridges": list(initial_bridges),
    })


@pytest.mark.parametrize("orientation,positions,action,expected_orientation,expected", [
    (Orientation.STANDING, [(4, 4)], Action.UP, Orientation.VERTICAL, [(2, 4), (3, 4)]),
    (Orientation.STANDING, [(4, 4)], Action.DOWN, Orientation.VERTICAL, [(5, 4), (6, 4)]),
    (Orientation.STANDING, [(4, 4)], Action.LEFT, Orientation.HORIZONTAL, [(4, 2), (4, 3)]),
    (Orientation.STANDING, [(4, 4)], Action.RIGHT, Orientation.HORIZONTAL, [(4, 5), (4, 6)]),
    (Orientation.HORIZONTAL, [(4, 4), (4, 5)], Action.UP, Orientation.HORIZONTAL, [(3, 4), (3, 5)]),
    (Orientation.HORIZONTAL, [(4, 4), (4, 5)], Action.DOWN, Orientation.HORIZONTAL, [(5, 4), (5, 5)]),
    (Orientation.HORIZONTAL, [(4, 4), (4, 5)], Action.LEFT, Orientation.STANDING, [(4, 3)]),
    (Orientation.HORIZONTAL, [(4, 4), (4, 5)], Action.RIGHT, Orientation.STANDING, [(4, 6)]),
    (Orientation.VERTICAL, [(4, 4), (5, 4)], Action.UP, Orientation.STANDING, [(3, 4)]),
    (Orientation.VERTICAL, [(4, 4), (5, 4)], Action.DOWN, Orientation.STANDING, [(6, 4)]),
    (Orientation.VERTICAL, [(4, 4), (5, 4)], Action.LEFT, Orientation.VERTICAL, [(4, 3), (5, 3)]),
    (Orientation.VERTICAL, [(4, 4), (5, 4)], Action.RIGHT, Orientation.VERTICAL, [(4, 5), (5, 5)]),
])
def test_all_intact_rolls(orientation, positions, action, expected_orientation, expected):
    state = State.make(positions, orientation)
    board = arena()
    assert apply_action(board, state, action) == State.make(expected, expected_orientation)


def test_invalid_move_leaves_input_untouched():
    board = arena()
    state = board.initial_state()
    before = (hash(board), hash(state), board.to_dict())
    assert apply_action(board, state, Action.UP) is None
    assert apply_action(board, state, Action.SPLIT_0_RIGHT) is None
    assert apply_action(board, state, "RIGHT") is None
    assert before == (hash(board), hash(state), board.to_dict())


def test_fragile_carries_lying_block_and_split_cube_but_not_standing():
    board = arena([(4, 4, "F")])
    standing_arrival = State.make([(4, 2), (4, 3)], Orientation.HORIZONTAL)
    assert apply_action(board, standing_arrival, Action.RIGHT) is None
    lying_arrival = State.make([(4, 3)], Orientation.STANDING)
    assert apply_action(board, lying_arrival, Action.RIGHT) is not None
    split = State.make([(4, 3), (6, 6)], Orientation.SPLIT)
    assert apply_action(board, split, Action.SPLIT_0_RIGHT) is not None


@pytest.mark.parametrize("tile,behavior,initial,expected_open", [
    ("o", "TOGGLE", False, True),
    ("o", "TOGGLE", True, False),
    ("o", "PERMANENT_OPEN", False, True),
    ("o", "PERMANENT_OPEN", True, True),
    ("o", "PERMANENT_CLOSE", False, False),
    ("o", "PERMANENT_CLOSE", True, False),
    ("x", "TOGGLE", False, True),
    ("x", "PERMANENT_OPEN", False, True),
    ("x", "PERMANENT_CLOSE", True, False),
])
def test_switch_behaviors_when_standing(tile, behavior, initial, expected_open):
    spec = {"pos": [4, 4], "behavior": behavior, "targets": [[7, 7]]}
    warning = (pytest.warns(UserWarning, match="Permanently impassable")
               if behavior == "PERMANENT_CLOSE" and not initial else nullcontext())
    with warning:
        board = arena([(4, 4, tile), (7, 7, "B")], [spec], initial_bridges=[(7, 7)] if initial else [])
    state = State.make([(4, 2), (4, 3)], Orientation.HORIZONTAL, board.initial_bridges)
    result = apply_action(board, state, Action.RIGHT)
    assert result is not None
    assert ((7, 7) in result.active_bridges) == expected_open


def test_heavy_switch_ignores_lying_block_and_split_cube():
    spec = {"pos": [4, 4], "behavior": "TOGGLE", "targets": [[7, 7]]}
    board = arena([(4, 4, "x"), (7, 7, "B")], [spec])
    for state, action in [
        (State.make([(4, 3)], Orientation.STANDING), Action.RIGHT),
        (State.make([(4, 3), (6, 6)], Orientation.SPLIT), Action.SPLIT_0_RIGHT),
    ]:
        assert not apply_action(board, state, action).active_bridges


def test_stationary_split_cube_does_not_retoggle_switch():
    spec = {"pos": [3, 3], "behavior": "TOGGLE", "targets": [[7, 7]]}
    board = arena([(3, 3, "o"), (7, 7, "B")], [spec])
    state = State.make([(3, 2), (6, 6)], Orientation.SPLIT)
    pressed = apply_action(board, state, Action.SPLIT_0_RIGHT)
    assert (7, 7) in pressed.active_bridges
    moved_other = apply_action(board, pressed, Action.SPLIT_1_LEFT)
    assert moved_other.active_bridges == pressed.active_bridges
    released = apply_action(board, moved_other, Action.SPLIT_0_LEFT)
    pressed_again = apply_action(board, released, Action.SPLIT_0_RIGHT)
    assert not pressed_again.active_bridges


def test_occupied_bridge_collapse_is_invalid_without_mutation():
    spec = {"pos": [3, 3], "behavior": "TOGGLE", "targets": [[6, 6]]}
    board = arena([(3, 3, "o"), (6, 6, "B")], [spec], initial_bridges=[(6, 6)])
    state = State.make([(3, 2), (6, 6)], Orientation.SPLIT, board.initial_bridges)
    assert apply_action(board, state, Action.SPLIT_0_RIGHT) is None
    assert state.active_bridges == frozenset({(6, 6)})


def test_closed_bridge_is_void_until_opened():
    spec = {"pos": [1, 1], "behavior": "PERMANENT_OPEN", "targets": [[4, 4]]}
    board = arena([(1, 1, "o"), (4, 4, "B")], [spec])
    state = State.make([(4, 3)], Orientation.STANDING)
    assert apply_action(board, state, Action.RIGHT) is None
    opened = State.make(state.positions, state.orientation, [(4, 4)])
    assert apply_action(board, opened, Action.RIGHT) is not None


def test_switch_can_open_bridge_under_the_same_landing_block():
    spec = {"pos": [4, 4], "behavior": "PERMANENT_OPEN", "targets": [[4, 5]]}
    board = arena([(4, 4, "o"), (4, 5, "B")], [spec])
    result = apply_action(board, State.make([(4, 3)], Orientation.STANDING), Action.RIGHT)
    assert result and (4, 5) in result.active_bridges


def test_split_spawn_requires_standing_and_merges_on_adjacency():
    spec = {"pos": [4, 4], "spawn_positions": [[2, 7], [4, 7]]}
    board = arena([(4, 4, "(")], split_switches=[spec])
    lying = apply_action(board, State.make([(4, 3)], Orientation.STANDING), Action.RIGHT)
    assert lying.orientation == Orientation.HORIZONTAL
    state = State.make([(4, 2), (4, 3)], Orientation.HORIZONTAL)
    split = apply_action(board, state, Action.RIGHT)
    assert split == State.make([(2, 7), (4, 7)], Orientation.SPLIT)
    assert apply_action(board, split, Action.DOWN) is None
    merged = apply_action(board, split, Action.SPLIT_0_DOWN)
    assert merged == State.make([(3, 7), (4, 7)], Orientation.VERTICAL)


def test_split_spawn_on_closed_bridge_fails():
    split_spec = {"pos": [4, 4], "spawn_positions": [[2, 7], [4, 7]]}
    switch_spec = {"pos": [1, 1], "behavior": "PERMANENT_OPEN", "targets": [[2, 7]]}
    board = arena([(4, 4, "("), (2, 7, "B"), (1, 1, "o")], [switch_spec], [split_spec])
    state = State.make([(4, 2), (4, 3)], Orientation.HORIZONTAL)
    assert apply_action(board, state, Action.RIGHT) is None


def test_horizontal_split_merge_and_coordinate_reordering():
    board = arena()
    state = State.make([(3, 3), (4, 4)], Orientation.SPLIT)
    merged = apply_action(board, state, Action.SPLIT_0_DOWN)
    assert merged == State.make([(4, 3), (4, 4)], Orientation.HORIZONTAL)
    state = State.make([(3, 3), (4, 6)], Orientation.SPLIT)
    reordered = apply_action(board, state, Action.SPLIT_0_DOWN)
    assert reordered.positions == ((4, 3), (4, 6))
    reordered = apply_action(board, reordered, Action.SPLIT_0_DOWN)
    assert reordered.positions == ((4, 6), (5, 3))


def test_split_spawn_can_press_soft_switch_but_not_heavy():
    split = {"pos": [4, 4], "spawn_positions": [[2, 7], [4, 7]]}
    soft = {"pos": [2, 7], "behavior": "PERMANENT_OPEN", "targets": [[7, 7]]}
    heavy = {"pos": [4, 7], "behavior": "PERMANENT_CLOSE", "targets": [[7, 7]]}
    board = arena([(4, 4, "("), (2, 7, "o"), (4, 7, "x"), (7, 7, "B")], [soft, heavy], [split])
    result = apply_action(board, State.make([(4, 2), (4, 3)], Orientation.HORIZONTAL), Action.RIGHT)
    assert result.is_split and (7, 7) in result.active_bridges


def test_goal_requires_standing_and_is_terminal():
    board = Board.from_dict({"grid": ["S..G."]})
    lying = apply_action(board, State.make([(0, 2)], Orientation.STANDING), Action.RIGHT)
    assert not is_goal(board, lying)
    arrival = apply_action(board, State.make([(0, 1), (0, 2)], Orientation.HORIZONTAL), Action.RIGHT)
    assert is_goal(board, arrival)
    assert successors(board, arrival) == []


LEVELS = sorted((Path(__file__).resolve().parents[1] / "levels").glob("*.json"))


@pytest.mark.parametrize("path", LEVELS, ids=lambda path: path.stem)
def test_each_bundled_level_has_a_replayable_solution(path):
    board = Board.from_json(path)
    start = board.initial_state()
    frontier, parents = deque([start]), {start: None}
    goal = None
    while frontier:
        state = frontier.popleft()
        if is_goal(board, state):
            goal = state
            break
        for action, next_state in successors(board, state):
            if next_state not in parents:
                parents[next_state] = (state, action)
                frontier.append(next_state)
        assert len(parents) < 20000, "Bundled demo should remain small enough for responsive search"
    assert goal is not None, f"No solution for {path.name}"
    actions, state = [], goal
    while parents[state] is not None:
        previous, action = parents[state]
        actions.append(action)
        state = previous
    states = [start]
    for action in reversed(actions):
        states.append(apply_action(board, states[-1], action))
        assert states[-1] is not None
    assert is_goal(board, states[-1])
    if "fragile" in path.stem:
        assert any(board.tile_at(*p) == TileType.FRAGILE for s in states for p in s.positions)
    if "switch" in path.stem:
        assert any(s.active_bridges for s in states)
    if "split" in path.stem:
        assert any(s.is_split for s in states)
