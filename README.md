# Bloxorz 3D Solver

A Python desktop application for playing Bloxorz and comparing Breadth-First Search (BFS), Depth-First Search (DFS), Uniform-Cost Search (UCS), and A*.

The application includes a 3D board, manual controls, solution playback, search metrics, and 13 JSON stages. Gameplay supports fragile tiles, bridges, soft and heavy switches, and block splitting and rejoining.

## Requirements and Python compatibility

- **CPython 3.10 or newer**, with a compatible Panda3D package for the selected Python version, operating system, and CPU architecture. A 64-bit installation is recommended.
- A desktop graphics environment with a working OpenGL driver.
- The dependencies listed in `requirements.txt`.
- Internet access during dependency installation. Gameplay and solving run locally afterward.

**Python 3.13 is not required.** Use a suitable version already installed on the machine.

The source uses Python 3.10 features, including union type annotations and slotted dataclasses; Python 3.9 and older are not supported by this source version. The pinned Panda3D 1.10.16 release currently provides packages for CPython 3.10–3.14 on supported platform combinations. See its [release files](https://pypi.org/project/Panda3D/1.10.16/#files) for the available Python, OS, and architecture tags.

Application validation has been recorded on **Windows 11 with CPython 3.12 and 3.13**. Installation commands for macOS and Linux are provided below; those platforms and other Python versions have not been validated locally. Newer Python versions also need a matching package for the pinned dependency.

## Quick start

Extract the archive and open a terminal in the directory containing `main.py` and `requirements.txt`.

Create a virtual environment on the machine that will run the program. The name `.venv` below is a directory name, not a required Python version. If an existing environment was created with another interpreter or copied from another machine, create a fresh environment.

### Windows — PowerShell

Check the Python version, create the environment, install dependencies, and start the application:

```powershell
py --version
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Verify that the first command reports Python 3.10 or newer and that Panda3D is available for that interpreter. If the `py` launcher is unavailable but `python` identifies an installed CPython interpreter, use these first two commands instead:

```powershell
python --version
python -m venv .venv
```

Then continue with the same `.venv\Scripts\python.exe` commands.

### macOS or Linux

```bash
python3 --version
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python main.py
```

Verify the reported Python version before creating the environment. On Linux, the distribution may require its Python virtual-environment package, commonly named `python3-venv`. A functioning desktop display and graphics driver are required.

These instructions call the virtual-environment interpreter directly; activating the environment is optional.

### Machines with several Python versions

Choose an installed interpreter that satisfies both the source and dependency requirements.

On Windows, list the available interpreters:

```powershell
py --list
```

For example, if a suitable Python 3.11 is installed, the environment can be created with:

```powershell
py -3.11 -m venv .venv
```

On macOS or Linux, an installed version-specific command can be used similarly:

```bash
python3.11 -m venv .venv
```

These are examples, not a requirement to install Python 3.11. Subsequent commands use the environment's interpreter, so their syntax stays the same regardless of the selected minor version.

If the environment has another name, such as `.venv313`, replace `.venv` in the commands with that actual directory name.

## Using VS Code

1. Open the directory containing `main.py` with **File → Open Folder**.
2. Follow the installation instructions for the operating system.
3. Open **Python: Select Interpreter** from the Command Palette.
4. Select the interpreter inside the environment created for this project:
   - Windows: `.venv\Scripts\python.exe`
   - macOS/Linux: `.venv/bin/python`
5. Run `main.py`, or use the terminal launch command above.

Wait for the opening animation to finish before moving the block or starting a search.

## Gameplay and controls

The objective is to place the intact block **upright on the goal hole**. A move fails if the block loses support over a void or a closed bridge. An upright intact block also breaks a fragile tile.

| Control | Action |
|---|---|
| Arrow keys or `W A S D` | Roll the block |
| `Space` or `Tab` | Select the other cube while the block is split |
| `Z` | Undo a manual move |
| `R` / **Reset** | Restart the current stage |
| **Stage selector** | Start a selected stage |
| **Solve BFS / DFS / UCS / A*** | Search from the current state |
| `P` / **Play–Pause** | Pause or resume solution playback |
| Playback buttons `\|<`, `<`, `>` | Return to the solution start, step backward, step forward |
| Speed slider | Set playback speed |
| `Q / E` | Rotate the camera |
| Right mouse drag | Rotate and tilt the camera |
| Mouse wheel | Zoom |
| `C` | Reset the camera |
| `F` | Toggle the expanded board view |
| `Esc` / **Cancel** | Cancel the current search and pause playback |

A successful search starts playback automatically. Manual movement is temporarily disabled while the block is animating, a search is active, or a solution is playing.

To compare algorithms from the same initial position, press **Reset** before each search and wait for the reset animation to finish.

## Search metrics

| Measurement | Definition |
|---|---|
| **Search Time** | Solver execution time measured with `perf_counter`, including memory-tracing overhead |
| **Python Peak Memory** | Peak Python allocations recorded by `tracemalloc`, displayed in KiB or MiB |
| **Expanded Nodes** | States for which successors were expanded; goal states and stale priority-queue entries are excluded |
| **Solution Length** | Number of actions in the returned solution |

Search Time excludes process startup, stage loading, graphics, and playback. Python Peak Memory measures traced Python allocations rather than total process RAM or GPU memory.

The GUI time limit controls the search worker's wall-clock lifetime, including startup. Cancelled or forcibly stopped searches may not provide final solver measurements.

### Algorithm configuration

- Every action has cost **1** in the search adapter.
- BFS and UCS therefore minimize the number of moves.
- DFS returns the first solution reached by its traversal order and does not guarantee a shortest path.
- A* uses a scaled Manhattan lower bound on stages without split teleporters. On stages containing split switches, it uses a zero heuristic and can behave like UCS.

Performance measurements should record the Python version, operating system, and hardware used. Results from different environments are not directly interchangeable.

## Stages

The `levels/` directory contains 13 stages:

| Stages | Main mechanics |
|---|---|
| 01–02 | Basic movement and board geometry |
| 03 | Fragile tiles |
| 04 and 06 | Switches and bridges |
| 05 | Splitting and rejoining |
| 07–08 | Combined fragile tiles, switches, and bridges |
| 09–13 | Combined mechanics with split teleporters and bridge dependencies |

Stages 01–06 introduce different mechanics and are not ordered strictly by difficulty. Stages 07–13 increase in both optimal solution length and BFS expansions.

### Loading a custom stage

Windows:

```powershell
.\.venv\Scripts\python.exe main.py --level levels/06_bridge_islands.json
```

macOS/Linux:

```bash
./.venv/bin/python main.py --level levels/06_bridge_islands.json
```

A stage can also be added as a JSON file under `levels/`. Restart the application to refresh the stage list.

Minimal example:

```json
{
  "name": "Two Rolls",
  "grid": [
    "S..G"
  ]
}
```

All grid rows must have the same length, and the grid must contain exactly one goal.

| Symbol | Meaning |
|---|---|
| `#` | Void |
| `.` | Floor |
| `S` | Starting floor tile |
| `G` | Goal hole |
| `F` | Fragile tile |
| `o` | Soft switch |
| `x` | Heavy switch |
| `(` | Split switch |
| `B` | Bridge tile |

Metadata coordinates are zero-based `[row, column]` pairs. Switch tiles require matching `switches` entries; split tiles require `split_switches` entries. The optional `initial_bridges` list identifies bridges that are initially open.

Complete examples:

- [Switch and bridge metadata](levels/04_switch.json)
- [Split destinations](levels/05_split.json)
- [Shared bridge controls](levels/09_shared_gate_relay.json)

Switch behaviors are `TOGGLE`, `PERMANENT_OPEN`, and `PERMANENT_CLOSE`. The latter two set their targets open or closed when triggered; another switch targeting the same bridge may change it afterward.

## Command-line options

| Option | Purpose |
|---|---|
| `--level PATH` | Load a stage JSON file |
| `--focus` | Start with an expanded board view |
| `--screenshot PNG` | Render an offscreen screenshot and exit |
| `--help` | Display command-line usage |

Windows examples:

```powershell
.\.venv\Scripts\python.exe main.py --focus
.\.venv\Scripts\python.exe main.py --screenshot preview.png
```

macOS/Linux examples:

```bash
./.venv/bin/python main.py --focus
./.venv/bin/python main.py --screenshot preview.png
```

Offscreen screenshots still require a working graphics context.

## Exporting a result

Select **Export result JSON** after a search to save `exports/last_result.json`. The export includes the board, actions, solution states, and metrics. A later export replaces that file.

Experimental tables, plots, and discussion are supplied separately in the project report.

## Project structure

```text
.
├── main.py                 # Application entry point
├── core/                   # Board, state, actions, and gameplay rules
├── solvers/                # BFS, DFS, UCS, A*, and shared search types
├── integration/            # Game session, solver worker, and playback
├── gui/                    # Panda3D application, scene, and effects
├── levels/                 # JSON stages
├── tests/                  # Automated tests
├── examples/               # Search API examples
├── algorithms.py           # Public search compatibility imports
├── iama/                   # Compatibility import package
├── requirements.txt        # Runtime dependencies
├── requirements-dev.txt    # Test dependencies
├── pytest.ini              # Test configuration
├── README.md
└── TEST_RESULTS.md         # Validation records and reproduction notes
```

## Running the tests

Test dependencies are optional for playing the game.

Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

macOS/Linux:

```bash
./.venv/bin/python -m pip install -r requirements-dev.txt
./.venv/bin/python -m pytest -q
```

The graphics integration test is disabled by default. Enable it with a real offscreen graphics context:

Windows PowerShell:

```powershell
$env:BLOXORZ_GRAPHICS_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest tests/test_app_delivery.py -q
```

macOS/Linux:

```bash
BLOXORZ_GRAPHICS_TESTS=1 ./.venv/bin/python -m pytest tests/test_app_delivery.py -q
```

See [TEST_RESULTS.md](TEST_RESULTS.md) for test scope and recorded validation results.

## Sharing the project for testing

Send the source archive, including `main.py`, the source directories, `levels/`, and the requirements files. Each recipient should extract it and follow the setup instructions on their own machine.

Virtual environments such as `.venv` and `.venv313` contain machine-specific interpreter paths. Create them locally rather than distributing them with the project. Runtime caches and generated exports are also unnecessary for installation.

For a useful test report, include the operating system, Python version, the command that failed, and the full error message. Check the selected environment with:

Windows:

```powershell
.\.venv\Scripts\python.exe -c "import sys, platform; print(sys.executable); print(sys.version); print(platform.platform())"
```

macOS/Linux:

```bash
./.venv/bin/python -c "import sys, platform; print(sys.executable); print(sys.version); print(platform.platform())"
```

## Troubleshooting

| Symptom | Resolution |
|---|---|
| `py`, `python`, or `python3` is not found | Install [CPython](https://www.python.org/downloads/) and reopen the terminal; use the command available on the operating system |
| Python is older than 3.10 | Select an installed CPython 3.10+ interpreter, or install one with a matching Panda3D package |
| `No suitable Python runtime found` | List the installed versions and select one that actually exists on the machine |
| `No matching distribution found for panda3d` | Update pip inside the environment and check the [Panda3D release files](https://pypi.org/project/Panda3D/1.10.16/#files); choose an interpreter and platform combination with a matching package |
| A newly released Python version has no compatible Panda3D package | Use an installed version for which the pinned dependency publishes a package |
| `venv` or `ensurepip` is unavailable on Linux | Install the distribution's virtual-environment support for the selected Python |
| `requirements.txt` or `main.py` is not found | Open a terminal in the project directory containing those files |
| `No module named panda3d` | Install requirements using the same virtual-environment interpreter used to launch the application |
| Installation uses an MSYS2/MinGW Python with incompatible wheel tags | Use a standard CPython installation with a package matching the operating system |
| Panda3D cannot create a graphics context | Check the desktop display, graphics-driver installation, and OpenGL availability |
| A large stage reaches the time limit | Increase the GUI time limit, up to 300 seconds, or compare another algorithm |

Panda3D startup messages such as `Known pipe types` and `wglGraphicsPipe` are informational on Windows.
