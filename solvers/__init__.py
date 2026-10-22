"""UCS and A* using the same search contract as the BFS/DFS feature branch."""

from .astar import astar, astar_search
from .heuristics import make_manhattan_heuristic, zero_heuristic
from .search_utils import SearchMetrics, SearchProblem, SearchResult, Transition
from .ucs import ucs, uniform_cost_search

__all__ = [
    "ucs", "uniform_cost_search", "astar", "astar_search",
    "SearchProblem", "SearchResult", "SearchMetrics", "Transition",
    "make_manhattan_heuristic", "zero_heuristic",
]
from .bfs import bfs
from .dfs import dfs
from .search_utils import SearchProblem, SearchResult, SearchMetrics, Transition

__all__ = ["bfs", "dfs", "SearchProblem", "SearchResult", "SearchMetrics", "Transition"]
