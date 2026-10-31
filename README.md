# Bloxorz 3D Solver

[GitHub repository](https://github.com/kitchauhcmus/CSC14003_csAI) · [Demo video](https://youtu.be/rDvzEJw_0O4)

## Setup

Requires **Python 3.10 or later** and a graphics environment with OpenGL support.

Extract the source code, open a terminal in the folder containing `main.py`, and run:

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

If your system uses the `py` launcher, replace `python` in the first command with `py`. These commands do not require activating the virtual environment.

**macOS / Linux:**

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python main.py
```

The macOS/Linux commands have not been validated locally. A compatible Panda3D package must be available for your operating system and Python version.

## Controls

Select a stage and move the block upright onto the goal. When the block splits, move the two cubes next to each other to rejoin them.

| Key / action | Function |
| --- | --- |
| Arrow keys or W/A/S/D | Move |
| Space / Tab | Switch the selected cube when split |
| Z | Undo |
| R / Reset button | Restart the current stage |
| P | Play / pause the solution |
| Q/E or right-mouse drag | Rotate the view |
| Mouse wheel / C | Zoom / reset the camera |
| F | Toggle the expanded board view |
| Esc / Cancel button | Cancel the search or pause playback |

## Solving

- Click **Solve BFS / DFS / UCS / A\*** to solve from the **current state**. Click **Reset** before each run to compare algorithms from the same starting point.
- Solutions play automatically. You can pause, step forward or backward, restart playback, and adjust the speed.
- The interface shows search time, peak memory, expanded nodes, and solution length. Memory is measured with `tracemalloc` and covers traced Python allocations, not total application RAM.
- **Export result JSON** saves to `exports/last_result.json`, overwriting the previous export.

Each action costs 1. DFS does not guarantee the shortest solution. A* uses a Manhattan-based heuristic on stages without split switches and a zero heuristic on stages with split switches.

## Tests

Install the development dependencies and run the test suite (Windows):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

The GUI test requires a graphics context and is skipped by default. To run it separately:

```powershell
$env:BLOXORZ_GRAPHICS_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest tests/test_app_delivery.py -q
```

On macOS/Linux, use `./.venv/bin/python` and prefix the GUI test command with `BLOXORZ_GRAPHICS_TESTS=1`. See [TEST_RESULTS.md](TEST_RESULTS.md) for previously recorded results.

## Project structure

```text
main.py         Application entry point
core/           Board, state representation, and movement rules
solvers/        BFS, DFS, UCS, A*, and heuristics
integration/    Game sessions, solver execution, and playback
gui/            Panda3D interface and 3D rendering
levels/         13 JSON stages
tests/          Engine, solver, integration, and GUI tests
```

Additional advanced-mechanics tests are in `core/test_advanced_mechanics.py`. Run all commands from the project root.
