"""Small, original procedural meshes with stable UVs and outward normals."""

from math import cos, isfinite, pi, sin, sqrt

from panda3d.core import (
    Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat,
    GeomVertexWriter, NodePath,
)


def _mesh(name, color, samples, indices):
    data = GeomVertexData(name, GeomVertexFormat.getV3n3t2(), Geom.UHStatic)
    data.setNumRows(len(samples))
    vertices = GeomVertexWriter(data, "vertex")
    normals = GeomVertexWriter(data, "normal")
    texcoords = GeomVertexWriter(data, "texcoord")
    for point, normal, uv in samples:
        vertices.addData3(*point)
        normals.addData3(*normal)
        texcoords.addData2(*uv)
    triangles = GeomTriangles(Geom.UHStatic)
    for triangle in indices:
        triangles.addVertices(*triangle)
    geom = Geom(data)
    geom.addPrimitive(triangles)
    node = GeomNode(name)
    node.addGeom(geom)
    path = NodePath(node)
    path.setColor(*color)
    return path


_BOX_FACES = (
        ((0, 0, 1), ((-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5))),
        ((0, 0, -1), ((-.5, .5, -.5), (.5, .5, -.5), (.5, -.5, -.5), (-.5, -.5, -.5))),
        ((1, 0, 0), ((.5, -.5, -.5), (.5, .5, -.5), (.5, .5, .5), (.5, -.5, .5))),
        ((-1, 0, 0), ((-.5, .5, -.5), (-.5, -.5, -.5), (-.5, -.5, .5), (-.5, .5, .5))),
        ((0, 1, 0), ((.5, .5, -.5), (-.5, .5, -.5), (-.5, .5, .5), (.5, .5, .5))),
        ((0, -1, 0), ((-.5, -.5, -.5), (.5, -.5, -.5), (.5, -.5, .5), (-.5, -.5, .5))),
)


def box(name: str, color: tuple[float, ...]) -> NodePath:
    """A [-.5,.5] unit box with hard face normals and a full UV square per face."""
    samples, indices = [], []
    for normal, points in _BOX_FACES:
        offset = len(samples)
        for point, uv in zip(points, ((0, 0), (1, 0), (1, 1), (0, 1))):
            samples.append((point, normal, uv))
        indices.extend(((offset, offset+1, offset+2), (offset, offset+2, offset+3)))
    return _mesh(name, color, samples, indices)


def beveled_box(name: str, color: tuple[float, ...], bevel: float = .035) -> NodePath:
    """A unit cube with planar chamfers; outer bounds stay exactly [-.5,.5].

    Bevel is measured before NodePath scaling. Each main face retains planar
    UVs, and the twelve edges/eight corners have their own outward flat normals.
    """
    if not isfinite(bevel) or not 0 <= bevel < .5:
        raise ValueError("bevel must be finite and in [0, .5)")
    if bevel == 0:
        return box(name, color)
    inner = .5 - bevel
    samples, indices = [], []

    def face(normal, points):
        # Ensure counterclockwise winding when viewed from outside.
        a, b, c = points[:3]
        ab = tuple(b[i]-a[i] for i in range(3))
        ac = tuple(c[i]-a[i] for i in range(3))
        cross = (ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2],
                 ab[0]*ac[1]-ab[1]*ac[0])
        if sum(cross[i]*normal[i] for i in range(3)) < 0:
            points = tuple(reversed(points))
        length = sqrt(sum(value*value for value in normal))
        normal = tuple(value/length for value in normal)
        dominant = max(range(3), key=lambda axis: abs(normal[axis]))
        uv_axes = ((1, 2), (0, 2), (0, 1))[dominant]
        offset = len(samples)
        for point in points:
            uv = (point[uv_axes[0]]+.5, point[uv_axes[1]]+.5)
            samples.append((point, normal, uv))
        for index in range(1, len(points)-1):
            indices.append((offset, offset+index, offset+index+1))

    for normal, points in _BOX_FACES:
        axis = next(i for i, value in enumerate(normal) if value)
        face(normal, tuple(tuple(p[i] if i == axis else p[i]*2*inner
                                 for i in range(3)) for p in points))
    for first_axis, second_axis in ((0, 1), (0, 2), (1, 2)):
        free_axis = 3-first_axis-second_axis
        for first_sign in (-1, 1):
            for second_sign in (-1, 1):
                normal = [0, 0, 0]
                normal[first_axis], normal[second_axis] = first_sign, second_sign
                points = []
                for free_sign, swap in ((-1, False), (1, False), (1, True), (-1, True)):
                    point = [0, 0, 0]
                    point[first_axis] = first_sign*(inner if swap else .5)
                    point[second_axis] = second_sign*(.5 if swap else inner)
                    point[free_axis] = free_sign*inner
                    points.append(tuple(point))
                face(normal, tuple(points))
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                face((sx, sy, sz), ((sx*.5, sy*inner, sz*inner),
                                   (sx*inner, sy*.5, sz*inner),
                                   (sx*inner, sy*inner, sz*.5)))
    return _mesh(name, color, samples, indices)


def disc(name: str, color: tuple[float, ...], segments: int = 32) -> NodePath:
    """A Z-axis cylinder of diameter one and height one, centered at the origin.

    Segment counts round up to a multiple of four so the bounds include all
    cardinal points exactly. Side normals are smooth and cap normals are flat.
    """
    if type(segments) is not int or segments < 3:
        raise ValueError("segments must be an integer of at least three")
    segments = (segments+3)//4*4
    samples, indices = [], []
    ring = [(cos(2*pi*i/segments)*.5, sin(2*pi*i/segments)*.5)
            for i in range(segments)]
    for z, normal, reverse in ((.5, (0, 0, 1), False), (-.5, (0, 0, -1), True)):
        offset = len(samples)
        points = list(reversed(ring)) if reverse else ring
        samples.extend(((x, y, z), normal, (x+.5, y+.5)) for x, y in points)
        indices.extend((offset, offset+i, offset+i+1) for i in range(1, segments-1))
    offset = len(samples)
    for index in range(segments+1):
        x, y = ring[index % segments]
        normal = (x*2, y*2, 0)
        samples.append(((x, y, -.5), normal, (index/segments, 0)))
        samples.append(((x, y, .5), normal, (index/segments, 1)))
    for index in range(segments):
        a = offset+index*2
        indices.extend(((a, a+2, a+3), (a, a+3, a+1)))
    return _mesh(name, color, samples, indices)
