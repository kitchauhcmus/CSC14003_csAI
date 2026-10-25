"""One isolated solver process; no modifications to search algorithms."""
import math
import multiprocessing as mp
from time import monotonic

from solvers import bfs, dfs, ucs, astar, make_manhattan_heuristic
from .search_problem import make_search_problem

SOLVERS = {"BFS": bfs, "DFS": dfs, "UCS": ucs, "A*": astar}

def _worker(sender, job_id, board, state, algorithm):
    try:
        problem = make_search_problem(board, state)
        if algorithm == "A*":
            # The team's Manhattan lower bound is invalid for teleport levels.
            heuristic = None if board.split_switches else make_manhattan_heuristic(board.goal_pos)
            result = astar(problem, heuristic)
        else:
            result = SOLVERS[algorithm](problem)
        sender.send((job_id, result, None))
    except Exception as exc:
        sender.send((job_id, None, f"{type(exc).__name__}: {exc}"))
    finally:
        sender.close()

class SolverRunner:
    def __init__(self):
        self.context = mp.get_context("spawn")
        self.process = None
        self.receiver = None
        self.error = None
        self.completion_status = None
        self._job_id = 0
        self._deadline = None

    @property
    def running(self):
        return self.process is not None

    def start(self, board, state, algorithm, *, timeout_seconds=30):
        if algorithm not in SOLVERS:
            raise ValueError("Unknown algorithm: " + str(algorithm))
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Time limit must be finite and positive")
        self.cancel()
        self.error = None
        self.completion_status = None
        self._job_id += 1
        receiver, sender = self.context.Pipe(duplex=False)
        process = self.context.Process(target=_worker,
            args=(sender, self._job_id, board, state, algorithm), daemon=True)
        try:
            process.start()
        except Exception:
            receiver.close()
            sender.close()
            try:
                process.close()
            except ValueError:
                pass
            raise
        sender.close()
        self.receiver, self.process = receiver, process
        # Includes process startup; final search_time is the solver's own metric.
        self._deadline = monotonic() + float(timeout_seconds)

    def poll(self):
        if self.process is None:
            return None
        try:
            if self.receiver.poll():
                job_id, result, error = self.receiver.recv()
                self._reap()
                if job_id != self._job_id:
                    return None
                self.error = error
                self.completion_status = "error" if error else result.status
                return result
        except (EOFError, OSError) as exc:
            self.error = "Search worker disconnected: " + str(exc)
            self.completion_status = "error"
            self._reap()
            return None
        if not self.process.is_alive():
            self.error = f"Search worker exited without a result (code {self.process.exitcode})."
            self.completion_status = "error"
            self._reap()
        elif monotonic() >= self._deadline:
            self.error = "Time limit reached. Final solver metrics are unavailable."
            self.completion_status = "timeout"
            self._reap(terminate=True)
        return None

    def _reap(self, *, terminate=False):
        process, receiver = self.process, self.receiver
        self.process = self.receiver = None
        self._deadline = None
        if process is not None:
            if terminate and process.is_alive():
                process.terminate()
            process.join(.15)
            if process.is_alive():
                process.terminate()
                process.join(.15)
            if process.is_alive():
                process.kill()
                process.join(.15)
            if not process.is_alive():
                process.close()
        if receiver is not None:
            receiver.close()

    def cancel(self):
        if self.process is not None:
            self._reap(terminate=True)
            self.completion_status = "cancelled"

    def close(self):
        self.cancel()

