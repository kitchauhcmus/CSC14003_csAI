"""Start the 3D application. Windows search workers use a guarded entry point."""
import argparse
import multiprocessing

def main():
    parser = argparse.ArgumentParser(description="Bloxorz 3D Solver")
    parser.add_argument("--level", help="Path to a stage JSON file")
    parser.add_argument("--focus", action="store_true", help="Hide side panels")
    parser.add_argument("--screenshot", metavar="PNG", help="Render an offscreen preview")
    args = parser.parse_args()
    try:
        from gui.app import BloxorzApp
    except ModuleNotFoundError as exc:
        if exc.name and (exc.name.startswith("panda3d") or exc.name.startswith("direct")):
            parser.exit(1, "Missing Panda3D. Run: python -m pip install -r requirements.txt\n")
        raise
    app = BloxorzApp(args.level, offscreen=bool(args.screenshot))
    try:
        if args.focus:
            app.toggle_focus()
        if args.screenshot:
            print(app.screenshot(args.screenshot))
        else:
            app.run()
    finally:
        app.close()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

