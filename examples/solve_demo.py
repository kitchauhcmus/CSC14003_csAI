"""Solve the two-roll corridor S..G using a hand-written transition graph.

This demonstrates the interface while core/board.py and movement rules are
unfinished on the reference branch; it is not a replacement game engine.
"""

import json

from core.constants import Action, Orientation
from core.state import State
from solvers import SearchProblem, Transition, astar, make_manhattan_heuristic, ucs


def make_problem() -> SearchProblem:
    start = State(((0, 0),), Orientation.STANDING)
    lying = State(((0, 1), (0, 2)), Orientation.HORIZONTAL)
    goal = State(((0, 3),), Orientation.STANDING)
    graph = {
        start: (Transition(Action.RIGHT, lying),),
        lying: (Transition(Action.LEFT, start), Transition(Action.RIGHT, goal)),
        goal: (Transition(Action.LEFT, lying),),
    }
    return SearchProblem(start, lambda state: state == goal, graph.__getitem__)


def main():
    problem = make_problem()
    for result in (ucs(problem), astar(problem, make_manhattan_heuristic((0, 3)))):
        print(json.dumps(result.to_dict(include_states=True), indent=2))


if __name__ == "__main__":
    main()
