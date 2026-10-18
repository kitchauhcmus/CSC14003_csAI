"""BFS based on the team's origin/feature/bfs-dfs implementation at cfab321."""

from collections import deque

from .search_utils import SearchOptions, SearchProblem, SearchResult, _SearchSession


def bfs(problem: SearchProblem, options: SearchOptions | None = None) -> SearchResult:
    """Find a shortest path in the unit-cost transition graph."""
    result = SearchResult("BFS", "unsolvable")
    with _SearchSession(result, options) as session:
        start = problem.initial_state
        visited = {start}
        parents = {start: None}
        queue = deque([start])
        while queue:
            if session.interrupted():
                return result
            state = queue.popleft()
            if problem.is_goal(state):
                return session.solve(state, parents)
            if not session.can_expand():
                return result
            for edge in problem.successors(state):
                if session.interrupted():
                    return result
                child = edge.state
                if child in visited:
                    continue
                visited.add(child)
                parents[child] = (state, edge.action)
                queue.append(child)
        # An exhausted successor callback may itself have consumed the budget.
        session.interrupted()
    return result
