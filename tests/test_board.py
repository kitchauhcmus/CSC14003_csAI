import pickle

import pytest

from core.board import Board


def test_board_is_immutable_hash_safe_and_pickleable():
    board = Board.from_dict({"grid": ["S..G"]})
    lookup = {board: "level"}
    with pytest.raises(AttributeError):
        board.name = "changed"
    with pytest.raises(AttributeError):
        del board.grid
    with pytest.raises(TypeError):
        board.switches[(0, 1)] = None
    restored = pickle.loads(pickle.dumps(board))
    assert restored == board
    assert lookup[restored] == "level"
    with pytest.raises(AttributeError):
        restored.name = "changed"


def test_json_round_trip():
    board = Board.from_dict({
        "grid": ["S.oBG"],
        "switches": [{"pos": [0, 2], "behavior": "TOGGLE", "targets": [[0, 3]]}],
    })
    assert Board.from_dict(board.to_dict()) == board


@pytest.mark.parametrize("data", [
    {"grid": ["S..G"], "start_pos": [False, 0]},
    {"grid": ["S..G", "..."]},
    {"grid": ["S..oG"]},
    {"grid": ["S...G"], "initial_bridges": [[0, 2]]},
])
def test_invalid_levels_rejected(data):
    with pytest.raises(ValueError):
        Board.from_dict(data)
