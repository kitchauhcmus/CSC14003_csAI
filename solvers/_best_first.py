"""Unit-cost UCS/A* adapted to the shared core.State contract.

The team's cea2273 iama/algorithms.py and Erroler/Bloxorz use the AIMA
best-first formulation: UCS has f=g and A* has f=g+h. This implementation
uses stable heap entries and reopens states when a lower g is found.
"""

from heapq import heappop, heappush
from itertools import count
from math import isfinite
from typing import Callable

from core.state import State

from .search_utils import SearchOptions, SearchProblem, SearchResult, _SearchSession


def _best_first(
    problem: SearchProblem,
    options: SearchOptions | None,
    heuristic: Callable[[State], float],
    algorithm: str,
) -> SearchResult:
    result = SearchResult(algorithm, "unsolvable")
    with _SearchSession(result, options) as session:
        if session.interrupted():
            return result
        start = problem.initial_state
        # A start state already at the goal needs no heuristic or expansion.
        if problem.is_goal(start):
            return session.solve(start, {start: None})
        priorities = count()

        def estimate(state):
            value = float(heuristic(state))
            if not isfinite(value) or value < 0:
                raise ValueError("heuristic must return a finite nonnegative number")
            return value

        frontier = [(estimate(start), next(priorities), 0, start)]
        best_cost = {start: 0}
        parents = {start: None}
        while frontier:
            if session.interrupted():
                return result
            _, _, cost, state = heappop(frontier)
            if cost != best_cost[state]:
                continue
            if problem.is_goal(state):
                return session.solve(state, parents)
            if not session.can_expand():
                return result
            for edge in problem.successors(state):
                if session.interrupted():
                    return result
                child = edge.state
                child_cost = cost + 1
                if child_cost >= best_cost.get(child, float("inf")):
                    continue
                child_estimate = estimate(child)
                best_cost[child] = child_cost
                parents[child] = (state, edge.action)
                heappush(
                    frontier,
                    (child_cost + child_estimate, next(priorities), child_cost, child),
                )
        session.interrupted()
    return result
