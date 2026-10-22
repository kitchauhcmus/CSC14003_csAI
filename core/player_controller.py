"""
core/player_controller.py
Quản lý trạng thái phiên chơi thủ công (Manual Play Session), đặc biệt giải quyết bài toán:
- Chuyển quyền điều khiển giữa 2 khối 1x1x1 (khi nhấn Spacebar).
- Theo dõi chính xác tọa độ khối con đang được chọn ngay cả khi State.positions tự động sort lại.
"""

from core.board import Board
from core.constants import Action, Direction
from core.rules import apply_action, is_goal
from core.state import State


class SplitController:
    """
    Bộ điều khiển hỗ trợ GUI quản lý thao tác của người chơi với Advanced Mechanics.
    """

    def __init__(self, board: Board):
        self.board: Board = board
        self.state: State = board.initial_state()
        self.move_count: int = 0
        # Lưu TỌA ĐỘ (r, c) của khối 1x1x1 đang được chọn thay vì chỉ lưu index 0/1
        self._active_cube_pos: tuple[int, int] | None = None

    def reset(self) -> None:
        """Khởi động lại màn chơi về trạng thái ban đầu."""
        self.state = self.board.initial_state()
        self.move_count = 0
        self._active_cube_pos = None

    @property
    def active_cube_index(self) -> int | None:
        """
        Trả về chỉ số (0 hoặc 1) của khối con đang được điều khiển trong `self.state.positions`.
        Trả về None nếu khối đang nguyên vẹn (1x1x2).
        """
        if not self.state.is_split:
            return None
        if self._active_cube_pos in self.state.positions:
            return self.state.positions.index(self._active_cube_pos)
        # Mặc định chọn khối đầu tiên nếu chưa khởi tạo
        self._active_cube_pos = self.state.positions[0]
        return 0

    @property
    def active_cube_coord(self) -> tuple[int, int] | None:
        """Trả về tọa độ (r, c) của khối 1x1x1 đang được chọn để GUI vẽ viền sáng (highlight)."""
        idx = self.active_cube_index
        return self.state.positions[idx] if idx is not None else None

    def switch_active_cube(self) -> tuple[int, int] | None:
        """
        Gọi hàm này khi người chơi nhấn phím SPACEBAR.
        Đổi quyền điều khiển sang khối 1x1x1 còn lại và trả về tọa độ mới được chọn.
        """
        if not self.state.is_split:
            return None
        current_idx = self.active_cube_index
        new_idx = 1 - (current_idx or 0)
        self._active_cube_pos = self.state.positions[new_idx]
        return self._active_cube_pos

    def move(self, direction: Direction) -> bool:
        """
        Thực hiện lăn khối theo hướng `direction` (UP/DOWN/LEFT/RIGHT).
        - Tự động ánh xạ sang Action thường hoặc Action SPLIT dựa vào khối đang chọn.
        - Tự động bám theo (track) tọa độ mới của khối con sau khi di chuyển, bất chấp State sort lại.
        - Trả về True nếu nước đi hợp lệ, False nếu nước đi bị chặn/rơi xuống vực.
        """
        idx = self.active_cube_index
        action = Action.from_input(direction, idx)

        next_state = apply_action(self.board, self.state, action)
        if next_state is None:
            return False

        # Cập nhật lại tọa độ khối con đang chọn nếu vẫn ở chế độ SPLIT
        if next_state.is_split:
            if not self.state.is_split:
                # Vừa mới dẫm vào Split Switch -> Mặc định chọn khối ở vị trí spawn đầu tiên
                self._active_cube_pos = next_state.positions[0]
            else:
                # Đang ở chế độ SPLIT và vừa di chuyển 1 khối -> Tính tọa độ mới của khối đó
                old_r, old_c = self.state.positions[idx]  # type: ignore[index]
                self._active_cube_pos = (old_r + direction.dr, old_c + direction.dc)
        else:
            # Hai khối vừa hợp nhất (merge) thành 1x1x2
            self._active_cube_pos = None

        self.state = next_state
        self.move_count += 1
        return True

    def is_won(self) -> bool:
        """Kiểm tra đã thắng màn chơi chưa."""
        return is_goal(self.board, self.state)