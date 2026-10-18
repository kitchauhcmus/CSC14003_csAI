"""Uniform-cost search for transitions that each cost one move."""

from ._best_first import _best_first
from .search_utils import SearchOptions, SearchProblem, SearchResult


def ucs(problem: SearchProblem, options: SearchOptions | None = None) -> SearchResult:
    return _best_first(problem, options, lambda state: 0.0, "UCS")
