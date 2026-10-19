"""Heuristics consume the shared core State, never a search Node."""

from typing import Callable

from core.state import State
from .search_utils import nonnegative_finite

Heuristic = Callable[[State], float]


def zero_heuristic(state: State) -> float:
    """Safe for every nonnegative-cost level, including split teleporters."""
    return 0.0


def make_manhattan_heuristic(
    goal_position: tuple[int, int], *, minimum_step_cost: float = 1.0
) -> Heuristic:
    """Lower bound for levels WITHOUT teleporting split switches.

    A regular roll reduces the nearest occupied tile's Manhattan distance by
    at most two. Moving an already-split cube reduces it by at most one.
    Bridges and ordinary switches do not invalidate this bound. Teleporting
    split switches do, even when the current State is not split yet.

    Every transition must cost at least minimum_step_cost. Pass a lower bound
    appropriate to weighted levels (zero is always safe).
    """
    step_cost = nonnegative_finite(minimum_step_cost, "minimum_step_cost")
    goal_row, goal_col = goal_position

    def heuristic(state: State) -> float:
        distance = min(
            abs(row - goal_row) + abs(col - goal_col)
            for row, col in state.positions
        )
        return ((distance + 1) // 2) * step_cost

    return heuristic
