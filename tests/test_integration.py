"""Integration checks use actual rules, search algorithms and Windows spawn."""

import multiprocessing
import time

import pytest

from core.board import Board
from core.constants import Action, Direction, Orientation
from core.rules import apply_action, is_goal
from integration import GameSession, PlaybackController, SolverRunner, make_search_problem
from solvers import SOLVERS, SearchResult


def straight_board():
    return Board.from_dict({"grid": ["S.....G"], "name": "Straight"})


def split_board():
    return Board.from_dict({
        "grid": [".......", ".......", "S..(...", ".......", ".......", "......G"],
        "split_switches": [{"pos": [2, 3], "spawn_positions": [[1, 1], [1, 4]]}],
    })


def wait_for_result(runner, seconds=8):
    deadline = time.monotonic() + seconds
    result = None
    while runner.running and time.monotonic() < deadline:
        result = runner.poll()
        if result is not None:
            break
        time.sleep(0.01)
    assert not runner.running, "Worker did not finish in the test deadline"
    return result


def test_session_fall_undo_and_reset_keep_last_valid_state():
    session = GameSession(straight_board())
    initial = session.state
    assert not session.move(Direction.UP)
    assert (session.state, session.status, session.move_count) == (initial, "lost", 1)
    assert not session.move(Direction.RIGHT)
    assert session.move_count == 1
    assert session.undo()
    assert (session.state, session.status, session.move_count) == (initial, "playing", 0)
    assert session.move(Direction.RIGHT)
    session.reset()
    assert (session.state, session.status, session.move_count) == (initial, "playing", 0)
    assert not session.undo()


def test_split_selection_follows_coordinates_when_sort_order_changes():
    session = GameSession(split_board())
    assert session.move(Direction.RIGHT)
    assert session.move(Direction.RIGHT)
    split_start = session.state
    assert session.state.orientation == Orientation.SPLIT
    assert session.selected_position == (1, 1)
    assert session.move(Direction.DOWN)
    # The same cube changed from index 0 to index 1 after canonical sorting.
    assert session.state.positions == ((1, 4), (2, 1))
    assert session.selected_position == (2, 1)
    assert session.move(Direction.RIGHT)
    assert session.state.positions == ((1, 4), (2, 2))
    assert session.selected_position == (2, 2)
    assert session.select_next_cube()
    assert session.selected_position == (1, 4)
    assert session.move(Direction.LEFT)
    assert session.undo()
    assert session.selected_position == (1, 4)
    assert session.undo()
    assert session.selected_position == (2, 1)
    assert session.undo()
    assert session.state == split_start
    assert session.selected_position == (1, 1)
    assert session.move_count == 2
    session.reset()
    assert session.selected_position is None
    assert session.move_count == 0


@pytest.mark.parametrize("algorithm", ["BFS", "DFS", "UCS", "A*"])
def test_solver_adapter_and_playback_use_same_rules(algorithm):
    board = straight_board()
    session = GameSession(board)
    result = SOLVERS[algorithm](make_search_problem(board))
    assert result.solved
    playback = PlaybackController(session)
    playback.load(result)
    for before, action, expected in zip(result.states, result.actions, result.states[1:]):
        assert session.state == before
        assert apply_action(board, before, action) == expected
        assert playback.step_forward()
        assert session.state == expected
    assert is_goal(board, session.state)
    assert session.status == "won"
    assert not playback.step_forward()
    assert playback.step_back()
    assert session.status == "playing"
    assert playback.step_forward()
    assert session.status == "won"


def test_playback_solves_from_midgame_and_has_its_own_timeline():
    board = straight_board()
    session = GameSession(board)
    assert session.move(Direction.RIGHT)
    current = session.state
    result = SOLVERS["BFS"](make_search_problem(board, current))
    assert result.states[0] == current
    playback = PlaybackController(session)
    playback.load(result)
    assert not session.undo()  # Earlier manual play is outside the replay timeline.
    assert session.move_count == 1
    playback.play()
    playback.update(0.49)
    assert playback.index == 0
    playback.update(0.01)
    assert playback.index == 1
    playback.pause()
    playback.update(10)
    assert playback.index == 1
    playback.speed = 4
    playback.play()
    playback.update(1)
    assert session.status == "won"
    assert session.move_count == 4
    assert not playback.playing
    playback.restart()
    assert (playback.index, session.state, session.move_count) == (0, current, 1)
    assert session.status == "playing"


