
"""Pure Bloxorz transitions shared by manual play and all search algorithms.

Only a newly pressed switch fires: compare qualifying occupied switch tiles in
the previous and candidate states. Soft switches accept any cube; heavy ones
require the intact block standing. A stationary split cube therefore cannot
toggle its switch on every move of the other cube. A split tile activates only
under a standing intact block and teleports to its two configured spawn cells.

Switch effects are resolved in coordinate order before final support checking.
TOGGLE flips targets; PERMANENT_OPEN/CLOSE set targets open/closed (idempotent
actions, not global latches overriding other switches). Entering a bridge while
simultaneously opening it is permitted; closing an occupied bridge invalidates
the move. Goal is terminal. Invalid moves never change the input Board/State.
"""

from dataclasses import dataclass

from core.board import Board
from core.constants import Action, Direction, MoveResult, Orientation, SwitchBehavior, TileType
from core.state import State


@dataclass(frozen=True, slots=True)
class MoveOutcome:
    """A pure move result, including the landing pose for a failure animation."""

    state: State | None
    reason: MoveResult
    attempted_state: State | None


def is_goal(board: Board, state: State) -> bool:
    return state.orientation == Orientation.STANDING and state.positions == (board.goal_pos,)


def _support_result(board: Board, state: State) -> MoveResult:
    """Explain support failure without changing the team's support rules."""
    for position in state.positions:
        tile = board.tile_at(*position)
        if tile == TileType.VOID:
            return MoveResult.FELL_VOID
        if tile == TileType.BRIDGE and position not in state.active_bridges:
            return MoveResult.BRIDGE_CLOSED
        if tile == TileType.FRAGILE and state.orientation == Orientation.STANDING:
            return MoveResult.FRAGILE_BROKE
    return MoveResult.OK


def _supported(board: Board, state: State) -> bool:
    return _support_result(board, state) == MoveResult.OK


def _pressed(board: Board, state: State) -> set[tuple[int, int]]:
    return {
        p for p in state.positions
        if board.tile_at(*p) == TileType.SOFT_SWITCH
        or (board.tile_at(*p) == TileType.HEAVY_SWITCH and state.orientation == Orientation.STANDING)
    }


def _roll(state: State, action: Action) -> State | None:
    direction = action.direction
    dr, dc = direction.value
    if state.is_split:
        if action.cube_index is None:
            return None
        positions = list(state.positions)
        r, c = positions[action.cube_index]
        positions[action.cube_index] = (r + dr, c + dc)
        if positions[0] == positions[1]:
            return None
        (r1, c1), (r2, c2) = sorted(positions)
        if abs(r1 - r2) + abs(c1 - c2) == 1:
            orientation = Orientation.HORIZONTAL if r1 == r2 else Orientation.VERTICAL
        else:
            orientation = Orientation.SPLIT
    else:
        if action.cube_index is not None:
            return None
        r, c = state.positions[0]
        if state.orientation == Orientation.STANDING:
            if direction in (Direction.UP, Direction.LEFT):
                positions = [(r + 2 * dr, c + 2 * dc), (r + dr, c + dc)]
            else:
                positions = [(r + dr, c + dc), (r + 2 * dr, c + 2 * dc)]
            orientation = Orientation.VERTICAL if dr else Orientation.HORIZONTAL
        elif state.orientation == Orientation.HORIZONTAL and dc:
            positions = [(r, c - 1 if dc < 0 else c + 2)]
            orientation = Orientation.STANDING
        elif state.orientation == Orientation.VERTICAL and dr:
            positions = [(r - 1 if dr < 0 else r + 2, c)]
            orientation = Orientation.STANDING
        else:
            positions = [(row + dr, col + dc) for row, col in state.positions]
            orientation = state.orientation
    return State.make(positions, orientation, state.active_bridges)


def evaluate_action(board: Board, state: State, action: Action) -> MoveOutcome:
    """Evaluate once; a failed landing remains available for GUI animation.

    ``state`` is None for all failures, preserving the solver's legal-move
    contract. ``attempted_state`` is visual data, never a legal successor.
    """
    if not isinstance(action, Action) or is_goal(board, state):
        return MoveOutcome(None, MoveResult.INVALID_ACTION, None)
    support = _support_result(board, state)
    if support != MoveResult.OK:
        return MoveOutcome(None, support, None)
    candidate = _roll(state, action)
    if candidate is None:
        return MoveOutcome(None, MoveResult.INVALID_ACTION, None)
    if candidate.orientation == Orientation.STANDING:
        split = board.split_switches.get(candidate.positions[0])
        if split is not None:
            candidate = State.make(split.spawn_positions, Orientation.SPLIT, state.active_bridges)
    active = set(state.active_bridges)
    for position in sorted(_pressed(board, candidate) - _pressed(board, state)):
        spec = board.switches[position]
        if spec.behavior == SwitchBehavior.TOGGLE:
            active.symmetric_difference_update(spec.targets)
        elif spec.behavior == SwitchBehavior.PERMANENT_OPEN:
            active.update(spec.targets)
        else:
            active.difference_update(spec.targets)
    candidate = State.make(candidate.positions, candidate.orientation, active)
    support = _support_result(board, candidate)
    return MoveOutcome(candidate if support == MoveResult.OK else None, support, candidate)


def apply_action_with_result(
    board: Board, state: State, action: Action
) -> tuple[State | None, MoveResult]:
    """Return (legal successor, reason); failed moves leave Board/State untouched."""
    outcome = evaluate_action(board, state, action)
    return outcome.state, outcome.reason


def apply_action(board: Board, state: State, action: Action) -> State | None:
    """Return the legal successor, or None for a fall, invalid action or goal."""
    return evaluate_action(board, state, action).state


def successors(board: Board, state: State) -> list[tuple[Action, State]]:
    """All legal moves in stable Action enum order; goal has no successors."""
    actions = (a for a in Action if (a.cube_index is not None) == state.is_split)
    result = []
    for action in actions:
        candidate = apply_action(board, state, action)
        if candidate is not None:
            result.append((action, candidate))
    return result

def is_touching_fragile(board: Board, state: State) -> bool:
    """
    Kiểm tra xem khối hộp ở trạng thái `state` có đang nằm đè lên bất kỳ ô gạch cam
    (FRAGILE) nào hay không. Hỗ trợ tính hàm chi phí (Cost Function) trong UCS Solver
    (ví dụ: phạt điểm cao hơn khi đi qua gạch dễ vỡ).
    """
    return any(board.tile_at(*pos) == TileType.FRAGILE for pos in state.positions)


def did_bridges_change(prev_state: State, next_state: State) -> bool:
    """
    Kiểm tra xem nước đi từ `prev_state` sang `next_state` có làm thay đổi trạng thái
    đóng/mở của bất kỳ cây cầu nào không. Hỗ trợ GUI phát âm thanh/hiệu ứng và hỗ trợ UCS.
    """
    return prev_state.active_bridges != next_state.active_bridges


def action_for_cube(
    state: State,
    direction: Direction,
    cube_coord: tuple[int, int] | None = None,
) -> Action:
    """Resolve a selected cube coordinate after State.positions has been sorted.

    The first cube is selected by default when a split has just occurred.
    GUI callers keep the coordinate, not an index, between moves.
    """
    if not isinstance(direction, Direction):
        raise ValueError("direction must be a Direction value.")
    if not state.is_split:
        return Action.from_input(direction)
    selected = state.positions[0] if cube_coord is None else cube_coord
    if selected not in state.positions:
        raise ValueError(f"Selected cube {selected!r} is not in this state.")
    return Action.from_input(direction, state.positions.index(selected))

