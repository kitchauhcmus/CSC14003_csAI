"""Shared search contract, compatible with the feature/bfs-dfs branch.

Transition.cost and SearchResult.solution_cost extend that contract without
changing its existing positional arguments or the four benchmark metrics.
"""

from dataclasses import dataclass, field
from math import isfinite
from typing import Callable, Iterable, Literal

from core.constants import Action
from core.state import State

Status = Literal["solved", "unsolvable", "timeout", "node_limit", "cancelled"]


def nonnegative_finite(value: float, name: str) -> float:
    """Validate costs and heuristic estimates before they reach the heap."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number.")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} must be finite and nonnegative.") from exc
    if not isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and nonnegative.")
    return number


@dataclass(frozen=True, slots=True)
class Transition:
    """A legal action, its resulting core State, and its nonnegative cost."""

    action: Action
    state: State
    cost: float = 1.0

    def __post_init__(self):
        if not isinstance(self.action, Action):
            raise TypeError("action must be an Action.")
        if not isinstance(self.state, State):
            raise TypeError("state must be a State.")
        object.__setattr__(self, "cost", nonnegative_finite(self.cost, "Transition.cost"))


@dataclass(frozen=True, slots=True)
class SearchProblem:
    """Connect a level's rules to a solver without duplicating game physics.

    successors must yield legal Transitions, including bridge updates, split
    actions, and rejoining cubes. is_goal decides whether a State wins the level.
    """

    initial_state: State
    is_goal: Callable[[State], bool]
    successors: Callable[[State], Iterable[Transition]]

    def __post_init__(self):
        if not isinstance(self.initial_state, State):
            raise TypeError("initial_state must be a State.")
        if not callable(self.is_goal) or not callable(self.successors):
            raise TypeError("is_goal and successors must be callable.")


@dataclass(slots=True)
class SearchMetrics:
    search_time: float = 0.0  # Seconds, including tracing overhead.
    memory_usage: int = 0  # Peak traced Python allocations during this search, bytes.
    expanded_nodes: int = 0  # Successor expansions; excludes goals and stale entries.
    solution_length: int | None = None  # Number of actions, or None if unsolved.

    def to_dict(self):
        return {
            "search_time": self.search_time,
            "memory_usage": self.memory_usage,
            "expanded_nodes": self.expanded_nodes,
            "solution_length": self.solution_length,
        }


@dataclass(slots=True)
class SearchResult:
    """Solution actions and core states, with the shared benchmark metrics."""

    algorithm: str
    status: Status
    actions: list[Action] = field(default_factory=list)
    states: list[State] = field(default_factory=list)
    metrics: SearchMetrics = field(default_factory=SearchMetrics)
    solution_cost: float | None = None

    @property
    def solved(self) -> bool:
        return self.status == "solved"

    def to_dict(self, include_states: bool = False):
        result = {
            "algorithm": self.algorithm,
            "status": self.status,
            "actions": [action.name for action in self.actions],
            "metrics": self.metrics.to_dict(),
            "solution_cost": self.solution_cost,
        }
        if include_states:
            result["states"] = [
                {
                    "positions": [list(position) for position in state.positions],
                    "orientation": state.orientation.name,
                    "active_bridges": [list(position) for position in sorted(state.active_bridges)],
                }
                for state in self.states
            ]
        return result


def reconstruct_path(
    goal: State, parents: dict[State, tuple[State, Action] | None]
) -> tuple[list[Action], list[State]]:
    """Recover actions and states in forward order, including start and goal."""
    state = goal
    actions, states = [], [state]
    while parents[state] is not None:
        previous, action = parents[state]
        actions.append(action)
        states.append(previous)
        state = previous
    return list(reversed(actions)), list(reversed(states))
