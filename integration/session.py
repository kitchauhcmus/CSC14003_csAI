"""A UI-independent game session built on the shared rules engine."""

from dataclasses import dataclass

from core.board import Board
from core.constants import Action, Direction, MoveResult
from core.rules import evaluate_action, is_goal
from core.state import State


@dataclass(frozen=True)
class _Snapshot:
    state: State
    selected_position: tuple[int, int] | None
    move_count: int
    status: str
    message: str
    last_failure: MoveResult
    last_attempt_state: State | None


class GameSession:
    """Track moves, selection and undo without duplicating game rules.

    A failed movement counts as an attempted move. The last valid State is
    retained so the renderer can animate the fall and Undo can restore play.
    """

    def __init__(self, board: Board):
        self.board = board
        self._history: list[_Snapshot] = []
        self.reset()

    def _snapshot(self) -> _Snapshot:
        return _Snapshot(self.state, self.selected_position, self.move_count,
                         self.status, self.message, self.last_failure, self.last_attempt_state)

    def _restore(self, snapshot: _Snapshot) -> None:
        self.state = snapshot.state
        self.selected_position = snapshot.selected_position
        self.move_count = snapshot.move_count
        self.status = snapshot.status
        self.message = snapshot.message
        self.last_failure = snapshot.last_failure
        self.last_attempt_state = snapshot.last_attempt_state

    def _begin_at(self, state: State, move_count: int = 0,
                  selected_position: tuple[int, int] | None = None) -> None:
        """Start an independent playback timeline at a solver's root state."""
        self.state = state
        self.move_count = move_count
        self.selected_position = (
            selected_position if state.is_split and selected_position in state.positions
            else state.positions[0] if state.is_split else None
        )
        self.status = "won" if is_goal(self.board, state) else "playing"
        self.message = "Stage complete." if self.status == "won" else ""
        self.last_failure = MoveResult.OK
        self.last_attempt_state = None
        self._history.clear()

    def reset(self) -> None:
        self._begin_at(self.board.initial_state())

    def move(self, direction: Direction) -> bool:
        if not isinstance(direction, Direction):
            raise TypeError("direction must be a Direction")
        cube_index = None
        if self.state.is_split:
            if self.selected_position not in self.state.positions:
                self.selected_position = self.state.positions[0]
            cube_index = self.state.positions.index(self.selected_position)
        return self.apply_action(Action.from_input(direction, cube_index))

    def apply_action(self, action: Action) -> bool:
        if not isinstance(action, Action):
            raise TypeError("action must be an Action")
        if self.status != "playing":
            return False
        if self.state.is_split != (action.cube_index is not None):
            raise ValueError("Action does not match the current block orientation")

        before = self._snapshot()
        outcome = evaluate_action(self.board, self.state, action)
        next_state = outcome.state
        self.last_failure = outcome.reason
        self.last_attempt_state = outcome.attempted_state
        if outcome.reason == MoveResult.INVALID_ACTION:
            self.message = "This action cannot be applied."
            return False
        self._history.append(before)
        self.move_count += 1
        if next_state is None:
            self.status = "lost"
            self.message = {
                MoveResult.FRAGILE_BROKE: "The orange tile broke under the upright block.",
                MoveResult.BRIDGE_CLOSED: "The block fell through a closed bridge.",
                MoveResult.FELL_VOID: "The block fell into the void.",
            }.get(outcome.reason, "The block fell.") + " Undo or restart to try again."
            return False

        moved_position = None
        if self.state.is_split:
            source = self.state.positions[action.cube_index]
            moved_position = (source[0] + action.direction.dr,
                              source[1] + action.direction.dc)
        self.state = next_state
        self.selected_position = (
            moved_position if next_state.is_split and moved_position in next_state.positions
            else next_state.positions[0] if next_state.is_split else None
        )
        self.status = "won" if is_goal(self.board, next_state) else "playing"
        self.message = "Stage complete." if self.status == "won" else ""
        return True

    def select_next_cube(self) -> bool:
        if not self.state.is_split or self.status != "playing":
            return False
        current = (self.state.positions.index(self.selected_position)
                   if self.selected_position in self.state.positions else 1)
        self.selected_position = self.state.positions[1 - current]
        return True

    def undo(self) -> bool:
        if not self._history:
            return False
        self._restore(self._history.pop())
        return True

