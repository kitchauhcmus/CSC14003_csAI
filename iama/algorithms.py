"""Compatibility import path for the refactored UCS and A* solvers.

Both functions now take SearchProblem and return SearchResult. Heuristics
receive core.state.State directly, rather than an AIMA Node.
"""

from solvers import astar_search, uniform_cost_search

__all__ = ["astar_search", "uniform_cost_search"]
