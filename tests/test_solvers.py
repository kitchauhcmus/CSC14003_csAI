"""Behavioral checks for the common unit-cost solver contract."""

from itertools import count
import json
from threading import Event
import tracemalloc

import pytest

from core.constants import Action, Orientation
from core.state import State
from solvers import SOLVERS, SearchOptions, SearchProblem, Transition, astar, bfs
import solvers.search_utils as search_utils


def state(number):
    return State.make([(0, number)], Orientation.STANDING)


def graph_problem(graph, goal=9):
    def successors(current):
        number = current.positions[0][1]
        return [Transition(action, state(target)) for action, target in graph.get(number, [])]

    return SearchProblem(state(0), lambda current: current == state(goal), successors)


@pytest.fixture(params=list(SOLVERS), ids=list(SOLVERS))
def solver(request):
    return SOLVERS[request.param]


def test_path_contains_initial_goal_and_matching_actions(solver):
    problem = graph_problem({0: [(Action.RIGHT, 1)], 1: [(Action.DOWN, 2)]}, goal=2)
    result = solver(problem)
    assert result.solved
    assert result.actions == [Action.RIGHT, Action.DOWN]
    assert result.states == [state(0), state(1), state(2)]
    assert len(result.states) == len(result.actions) + 1
    assert result.metrics.solution_length == 2
    assert result.metrics.expanded_nodes == 2
    assert result.metrics.search_time >= 0
    assert isinstance(result.metrics.memory_usage, int)
    assert result.metrics.memory_usage >= 0
    payload = json.loads(json.dumps(result.to_dict(include_states=True)))
    assert payload["actions"] == ["RIGHT", "DOWN"]
    assert payload["states"][0]["orientation"] == "STANDING"
    assert payload["metrics"]["solution_length"] == 2


def test_initial_goal_needs_no_expansion_even_with_zero_node_budget(solver):
    result = solver(graph_problem({}, goal=0), SearchOptions(node_limit=0))
    assert result.solved
    assert result.actions == []
    assert result.states == [state(0)]
    assert result.metrics.expanded_nodes == 0
    assert result.metrics.solution_length == 0


def test_exhausted_cyclic_graph_is_unsolvable(solver):
    result = solver(graph_problem({0: [(Action.RIGHT, 1)], 1: [(Action.LEFT, 0)]}))
    assert result.status == "unsolvable"
    assert not result.solved
    assert result.actions == result.states == []
    assert result.metrics.solution_length is None
    assert result.metrics.expanded_nodes == 2


@pytest.mark.parametrize("budget", [0, 1])
def test_node_limit_never_expands_more_than_budget(solver, budget):
    problem = graph_problem({0: [(Action.RIGHT, 1)], 1: [(Action.DOWN, 2)]}, goal=2)
    result = solver(problem, SearchOptions(node_limit=budget))
    assert result.status == "node_limit"
    assert result.metrics.expanded_nodes == budget
    assert result.actions == result.states == []
    assert result.metrics.solution_length is None


def test_goal_after_last_permitted_expansion_is_still_solved(solver):
    problem = graph_problem({0: [(Action.RIGHT, 1)], 1: [(Action.DOWN, 2)]}, goal=2)
    result = solver(problem, SearchOptions(node_limit=2))
    assert result.solved
    assert result.metrics.expanded_nodes == 2


def test_zero_timeout_exits_without_expanding(solver):
    result = solver(graph_problem({}), SearchOptions(timeout_seconds=0))
    assert result.status == "timeout"
    assert result.metrics.expanded_nodes == 0
    assert result.metrics.solution_length is None


def test_timeout_is_checked_during_search_without_sleeping(solver, monkeypatch):
    ticks = count()
    monkeypatch.setattr(search_utils, "perf_counter", lambda: next(ticks) * 0.1)
    graph = {i: [(Action.RIGHT, i + 1)] for i in range(100)}
    result = solver(graph_problem(graph, goal=100), SearchOptions(timeout_seconds=0.25))
    assert result.status == "timeout"
    assert result.metrics.search_time >= 0.25
    assert result.actions == result.states == []


def test_already_cancelled_search_exits_without_expanding(solver):
    event = Event()
    event.set()
    result = solver(graph_problem({}), SearchOptions(cancel_event=event))
    assert result.status == "cancelled"
    assert result.metrics.expanded_nodes == 0


