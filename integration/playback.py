"""Deterministic, reversible solution playback independent of manual history."""

import math

from core.rules import apply_action as apply_rule_action, is_goal
from solvers import SearchResult

from .session import GameSession


class PlaybackController:
    def __init__(self, session: GameSession):
        self.session = session
        self.playing = False
        self.index = 0
        self.error: str | None = None
        self._speed = 2.0
        self._elapsed = 0.0
        self._result: SearchResult | None = None
        self._snapshots = []

    @property
    def has_result(self) -> bool:
        return self._result is not None

    @property
    def speed(self) -> float:
        return self._speed

    @speed.setter
    def speed(self, value: float) -> None:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Playback speed must be a finite positive number")
        # Retain the fraction of the current step, not wall time accumulated at
        # the old speed. Increasing speed must not consume several steps at once.
        self._elapsed *= self._speed / float(value)
        self._speed = float(value)

    def load(self, result: SearchResult) -> None:
        if not result.solved or len(result.states) != len(result.actions) + 1:
            raise ValueError("Playback requires a solved result with its complete state path")
        if not is_goal(self.session.board, result.states[-1]):
            raise ValueError("The solution does not finish at this stage's goal")
        # Reject a stale result from another stage or a broken solver path before
        # replacing the player's state. Every action must use the shared rules.
        for before, action, expected in zip(result.states, result.actions, result.states[1:]):
            if apply_rule_action(self.session.board, before, action) != expected:
                raise ValueError("The solution contains an invalid transition for this stage")
        self.pause()
        self.error = None
        self._result = result
        self.index = 0
        matching_start = self.session.state == result.states[0]
        count = self.session.move_count if matching_start else 0
        selection = self.session.selected_position if matching_start else None
        self.session._begin_at(result.states[0], count, selection)
        self._snapshots = [self.session._snapshot()]

    def play(self) -> None:
        self.playing = bool(self._result and self.index < len(self._result.actions)
                            and self.error is None)

    def pause(self) -> None:
        self.playing = False
        self._elapsed = 0.0

    def _fail(self, message: str) -> bool:
        self.pause()
        self.error = message
        self.session.message = message
        return False

    def step_forward(self) -> bool:
        if self._result is None or self.index >= len(self._result.actions):
            self.pause()
            return False
        if self.session.state != self._result.states[self.index]:
            return self._fail("The game changed. Restart playback or solve from the current state.")
        action = self._result.actions[self.index]
        expected = self._result.states[self.index + 1]
        if apply_rule_action(self.session.board, self.session.state, action) != expected:
            return self._fail("Playback stopped because the solution does not match the game rules.")
        if not self.session.apply_action(action):
            return self._fail("Playback cannot continue from the current game status.")
        self.index += 1
        snapshot = self.session._snapshot()
        if len(self._snapshots) > self.index:
            self._snapshots[self.index] = snapshot
        else:
            self._snapshots.append(snapshot)
        if self.index == len(self._result.actions):
            self.pause()
        return True

    def step_back(self) -> bool:
        self.pause()
        if self._result is None or self.index == 0:
            return False
        self.index -= 1
        self.session._restore(self._snapshots[self.index])
        self.session._history = list(self._snapshots[:self.index])
        self.error = None
        return True

    def restart(self) -> None:
        self.pause()
        if self._result is None:
            return
        self.index = 0
        self.error = None
        self.session._restore(self._snapshots[0])
        self.session._history.clear()

    def update(self, dt: float, max_steps: int | None = None) -> None:
        """Advance time while optionally limiting transitions per render frame.

        A busy scene can pass zero to retain elapsed playback time without
        changing the model; unused time remains available on subsequent frames.
        """
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("Frame time must be a finite nonnegative number")
        if max_steps is not None and (type(max_steps) is not int or max_steps < 0):
            raise ValueError("max_steps must be a nonnegative integer or None")
        if not self.playing:
            return
        self._elapsed += dt
        interval = 1.0 / self.speed
        steps = 0
        while (self.playing and self._elapsed >= interval
               and (max_steps is None or steps < max_steps)):
            self._elapsed -= interval
            if not self.step_forward():
                break
            steps += 1

