"""Local integration regressions using the real engine and original solvers."""

import multiprocessing as mp
from pathlib import Path
from time import monotonic, sleep

import pytest

from core.board import Board
from core.constants import Action, Direction, MoveResult, Orientation
from core.rules import apply_action, is_goal
from core.state import State
from integration.playback import PlaybackController
from integration.search_problem import make_search_problem
from integration.session import GameSession
from integration.solver_runner import SOLVERS, SolverRunner
from solvers import SearchResult, bfs


def corridor():
    return Board.from_dict({"name": "Integration corridor", "grid": ["S..G"]})


def wait_result(runner, seconds=15):
    deadline = monotonic() + seconds
    result = None
    while runner.running and monotonic() < deadline:
        result = runner.poll()
        if result is not None:
            return result
        sleep(0.01)
    assert not runner.running, "Spawned solver did not finish within the test deadline"
    return result


def assert_clean(runner, pid):
    assert not runner.running
    assert runner.process is None
    assert runner.receiver is None
    assert pid not in {process.pid for process in mp.active_children()}


def test_session_failed_move_keeps_valid_state_and_undo_restores_failure_fields():
    board = corridor()
    session = GameSession(board)
    initial = session.state
    assert not session.move(Direction.LEFT)
    assert session.status == "lost"
    assert session.state == initial
    assert session.last_failure == MoveResult.FELL_VOID
    assert session.last_attempt_state.positions == ((0, -2), (0, -1))
    assert session.move_count == 1
    assert not session.move(Direction.RIGHT)
    assert session.move_count == 1
    assert session.undo()
    assert session.status == "playing"
    assert session.state == initial
    assert session.last_failure == MoveResult.OK
    assert session.last_attempt_state is None
    assert session.move_count == 0
    assert not session.undo()


def test_session_win_undo_and_reset_have_independent_histories():
    session = GameSession(corridor())
    assert session.move(Direction.RIGHT)
    lying = session.state
    assert session.move(Direction.RIGHT)
    assert session.status == "won" and session.move_count == 2
    assert not session.move(Direction.LEFT)
    assert session.undo()
    assert session.state == lying and session.status == "playing"
    assert session.move_count == 1
    session.reset()
    assert session.state == session.board.initial_state()
    assert session.move_count == 0 and session.status == "playing"
    assert not session.undo()


def test_session_follows_selected_split_coordinate_when_sorted_index_changes():
    board = Board.from_dict({"grid": ["S....G", "......", "......", "......"]})
    session = GameSession(board)
    initial = State.make(((1, 1), (1, 4)), Orientation.SPLIT)
    session._begin_at(initial, selected_position=(1, 1))
    assert session.move(Direction.DOWN)
    assert session.state.positions == ((1, 4), (2, 1))
    assert session.selected_position == (2, 1)
    assert session.move(Direction.RIGHT)
    assert session.state.positions == ((1, 4), (2, 2))
    assert session.selected_position == (2, 2)
    assert session.select_next_cube()
    assert session.selected_position == (1, 4)
    assert session.undo()
    assert session.selected_position == (2, 1)
    assert session.undo()
    assert session.state == initial and session.selected_position == (1, 1)


def test_session_rejects_action_orientation_mismatch_without_consuming_move():
    session = GameSession(corridor())
    with pytest.raises(ValueError):
        session.apply_action(Action.SPLIT_0_RIGHT)
    with pytest.raises(TypeError):
        session.move("RIGHT")
    assert session.state == session.board.initial_state()
    assert session.move_count == 0 and not session.undo()


def test_playback_validates_transition_path_before_replacing_session():
    board = corridor()
    session = GameSession(board)
    playback = PlaybackController(session)
    valid = bfs(make_search_problem(board))
    broken = SearchResult("BFS", "solved", [Action.LEFT, Action.RIGHT], valid.states)
    with pytest.raises(ValueError, match="invalid transition"):
        playback.load(broken)
    assert session.state == board.initial_state()
    assert session.move_count == 0 and not playback.has_result
    with pytest.raises(ValueError, match="complete state path"):
        playback.load(SearchResult("BFS", "unsolvable"))
    with pytest.raises(ValueError, match="goal"):
        playback.load(SearchResult("BFS", "solved", [Action.RIGHT], valid.states[:2]))


def test_playback_can_start_at_current_midgame_state_and_step_back_from_win():
    board = corridor()
    session = GameSession(board)
    session.move(Direction.RIGHT)
    midgame = session.state
    result = bfs(make_search_problem(board, midgame))
    playback = PlaybackController(session)
    playback.load(result)
    assert result.states[0] == midgame and len(result.actions) == 1
    assert session.move_count == 1 and not session.undo()
    assert playback.step_forward()
    assert session.status == "won" and session.move_count == 2
    assert playback.step_back()
    assert session.state == midgame and session.move_count == 1
    assert session.status == "playing" and playback.index == 0
    assert playback.step_forward()
    playback.restart()
    assert session.state == midgame and session.move_count == 1
    assert not session.undo()


