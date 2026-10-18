"""Connect search algorithms to the same transitions used by manual play."""

from core.board import Board
from core.rules import is_goal, successors
from core.state import State
from solvers import SearchProblem, Transition


def make_search_problem(board: Board, initial_state: State | None = None) -> SearchProblem:
    # These closures are created inside the worker, never sent through a pipe.
    return SearchProblem(
        initial_state=board.initial_state() if initial_state is None else initial_state,
        is_goal=lambda state: is_goal(board, state),
        successors=lambda state: [Transition(action, target)
                                  for action, target in successors(board, state)],
    )