def test_cancel_during_successor_generation_discards_partial_path(solver):
    event = Event()

    def successors(current):
        event.set()
        return [Transition(Action.RIGHT, state(1))]

    problem = SearchProblem(state(0), lambda current: False, successors)
    result = solver(problem, SearchOptions(cancel_event=event))
    assert result.status == "cancelled"
    assert result.metrics.expanded_nodes == 1
    assert result.actions == result.states == []
    assert result.metrics.solution_length is None


def test_cancellation_inside_empty_successor_callback_is_not_unsolvable(solver):
    event = Event()

    def successors(current):
        event.set()
        return []

    problem = SearchProblem(state(0), lambda current: False, successors)
    result = solver(problem, SearchOptions(cancel_event=event))
    assert result.status == "cancelled"
    assert result.metrics.expanded_nodes == 1


def test_search_exception_releases_tracing_and_allows_next_run(solver):
    def broken_successors(current):
        raise RuntimeError("invalid level transition")

    problem = SearchProblem(state(0), lambda current: False, broken_successors)
    with pytest.raises(RuntimeError, match="invalid level transition"):
        solver(problem)
    assert not tracemalloc.is_tracing()
    assert solver(graph_problem({}, goal=0)).solved


def test_external_trace_is_not_stopped_or_reused(solver):
    tracemalloc.start()
    try:
        with pytest.raises(RuntimeError, match="already active"):
            solver(graph_problem({}, goal=0))
        assert tracemalloc.is_tracing()
    finally:
        tracemalloc.stop()
    assert solver(graph_problem({}, goal=0)).solved


def test_shortest_searches_agree_on_unit_cost_and_dfs_uses_successor_order():
    problem = graph_problem(
        {
            0: [(Action.RIGHT, 1), (Action.DOWN, 2)],
            1: [(Action.RIGHT, 3)],
            3: [(Action.RIGHT, 4)],
            4: [(Action.DOWN, 5)],
            2: [(Action.RIGHT, 5)],
        },
        goal=5,
    )
    for name in ["BFS", "UCS", "A*"]:
        result = SOLVERS[name](problem)
        assert result.metrics.solution_length == 2
        assert result.actions == [Action.DOWN, Action.RIGHT]
    assert SOLVERS["DFS"](problem).metrics.solution_length == 4


def test_astar_reopens_a_state_for_an_admissible_inconsistent_heuristic():
    # Via 1,3,4 the goal costs 5; via 2,4 it costs 4. h(2)=3 is exact
    # but inconsistent with edge 2->4, so state 4 must be reopened.
    graph = {
        0: [(Action.RIGHT, 1), (Action.DOWN, 2)],
        1: [(Action.RIGHT, 3)],
        3: [(Action.RIGHT, 4)],
        2: [(Action.RIGHT, 4)],
        4: [(Action.DOWN, 5)],
        5: [(Action.RIGHT, 6)],
    }
    original = graph_problem(graph, goal=6)
    expanded = []

    def successors(current):
        expanded.append(current)
        return original.successors(current)

    problem = SearchProblem(original.initial_state, original.is_goal, successors)
    result = astar(problem, heuristic=lambda current: 3 if current == state(2) else 0)
    assert result.solved
    assert result.metrics.solution_length == 4
    assert result.states == [state(i) for i in [0, 2, 4, 5, 6]]
    assert expanded.count(state(4)) == 2


@pytest.mark.parametrize("estimate", [float("nan"), float("inf"), -1])
def test_invalid_heuristic_does_not_leave_tracemalloc_running(estimate):
    with pytest.raises(ValueError, match="heuristic"):
        astar(graph_problem({}), heuristic=lambda current: estimate)
    assert not tracemalloc.is_tracing()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"timeout_seconds": -1},
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": float("inf")},
        {"node_limit": -1},
        {"node_limit": 1.5},
    ],
)
def test_invalid_search_limits_are_rejected(kwargs):
    with pytest.raises(ValueError):
        SearchOptions(**kwargs)


def test_nested_solver_does_not_interfere_with_outer_trace():
    def nested_search(current):
        bfs(graph_problem({}, goal=0))
        return []

    with pytest.raises(RuntimeError, match="sequentially"):
        bfs(SearchProblem(state(0), lambda current: False, nested_search))
    assert not tracemalloc.is_tracing()
    assert bfs(graph_problem({}, goal=0)).solved
