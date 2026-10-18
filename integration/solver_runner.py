"""Run searches in a spawned process so rendering and input remain responsive."""

import math
import multiprocessing
import time

from core.board import Board
from core.state import State
from solvers import SOLVERS, SearchOptions, SearchResult

from .search_problem import make_search_problem


def _solver_worker(connection, job_id: int, board: Board, state: State,
                   algorithm: str, timeout_seconds: float, node_limit: int,
                   cancel_event) -> None:
    """Top-level spawn target: only data and a multiprocessing Event cross processes."""
    try:
        options = SearchOptions(timeout_seconds=timeout_seconds, node_limit=node_limit,
                                cancel_event=cancel_event)
        result = SOLVERS[algorithm](make_search_problem(board, state), options=options)
        connection.send((job_id, result, None))
    except Exception as exc:
        try:
            connection.send((job_id, None, f"{type(exc).__name__}: {exc}"))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        connection.close()


class SolverRunner:
    """One active search job; replacing a job discards its pipe and result."""

    def __init__(self):
        self._context = multiprocessing.get_context("spawn")
        self._process = None
        self._connection = None
        self._cancel_event = None
        self._job_id = 0
        self._deadline = 0.0
        self.error: str | None = None

    @property
    def running(self) -> bool:
        # A completed process can still have a result waiting for poll().
        return self._process is not None

    def start(self, board: Board, state: State, algorithm: str,
              timeout_seconds: float = 15.0, node_limit: int = 150000) -> int:
        if algorithm not in SOLVERS:
            raise ValueError(f"Unknown solver: {algorithm}")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Search timeout must be a finite positive number")
        if isinstance(node_limit, bool) or not isinstance(node_limit, int) or node_limit < 1:
            raise ValueError("Search node limit must be a positive integer")
        self.cancel()
        self.error = None
        self._job_id += 1
        receiver, sender = self._context.Pipe(duplex=False)
        self._cancel_event = self._context.Event()
        process = self._context.Process(
            target=_solver_worker,
            args=(sender, self._job_id, board, state, algorithm, timeout_seconds,
                  node_limit, self._cancel_event),
            daemon=True,
        )
        self._connection = receiver
        self._process = process
        # Allow a short grace period for startup/result serialization. The worker
        # enforces the actual search deadline; this parent deadline catches hangs.
        self._deadline = time.monotonic() + timeout_seconds + 1.0
        try:
            process.start()
        except Exception as exc:
            self.error = f"Could not start search: {exc}"
            receiver.close()
            self._connection = self._process = self._cancel_event = None
            raise RuntimeError(self.error) from exc
        finally:
            sender.close()
        return self._job_id

    def _reap(self, terminate: bool = False) -> None:
        process = self._process
        if process is not None:
            if terminate and process.is_alive():
                process.terminate()
            process.join(timeout=0.2)
            if process.is_alive():
                process.terminate()
                process.join(timeout=0.2)
            if process.is_alive():
                process.kill()
                process.join(timeout=0.2)
            if not process.is_alive():
                process.close()
        if self._connection is not None:
            self._connection.close()
        self._process = self._connection = self._cancel_event = None

    def poll(self) -> SearchResult | None:
        if self._process is None:
            return None
        try:
            if self._connection.poll():
                job_id, result, error = self._connection.recv()
                self._reap()
                if job_id != self._job_id:
                    return None
                self.error = error
                return result
        except (EOFError, OSError) as exc:
            self.error = f"Search worker disconnected: {exc}"
            self._reap(terminate=True)
            return None
        if not self._process.is_alive():
            exitcode = self._process.exitcode
            self.error = f"Search worker exited without a result (exit code {exitcode})."
            self._reap()
        elif time.monotonic() >= self._deadline:
            self.error = "Search exceeded its time limit and was stopped."
            self._reap(terminate=True)
        return None

    def cancel(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()
        self._reap()

    def close(self) -> None:
        self.cancel()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