def test_playback_rejects_invalid_path_without_mutating_game():
    board = straight_board()
    session = GameSession(board)
    result = SOLVERS["BFS"](make_search_problem(board))
    result.actions[0] = Action.UP
    playback = PlaybackController(session)
    with pytest.raises(ValueError, match="invalid transition"):
        playback.load(result)
    assert session.state == board.initial_state()
    assert not playback.has_result
    with pytest.raises(ValueError):
        playback.load(SearchResult("BFS", "unsolvable"))


def test_playback_stops_when_manual_play_changes_state():
    board = straight_board()
    session = GameSession(board)
    playback = PlaybackController(session)
    playback.load(SOLVERS["BFS"](make_search_problem(board)))
    session.move(Direction.RIGHT)
    assert not playback.step_forward()
    assert playback.error
    playback.restart()
    assert playback.step_forward()


def test_playback_speed_change_keeps_fractional_step_progress():
    board = straight_board()
    playback = PlaybackController(GameSession(board))
    playback.load(SOLVERS["BFS"](make_search_problem(board)))
    playback.speed = 0.5
    playback.play()
    playback.update(1.9)
    assert playback.index == 0
    playback.speed = 4
    playback.update(0.01)
    assert playback.index == 0
    playback.update(0.01)
    assert playback.index == 1
    assert playback.playing


def test_runner_spawn_result_replacement_and_cleanup():
    board = straight_board()
    initial = board.initial_state()
    midgame = apply_action(board, initial, Action.RIGHT)
    with SolverRunner() as runner:
        first_job = runner.start(board, initial, "BFS")
        old_pid = runner._process.pid
        next_job = runner.start(board, midgame, "UCS")
        assert next_job > first_job
        result = wait_for_result(runner)
        assert runner.error is None
        assert result.solved and result.algorithm == "UCS"
        assert result.states[0] == midgame
        assert is_goal(board, result.states[-1])
        assert old_pid not in {child.pid for child in multiprocessing.active_children()}
        runner.start(board, initial, "BFS")
        cancelled_pid = runner._process.pid
        runner.cancel()
        assert not runner.running and runner.poll() is None
        assert cancelled_pid not in {child.pid for child in multiprocessing.active_children()}


def test_runner_timeout_is_a_search_result_and_releases_process():
    board = straight_board()
    with SolverRunner() as runner:
        runner.start(board, board.initial_state(), "BFS", timeout_seconds=0.000001)
        result = wait_for_result(runner)
        assert runner.error is None
        assert result.status == "timeout"
        assert not runner.running


class BrokenBoard(Board):
    def tile_at(self, *position):
        if getattr(self, "_frozen", False):
            raise RuntimeError("worker failure test")
        return super().tile_at(*position)


def test_runner_surfaces_worker_errors_and_can_start_again():
    valid_board = straight_board()
    board = BrokenBoard(valid_board.grid, valid_board.start_pos)
    with SolverRunner() as runner:
        runner.start(board, board.initial_state(), "BFS")
        assert wait_for_result(runner) is None
        assert "worker failure test" in runner.error
        runner.start(valid_board, valid_board.initial_state(), "BFS")
        assert wait_for_result(runner).solved
        assert runner.error is None


class SlowBoard(Board):
    def tile_at(self, *position):
        if getattr(self, "_frozen", False):
            time.sleep(3)  # Simulate a callback that cannot observe cancellation.
        return super().tile_at(*position)


def test_runner_hard_deadline_stops_a_stalled_worker_without_orphans():
    valid_board = straight_board()
    board = SlowBoard(valid_board.grid, valid_board.start_pos)
    with SolverRunner() as runner:
        runner.start(board, board.initial_state(), "BFS", timeout_seconds=0.01)
        worker_pid = runner._process.pid
        assert wait_for_result(runner) is None
        assert "time limit" in runner.error
        assert worker_pid not in {child.pid for child in multiprocessing.active_children()}
