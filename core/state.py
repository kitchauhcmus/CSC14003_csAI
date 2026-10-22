from dataclasses import dataclass, field
from typing import Any, Iterable
from core.constants import Orientation


def is_strict_int(val: Any) -> bool:
    """True nếu val là int thật (loại bool vì bool kế thừa int)."""
    return isinstance(val, int) and not isinstance(val, bool)


def strict_int(val: Any, context: str = "value") -> int:
    """Chỉ chấp nhận int thật; từ chối bool, float, str."""
    if not is_strict_int(val):
        raise ValueError(f"Expected strict int for {context}, got {val!r} ({type(val).__name__}).")
    return val


@dataclass(frozen=True, slots=True)
class State:
    """
    Trạng thái bất biến (Immutable) và Hashable của bài toán Bloxorz.

    Attributes:
        positions: Tọa độ (r, c) các ô khối đang chiếm.
            - STANDING: ((r, c),)
            - HORIZONTAL / VERTICAL / SPLIT: ((r1, c1), (r2, c2)) đã sắp xếp từ điển.
        orientation: STANDING, HORIZONTAL, VERTICAL hoặc SPLIT.
        active_bridges: Frozenset các cầu ĐANG MỞ (cầu không nằm trong tập = đang đóng).

    Hợp đồng khởi tạo:
        - `State.make(...)`: dùng ngoài `core/`. Luôn kiểm tra toàn diện và ném `ValueError`
          (kể cả khi chạy `python -O`).
        - `State(...)`: đường nóng nội bộ `core/rules.py`. Chỉ kiểm tra nhanh bằng `assert`.

    Lưu ý GUI khi SPLIT: `positions` luôn được sắp xếp lại nên chỉ số cube có thể đổi chỗ
    sau mỗi nước đi. GUI lưu tọa độ ô của cube đang chọn và dùng `rules.action_for_cube(...)`.
    """
    positions: tuple[tuple[int, int], ...]
    orientation: Orientation
    active_bridges: frozenset[tuple[int, int]] = field(default_factory=frozenset)

    def __post_init__(self):
        if (
            isinstance(self.positions, tuple)
            and len(self.positions) == 2
            and isinstance(self.positions[0], tuple)
            and isinstance(self.positions[1], tuple)
            and self.positions[0] > self.positions[1]
        ):
            object.__setattr__(self, "positions", (self.positions[1], self.positions[0]))

        assert State._is_valid(
            self.positions, self.orientation, self.active_bridges, check_bridges=False
        ), (
            f"Invalid state invariant: orientation={self.orientation}, "
            f"positions={self.positions}, active_bridges={self.active_bridges}"
        )

    @staticmethod
    def _is_valid(positions: Any, orientation: Any, active_bridges: Any,
                  check_bridges: bool = True) -> bool:
        """Kiểm tra kiểu dữ liệu và tính nhất quán hình học."""
        if not isinstance(orientation, Orientation):
            return False
        if not isinstance(positions, tuple) or not isinstance(active_bridges, frozenset):
            return False
        if not all(
            isinstance(p, tuple) and len(p) == 2 and is_strict_int(p[0]) and is_strict_int(p[1])
            for p in positions
        ):
            return False
        if check_bridges and not all(
            isinstance(b, tuple) and len(b) == 2 and is_strict_int(b[0]) and is_strict_int(b[1])
            for b in active_bridges
        ):
            return False

        n = len(positions)
        if orientation == Orientation.STANDING:
            return n == 1
        if n != 2:
            return False

        (r1, c1), (r2, c2) = positions
        if orientation == Orientation.HORIZONTAL:
            return r1 == r2 and c2 == c1 + 1
        if orientation == Orientation.VERTICAL:
            return c1 == c2 and r2 == r1 + 1
        if orientation == Orientation.SPLIT:
            return abs(r1 - r2) + abs(c1 - c2) >= 2
        return False

    @classmethod
    def make(
        cls,
        positions: Iterable[tuple[int, int]],
        orientation: Orientation,
        active_bridges: Iterable[tuple[int, int]] = (),
    ) -> "State":
        """Factory an toàn: kiểm tra chặt, luôn ném ValueError (không phải AssertionError)."""
        if not isinstance(orientation, Orientation):
            raise ValueError(f"Invalid orientation: {orientation!r}")

        try:
            pos_list = list(positions)
            bridge_list = list(active_bridges)
        except TypeError as exc:
            raise ValueError("positions and active_bridges must be iterables of (r, c) pairs.") from exc

        parsed_pos: list[tuple[int, int]] = []
        for idx, item in enumerate(pos_list):
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise ValueError(f"Position at index {idx} must be a pair (r, c), got {item!r}.")
            parsed_pos.append((strict_int(item[0], f"positions[{idx}].r"),
                               strict_int(item[1], f"positions[{idx}].c")))

        parsed_bridges: list[tuple[int, int]] = []
        for idx, item in enumerate(bridge_list):
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise ValueError(f"Bridge at index {idx} must be a pair (r, c), got {item!r}.")
            parsed_bridges.append((strict_int(item[0], f"bridges[{idx}].r"),
                                   strict_int(item[1], f"bridges[{idx}].c")))

        if len(parsed_pos) == 2 and parsed_pos[0] > parsed_pos[1]:
            pos_tuple = (parsed_pos[1], parsed_pos[0])
        else:
            pos_tuple = tuple(parsed_pos)
        bridges = frozenset(parsed_bridges)

        # Kiểm tra TRƯỚC khi gọi cls(...) để luôn ném ValueError
        if not cls._is_valid(pos_tuple, orientation, bridges, check_bridges=True):
            raise ValueError(
                f"Invalid state invariant: orientation={orientation}, positions={pos_tuple}"
            )
        return cls(positions=pos_tuple, orientation=orientation, active_bridges=bridges)

    @property
    def is_split(self) -> bool:
        return self.orientation == Orientation.SPLIT

    def __lt__(self, other: "State") -> bool:
        """Tie-breaker cho heapq. positions đã xác định duy nhất orientation nên không cần so thêm.
        Solver nên dùng (priority, next(counter), state) để khỏi so sánh State."""
        if not isinstance(other, State):
            return NotImplemented
        return (self.positions, tuple(sorted(self.active_bridges))) < (
            other.positions, tuple(sorted(other.active_bridges))
        )