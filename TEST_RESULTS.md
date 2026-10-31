# Validation and Test Results

Recorded checks for Bloxorz 3D Solver. See [README.md](README.md) for installation and usage. The benchmark below is the run used for the report's performance tables and plots.

## Environment

- **CPU:** AMD Ryzen 7 7735HS.
- **RAM recognized by the operating system:** approximately 15.19 GiB.
- **Operating system:** Windows 11, 64-bit.
- **Python:** CPython 3.12.14.
- **Graphics library:** Panda3D 1.10.16. The solver benchmark ran without the GUI.

## Recorded checks

| Check | Result | Date |
|---|---|---|
| Functional and integration suite, 13-stage configuration | 130 tests passed, 1 GUI test skipped; 87 subtests passed | 2026-10-31 |
| Opt-in GUI integration test, run separately | 1 test passed | 2026-10-31 |
| Benchmark used in the report: 13 stages, 4 algorithms, 5 repetitions | 260 of 260 runs solved; all returned paths validated | 2026-10-25 |

The GUI test was skipped in the first run because it is opt-in, then passed when run separately. Test counts can change if the stage set or tests are updated.

## Functional coverage

- **Game rules:** movement, invalid moves, goal detection, fragile tiles, switches, bridges, splitting, teleporting, and merging.
- **Search:** legal solution paths, duplicate handling, weighted test graphs, UCS/A* optimality checks, and heuristics.
- **Integration:** undo/reset, cube selection, solver processes, cancellation, timeouts, and solution playback.
- **Graphics and GUI:** animation, keyboard input, automatic playback, split selection, and JSON export. The GUI integration test uses a real offscreen graphics context.

## Benchmark used in the report

BFS, DFS, UCS, and A* ran on the same **13 JSON stages**, **5 times per stage and algorithm** (260 runs). Every search started from `Board.initial_state()`. Runs used fresh processes and executed sequentially, with stage and algorithm order rotated between repetitions.

All returned paths were checked for the correct initial state, matching state/action counts, legal transitions, a final goal state, and the reported solution length. All 260 paths passed. Expanded-node counts, solution lengths, and action sequences were identical across repetitions for each stage-algorithm pair.

All game actions cost 1. A* uses the Manhattan lower bound on stages without split switches and a zero heuristic on stages with split switches. Weighted graphs are separate unit tests. DFS does not guarantee the shortest solution.

Performance tables and plots are in the report. The benchmark script, raw measurements, and environment logs are maintained separately from this game-source package; the commands below run the functional tests, not the performance benchmark.

## Measurement definitions

| Measurement | Scope |
|---|---|
| Search time | Solver `perf_counter` interval, including memory tracking; excludes loading, process startup, GUI, and post-search validation |
| Peak memory | Peak Python allocations tracked by `tracemalloc`, not total process RAM or GPU memory |
| Expanded nodes | Number of state expansions; excludes the goal and stale heap entries, but includes any re-expansions |
| Solution length | Number of returned actions, including individual split-cube moves; switching cube selection is not counted |

Time and peak memory are reported as **mean ± sample standard deviation** over five runs. All algorithms used the same machine and measurement method. Time and memory may differ across machines or Python versions; the benchmark covers these 13 solvable stages.

## Reproducing the functional tests

After setting up the environment in the README, run from the project root (Windows PowerShell):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:BLOXORZ_GRAPHICS_TESTS = "0"
.\.venv\Scripts\python.exe -m pytest -q
```

To run the graphics integration test:

```powershell
$env:BLOXORZ_GRAPHICS_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest tests/test_app_delivery.py -q
```

Record the environment and terminal output when reporting a new test run. Cancelled or timed-out searches are not completed benchmark results and may have no final solver metrics.

