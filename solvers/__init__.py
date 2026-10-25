"""Public solver entry points sharing the same search contract."""

from .astar import astar, astar_search
from .bfs import bfs
from .dfs import dfs
from .heuristics import make_manhattan_heuristic, zero_heuristic
from .search_utils import SearchMetrics, SearchProblem, SearchResult, Transition
from .ucs import ucs, uniform_cost_search

__all__ = [
    "bfs", "dfs", "ucs", "uniform_cost_search", "astar", "astar_search",
    "SearchProblem", "SearchResult", "SearchMetrics", "Transition",
    "make_manhattan_heuristic", "zero_heuristic",
]

