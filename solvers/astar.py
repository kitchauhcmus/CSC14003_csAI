"""A* search over core State and Action objects."""

from ._cost_search import cost_search
from .heuristics import Heuristic, zero_heuristic
from .search_utils import SearchProblem, SearchResult


def astar(
    problem: SearchProblem, heuristic: Heuristic | None = None
) -> SearchResult:
    """Find a minimum-cost path with an admissible, nonnegative heuristic.

    The heuristic receives a State, estimates remaining cost, and must be zero
    at goals. A zero heuristic is the safe default, giving UCS's search order.
    Inconsistent admissible heuristics are supported by reopening states.
    """
    return cost_search(
        problem, zero_heuristic if heuristic is None else heuristic, "A*"
    )


def astar_search(problem: SearchProblem, h: Heuristic | None = None) -> SearchResult:
    """Preserve the old function name and h keyword with the new core API."""
    return astar(problem, h)
