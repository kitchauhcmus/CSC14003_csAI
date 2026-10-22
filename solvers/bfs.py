from collections import deque
from time import perf_counter
import tracemalloc
from .search_utils import SearchProblem, SearchResult, SearchMetrics, reconstruct_path


def bfs(problem: SearchProblem) -> SearchResult:
    if tracemalloc.is_tracing():
        raise RuntimeError("tracemalloc đang được sử dụng; hãy chạy solver tuần tự.")
    metrics = SearchMetrics()
    result = SearchResult("BFS", "unsolvable", metrics=metrics)
    started = perf_counter()
    tracemalloc.start()
    try:
        start = problem.initial_state
        visited = {start}
        parents = {start: None}
        queue = deque([start])
        while queue:
            state = queue.popleft()
            if problem.is_goal(state):
                result.status = "solved"
                result.actions, result.states = reconstruct_path(state, parents)
                metrics.solution_length = len(result.actions)
                break
            metrics.expanded_nodes += 1
            for edge in problem.successors(state):
                child = edge.state
                if child in visited:
                    continue
                visited.add(child)
                parents[child] = (state, edge.action)
                queue.append(child)
    finally:
        try:
            metrics.memory_usage = tracemalloc.get_traced_memory()[1]
            metrics.search_time = perf_counter() - started
        finally:
            tracemalloc.stop()
    return result
