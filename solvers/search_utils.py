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
from dataclasses import dataclass, field
from typing import Callable, Iterable, Literal

from core.constants import Action
from core.state import State

Status = Literal["solved", "unsolvable", "timeout", "node_limit", "cancelled"]


@dataclass(frozen=True, slots=True)
class Transition:
    """Biểu diễn một bước chuyển từ trạng thái hiện tại sang trạng thái kế tiếp.
    
    Attributes:
        action: Hành động thực hiện từ trạng thái hiện tại.
        state: Trạng thái kế tiếp sau khi thực hiện hành động.
        
    """
    action: Action
    state: State

    def __post_init__(self):
        if not isinstance(self.action, Action): 
            raise TypeError("action phải có kiểu Action.")
        if not isinstance(self.state, State): 
            raise TypeError("state phải có kiểu State.")


@dataclass(frozen=True, slots=True)
class SearchProblem:
    """Lưu trạng thái ban đầu và các hàm cần thiết cho thuật toán tìm kiếm."""

    initial_state: State  # Trạng thái bắt đầu tìm kiếm
    is_goal: Callable[[State], bool]  # Hàm kiểm tra một trạng thái có phải đích không
    successors: Callable[[State], Iterable[Transition]]  # Hàm sinh các bước chuyển hợp lệ từ một trạng thái

    def __post_init__(self):
        # Kiểm tra kiểu của trạng thái ban đầu sau khi khởi tạo
        if not isinstance(self.initial_state, State):
            raise TypeError("initial_state phải là đối tượng thuộc lớp State.")


@dataclass(slots=True)
class SearchMetrics:
    search_time: float = 0.0  # Search Time: thời gian chạy, đơn vị giây
    memory_usage: int = 0  # Memory Usage: bộ nhớ Python đỉnh, đơn vị byte
    expanded_nodes: int = 0  # Expanded Nodes: số trạng thái đã bắt đầu mở rộng
    solution_length: int | None = None  # Solution Length: số hành động; None nếu chưa có nghiệm

    def to_dict(self):
        return {
            "search_time": self.search_time,
            "memory_usage": self.memory_usage,
            "expanded_nodes": self.expanded_nodes,
            "solution_length": self.solution_length,
        }

@dataclass(slots=True)
class SearchResult:
    """Lưu kết quả và số liệu của một lần chạy thuật toán tìm kiếm."""

    algorithm: str  # Tên thuật toán: BFS hoặc DFS
    status: Status  # Trạng thái kết thúc: solved, unsolvable, timeout, node_limit hoặc cancelled
    actions: list[Action] = field(default_factory=list)  # Các hành động từ đầu đến đích
    states: list[State] = field(default_factory=list)  # Các trạng thái trên đường đi, gồm cả đầu và đích
    metrics: SearchMetrics = field(default_factory=SearchMetrics)  # Bốn chỉ số hiệu năng

    @property
    def solved(self) -> bool:
        return self.status == "solved"

    def to_dict(self, include_states: bool = False):
        """Chuyển kết quả thành dictionary có thể xuất JSON; tùy chọn kèm chuỗi trạng thái."""
        result = {
            "algorithm": self.algorithm,
            "status": self.status,
            "actions": [a.name for a in self.actions],  # Đổi Action thành tên, ví dụ "RIGHT"
            "metrics": self.metrics.to_dict(),
        }

        if include_states:
            result["states"] = [
                {
                    "positions": [list(p) for p in s.positions],  
                    "orientation": s.orientation.name,  
                    "active_bridges": [list(p) for p in sorted(s.active_bridges)],
                }
                for s in self.states
            ]

        return result

def reconstruct_path(goal, parents):
    """Truy ngược bảng cha, trả về hành động, trạng thái."""
    state = goal
    actions, states = [], [state]
    while parents[state] is not None:
        previous, action = parents[state]
        actions.append(action)
        states.append(previous)
        state = previous
    return list(reversed(actions)), list(reversed(states))
