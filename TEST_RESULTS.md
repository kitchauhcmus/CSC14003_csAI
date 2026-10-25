# Validation and Test Summary

This document records functional verification and solver validation for Bloxorz 3D Solver. It supplements the installation instructions in [README.md](README.md).

## Recorded validation

| Check | Configuration | Recorded result | Date |
|---|---|---|---|
| Functional and integration suite | Windows, CPython 3.12, Panda3D 1.10.16; six-stage configuration; graphics test enabled | 103 tests passed and 87 subtests passed | 2026-10-24 |
| Full-stage solver benchmark | Windows 11, CPython 3.13.7, Panda3D 1.10.16; 13 stages, four algorithms, five repetitions | 260 of 260 runs solved; all returned paths validated | 2026-10-24 |

The functional-suite count refers to the configuration recorded on that date. Some integration tests are parameterized by the JSON files in `levels/`; adding stages changes the number of collected cases. The historical count is not an expected total for every later checkout.

## Functional coverage

The automated tests cover the following areas:

| Area | Coverage |
|---|---|
| Block movement | Upright and lying orientations, directional rolling, reverse moves, and immutable input states |
| Invalid moves | Void cells, closed bridges, fragile-tile failures, and invalid actions |
| Win condition | The intact block standing on the goal; undo and reset after completion |
| Switches and bridges | Soft versus heavy activation, bridge modes, and bridge changes affecting occupied tiles |
| Split blocks | Teleport destinations, independent cube selection, rejoining, and coordinate ordering |
| Session management | Move counts, selection, undo history, restart, and failure information |
| Search contracts | Weighted transitions, result serialization, UCS/A* behavior, and heuristic validation |
| Solver execution | Spawned processes, cancellation, timeout, cleanup, and replacing an active search |
| Solution playback | Path validation, current-state roots, forward/backward stepping, and speed changes |
| 3D presentation | Edge-pivot rolling, animation timing, bridge effects, falling, goal sinking, and fragile-tile breakup |
| GUI integration | Input focus, manual controls, solver invocation, automatic playback, split selection, and result export |

The graphics integration test requires an available graphics context and is opt-in.

## Solver benchmark validation

The recorded benchmark used:

- **13** stage JSON files.
- **BFS, DFS, UCS, and A***.
- **5** independent repetitions for each stage–algorithm pair.
- **260** measured runs in total.

Each run began at the stage's initial state, including its initial bridge configuration. A fresh spawned process executed each search; jobs ran sequentially with rotating stage and algorithm order.

For every returned solution, validation checked:

1. The first state matched `Board.initial_state()`.
2. The state sequence contained one more item than the action sequence.
3. Every action produced the next state through the shared rules engine.
4. The final state satisfied the goal condition.
5. The reported solution length matched the action count.

All 260 paths passed these checks. For each stage–algorithm pair, expanded-node counts, solution lengths, and action sequences were identical across the five repetitions. Hashes of the measured source and stage files were unchanged between the beginning and end of the experiment.

Performance tables, plots, environment details, and raw observations are provided in the accompanying experimental report.

## Measurement definitions

| Measurement | Scope |
|---|---|
| Search time | Solver `perf_counter` interval, including `tracemalloc` overhead; excludes stage parsing, process startup, graphics, IPC, and post-search path validation |
| Peak memory | Peak traced Python allocations during the search; reported separately from total process or GPU memory |
| Expanded nodes | States whose successors were expanded; excludes goal states and stale priority-queue entries |
| Solution length | Number of actions in the returned solution |

The benchmark reports the arithmetic mean and sample standard deviation across five runs. A maximum per-run peak-memory value is retained in the detailed results.

All actions have unit cost. A* uses a scaled Manhattan lower bound when no split teleporter is present, and a zero heuristic otherwise. DFS is not expected to return a shortest solution.

## Reproducing the functional tests

From the directory containing `main.py`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

To run the graphics integration test:

```powershell
$env:BLOXORZ_GRAPHICS_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest tests/test_app_delivery.py -q
```

Use the interpreter belonging to the environment created for this project. Record the Python version, dependency versions, stage set, and terminal output when reporting a new validation run.

## Interpretation

The recorded results apply to the tested versions and configurations. Runtime and peak allocations may differ across machines and Python versions. The 13-stage benchmark contains solvable stages; it does not establish performance on every possible board or on unsolvable instances.

Cancelled or forcibly timed-out searches may not provide final solver measurements and should be recorded separately from completed runs.

