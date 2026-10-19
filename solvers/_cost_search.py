"""Priority-queue search shared by UCS and A*."""

from heapq import heappop, heappush
from itertools import count
from math import inf
from time import perf_counter
import tracemalloc

from .heuristics import Heuristic
from .search_utils import (
    SearchMetrics,
    SearchProblem,
    SearchResult,
    nonnegative_finite,
    reconstruct_path,
)


def cost_search(
    problem: SearchProblem, heuristic: Heuristic, algorithm: str
) -> SearchResult:
    # Match BFS/DFS's measurement contract; never stop a caller's tracing session.
    if tracemalloc.is_tracing():
        raise RuntimeError("tracemalloc is already in use; run solvers sequentially.")

    metrics = SearchMetrics()
    result = SearchResult(algorithm, "unsolvable", metrics=metrics)
    started = perf_counter()
    tracemalloc.start()
    try:
        start = problem.initial_state
        best_cost = {start: 0.0}
        parents = {start: None}
        sequence = count()
        initial_priority = nonnegative_finite(heuristic(start), "heuristic")
        # FIFO tie-breaks avoid comparing States (including their bridge sets).
        frontier = [(initial_priority, next(sequence), 0.0, start)]

        while frontier:
            _, _, cost, state = heappop(frontier)
            if cost != best_cost[state]:
                continue  # A cheaper entry for this complete State superseded it.

            # Test on removal, not generation: a cheaper goal path may still exist.
            if problem.is_goal(state):
                result.status = "solved"
                result.actions, result.states = reconstruct_path(state, parents)
                result.solution_cost = cost
                metrics.solution_length = len(result.actions)
                break

            metrics.expanded_nodes += 1
            for edge in problem.successors(state):
                candidate = nonnegative_finite(cost + edge.cost, "path cost")
                if candidate >= best_cost.get(edge.state, inf):
                    continue
                estimate = nonnegative_finite(heuristic(edge.state), "heuristic")
                priority = nonnegative_finite(candidate + estimate, "priority")
                best_cost[edge.state] = candidate
                parents[edge.state] = (state, edge.action)
                heappush(frontier, (priority, next(sequence), candidate, edge.state))
                # No permanent closed set: better paths reopen expanded states,
                # so A* also handles admissible but inconsistent heuristics.
    finally:
        try:
            metrics.memory_usage = tracemalloc.get_traced_memory()[1]
            metrics.search_time = perf_counter() - started
        finally:
            tracemalloc.stop()
    return result
