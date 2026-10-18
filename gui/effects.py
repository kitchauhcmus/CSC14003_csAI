"""Small deterministic animation tools, independent of a window or game rules.

EffectTrack callbacks receive normalized progress, not seconds. The scene can
combine smoothstep(), a quaternion and a pivot offset without accumulating
rotation error. Effects owns foreground tracks; keep ambient loops separately
when they should not block player input.
"""

from math import hypot, isfinite
from numbers import Real
from typing import Callable

from panda3d.core import Quat, Vec3


def _number(value: float, name: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number.")
    result = float(value)
    if not isfinite(result) or (nonnegative and result < 0):
        raise ValueError(f"{name} must be finite" + (" and nonnegative." if nonnegative else "."))
    return result


def _vector(value: Vec3, name: str) -> Vec3:
    try:
        result = Vec3(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite 3D vector.") from exc
    if not all(isfinite(component) for component in (result.x, result.y, result.z)):
        raise ValueError(f"{name} must be a finite 3D vector.")
    return result


def smoothstep(t: float) -> float:
    """Cubic ease with zero endpoint velocity; clamp finite input to [0, 1]."""
    t = max(0.0, min(1.0, _number(t, "progress")))
    return t * t * (3.0 - 2.0 * t)


def roll_quat(angle_degrees: float, axis: Vec3) -> Quat:
    """An axis-angle rotation; normalize a copied axis, leaving input intact."""
    angle = _number(angle_degrees, "angle")
    axis = _vector(axis, "axis")
    length = hypot(axis.x, axis.y, axis.z)
    if length == 0:
        raise ValueError("axis must be nonzero.")
    unit = Vec3(axis.x / length, axis.y / length, axis.z / length)
    rotation = Quat()
    rotation.setFromAxisAngle(angle, unit)
    return rotation


def rigid_pivot_offset(pivot: Vec3, rotation: Quat) -> Vec3:
    """Translation for x' = R*x + (pivot - R*pivot), keeping pivot fixed."""
    pivot = _vector(pivot, "pivot")
    try:
        copied_rotation = Quat(rotation)
    except (TypeError, ValueError) as exc:
        raise ValueError("rotation must be a finite, nonzero quaternion.") from exc
    components = (copied_rotation.getR(), copied_rotation.getI(),
                  copied_rotation.getJ(), copied_rotation.getK())
    length = hypot(*components)
    if not all(isfinite(value) for value in components) or length == 0:
        raise ValueError("rotation must be a finite, nonzero quaternion.")
    # Panda xform assumes a unit quaternion. Copy and normalize instead of
    # changing a caller's cached rotation.
    copied_rotation = Quat(*(component / length for component in components))
    return pivot - copied_rotation.xform(pivot)


def falling_offset(
    elapsed: float,
    direction: Vec3,
    horizontal_speed: float = .9,
    gravity: float = 18,
) -> Vec3:
    """Ballistic offset from rest in z; normalized XY direction controls drift.

    A zero XY direction falls straight down. Its z component is ignored because
    vertical displacement is determined by gravity, never by horizontal speed.
    """
    elapsed = _number(elapsed, "elapsed", nonnegative=True)
    speed = _number(horizontal_speed, "horizontal_speed", nonnegative=True)
    gravity = _number(gravity, "gravity", nonnegative=True)
    direction = _vector(direction, "direction")
    length = hypot(direction.x, direction.y)
    distance = speed * elapsed
    dx, dy = ((direction.x / length, direction.y / length) if length else (0.0, 0.0))
    return Vec3(dx * distance, dy * distance, -.5 * gravity * elapsed * elapsed)


class EffectTrack:
    """One delayed timeline with an optional completion callback.

    advance(dt) returns whether the track is finished. An overshoot emits only
    the clamped final progress; a zero duration emits 1 immediately once delay
    expires. Completion is committed before calling user code, so reentrant or
    subsequent advances cannot fire completion twice. cancel() finishes a track
    without callbacks, which lets reset/undo discard visual work safely.
    """

    def __init__(
        self,
        duration: float,
        update_callback: Callable[[float], None],
        on_complete: Callable[[], None] | None = None,
        delay: float = 0,
    ):
        self.duration = _number(duration, "duration", nonnegative=True)
        self.delay = _number(delay, "delay", nonnegative=True)
        if not callable(update_callback):
            raise ValueError("update_callback must be callable.")
        if on_complete is not None and not callable(on_complete):
            raise ValueError("on_complete must be callable or None.")
        self._update_callback = update_callback
        self._on_complete = on_complete
        self._elapsed = 0.0
        self._done = False
        self._cancelled = False

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def done(self) -> bool:
        return self._done

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        if not self._done:
            self._done = self._cancelled = True

    def advance(self, dt: float) -> bool:
        dt = _number(dt, "dt", nonnegative=True)
        if self._done:
            return True
        self._elapsed += dt
        if self._elapsed < self.delay:
            return False
        progress = (min(1.0, (self._elapsed - self.delay) / self.duration)
                    if self.duration else 1.0)
        complete = progress >= 1.0
        if complete:
            self._done = True
        try:
            self._update_callback(progress)
        finally:
            if complete and self._on_complete is not None:
                self._on_complete()
        return self._done


class Effects:
    """Own independent tracks; additions during update start on the next tick."""

    def __init__(self):
        self._tracks: list[EffectTrack] = []
        self._updating = False

    @property
    def busy(self) -> bool:
        return any(not track.done for track in self._tracks)

    def add(self, track: EffectTrack) -> EffectTrack:
        if not isinstance(track, EffectTrack):
            raise ValueError("Effects.add expects an EffectTrack.")
        if not track.done and track not in self._tracks:
            self._tracks.append(track)
        return track

    def clear(self) -> None:
        for track in self._tracks:
            track.cancel()
        self._tracks.clear()

    def update(self, dt: float) -> None:
        dt = _number(dt, "dt", nonnegative=True)
        if self._updating:
            raise RuntimeError("Effects.update cannot be called recursively.")
        self._updating = True
        try:
            for track in tuple(self._tracks):
                if not track.done:
                    track.advance(dt)
        finally:
            self._tracks = [track for track in self._tracks if not track.done]
            self._updating = False
