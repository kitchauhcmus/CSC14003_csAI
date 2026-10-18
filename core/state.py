from dataclasses import dataclass, field
from typing import Iterable
from core.constants import Orientation


@dataclass(frozen=True, slots=True)
class State:
    """
    Trạng thái bất biến (Immutable) và Hashable của bài toán Bloxorz.

    Attributes:
        positions: Tuple chứa tọa độ (r, c) của các ô mà khối đang chiếm.
            - STANDING: ((r, c),)
            - HORIZONTAL / VERTICAL / SPLIT: ((r1, c1), (r2, c2)) đã sắp xếp từ điển.
        orientation: Tư thế hiện tại của khối (STANDING, HORIZONTAL, VERTICAL, SPLIT).
        active_bridges: Frozenset chứa tọa độ (r, c) của các cây cầu ĐANG MỞ
            (cầu mở hoạt động như ô sàn bình thường; cầu không nằm trong tập này
            đang đóng và hoạt động như ô trống/vực).

    Lưu ý sử dụng:
        - Các module bên ngoài `core/` nên khởi tạo thông qua `State.make(...)`
          để tự động chuẩn hóa kiểu dữ liệu về tuple/frozenset.
        - Lưu ý cho GUI khi ở trạng thái SPLIT: Do `positions` luôn được sắp xếp lại,
          chỉ số (0 hoặc 1) của hai khối con có thể đổi chỗ sau một nước đi. GUI cần
          lưu tọa độ (r, c) của khối đang được chọn thay vì lưu chỉ số index.

        - Ở trạng thái SPLIT, `positions` không cho biết khối con nào đang được chọn
        (thông tin đó nằm ở `Action`), và `rules.py` có trách nhiệm tự động gộp
        (merge) hai khối con ngay khi chúng di chuyển tới hai ô kề cạnh nhau.
        """
    positions: tuple[tuple[int, int], ...]
    orientation: Orientation
    active_bridges: frozenset[tuple[int, int]] = field(default_factory=frozenset)

    def __post_init__(self):
        # Chuẩn hóa thứ tự tọa độ (chỉ sort tối đa 2 phần tử)
        if (
            isinstance(self.positions, tuple)
            and len(self.positions) == 2
            and self.positions[0] > self.positions[1]
        ):
            object.__setattr__(self, "positions", (self.positions[1], self.positions[0]))

        assert self._is_valid_invariant(), (
            f"Invalid state invariant: orientation={self.orientation}, "
            f"positions={self.positions}, active_bridges={self.active_bridges}"
        )

    def _is_valid_invariant(self) -> bool:
        """Kiểm tra tính toàn vẹn kiểu dữ liệu và tính nhất quán hình học."""
        # Đảm bảo tính hashable (chặn trường hợp gọi trực tiếp State([list], ...))
        if not isinstance(self.positions, tuple) or not isinstance(self.active_bridges, frozenset):
            return False
        if not all(isinstance(p, tuple) and len(p) == 2 for p in self.positions):
            return False

        n = len(self.positions)
        if self.orientation == Orientation.STANDING:
            return n == 1

        if n != 2:
            return False

        (r1, c1), (r2, c2) = self.positions
        if self.orientation == Orientation.HORIZONTAL:
            return r1 == r2 and c2 == c1 + 1
        elif self.orientation == Orientation.VERTICAL:
            return c1 == c2 and r2 == r1 + 1
        elif self.orientation == Orientation.SPLIT:
            # Hai khối con không được trùng ô (dist == 0) và không được kề cạnh (dist == 1),
            # vì nếu kề cạnh thì phải được gộp lại thành khối 1x1x2.
            return abs(r1 - r2) + abs(c1 - c2) >= 2

        return False

    @classmethod
    def make(
        cls,
        positions: Iterable[tuple[int, int]],
        orientation: Orientation,
        active_bridges: Iterable[tuple[int, int]] = (),
    ) -> "State":
        """Factory method chuẩn hóa kiểu dữ liệu đầu vào về tuple và frozenset."""
        pos_tuple = tuple((int(r), int(c)) for r, c in positions)
        bridges_frozenset = frozenset((int(r), int(c)) for r, c in active_bridges)
        return cls(
            positions=pos_tuple,
            orientation=orientation,
            active_bridges=bridges_frozenset,
        )

    @property
    def is_split(self) -> bool:
        """Trả về True nếu khối đang bị tách thành hai khối 1x1x1."""
        return self.orientation == Orientation.SPLIT

    def __lt__(self, other: "State") -> bool:
        """
        Lưới an toàn (tie-breaker) nhất quán với __eq__ cho Priority Queue (heapq).
        Khuyến nghị cho Solver: Sử dụng tuple (priority, next(counter), state)
        với counter = itertools.count() để tránh chi phí so sánh State và giữ thứ tự FIFO.
        """
        if not isinstance(other, State):
            return NotImplemented
        return (
            self.positions,
            self.orientation.value,
            tuple(sorted(self.active_bridges)),
        ) < (
            other.positions,
            other.orientation.value,
            tuple(sorted(other.active_bridges)),
        )