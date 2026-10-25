"""Classic 3D presentation; animation never changes the engine's State."""

from math import atan2, ceil, cos, degrees, hypot, isfinite, pi, radians, sin
from panda3d.core import (
    AmbientLight, BitMask32, CardMaker, DirectionalLight, OrthographicLens,
    PNMImage, Point3, Quat, Texture, TransparencyAttrib, Vec3,
)
from core.constants import Orientation, TileType
from core.rules import is_goal
from gui.effects import EffectTrack, Effects, falling_offset, roll_quat, smoothstep
from gui.geometry import beveled_box, disc
from gui.materials import ClassicMaterials

TILE_COLORS = {
    TileType.FLOOR: (1,1,1,1), TileType.FRAGILE: (1,.60,.27,1),
    TileType.SOFT_SWITCH: (1,1,1,1), TileType.HEAVY_SWITCH: (1,1,1,1),
    TileType.SPLIT_SWITCH: (.85,.64,.83,1), TileType.BRIDGE: (.87,.90,.88,1),
}
BLOCK_COLOR = (1,1,1,1)


class BoardScene:
    def __init__(self, base):
        self.base = base
        self.root = base.render.attachNewNode("classic-board")
        self.tiles = self.root.attachNewNode("tiles")
        self.blocks = self.root.attachNewNode("blocks")
        self.shadows = self.root.attachNewNode("soft-shadows")
        self.debris = self.root.attachNewNode("fragile-debris")
        self.materials = ClassicMaterials()
        self.effects = Effects()
        self.board = self.state = self.animation = None
        self.heading, self.elevation, self.zoom = -22., 52., 1.
        self.tile_nodes, self.bridge_nodes, self.switch_nodes = {}, {}, {}
        self.shadow_nodes = {}
        self._block_nodes = {}
        self.lens = OrthographicLens()
        self.lens.setNearFar(.1,500)
        base.camNode.setLens(self.lens)
        base.camLens = self.lens
        self._lights()
        self._background()

    def _lights(self):
        ambient = AmbientLight("ambient")
        ambient.setColor((.46,.46,.49,1))
        self.root.setLight(self.root.attachNewNode(ambient))
        self.key = DirectionalLight("sun")
        self.key.setColor((.85,.82,.75,1))
        self.key.setShadowCaster(True,1024,1024)
        self.key.setCameraMask(BitMask32.bit(2))
        self.key.getLens().setNearFar(1,100)
        self.key_node = self.root.attachNewNode(self.key)
        self.root.setLight(self.key_node)
        rim = DirectionalLight("fill")
        rim.setColor((.20,.22,.28,1))
        light = self.root.attachNewNode(rim)
        light.setHpr(140,-25,0)
        self.root.setLight(light)
        self.root.setShaderAuto()

    def _background(self):
        image = PNMImage(2,128,3)
        for y in range(128):
            t = 1-y/127
            for x in range(2):
                image.setXel(x,y,.11+.43*t,.018+.070*t,.012+.022*t)
        texture = Texture("red-gradient")
        texture.load(image)
        card = CardMaker("backdrop")
        card.setFrame(-100,100,-100,100)
        self.backdrop = self.base.camera.attachNewNode(card.generate())
        self.backdrop.setY(150)
        self.backdrop.setTexture(texture)
        self.backdrop.setLightOff()
        self.backdrop.setShaderOff()
        self.backdrop.setDepthWrite(False)
        self.backdrop.hide(BitMask32.bit(2))
        image = PNMImage(64,64,4)
        for y in range(64):
            for x in range(64):
                radius = ((x-31.5)/31.5)**2 + ((y-31.5)/31.5)**2
                image.setXelA(x,y,0,0,0,.26*max(0,1-radius)**2)
        self.shadow_texture = Texture("soft-blob")
        self.shadow_texture.load(image)

    @property
    def busy(self):
        return self.animation is not None or self.effects.busy

    def _piece(self,parent,name,position,scale,color=(1,1,1,1),*,metal=False,stone=False):
        piece = beveled_box(name,color)
        piece.reparentTo(parent)
        piece.setPos(*position)
        piece.setScale(*scale)
        if metal:
            self.materials.apply_metal(piece)
        elif stone:
            self.materials.apply_stone(piece)
        return piece

    def set_board(self,board,state,selected=None,*,intro=True):
        self.effects.clear()
        self.animation = None
        self.board = board
        self.heading, self.elevation, self.zoom = -22.,52.,1.
        self._build_tiles()
        self.set_state(state,selected)
        self.update_camera()
        target = Point3((board.cols-1)/2,-(board.rows-1)/2,0)
        self.key_node.setPos(target+Vec3(-8,-10,20))
        self.key_node.lookAt(target)
        self.key.getLens().setFilmSize(max(board.rows,board.cols)*1.6)
        if intro:
            self._intro()

    def _build_tiles(self):
        self.tiles.getChildren().detach()
        self.shadows.getChildren().detach()
        self.debris.getChildren().detach()
        self.tile_nodes, self.bridge_nodes, self.switch_nodes = {}, {}, {}
        self.shadow_nodes = {}
        for row,cells in enumerate(self.board.grid):
            for col,tile in enumerate(cells):
                if tile == TileType.VOID:
                    continue
                position = (row,col)
                group = self.tiles.attachNewNode(f"tile-{row}-{col}")
                group.setPos(col,-row,0)
                self.tile_nodes[position] = group
                shadow = CardMaker("tile-shadow")
                shadow.setFrame(-1.05,1.05,-1.05,1.05)
                node = self.shadows.attachNewNode(shadow.generate())
                self.shadow_nodes[position] = node
                node.setPos(col+.5,-row-.3,-1.9)
                node.setP(-90)
                node.setTexture(self.shadow_texture)
                node.setTransparency(TransparencyAttrib.MAlpha)
                node.setLightOff()
                node.setShaderOff()
                node.setDepthWrite(False)
                node.hide(BitMask32.bit(2))
                if tile == TileType.GOAL:
                    for dx,dy,sx,sy in ((-.515,0,.03,1.06),(.515,0,.03,1.06),
                                        (0,-.515,1,.03),(0,.515,1,.03)):
                        self._piece(group,"well-wall",(dx,dy,-1),(sx,sy,2),(.44,.43,.40,1),stone=True)
                    self._piece(group,"well-bottom",(0,0,-2.05),(1,1,.05),(.07,.055,.04,1))
                    continue
                holder = group
                if tile == TileType.BRIDGE:
                    holder = group.attachNewNode("bridge-hinge")
                    holder.setX(-.5)
                    self.bridge_nodes[position] = holder
                self._piece(holder,"stone",(.5 if tile == TileType.BRIDGE else 0,0,-.14),
                            (.98,.98,.28),TILE_COLORS[tile],stone=True)
                if tile in (TileType.SOFT_SWITCH,TileType.HEAVY_SWITCH,TileType.SPLIT_SWITCH):
                    marker = group.attachNewNode("switch-button")
                    marker.setZ(.035)
                    self.switch_nodes[position] = marker
                    if tile == TileType.SOFT_SWITCH:
                        mesh = disc("round-switch",(.55,.53,.48,1))
                        mesh.reparentTo(marker)
                        mesh.setScale(.52,.52,.065)
                    elif tile == TileType.HEAVY_SWITCH:
                        for angle in (-45,45):
                            self._piece(marker,"switch-mark",(0,0,0),(.56,.13,.065),
                                        (.55,.53,.49,1)).setH(angle)
                    else:
                        self._split_mark(marker)
                if tile == TileType.FRAGILE:
                    self._piece(group,"fragile-seam",(0,0,.006),(.8,.018,.015),
                                (.35,.18,.07,1)).setH(27)

    def _split_mark(self, parent):
        """Model the required () symbol as raised curved strips on the tile."""
        for side in (-1, 1):
            points = [(side * (.13 + .13*cos(-pi/2+i*pi/12)),
                       .29*sin(-pi/2+i*pi/12)) for i in range(13)]
            for index, ((x1,y1),(x2,y2)) in enumerate(zip(points,points[1:])):
                dx,dy = x2-x1,y2-y1
                self._piece(parent,f"split-parenthesis-{side}-{index}",
                            ((x1+x2)/2,(y1+y2)/2,.015),
                            (.060,hypot(dx,dy)+.018,.055),(.35,.17,.32,1)
                            ).setH(degrees(atan2(-dx,dy)))

    def _pressed(self,position,state):
        tile = self.board.tile_at(*position)
        return position in state.positions and (tile == TileType.SOFT_SWITCH or state.orientation == Orientation.STANDING)

    def _sync_tiles(self,state,*,animate=False):
        for position,node in self.bridge_nodes.items():
            target = 0. if position in state.active_bridges else 90.
            start = node.getR()
            if animate and abs(start-target)>.1:
                node.show()
                self.effects.add(EffectTrack(.30,lambda t,n=node,a=start,b=target:
                                            n.setR(a+(b-a)*smoothstep(t)),
                                            on_complete=(lambda n=node: n.hide()) if target else None))
            else:
                node.setR(target)
                node.hide() if target else node.show()
            shadow = self.shadow_nodes[position]
            if target:
                shadow.hide()
            else:
                shadow.show()
                shadow.hide(BitMask32.bit(2))
        for position,node in self.switch_nodes.items():
            target = -.035 if self._pressed(position,state) else .035
            start = node.getZ()
            if animate and abs(start-target)>.001:
                self.effects.add(EffectTrack(.10,lambda t,n=node,a=start,b=target:
                                            n.setZ(a+(b-a)*smoothstep(t))))
            else:
                node.setZ(target)

    def _draw_blocks(self,state,selected=None):
        self.blocks.getChildren().detach()
        self.blocks.setPos(0,0,0)
        self.blocks.setQuat(Quat.identQuat())
        self.blocks.setScale(1)
        self.blocks.show()
        self._block_nodes = {}
        if state.is_split:
            for position in state.positions:
                row,col = position
                group = self.blocks.attachNewNode("cube")
                self._block_nodes[position] = group
                self._piece(group,"split-cube",(col,-row,.5),(1,1,1),metal=True)
                if position == selected:
                    for dx,dy,sx,sy in ((-.42,0,.045,.84),(.42,0,.045,.84),
                                        (0,-.42,.84,.045),(0,.42,.84,.045)):
                        highlight = self._piece(group,"selected-cube",
                                                (col+dx,-row+dy,1.015),(sx,sy,.022),
                                                (.20,1,.82,1))
                        highlight.setLightOff()
        else:
            row = sum(p[0] for p in state.positions)/len(state.positions)
            col = sum(p[1] for p in state.positions)/len(state.positions)
            scale = {Orientation.STANDING:(1,1,2),Orientation.HORIZONTAL:(2,1,1),
                     Orientation.VERTICAL:(1,2,1)}[state.orientation]
            self._piece(self.blocks,"block",(col,-row,scale[2]/2),scale,metal=True)

    def set_state(self,state,selected=None):
        """Immediate undo/seek snapshot; discard stale visual callbacks."""
        self.effects.clear()
        self.animation = None
        self.state = state
        self.debris.getChildren().detach()
        for node in self.tile_nodes.values():
            node.setZ(0)
            node.setHpr(0,0,0)
            node.show()
        self._sync_tiles(state)
        self._draw_blocks(state,selected)

    def _intro(self):
        for (row,col),node in self.tile_nodes.items():
            delay = ((row*3+col*5)%11)*.018
            node.setZ(-5)
            self.effects.add(EffectTrack(.46,lambda t,n=node:n.setZ(-5*(1-smoothstep(t))),delay=delay))
        self.blocks.setZ(3)
        self.effects.add(EffectTrack(.26,lambda t:self.blocks.setZ(3*(1-smoothstep(t))),delay=.64))

    def restart(self,state,selected=None):
        self.effects.clear()
        self.animation = {"kind":"restart","elapsed":0,"duration":.52,"state":state,"selected":selected}
        self.blocks.hide()

    def _begin_roll(self,previous,action,on_complete):
        source = previous.positions[action.cube_index] if previous.is_split else None
        moving = self._block_nodes[source] if source is not None else self.blocks
        dx,dy = action.direction.dc,-action.direction.dr
        positions = (source,) if source is not None else previous.positions
        xs,ys = [p[1] for p in positions],[-p[0] for p in positions]
        pivot = Vec3(max(xs)+.5 if dx>0 else min(xs)-.5 if dx<0 else sum(xs)/len(xs),
                     max(ys)+.5 if dy>0 else min(ys)-.5 if dy<0 else sum(ys)/len(ys),0)
        self.animation = {"kind":"roll","elapsed":0,"duration":.22,"node":moving,
                          "pivot":pivot,"axis":Vec3(-dy,dx,0),"start_pos":Vec3(moving.getPos()),
                          "start_quat":Quat(moving.getQuat()),"complete":on_complete}

    def transition(self,previous,current,selected=None,action=None):
        if previous == current:
            self.set_state(current,selected)
            return
        if self.state != previous or self.busy:
            self.set_state(previous,previous.positions[0] if previous.is_split else None)

        def complete():
            self.state = current
            self._sync_tiles(current,animate=True)
            if previous.is_split or current.is_split:
                self._draw_blocks(current,selected)
            if current.is_split and not previous.is_split:
                self.animation = {"kind":"reveal","elapsed":0,"duration":.22}
            elif is_goal(self.board,current):
                self.animation = {"kind":"goal","elapsed":0,"duration":.60,
                                  "node":self.blocks,"start_pos":Vec3(self.blocks.getPos())}

        if action is None:
            self.set_state(current,selected)
            complete()
        else:
            self._begin_roll(previous,action,complete)

    def _break_fragile(self, target, moving):
        """Animate an engine-reported fragile failure without deciding legality.

        The engine may supply its attempted State or the affected (row, col).
        The bounds fallback only locates the already-animated mesh visually.
        """
        if hasattr(target,"positions"):
            position = target.positions[0]
        elif target is not None:
            position = tuple(target)
        else:
            low,high = moving.getTightBounds(self.root)
            center = (low+high)*.5
            position = (round(-center.y),round(center.x))
        if position not in self.tile_nodes or self.board.tile_at(*position) != TileType.FRAGILE:
            return
        self.tile_nodes[position].hide()
        self.shadow_nodes[position].hide()
        row,col = position
        for ix in range(3):
            for iy in range(3):
                dx,dy = (ix-1)*.32,(iy-1)*.32
                node = self._piece(self.debris,"orange-fragment",
                                   (col+dx,-row+dy,-.14),(.305,.305,.25),
                                   TILE_COLORS[TileType.FRAGILE],stone=True)
                origin = Vec3(node.getPos())
                drift = Vec3(dx*1.3,dy*1.3,0)
                spin = Vec3((ix-1)*120,(iy-1)*160,(ix+iy-2)*90)

                def update_fragment(t,n=node,start=origin,velocity=drift,rotation=spin):
                    seconds = t*.70
                    n.setPos(start+velocity*seconds+Vec3(0,0,-9*seconds*seconds))
                    n.setHpr(rotation*t)

                self.effects.add(EffectTrack(.70,update_fragment,on_complete=node.hide))

    def _drop_after_bridge_closes(self, previous, attempted, moving, action):
        """Render unsupported pieces using the engine's failed landing snapshot.

        A switch pressed by one split cube can remove support from the other.
        Do not assume that the cube which just moved is the one that must fall.
        """
        self._sync_tiles(attempted,animate=True)
        if attempted.is_split:
            if not previous.is_split:
                # A split switch may have teleported the cubes onto a closed
                # bridge. The engine supplies both spawn coordinates.
                self._draw_blocks(attempted)
                nodes = self._block_nodes
            else:
                stationary = {p:n for p,n in self._block_nodes.items() if n != moving}
                landing = next((p for p in attempted.positions if p not in stationary),None)
                nodes = dict(stationary)
                if landing is not None:
                    nodes[landing] = moving
            entries = []
            for position,node in nodes.items():
                tile = self.board.tile_at(*position)
                missing = tile == TileType.VOID or (
                    tile == TileType.BRIDGE and position not in attempted.active_bridges)
                if missing:
                    drift = (Vec3(action.direction.dc,-action.direction.dr,0)
                             if node == moving else Vec3(0))
                    entries.append((node,Vec3(node.getPos()),drift))
            if entries:
                self.animation = {"kind":"fall-many","elapsed":0,"duration":.58,
                                  "entries":entries}
                return True
        elif previous.is_split:
            # Adjacent cubes have merged in the attempted engine pose.
            self._draw_blocks(attempted)
            self.animation = {"kind":"fall","elapsed":0,"duration":.58,
                              "node":self.blocks,"start_pos":Vec3(self.blocks.getPos()),
                              "direction":Vec3(action.direction.dc,-action.direction.dr,0)}
            return True
        return False

    def fall(self,state,action,*,reason=None,target=None):
        """Animate the failure reported by the engine; keep the other split cube.

        reason accepts MoveResult; target optionally supplies the engine's
        attempted landing State. No game transition is computed here.
        """
        if self.state != state or self.busy:
            self.set_state(state,state.positions[action.cube_index] if state.is_split else None)
        moving = self._block_nodes[state.positions[action.cube_index]] if state.is_split else self.blocks

        def drop():
            failure = getattr(reason,"name",str(reason)).lower()
            if failure in ("fragile","fragile_broke"):
                self._break_fragile(target,moving)
            if failure == "bridge_closed" and hasattr(target,"active_bridges"):
                if self._drop_after_bridge_closes(state,target,moving,action):
                    return
            self.animation = {"kind":"fall","elapsed":0,"duration":.58,"node":moving,
                              "start_pos":Vec3(moving.getPos()),
                              "direction":Vec3(action.direction.dc,-action.direction.dr,0)}

        self._begin_roll(state,action,drop)

    def update(self,dt):
        if not isfinite(dt) or dt<0:
            raise ValueError("Frame time must be finite and nonnegative")
        # Substeps carry time through roll -> sink/fall and restart -> intro.
        count = max(1,ceil(dt*60))
        step = dt/count
        for _ in range(count):
            self.effects.update(step)
            a = self.animation
            if a is None:
                continue
            a["elapsed"] += step
            t = min(1,a["elapsed"]/a["duration"])
            if a["kind"] == "roll":
                q = roll_quat(90*smoothstep(t),a["axis"])
                a["node"].setQuat(a["start_quat"]*q)
                a["node"].setPos(a["pivot"]+q.xform(a["start_pos"]-a["pivot"]))
            elif a["kind"] in ("fall","goal"):
                a["node"].setPos(a["start_pos"]+falling_offset(t*a["duration"],a.get("direction",Vec3(0))))
            elif a["kind"] == "fall-many":
                for node,origin,direction in a["entries"]:
                    node.setPos(origin+falling_offset(t*a["duration"],direction))
            elif a["kind"] == "reveal":
                self.blocks.setZ(.22*sin(3.14159265*t))
            elif a["kind"] == "restart":
                for (row,col),node in self.tile_nodes.items():
                    local = max(0,a["elapsed"]-((row*3+col*5)%7)*.025)
                    node.setZ(-15*local*local)
            if t>=1:
                self.animation = None
                if a["kind"] == "roll":
                    a["complete"]()
                elif a["kind"] in ("fall","goal"):
                    a["node"].hide()
                elif a["kind"] == "fall-many":
                    for node,_,_ in a["entries"]:
                        node.hide()
                elif a["kind"] == "reveal":
                    self.blocks.setZ(0)
                elif a["kind"] == "restart":
                    self.set_state(a["state"],a["selected"])
                    self._intro()

    def orbit(self,amount):
        self.heading += amount
        self.update_camera()

    def tilt(self,amount):
        self.elevation = max(25,min(75,self.elevation+amount))
        self.update_camera()

    def zoom_by(self,amount):
        self.zoom = max(.55,min(1.8,self.zoom*amount))
        self.update_camera()

    def reset_camera(self):
        self.heading,self.elevation,self.zoom = -22.,52.,1.
        self.update_camera()

    def update_camera(self):
        if self.board is None:
            return
        positions = [(r,c) for r,row in enumerate(self.board.grid) for c,t in enumerate(row) if t!=TileType.VOID]
        minr,maxr = min(p[0] for p in positions),max(p[0] for p in positions)
        minc,maxc = min(p[1] for p in positions),max(p[1] for p in positions)
        target = Point3((minc+maxc)/2,-(minr+maxr)/2,.35)
        h,e = radians(self.heading),radians(self.elevation)
        self.base.camera.setPos(target+Vec3(sin(h)*cos(e),-cos(h)*cos(e),sin(e))*max(self.board.rows,self.board.cols)*3)
        self.base.camera.lookAt(target)
        corners = [self.base.camera.getRelativePoint(self.base.render,Point3(c,-r,z))
                   for c in (minc-.6,maxc+.6) for r in (minr-.6,maxr+.6) for z in (0,2)]
        width,height = max(p.x for p in corners)-min(p.x for p in corners),max(p.z for p in corners)-min(p.z for p in corners)
        aspect = self.lens.getAspectRatio()
        film_height = max(height+1.3,(width+1.3)/aspect)*self.zoom
        self.lens.setFilmSize(film_height*aspect,film_height)
        self.backdrop.setScale(film_height*aspect/200,1,film_height/200)
