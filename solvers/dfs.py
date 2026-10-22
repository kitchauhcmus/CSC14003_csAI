from time import perf_counter
import tracemalloc
from .search_utils import SearchProblem, SearchResult, SearchMetrics, reconstruct_path


def dfs(problem: SearchProblem) -> SearchResult:
    if tracemalloc.is_tracing():
        raise RuntimeError("tracemalloc đang được sử dụng; hãy chạy solver tuần tự.")
    metrics = SearchMetrics()
    result = SearchResult("DFS", "unsolvable", metrics=metrics)
    started = perf_counter()
    tracemalloc.start()
    try:
        start = problem.initial_state
        visited = {start}
        parents = {start: None}
        if problem.is_goal(start):
            result.status = "solved"
            result.actions, result.states = reconstruct_path(start, parents)
            metrics.solution_length = len(result.actions)
        else:
            metrics.expanded_nodes += 1
            stack = [(start, iter(problem.successors(start)))]
            while stack:
                _, children = stack[-1]
                edge = next(children, None)
                if edge is None:
                    stack.pop()
                    continue
                child = edge.state
                if child in visited:
                    continue
                visited.add(child)
                parents[child] = (stack[-1][0], edge.action)
                if problem.is_goal(child):
                    result.status = "solved"
                    result.actions, result.states = reconstruct_path(child, parents)
                    metrics.solution_length = len(result.actions)
                    break
                metrics.expanded_nodes += 1
                stack.append((child, iter(problem.successors(child))))
    finally:
        try:
            metrics.memory_usage = tracemalloc.get_traced_memory()[1]
            metrics.search_time = perf_counter() - started
        finally:
            tracemalloc.stop()
    return result
