from dataclasses import dataclass, field
from typing import Tuple, FrozenSet
from core.constants import Orientation


@dataclass(frozen=True)
class State:
    """
    Trạng thái bất biến (Immutable) và Hashable của game.
    Tối ưu hóa tối đa tốc độ duyệt cây cho các thuật toán AI.
    """
    positions: Tuple[Tuple[int, int], ...]
    orientation: Orientation
    active_bridges: FrozenSet[Tuple[int, int]] = field(default_factory=frozenset)

    def is_split(self) -> bool:
        """Kiểm tra xem khối có đang bị tách thành 2 cục 1x1x1 hay không."""
        return self.orientation == Orientation.SPLIT

    def __lt__(self, other: "State") -> bool:
        """Tie-breaker cho Priority Queue (heapq) trong UCS và A*."""
        if not isinstance(other, State):
            return NotImplemented
        return (self.positions, self.orientation.value) < (other.positions, other.orientation.value)