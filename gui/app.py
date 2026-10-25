"""Panda3D application: one responsive render loop, isolated search workers."""

import json
from pathlib import Path
from time import perf_counter

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectEntry, DirectFrame, DirectLabel, DirectOptionMenu, DirectSlider
from direct.showbase.ShowBase import ShowBase
from panda3d.core import Filename, TextNode, loadPrcFileData

from core.board import Board
from core.constants import Direction
from gui.scene import BoardScene
from integration import GameSession, PlaybackController, SolverRunner

ROOT = Path(__file__).resolve().parents[1]
INK = (.88, .94, .97, 1)
MUTED = (.47, .60, .68, 1)
ACCENT = (.23, .86, .73, 1)
PANEL = (.045, .075, .105, 1)
BUTTON = (.12, .20, .26, 1)


class BloxorzApp(ShowBase):
    def __init__(self, level_path=None, *, offscreen=False):
        loadPrcFileData("bloxorz", "\n".join((
            "window-title Bloxorz | 3D Solver Lab", "win-size 1440 900",
            "sync-video true", "show-frame-rate-meter false", "audio-library-name null",
            "framebuffer-multisample 1", "multisamples 4", "textures-power-2 none",
            "notify-level warning",
        )))
        super().__init__(windowType="offscreen" if offscreen else None)
        if self.win is None:
            raise RuntimeError("Unable to create a 3D graphics context. Check your graphics driver.")
        self.disableMouse()
        self.setBackgroundColor(.065, .10, .14, 1)
        self.camLens.setNearFar(.1, 500)
        self.camLens.setFov(43)
        self._load_font()
        self.runner = SolverRunner()
        self.scene = BoardScene(self)
        self.level_paths = sorted((ROOT / "levels").glob("*.json"))
        if level_path is not None:
            path = Path(level_path).resolve()
            if path not in self.level_paths:
                self.level_paths.insert(0, path)
        else:
            if not self.level_paths:
                raise ValueError("No level JSON files found in levels/.")
            path = self.level_paths[0]
        self.level_names = []
        for file_path in self.level_paths:
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("A level must contain a JSON object")
                name = file_path.stem + " / " + str(data.get("name", file_path.stem))
            except (ValueError, OSError):
                name = file_path.stem + " [invalid]"
            self.level_names.append(str(name))
        self.session = GameSession(Board.from_json(path))
        self.playback = PlaybackController(self.session)
        self.algorithm = "BFS"
        self.last_result = None
        self.notice = "Ready. Roll the block upright into the square goal."
        self.notice_error = False
        self._search_started = 0.0
        self._closed = False
        self._drag = None
        self.focus_mode = False
        self._ui_ready = False
        self._ui()
        self._bind_keys()
        self._ui_ready = True
        self.scene.set_board(self.session.board, self.session.state, self.session.selected_position)
        self.accept("window-event", self._resize)
        self._resize(self.win)
        self.taskMgr.add(self._tick, "bloxorz-update")
        self._refresh()

    def _load_font(self):
        candidates = (Path("C:/Windows/Fonts/segoeui.ttf"),
                      Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                      Path("/System/Library/Fonts/Supplemental/Arial.ttf"))
        for path in candidates:
            if path.exists():
                font = self.loader.loadFont(str(Filename.fromOsSpecific(str(path))))
                font.setPixelsPerUnit(90)
                DGG.setDefaultFont(font)
                break

    def _label(self, parent, text, x, z, scale=.035, color=INK, **kwargs):
        kwargs.setdefault("text_align", TextNode.ALeft)
        return DirectLabel(parent=parent, text=text, pos=(x, 0, z), scale=scale,
                           text_fg=color, frameColor=(0, 0, 0, 0),
                           textMayChange=True, **kwargs)

    def _button(self, parent, text, x, z, width, command, *, accent=False):
        return DirectButton(parent=parent, text=text, pos=(x, 0, z), scale=1,
                            frameSize=(-width/2, width/2, -.045, .045),
                            text_scale=.035, text_pos=(0, -.012), text_fg=PANEL if accent else INK,
                            frameColor=ACCENT if accent else BUTTON,
                            relief=DGG.FLAT, pressEffect=False, command=command,
                            rolloverSound=None, clickSound=None)

    def _ui(self):
        left = DirectFrame(parent=self.a2dTopLeft, frameSize=(0, .78, -2, 0), frameColor=PANEL)
        right = DirectFrame(parent=self.a2dTopRight, pos=(-.66, 0, 0),
                            frameSize=(0, .66, -2, 0), frameColor=PANEL)
        self.side_panels = (left, right)
        self._label(left, "CSC14003  /  AI LAB", .075, -.095, .027, ACCENT)
        self._label(left, "BLOXORZ", .07, -.245, .082)
        self._label(left, "3D SOLVER", .075, -.335, .052, MUTED)
        self._label(left, "01  /  CHOOSE A STAGE", .075, -.47, .027, ACCENT)
        self.level_menu = DirectOptionMenu(
            parent=left, items=self.level_names, initialitem=self.level_paths.index(Path(self._current_path()).resolve()),
            pos=(.075, 0, -.58), scale=.035, text_fg=INK, text_align=TextNode.ALeft,
            frameColor=BUTTON, highlightColor=(.18, .33, .38, 1), relief=DGG.FLAT,
            command=self._choose_level, popupMarker_scale=.6,
        )
        self.stage_info = self._label(left, "", .075, -.72, .032, MUTED)
        self._label(left, "ROLL TO THE GOAL", .075, -.87, .027, ACCENT)
        self.move_label = self._label(left, "00", .075, -1.00, .09)
        self.mode_label = self._label(left, "moves", .26, -1.00, .031, MUTED)
        self._button(left, "W / ^", .39, -1.11, .17, lambda: self.move(Direction.UP))
        self._button(left, "A / <", .19, -1.23, .17, lambda: self.move(Direction.LEFT))
        self._button(left, "S / v", .39, -1.23, .17, lambda: self.move(Direction.DOWN))
        self._button(left, "D / >", .59, -1.23, .17, lambda: self.move(Direction.RIGHT))
        self._button(left, "Undo [Z]", .225, -1.39, .30, self.undo)
        self._button(left, "Reset [R]", .555, -1.39, .30, self.reset)
        self.split_button = self._button(left, "Switch cube [Space]", .39, -1.52, .63, self.select_cube)
        self._label(left, "CAMERA", .075, -1.66, .027, ACCENT)
        self._label(left, "Q / E   Orbit     Wheel   Zoom\nRight drag   Orbit / tilt\nC   Reset view     F   Focus", .075, -1.74, .029, MUTED,
                    text_wordwrap=24)
        self._label(left, "Built in Python + Panda3D", .075, -1.95, .023, MUTED)

        self._label(right, "02  /  SEARCH", .055, -.095, .027, ACCENT)
        self.solve_buttons = []
        for algorithm, x, z in (("BFS", .18, -.23), ("DFS", .48, -.23),
                                 ("UCS", .18, -.36), ("A*", .48, -.36)):
            self.solve_buttons.append(self._button(
                right, "Solve " + algorithm, x, z, .26,
                lambda name=algorithm: self.solve(name), accent=True))
        self._label(right, "TIME LIMIT / s", .055, -.47, .025, MUTED)
        self.timeout_entry = DirectEntry(
            parent=right, pos=(.06, 0, -.55), scale=.038,
            initialText="30", width=4.8, numLines=1,
            text_fg=INK, frameColor=BUTTON, relief=DGG.FLAT)
        self.cancel_button = self._button(right, "Cancel", .46, -.53, .28, self.cancel_search)
        self._label(right, "Wall-clock limit; includes worker startup.", .055, -.65, .022, MUTED)
        self._label(right, "SEARCH RESULT", .055, -.82, .027, ACCENT)
        self.result_status = self._label(right, "No search yet", .055, -.91, .034)
        self.metric_labels = {}
        for i, (key, title) in enumerate((("time", "Time"), ("expanded", "Expanded"),
                                          ("memory", "Python peak"), ("length", "Solution steps"))):
            z = -1.015 - i*.09
            self._label(right, title, .055, z, .029, MUTED)
            self.metric_labels[key] = self._label(right, "--", .36, z, .03)
        self._label(right, "03  /  PLAYBACK", .055, -1.43, .027, ACCENT)
        self.timeline_label = self._label(right, "Solve to unlock playback", .055, -1.51, .028, MUTED)
        self.replay_button = self._button(right, "|<", .125, -1.62, .13, self.restart_playback)
        self.back_button = self._button(right, "<", .275, -1.62, .13, self.step_back)
        self.next_button = self._button(right, ">", .425, -1.62, .13, self.step_forward)
        self.play_button = self._button(right, "Play", .575, -1.62, .13, self.toggle_playback)
        self.speed_label = self._label(right, "2.0 steps / s", .055, -1.73, .027, MUTED)
        self.speed_slider = DirectSlider(parent=right, pos=(.33, 0, -1.80), scale=.26,
                                        range=(.5, 4), value=2, pageSize=.5,
                                        frameColor=BUTTON, thumb_frameColor=ACCENT,
                                        command=self._set_speed)
        self.export_button = self._button(right, "Export result JSON", .33, -1.92, .55, self.export_result)
        self.header = self._label(self.aspect2d, "", -.06, .86, .047)
        self.subheader = self._label(self.aspect2d, "", -.06, .79, .026, MUTED)
        self.focus_return = self._button(self.a2dTopRight, "Controls [F]", -.22, -.10, .33, self.toggle_focus)
        self.focus_moves = self._label(self.a2dTopLeft, "", .08, -.12, .04)
        self.focus_return.hide()
        self.focus_moves.hide()
        self.status_label = DirectLabel(parent=self.aspect2d, text="", pos=(.06, 0, -.86),
                                        text_scale=.034, text_fg=INK, text_wordwrap=43,
                                        frameColor=(0, 0, 0, 0), textMayChange=True)
        legends = (("Goal", (.22, .91, .76, 1)), ("Fragile", (.91, .48, .20, 1)),
                   ("Soft", (.19, .65, .68, 1)), ("Heavy", (.60, .40, .85, 1)),
                   ("Split", (.83, .40, .64, 1)), ("Bridge", (.20, .57, .49, 1)))
        for index, (title, color) in enumerate(legends):
            x = -.64 + index*.245
            DirectFrame(parent=self.aspect2d, pos=(x, 0, -.962),
                        frameSize=(-.011, .011, -.011, .011), frameColor=color)
            self._label(self.aspect2d, title, x+.025, -.972, .025, MUTED)

    def _current_path(self):
        # The constructor's board name is not required to equal the file name.
        for path in self.level_paths:
            try:
                if Board.from_json(path) == self.session.board:
                    return path
            except (ValueError, OSError):
                continue
        return self.level_paths[0]

    def _bind_keys(self):
        for names, direction in ((("arrow_up", "w"), Direction.UP), (("arrow_down", "s"), Direction.DOWN),
                                 (("arrow_left", "a"), Direction.LEFT), (("arrow_right", "d"), Direction.RIGHT)):
            for key in names:
                self.accept(key, self._key, [self.move, direction])
        for key, callback in (("z", self.undo), ("r", self.reset), ("tab", self.select_cube),
                              ("space", self.select_cube), ("p", self.toggle_playback), ("enter", self.solve),
                              ("c", self.scene.reset_camera), ("escape", self.cancel_search)):
            self.accept(key, callback if key in ("enter", "escape") else self._key,
                        [] if key in ("enter", "escape") else [callback])
        self.accept("f", self._key, [self.toggle_focus])
        self.accept("q", self._key, [self.scene.orbit, -15])
        self.accept("e", self._key, [self.scene.orbit, 15])
        self.accept("wheel_up", self.scene.zoom_by, [.9])
        self.accept("wheel_down", self.scene.zoom_by, [1.1])
        self.accept("mouse3", self._start_drag)
        self.accept("mouse3-up", self._stop_drag)

    def _typing(self):
        return bool(self.timeout_entry.guiItem.getFocus())

    def _key(self, callback, *args):
        if not self._typing():
            callback(*args)

    def toggle_focus(self):
        self.focus_mode = not self.focus_mode
        for panel in self.side_panels:
            panel.hide() if self.focus_mode else panel.show()
        for widget in (self.focus_return, self.focus_moves):
            widget.show() if self.focus_mode else widget.hide()
        self._resize(self.win)

    def _set_notice(self, text, error=False):
        self.notice, self.notice_error = text, error

    def _choose_level(self, name):
        if not self._ui_ready:
            return
        index = self.level_names.index(name)
        try:
            board = Board.from_json(self.level_paths[index])
        except (ValueError, OSError) as exc:
            self._set_notice(str(exc), True)
            return
        self.runner.cancel()
        self.session = GameSession(board)
        self.playback = PlaybackController(self.session)
        self.last_result = None
        self.playback.speed = float(self.speed_slider["value"])
        self.scene.set_board(board, self.session.state, self.session.selected_position)
        self._set_notice("Stage loaded. Solve from any valid position.")

    def _choose_algorithm(self, algorithm):
        self.algorithm = algorithm

    def _set_speed(self):
        if hasattr(self, "speed_slider"):
            self.playback.speed = float(self.speed_slider["value"])

    def _clear_playback(self):
        self.playback.pause()
        self.playback = PlaybackController(self.session)
        self.playback.speed = float(self.speed_slider["value"])

    def move(self, direction):
        if self.runner.running or self.scene.busy or self.playback.playing:
            return
        if self.session.status != "playing":
            self._set_notice("Press R to restart or Z to undo.")
            return
        self._clear_playback()
        previous = self.session.state
        from core.constants import Action
        selected = self.session.selected_position
        index = previous.positions.index(selected) if previous.is_split and selected in previous.positions else None
        action = Action.from_input(direction, index)
        moved = self.session.move(direction)
        if moved:
            self.scene.transition(previous, self.session.state, self.session.selected_position, action)
            self._set_notice("Goal reached. Well played!" if self.session.status == "won" else "Your move.")
        else:
            if self.session.status == "lost":
                self.scene.fall(previous, action, reason=self.session.last_failure,
                                target=self.session.last_attempt_state)
            self._set_notice(self.session.message or "The block fell. Undo or reset to try again.", True)

    def reset(self):
        self.runner.cancel()
        self.session.reset()
        self._clear_playback()
        self.last_result = None
        self.scene.restart(self.session.state, self.session.selected_position)
        self._set_notice("Stage reset.")

    def undo(self):
        if self.runner.running:
            return
        if self.playback.has_result:
            self.step_back()
            return
        if self.session.undo():
            self.scene.set_state(self.session.state, self.session.selected_position)
            self._set_notice("Move undone.")

    def select_cube(self):
        if self.runner.running or self.playback.playing or self.scene.busy:
            return
        self.session.select_next_cube()
        self.scene.set_state(self.session.state, self.session.selected_position)

    def solve(self, algorithm=None):
        if algorithm is not None:
            self.algorithm = algorithm
        if self.runner.running or self.scene.busy:
            return
        if self.session.status == "lost":
            self._set_notice("Undo or reset the failed move before solving.", True)
            return
        try:
            timeout = float(self.timeout_entry.get())
            if not 0 < timeout <= 300:
                raise ValueError
        except ValueError:
            self._set_notice("Use a time limit greater than 0 and at most 300 seconds.", True)
            return
        self._clear_playback()
        self.last_result = None
        self.timeout_entry["focus"] = False
        try:
            self.runner.start(self.session.board, self.session.state, self.algorithm,
                              timeout_seconds=timeout)
        except (OSError, RuntimeError, ValueError) as exc:
            self._set_notice("Unable to start search: " + str(exc), True)
            return
        self._search_started = perf_counter()
        self._set_notice("Searching from the current state. Camera controls remain available.")

    def cancel_search(self):
        if self.runner.running:
            self.runner.cancel()
            self._set_notice("Search cancelled.")
        self.playback.pause()

    def toggle_playback(self):
        if not self.playback.has_result or self.runner.running:
            return
        if self.playback.playing:
            self.playback.pause()
        else:
            self.playback.play()

    def step_forward(self):
        if self.runner.running or self.scene.busy:
            return
        self.playback.pause()
        previous = self.session.state
        index = self.playback.index
        if self.playback.step_forward():
            action = self.last_result.actions[index] if self.last_result else None
            self.scene.transition(previous, self.session.state, self.session.selected_position, action)

    def step_back(self):
        if self.runner.running:
            return
        self.playback.pause()
        if self.playback.step_back():
            self.scene.set_state(self.session.state, self.session.selected_position)

    def restart_playback(self):
        if self.playback.has_result and not self.runner.running:
            self.playback.restart()
            self.scene.set_state(self.session.state, self.session.selected_position)

    def export_result(self):
        if self.last_result is None:
            return
        try:
            folder = ROOT / "exports"
            folder.mkdir(exist_ok=True)
            path = folder / "last_result.json"
            data = self.last_result.to_dict(include_states=True)
            data["board"] = self.session.board.to_dict()
            data["notes"] = {"memory": "Peak traced Python allocations; not total process RAM.",
                             "astar": "Team Manhattan lower bound on non-teleport stages; zero on split-switch stages."}
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self._set_notice("Saved to exports/last_result.json")
        except (OSError, ValueError) as exc:
            self._set_notice("Export failed: " + str(exc), True)

    def _start_drag(self):
        if self.mouseWatcherNode.hasMouse():
            point = self.mouseWatcherNode.getMouse()
            # Dragging starts only inside the scene, avoiding UI controls.
            aspect = self.getAspectRatio()
            x = point.x*aspect
            if self.focus_mode or -aspect+.78 < x < aspect-.66:
                self._drag = (point.x, point.y)

    def _stop_drag(self):
        self._drag = None

    def _resize(self, window):
        if window is None or not self._ui_ready:
            return
        width, height = max(1, window.getXSize()), max(1, window.getYSize())
        aspect = width / height
        # UI sidebars keep a constant height-relative width; the 3D viewport
        # occupies the actual remaining space, with a matching camera aspect.
        left = 0 if self.focus_mode else min(.40, .78/(2*aspect))
        right = 1 if self.focus_mode else max(.60, 1-.66/(2*aspect))
        bottom, top = (0, 1) if self.focus_mode else (.08, .90)
        self.camNode.getDisplayRegion(0).setDimensions(left, right, bottom, top)
        self.camLens.setAspectRatio(width*(right-left)/(height*(top-bottom)))
        self.scene.update_camera()
        self.header.setPos(.06, 0, .88)
        self.header["text_align"] = TextNode.ACenter
        self.subheader.setPos(.06, 0, .81)
        self.subheader["text_align"] = TextNode.ACenter

    def _refresh(self):
        board = self.session.board
        self.header["text"] = board.name
        self.subheader["text"] = "ORTHOGRAPHIC 3D  /  " + str(board.rows) + " x " + str(board.cols)
        self.stage_info["text"] = f"{board.rows} rows x {board.cols} columns\nArrow keys or W A S D to move"
        self.move_label["text"] = f"{self.session.move_count:02d}"
        self.focus_moves["text"] = f"Moves: {self.session.move_count:02d}"
        self.mode_label["text"] = self.session.status.upper()
        self.mode_label["text_fg"] = ACCENT if self.session.status == "won" else MUTED
        self.status_label["text"] = self.notice
        self.status_label["text_fg"] = (1, .53, .40, 1) if self.notice_error else INK
        for button in self.solve_buttons:
            button["state"] = DGG.DISABLED if self.runner.running else DGG.NORMAL
        self.cancel_button["state"] = DGG.NORMAL if self.runner.running else DGG.DISABLED
        self.split_button["state"] = DGG.NORMAL if self.session.state.is_split else DGG.DISABLED
        available = self.playback.has_result and not self.runner.running
        for button in (self.replay_button, self.back_button, self.next_button, self.play_button):
            button["state"] = DGG.NORMAL if available else DGG.DISABLED
        self.play_button["text"] = "Pause" if self.playback.playing else "Play"
        self.export_button["state"] = DGG.NORMAL if self.last_result else DGG.DISABLED
        self.speed_label["text"] = f"{self.playback.speed:.1f} steps / s"
        if available:
            self.timeline_label["text"] = f"Step {self.playback.index} / {len(self.last_result.actions)}"
        else:
            self.timeline_label["text"] = "Solve to unlock playback"
        if self.runner.running:
            self.result_status["text"] = f"{self.algorithm} / searching"
            self.metric_labels["time"]["text"] = f"{perf_counter()-self._search_started:.1f} s"
        elif self.last_result:
            result = self.last_result
            self.result_status["text"] = f"{result.algorithm} / {result.status}"
            self.metric_labels["time"]["text"] = f"{result.metrics.search_time*1000:.1f} ms"
            self.metric_labels["expanded"]["text"] = f"{result.metrics.expanded_nodes:,}"
            memory = result.metrics.memory_usage / 1024
            self.metric_labels["memory"]["text"] = f"{memory/1024:.2f} MiB" if memory >= 1024 else f"{memory:.1f} KiB"
            length = result.metrics.solution_length
            self.metric_labels["length"]["text"] = "--" if length is None else str(length)
        else:
            self.result_status["text"] = self.runner.completion_status or "No search yet"
            for label in self.metric_labels.values():
                label["text"] = "--"

    def _tick(self, task):
        from panda3d.core import ClockObject
        dt = min(ClockObject.getGlobalClock().getDt(), .1)
        self.scene.update(dt)
        if self._drag and self.mouseWatcherNode.hasMouse():
            point = self.mouseWatcherNode.getMouse()
            self.scene.orbit((point.x-self._drag[0])*150)
            self.scene.tilt((point.y-self._drag[1])*80)
            self._drag = (point.x, point.y)
        result = self.runner.poll()
        if result is not None:
            self.last_result = result
            if result.solved:
                try:
                    self.playback.load(result)
                    self.playback.speed = float(self.speed_slider["value"])
                    self.scene.set_state(self.session.state, self.session.selected_position)
                    self.playback.play()
                    self._set_notice(f"Solved in {len(result.actions)} moves. Auto-playing; press P to pause.")
                except ValueError as exc:
                    self._set_notice("Invalid solver path: " + str(exc), True)
            else:
                self._set_notice("Search finished: " + result.status.replace("_", " ") + ".", True)
        if self.runner.error:
            self._set_notice("Search failed: " + self.runner.error, True)
            self.runner.error = None
        if self.playback.playing:
            previous, index = self.session.state, self.playback.index
            try:
                self.playback.update(dt, max_steps=0 if self.scene.busy else 1)
                if previous != self.session.state:
                    action = self.last_result.actions[index] if self.last_result else None
                    self.scene.transition(previous, self.session.state, self.session.selected_position, action)
                if self.playback.error:
                    self._set_notice(self.playback.error, True)
            except ValueError as exc:
                self.playback.pause()
                self._set_notice(str(exc), True)
        self._refresh()
        return task.cont

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.runner.close()
        self.taskMgr.remove("bloxorz-update")
        self.destroy()

    def userExit(self):
        self.close()
        raise SystemExit(0)

    def screenshot(self, path, *, settle=True):
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        if settle:
            self.scene.update(3)
        for _ in range(4):
            self.taskMgr.step()
            self.graphicsEngine.renderFrame()
        if not self.win.saveScreenshot(Filename.fromOsSpecific(str(path))):
            raise RuntimeError("Unable to save screenshot.")
        return path

