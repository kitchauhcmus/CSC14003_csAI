"""Shared solver contract, based on origin/feature/bfs-dfs at cfab321.

Every transition costs one move. Times are seconds and memory_usage is the
process-wide peak Python allocation traced during this search, in bytes.
Only one traced search may run in a process at a time.
"""

from dataclasses import dataclass, field
from math import isfinite
from threading import Lock
from time import perf_counter
from typing import Callable, Iterable, Literal, Protocol
import tracemalloc

from core.constants import Action
from core.state import State

Status = Literal["solved", "unsolvable", "timeout", "node_limit", "cancelled"]


class CancellationSignal(Protocol):
    def is_set(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class Transition:
    action: Action
    state: State

    def __post_init__(self):
        if not isinstance(self.action, Action):
            raise TypeError("action must be an Action")
        if not isinstance(self.state, State):
            raise TypeError("state must be a State")


@dataclass(frozen=True, slots=True)
class SearchProblem:
    initial_state: State
    is_goal: Callable[[State], bool]
    successors: Callable[[State], Iterable[Transition]]

    def __post_init__(self):
        if not isinstance(self.initial_state, State):
            raise TypeError("initial_state must be a State")
        if not callable(self.is_goal) or not callable(self.successors):
            raise TypeError("is_goal and successors must be callable")


@dataclass(frozen=True, slots=True)
class SearchOptions:
    """Cooperative search limits; None disables the corresponding limit.

    Cancellation and timeout take precedence over checking the next goal.
    node_limit bounds the number of states whose successors are requested;
    goal states are checked before this limit and are not expanded.
    Checks run between states and transitions, not inside user callbacks.
    """

    timeout_seconds: float | None = 15.0
    node_limit: int | None = 150_000
    cancel_event: CancellationSignal | None = None

    def __post_init__(self):
        if self.timeout_seconds is not None:
            if not isfinite(self.timeout_seconds) or self.timeout_seconds < 0:
                raise ValueError("timeout_seconds must be finite and nonnegative, or None")
        if self.node_limit is not None:
            if type(self.node_limit) is not int or self.node_limit < 0:
                raise ValueError("node_limit must be a nonnegative integer, or None")
        if self.cancel_event is not None and not callable(
            getattr(self.cancel_event, "is_set", None)
        ):
            raise TypeError("cancel_event must provide is_set()")


@dataclass(slots=True)
class SearchMetrics:
    search_time: float = 0.0
    memory_usage: int = 0
    expanded_nodes: int = 0
    solution_length: int | None = None

    def to_dict(self):
        return {
            "search_time": self.search_time,
            "memory_usage": self.memory_usage,
            "expanded_nodes": self.expanded_nodes,
            "solution_length": self.solution_length,
        }


@dataclass(slots=True)
class SearchResult:
    algorithm: str
    status: Status
    actions: list[Action] = field(default_factory=list)
    states: list[State] = field(default_factory=list)
    metrics: SearchMetrics = field(default_factory=SearchMetrics)

    @property
    def solved(self) -> bool:
        return self.status == "solved"

    def to_dict(self, include_states: bool = False):
        result = {
            "algorithm": self.algorithm,
            "status": self.status,
            "actions": [action.name for action in self.actions],
            "metrics": self.metrics.to_dict(),
        }
        if include_states:
            result["states"] = [
                {
                    "positions": [list(position) for position in state.positions],
                    "orientation": state.orientation.name,
                    "active_bridges": [list(p) for p in sorted(state.active_bridges)],
                }
                for state in self.states
            ]
        return result


def reconstruct_path(goal, parents):
    state = goal
    actions, states = [], [state]
    while parents[state] is not None:
        previous, action = parents[state]
        actions.append(action)
        states.append(previous)
        state = previous
    return list(reversed(actions)), list(reversed(states))


_TRACE_LOCK = Lock()


class _SearchSession:
    """Own tracemalloc for one run and always release it on exceptions."""

    def __init__(self, result: SearchResult, options: SearchOptions | None):
        self.result = result
        self.options = options if options is not None else SearchOptions()
        self.started = 0.0

    def __enter__(self):
        if not _TRACE_LOCK.acquire(blocking=False):
            raise RuntimeError("Run solvers sequentially within each process")
        try:
            if tracemalloc.is_tracing():
                raise RuntimeError("tracemalloc is already active; run solvers sequentially")
            self.started = perf_counter()
            tracemalloc.start()
        except BaseException:
            _TRACE_LOCK.release()
            raise
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            self.result.metrics.memory_usage = tracemalloc.get_traced_memory()[1]
            self.result.metrics.search_time = perf_counter() - self.started
        finally:
            tracemalloc.stop()
            _TRACE_LOCK.release()
        return False

    def interrupted(self) -> bool:
        if self.options.cancel_event is not None and self.options.cancel_event.is_set():
            self.result.status = "cancelled"
            return True
        timeout = self.options.timeout_seconds
        if timeout is not None and perf_counter() - self.started >= timeout:
            self.result.status = "timeout"
            return True
        return False

    def can_expand(self) -> bool:
        limit = self.options.node_limit
        if limit is not None and self.result.metrics.expanded_nodes >= limit:
            self.result.status = "node_limit"
            return False
        self.result.metrics.expanded_nodes += 1
        return True

    def solve(self, state: State, parents) -> SearchResult:
        self.result.actions, self.result.states = reconstruct_path(state, parents)
        self.result.metrics.solution_length = len(self.result.actions)
        self.result.status = "solved"
        return self.result
