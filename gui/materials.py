"""Original, tileable classic stone and weathered metal textures.

PNMImage generation is deterministic and runs once per process. Textures use
ordinary UV sampling and fixed-function materials, without shader dependencies.
No external images or extra packages are required.
"""

from math import floor

from panda3d.core import Material, PNMImage, Texture


def _hash(x, y, seed):
    value = ((x*374761393 + y*668265263 + seed*1442695041) & 0xffffffff)
    value = ((value ^ (value >> 13))*1274126177) & 0xffffffff
    return ((value ^ (value >> 16)) & 0xffffffff)/0xffffffff


def _noise(u, v, frequency, seed):
    x, y = u*frequency, v*frequency
    ix, iy = floor(x), floor(y)
    fx, fy = x-ix, y-iy
    fx, fy = fx*fx*(3-2*fx), fy*fy*(3-2*fy)
    a = _hash(ix % frequency, iy % frequency, seed)
    b = _hash((ix+1) % frequency, iy % frequency, seed)
    c = _hash(ix % frequency, (iy+1) % frequency, seed)
    d = _hash((ix+1) % frequency, (iy+1) % frequency, seed)
    return (a+(b-a)*fx)*(1-fy) + (c+(d-c)*fx)*fy


def _smoothstep(low, high, value):
    t = max(0, min(1, (value-low)/(high-low)))
    return t*t*(3-2*t)


def _texture(name, kind, size=128):
    image = PNMImage(size, size, 3)
    for y in range(size):
        for x in range(size):
            u, v = x/size, y/size
            broad = _noise(u, v, 4, 17 if kind == "stone" else 47)
            middle = _noise(u, v, 12, 29 if kind == "stone" else 71)
            fine = _noise(u, v, 32, 83)
            grain = _hash(x, y, 127)-.5
            if kind == "stone":
                # Low-contrast limestone clouds, tiny pores and faint mineral veins.
                vein = max(0, 1-abs(middle-.51)*75)
                value = .77+(broad-.5)*.10+(middle-.5)*.07+(fine-.5)*.035
                value += grain*.022-vein*.025
                if _hash(x, y, 191) > .997:
                    value -= .055
                rgb = (value*.995, value, value*1.012)
            else:
                # Broad oxidized islands over desaturated blue-black steel.
                rust = _smoothstep(.43, .66, broad*.62+middle*.38)
                steel, oxide = (.255, .285, .32), (.49, .275, .18)
                light = .92+fine*.16+grain*.07
                rgb = tuple((steel[i]*(1-rust)+oxide[i]*rust)*light for i in range(3))
            image.setXel(x, y, *(max(0, min(1, channel)) for channel in rgb))
    texture = Texture(name)
    texture.load(image)
    texture.setWrapU(Texture.WMRepeat)
    texture.setWrapV(Texture.WMRepeat)
    texture.setMinfilter(Texture.FTLinearMipmapLinear)
    texture.setMagfilter(Texture.FTLinear)
    texture.setAnisotropicDegree(2)
    return texture


class ClassicMaterials:
    """Reusable textures and apply helpers; node colors continue to tint them."""

    _cache = None

    def __init__(self):
        if ClassicMaterials._cache is None:
            stone = _texture("classic-limestone", "stone")
            metal = _texture("classic-oxidized-steel", "metal")
            stone_material = Material("limestone")
            stone_material.setAmbient((.75, .75, .75, 1))
            stone_material.setDiffuse((1, 1, 1, 1))
            stone_material.setSpecular((.035, .035, .035, 1))
            stone_material.setShininess(5)
            metal_material = Material("oxidized-steel")
            metal_material.setAmbient((.65, .65, .65, 1))
            metal_material.setDiffuse((1, 1, 1, 1))
            metal_material.setSpecular((.24, .23, .21, 1))
            metal_material.setShininess(18)
            ClassicMaterials._cache = (stone, metal, stone_material, metal_material)
        self.stone, self.metal, self._stone_material, self._metal_material = ClassicMaterials._cache

    def apply_stone(self, node):
        node.setTexture(self.stone, 1)
        node.setMaterial(self._stone_material, 1)
        return node

    def apply_metal(self, node):
        node.setTexture(self.metal, 1)
        node.setMaterial(self._metal_material, 1)
        return node
