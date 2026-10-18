"""A* with a safe zero heuristic unless a caller supplies another."""

from typing import Callable

from core.state import State

from ._best_first import _best_first
from .search_utils import SearchOptions, SearchProblem, SearchResult


def astar(
    problem: SearchProblem,
    options: SearchOptions | None = None,
    heuristic: Callable[[State], float] | None = None,
) -> SearchResult:
    """Find a shortest path when h is admissible, nonnegative and h(goal)=0.

    The default h=0 is admissible for every supported board, including split
    switches. A custom h receives core.State, not an AIMA Node. Plain Manhattan
    distance is not assumed admissible for rolling blocks or teleporting splits.
    """
    if heuristic is None:
        heuristic = lambda state: 0.0
    return _best_first(problem, options, heuristic, "A*")
