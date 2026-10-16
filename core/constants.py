from enum import Enum

class Direction(Enum):
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3

class Action(Enum):
    # 4 hành động khi khối nguyên vẹn
    UP = (None, Direction.UP)
    DOWN = (None, Direction.DOWN)
    LEFT = (None, Direction.LEFT)
    RIGHT = (None, Direction.RIGHT)

    # 8 hành động khi bị tách đôi (SPLIT): (index_cục_được_chọn, hướng_lăn)
    SPLIT_0_UP = (0, Direction.UP)
    SPLIT_0_DOWN = (0, Direction.DOWN)
    SPLIT_0_LEFT = (0, Direction.LEFT)
    SPLIT_0_RIGHT = (0, Direction.RIGHT)

    SPLIT_1_UP = (1, Direction.UP)
    SPLIT_1_DOWN = (1, Direction.DOWN)
    SPLIT_1_LEFT = (1, Direction.LEFT)
    SPLIT_1_RIGHT = (1, Direction.RIGHT)

    @property
    def cube_index(self):
        """Trả về None nếu là khối nguyên, trả về 0 hoặc 1 nếu đang SPLIT."""
        return self.value[0]

    @property
    def direction(self) -> Direction:
        """Trả về hướng di chuyển thực sự (UP/DOWN/LEFT/RIGHT)."""
        return self.value[1]

    @classmethod
    def from_input(cls, direction: Direction, cube_index: int | None = None) -> "Action":
        """Hàm helper tiện ích cho GUI: truyền hướng và index cục -> lấy Action."""
        return cls((cube_index, direction))

class Orientation(Enum):
    STANDING = 0     # Đứng thẳng 1 ô
    HORIZONTAL = 1   # Nằm ngang (chiếm 2 ô theo trục c)
    VERTICAL = 2     # Nằm dọc (chiếm 2 ô theo trục r)
    SPLIT = 3        # tách làm 2 bởi split_switch

class TileType(Enum):
    VOID = 0
    FLOOR = 1
    GOAL = 2
    FRAGILE = 3         # gạch cam
    SOFT_SWITCH = 4     # công tắc tròn
    HEAVY_SWITCH = 5    # công tắc X
    SPLIT_SWITCH = 6    # Công tắc ()
    BRIDGE = 7          # Cầu 
class SwitchBehavior(Enum):

    TOGGLE = 0             # Đảo trạng thái cầu
    PERMANENT_OPEN = 1     # Chỉ mở cầu, đã mở thì không đóng lại được nữa
    PERMANENT_CLOSE = 2    # Chỉ đóng cầu