def test_playback_stops_when_game_state_diverges_then_restart_recovers():
    board = corridor()
    session = GameSession(board)
    playback = PlaybackController(session)
    playback.load(bfs(make_search_problem(board)))
    session.move(Direction.RIGHT)
    assert not playback.step_forward()
    assert playback.error and not playback.playing and playback.index == 0
    playback.restart()
    assert playback.error is None and session.state == board.initial_state()
    assert playback.step_forward()


def test_playback_retains_elapsed_time_while_scene_busy_and_limits_frame_steps():
    board = corridor()
    session = GameSession(board)
    playback = PlaybackController(session)
    playback.load(bfs(make_search_problem(board)))
    playback.play()
    playback.update(1.0, max_steps=0)
    assert playback.index == 0 and session.move_count == 0
    playback.update(0, max_steps=1)
    assert playback.index == 1 and session.status == "playing"
    playback.update(0, max_steps=1)
    assert playback.index == 2 and session.status == "won"
    assert not playback.playing


def test_playback_speed_change_preserves_fraction_of_current_step():
    board = corridor()
    playback = PlaybackController(GameSession(board))
    playback.load(bfs(make_search_problem(board)))
    playback.play()
    playback.update(0.25)
    playback.speed = 4
    playback.update(0.124)
    assert playback.index == 0
    playback.update(0.002)
    assert playback.index == 1
    for invalid in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            playback.speed = invalid
    for invalid in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            playback.update(invalid)
    for invalid in (-1, True, 0.5):
        with pytest.raises(ValueError):
            playback.update(0, max_steps=invalid)


@pytest.mark.parametrize("algorithm", tuple(SOLVERS))
def test_runner_spawn_real_board_with_every_original_algorithm(algorithm):
    board = corridor()
    runner = SolverRunner()
    try:
        runner.start(board, board.initial_state(), algorithm, timeout_seconds=10)
        pid = runner.process.pid
        result = wait_result(runner)
        assert result is not None, runner.error
        assert result.solved and result.algorithm == algorithm
        assert result.actions == [Action.RIGHT, Action.RIGHT]
        assert result.states[0] == board.initial_state()
        assert is_goal(board, result.states[-1])
        assert result.metrics.solution_length == 2
        assert result.metrics.expanded_nodes == 2
        assert result.metrics.memory_usage > 0
        assert runner.completion_status == "solved" and runner.error is None
        assert_clean(runner, pid)
    finally:
        runner.close()


def test_runner_tiny_timeout_returns_no_result_or_invented_metrics_and_reaps():
    # A broad board prevents a completed search winning the result/deadline race.
    board = Board.from_dict({"grid": ["S" + "." * 79] + ["." * 80] * 78 + ["." * 79 + "G"]})
    runner = SolverRunner()
    try:
        runner.start(board, board.initial_state(), "BFS", timeout_seconds=0.000001)
        pid = runner.process.pid
        assert wait_result(runner) is None
        assert runner.completion_status == "timeout"
        assert "metrics are unavailable" in runner.error
        assert_clean(runner, pid)
    finally:
        runner.close()


def test_runner_cancel_cleans_child_and_connection_and_does_not_return_old_result():
    board = corridor()
    runner = SolverRunner()
    try:
        runner.start(board, board.initial_state(), "BFS")
        pid, receiver = runner.process.pid, runner.receiver
        runner.cancel()
        assert runner.completion_status == "cancelled" and receiver.closed
        assert runner.poll() is None
        assert_clean(runner, pid)
    finally:
        runner.close()


def test_runner_replacing_level_discards_previous_job_and_returns_new_root():
    old_board = corridor()
    new_board = Board.from_dict({"name": "Replacement", "grid": ["S.....G"]})
    root = apply_action(new_board, new_board.initial_state(), Action.RIGHT)
    runner = SolverRunner()
    try:
        runner.start(old_board, old_board.initial_state(), "BFS")
        old_pid, old_receiver, old_job = runner.process.pid, runner.receiver, runner._job_id
        runner.start(new_board, root, "UCS", timeout_seconds=10)
        new_pid = runner.process.pid
        assert runner._job_id > old_job and old_receiver.closed
        assert old_pid not in {process.pid for process in mp.active_children()}
        result = wait_result(runner)
        assert result is not None, runner.error
        assert result.algorithm == "UCS" and result.states[0] == root
        assert is_goal(new_board, result.states[-1])
        assert not is_goal(old_board, result.states[-1])
        assert_clean(runner, new_pid)
    finally:
        runner.close()


@pytest.mark.parametrize("algorithm", tuple(SOLVERS))
@pytest.mark.parametrize("path", sorted((Path(__file__).resolve().parents[1] / "levels").glob("*.json")), ids=lambda p: p.stem)
def test_demo_level_solutions_replay_through_real_engine(path, algorithm):
    board = Board.from_json(path)
    result = SOLVERS[algorithm](make_search_problem(board))
    assert result.solved, f"{path.name}: {algorithm} returned {result.status}"
    assert len(result.states) == len(result.actions) + 1
    assert result.states[0] == board.initial_state()
    assert is_goal(board, result.states[-1])
    for before, action, after in zip(result.states, result.actions, result.states[1:]):
        assert apply_action(board, before, action) == after
