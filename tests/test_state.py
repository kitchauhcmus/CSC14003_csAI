from dataclasses import FrozenInstanceError

import pytest

from core.constants import Orientation
from core.state import State, is_strict_int, strict_int


@pytest.mark.parametrize("value", [True, False, 1.2, "2", None])
def test_coordinates_do_not_coerce(value):
    assert not is_strict_int(value)
    with pytest.raises(ValueError):
        strict_int(value)
    with pytest.raises(ValueError):
        State.make([(value, 0)], Orientation.STANDING)


def test_make_canonicalizes_and_is_hashable():
    a = State.make([[2, 4], [2, 3]], Orientation.HORIZONTAL, [[0, 1]])
    b = State(((2, 3), (2, 4)), Orientation.HORIZONTAL, frozenset({(0, 1)}))
    assert a == b and hash(a) == hash(b)
    with pytest.raises(FrozenInstanceError):
        a.orientation = Orientation.STANDING


@pytest.mark.parametrize("positions,orientation", [
    ([], Orientation.STANDING),
    ([(0, 0), (0, 0)], Orientation.SPLIT),
    ([(0, 0), (0, 1)], Orientation.SPLIT),
    ([(0, 0), (2, 0)], Orientation.VERTICAL),
    ([(0, 0), (1, 0)], Orientation.HORIZONTAL),
    ([(0, 0)], 0),
])
def test_invalid_geometry_raises_value_error(positions, orientation):
    with pytest.raises(ValueError):
        State.make(positions, orientation)


def test_direct_constructor_rejects_mutable_and_bad_coordinates():
    with pytest.raises(ValueError):
        State([(0, 0)], Orientation.STANDING)
    with pytest.raises(ValueError):
        State((([1], 0),), Orientation.STANDING)
    with pytest.raises(ValueError):
        State(((0, 0),), Orientation.STANDING, frozenset({("1", 0)}))
