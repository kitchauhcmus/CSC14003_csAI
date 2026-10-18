"""
tests/test_advanced_mechanics.py
Bộ kiểm thử tự động (Unit Tests) cho toàn bộ cơ chế nâng cao (Advanced Mechanics):
- Fragile Tiles (Gạch cam dễ vỡ)
- Bridges (Cầu đóng/mở)
- Soft Switch (Công tắc tròn) & Heavy Switch (Công tắc X)
- Chế độ cầu: TOGGLE, PERMANENT_OPEN, PERMANENT_CLOSE
- Split Switch (Tách khối), điều khiển từng khối (SplitController), và Hợp nhất (Merge)
- Tương thích với AI Solver (kiểm tra tính bất biến, hashing và giải thử bằng BFS)
"""

import unittest
from collections import deque

from core.board import Board
from core.constants import Action, Direction, Orientation, SwitchBehavior
from core.player_controller import SplitController
from core.rules import apply_action, is_goal, successors
from core.state import State


class TestAdvancedMechanics(unittest.TestCase):

    def test_fragile_tile_mechanics(self):
        """1. Kiểm thử Fragile Tile: Nằm đè lên thì sống, đứng thẳng lên thì rơi (None)."""
        data = {
            "name": "Fragile Test",
            "grid": [
                "S.F.G",
                ".....",
            ],
        }
        board = Board.from_dict(data)
        s0 = board.initial_state()  # STANDING tại (0, 0)

        # Lăn sang phải -> NẰM NGANG tại (0, 1) và (0, 2) [đè lên gạch cam F ở (0, 2)] -> HỢP LỆ
        s1 = apply_action(board, s0, Action.RIGHT)
        self.assertIsNotNone(s1, "Khối nằm ngang trên gạch Fragile phải hợp lệ.")
        self.assertEqual(s1.orientation, Orientation.HORIZONTAL)

        # Tạo trạng thái nằm ngang ở (0, 0) và (0, 1), sau đó lăn phải để ĐỨNG LÊN (0, 2) -> PHẢI BỊ RƠI
        s_before_stand = State.make([(0, 0), (0, 1)], Orientation.HORIZONTAL)
        s_fall = apply_action(board, s_before_stand, Action.RIGHT)
        self.assertIsNone(s_fall, "Khối đứng thẳng trên gạch Fragile phải bị rơi (trả về None).")

    def test_soft_and_heavy_switches_with_bridge_modes(self):
        """2. Kiểm thử Soft Switch, Heavy Switch và các chế độ cầu (Toggle, Permanent)."""
        data = {
            "name": "Switch & Bridge Test",
            "grid": [
                "S.o.x.B.G",
                ".........",
            ],
            "initial_bridges": [],  # Cầu tại (0, 6) ban đầu ĐÓNG
            "switches": [
                # Soft switch tại (0, 2) chế độ TOGGLE điều khiển cầu (0, 6)
                {"pos": [0, 2], "behavior": "TOGGLE", "targets": [[0, 6]]},
                # Heavy switch tại (0, 4) chế độ PERMANENT_CLOSE điều khiển cầu (0, 6)
                {"pos": [0, 4], "behavior": "PERMANENT_CLOSE", "targets": [[0, 6]]},
            ],
        }
        board = Board.from_dict(data)
        s0 = board.initial_state()  # STANDING tại (0, 0)

        # Lăn phải -> Nằm ngang ở (0,1)-(0,2), chạm vào Soft Switch (0,2) -> Cầu (0,6) MỞ
        s1 = apply_action(board, s0, Action.RIGHT)
        self.assertIn((0, 6), s1.active_bridges, "Soft switch phải kích hoạt ngay cả khi khối đang nằm.")

        # Giả sử khối nằm ngang đè lên Heavy Switch ở (0,3)-(0,4) -> Cầu KHÔNG bị đóng vì chưa đứng thẳng
        s_lie_before_heavy = State.make([(1, 3), (1, 4)], Orientation.HORIZONTAL, [(0, 6)])
        s_lie_on_heavy = apply_action(board, s_lie_before_heavy, Action.UP)
        self.assertIn((0, 6), s_lie_on_heavy.active_bridges, "Heavy switch KHÔNG được kích hoạt khi khối nằm.")

        # Đứng thẳng lên Heavy Switch tại (0, 4) -> Cầu (0, 6) phải ĐÓNG lại
        s_stand_before_heavy = State.make([(0, 2), (0, 3)], Orientation.HORIZONTAL, [(0, 6)])
        s_stand_on_heavy = apply_action(board, s_stand_before_heavy, Action.RIGHT)
        self.assertNotIn((0, 6), s_stand_on_heavy.active_bridges, "Heavy switch phải kích hoạt khi khối đứng thẳng.")

    def test_split_switch_control_and_merge(self):
        """3. Kiểm thử tách khối (Split), đổi quyền điều khiển (Spacebar) và hợp nhất (Merge)."""
        data = {
            "name": "Split & Merge Test",
            "grid": [
                "S..(.G",
                "......",
                "......",
            ],
            "split_switches": [
                # Khi đứng vào (0, 3), tách thành 2 khối con tại (2, 1) và (2, 3)
                {"pos": [0, 3], "spawn_positions": [[2, 1], [2, 3]]}
            ],
        }
        board = Board.from_dict(data)
        controller = SplitController(board)

        # Đưa khối đứng thẳng vào ô Split Switch (0, 3)
        # Từ (0,0) -> lăn phải nằm ở (0,1)-(0,2) -> lăn phải đứng ở (0,3)
        self.assertTrue(controller.move(Direction.RIGHT))
        self.assertTrue(controller.move(Direction.RIGHT))

        # Kiểm tra đã tách thành 2 khối tại (2, 1) và (2, 3)
        self.assertTrue(controller.state.is_split)
        self.assertEqual(controller.state.positions, ((2, 1), (2, 3)))
        self.assertEqual(controller.active_cube_coord, (2, 1))

        # Nhấn Spacebar đổi quyền điều khiển sang khối ở (2, 3)
        controller.switch_active_cube()
        self.assertEqual(controller.active_cube_coord, (2, 3))

        # Di chuyển khối ở (2, 3) sang TRÁI về (2, 2) -> Nằm sát khối (2, 1) -> Tự động MERGE!
        self.assertTrue(controller.move(Direction.LEFT))
        self.assertFalse(controller.state.is_split, "Hai khối nằm cạnh nhau phải tự động hợp nhất.")
        self.assertEqual(controller.state.orientation, Orientation.HORIZONTAL)
        self.assertEqual(controller.state.positions, ((2, 1), (2, 2)))

    def test_stationary_split_cube_does_not_retoggle_switch(self):
        """4. Đảm bảo khối con đứng yên trên công tắc TOGGLE không kích hoạt lại công tắc khi khối kia di chuyển."""
        data = {
            "name": "Stationary Split Switch Test",
            "grid": [
                "S.o..G",
                "....B.",
            ],
            "initial_bridges": [[1, 4]],
            "switches": [
                {"pos": [0, 2], "behavior": "TOGGLE", "targets": [[1, 4]]}
            ],
        }
        board = Board.from_dict(data)
        # Khối 0 đang đè sẵn lên công tắc (0, 2), khối 1 ở (0, 4), cầu (1, 4) đang mở
        state = State.make([(0, 2), (0, 4)], Orientation.SPLIT, [(1, 4)])

        # Di chuyển khối 1 từ (0, 4) sang trái (0, 3), khối 0 vẫn đứng yên trên công tắc (0, 2)
        next_state = apply_action(board, state, Action.SPLIT_1_LEFT)
        self.assertIsNotNone(next_state)
        self.assertIn(
            (1, 4),
            next_state.active_bridges,
            "Khối con đứng yên trên công tắc không được phép toggle lại cầu khi khối kia di chuyển.",
        )

    def test_ai_solver_compatibility_bfs(self):
        """5. Kiểm thử tích hợp với AI Solver (BFS) trên màn chơi kết hợp Công tắc + Cầu + Gạch cam."""
        data = {
            "name": "AI Solver Integration Stage",
            "grid": [
                "S.o.B.G",
                ".......",
            ],
            "initial_bridges": [],
            "switches": [
                {"pos": [0, 2], "behavior": "PERMANENT_OPEN", "targets": [[0, 4]]}
            ],
        }
        board = Board.from_dict(data)
        initial = board.initial_state()

        # Chạy BFS chuẩn sử dụng hàm successors() và is_goal()
        queue = deque([(initial, [])])
        visited = {initial}
        solution = None

        while queue:
            curr_state, path = queue.popleft()
            if is_goal(board, curr_state):
                solution = path
                break
            for action, next_state in successors(board, curr_state):
                if next_state not in visited:
                    visited.add(next_state)
                    queue.append((next_state, path + [action]))

        self.assertIsNotNone(solution, "AI Solver (BFS) phải tìm được lời giải qua cầu và công tắc.")
        self.assertGreater(len(solution), 0)


if __name__ == "__main__":
    unittest.main()