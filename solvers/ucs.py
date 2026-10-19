"""Uniform-cost search over core State and Action objects."""

from ._cost_search import cost_search
from .heuristics import zero_heuristic
from .search_utils import SearchProblem, SearchResult


def ucs(problem: SearchProblem) -> SearchResult:
    """Return a minimum-cost solution for finite, nonnegative-cost problems."""
    return cost_search(problem, zero_heuristic, "UCS")


uniform_cost_search = ucs
