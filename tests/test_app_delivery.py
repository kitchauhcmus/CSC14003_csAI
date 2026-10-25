"""Opt-in end-to-end test with a real Panda3D graphics context."""
import os
import time
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("BLOXORZ_GRAPHICS_TESTS") != "1",
    reason="Set BLOXORZ_GRAPHICS_TESTS=1 to open an offscreen GPU context",
)

def test_actual_app_input_solver_autoplay_and_split(tmp_path, monkeypatch):
    from core.constants import Direction
    import gui.app as app_module
    from gui.app import BloxorzApp
    app = BloxorzApp(offscreen=True)
    try:
        app.scene.update(3)
        initial = app.session.state
        # Typed letters must not also move the game.
        app.timeout_entry["focus"] = True
        app.messenger.send("d")
        assert app.session.state == initial
        app.timeout_entry["focus"] = False
        app.messenger.send("d")
        assert app.session.move_count == 1
        app.scene.update(1)
        app.undo()
        assert app.session.state == initial
        app.solve("A*")
        deadline = time.monotonic() + 15
        while app.runner.running and time.monotonic() < deadline:
            app.taskMgr.step()
            time.sleep(.01)
        assert not app.runner.running, "Worker did not finish"
        assert app.last_result is not None and app.last_result.solved, app.notice
        assert app.playback.playing  # Solutions auto-play as required.
        app.playback.pause()
        while app.playback.index < len(app.last_result.actions):
            app.scene.update(2)
            app.step_forward()
        app.scene.update(2)
        assert app.session.status == "won"
        assert not app.scene.busy
        app.step_back()
        assert app.session.status == "playing"
        app.toggle_focus()
        assert app.focus_mode
        app.toggle_focus()
        assert not app.focus_mode
        monkeypatch.setattr(app_module, "ROOT", tmp_path)
        app.export_result()
        assert (tmp_path / "exports" / "last_result.json").is_file()
        # Split through the actual stage selector, then Space changes selection.
        name = next(n for n in app.level_names if n.startswith("05_split"))
        app._choose_level(name)
        app.scene.update(3)
        app.move(Direction.RIGHT)
        app.scene.update(1)
        app.move(Direction.RIGHT)
        app.scene.update(2)
        assert app.session.state.is_split
        selected = app.session.selected_position
        app.messenger.send("space")
        assert app.session.selected_position != selected
        screenshot = app.screenshot(tmp_path / "split.png")
        assert screenshot.stat().st_size > 1000
    finally:
        app.close()
        assert not app.runner.running

