"""True 3D board, camera and rigid rolling animation, independent of widgets."""

from math import cos, radians, sin

from panda3d.core import AmbientLight, DirectionalLight, Point3, Quat, Vec3

from core.constants import Orientation, TileType
from gui.geometry import box

TILE_COLORS = {
    TileType.FLOOR: (.26, .37, .47, 1),
    TileType.FRAGILE: (.91, .48, .20, 1),
    TileType.SOFT_SWITCH: (.19, .65, .68, 1),
    TileType.HEAVY_SWITCH: (.60, .40, .85, 1),
    TileType.SPLIT_SWITCH: (.83, .40, .64, 1),
    TileType.BRIDGE: (.20, .57, .49, 1),
}
BLOCK_COLOR = (.98, .72, .25, 1)


class BoardScene:
    def __init__(self, base):
        self.base = base
        self.root = base.render.attachNewNode("board-scene")
        self.tiles = self.root.attachNewNode("tiles")
        self.blocks = self.root.attachNewNode("blocks")
        self.board = None
        self.state = None
        self.animation = None
        self.heading, self.elevation, self.zoom = -45.0, 48.0, 1.0
        self._lights()

    def _lights(self):
        ambient = AmbientLight("ambient")
        ambient.setColor((.48, .55, .66, 1))
        self.root.setLight(self.root.attachNewNode(ambient))
        key = DirectionalLight("key")
        key.setColor((.95, .93, .84, 1))
        light = self.root.attachNewNode(key)
        light.setHpr(-35, -55, 0)
        self.root.setLight(light)
        rim = DirectionalLight("rim")
        rim.setColor((.28, .44, .59, 1))
        light = self.root.attachNewNode(rim)
        light.setHpr(150, -25, 0)
        self.root.setLight(light)

    @property
    def busy(self):
        return self.animation is not None

    def set_board(self, board, state, selected=None):
        self.board = board
        self.heading, self.elevation, self.zoom = -45.0, 48.0, 1.0
        self.set_state(state, selected)
        self.update_camera()

    def _piece(self, parent, name, position, scale, color):
        piece = box(name, color)
        piece.reparentTo(parent)
        piece.setPos(*position)
        piece.setScale(*scale)
        return piece

    def _draw_tiles(self, state):
        self.tiles.getChildren().detach()
        board = self.board
        for row, cells in enumerate(board.grid):
            for col, tile in enumerate(cells):
                if tile == TileType.VOID:
                    continue
                x, y = col, -row
                if tile == TileType.GOAL:
                    # A real opening, with four luminous edge strips and a dark well.
                    for dx, dy, sx, sy in ((-.46, 0, .08, 1), (.46, 0, .08, 1),
                                          (0, -.46, .84, .08), (0, .46, .84, .08)):
                        self._piece(self.tiles, "goal-rim", (x+dx, y+dy, -.1),
                                    (sx, sy, .24), (.22, .91, .76, 1))
                    self._piece(self.tiles, "goal-well", (x, y, -.6), (.88, .88, .12), (.035, .065, .085, 1))
                    continue
                if tile == TileType.BRIDGE and (row, col) not in state.active_bridges:
                    self._piece(self.tiles, "closed-bridge", (x, y, -.45), (.78, .78, .08), (.08, .19, .22, 1))
                    continue
                self._piece(self.tiles, "tile", (x, y, -.15), (.94, .94, .3), TILE_COLORS[tile])
                if tile in (TileType.SOFT_SWITCH, TileType.HEAVY_SWITCH, TileType.SPLIT_SWITCH):
                    marker = self._piece(self.tiles, "switch", (x, y, .025),
                                         (.39, .39, .06), (.88, .96, 1, 1))
                    marker.setH(45 if tile == TileType.HEAVY_SWITCH else 0)
                    if tile == TileType.SPLIT_SWITCH:
                        marker.setSx(.14)
                        self._piece(self.tiles, "split-marker", (x+.23, y, .025),
                                    (.14, .39, .06), (.88, .96, 1, 1))
                if tile == TileType.FRAGILE:
                    self._piece(self.tiles, "fragile-stripe", (x, y, .012),
                                (.8, .055, .025), (.43, .20, .10, 1)).setH(30)
        # A small start marker remains visible after the block moves away.
        row, col = board.start_pos
        self._piece(self.tiles, "start", (col, -row, .012), (.21, .21, .024), (.38, .76, .91, 1))

    def _draw_blocks(self, state, selected=None):
        self.blocks.getChildren().detach()
        self._block_nodes = {}
        if state.is_split:
            for position in state.positions:
                row, col = position
                group = self.blocks.attachNewNode("cube")
                self._block_nodes[position] = group
                color = BLOCK_COLOR if position == selected else (.88, .58, .20, 1)
                self._piece(group, "split-cube", (col, -row, .48), (.91, .91, .96), color)
                if position == selected:
                    self._piece(group, "selection", (col, -row, 1.01), (.48, .48, .055), (.94, 1, 1, 1))
        else:
            row = sum(p[0] for p in state.positions) / len(state.positions)
            col = sum(p[1] for p in state.positions) / len(state.positions)
            scale = {
                Orientation.STANDING: (.91, .91, 1.94),
                Orientation.HORIZONTAL: (1.94, .91, .94),
                Orientation.VERTICAL: (.91, 1.94, .94),
            }[state.orientation]
            self._piece(self.blocks, "block", (col, -row, scale[2]/2), scale, BLOCK_COLOR)

    def set_state(self, state, selected=None):
        self.animation = None
        self.blocks.show()
        self.blocks.setPos(0, 0, 0)
        self.blocks.setQuat(Quat.identQuat())
        self.state = state
        self._draw_tiles(state)
        self._draw_blocks(state, selected)

    def transition(self, previous, current, selected=None, action=None):
        if previous == current:
            self.set_state(current, selected)
            return
        # Teleports and split/merge use a short reveal; regular moves rotate a
        # rigid box by exactly 90 degrees around the contact edge.
        if action is None or (current.is_split and not previous.is_split):
            self.set_state(current, selected)
            self.animation = {"kind": "reveal", "elapsed": 0, "duration": .18,
                              "state": current, "selected": selected}
            return
        source = previous.positions[action.cube_index] if previous.is_split else None
        self.set_state(previous, source)
        moving = self._block_nodes[source] if previous.is_split else self.blocks
        dx, dy = action.direction.dc, -action.direction.dr
        positions = (source,) if previous.is_split else previous.positions
        xs = [p[1] for p in positions]
        ys = [-p[0] for p in positions]
        center = Vec3(sum(xs)/len(xs), sum(ys)/len(ys), 0)
        pivot = Vec3(max(xs)+.5 if dx > 0 else min(xs)-.5 if dx < 0 else center.x,
                     max(ys)+.5 if dy > 0 else min(ys)-.5 if dy < 0 else center.y, 0)
        self.animation = {"kind": "roll", "elapsed": 0, "duration": .23,
                          "state": current, "selected": selected,
                          "pivot": pivot, "axis": Vec3(-dy, dx, 0), "node": moving}

    def fall(self, state, action):
        """Visualize a rejected manual move; the session keeps its undo state."""
        self.set_state(state)
        self.animation = {"kind": "fall", "elapsed": 0, "duration": .65,
                          "state": state, "selected": None,
                          "direction": Vec3(action.direction.dc, -action.direction.dr, 0)}

    def update(self, dt):
        if self.animation is None:
            return
        animation = self.animation
        animation["elapsed"] += dt
        t = min(1, animation["elapsed"] / animation["duration"])
        eased = t*t*(3-2*t)
        if animation["kind"] == "roll":
            rotation = Quat()
            rotation.setFromAxisAngle(90*eased, animation["axis"])
            pivot = animation["pivot"]
            animation["node"].setQuat(rotation)
            animation["node"].setPos(pivot - rotation.xform(pivot))
        elif animation["kind"] == "fall":
            self.blocks.setPos(animation["direction"]*eased + Vec3(0, 0, -6*eased*eased))
            self.blocks.setHpr(0, 60*eased, 30*eased)
        else:
            self.blocks.setZ(.22*sin(3.14159*t))
        if t == 1:
            if animation["kind"] == "fall":
                self.blocks.hide()
                self.animation = None
            else:
                self.set_state(animation["state"], animation["selected"])

    def orbit(self, amount):
        self.heading += amount
        self.update_camera()

    def tilt(self, amount):
        self.elevation = max(25, min(75, self.elevation + amount))
        self.update_camera()

    def zoom_by(self, amount):
        self.zoom = max(.55, min(1.8, self.zoom * amount))
        self.update_camera()

    def reset_camera(self):
        self.heading, self.elevation, self.zoom = -45.0, 48.0, 1.0
        self.update_camera()

    def update_camera(self):
        if self.board is None:
            return
        target = Point3((self.board.cols-1)/2, -(self.board.rows-1)/2, .15)
        heading, elevation = radians(self.heading), radians(self.elevation)
        # Both dimensions matter when a tall board is viewed from a diagonal.
        distance = max(self.board.rows, self.board.cols, 5) * 1.75 * self.zoom
        offset = Vec3(sin(heading)*cos(elevation), -cos(heading)*cos(elevation), sin(elevation))*distance
        self.base.camera.setPos(target + offset)
        self.base.camera.lookAt(target)
