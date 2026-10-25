"""Regressions for the local GUI-facing engine additions.

The team's advanced-mechanics tests remain unchanged in core/.
"""

import pytest

from core.board import Board
from core.constants import Action, Direction, MoveResult, Orientation
from core.player_controller import SplitController
from core.rules import (
    action_for_cube,
    apply_action,
    apply_action_with_result,
    evaluate_action,
    is_goal,
    successors,
)
from core.state import State


def floor_board():
    return Board.from_dict({"grid": ["S.....G", ".......", ".......", "......."]})


def test_intact_roll_and_reverse_leave_input_unchanged():
    board = floor_board()
    initial = board.initial_state()
    original_board = board.to_dict()
    next_state = apply_action(board, initial, Action.RIGHT)
    assert next_state.positions == ((0, 1), (0, 2))
    assert next_state.orientation == Orientation.HORIZONTAL
    assert apply_action(board, next_state, Action.LEFT) == initial
    assert board.to_dict() == original_board
    assert initial.positions == ((0, 0),)


@pytest.mark.parametrize(
    "action, positions",
    [
        (Action.UP, ((0, 3), (1, 3))),
        (Action.DOWN, ((3, 3), (4, 3))),
        (Action.LEFT, ((2, 1), (2, 2))),
        (Action.RIGHT, ((2, 4), (2, 5))),
    ],
)
def test_four_roll_directions(action, positions):
    board = Board.from_dict({"grid": ["S.....G"] + ["......."] * 5})
    state = State.make([(2, 3)], Orientation.STANDING)
    assert apply_action(board, state, action).positions == positions


def test_void_failure_keeps_attempted_landing_for_animation():
    board = floor_board()
    state = board.initial_state()
    outcome = evaluate_action(board, state, Action.UP)
    assert outcome.state is None
    assert outcome.reason == MoveResult.FELL_VOID
    assert outcome.attempted_state.positions == ((-2, 0), (-1, 0))
    assert apply_action_with_result(board, state, Action.UP) == (None, MoveResult.FELL_VOID)
    assert state == board.initial_state()


def test_fragile_failure_identifies_landing_tile():
    board = Board.from_dict({"grid": ["S.F.G"]})
    state = State.make([(0, 0), (0, 1)], Orientation.HORIZONTAL)
    outcome = evaluate_action(board, state, Action.RIGHT)
    assert outcome.state is None
    assert outcome.reason == MoveResult.FRAGILE_BROKE
    assert outcome.attempted_state.positions == ((0, 2),)
    assert outcome.attempted_state.orientation == Orientation.STANDING
    # Lying on the same fragile tile remains legal, as defined by the engine.
    assert apply_action(board, board.initial_state(), Action.RIGHT) is not None


def test_closed_bridge_failure_and_simultaneous_opening():
    data = {
        "grid": ["SoB.G"],
        "switches": [{"pos": [0, 1], "behavior": "PERMANENT_OPEN", "targets": [[0, 2]]}],
    }
    board = Board.from_dict(data)
    opened = evaluate_action(board, board.initial_state(), Action.RIGHT)
    assert opened.reason == MoveResult.OK
    assert opened.state.active_bridges == frozenset({(0, 2)})

    # The identical geometry is unsupported when the newly pressed switch closes it.
    data["initial_bridges"] = [[0, 2]]
    data["switches"][0]["behavior"] = "PERMANENT_CLOSE"
    closing_board = Board.from_dict(data)
    closed = evaluate_action(closing_board, closing_board.initial_state(), Action.RIGHT)
    assert closed.reason == MoveResult.BRIDGE_CLOSED
    assert closed.state is None
    assert closed.attempted_state.positions == ((0, 1), (0, 2))
    assert not closed.attempted_state.active_bridges
    assert closing_board.initial_bridges == frozenset({(0, 2)})


def test_terminal_and_mismatched_action_are_not_falls():
    board = floor_board()
    goal = State.make([board.goal_pos], Orientation.STANDING)
    assert is_goal(board, goal)
    assert successors(board, goal) == []
    for state, action in [(goal, Action.LEFT), (board.initial_state(), Action.SPLIT_0_RIGHT)]:
        outcome = evaluate_action(board, state, action)
        assert outcome.reason == MoveResult.INVALID_ACTION
        assert outcome.state is None
        assert outcome.attempted_state is None


def test_coordinate_selection_survives_sorted_split_positions():
    board = floor_board()
    state = State.make([(1, 1), (1, 4)], Orientation.SPLIT)
    action = action_for_cube(state, Direction.DOWN, (1, 1))
    assert action == Action.SPLIT_0_DOWN
    moved = apply_action(board, state, action)
    assert moved.positions == ((1, 4), (2, 1))
    assert action_for_cube(moved, Direction.DOWN, (2, 1)) == Action.SPLIT_1_DOWN
    with pytest.raises(ValueError, match="not in this state"):
        action_for_cube(moved, Direction.DOWN, (0, 0))


def test_team_controller_tracks_selected_cube_after_sorting_and_reset():
    controller = SplitController(floor_board())
    controller.state = State.make([(1, 1), (1, 4)], Orientation.SPLIT)
    assert controller.active_cube_coord == (1, 1)
    assert controller.move(Direction.DOWN)
    assert controller.active_cube_coord == (2, 1)
    assert controller.active_cube_index == 1
    assert controller.switch_active_cube() == (1, 4)
    assert controller.move_count == 1
    controller.reset()
    assert controller.state == controller.board.initial_state()
    assert controller.active_cube_coord is None
    assert controller.move_count == 0
