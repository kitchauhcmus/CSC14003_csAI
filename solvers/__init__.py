"""Public solver API used by the GUI integration layer."""

from .astar import astar
from .bfs import bfs
from .dfs import dfs
from .search_utils import SearchMetrics, SearchOptions, SearchProblem, SearchResult, Transition
from .ucs import ucs

SOLVERS = {"BFS": bfs, "DFS": dfs, "UCS": ucs, "A*": astar}

__all__ = [
    "bfs", "dfs", "ucs", "astar", "SOLVERS", "SearchProblem", "SearchResult",
    "SearchMetrics", "SearchOptions", "Transition",
]
