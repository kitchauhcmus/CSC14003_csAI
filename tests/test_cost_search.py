import json
from math import inf
import random
import tracemalloc
import unittest
from unittest.mock import patch

from core.constants import Action, Orientation
from core.state import State
from examples.solve_demo import make_problem
from solvers import (
    SearchProblem, Transition, astar, make_manhattan_heuristic, ucs,
)


def standing(column, bridges=frozenset()):
    return State(((0, column),), Orientation.STANDING, bridges)


def graph_problem(start, goal, graph):
    return SearchProblem(start, lambda state: state == goal, lambda state: graph.get(state, ()))


class CostSearchTests(unittest.TestCase):
    def assert_path(self, problem, result):
        self.assertTrue(result.solved)
        self.assertEqual(result.states[0], problem.initial_state)
        self.assertTrue(problem.is_goal(result.states[-1]))
        self.assertEqual(len(result.states), len(result.actions) + 1)
        self.assertEqual(result.metrics.solution_length, len(result.actions))
        cost = 0.0
        for source, action, target in zip(result.states, result.actions, result.states[1:]):
            matches = [
                edge for edge in problem.successors(source)
                if edge.action == action and edge.state == target
            ]
            self.assertTrue(matches, "Returned path must replay through legal transitions")
            cost += min(edge.cost for edge in matches)
        self.assertAlmostEqual(result.solution_cost, cost)

    def test_corridor_uses_core_states_and_actions(self):
        problem = make_problem()
        for solve in (ucs, astar):
            with self.subTest(solver=solve.__name__):
                result = solve(problem)
                self.assert_path(problem, result)
                self.assertEqual(result.actions, [Action.RIGHT, Action.RIGHT])
                self.assertEqual(result.solution_cost, 2)
                self.assertEqual(result.metrics.expanded_nodes, 2)
                self.assertGreater(result.metrics.memory_usage, 0)
                self.assertGreaterEqual(result.metrics.search_time, 0)

    def test_goal_at_start_and_no_solution(self):
        start, other = standing(0), standing(1)
        for solve in (ucs, astar):
            with self.subTest(solver=solve.__name__):
                result = solve(graph_problem(start, start, {}))
                self.assertEqual(result.states, [start])
                self.assertEqual(result.actions, [])
                self.assertEqual(result.solution_cost, 0)
                self.assertEqual(result.metrics.solution_length, 0)
                self.assertEqual(result.metrics.expanded_nodes, 0)
                result = solve(graph_problem(start, other, {}))
                self.assertFalse(result.solved)
                self.assertEqual(result.status, "unsolvable")
                self.assertEqual(result.states, [])
                self.assertEqual(result.actions, [])
                self.assertIsNone(result.solution_cost)
                self.assertIsNone(result.metrics.solution_length)
                self.assertEqual(result.metrics.expanded_nodes, 1)

    def test_cheaper_longer_path_beats_first_generated_goal(self):
        start, middle, goal = map(standing, range(3))
        graph = {
            start: [Transition(Action.RIGHT, goal, 9), Transition(Action.DOWN, middle, 1)],
            middle: [Transition(Action.RIGHT, goal, 1)],
        }
        problem = graph_problem(start, goal, graph)
        for solve in (ucs, astar):
            with self.subTest(solver=solve.__name__):
                result = solve(problem)
                self.assert_path(problem, result)
                self.assertEqual(result.solution_cost, 2)
                self.assertEqual(result.actions, [Action.DOWN, Action.RIGHT])

    def test_astar_reopens_state_for_inconsistent_admissible_heuristic(self):
        start, a, b, goal = map(standing, range(4))
        graph = {
            start: [Transition(Action.RIGHT, a, 3), Transition(Action.DOWN, b, 1)],
            a: [Transition(Action.RIGHT, goal, 3)],
            b: [Transition(Action.UP, a, 1)],
        }
        # h(b)=4 is admissible but h(b) > cost(b,a)+h(a); A expands twice.
        heuristic = {start: 5, a: 0, b: 4, goal: 0}
        problem = graph_problem(start, goal, graph)
        result = astar(problem, heuristic.__getitem__)
        self.assert_path(problem, result)
        self.assertEqual(result.states, [start, b, a, goal])
        self.assertEqual(result.solution_cost, 5)
        self.assertEqual(result.metrics.expanded_nodes, 4)

    def test_stale_heap_entries_do_not_expand_again(self):
        start, a, b, dead, goal = map(standing, range(5))
        graph = {
            start: [Transition(Action.RIGHT, a, 4), Transition(Action.DOWN, b)],
            b: [Transition(Action.UP, a)],
            a: [Transition(Action.RIGHT, dead)],
        }
        for solve in (ucs, astar):
            with self.subTest(solver=solve.__name__):
                result = solve(graph_problem(start, goal, graph))
                self.assertFalse(result.solved)
                self.assertEqual(result.metrics.expanded_nodes, 4)

    def test_zero_cost_cycle_terminates_and_reconstructs(self):
        start, middle, goal = map(standing, range(3))
        graph = {
            start: [Transition(Action.RIGHT, middle, 0)],
            middle: [Transition(Action.LEFT, start, 0), Transition(Action.RIGHT, goal, 0)],
        }
        problem = graph_problem(start, goal, graph)
        for solve in (ucs, astar):
            with self.subTest(solver=solve.__name__):
                result = solve(problem)
                self.assert_path(problem, result)
                self.assertEqual(result.solution_cost, 0)
                self.assertEqual(result.metrics.solution_length, 2)
                self.assertEqual(result.metrics.expanded_nodes, 2)

    def test_bridge_settings_are_part_of_search_identity(self):
        closed = standing(0)
        opened = standing(0, frozenset({(0, 1)}))
        goal = standing(3, opened.active_bridges)
        # A switch route returns to the same position with a different bridge set.
        switch = standing(-3)
        graph = {
            closed: [Transition(Action.LEFT, switch)],
            switch: [Transition(Action.RIGHT, opened)],
            opened: [Transition(Action.RIGHT, goal)],
        }
        problem = graph_problem(closed, goal, graph)
        for solve in (ucs, astar):
            with self.subTest(solver=solve.__name__):
                result = solve(problem)
                self.assert_path(problem, result)
                self.assertEqual(result.states, [closed, switch, opened, goal])
                self.assertEqual(result.states[0].positions, result.states[2].positions)

    def test_split_cube_actions_and_merge_survive_path_reconstruction(self):
        start = State(((0, 0), (0, 4)), Orientation.SPLIT)
        moved_0 = State(((0, 1), (0, 4)), Orientation.SPLIT)
        moved_1 = State(((0, 1), (0, 3)), Orientation.SPLIT)
        joined = State(((0, 1), (0, 2)), Orientation.HORIZONTAL)
        goal = standing(3)
        graph = {
            start: [Transition(Action.SPLIT_0_RIGHT, moved_0)],
            moved_0: [Transition(Action.SPLIT_1_LEFT, moved_1)],
            moved_1: [Transition(Action.SPLIT_1_LEFT, joined)],
            joined: [Transition(Action.RIGHT, goal)],
        }
        problem = graph_problem(start, goal, graph)
        for solve in (ucs, astar):
            with self.subTest(solver=solve.__name__):
                result = solve(problem)
                self.assert_path(problem, result)
                self.assertEqual(result.states, [start, moved_0, moved_1, joined, goal])
                self.assertEqual([a.cube_index for a in result.actions], [0, 1, 1, None])

    def test_equal_priorities_use_fifo_without_comparing_states(self):
        start, left, right, goal = map(standing, range(4))
        graph = {
            start: [Transition(Action.LEFT, left), Transition(Action.RIGHT, right)],
            left: [Transition(Action.DOWN, goal)],
            right: [Transition(Action.UP, goal)],
        }
        with patch.object(State, "__lt__", side_effect=AssertionError("State compared")):
            for solve in (ucs, astar):
                with self.subTest(solver=solve.__name__):
                    result = solve(graph_problem(start, goal, graph))
                    self.assertEqual(result.states, [start, left, goal])

    def test_custom_heuristic_receives_state(self):
        seen = []

        def heuristic(state):
            self.assertIsInstance(state, State)
            seen.append(state.positions)
            return 0

        result = astar(make_problem(), heuristic)
        self.assertTrue(result.solved)
        self.assertIn(((0, 1), (0, 2)), seen)

    def test_manhattan_bound_accounts_for_two_tile_rolls(self):
        problem = make_problem()
        heuristic = make_manhattan_heuristic((0, 3))
        self.assertEqual(heuristic(problem.initial_state), 2)
        self.assertEqual(heuristic(standing(3)), 0)
        self.assertEqual(make_manhattan_heuristic((0, 3), minimum_step_cost=0.25)(standing(0)), 0.5)
        result = astar(problem, heuristic)
        self.assert_path(problem, result)
        self.assertEqual(result.solution_cost, 2)

    def test_default_heuristic_is_safe_for_teleporting_successors(self):
        start, detour, goal = standing(0), standing(100), standing(3)
        split = State(((0, 1), (0, 4)), Orientation.SPLIT)
        graph = {
            start: [Transition(Action.RIGHT, goal, 8), Transition(Action.LEFT, detour)],
            detour: [Transition(Action.DOWN, split)],
            split: [Transition(Action.SPLIT_0_RIGHT, goal)],
        }
        problem = graph_problem(start, goal, graph)
        result = astar(problem)
        self.assert_path(problem, result)
        self.assertEqual(result.solution_cost, 3)

    def test_json_export_includes_core_fields_and_metrics(self):
        payload = json.loads(json.dumps(ucs(make_problem()).to_dict(include_states=True)))
        self.assertEqual(payload["actions"], ["RIGHT", "RIGHT"])
        self.assertEqual(payload["solution_cost"], 2)
        self.assertEqual(payload["states"][1], {
            "positions": [[0, 1], [0, 2]], "orientation": "HORIZONTAL", "active_bridges": [],
        })
        self.assertEqual(set(payload["metrics"]), {
            "search_time", "memory_usage", "expanded_nodes", "solution_length",
        })

    def test_old_import_paths_expose_new_contract_without_gui_dependencies(self):
        from algorithms import astar_search, uniform_cost_search
        from iama.algorithms import astar_search as old_astar, uniform_cost_search as old_ucs

        for solve in (uniform_cost_search, old_ucs):
            self.assertEqual(solve(make_problem()).solution_cost, 2)
        for solve in (astar_search, old_astar):
            self.assertEqual(solve(make_problem(), h=lambda state: 0).solution_cost, 2)

    def test_invalid_transition_costs_are_rejected(self):
        for cost in (-1, inf, -inf, float("nan"), 10 ** 400):
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                Transition(Action.RIGHT, standing(0), cost)
        for cost in ("1", True, None):
            with self.subTest(cost=cost), self.assertRaises(TypeError):
                Transition(Action.RIGHT, standing(0), cost)

    def test_invalid_core_inputs_are_rejected(self):
        with self.assertRaises(TypeError):
            Transition("RIGHT", standing(0))
        with self.assertRaises(TypeError):
            Transition(Action.RIGHT, ((0, 0),))
        with self.assertRaises(TypeError):
            SearchProblem(((0, 0),), lambda state: False, lambda state: ())
        with self.assertRaises(TypeError):
            SearchProblem(standing(0), False, lambda state: ())

    def test_invalid_heuristic_and_callback_errors_release_tracing(self):
        for estimate in (-1, inf, float("nan")):
            with self.subTest(estimate=estimate), self.assertRaises(ValueError):
                astar(make_problem(), lambda state: estimate)
            self.assertFalse(tracemalloc.is_tracing())

        def broken_successors(state):
            raise RuntimeError("rules failed")

        problem = SearchProblem(standing(0), lambda state: False, broken_successors)
        with self.assertRaisesRegex(RuntimeError, "rules failed"):
            ucs(problem)
        self.assertFalse(tracemalloc.is_tracing())
        self.assertTrue(ucs(make_problem()).solved)

    def test_existing_tracing_session_is_preserved(self):
        tracemalloc.start()
        try:
            for solve in (ucs, astar):
                with self.assertRaisesRegex(RuntimeError, "already in use"):
                    solve(make_problem())
                self.assertTrue(tracemalloc.is_tracing())
        finally:
            tracemalloc.stop()

    def test_path_cost_overflow_is_reported_and_tracing_is_released(self):
        start, middle, goal = map(standing, range(3))
        graph = {
            start: [Transition(Action.RIGHT, middle, 1e308)],
            middle: [Transition(Action.RIGHT, goal, 1e308)],
        }
        with self.assertRaisesRegex(ValueError, "path cost"):
            ucs(graph_problem(start, goal, graph))
        self.assertFalse(tracemalloc.is_tracing())

    def test_weighted_graphs_match_independent_bellman_ford_oracle(self):
        randomizer = random.Random(14003)
        states = [standing(i) for i in range(8)]
        actions = (Action.UP, Action.DOWN, Action.LEFT, Action.RIGHT)
        for case in range(30):
            graph = {
                state: [
                    Transition(action, child, randomizer.randint(0, 7))
                    for action, child in zip(actions, randomizer.sample(states, randomizer.randint(0, 4)))
                ]
                for state in states
            }
            # Reverse Bellman-Ford gives exact distances to the goal without a heap.
            distance = dict.fromkeys(states, inf)
            distance[states[-1]] = 0
            for _ in range(len(states) - 1):
                for state, edges in graph.items():
                    for edge in edges:
                        distance[state] = min(distance[state], edge.cost + distance[edge.state])
            # Lower each estimate independently: admissible, possibly inconsistent.
            estimates = {
                state: 0 if distance[state] == inf else distance[state] * randomizer.choice((0, 0.5, 1))
                for state in states
            }
            problem = graph_problem(states[0], states[-1], graph)
            for result in (ucs(problem), astar(problem, estimates.__getitem__)):
                with self.subTest(case=case, algorithm=result.algorithm):
                    if distance[states[0]] == inf:
                        self.assertFalse(result.solved)
                    else:
                        self.assert_path(problem, result)
                        self.assertEqual(result.solution_cost, distance[states[0]])


if __name__ == "__main__":
    unittest.main()
