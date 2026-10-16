from enum import Enum

class Direction(Enum):
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3

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