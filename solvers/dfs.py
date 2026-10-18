"""Iterative DFS based on origin/feature/bfs-dfs at cfab321."""

from .search_utils import SearchOptions, SearchProblem, SearchResult, _SearchSession


def dfs(problem: SearchProblem, options: SearchOptions | None = None) -> SearchResult:
    """Find a path using successor order; it need not be shortest."""
    result = SearchResult("DFS", "unsolvable")
    with _SearchSession(result, options) as session:
        start = problem.initial_state
        visited = {start}
        parents = {start: None}
        if session.interrupted():
            return result
        if problem.is_goal(start):
            return session.solve(start, parents)
        if not session.can_expand():
            return result
        stack = [(start, iter(problem.successors(start)))]
        while stack:
            if session.interrupted():
                return result
            state, children = stack[-1]
            edge = next(children, None)
            if edge is None:
                stack.pop()
                continue
            if session.interrupted():
                return result
            child = edge.state
            if child in visited:
                continue
            visited.add(child)
            parents[child] = (state, edge.action)
            if problem.is_goal(child):
                return session.solve(child, parents)
            if not session.can_expand():
                return result
            stack.append((child, iter(problem.successors(child))))
        session.interrupted()
    return result
