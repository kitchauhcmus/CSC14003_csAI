"""Opt-in real graphics smoke test: BLOXORZ_TEST_GRAPHICS=1 python -m pytest."""

import os
import time

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("BLOXORZ_TEST_GRAPHICS") != "1",
                                reason="Set BLOXORZ_TEST_GRAPHICS=1 to open an offscreen graphics context")


def test_real_3d_application_end_to_end(tmp_path):
    from core.constants import Direction
    from gui.app import BloxorzApp
    from integration import make_search_problem
    from solvers import bfs

    app = BloxorzApp(offscreen=True)
    try:
        app.screenshot(tmp_path / "initial.png")
        assert (tmp_path / "initial.png").stat().st_size > 10000
        initial = app.session.state
        # Native focus changes do not update DirectEntry's configuration option.
        app.timeout_entry.guiItem.setFocus(True)
        assert app._typing()
        app.messenger.send("arrow_up")
        app.messenger.send("r")
        assert app.session.state == initial and app.session.move_count == 0
        app.timeout_entry.guiItem.setFocus(False)
        app.messenger.send("f")
        assert app.focus_mode and all(panel.isHidden() for panel in app.side_panels)
        app.messenger.send("f")
        assert not app.focus_mode and all(not panel.isHidden() for panel in app.side_panels)
        path = bfs(make_search_problem(app.session.board))
        app.move(path.actions[0].direction)
        assert app.scene.busy and app.session.state == path.states[1]
        app.scene.update(1)
        assert not app.scene.busy
        app.undo()
        assert app.session.state == initial

        # A button can start a search even while an entry has focus.
        app.limit_entry.guiItem.setFocus(True)
        app.solve()
        assert app.runner.running
        frames = 0
        deadline = time.monotonic() + 10
        while app.last_result is None and time.monotonic() < deadline:
            app.taskMgr.step()
            frames += 1
            time.sleep(.005)
        assert frames > 0 and app.last_result and app.last_result.solved
        assert app.playback.has_result
        app.screenshot(tmp_path / "solved-path.png")
        while app.playback.index < len(app.last_result.actions):
            app.step_forward()
            app.scene.update(1)
        assert app.session.status == "won"
        app.step_back()
        assert app.session.status == "playing"
        app.restart_playback()
        assert app.session.state == initial

        # Error notifications are consumed once; Reset clears the visible error.
        app.runner.error = "simulated worker failure"
        app.taskMgr.step()
        assert "simulated worker failure" in app.notice
        app.reset()
        app.taskMgr.step()
        assert app.notice == "Stage reset."
        assert app.scene.busy  # Tile collapse/assembly blocks moves until complete.
        app.scene.update(2)
        assert not app.scene.busy

        # A falling move animates, and Undo restores the visible block.
        for direction in Direction:
            from core.rules import apply_action
            from core.constants import Action
            if apply_action(app.session.board, initial, Action.from_input(direction)) is None:
                app.move(direction)
                assert app.session.status == "lost"
                app.scene.update(1)
                assert app.scene.blocks.isHidden()
                app.undo()
                assert app.session.status == "playing" and not app.scene.blocks.isHidden()
                break

        # The selected split cube rolls independently; the stationary cube stays.
        split_name = next(name for name, path in zip(app.level_names, app.level_paths)
                          if path.stem.startswith("05_"))
        app._choose_level(split_name)
        app.scene.update(2)
        result = bfs(make_search_problem(app.session.board))
        app.last_result = result
        app.playback.load(result)
        for _ in range(2):
            app.step_forward()
            app.scene.update(1)
        assert app.session.state.is_split
        app.step_forward()
        assert app.scene.animation["kind"] == "roll"
        moving = app.scene.animation["node"]
        stationary = next(node for node in app.scene._block_nodes.values() if node != moving)
        app.scene.update(.1)
        assert stationary.getPos().length() == 0
        app.scene.update(1)
        app.step_forward()
        app.scene.update(1)
        assert app.session.status == "won"
        assert app.scene.blocks.isHidden()  # Goal sink finishes after the last roll.
        app.screenshot(tmp_path / "split-complete.png")
    finally:
        app.close()
    assert not app.runner.running
