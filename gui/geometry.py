"""Small, original procedural meshes; no downloaded models or textures."""

from panda3d.core import (
    Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat,
    GeomVertexWriter, NodePath,
)


def box(name: str, color: tuple[float, ...]) -> NodePath:
    """A unit box centered at the origin with per-face normals."""
    data = GeomVertexData(name, GeomVertexFormat.getV3n3(), Geom.UHStatic)
    vertices, normals = GeomVertexWriter(data, "vertex"), GeomVertexWriter(data, "normal")
    faces = (
        ((0, 0, 1), ((-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5))),
        ((0, 0, -1), ((-.5, .5, -.5), (.5, .5, -.5), (.5, -.5, -.5), (-.5, -.5, -.5))),
        ((1, 0, 0), ((.5, -.5, -.5), (.5, .5, -.5), (.5, .5, .5), (.5, -.5, .5))),
        ((-1, 0, 0), ((-.5, .5, -.5), (-.5, -.5, -.5), (-.5, -.5, .5), (-.5, .5, .5))),
        ((0, 1, 0), ((.5, .5, -.5), (-.5, .5, -.5), (-.5, .5, .5), (.5, .5, .5))),
        ((0, -1, 0), ((-.5, -.5, -.5), (.5, -.5, -.5), (.5, -.5, .5), (-.5, -.5, .5))),
    )
    triangles = GeomTriangles(Geom.UHStatic)
    for face_index, (normal, points) in enumerate(faces):
        for point in points:
            vertices.addData3(*point)
            normals.addData3(*normal)
        offset = face_index * 4
        triangles.addVertices(offset, offset + 1, offset + 2)
        triangles.addVertices(offset, offset + 2, offset + 3)
    geom = Geom(data)
    geom.addPrimitive(triangles)
    node = GeomNode(name)
    node.addGeom(geom)
    path = NodePath(node)
    path.setColor(*color)
    return path
