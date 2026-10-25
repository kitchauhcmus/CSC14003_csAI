"""Adapt the team's pure rules to the team's original search contract."""
from core.rules import is_goal, successors
from solvers import SearchProblem, Transition

def make_search_problem(board, state=None):
    # Construct callbacks inside the worker: Windows never needs to pickle them.
    return SearchProblem(
        board.initial_state() if state is None else state,
        lambda current: is_goal(board, current),
        lambda current: [Transition(action, target, 1.0)
                         for action, target in successors(board, current)],
    )

