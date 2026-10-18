"""Run with python main.py. Search workers are safe with Windows spawn."""

import argparse
import multiprocessing


def main():
    parser = argparse.ArgumentParser(description="Bloxorz 3D Solver Lab")
    parser.add_argument("--level", help="Path to a Board JSON level")
    parser.add_argument("--screenshot", metavar="PNG", help="Render an offscreen screenshot and exit")
    args = parser.parse_args()
    try:
        from gui.app import BloxorzApp
    except ModuleNotFoundError as exc:
        if exc.name and (exc.name.startswith("panda3d") or exc.name.startswith("direct")):
            parser.exit(1, "Panda3D is required. Run: python -m pip install -r requirements.txt\n")
        raise
    app = BloxorzApp(args.level, offscreen=bool(args.screenshot))
    try:
        if args.screenshot:
            print(app.screenshot(args.screenshot))
        else:
            app.run()
    finally:
        app.close()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
