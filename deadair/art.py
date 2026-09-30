"""
DEAD AIR — procedural scene art.

Every frame is raymarched from a signed-distance description of the place you
are standing in, then lit by your actual lamp. Nothing here is a picture file:
the beam is a light in the scene, so when the battery dies the image loses reach
and detail for the same reason the prose does.

Pure rendering. It knows about rooms only through SCENES, which is data.
"""

from __future__ import annotations

import itertools
import math
import threading
import time
from dataclasses import dataclass, replace
from functools import lru_cache

import numpy as np
from PIL import Image

F32 = np.float32

# --------------------------------------------------------------------------
#  value noise — one small 3D lattice, sampled with wrap
# --------------------------------------------------------------------------

_N = 64
_MASK = _N - 1
_NTEX = np.random.default_rng(19110000).random((_N, _N, _N)).astype(F32)


def _noise(x, y, z):
    xi, yi, zi = np.floor(x), np.floor(y), np.floor(z)
    xf, yf, zf = (x - xi), (y - yi), (z - zi)
    xf = xf * xf * (3.0 - 2.0 * xf)
    yf = yf * yf * (3.0 - 2.0 * yf)
    zf = zf * zf * (3.0 - 2.0 * zf)

    x0 = xi.astype(np.int32) & _MASK
    y0 = yi.astype(np.int32) & _MASK
    z0 = zi.astype(np.int32) & _MASK
    x1, y1, z1 = (x0 + 1) & _MASK, (y0 + 1) & _MASK, (z0 + 1) & _MASK

    t = _NTEX
    c00 = t[x0, y0, z0] + (t[x1, y0, z0] - t[x0, y0, z0]) * xf
    c10 = t[x0, y1, z0] + (t[x1, y1, z0] - t[x0, y1, z0]) * xf
    c01 = t[x0, y0, z1] + (t[x1, y0, z1] - t[x0, y0, z1]) * xf
    c11 = t[x0, y1, z1] + (t[x1, y1, z1] - t[x0, y1, z1]) * xf
    c0 = c00 + (c10 - c00) * yf
    c1 = c01 + (c11 - c01) * yf
    return c0 + (c1 - c0) * zf


def _fbm(x, y, z, octaves=2, gain=0.5, lac=2.03):
    total = np.zeros_like(x)
    amp, freq, norm = 1.0, 1.0, 0.0
    for _ in range(octaves):
        total += amp * _noise(x * freq, y * freq, z * freq)
        norm += amp
        amp *= gain
        freq *= lac
    return total / norm


# --------------------------------------------------------------------------
#  scene description
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Scene:
    """A place, as geometry. `air()` is positive in open space, negative in rock."""
    kind: str = "tube"          # tube | chamber | hole | forest | crawl | drop | void
    rx: float = 1.5             # tube half-width
    ry: float = 1.2             # tube half-height
    bend: float = 0.5           # how far the passage wanders off the axis
    rough: float = 0.5          # displacement amplitude on the rock
    freq: float = 0.5           # rock texture frequency
    bed: float = 0.0            # horizontal bedding-plane relief
    floor: float = -1.25        # flat floor height, or None for a raw tube
    ceil: float = 5.0           # chamber ceiling
    wall: float = 6.0           # chamber half-width
    far: float = 26.0           # chamber far wall
    water: float = None         # water plane height, or None
    hole_r: float = 2.6         # shaft radius for kind="hole" (the pitch head)
    hole_z: float = 5.2         # how far ahead the hole sits
    depth_below: float = 12.0   # how deep the hole goes before rock
    trees: int = 0              # trunks in view — a stand, or around a hole
    canopy: float = 0.0         # height of the lowest branches, 0 = bare
    understory: float = 0.0     # how thick the brush is, 1.0 = walls the path
    path: float = 0.0           # half-width of a cleared path, 0 = none
    rise: float = 0.0           # ground slope away from you — the ridge going up
    deadwood: bool = False      # bare standing trunks — no crowns, no brush
    broadleaf: float = 0.0      # share of the canopy that is oak, not hemlock
    camp: bool = False          # Wolf Sink: the hole in the stand, and the camp
    crowd: bool = False         # the people standing round the camp's table
    at: tuple = (0.0, 0.0)      # where you stand in the scene: x, z metres
    face: float = 0.0           # which way you face, degrees right of ahead
    roll: float = 0.0           # how far off level you are, radians
    ground: str = ""            # the floor: cobble | plate | rubble | guano | silt | dust | bone
    ways: tuple = ()            # openings in a room's walls: (bearing, width, height)
    pockets: int = 0            # hollows worn into a dome's roof
    bell: float = 0.0           # how far a dome's walls draw in toward its top
    chimney: float = 0.0        # a shaft up out of the roof, this wide
    slope: float = 0.0          # how steeply the floor climbs ahead
    props: tuple = ()           # what is in the room: clusters of primitives
    marks: tuple = ()           # what has been put on the rock
    glow: tuple = ()            # lights of its own: (x, y, z, power, material)
    murk: float = 0.0           # bad air pooled this deep over the floor
    absorb: tuple = ()          # where light goes in and does not come out
    pit: tuple = ()             # a hole in the floor: (x, z, radius)
    clear: float = 0.0          # how far the beam carries down into water
    flow: float = 0.0           # how hard the water is running: ripples on it
    scallop: float = 0.0        # how deep the flow has scooped the walls
    ledges: float = 0.0         # how far the beds stand out of a wall, in ledges
    neck: float = 0.0           # where a rift pinches to a slot, 0 = never
    scar: float = 0.0           # how far a jumble's roof steps up where it fell
    clearing: tuple = ()        # in a forest: (x, z, radius) the woods keep off
    exposure: float = 0.0       # eyes opened up to the dark, 0 = as it is
    fill: float = 0.0           # how far the floor's fill banks up the walls
    gloom: float = 0.0          # how fast the light dies going into a way
    lights: float = 0.0         # how hard the camp's work lights burn
    lens: float = 0.0           # cap the lens at this half-angle tan, 0 = fill
    fog: float = 16.0           # scatter distance
    reach: float = 9.0          # lamp falloff distance at full power
    palette: str = "cave"       # cave | dusk | night
    tilt: float = 0.0           # camera pitch, radians, negative looks down
    sky: float = 0.0            # sky radiance (surface scenes)
    day: float = 0.0            # 0-1, how much of the day is left
    var: float = 0.0            # decorrelates the rock between rooms


def _smin(a, b, k):
    """Polynomial smooth minimum — rounds the corner where two surfaces meet."""
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def _plates(x, z, size, seed, lean=0.9):
    """Shattered plate seen from above. For each point: the height its slab
    sits at (0..1, with the slab's own tilt already in it — `lean` is how
    far over they go) and how close it is to a crack between two slabs (0
    on the crack). Jittered cells, the nearest two of the nine around."""
    gx, gz = np.floor(x / size), np.floor(z / size)
    best = np.full(x.shape, 1e9, dtype=F32)
    second = np.full(x.shape, 1e9, dtype=F32)
    height = np.zeros(x.shape, dtype=F32)
    for ox in (-1.0, 0.0, 1.0):
        for oz in (-1.0, 0.0, 1.0):
            cx, cz = gx + ox, gz + oz
            ix = cx.astype(np.int32) & _MASK
            iz = cz.astype(np.int32) & _MASK

            def rand(k):
                return _NTEX[ix, iz, (seed + k) & _MASK]
            fx, fz = (cx + rand(0)) * size, (cz + rand(7)) * size
            d = np.sqrt((x - fx) ** 2 + (z - fz) ** 2)
            closer = d < best
            second = np.where(closer, best, np.minimum(second, d))
            # each slab came down at its own angle
            tilt = ((x - fx) * (rand(19) - 0.5) + (z - fz) * (rand(23) - 0.5))
            height = np.where(closer, rand(13) + tilt * lean / size, height)
            best = np.minimum(best, d)
    return height, (second - best) * 0.5


def _cobbles(x, z, size, seed):
    """Stream cobble seen from above: rounded stones of every size, a few
    of them long, lying loose in the sand the water left between them —
    not a pavement. Jittered cells, a stone to most of them, the tallest
    of the nine around. Returns the height and what each point is."""
    gx, gz = np.floor(x / size), np.floor(z / size)
    top = np.zeros(x.shape, dtype=F32)
    for ox in (-1.0, 0.0, 1.0):
        for oz in (-1.0, 0.0, 1.0):
            cx, cz = gx + ox, gz + oz
            ix = cx.astype(np.int32) & _MASK
            iz = cz.astype(np.int32) & _MASK

            def rand(k):
                return _NTEX[ix, iz, (seed + k) & _MASK]
            fx, fz = (cx + rand(0)) * size, (cz + rand(7)) * size
            # a few big ones among a lot of small, some cells only sand
            r = size * (0.12 + 0.48 * rand(13) ** 1.3) * (rand(19) > 0.18)
            # stretched along its own axis, the way the water laid it
            a = rand(23) * math.pi
            ca, sa = np.cos(a), np.sin(a)
            u = ((x - fx) * ca + (z - fz) * sa) / (1.0 + 0.5 * rand(29))
            w = (z - fz) * ca - (x - fx) * sa
            e = 1.0 - (u * u + w * w) / np.maximum(r * r, 1e-6)
            # water-worn flat, and bedded half into the sand
            top = np.maximum(top, 0.32 * r * np.clip(e, 0.0, 1.0) ** 0.6)
    return top, np.where(top > 0.004, _M_COBBLE, _M_SILT)


def _chips(x, z, size, seed):
    """Scree seen from above: loose angular chips of every size, each
    lying at its own tilt, some over the edge of the next, and the fines
    showing where there are none — not a tiling. Jittered cells, a chip to
    most of them, the highest of the nine around."""
    gx, gz = np.floor(x / size), np.floor(z / size)
    top = np.zeros(x.shape, dtype=F32)
    for ox in (-1.0, 0.0, 1.0):
        for oz in (-1.0, 0.0, 1.0):
            cx, cz = gx + ox, gz + oz
            ix = cx.astype(np.int32) & _MASK
            iz = cz.astype(np.int32) & _MASK

            def rand(k):
                return _NTEX[ix, iz, (seed + k) & _MASK]
            fx, fz = (cx + rand(0)) * size, (cz + rand(7)) * size
            r = size * (0.2 + 0.75 * rand(13) ** 1.6) * (rand(19) > 0.22)
            a = rand(23) * math.pi
            ca, sa = np.cos(a), np.sin(a)
            u = (x - fx) * ca + (z - fz) * sa
            w = ((z - fz) * ca - (x - fx) * sa) * (1.0 + 0.8 * rand(29))
            # a broken outline: straight sides and cut corners
            edge = r - np.maximum(np.maximum(np.abs(u), np.abs(w)),
                                  (np.abs(u) + np.abs(w)) * 0.72)
            face = (0.3 * r + (rand(31) - 0.5) * 0.9 * u
                    + (rand(37) - 0.5) * 0.9 * w)
            top = np.maximum(top, np.minimum(face, edge * 2.5))
    return top


def _seg(px, py, pz, a, b, r):
    """Distance to a capsule of radius `r` from point `a` to point `b`."""
    bx, by, bz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    qx, qy, qz = px - a[0], py - a[1], pz - a[2]
    h = np.clip((qx * bx + qy * by + qz * bz)
                / max(bx * bx + by * by + bz * bz, 1e-12), 0.0, 1.0)
    qx, qy, qz = qx - bx * h, qy - by * h, qz - bz * h
    return np.sqrt(qx * qx + qy * qy + qz * qz) - r


def _rbox(px, py, pz, c, half, r, yaw=0.0):
    """Distance to a box centred on `c` with half-extents `half`, its edges
    rounded by `r`, turned `yaw` degrees about the vertical."""
    ca, sa = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    dx, dz = px - c[0], pz - c[2]
    qx = np.abs(dx * ca + dz * sa) - half[0] + r
    qy = np.abs(py - c[1]) - half[1] + r
    qz = np.abs(dz * ca - dx * sa) - half[2] + r
    return (np.sqrt(np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2
                    + np.maximum(qz, 0.0) ** 2)
            + np.minimum(np.maximum(qx, np.maximum(qy, qz)), 0.0) - r)


# --------------------------------------------------------------------------
#  the stand — every tree in a forest scene, planted once
# --------------------------------------------------------------------------
#
# A forest is a few hundred trunks, and a signed distance has to be the
# distance to the *nearest* of them, so the naive version measures every
# tree at every step of every ray — which is why the woods used to stop at
# twenty trees. Instead the ground is cut into cells, and each cell lists
# only the things that reach within a margin of it. A point looks up its
# cell and measures a handful; anything unlisted is at least the distance to
# the cell wall plus that margin away, so that is as far as a step may go.

_TREE_DEPTH = 56.0    # how far back the stand is planted
_CELL = 2.0           # lookup cell on the ground, metres a side
_STRIDE = 1.7         # the longest step a forest ray takes
_GX0, _GZ0 = -112.0, -6.0
_NX, _NZ = 113, 51    # the grid: x -112..114, z -6..96


def _rise(s, z):
    """The ground goes up ahead of you — the ridge climbing."""
    return s.rise * np.maximum(z - 4.0, 0.0)


def _path_x(s, z):
    """Where the path runs: wandering, then bending off out of sight.

    A path that ran straight to the horizon would be an avenue cut through
    the stand. This one turns away after a dozen metres, the way a
    switchback does, and the trees close in behind the turn.
    """
    v = s.var
    turn = 1.0 if int(v) % 2 else -1.0
    return (1.1 * np.sin(z * 0.13 + v) + 0.5 * np.sin(z * 0.37 + v * 1.7)
            + turn * 0.012 * np.maximum(z - 10.0, 0.0) ** 2)


# --------------------------------------------------------------------------
#  Wolf Sink — the one place above ground that is built as well as grown
# --------------------------------------------------------------------------
#
# Laid out in the clearing's own coordinates: you come in on the flagging at
# the origin, facing the hole a dozen yards off. Basecamp and the sink are
# both drawn from this one layout — the sink just stands you at the lip — so
# the lights behind you at two in the morning are the ones you walked past
# at dusk, on the same stands.

_SINK = (0.4, 11.5, 3.3, 14.0)      # the hole: centre x, z, mouth radius, depth
_CLEARING = (-0.5, 4.8, 8.8, 5.0)   # cut for the camp: centre x, z, half-widths
_VEHICLES = ((-7.4, 7.4, 24.0, "truck"), (7.8, 9.6, -34.0, "suv"))
_GENERATOR = (5.4, 3.6, 14.0)       # x, z, yaw in degrees
_TABLE = (-2.7, 5.4, 12.0)
# "A generator running a string of work lights": bulbs on a cable sagging
# across the camp, and floods on stands. The low one by the generator is
# the one behind you when you stand at the lip: set a lamp not much higher
# than a man and his shadow runs out long across the ground, over the lip,
# and down the far wall, until the wall is too deep for the lamp to reach.
_STRING = ((-6.2, 2.7, 5.4), (3.6, 2.9, 6.6), 0.45, 6)   # ends, sag, bulbs
_STANDS = ((-4.6, 7.0, 3.2, 1.0), (5.6, 3.0, 2.2, 1.8),
           (2.6, -1.5, 3.2, 0.8))                # x, z, height, power
# where each stands and the way they face, in degrees off straight ahead
_PEOPLE = ((-3.8, 5.0, 60.0, "stand"), (-3.0, 6.3, 150.0, "stand"),
           (-1.6, 5.8, -120.0, "stand"), (-2.3, 4.5, 10.0, "sit"),
           (-4.6, 6.2, 110.0, "stand"),
           # the two in oversuits, off by themselves, waiting to be told
           (3.0, 7.5, -20.0, "suit"), (3.6, 7.9, -35.0, "suit"))
# each vehicle as boxes in its own frame: centre x, y, z; half x, y, z; round
_BODIES = {
    "truck": ((0.0, 0.80, 0.0, 0.95, 0.40, 2.65, 0.12),     # body and bed
              (0.0, 1.46, 0.75, 0.90, 0.36, 0.95, 0.16)),    # cab
    "suv": ((0.0, 0.92, 0.0, 0.96, 0.46, 2.35, 0.18),
            (0.0, 1.60, -0.25, 0.88, 0.30, 1.75, 0.20)),
}

# what a surface is made of, for shading — and the tone each one takes
(_M_GROUND, _M_BARK, _M_LEAF, _M_BRUSH, _M_ROCK, _M_PAINT, _M_TYRE,
 _M_CLOTH, _M_SUIT, _M_METAL, _M_PAPER, _M_LAMP,
 _M_SILT, _M_PACK, _M_BUG, _M_FLAG,
 _M_COBBLE, _M_GUANO, _M_BONE, _M_DUST, _M_IRON, _M_TIMBER, _M_ROPE,
 _M_TAG, _M_GLINT, _M_RED, _M_BLUE, _M_DAWN, _M_PALE, _M_WATER,
 _M_DRESSED, _M_MORTAR, _M_FIELD) = range(33)
_TONE = np.array([0.85, 0.75, 0.50, 0.55, 1.05, 0.80, 0.30,
                  0.45, 1.15, 0.65, 1.60, 1.00,
                  1.00, 0.45, 1.25, 1.30,
                  0.95, 0.16, 1.55, 1.30, 0.42, 0.70, 1.60,
                  2.00, 1.00, 1.00, 1.00, 1.00, 1.90, 0.40,
                  1.35, 1.25, 1.45], dtype=F32)
# The palettes are luminance ramps; a very few things keep their own colour
# through them — the ones the story names by it. Wren's flagging, "Wren's
# color"; her red pack; the blue dive line; the gray at the top of the
# workings, which is not lamplight.
_TINT = {_M_FLAG: (255, 92, 36), _M_RED: (190, 34, 28), _M_BLUE: (48, 96, 232),
         _M_DAWN: (168, 180, 198)}


def _slump(s, x, z):
    """How far the ground has sagged toward the sink's mouth, in metres.

    `x`, `z` are arrays. Also returns the mouth radius in each direction —
    the lip is ragged, not a circle.
    """
    sx, sz, sr, _ = _SINK
    qx, qz = x - sx, z - sz
    r = np.sqrt(qx * qx + qz * qz)
    ang = np.arctan2(qx, qz)
    mouth = sr * (1.0 + 0.16 * np.sin(ang * 3.0 + s.var)
                  + 0.08 * np.sin(ang * 7.0 - s.var))
    u = np.clip((mouth + 1.3 - r) / 1.3, 0.0, 1.0)
    return 0.6 * u * u * (3.0 - 2.0 * u), r, ang, mouth


class _Camp:
    """The search camp at the sink: its gear and people as primitives, the
    work lights, and what stands between those lights and everything else.

    Every shadow caster is a standing cylinder — people, the vehicles in
    three slices, trunks — so a shadow is a flat test, not a second march.
    """

    def __init__(self, s):
        def ground(x, z):
            return s.floor + float(_rise(s, np.float32(z)))

        boxes, caps, occ = [], [], []
        for vx, vz, yaw, kind in _VEHICLES:
            c, sn = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
            g = ground(vx, vz)

            def place(lx, lz):
                return vx + lx * c - lz * sn, vz + lx * sn + lz * c
            for lx, ly, lz, bx, by, bz, rd in _BODIES[kind]:
                wx, wz = place(lx, lz)
                boxes.append((wx, g + ly, wz, yaw, bx, by, bz, rd, _M_PAINT))
            for wx, wz in (place(a * 0.95, b * 1.6)
                           for a in (-1, 1) for b in (-1, 1)):
                boxes.append((wx, g + 0.36, wz, yaw, 0.14, 0.36, 0.36, 0.13,
                              _M_TYRE))
            for lz in (-1.7, 0.0, 1.7):
                wx, wz = place(0.0, lz)
                occ.append((wx, wz, 0.95, g + 0.3, g + 1.8))

        x, z, yaw = _GENERATOR
        g = ground(x, z)
        boxes.append((x, g + 0.32, z, yaw, 0.42, 0.32, 0.30, 0.05, _M_METAL))
        occ.append((x, z, 0.4, g, g + 0.64))

        # the folding table, and the map on it held down at the corners
        x, z, yaw = _TABLE
        g = ground(x, z)
        c, sn = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        boxes.append((x, g + 0.74, z, yaw, 0.92, 0.022, 0.38, 0.015, _M_PAPER))
        for a in (-0.78, 0.78):
            boxes.append((x + a * c, g + 0.37, z + a * sn, yaw,
                          0.025, 0.36, 0.33, 0.01, _M_METAL))
        occ.append((x, z, 0.6, g + 0.70, g + 0.78))

        # floods on stands, their heads turned in on the camp; then the
        # string. A lamp is (x, y, z, power, casts shadows).
        self.lamps = []
        for x, z, tall, power in _STANDS:
            g = ground(x, z)
            caps.append((x, z, g, g + tall - 0.1, 0.035, _M_METAL))
            aim = math.degrees(math.atan2(_TABLE[0] - x, _TABLE[1] - z))
            boxes.append((x, g + tall, z, -aim, 0.22, 0.15, 0.09, 0.03,
                          _M_LAMP))
            self.lamps.append((x, g + tall, z, power, True))
        (ax, ay, az), (bx, by, bz), sag, n = _STRING
        for k in range(n):
            u = (k + 0.5) / n
            x, z = ax + (bx - ax) * u, az + (bz - az) * u
            y = (ground(x, z) + ay + (by - ay) * u
                 - sag * 4.0 * u * (1.0 - u))
            caps.append((x, z, y, y, 0.08, _M_LAMP))
            self.lamps.append((x, y, z, 0.3, False))

        # "Limestone and root": the hemlocks' roots hang off the far rim and
        # down the wall where the ground went out from under them
        rrng = np.random.default_rng(int(s.var * 100) + 3)
        sx, sz, _, _ = _SINK
        lip = ground(sx, sz)
        for a in rrng.uniform(-1.7, 0.7, 24):
            _, _, _, mouth = _slump(s, np.array([sx + math.sin(a)]),
                                    np.array([sz + math.cos(a)]))
            rad = float(mouth[0]) * rrng.uniform(0.74, 0.8)
            top = lip - rrng.uniform(0.2, 0.7)
            caps.append((sx + rad * math.sin(a), sz + rad * math.cos(a),
                         top - rrng.uniform(0.4, 2.4) ** 1.3, top,
                         rrng.uniform(0.018, 0.04), _M_BARK))

        if s.crowd:
            # legs, a torso square across the shoulders, a head: at this size
            # that is all a person is, and a pill reads as a post
            for x, z, face, pose in _PEOPLE:
                g = ground(x, z)
                m = _M_SUIT if pose == "suit" else _M_CLOTH
                big = 1.12 if pose == "suit" else 1.0
                fx = math.sin(math.radians(face))
                fz = math.cos(math.radians(face))
                if pose == "sit":
                    torso, head = g + 0.86, g + 1.32
                    boxes.append((x + fx * 0.3, g + 0.48, z + fz * 0.3, -face,
                                  0.17, 0.08, 0.26, 0.07, m))        # thighs
                    caps.append((x + fx * 0.55, z + fz * 0.55, g + 0.08,
                                 g + 0.46, 0.08, m))                 # shins
                else:
                    torso, head = g + 1.18, g + 1.63
                    caps.append((x, z, g + 0.12, g + 0.80, 0.13 * big, m))
                boxes.append((x, torso, z, -face, 0.21 * big, 0.29,
                              0.12 * big, 0.1, m))
                caps.append((x, z, head, head, 0.11 * big + (0.03 if big > 1
                                                               else 0.0), m))
                occ.append((x, z, 0.22 * big, g, head + 0.12))

        # binned into the ground cells like the trees, so a point only
        # measures the gear standing near it
        b = np.array(boxes, dtype=F32).T
        yaw = np.radians(b[3])
        gb = np.array([ground(x, z) for x, z in zip(b[0], b[2])])
        self.boxes = _Kind(b[0], b[2], np.hypot(b[4], b[6]),
                           lo=np.min(b[1] - b[5] - gb), hi=np.max(b[1] + b[5] - gb),
                           margin=0.6, cy=b[1], c=np.cos(yaw), sn=np.sin(yaw),
                           bx=b[4], by=b[5], bz=b[6], rd=b[7], mat=b[8])
        p = np.array(caps, dtype=F32).T
        gp = np.array([ground(x, z) for x, z in zip(p[0], p[1])])
        self.caps = _Kind(p[0], p[1], p[4],
                          lo=np.min(p[2] - p[4] - gp), hi=np.max(p[3] + p[4] - gp),
                          margin=0.6, y0=p[2], y1=p[3], r=p[4], mat=p[5])
        self.occ = [tuple(o) for o in occ]

    def distance(self, band, cell, px, py, pz, g, codes=False):
        """Distance from each point to the nearest piece of the camp, what
        that piece is (with `codes`), and which points were measured at all
        — `band(kind, g)` picks them, as it does for the trees."""
        def box(lx, ly, lz, j, f):
            cx, cz, cy, c, sn, bx, by, bz, rd, _ = f
            dx = lx[j, None] - cx
            dz = lz[j, None] - cz
            qx = np.abs(dx * c + dz * sn) - bx + rd
            qy = np.abs(ly[j, None] - cy) - by + rd
            qz = np.abs(dz * c - dx * sn) - bz + rd
            return (np.sqrt(np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2
                            + np.maximum(qz, 0.0) ** 2)
                    + np.minimum(np.maximum(qx, np.maximum(qy, qz)), 0.0) - rd)

        def cap(lx, ly, lz, j, f):
            x, z, y0, y1, r, _ = f
            ex = lx[j, None] - x
            ey = ly[j, None] - np.clip(ly[j, None], y0, y1)
            ez = lz[j, None] - z
            return np.sqrt(ex * ex + ey * ey + ez * ez) - r

        d = np.full(px.shape, 1.0e3, dtype=F32)
        what = np.zeros(px.shape, dtype=np.int32)
        seen = []
        for k, fn, m in ((self.boxes, box, 9), (self.caps, cap, 5)):
            i = band(k, g)
            if not i.size:
                continue
            seen.append((k, i))
            lx, ly, lz = px[i], py[i], pz[i]
            got = k.nearest(cell[i], lambda j, f: fn(lx, ly, lz, j, f),
                            pick=m if codes else None)
            dk, mk = got if codes else (got, None)
            closer = dk < d[i]
            d[i] = np.where(closer, dk, d[i])
            if codes:
                what[i] = np.where(closer, mk.astype(np.int32), what[i])
        return d, what, seen


def _into_sink(s, px, py, pz, wx, wy, wz):
    """How much of a lamp at (p + w) a point down in the sink can see.

    A lamp standing outside a hole lights into it only through the mouth:
    where the line to it crosses the lip's level inside the throat, the lamp
    is seen; anywhere else the hillside is in the way. So the far wall
    catches the light for a metre or two below the rim and then nothing
    does, which is what makes it a hole and not a dip.
    """
    lip = s.floor + float(_rise(s, np.float32(_SINK[1])))
    below = lip - py
    _, r, _, mouth = _slump(s, px, pz)
    out = np.ones(px.shape, dtype=F32)
    k = np.flatnonzero((below > 0.2) & (r < mouth * 1.05) & (wy > 1e-3))
    if k.size:
        u = np.minimum(below[k] / wy[k], 1.0)
        cx = px[k] + wx[k] * u
        cz = pz[k] + wz[k] * u
        _, r, _, mouth = _slump(s, cx, cz)
        out[k] = np.clip((mouth * 0.8 - r) / 0.4 + 0.5, 0.0, 1.0)
    return out


def _shadow(occ, px, py, pz, wx, wy, wz):
    """1 where a lamp at (p + w) sees point p, falling to 0 behind anything
    that stands in the way. `occ` is (x, z, radius, bottom, top) arrays of
    standing cylinders; the test is where the lamp's ray passes closest to
    each one's axis, and how high it is there."""
    ox, oz, orad, oy0, oy1 = occ
    l2 = wx * wx + wz * wz + 1e-6
    u = np.clip(((ox - px[:, None]) * wx[:, None]
                 + (oz - pz[:, None]) * wz[:, None]) / l2[:, None], 0.0, 1.0)
    cx = px[:, None] + u * wx[:, None] - ox
    cz = pz[:, None] + u * wz[:, None] - oz
    y = py[:, None] + u * wy[:, None]
    # something only shades what is past it, not its own lit face
    along = u * np.sqrt(l2)[:, None]
    block = (np.clip((orad - np.sqrt(cx * cx + cz * cz)) / 0.12 + 0.5, 0.0, 1.0)
             * ((y > oy0) & (y < oy1) & (along > orad + 0.1)))
    return 1.0 - block.max(axis=1)


def _bin(x, z, reach, margin):
    """For each lookup cell, the objects whose footprint comes within
    `margin` of it, padded out with the sentinel index len(x)."""
    lo_i = np.floor((x - reach - margin - _GX0) / _CELL).astype(int)
    hi_i = np.floor((x + reach + margin - _GX0) / _CELL).astype(int)
    lo_j = np.floor((z - reach - margin - _GZ0) / _CELL).astype(int)
    hi_j = np.floor((z + reach + margin - _GZ0) / _CELL).astype(int)
    cells = [[] for _ in range(_NX * _NZ)]
    for k in range(len(x)):
        for j in range(max(lo_j[k], 0), min(hi_j[k], _NZ - 1) + 1):
            for i in range(max(lo_i[k], 0), min(hi_i[k], _NX - 1) + 1):
                cells[j * _NX + i].append(k)
    table = np.full((_NX * _NZ, max(1, max(map(len, cells)))), len(x),
                    dtype=np.int32)
    for c, ids in enumerate(cells):
        table[c, :len(ids)] = ids
    return table


class _Kind:
    """One kind of thing in the stand — trunks, crowns, saplings, brush —
    with the cells that find it and the band of height it lives in, so a
    point well above or below the band can skip it.

    `margin` trades the two costs: a wide one lists more things per cell,
    a narrow one holds the step short near every cell wall.

    Each cell's list is stored already unpacked — every field of every
    thing on it, side by side — so a point fetches its whole neighbourhood
    in one contiguous copy instead of one scattered gather per field. The
    real entries come first and the sentinel pads the rest, so a cell
    listing three things can be read as just three columns.
    """

    def __init__(self, x, z, reach, lo, hi, margin, **params):
        self.n = len(x)
        self.lo, self.hi = float(lo), float(hi)
        self.reach = float(np.max(reach)) if self.n else 0.0
        self.margin = margin
        if not self.n:
            return
        table = _bin(x, z, reach, margin)
        # the sentinel is a copy of the first one, parked far off the map
        cols = [np.append(x, 1.0e4), np.append(z, 1.0e4)]
        cols += [np.append(v, v[0]) for v in params.values()]
        # (cell, field, slot)
        self.blk = np.ascontiguousarray(
            np.stack(cols).astype(F32)[:, table].transpose(1, 0, 2))
        self.count = (table < self.n).sum(axis=1)
        full = table.shape[1]
        self.tiers = sorted({min(t, full) for t in (1, 2, 3, 5, 8, 12, full)})

    def nearest(self, cell, fn, pick=None):
        """Distance from each point to the nearest thing of this kind; 1e3
        where its cell lists nothing.

        `fn(j, fields)` measures points `j` against the fields of what their
        cells list — x, z, then the params in the order given, each one
        column per listed thing. Points go through grouped by how full their
        cell is, so a sparse cell never pays for the fullest one. With
        `pick`, also returns that field of whichever thing was nearest.
        """
        out = np.full(cell.shape, 1.0e3, dtype=F32)
        got = np.zeros(cell.shape, dtype=F32) if pick is not None else None
        cnt = self.count[cell]
        lo = 0
        for hi in self.tiers:
            j = np.flatnonzero((cnt > lo) & (cnt <= hi))
            if j.size:
                b = self.blk[cell[j], :, :hi]
                f = [b[:, n] for n in range(b.shape[1])]
                d = fn(j, f)
                if pick is None:
                    out[j] = d.min(axis=1)
                else:
                    a = d.argmin(axis=1)
                    rows = np.arange(j.size)
                    out[j] = d[rows, a]
                    got[j] = f[pick][rows, a]
            lo = hi
        return out if pick is None else (out, got)


class _Stand:
    """The trees and brush of one forest scene."""

    def __init__(self, s: Scene):
        rng = np.random.default_rng(int(s.var * 1000) + 7)
        D = _TREE_DEPTH

        # Plant on a jittered lattice turned off the view axis: spaced the
        # way a stand thins itself out, without the avenues a square grid
        # shows straight down its rows. `trees` is how many stems end up in
        # the wedge you can see; a fifth of the lattice is left empty.
        keep = 0.8
        area = 1.6 * (D * D - 1.0) + 8.0 * (D - 1.0)
        a = math.sqrt(area * keep / max(1, s.trees))
        span = int(math.hypot(1.6 * D + 4.0, D) / a) + 2
        gi, gj = np.meshgrid(np.arange(-span, span + 1),
                             np.arange(-span, span + 1))
        lx = (gi.ravel() + rng.uniform(-0.42, 0.42, gi.size)) * a
        lz = (gj.ravel() + rng.uniform(-0.42, 0.42, gi.size)) * a
        th = 0.41 + s.var * 0.37
        tx = lx * math.cos(th) - lz * math.sin(th)
        tz = lx * math.sin(th) + lz * math.cos(th)
        ok = ((tz > 1.0) & (tz < D) & (np.abs(tx) < 1.6 * tz + 4.0)
              & (rng.random(gi.size) < keep))
        tx, tz = tx[ok], tz[ok]

        # most stems middling, a few old ones, and a shade-suppressed
        # understory of saplings that never got their light
        tr = 0.08 + 0.22 * rng.random(tx.size) ** 1.7
        old = rng.random(tx.size) < 0.07
        tr[old] += rng.uniform(0.10, 0.18, old.sum())

        # Two thick ones planted close on either side of the path, so you
        # are looking *into* the stand and not at the edge of a clearing.
        if s.path:
            hz = rng.uniform(3.4, 5.6, 2)
            hx = _path_x(s, hz) + np.array([-1.0, 1.0]) * (
                s.path + rng.uniform(1.0, 2.4, 2))
            room = np.min(np.hypot(tx[:, None] - hx, tz[:, None] - hz), axis=1)
            tx, tz, tr = tx[room > 2.2], tz[room > 2.2], tr[room > 2.2]
            tx = np.append(tx, hx)
            tz = np.append(tz, hz)
            tr = np.append(tr, rng.uniform(0.28, 0.38, 2))

        if s.camp:
            # "the ground opens up under a stand of hemlock": a ring of them
            # closing round the far side of the hole, open on the camp side
            sx, sz, sr, _ = _SINK
            ang = rng.uniform(-2.2, 2.2, 9)
            rad = sr + rng.uniform(0.7, 3.2, 9)
            rx, rz = sx + rad * np.sin(ang), sz + rad * np.cos(ang)
            room = np.min(np.hypot(tx[:, None] - rx, tz[:, None] - rz), axis=1)
            tx, tz, tr = tx[room > 1.8], tz[room > 1.8], tr[room > 1.8]
            tx = np.append(tx, rx)
            tz = np.append(tz, rz)
            tr = np.append(tr, rng.uniform(0.2, 0.36, 9))

        # nothing on the path, and nothing standing in the camera's lap —
        # nor where people once cleared the ground and kept it clear
        clear = ~((tz < 2.2) & (np.abs(tx) < 1.4))
        for kx, kz, kr in s.clearing:
            clear &= np.hypot(tx - kx, tz - kz) > kr + tr
        if s.path:
            clear &= np.abs(tx - _path_x(s, tz)) > s.path + tr + 0.5
        if s.camp:
            # cut back for the camp, and nothing growing out of the hole
            cx, cz, ax, az = _CLEARING
            clear &= ((tx - cx) / ax) ** 2 + ((tz - cz) / az) ** 2 > 1.0
            clear &= np.hypot(tx - _SINK[0], tz - _SINK[1]) > _SINK[2] + tr + 0.5
        tx, tz, tr = tx[clear], tz[clear], tr[clear]
        n = tx.size
        base = s.floor + _rise(s, tz)

        lean = rng.uniform(-0.035, 0.035, n)
        young = tr < 0.11
        self.leafy = bool(s.canopy) and not s.deadwood
        if not self.leafy:
            # Standing dead hemlock, not a colonnade: the tops snap off at
            # every height, a third of them lean, and some are stumps.
            tr = tr * rng.uniform(0.75, 1.35, n)
            top = rng.uniform(2.5, 16.0, n)
            stump = rng.random(n) < 0.12
            top[stump] = rng.uniform(0.4, 1.8, stump.sum())
            tilted = rng.random(n) < 0.33
            lean[tilted] = rng.uniform(-0.15, 0.15, tilted.sum())
        else:
            # Hemlock and pine: a tall narrow cone per tree, widest at the
            # skirt, the skirt drooping at the tips. Oak, where there is
            # any, is a squat wide crown on the same frame. Saplings carry
            # their branches almost to the ground — they fill the band
            # between the brush and the canopy that otherwise shows sky
            # under every tree.
            cr = 1.0 + tr * 5.5 + rng.uniform(0.0, 0.7, n)
            skirt = s.canopy * rng.uniform(0.6, 1.35, n)
            ch = cr * rng.uniform(2.3, 3.4, n)
            droop = cr * rng.uniform(0.25, 0.55, n)
            oak = ~young & (rng.random(n) < s.broadleaf)
            k = oak.sum()
            cr[oak] = 1.8 + tr[oak] * 7.0 + rng.uniform(0.0, 1.0, k)
            ch[oak] = cr[oak] * rng.uniform(0.9, 1.3, k)
            droop[oak] = cr[oak] * rng.uniform(0.35, 0.6, k)
            skirt[oak] = s.canopy * rng.uniform(0.7, 1.2, k)
            k = young.sum()
            cr[young] = rng.uniform(0.6, 1.3, k)
            skirt[young] = rng.uniform(0.15, 1.1, k)
            ch[young] = cr[young] * rng.uniform(1.8, 2.7, k)
            droop[young] = cr[young] * rng.uniform(0.25, 0.55, k)
            top = skirt + ch * 0.8

            # A crown sits where its trunk has leaned to by that height.
            cx = tx + lean * np.minimum(skirt + ch * 0.3, 9.0)
            for name, pick in (("crowns", ~young), ("saplings", young)):
                setattr(self, name, _Kind(
                    cx[pick], tz[pick], cr[pick],
                    lo=np.min(skirt[pick], initial=99.0),
                    hi=np.max((skirt + ch)[pick], initial=0.0), margin=1.0,
                    sk=(base + skirt)[pick],
                    # the crown's two faces as planes in (radius, height),
                    # normalised: upper = r*A + y*B - C, lower = D - r*E - y*F
                    A=(ch / np.hypot(ch, cr))[pick],
                    B=(cr / np.hypot(ch, cr))[pick],
                    C=(cr * ch / np.hypot(ch, cr))[pick],
                    D=(droop * cr / np.hypot(cr, droop))[pick],
                    E=(droop / np.hypot(cr, droop))[pick],
                    F=(cr / np.hypot(cr, droop))[pick]))

        self.trunks = _Kind(tx, tz, tr * 1.6 + np.abs(lean) * 9.0,
                            lo=0.0, hi=np.max(top, initial=0.0), margin=1.0,
                            base=base, lean=lean, r=tr, top=top)

        # Brush: rhododendron and laurel walling the path in, and more of it
        # scattered back through the stand. None in the dead timber.
        # `understory` is how thick it is: 1.0 walls the path in for the
        # first thirty metres and puts a bush under every fourth tree.
        nh = 0 if s.deadwood or not s.path else int(28 * s.understory)
        ns = 0 if s.deadwood else int(n * s.understory / 4.0)
        hz = 4.0 + rng.random(nh) ** 1.2 * 26.0
        side = np.where(rng.random(nh) < 0.5, -1.0, 1.0)
        br_h = rng.uniform(0.9, 1.6, nh)
        hx = _path_x(s, hz) + side * (s.path + br_h * 0.55
                                      + rng.uniform(0.0, 0.9, nh))
        sz = np.sqrt(rng.uniform(4.0 ** 2, D * D, ns))
        sx = rng.uniform(-1.0, 1.0, ns) * (1.6 * sz + 3.0)
        bx, bz = np.append(hx, sx), np.append(hz, sz)
        br = np.append(br_h, rng.uniform(0.5, 1.5, ns))
        # below eye height, or the nearest bush is the whole picture
        bh = rng.uniform(0.5, 1.3, nh + ns) * (0.7 + 0.3 * s.understory)
        clear = np.ones(bx.size, dtype=bool)
        for kx, kz, kr in s.clearing:
            clear &= np.hypot(bx - kx, bz - kz) > kr + br * 0.5
        if s.path:
            clear &= np.abs(bx - _path_x(s, bz)) > s.path + br * 0.35
        if s.camp:
            cx, cz, ax, az = _CLEARING
            clear &= ((bx - cx) / ax) ** 2 + ((bz - cz) / az) ** 2 > 1.0
            clear &= np.hypot(bx - _SINK[0], bz - _SINK[1]) > _SINK[2] + br
        bx, bz, br, bh = bx[clear], bz[clear], br[clear], bh[clear]
        sag = np.zeros(bx.size)
        if s.camp:
            # ferns at the lip, where the cold air coming up stirs them
            ang = rng.uniform(-2.3, 2.3, 30)
            _, _, _, mouth = _slump(s, _SINK[0] + np.sin(ang),
                                    _SINK[1] + np.cos(ang))
            rad = mouth + rng.uniform(0.05, 1.0, 30)
            fx = _SINK[0] + rad * np.sin(ang)
            fz = _SINK[1] + rad * np.cos(ang)
            bx, bz = np.append(bx, fx), np.append(bz, fz)
            br = np.append(br, rng.uniform(0.2, 0.4, 30))
            bh = np.append(bh, rng.uniform(0.15, 0.35, 30))
            sag = _slump(s, bx, bz)[0]
        bry = bh / 1.35                         # a third of it sunk in the dirt
        self.brush = _Kind(bx, bz, br, lo=-1.2 if s.camp else 0.0,
                           hi=np.max(bh, initial=0.0), margin=0.6,
                           cy=s.floor + _rise(s, bz) - sag + bry * 0.35,
                           inv=1.0 / br, yinv=1.0 / bry,
                           scale=np.minimum(br, bry))

        self.camp = _Camp(s) if s.camp else None
        if self.camp:
            # the trunks near enough a lamp to throw a shadow worth drawing
            lamps = np.array([l[:3] for l in self.camp.lamps], dtype=F32)
            near = np.min(np.hypot(tx[:, None] - lamps[:, 0],
                                   tz[:, None] - lamps[:, 2]), axis=1) < 18.0
            trunks = [(x, z, r * 1.1, b - 1.2, b + t) for x, z, r, b, t in
                      zip(tx[near], tz[near], tr[near], base[near], top[near])]
            self.camp.occ = self.camp.occ + trunks


@lru_cache(maxsize=8)
def _stand_for(s: Scene) -> _Stand:
    return _Stand(s)


def _stand(s: Scene) -> _Stand:
    # the sky changes by the minute and the trees do not
    return _stand_for(replace(s, sky=0.0, day=0.0))


def _cones(k, cell, px, py, pz):
    """Distance to the nearest crown of kind `k`: a cone widest at its
    skirt, with the underside rising toward the trunk — the droop of the
    branch tips."""
    def crown(j, f):
        x, z, sk, A, B, C, D, E, F = f
        hx = px[j, None] - x
        hz = pz[j, None] - z
        rr = np.sqrt(hx * hx + hz * hz)
        yc = py[j, None] - sk
        return np.maximum(rr * A + yc * B - C, D - rr * E - yc * F)
    return k.nearest(cell, crown)


# --------------------------------------------------------------------------
#  the cave, room by room
# --------------------------------------------------------------------------
#
# The chambers used to be one rounded box apiece with different numbers,
# and the passages one tube, so half the cave came out as the same picture.
# A cave never repeats itself. Each room is now one of a few shapes — a
# dome, a hall, a rift, a mine drift, a jumble of fallen blocks — furnished
# with what its own prose puts in it: things as primitives, paint on the
# rock, its own kind of floor, its own light where the story gives it one.

_ROOMS = ("dome", "hall", "rift", "mine", "jumble", "under")


def _rot(yaw, pitch=0.0, roll=0.0):
    """World-from-local rotation, in degrees: roll about the thing's own
    length, then pitch it up, then turn it."""
    y, p, r = (math.radians(a) for a in (yaw, pitch, roll))
    ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0],
                   [-math.sin(y), 0, math.cos(y)]])
    rx = np.array([[1, 0, 0], [0, math.cos(p), -math.sin(p)],
                   [0, math.sin(p), math.cos(p)]])
    rz = np.array([[math.cos(r), -math.sin(r), 0],
                   [math.sin(r), math.cos(r), 0], [0, 0, 1]])
    return ry @ rx @ rz


def _box(mat, c, half, r=0.02, yaw=0.0, pitch=0.0, roll=0.0):
    """A rounded box — a stone, a rung plate, a timber — as scene data."""
    return ("box", mat, tuple(c), tuple(half), r, yaw, pitch, roll)


def _cap(mat, a, b, r):
    """A capsule from `a` to `b` — a rope, a rail, a bone — as scene data."""
    return ("cap", mat, tuple(a), tuple(b), r)


def _corners(normals, offsets):
    """The corners of the solid a set of planes cuts out: every point where
    three of them meet that is inside all the others."""
    n, d = np.asarray(normals, float), np.asarray(offsets, float)
    i, j, k = _triples(len(d))
    # three planes meet where Cramer's rule puts them; every pair's cross
    # product worked out once, by hand (np.cross costs more to call than
    # to run on arrays this small)
    a, b = n[:, None, :], n[None, :, :]
    cr = np.stack((a[..., 1] * b[..., 2] - a[..., 2] * b[..., 1],
                   a[..., 2] * b[..., 0] - a[..., 0] * b[..., 2],
                   a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]), axis=-1)
    jk, ki, ij = cr[j, k], cr[k, i], cr[i, j]
    det = (n[i] * jk).sum(axis=1)
    ok = np.abs(det) > 1e-6
    p = ((d[i, None] * jk + d[j, None] * ki + d[k, None] * ij)[ok]
         / det[ok, None])
    return p[np.all(p @ n.T - d < 1e-6, axis=1)]


@lru_cache(maxsize=32)
def _triples(n):
    """Every way to pick three of n planes, as three index arrays."""
    return tuple(np.array(list(itertools.combinations(range(n), 3))).T)


class _Rock:
    """One piece of fallen limestone, in its own frame and then set down.

    Limestone breaks along its beds and its joints, so a block is not a box:
    a top and a bottom that were bedding planes, near parallel; five to
    eight sides that were joints, none of them square to the next or quite
    upright; and corners knocked off where it landed. Any convex solid cut
    by planes has an exact distance inside it and a safe one outside.
    """

    def __init__(self, half, seed, yaw=0.0, pitch=0.0, roll=0.0, chips=3,
                 lean=0.0):
        """`lean` pitches the whole rock up, in degrees, after it has been
        turned — the angle of the slope it came to rest on."""
        rng = np.random.default_rng(seed)
        a, b, c = half
        normals, offsets = [], []

        def cut(nrm, off):
            nrm = np.asarray(nrm, float)
            normals.append(nrm / np.linalg.norm(nrm))
            offsets.append(off)

        # the beds are seldom quite parallel: most slabs are a wedge
        cut((rng.normal(0, 0.12), 1.0, rng.normal(0, 0.12)), b * rng.uniform(0.85, 1.0))
        cut((rng.normal(0, 0.12), -1.0, rng.normal(0, 0.12)), b * rng.uniform(0.85, 1.0))
        k = int(rng.integers(5, 9))
        start = rng.uniform(0.0, 2.0 * math.pi)
        for i in range(k):
            th = start + (i + rng.uniform(-0.3, 0.3)) * 2.0 * math.pi / k
            reach = math.hypot(a * math.cos(th), c * math.sin(th))
            cut((math.cos(th), rng.uniform(-0.5, 0.5), math.sin(th)),
                reach * rng.uniform(0.8, 1.0))
        for _ in range(chips):
            u = rng.normal(0.0, 1.0, 3)
            u /= np.linalg.norm(u)
            top = float(np.max(_corners(normals, offsets) @ u))
            cut(u, top - min(a, b, c) * rng.uniform(0.3, 0.9))

        self.rot = _rot(yaw, pitch, roll)
        if lean:
            self.rot = _rot(0.0, lean) @ self.rot
        self.normals = np.array(normals) @ self.rot.T       # turned into the world
        self.offsets = np.array(offsets)
        self.local = _corners(normals, offsets) @ self.rot.T
        self.reach = float(np.max(np.hypot(self.local[:, 0], self.local[:, 2])))
        self.size = min(a, b, c)
        self.at = np.zeros(3)

    def put(self, x, y, z):
        self.at = np.array([x, y, z], float)
        return self

    def corners(self):
        return self.local + self.at

    def top(self, x, z):
        """How high this rock stands over each of the points (x, z) —
        arrays — or -inf where it is not over them."""
        n, off = self.normals, self.offsets
        rest = (off[:, None] - n[:, 0, None] * (x - self.at[0])
                - n[:, 2, None] * (z - self.at[2]))
        up, down = n[:, 1] > 1e-3, n[:, 1] < -1e-3
        hi = np.min(rest[up] / n[up, 1, None], axis=0, initial=np.inf)
        lo = np.max(rest[down] / n[down, 1, None], axis=0, initial=-np.inf)
        over = (hi >= lo) & np.all(rest[~(up | down)] >= 0.0, axis=0)
        return np.where(over, hi + self.at[1], -np.inf)

    def clear_of(self, x, y, z):
        """At least how far the point is from this rock."""
        p = np.array([x, y, z]) - self.at
        return float(np.max(self.normals @ p - self.offsets))

    def data(self, mat=_M_ROCK):
        """As scene data: its planes in the world, a sphere round it, and
        how rough its broken faces are."""
        offs = self.offsets + self.normals @ self.at
        pts = self.corners()
        mid = pts.mean(axis=0)
        return ("rock", mat,
                tuple(tuple(float(q) for q in (*nrm, off))
                      for nrm, off in zip(self.normals, offs)),
                tuple(float(q) for q in mid),
                float(np.max(np.linalg.norm(pts - mid, axis=1))),
                min(0.07, 0.015 + 0.1 * self.size))


class _Props:
    """What a room has in it: clusters of primitives, each with a bounding
    sphere, so a point far from a cluster pays one distance for all of it."""

    def __init__(self, clusters):
        self.groups = []
        for cl in clusters:
            boxes = [p for p in cl if p[0] == "box"]
            caps = [p for p in cl if p[0] == "cap"]
            rocks = [p for p in cl if p[0] == "rock"]
            centres, radii = [], []
            for _, _, c, half, r, *_ in boxes:
                centres.append(c)
                radii.append(math.sqrt(sum(h * h for h in half)) + r)
            for _, _, a, b, r in caps:
                centres.append(tuple((a[i] + b[i]) / 2 for i in range(3)))
                radii.append(0.5 * math.dist(a, b) + r)
            for _, _, _, c, r, rough in rocks:
                centres.append(c)
                radii.append(r + rough)
            mid = np.mean(np.array(centres), axis=0)
            rad = max(math.dist(mid, c) + r for c, r in zip(centres, radii))
            g = {"mid": mid.astype(F32), "rad": float(rad)}
            if boxes:
                g["bc"] = np.array([p[2] for p in boxes], dtype=F32).T
                g["bh"] = np.array([p[3] for p in boxes], dtype=F32).T
                g["br"] = np.array([p[4] for p in boxes], dtype=F32)
                # local from world: the transpose of each rotation
                g["bR"] = np.array([_rot(*p[5:8]).T for p in boxes], dtype=F32)
                g["bm"] = np.array([p[1] for p in boxes], dtype=np.int32)
            if caps:
                g["ca"] = np.array([p[2] for p in caps], dtype=F32).T
                g["cb"] = np.array([p[3] for p in caps], dtype=F32).T
                g["cr"] = np.array([p[4] for p in caps], dtype=F32)
                g["cm"] = np.array([p[1] for p in caps], dtype=np.int32)
            if rocks:
                # every rock padded to the same count of planes with copies
                # of its own first one, which changes nothing
                most = max(len(p[2]) for p in rocks)
                planes = np.array([p[2] + p[2][:1] * (most - len(p[2]))
                                   for p in rocks], dtype=F32)
                g["kn"] = np.ascontiguousarray(planes[:, :, :3])
                g["kd"] = np.ascontiguousarray(planes[:, :, 3])
                g["kc"] = np.array([p[3] for p in rocks], dtype=F32)
                g["kb"] = np.array([p[4] + p[5] for p in rocks], dtype=F32)
                g["kr"] = np.array([p[5] for p in rocks], dtype=F32)
                g["km"] = np.array([p[1] for p in rocks], dtype=np.int32)
            self.groups.append(g)

    @staticmethod
    def _rocks(g, lx, ly, lz, detail):
        """Distance to each fallen rock: its planes, then the broken face
        of it. The roughness only cuts in, so the planes stay a bound; it is
        only worked out where a surface is close enough to show it.

        A rock sits inside its bounding sphere, so the sphere is a safe
        distance to it from outside; the planes are only measured for the
        pairs of point and rock that are close. The march finds the planes
        alone, as it finds the walls without their second octave: the
        broken face only has to be there when the normals are taken."""
        c = g["kc"]
        d = np.sqrt((lx[:, None] - c[:, 0]) ** 2 + (ly[:, None] - c[:, 1]) ** 2
                    + (lz[:, None] - c[:, 2]) ** 2) - g["kb"]
        pi, ri = np.nonzero(d < 0.5)
        if not pi.size:
            return d
        pts = np.stack((lx[pi], ly[pi], lz[pi]), axis=1)
        flat = (np.einsum("mj,mpj->mp", pts, g["kn"][ri]) - g["kd"][ri]).max(axis=1)
        near = np.flatnonzero(flat < 0.25) if detail else ()
        if len(near):
            x, y, z = pts[near, 0], pts[near, 1], pts[near, 2]
            # a broken face is flat overall and crazed with creases: fold
            # the noise so its middle becomes a ridge line
            grit = (0.65 * (1.0 - np.abs(2.0 * _noise(x * 4.1 + 11.0, y * 4.1,
                                                        z * 4.1) - 1.0))
                    + 0.35 * (1.0 - np.abs(2.0 * _noise(x * 9.7, y * 9.7 + 5.0,
                                                        z * 9.7) - 1.0)))
            # and bent a little across its whole width, the way a break runs
            wave = _noise(x * 1.2 - 7.0, y * 1.2, z * 1.2)
            flat[near] = flat[near] + g["kr"][ri[near]] * (0.8 * grit + 0.6 * wave)
        d[pi, ri] = flat
        return d

    def distance(self, px, py, pz, codes=False, detail=False):
        d = np.full(px.shape, 1.0e3, dtype=F32)
        what = np.zeros(px.shape, dtype=np.int32)
        for g in self.groups:
            m = g["mid"]
            far = np.sqrt((px - m[0]) ** 2 + (py - m[1]) ** 2
                          + (pz - m[2]) ** 2) - g["rad"]
            # nothing in a cluster is nearer than its bounding sphere; close
            # to it, measure the real thing instead
            d = np.minimum(d, np.where(far < 1.2, 1.0e3, far))
            i = np.flatnonzero(far < 1.2)
            if not i.size:
                continue
            lx, ly, lz = px[i], py[i], pz[i]
            parts, mats = [], []
            if "bc" in g:
                c, hh, rr, R = g["bc"], g["bh"], g["br"], g["bR"]
                dx, dy, dz = lx[:, None] - c[0], ly[:, None] - c[1], lz[:, None] - c[2]
                qx = np.abs(dx * R[:, 0, 0] + dy * R[:, 0, 1] + dz * R[:, 0, 2]) - hh[0] + rr
                qy = np.abs(dx * R[:, 1, 0] + dy * R[:, 1, 1] + dz * R[:, 1, 2]) - hh[1] + rr
                qz = np.abs(dx * R[:, 2, 0] + dy * R[:, 2, 1] + dz * R[:, 2, 2]) - hh[2] + rr
                parts.append(np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2
                                     + np.maximum(qz, 0) ** 2)
                             + np.minimum(np.maximum(qx, np.maximum(qy, qz)), 0) - rr)
                mats.append(g["bm"])
            if "ca" in g:
                a, b, rr = g["ca"], g["cb"], g["cr"]
                bx, by, bz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
                ax_, ay_, az_ = lx[:, None] - a[0], ly[:, None] - a[1], lz[:, None] - a[2]
                h = np.clip((ax_ * bx + ay_ * by + az_ * bz)
                            / np.maximum(bx * bx + by * by + bz * bz, 1e-9), 0.0, 1.0)
                parts.append(np.sqrt((ax_ - bx * h) ** 2 + (ay_ - by * h) ** 2
                                     + (az_ - bz * h) ** 2) - rr)
                mats.append(g["cm"])
            if "kn" in g:
                parts.append(self._rocks(g, lx, ly, lz, detail))
                mats.append(g["km"])
            allp = np.concatenate(parts, axis=1)
            dd = allp.min(axis=1)
            closer = dd < d[i]
            d[i] = np.where(closer, dd, d[i])
            if codes:
                mm = np.concatenate(mats)[allp.argmin(axis=1)]
                what[i] = np.where(closer, mm, what[i])
        return (d, what) if codes else d


@lru_cache(maxsize=32)
def _props_for(props):
    return _Props(props) if props else None


class _Later:
    """Furniture that takes working out — a whole collapse, dropped rock
    by rock — built the first time its room is drawn, not when the game
    starts. The rooms ahead are drawn on a worker thread before you walk
    into them, so that is where the cost lands; at import it was a
    second's pause before the title. Stands in for a Scene's `props`: it
    is true, it iterates as the clusters, and it hashes as itself."""

    def __init__(self, fn, *args, **kw):
        self.fn, self.args, self.kw = fn, args, kw
        self.got = None
        self.lock = threading.Lock()

    def __iter__(self):
        with self.lock:
            if self.got is None:
                self.got = tuple(self.fn(*self.args, **self.kw))
        return iter(self.got)


def _ground_bump(s, px, pz, n):
    """The floor's own relief — cobble, broken plate, guano, silt — and
    what it is made of."""
    v = s.var
    g = s.ground
    if g == "cobble":
        return _cobbles(px, pz, 0.3, int(v * 10))
    if g == "plate":
        # a bed that came down flat and broke where it hit: slabs a pace or
        # two across, each settled at its own tilt, the cracks between them
        # opened wide and dark
        lift, crack = _plates(px, pz, 1.4, int(v * 10), lean=2.2)
        return (lift * 0.3 - 0.3 * np.clip(1.0 - crack / 0.14, 0.0, 1.0) ** 2,
                _M_ROCK)
    if g == "guano":
        return (0.18 * (_noise(px * 0.45 + v, 0.3, pz * 0.45) - 0.5)
                + 0.03 * (n - 0.5), _M_GUANO)
    if g == "rubble":
        # what broke small when the roof came down, heaped under the
        # blocks; the chips big enough to see are rocks of their own
        return _RUBBLE * n, _M_ROCK
    if g == "scree":
        # the same heap under loose chips (`_chips`, added by the room
        # only near the floor, where they can be seen)
        return _RUBBLE * n, _M_ROCK
    if g in ("silt", "dust", "bone"):
        mat = {"silt": _M_SILT, "dust": _M_DUST, "bone": _M_BONE}[g]
        return 0.01 * (n - 0.5), mat
    return (n - 0.5) * s.rough * 0.5, _M_ROCK


def _ripple(s, x, z):
    """Running water's surface, in metres off level: crests across the
    flow, bent and broken up by the bed under them. A centimetre at most —
    enough to break up what the water reflects, which is how you see that
    it moves."""
    bend = _noise(x * 2.3 + s.var, np.full(x.shape, 1.7, F32), z * 0.9)
    chop = _noise(x * 5.1, np.full(x.shape, 3.3, F32), z * 2.2 - s.var) - 0.5
    return s.flow * 0.006 * (np.sin(z * 11.0 + bend * 7.0) + 0.8 * chop)


def _parting(s, y, n):
    """How deep into a parting between two beds a height is: 1 on the
    parting, 0 on the face of a bed. The beds run from a hand to a forearm
    thick, waver along the wall (`n` is the rock's own noise), and some of
    the partings are barely there."""
    f = (y + 0.16 * np.sin(y * 2.3 + s.var) + 0.1 * np.sin(y * 5.3)) / 0.42 + 0.45 * n
    k = np.floor(f)
    deep = 0.35 + 0.65 * _NTEX[k.astype(np.int32) & _MASK, 5, 11]
    return deep * np.clip(1.0 - np.abs(f - k - 0.5) / 0.09, 0.0, 1.0)


@lru_cache(maxsize=32)
def _ways(s):
    """A dome's or a hall's openings, worked out once: for each, the line
    it runs along (sin, cos), its half-width and half-height, its sill, its
    shape, where its line starts (x, z off the room's middle, and how far
    along it reads there), where the cut into the rock starts, and how far
    out the mouth is.

    A way in `s.ways` is a bearing, a width, a height, how far up the wall
    it starts (0, the floor, if not given), a shape where its proportions
    do not say it ("keyhole", "bedding"), and a skew: how many
    degrees off the bearing it runs once it is into the rock (0, straight
    out, if not given)."""
    fl = s.floor

    def mouth(sx_, sz_, y):
        """How far out along a bearing the room's own wall stands, at
        height `y` over the floor: where a way leaves the room."""
        if s.kind == "dome":
            return s.wall * math.sqrt(max(0.05, 1.0 - (y / (s.ceil - fl)) ** 2))
        return min(s.far / max(abs(sz_), 1e-3), s.wall / max(abs(sx_), 1e-3))

    ways = []
    for b, w, hh, *rest in s.ways:
        sill = rest[0] if rest else 0.0
        skew = rest[2] if len(rest) > 2 else 0.0
        sx_, sz_ = math.sin(math.radians(b)), math.cos(math.radians(b))
        m = mouth(sx_, sz_, sill + hh * 0.5)
        # A skewed way is measured from where it leaves the room, along
        # its own line; a straight one from the middle of the room, as it
        # always was. Either way `along` reads `m` at the mouth.
        ox = oz = 0.0
        start = 0.5
        if skew:
            ox, oz = m * sx_, m * sz_
            sx_, sz_ = (math.sin(math.radians(b + skew)),
                        math.cos(math.radians(b + skew)))
            start = m - 0.4
        ways.append((sx_, sz_, w * 0.5, hh * 0.5, sill,
                     rest[1] if len(rest) > 1 else "", ox, oz,
                     m if skew else 0.0, start, m))
    return tuple(ways)


def _room_air(s, detail):
    """Signed distance, with a `.material`, for the furnished room kinds."""
    v = s.var
    oct_n = 2 if detail else 1
    fl = s.floor
    props = _props_for(s.props)
    rng = np.random.default_rng(int(v * 1000) + 5)

    def rockface(px, py, pz):
        n = _fbm(px * s.freq + v, py * s.freq, pz * s.freq, oct_n)
        d = (n - 0.5) * s.rough
        if s.bed:
            d = d + s.bed * np.sin(py * 4.1 + n * 3.4) * 0.5
        if s.scallop:
            # water-scooped hollows, each a spoon a hand or two across,
            # stretched the way the flow went: ridges between dished cells
            c = _noise(pz * 1.6 + v, py * 3.2, px * 0.8)
            d = d + s.scallop * (1.0 - np.abs(2.0 * c - 1.0)) ** 2
        if s.ledges:
            # Water cutting down through the beds leaves each one standing
            # a little proud and the soft parting between two of them cut
            # back into a groove (drawn dark as well, in `_paint`): lines
            # that run the length of the wall, which is what makes a canyon
            # read as one going away from you.
            d = d + s.ledges * (1.0 - _parting(s, py, n))
        return d, n

    if s.kind in ("dome", "hall"):
        ways = _ways(s)
        cz = s.far if s.kind == "dome" else 0.0
        # the pockets bats wore into a roost's ceiling, over centuries
        pockets = []
        for _ in range(s.pockets):
            a = rng.uniform(0, 2 * math.pi)
            e = rng.uniform(0.15, 0.75)
            pockets.append((s.wall * e * math.sin(a), fl + (s.ceil - fl)
                            * math.sqrt(max(0.0, 1 - e * e)) * 0.98,
                            cz + s.wall * e * math.cos(a), rng.uniform(0.25, 0.5)))

    def walls_of(px, py, pz):
        d, n = rockface(px, py, pz)
        if s.kind == "dome":
            R, H = s.wall, s.ceil - fl
            if s.bell:
                # A bell: broadest at the floor, the walls leaning in from
                # about head height and closing over toward the crown.
                u = np.clip((py - fl) / H, 0.0, 1.0)
                R = R * (1.0 - s.bell * u * np.sqrt(u))
            q = np.sqrt((px / R) ** 2 + ((py - fl) / H) ** 2
                        + ((pz - cz) / R) ** 2)
            w = (1.0 - q) * min(s.wall, H) * 0.9 - d
        elif s.kind == "hall":
            k = max(0.5, min(s.wall, s.ceil - fl) * 0.4)
            w = _smin(s.ceil - py, s.wall - np.abs(px), k)
            w = _smin(w, s.far - pz, k)
            w = _smin(w, pz + 4.0, k) - d
        elif s.kind == "rift":
            xc = s.bend * (np.sin(pz * 0.35 + v) + 0.35 * np.sin(pz * 0.9 + v * 2))
            rel = np.clip((py - fl) / (s.ceil - fl), 0.0, 1.0)
            width = s.rx + (s.ry - s.rx) * rel
            if s.neck:
                # the approach funnels in to the slot over a metre or so,
                # the way a passage gives up its room before a squeeze
                into = np.clip((pz - s.neck) / 1.1 + 0.5, 0.0, 1.0)
                into = into * into * (3.0 - 2.0 * into)
                width = s.wall + (width - s.wall) * into
                xc = xc * into
                top = s.ceil + 0.9 * (1.0 - into)     # the approach stands taller
            else:
                top = s.ceil
            w = _smin(width * 0.5 - np.abs(px - xc), top - py, 0.35)
            w = _smin(w, s.far - pz, 0.3) - d
        elif s.kind == "mine":
            base = fl + s.slope * np.maximum(pz, 0.0)
            w = np.minimum(np.minimum(s.rx - np.abs(px), base + s.ry - py),
                           s.far - pz) - 0.35 * d
        elif s.kind == "jumble":
            base = fl + s.slope * np.maximum(pz, 0.0)
            xc = s.bend * np.sin(pz * 0.3 + v)
            k = 0.6
            roof = base + (s.ceil - fl) - py
            if s.scar:
                # Where the roof came away it is the underside of the next
                # bed up: flat facets, each tilted its own way, stepped
                # back at the broken edges — not the lumps the rest of the
                # rock has. Measured only near the roof; a step is not a
                # smooth surface, so it is also approached slower.
                i = np.flatnonzero(roof < 1.5)
                if i.size:
                    lift, _ = _plates(px[i], pz[i], 1.5, int(v * 10) + 5)
                    roof[i] = ((roof[i] + s.scar * np.clip(lift, 0.0, 1.2)
                                + 0.75 * d[i]) * 0.7)
            w = _smin(roof, s.wall - np.abs(px - xc), k)
            w = _smin(w, s.far - pz, k)
            w = _smin(w, pz + 3.0, k) - d
        else:                                    # under: a drowned tube
            xc = s.bend * np.sin(pz * 0.17 + v)
            q = np.sqrt(((px - xc) / s.rx) ** 2 + (py / s.ry) ** 2)
            w = (1.0 - q) * min(s.rx, s.ry) - d
        if s.fill:
            # Sediment does not stop at the wall in a crease: it banks up
            # against it, and the wall comes down into it in a curve. Only
            # the room's own walls — the ways are cut after, or it would
            # silt a slot shut to the knee and leave the rest hanging.
            w = _smin(w, floor_of(px, py, pz, n)[0], s.fill)
        if s.kind in ("dome", "hall"):
            for sx_, sz_, hw, hh, sill, shape, ox, oz, m0, start, m in ways:
                along = (px - ox) * sx_ + (pz - cz - oz) * sz_ + m0
                side = (px - ox) * sz_ - (pz - cz - oz) * sx_
                mid = fl + sill + hh
                if shape == "keyhole":
                    # A keyhole: the round tube water dissolved first, and
                    # under it the slot a stream later cut down through its
                    # floor — `hw` is the tube, shoulder-wide; the slot is
                    # hip-wide. It snakes once it is into the rock, so the
                    # light never finds the far end.
                    # Neither part is drawn true: the tube is out of round,
                    # the slot wanders as it goes down and widens by
                    # degrees toward the tube, and the edges are ragged.
                    into = np.clip(along - m - 0.6, 0.0, 1.0)
                    top = fl + sill + 2.0 * hh - hw
                    up = np.clip((py - fl - sill) / (top - fl - sill), 0.0, 1.0)
                    q = (side - 0.13 * np.sin(along * 1.9 + v) * into
                         - 0.03 * np.sin(py * 3.1 + v))
                    ang = np.arctan2(q, py - top)
                    r = hw * (1.0 + 0.08 * np.sin(ang * 2.0 + v)
                              + 0.05 * np.sin(ang * 5.0 - v))
                    tube = r - np.sqrt(q * q + (py - top) ** 2)
                    slot = np.minimum(hw * (0.58 + 0.12 * up) - np.abs(q), top - py)
                    tun = -_smin(-tube, -slot, 0.06)
                    w = np.maximum(w, np.where(along > start, tun, -1.0) - 0.45 * d)
                    continue
                if shape == "bedding":
                    # A way along a bedding plane, and not a hole drilled in
                    # the wall: the room's own floor running on in under the
                    # bed above, wide and low. The roof is that bed's
                    # underside, flat, dipping a little across the way,
                    # stepped up where a slab of it came away (the phase is
                    # the bearing's own, so no two step alike), and coming
                    # down to the floor at both sides, so the way pinches
                    # out into cracks. Past the mouth it turns back across
                    # the way you are looking, so the beam finds its far
                    # wall going round the bend and the dark is only where
                    # it goes on out of sight — a way that runs straight
                    # off from the lamp is a black oval.
                    ph = v + 3.7 * sx_ + 1.3 * sz_
                    into = np.maximum(along - m + 0.4, 0.0)
                    q = side + math.copysign(0.75, sx_) * (np.sqrt(1.0 + into * into)
                                                            - 1.0)
                    edge = np.clip((hw - np.abs(q)) / (0.4 * hw), 0.0, 1.0)
                    roof = (fl + sill + 2.0 * hh * edge * edge * (3.0 - 2.0 * edge)
                            - 0.3 * hh * q / hw
                            + 0.09 * np.clip(3.0 * np.sin(q * 2.1 + ph) - 1.2, 0.0, 1.0)
                            - 0.07 * into)
                    tun = np.minimum(roof - py, hw - np.abs(q)) * 0.4
                    w = np.maximum(w, np.where(along > start, tun, -1.0) - 0.4 * d)
                    continue
                if hh < 0.5 * hw:
                    # a bedding-plane crawl leaves as a slot between two
                    # beds: flat above and below, thinning out to the sides
                    thin = hh * (1.0 - 0.6 * np.clip(side / hw, -1.0, 1.0) ** 2)
                    tun = _smin(thin - np.abs(py - mid), hw - np.abs(side), 0.2)
                    w = np.maximum(w, np.where(along > start, tun, -1.0) - 0.3 * d)
                    continue
                if hh > 2.5 * hw:
                    # a canyon, cut down by water: sides near parallel, a
                    # little wider where the stream runs than at the top
                    up = np.clip((py - fl - sill) / (2.0 * hh), 0.0, 1.0)
                    tun = _smin(hw * (1.25 - 0.5 * up) - np.abs(side),
                                hh - np.abs(py - mid), 0.3)
                    w = np.maximum(w, np.where(along > start, tun, -1.0) - 0.9 * d)
                    continue
                tun = (1.0 - np.sqrt((side / hw) ** 2 + ((py - mid) / hh) ** 2)) * hw
                w = np.maximum(w, np.where(along > start, tun, -1.0) - 0.5 * d)
            for x, y, z, r in pockets:
                w = np.maximum(w, r - np.sqrt((px - x) ** 2 + (py - y) ** 2
                                              + (pz - z) ** 2) - 0.3 * d)
        if s.chimney:
            # a shaft going up out of the roof, past any beam
            cx, czz = 0.0, (cz if s.kind == "dome" else s.hole_z)
            chim = s.chimney - np.sqrt((px - cx) ** 2 + (pz - czz) ** 2) - 0.5 * d
            w = np.maximum(w, np.where(py > s.ceil - 1.5, chim, -1.0))
        return w, n

    def floor_of(px, py, pz, n):
        base = fl + (s.slope * np.maximum(pz, 0.0) if s.kind in ("mine", "jumble")
                     else 0.0)
        bump, mat = _ground_bump(s, px, pz, n)
        if s.ground == "scree":
            i = np.flatnonzero(py - base - bump < 0.3)
            if i.size:
                bump = bump.copy()
                bump[i] = bump[i] + _chips(px[i], pz[i], 0.32, int(s.var * 10) + 7)
        f = (py - base - bump) * 0.8
        if s.pit:
            x, z, r = s.pit
            f = np.maximum(f, r - np.sqrt((px - x) ** 2 + (pz - z) ** 2))
        return f, mat

    def parts(px, py, pz, codes=False):
        w, n = walls_of(px, py, pz)
        f, fmat = floor_of(px, py, pz, n)
        if s.water is not None:
            top = py - s.water
            if s.flow:
                i = np.flatnonzero(np.abs(top) < 0.1)
                top[i] = top[i] - _ripple(s, px[i], pz[i])
            f = np.minimum(f, top)
        got = props.distance(px, py, pz, codes, detail) if props else None
        if codes:
            pd, what = got if got is not None else (np.full_like(px, 1e3), None)
            return w, f, pd, what, fmat
        return w, f, (got if got is not None else np.full_like(px, 1e3))

    def air(px, py, pz):
        w, f, pd = parts(px, py, pz)
        return np.minimum(np.minimum(w, f), pd)

    def dry(px, py, pz):
        """The room as if the water were not there: what the beam finds
        when it goes down through it."""
        w, n = walls_of(px, py, pz)
        f, _ = floor_of(px, py, pz, n)
        a = np.minimum(w, f)
        return (np.minimum(a, props.distance(px, py, pz, detail=detail))
                if props else a)

    def material(px, py, pz):
        w, f, pd, what, fmat = parts(px, py, pz, codes=True)
        m = np.argmin(np.stack((w, f, pd)), axis=0)
        mat = np.where(m == 0, _M_ROCK, fmat)
        if s.water is not None:
            mat = np.where((m == 1) & (np.abs(py - s.water) < 0.02), _M_WATER, mat)
        if what is not None:
            mat = np.where(m == 2, what, mat)
        return mat

    air.material = material
    air.dry = dry
    return air


def _paint(s, x, y, z, nx, ny, nz):
    """What has been put on the rock: soot, lamp-black, footprints, a
    crowd of crickets. Returns a factor for each hit's albedo."""
    out = np.ones(x.shape, dtype=F32)
    if s.gloom:
        # Inside a way the lamp only gets in at a slant, off the lips of
        # it, and nothing in there sends much back: the rock goes dark by
        # degrees as the way goes in, which is what tells you it is a way
        # and not a mark on the wall.
        cz = s.far if s.kind == "dome" else 0.0
        for sx_, sz_, hw, hh, sill, _, ox, oz, m0, _, m in _ways(s):
            along = (x - ox) * sx_ + (z - cz - oz) * sz_ + m0
            side = (x - ox) * sz_ - (z - cz - oz) * sx_
            near = (np.abs(side) < hw + 0.3) & (y < s.floor + sill + 2.0 * hh + 0.3)
            deep = np.clip(along - m + 0.1, 0.0, None) * near
            out = out * np.exp(-s.gloom * deep)
    if s.ledges:
        # the partings between the beds are shale, darker than the stone,
        # and the fainter the ledges the fainter the partings
        n = _fbm(x * s.freq + s.var, y * s.freq, z * s.freq, 1)
        out = out * (1.0 - 0.55 * min(1.0, s.ledges / 0.06) * _parting(s, y, n)
                     * (np.abs(ny) < 0.8))
    for mark in s.marks:
        kind, *a = mark
        if kind == "specks":
            # Insects at head height: a crowd of small dark bodies, thick
            # in some places and thin in others, thinning out above and
            # below the band they keep to — not rows. Each sits anywhere in
            # its own cell of space; where the rock passes near one, it
            # shows.
            y0, y1, size, cover = a
            wall = np.abs(ny) < 0.7
            h = y - s.floor
            band = np.clip(np.minimum(h - y0, y1 - h) / 0.25 + 0.5, 0.0, 1.0) * wall
            patch = np.clip(1.8 * _noise(x * 1.3 + 40.0, y * 1.3, z * 1.3) - 0.35,
                            0.0, 1.0)
            gx, gy, gz = np.floor(x / size), np.floor(y / size), np.floor(z / size)
            ix, iy, iz = (g.astype(np.int32) & _MASK for g in (gx, gy, gz))
            here = _NTEX[ix, iy, iz] < cover * patch
            cx = (gx + 0.15 + 0.7 * _NTEX[iy, iz, ix]) * size
            cy = (gy + 0.15 + 0.7 * _NTEX[iz, ix, iy]) * size
            cz = (gz + 0.15 + 0.7 * _NTEX[ix, iz, iy]) * size
            big = 0.3 + 0.2 * _NTEX[iz, iy, ix]
            dist = np.sqrt((x - cx) ** 2 + ((y - cy) * 1.6) ** 2 + (z - cz) ** 2)
            dot = np.clip(1.0 - dist / (size * big), 0.0, 1.0) ** 0.5
            out = out * (1.0 - 0.85 * dot * here * band)
        elif kind == "soot":
            # carbide smoke: feathered, darkest at the heart, streaking up
            cx, cy, cz, r, k = a
            i = np.flatnonzero((np.abs(x - cx) < 1.3 * r) & (np.abs(z - cz) < 1.3 * r)
                               & (y > cy - 1.3 * r) & (y < cy + 3.0 * r))
            if i.size:
                xi, yi, zi = x[i], y[i], z[i]
                dy = np.maximum(yi - cy, 0.0) * 0.45 + np.minimum(yi - cy, 0.0) * 1.6
                dist = np.sqrt((xi - cx) ** 2 + dy ** 2 + (zi - cz) ** 2) / r
                feather = _noise(xi * 7.0, yi * 3.0, zi * 7.0)
                out[i] = out[i] * (1.0 - k * np.clip(1.2 - dist - 0.35 * feather,
                                                     0.0, 1.0))
        elif kind == "text":
            # lettering in lamp-black on a wall facing `yaw` — or cut into
            # a stone, which reads the same: the cut holds the shadow.
            # `deep` is how far off the face it takes, so what is cut in
            # the front of a thin stone does not come through its back.
            words, cx, cy, cz, tall, yaw, k, *deep = a
            c, sn = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
            u = (x - cx) * c - (z - cz) * sn        # across the wall
            w = (y - cy)                             # up it
            off = np.abs((x - cx) * sn + (z - cz) * c)
            ink = _letters(words, u / tall, w / tall) * (off < (deep[0] if deep
                                                                else 0.5))
            out = out * (1.0 - k * ink)
        elif kind == "prints":
            # a line of boot prints pressed into silt, one after the other
            x0, z0, bearing, pace, count, k = a
            c, sn = math.cos(math.radians(bearing)), math.sin(math.radians(bearing))
            along = (x - x0) * sn + (z - z0) * c
            across = (x - x0) * c - (z - z0) * sn
            step = np.clip(np.round(along / pace), 0, count - 1)
            side = np.where(step % 2 == 0, -0.11, 0.11)
            du = (along - step * pace) / 0.16
            dv = (across - side) / 0.07
            print_ = np.clip(1.0 - (du * du + dv * dv), 0.0, 1.0) * (ny > 0.8)
            out = out * (1.0 - k * print_ * (along > -0.2)
                         * (along < (count - 0.5) * pace))
        elif kind == "joint":
            # the crack the water found and opened: a dark hairline
            # wandering up a wall that faces you, from y0 to y1
            cx, cz, y0, y1, k = a
            off = (x - cx - 0.04 * np.sin(y * 3.7 + cz)
                   - 0.05 * (_noise(y * 4.0, 2.0, cz) - 0.5))
            line = (np.clip(1.0 - np.abs(off) / 0.014, 0.0, 1.0)
                    * (y > y0) * (y < y1) * (np.abs(z - cz) < 0.5) * (np.abs(nz) > 0.4))
            out = out * (1.0 - k * line)
        elif kind == "stones":
            # Laid fieldstone, on the faces of whatever stands in the box
            # given: courses a hand or two high that waver, each stone its
            # own length, the joints between them dark where it was laid
            # dry and pale where somebody mortared it (`k` below zero).
            x0, x1, y0, y1, z0, z1, k = a
            i = np.flatnonzero((x > x0) & (x < x1) & (y > y0) & (y < y1)
                               & (z > z0) & (z < z1) & (np.abs(ny) < 0.75))
            if i.size:
                xi, yi, zi = x[i], y[i], z[i]
                along = np.where(np.abs(nx[i]) > np.abs(nz[i]), zi, xi)
                # the beds wander, and no two courses are the same height
                f = ((yi - y0) / 0.2
                     + 0.5 * (_noise(along * 1.3, yi * 0.7, 3.0) - 0.5)
                     + 0.35 * np.sin(along * 2.3 + yi))
                row = np.floor(f).astype(np.int32)
                tall = 0.13 + 0.14 * _NTEX[row & _MASK, 11, 4]
                horiz = np.clip((0.5 - np.abs(f - row - 0.5)) * tall / 0.024,
                                0.0, 1.0)
                # stones from a fist to a forearm long, the ends not square
                long = 0.16 + 0.42 * _NTEX[row & _MASK, 3, 7] ** 1.5
                g = ((along + 0.12 * (f - row) * (_NTEX[row & _MASK, 5, 1] - 0.5)
                      + _NTEX[row & _MASK, 9, 2] * long) / long)
                g = g + 0.25 * (_noise(along * 3.1, yi * 3.1, 7.0) - 0.5)
                vert = np.clip(np.abs(g - np.round(g)) * long / 0.022, 0.0, 1.0)
                joint = 1.0 - np.minimum(horiz, vert)
                # each stone a shade of its own
                own = _NTEX[row & _MASK, np.floor(g).astype(np.int32) & _MASK, 5]
                out[i] = out[i] * (1.0 - k * joint) * (0.7 + 0.55 * own)
        elif kind == "scuff":
            # fresh scuffing: rock rubbed pale by a body going through, in
            # streaks the way it went, fading out from the worst of it
            cx, cy, cz, r, k = a
            dist = np.sqrt((x - cx) ** 2 + ((y - cy) * 1.5) ** 2 + (z - cz) ** 2) / r
            streak = 0.5 + 0.5 * np.sin(y * 70.0 + 5.0 * _noise(x * 9.0, y * 2.0, z * 9.0))
            fade = np.clip(1.0 - dist, 0.0, 1.0) * (0.4 + 0.6 * streak)
            out = out * (1.0 + k * fade)
        elif kind == "band":
            # A flood line: the rock stained up to where the water stood,
            # the top of it wandering as the water settled, and a darker
            # rim of dried scum along it — a tide mark, not a ruled line.
            y0, y1, k = a
            top = s.floor + y1 + 0.07 * (_noise(x * 1.7, z * 0.6, 9.0) - 0.5)
            wall = np.abs(ny) < 0.8
            out = out * (1.0 - k * ((y > s.floor + y0) & (y < top)) * wall)
            rim = np.clip(1.0 - np.abs(y - top) / 0.035, 0.0, 1.0)
            out = out * (1.0 - 1.4 * k * rim * wall)
    return out


# a 3x5 hand for lamp-black lettering: enough for a date, and for the one
# word cut on the 1911 stone
_GLYPHS = {
    "E": "111100110100111", "H": "101101111101101", "R": "110101110101101",
    "0": "111101101101111", "1": "010110010010111", "2": "111001111100111",
    "3": "111001111001111", "4": "101101111001001", "5": "111100111001111",
    "6": "111100111101111", "7": "111001010010010", "8": "111101111101111",
    "9": "111101111001111",
}


def _letters(words, u, w):
    """How much ink is at (u, w), in letter-heights from the start of the
    text's baseline. Blocky on purpose — it was written with a finger."""
    ink = np.zeros(u.shape, dtype=F32)
    cols = np.floor(u * 3.0 / 0.8).astype(np.int32)        # 3 cells a glyph wide
    rows = np.floor((1.0 - w) * 5.0).astype(np.int32)      # 5 tall
    for k, ch in enumerate(words):
        g = _GLYPHS.get(ch)
        if not g:
            continue
        cc = cols - k * 4                                   # a gap between
        inside = (cc >= 0) & (cc < 3) & (rows >= 0) & (rows < 5)
        idx = np.where(inside, rows * 3 + cc, 0)
        bits = np.array([int(b) for b in g], dtype=F32)
        ink = np.maximum(ink, bits[idx] * inside)
    return ink


def _air_fn(s: Scene, detail=False):
    """Signed distance for a scene: positive in open space, negative in rock.

    `detail` adds the second noise octave. The march runs without it — it only
    needs to know roughly where the rock is — and the normals are taken with
    it, which is where the texture actually shows up.
    """
    if s.kind in _ROOMS:
        return _room_air(s, detail)
    v = s.var
    oct_n = 2 if detail else 1

    def rock(px, py, pz):
        """Displacement: fbm lumps, plus the horizontal bedding limestone has."""
        n = _fbm(px * s.freq + v, py * s.freq, pz * s.freq, oct_n)
        d = (n - 0.5) * s.rough
        if s.bed:
            d = d + s.bed * np.sin(py * 4.1 + n * 3.4) * 0.5
        return d

    if s.kind == "tube":
        def air(px, py, pz):
            cx = s.bend * np.sin(pz * 0.17 + v)
            cy = 0.18 * np.sin(pz * 0.11 + v * 2.0)
            d = np.sqrt(((px - cx) / s.rx) ** 2 + ((py - cy) / s.ry) ** 2)
            a = (1.0 - d) * min(s.rx, s.ry) - rock(px, py, pz)
            if s.floor is not None:
                a = np.minimum(a, py - s.floor)
            if s.water is not None:
                a = np.minimum(a, py - s.water)
            return a

    elif s.kind == "chamber":
        # A box, but with every corner rounded off — cave chambers do not
        # have corners, and a hard edge reads instantly as architecture.
        k = max(0.5, min(s.wall, s.ceil - s.floor) * 0.55)

        def air(px, py, pz):
            a = _smin(s.ceil - py, s.wall - np.abs(px), k)
            a = _smin(a, s.far - pz, k)
            a = _smin(a, pz + s.wall * 0.9, k)
            a = np.minimum(a, py - s.floor)      # the floor stays sharp
            a = a - rock(px, py, pz)
            if s.water is not None:
                a = np.minimum(a, py - s.water)
            return a

    elif s.kind == "hole":
        # a shaft opening in a floor — the pitch head. The sink above ground
        # is a forest scene with `camp`, because it stands in the woods.
        def air(px, py, pz):
            ground = py - s.floor - rock(px, py, pz)
            ang = np.arctan2(px, pz - s.hole_z)
            r = np.sqrt(px ** 2 + (pz - s.hole_z) ** 2)
            rim = s.hole_r * (1.0 + 0.26 * np.sin(ang * 3.0 + v)
                              + 0.12 * np.sin(ang * 7.0 - v))
            shaft = np.minimum(rim - r, py - (s.floor - s.depth_below))
            return np.maximum(ground, shaft)

    elif s.kind == "forest":
        st = _stand(s)
        props = _props_for(s.props)
        # the tilt costs the plane SDF its unit gradient, and so does the
        # soil slumping into the sink; keep it conservative
        rise_norm = math.sqrt(1.0 + s.rise * s.rise + (0.5 if s.camp else 0.0))
        inv_cell = 1.0 / _CELL
        # the level of the sink's lip, and of its floor
        lip = s.floor + float(_rise(s, np.float32(_SINK[1])))
        pit = lip - _SINK[3]

        def band(k, g):
            """The points close enough in height to meet something of kind k.

            Anything skipped is more than a full stride away, which the march
            never steps; the give is the hill rising under the thing's reach.
            """
            slop = _STRIDE + s.rise * (k.reach + _STRIDE)
            return np.flatnonzero((g > k.lo - slop) & (g < k.hi + slop))

        def parts(px, py, pz, codes=False):
            """Distances to the ground, the nearest trunk, the leaves, the
            brush and the camp, kept apart — plus the step bound, and with
            `codes` what each piece of the camp is. 1e3 means none near."""
            # The ground goes up ahead of you. This is in the prose — nineteen
            # hundred feet of ridge — and it is also what makes the far ground
            # drawable: a slope is something a ray can actually hit.
            g = py - s.floor - _rise(s, pz)
            # one noise sample does for the ground and for the leaves
            n = _fbm(px * s.freq + v, py * s.freq, pz * s.freq, oct_n)
            disp = (n - 0.5) * (s.rough * 0.6)
            if s.path:
                onp = 1.0 / (1.0 + ((px - _path_x(s, pz)) / s.path) ** 2 * 1.6)
                ground = g - disp * (1.0 - 0.7 * onp) - 0.10 * onp
            else:
                ground = g - disp
            if s.camp:
                # the camp's bench is trodden flat
                cx, cz, ax, az = _CLEARING
                flat = np.clip(1.6 - ((px - cx) / ax) ** 2
                               - ((pz - cz) / az) ** 2, 0.0, 1.0)
                ground = ground + disp * 0.7 * flat
                # The sink: soil slumping in toward a ragged lip, then a
                # limestone throat, narrower than the mouth and stepped with
                # ledges where the bedding broke, going down past any light.
                sag, r, ang, mouth = _slump(s, px, pz)
                ground = (ground + sag) / rise_norm
                dd = lip - py
                # the bedding broke in steps: each layer juts a little and
                # then the next falls back under it
                f = dd * 1.1 + n * 0.7
                f = f - np.floor(f)
                ledge = np.where(f < 0.7, f / 0.7, (1.0 - f) / 0.3)
                throat = (mouth * (0.80 + 0.05 * np.sin(dd * 2.1 + ang * 2.0 + v))
                          - 0.2 * ledge)
                shaft = np.minimum(throat - r, py - pit) * 0.8
                ground = np.maximum(ground, shaft)
            else:
                ground = ground / rise_norm

            ci = np.clip(((px - _GX0) * inv_cell).astype(np.int32), 0, _NX - 1)
            cj = np.clip(((pz - _GZ0) * inv_cell).astype(np.int32), 0, _NZ - 1)
            ex = px - (_GX0 + ci.astype(F32) * _CELL)
            ez = pz - (_GZ0 + cj.astype(F32) * _CELL)
            wall = np.minimum(np.minimum(ex, _CELL - ex),
                              np.minimum(ez, _CELL - ez))
            # nothing this cell leaves out is nearer than this
            wall = np.maximum(wall, 0.0) - 0.1
            bound = wall + st.trunks.margin
            cell = cj * _NX + ci

            # trunks: a per-trunk lean, a taper up, a flare at the root, each
            # standing on its own patch of hill
            def bark(j, f):
                x, z, base, lean, r, top = f
                yb = py[j, None] - base
                ybc = np.clip(yb, 0.0, 9.0)
                hx = px[j, None] - x - lean * ybc
                hz = pz[j, None] - z
                trad = r * (1.12 - 0.045 * ybc
                            + 0.5 * np.clip(0.9 - yb, 0.0, 0.9))
                return np.maximum(np.sqrt(hx * hx + hz * hz) - trad, yb - top)
            trunk = (st.trunks.nearest(cell, bark) if st.trunks.n
                     else np.full_like(ground, 1.0e3))

            leaves = np.full_like(ground, 1.0e3)
            if st.leafy:
                for k in (st.crowns, st.saplings):
                    i = band(k, g) if k.n else ()
                    if len(i):
                        leaves[i] = np.minimum(
                            leaves[i], _cones(k, cell[i], px[i], py[i], pz[i]))
                        bound[i] = np.minimum(bound[i], wall[i] + k.margin)
                # the carve only ever cuts the crown back, never bulges it —
                # a bulge hangs threads off the underside
                leaves = leaves + np.clip(0.55 - n, 0.0, 0.55) * 1.6

            bush = np.full_like(ground, 1.0e3)
            k = st.brush
            i = band(k, g) if k.n else ()
            if len(i):
                lx, ly, lz = px[i], py[i], pz[i]

                def leaf(j, f):
                    x, z, cy, inv, yinv, scale = f
                    qx = (lx[j, None] - x) * inv
                    qy = (ly[j, None] - cy) * yinv
                    qz = (lz[j, None] - z) * inv
                    return (np.sqrt(qx * qx + qy * qy + qz * qz) - 1.0) * scale
                near = k.nearest(cell[i], leaf)
                # leafy, not pillows: a finer carve-only tap, taken only
                # where there is a bush close enough to carve
                j = np.flatnonzero(near < 0.9)
                if j.size:
                    jx, jy, jz = lx[j], ly[j], lz[j]
                    cut = np.clip(0.5 - _noise(jx * 1.4 - v, jy * 1.2, jz * 1.4),
                                  0.0, 0.5) * 0.9
                    if detail:
                        cut = cut - (_noise(jx * 3.1 - v, jy * 2.7,
                                            jz * 3.1) - 0.5) * 0.3
                    near[j] = near[j] + cut
                bush[i] = near
                bound[i] = np.minimum(bound[i], wall[i] + k.margin)

            gear = np.full_like(ground, 1.0e3)
            what = np.zeros(ground.shape, dtype=np.int32) if codes else None
            if st.camp is not None:
                gear, what, seen = st.camp.distance(band, cell, px, py, pz, g,
                                                    codes)
                for k, i in seen:
                    bound[i] = np.minimum(bound[i], wall[i] + k.margin)
            if props:
                # what is set down here — the stones of a place people
                # lived — is a few clusters, each measured whole only near
                got = props.distance(px, py, pz, codes, detail)
                pd, pw = got if codes else (got, None)
                if codes:
                    what = np.where(pd < gear, pw, what)
                gear = np.minimum(gear, pd)
            if codes:
                return ground, trunk, leaves, bush, gear, bound, what
            return ground, trunk, leaves, bush, gear, bound

        def air(px, py, pz):
            ground, trunk, leaves, bush, gear, bound = parts(px, py, pz)
            a = _smin(ground, trunk, 0.25)
            i = np.flatnonzero(leaves < 2.0)
            if i.size:
                a[i] = _smin(a[i], leaves[i], 0.40)
            i = np.flatnonzero(bush < 2.0)
            if i.size:
                a[i] = _smin(a[i], bush[i], 0.3)
            return np.minimum(np.minimum(a, gear), bound)

        def material(px, py, pz):
            """What a point on the surface is made of — one of the _M_ codes."""
            ground, trunk, leaves, bush, gear, _, what = parts(
                px, py, pz, codes=True)
            m = np.argmin(np.stack((ground, trunk, leaves, bush, gear)), axis=0)
            mat = np.where(m == 4, what, m)
            if s.camp:
                # below the slumped soil the sink is limestone
                _, r, _, mouth = _slump(s, px, pz)
                rock = (m == 0) & (r < mouth * 1.02) & (lip - py > 0.8)
                mat = np.where(rock, _M_ROCK, mat)
            return mat

        air.material = material

    elif s.kind == "crawl":
        # A bedding-plane crawl: the gap between two beds of limestone, too
        # low anywhere to lift your head, pinching shut to either side. The
        # silt floor keeps whatever has been dragged through it.
        def centre(z):
            return 0.4 * np.sin(z * 0.12 + v)

        def track(z):
            """Where the drag marks run: a little left of the middle."""
            return centre(z) - 0.12 + 0.05 * np.sin(z * 0.8 + v)

        # the handprint between the marks, in plan: a palm and five fingers
        hand_z = 1.45
        hand_x = float(track(np.float32(hand_z)))
        fingers = [(hand_x + dx, hand_z + dz, hand_x + ex, hand_z + ez)
                   for dx, dz, ex, ez in ((-0.034, 0.035, -0.052, 0.078),
                                          (-0.013, 0.045, -0.018, 0.100),
                                          (0.008, 0.046, 0.012, 0.105),
                                          (0.026, 0.040, 0.036, 0.088),
                                          (0.040, 0.012, 0.075, 0.035))]

        def hand(x, z):
            px_, pz_ = (x - hand_x) / 0.042, (z - hand_z) / 0.052
            d = (np.sqrt(px_ * px_ + pz_ * pz_) - 1.0) * 0.042
            for ax_, az_, bx_, bz_ in fingers:
                vx, vz = bx_ - ax_, bz_ - az_
                h = np.clip(((x - ax_) * vx + (z - az_) * vz)
                            / (vx * vx + vz * vz), 0.0, 1.0)
                d = np.minimum(d, np.hypot(x - ax_ - vx * h, z - az_ - vz * h)
                               - 0.009)
            return d

        # the pack you are pushing ahead of you, off to your right: a
        # tackle bag, a long tube on its side
        pack = ((0.38, s.floor + 0.13, 1.25), (0.95, s.floor + 0.13, 1.55), 0.13)

        def roof_at(x, z, n=0.5):
            gap = (0.37 + 0.05 * np.sin(z * 0.21 + v * 2.0)
                   + 0.03 * np.sin(z * 0.67))
            return s.floor + gap - 0.05 * (n - 0.5)

        # The cave cricket, unhurried, picking its way across the silt a
        # little way ahead of your face: body, head, three pairs of legs —
        # the hind ones long and kneed up high — and two long feelers.
        bug_x, bug_z, bug_yaw = 0.30, 0.78, 250.0
        bx_, bz_ = np.float32(bug_x), np.float32(bug_z)
        by = s.floor + 0.012 * (float(_fbm(bx_ * 2.3 + v, np.float32(s.floor) * 2.3,
                                           bz_ * 2.3, oct_n)) - 0.5)
        cy_, sy_ = math.cos(math.radians(bug_yaw)), math.sin(math.radians(bug_yaw))

        def at(u, w, h):
            """A point in the cricket's own frame: u forward, w across,
            h up off the silt it stands on."""
            return (bug_x + u * sy_ + w * cy_, by + h, bug_z + u * cy_ - w * sy_)

        legs = []
        for side in (-1.0, 1.0):
            for u0, knee, foot in ((0.010, (0.020, 0.012, 0.020),
                                    (0.030, 0.020, 0.0)),
                                   (0.000, (0.004, 0.018, 0.020),
                                    (0.004, 0.030, 0.0)),
                                   (-0.010, (-0.004, 0.016, 0.036),
                                    (-0.040, 0.026, 0.0))):
                a = at(u0, side * 0.006, 0.014)
                k = at(knee[0], side * knee[1], knee[2])
                f = at(foot[0], side * foot[1], foot[2])
                legs += [(a, k, 0.003), (k, f, 0.0024)]
            legs.append((at(0.020, side * 0.003, 0.016),
                         at(0.090, side * 0.030, 0.034), 0.0018))
        bug = [(at(-0.014, 0.0, 0.016), at(0.012, 0.0, 0.015), 0.008),
               (at(0.019, 0.0, 0.013), at(0.019, 0.0, 0.013), 0.006)] + legs
        bug_c = at(0.0, 0.0, 0.015)

        def parts(px, py, pz):
            """Silt floor, rock roof, the pack, the cricket."""
            n = _fbm(px * 2.3 + v, py * 2.3, pz * 2.3, oct_n)
            side = np.abs(px - centre(pz))
            width = 2.3 + 0.6 * np.sin(pz * 0.3 + v)
            pinch = np.clip((side - width + 0.9) / 1.8, 0.0, 1.0)
            pinch = pinch * pinch * (3.0 - 2.0 * pinch)
            roof = roof_at(px, pz, n)
            roof = roof - (roof - s.floor + 0.1) * pinch
            # the silt: near flat, with two furrows dragged into it and a
            # hand pressed between them
            silt = s.floor + 0.012 * (n - 0.5)
            low = np.flatnonzero(py < s.floor + 0.1)
            if low.size:
                lx, lz = px[low], pz[low]
                off = lx - track(lz)
                furrow = (np.exp(-((off + 0.17) / 0.045) ** 2)
                          + np.exp(-((off - 0.17) / 0.045) ** 2))
                ridge = (np.exp(-((off + 0.24) / 0.03) ** 2)
                         + np.exp(-((off - 0.24) / 0.03) ** 2))
                silt[low] = silt[low] + ((0.012 * ridge - 0.035 * furrow)
                                         * np.clip(lz * 2.0, 0.0, 1.0))
            near = np.flatnonzero((np.abs(pz - hand_z) < 0.25)
                                  & (py < s.floor + 0.1))
            if near.size:
                press = np.clip(-hand(px[near], pz[near]) / 0.012 + 0.6,
                                0.0, 1.0)
                silt[near] = silt[near] - 0.012 * press
            floor = (py - silt) * 0.8
            roof = (roof - py) * 0.8

            gear = _seg(px, py, pz, *pack)
            crit = np.full_like(px, 1.0e3)
            i = np.flatnonzero((px - bug_c[0]) ** 2 + (py - bug_c[1]) ** 2
                               + (pz - bug_c[2]) ** 2 < 0.03)
            if i.size:
                crit[i] = np.min([_seg(px[i], py[i], pz[i], a, b, r)
                                  for a, b, r in bug], axis=0)
            return floor, roof, gear, crit

        def air(px, py, pz):
            floor, roof, gear, crit = parts(px, py, pz)
            return np.minimum(np.minimum(floor, roof), np.minimum(gear, crit))

        def material(px, py, pz):
            m = np.argmin(np.stack(parts(px, py, pz)), axis=0)
            return np.array([_M_SILT, _M_ROCK, _M_PACK, _M_BUG])[m]

        air.material = material

    elif s.kind == "drop":
        # Flat on your stomach at the lip with your head over the edge: a
        # hole in the gallery floor, down through a metre and a bit of rock,
        # into a chamber the beam cannot find the far side of — only the
        # breakdown on its floor, twelve metres down. On the lip, the two
        # naturals the prose offers for a rig, and Wren's flagging.
        top = s.floor                       # the gallery floor you lie on
        under = top - 1.3                   # the chamber's ceiling
        bottom = top - s.depth_below        # its floor
        hx_, hz_, mr = 0.0, s.hole_z, s.hole_r

        def mouth_at(ang):
            return mr * (1.0 + 0.15 * np.sin(ang * 3.0 + v)
                         + 0.08 * np.sin(ang * 5.0 - v))

        def lip(a):
            """The point on the lip in direction `a`, radians from ahead."""
            m = float(mouth_at(np.float32(a)))
            return hx_ + m * math.sin(a), hz_ + m * math.cos(a)

        # the flake, standing on the right lip; the thread, a loop of rock
        # the water left on the left lip
        fx, fz = lip(1.75)
        flake = ((fx + 0.12, top + 0.13, fz), (0.035, 0.15, 0.22), 0.02, 75.0)
        tx, tz = lip(-1.6)
        thread = (tx - 0.14, top + 0.01, tz)
        # the flagging: tied round the flake, run over the lip, hanging
        tape = [((fx + 0.12, top + 0.22, fz), (0.05, 0.022, 0.23), 0.006, 75.0),
                ((fx + 0.0, top + 0.012, fz - 0.04), (0.13, 0.005, 0.026),
                 0.004, 15.0),
                ((fx - 0.11, top - 0.26, fz - 0.07), (0.007, 0.27, 0.026),
                 0.004, 15.0)]

        def parts(px, py, pz):
            """Rock, the breakdown far below, and the tape."""
            n = _fbm(px * s.freq + v, py * s.freq, pz * s.freq, oct_n)
            qx, qz = px - hx_, pz - hz_
            r = np.sqrt(qx * qx + qz * qz)
            ang = np.arctan2(qx, qz)
            down = np.clip((top - py) / (top - under), 0.0, 1.0)
            throat = (mouth_at(ang) * (1.0 + 0.45 * down * down)
                      + (n - 0.5) * s.rough)
            disp = (n - 0.5) * s.rough * 0.5
            slab = np.maximum(py - (top + disp), (under + disp) - py)
            rock = np.maximum(slab, (throat - r) * 0.8)
            rock = np.minimum(rock, (top + 1.7) - py)
            # shattered plate, far down: slabs at their own heights, with
            # the cracks between them opened up
            low = np.flatnonzero(py < bottom + 2.0)
            if low.size:
                lift, crack = _plates(px[low], pz[low], 2.4, int(v * 10))
                floor = (bottom + lift * 0.7 + disp[low]
                         - 0.35 * np.clip(1.0 - crack / 0.12, 0.0, 1.0))
                rock[low] = np.minimum(rock[low], (py[low] - floor) * 0.8)
            # the naturals
            ty, tz_ = py - thread[1], pz - thread[2]
            ring = np.sqrt(ty * ty + tz_ * tz_) - 0.11
            loop = np.sqrt(ring * ring + (px - thread[0]) ** 2) - 0.045
            rock = np.minimum(rock, np.minimum(_rbox(px, py, pz, *flake), loop))
            flag = np.min([_rbox(px, py, pz, *b) for b in tape], axis=0)
            return rock, flag

        def air(px, py, pz):
            rock, flag = parts(px, py, pz)
            return np.minimum(rock, flag)

        def material(px, py, pz):
            rock, flag = parts(px, py, pz)
            return np.where(flag < rock, _M_FLAG, _M_ROCK)

        air.material = material

    else:                                            # "void"
        def air(px, py, pz):
            return np.full_like(px, 1.0)

    return air


# --------------------------------------------------------------------------
#  raymarch
# --------------------------------------------------------------------------

def _march(air, dx, dy, dz, steps=44, tmax=34.0, org=None,
           factor=0.62, eps=0.012, smax=1.7, cone=0.0):
    """Sphere-trace, compacting away rays that have already landed.

    Most rays in a cave hit rock within a few metres, so carrying the whole
    frame through all the steps would be almost entirely wasted work.

    `cone` is the angle a pixel spans. With it, a ray lands once it is within
    a fraction of a pixel of something at that range, and never takes a step
    shorter than that — a ray skimming a hillside otherwise closes on it a
    few centimetres at a time, long after the pixel has made up its mind.
    """
    k = dx.size
    zero = np.zeros(k, dtype=F32)
    ox, oy, oz = org if org is not None else (zero, zero, zero)
    t = np.full(k, 0.08, dtype=F32)
    hit = np.zeros(k, dtype=bool)
    live = np.arange(k)
    lt = t.copy()
    ldx, ldy, ldz = dx, dy, dz
    lox, loy, loz = ox, oy, oz
    for _ in range(steps):
        a = air(lox + ldx * lt, loy + ldy * lt, loz + ldz * lt)
        landed = a < eps + cone * lt
        t[live] = lt
        hit[live] = landed
        keep = ~(landed | (lt >= tmax))
        if not keep.any():
            break
        live = live[keep]
        # the displacement breaks the Lipschitz bound, so step conservatively
        lt = lt[keep]
        lt = lt + np.maximum(np.clip(a[keep] * factor, 0.05, smax),
                             cone * 2.0 * lt)
        ldx, ldy, ldz = ldx[keep], ldy[keep], ldz[keep]
        lox, loy, loz = lox[keep], loy[keep], loz[keep]
    else:
        t[live] = lt
    return t, hit


def _normal(air, x, y, z, h=0.03):
    """Tetrahedral gradient — four taps instead of six."""
    offs = ((1.0, -1.0, -1.0), (-1.0, -1.0, 1.0),
            (-1.0, 1.0, -1.0), (1.0, 1.0, 1.0))
    nx = ny = nz = 0.0
    for ox, oy, oz in offs:
        d = air(x + ox * h, y + oy * h, z + oz * h)
        nx = nx + ox * d
        ny = ny + oy * d
        nz = nz + oz * d
    ln = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-6
    return nx / ln, ny / ln, nz / ln


# --------------------------------------------------------------------------
#  palettes — luminance ramps, not tints
# --------------------------------------------------------------------------

_RAMPS = {
    "cave":  [(0.00, (3, 3, 6)), (0.16, (24, 17, 13)), (0.40, (94, 58, 29)),
              (0.72, (214, 152, 88)), (1.00, (255, 240, 216))],
    "dusk":  [(0.00, (7, 9, 13)), (0.20, (26, 31, 36)), (0.48, (62, 68, 62)),
              (0.74, (146, 136, 108)), (1.00, (236, 220, 188))],
    # bad air: the lamp's own colour, gone sick
    "sallow": [(0.00, (4, 4, 2)), (0.16, (21, 20, 9)), (0.40, (78, 74, 32)),
               (0.72, (190, 178, 104)), (1.00, (248, 242, 206))],
    # under the water, where the beam goes green and gives up
    "under": [(0.00, (1, 4, 5)), (0.20, (8, 24, 27)), (0.45, (26, 66, 66)),
              (0.75, (104, 160, 146)), (1.00, (214, 240, 226))],
    "night": [(0.00, (3, 4, 8)), (0.20, (18, 21, 29)), (0.46, (50, 54, 57)),
              (0.74, (166, 138, 96)), (1.00, (244, 226, 194))],
}


@lru_cache(maxsize=8)
def _lut(name):
    pts = _RAMPS.get(name, _RAMPS["cave"])
    xs = np.array([p[0] for p in pts], dtype=F32)
    lut = np.zeros((256, 3), dtype=F32)
    g = np.linspace(0.0, 1.0, 256, dtype=F32)
    for c in range(3):
        ys = np.array([p[1][c] for p in pts], dtype=F32)
        lut[:, c] = np.interp(g, xs, ys)
    return lut


# --------------------------------------------------------------------------
#  render
# --------------------------------------------------------------------------

_FOREST_TAN = 1.6     # widest lens a forest gets, as a half-angle tangent
# A furnished cave room is about what is in it, and on a very wide letterbox
# the widest lens shrank all of that into the middle third. Rooms get a
# little more than a forest; the plain passages keep the full wrap.
_ROOM_TAN = 2.0


def _ground_t(s, dy, dz, oy=0.0, oz=0.0):
    """Where a ray from an eye at height `oy`, `oz` along, meets the bare
    hillside — or inf if it never does."""
    tg = np.full(dy.shape, np.inf, dtype=F32)
    down = dy < -1e-4
    flat = (s.floor - oy) / np.where(down, dy, -1.0)
    near = down & (oz + dz * flat < 4.0)
    tg[near] = flat[near]
    den = dy - s.rise * dz
    up = (den < -1e-4) & ~near
    slope = (s.floor + s.rise * (oz - 4.0) - oy) / np.where(up, den, -1.0)
    far = up & (oz + dz * slope >= 4.0)
    tg[far] = slope[far]
    return tg


def _eye(s):
    """Where you stand: `at` metres in, at eye height over the ground there."""
    if s.kind in _ROOMS:
        z = s.at[1]
        up = s.slope * max(z, 0.0) if s.kind in ("mine", "jumble") else 0.0
        return float(s.at[0]), up, float(z)
    x = np.full(1, s.at[0], dtype=F32)
    z = np.full(1, s.at[1], dtype=F32)
    sag = _slump(s, x, z)[0][0] if s.camp else 0.0
    return float(s.at[0]), float(_rise(s, z)[0] - sag), float(s.at[1])


def _cone_of(axis):
    """How much of the helmet beam a ray at this cosine off-axis is in."""
    return 0.20 + 0.80 * np.clip((axis - 0.60) / 0.36, 0.0, 1.0) ** 0.7


def _render(s: Scene, light: float, w: int, h: int) -> Image.Image:
    """Render a scene. `light` is 0..1 — how much lamp you have."""
    aspect = w / h
    tan_x, tan_y = 0.56 * aspect, 0.56
    cap = s.lens or (_FOREST_TAN if s.kind == "forest" else
                     _ROOM_TAN if s.kind in _ROOMS else 0.0)
    if cap and tan_x > cap:
        # The viewport is a letterbox, and widening the lens to fill it turns
        # the picture into a fisheye: the horizon bows, everything shrinks
        # toward the middle distance, and a whole stand reads as six trees on
        # a diorama. Hold the horizontal angle and let the frame be a slit.
        tan_x = cap
        tan_y = tan_x / aspect
    j, i = np.meshgrid(np.arange(h, dtype=F32), np.arange(w, dtype=F32),
                       indexing="ij")
    sx = ((i + 0.5) / w * 2.0 - 1.0) * tan_x
    sy = (1.0 - (j + 0.5) / h * 2.0) * tan_y
    if s.roll:
        cr, sr = math.cos(s.roll), math.sin(s.roll)
        sx, sy = sx * cr - sy * sr, sx * sr + sy * cr
    dx, dy, dz = sx, sy, np.ones_like(sx)
    if s.tilt:
        ct, st = math.cos(s.tilt), math.sin(s.tilt)
        dy, dz = dy * ct + dz * st, dz * ct - dy * st
    if s.face:
        cf, sf = math.cos(math.radians(s.face)), math.sin(math.radians(s.face))
        dx, dz = dx * cf + dz * sf, dz * cf - dx * sf
    ln = np.sqrt(dx * dx + dy * dy + dz * dz)
    dx, dy, dz = (dx / ln).ravel(), (dy / ln).ravel(), (dz / ln).ravel()
    # How far each ray is off the way your head points: the helmet beam is
    # centred there. The older cave scenes centre it on the horizontal,
    # which is the same thing for all but the few that tilt.
    lamp_led = ("crawl", "drop") + _ROOMS
    near_axis = (1.0 / ln).ravel() if s.kind in lamp_led else dz

    coarse = _air_fn(s)
    fine = _air_fn(s, detail=True)
    surface = s.kind in ("forest", "hole")
    # Above ground the dominant surface is an exact plane, so the march can
    # stride out; underground the displaced tube needs small careful steps.
    # A forest ray still threads past dozens of trunks to reach the far
    # stand; nearly all land inside fifty steps, and the long tail is only
    # the few aimed deep into the haze, so the high cap costs almost nothing.
    if s.kind == "forest":
        mp = dict(steps=128, tmax=_TREE_DEPTH + 12.0, factor=0.92, eps=0.045,
                  smax=_STRIDE, cone=0.35 * 2.0 * tan_x / w)
    elif surface:
        mp = dict(steps=30, factor=0.92, eps=0.03)
    elif s.kind in ("crawl", "drop"):
        # Small things close to the lamp — a cricket, a strip of tape — want
        # a fine tolerance. A crawl's rays skim the beds and creep, but past
        # a few beam-lengths there is nothing to see, so they can stop.
        mp = dict(steps=96, tmax=3.0 * s.reach if s.kind == "crawl" else 30.0,
                  factor=0.75, eps=0.002, cone=0.3 * 2.0 * tan_x / w)
    elif s.kind in _ROOMS:
        mp = dict(steps=140, tmax=45.0, factor=0.75, eps=0.003,
                  cone=0.12 * 2.0 * tan_x / w)
    else:
        mp = {}
    ex, ey, ez = (_eye(s) if s.kind == "forest" or s.kind in _ROOMS
                  else (0.0, 0.0, 0.0))
    if ex or ey or ez:
        mp["org"] = tuple(np.full(dx.size, e, dtype=F32) for e in (ex, ey, ez))
    t, hit = _march(coarse, dx, dy, dz, **mp)
    if s.kind == "forest":
        # A ray that skims the hillside closes on it a few centimetres a step
        # and can run out of steps before it lands. Left alone it was drawn
        # as sky — a third of the ground was — and every trunk behind it
        # stood on a strip of nothing. The hill is a known plane, so put
        # those rays down on it.
        tg = _ground_t(s, dy, dz, ey, ez)
        if s.camp:
            # except where the hill has a hole in it: those go to the bottom
            reach = np.where(np.isfinite(tg), tg, 1e4)
            gx, gz = ex + dx * reach, ez + dz * reach
            into = np.hypot(gx - _SINK[0], gz - _SINK[1]) < _SINK[2] * 1.3
            lip = s.floor + float(_rise(s, np.float32(_SINK[1])))
            tb = (lip - _SINK[3] - ey) / np.minimum(dy, -1e-4)
            tg = np.where(into & (dy < 0), tb, tg)
        miss = ~hit & np.isfinite(tg)
        t = np.where(miss, tg, t).astype(F32)
        hit = hit | miss

    if s.kind in lamp_led or (s.kind == "forest" and s.props):
        # The march lands anywhere within a tolerance, and so close to the
        # lamp that shows: a surface a hand away comes out in terraces. Two
        # more steps put each hit down on the rock itself. A forest's
        # tolerance is wider still — it is set for trees — so a scene with
        # stones close enough to read a date off takes them too.
        for _ in range(2):
            a = coarse(dx * t + ex, dy * t + ey, dz * t + ez)
            t = np.where(hit, t + a * 0.9, t).astype(F32)
    hx, hy, hz = dx * t + ex, dy * t + ey, dz * t + ez
    nx, ny, nz = _normal(fine, hx, hy, hz)

    grain = _fbm(hx * 2.4 + s.var, hy * 2.4, hz * 2.4, 3)
    albedo = 0.30 + 0.52 * grain
    shade = 1.0
    mat = None
    camp = _stand(s).camp if s.kind == "forest" and s.camp else None
    if s.kind in lamp_led:
        mat = coarse.material(hx, hy, hz)
        # a rope is one colour its whole length; the rock's mottle along
        # a line that thin read as the stripes on a surveyor's pole
        albedo = np.where(mat == _M_ROPE, 0.56, albedo) * _TONE[mat]
        if s.marks or s.ledges or s.gloom:
            albedo = albedo * _paint(s, hx, hy, hz, nx, ny, nz)
    if s.kind == "forest":
        # Contact shadow: how much of the air just off the surface is really
        # open. Where a trunk goes into the ground, or brush sits on it, the
        # answer is not much — and that dark seam is what plants the tree.
        occ = 0.0
        for gap, wgt in ((0.25, 0.5), (0.8, 0.5)):
            d = coarse(hx + nx * gap, hy + ny * gap, hz + nz * gap)
            occ = occ + wgt * np.clip(1.0 - d / gap, 0.0, 1.0)
        # and under a closed canopy the whole floor of the wood is in shade:
        # the near things go dark and the brightness is all in the distance
        canopy = 0.5 if _stand(s).leafy else 1.0
        ao = 1.0 - 0.85 * occ
        # What each ray landed on. The woods are all one grey at dusk, so
        # what separates them is what things are made of: needles and
        # rhododendron leaf drink the light, bark less so, and a trail is
        # packed pale dirt with a slot of open sky over it.
        mat = coarse.material(hx, hy, hz)
        tone = _TONE.copy()
        if s.deadwood:
            tone[_M_BARK] = 1.45   # the bark is off them and the wood gone silver
        # A run of water under trees at dusk gives back the dark of the
        # canopy over it: a wet line darker than the leaves either side,
        # flat and even where they are mottled.
        tone[_M_WATER] = 0.7
        albedo = np.where(mat == _M_WATER, 0.5, albedo) * tone[mat]
        if s.marks:
            albedo = albedo * _paint(s, hx, hy, hz, nx, ny, nz)
        if s.path:
            onp = 1.0 / (1.0 + ((hx - _path_x(s, hz)) / s.path) ** 2 * 1.6)
            onp = onp * (mat == _M_GROUND)
            albedo = albedo * (1.0 + 1.3 * onp)
            canopy = canopy + (1.0 - canopy) * 0.7 * onp
        for kx, kz, kr in s.clearing:
            # the woods have come back round it but not over it yet, and
            # what sky there is gets in
            gap = np.clip((kr + 1.5 - np.hypot(hx - kx, hz - kz)) / 3.0, 0.0, 1.0)
            canopy = canopy + (1.0 - canopy) * 0.85 * gap
        if s.camp:
            # the camp's bench is trodden bare, and open to the sky
            cx, cz, ax, az = _CLEARING
            bare = np.clip(1.4 - ((hx - cx) / ax) ** 2 - ((hz - cz) / az) ** 2,
                           0.0, 1.0) * (mat == _M_GROUND)
            albedo = albedo * (1.0 + 0.35 * bare)
            canopy = canopy + (1.0 - canopy) * 0.8 * bare
        shade = ao * canopy

    if surface:
        # `sky` is the radiance of the sky itself; surfaces get a fraction of
        # it, and how much depends on how much sky they can still see — which
        # is none at all, down a hole.
        level = s.floor + (_rise(s, hz) if s.camp else 0.0)
        sky_occ = np.clip((hy - (level - 1.2)) / 1.5, 0.0, 1.0) ** 1.7
        sky_amt = (0.45 + 0.55 * ny) * sky_occ
        sun = np.clip(nx * -0.70 + ny * 0.34 + nz * -0.62, 0.0, 1.0)
        lit = albedo * s.sky * (0.85 * sky_amt + 0.70 * sun ** 1.6 * sky_occ) * shade
        # A headlamp switched on in daylight does not brighten the hillside;
        # it puts a pale coin on the ground in front of your boots. So the
        # day shortens the lamp's reach rather than dimming it.
        head = np.clip(-(dx * nx + dy * ny + dz * nz), 0.0, 1.0)
        reach = max(0.6, s.reach * (1.0 - 0.86 * s.day))
        lit = lit + albedo * head * light * 2.2 / (1.0 + (t / reach) ** 2 * 2.2)
        if camp is not None and s.lights:
            # The generator's string of lamps on stands. They make a hard
            # white room out of forty feet of hemlock and nothing at all out
            # of the rest of the ridge — which is the line in the prose, and
            # the reason the hole reads as a hole: nothing that goes down it
            # comes back lit. You stand in their light too, so your own
            # shadow goes out ahead of you.
            casters = camp.occ + [(ex, ez, 0.25, ey - 1.55, ey - 0.12),
                                  (ex, ez, 0.12, ey - 0.12, ey + 0.16)]
            occ_arr = tuple(np.array(c, dtype=F32) for c in zip(*casters))
            for lx, ly, lz, power, casts in camp.lamps:
                wx, wy, wz = lx - hx, ly - hy, lz - hz
                d2 = wx * wx + wy * wy + wz * wz
                d = np.sqrt(d2)
                ndl = np.clip((nx * wx + ny * wy + nz * wz) / d, 0.0, 1.0)
                fall = (s.lights * power / (1.0 + d2 * 0.045)
                        * np.clip((19.0 - d) / 7.0, 0.0, 1.0))
                j = np.flatnonzero((ndl * fall > 0.003) & hit)
                if j.size:
                    seen = _into_sink(s, hx[j], hy[j], hz[j],
                                      wx[j], wy[j], wz[j])
                    if casts:
                        seen = seen * _shadow(occ_arr, hx[j], hy[j], hz[j],
                                              wx[j], wy[j], wz[j])
                    lit[j] = lit[j] + albedo[j] * ao[j] * ndl[j] * fall[j] * seen
    else:
        reach = s.reach * (0.32 + 0.68 * light)
        diff = np.clip(-(dx * nx + dy * ny + dz * nz), 0.0, 1.0)
        if mat is not None:
            # a strand a couple of pixels wide catches the lamp all the way
            # across; shaded as a solid it was all dark edge, and broke up
            diff = np.where(mat == _M_ROPE, np.maximum(diff, 0.75), diff)
        cone = np.clip((near_axis - 0.60) / 0.36, 0.0, 1.0) ** 0.7
        cone = 0.20 + 0.80 * cone
        atten = 1.0 / (1.0 + (t / reach) ** 2 * 2.6)
        if s.kind == "crawl":
            # Rock a hand's width from the lamp takes it full in the face:
            # even at a glancing angle the nearest of it burns almost white.
            atten = atten * (1.0 + 0.5 / (t * t + 0.12))
        lit = albedo * (light * 1.95 * diff * cone * atten + 0.010 * light)
        # the few rooms with a light of their own: a lamp left burning, the
        # gray leaking in at the top of the workings
        for gx, gy, gz, power, _ in s.glow:
            wx, wy, wz = gx - hx, gy - hy, gz - hz
            d2 = wx * wx + wy * wy + wz * wz
            ndl = np.clip((nx * wx + ny * wy + nz * wz) / np.sqrt(d2), 0.0, 1.0)
            lit = lit + albedo * power * ndl / (1.0 + d2 * 0.5)
        if mat is not None:
            # a retroreflective tag sends the lamp straight back at you
            lit = np.where(mat == _M_GLINT, lit * 6.0 + 0.2 * light, lit)

    if s.water is not None:
        # Water is the one surface here that is not rock, so it gets a real
        # second march: mirror the ray in the plane and shade what it finds.
        on_water = (np.abs(hy - s.water) < 0.13) & hit & (dy < -0.02)
        if mat is not None:
            # only the water itself: not a salamander sitting on it, or the
            # rock where the wall goes in
            on_water &= mat == _M_WATER
        widx = np.flatnonzero(on_water)
        if widx.size:
            ox = hx[widx]
            oy = np.full(widx.size, s.water + 0.03, dtype=F32)
            oz = hz[widx]
            rdx, rdy, rdz = dx[widx], -dy[widx], dz[widx]
            if s.flow:
                # Running water is not a mirror: reflected off the ripples,
                # the lit walls come back broken into wobbling bands, which
                # is how you see from above that it is moving.
                wnx, wny, wnz = nx[widx], np.maximum(ny[widx], 0.5), nz[widx]
                ln_ = np.sqrt(wnx * wnx + wny * wny + wnz * wnz)
                wnx, wny, wnz = wnx / ln_, wny / ln_, wnz / ln_
                dn = dx[widx] * wnx + dy[widx] * wny + dz[widx] * wnz
                rdx = dx[widx] - 2.0 * dn * wnx
                rdy = np.maximum(dy[widx] - 2.0 * dn * wny, 0.02)
                rdz = dz[widx] - 2.0 * dn * wnz
            rt, rhit = _march(coarse, rdx, rdy, rdz, steps=26, tmax=18.0,
                              org=(ox, oy, oz),
                              **{k: v for k, v in mp.items()
                                 if k not in ("steps", "tmax", "org")})
            rpx, rpy, rpz = ox + rdx * rt, oy + rdy * rt, oz + rdz * rt
            rnx, rny, rnz = _normal(fine, rpx, rpy, rpz)
            rdiff = np.clip(-(rdx * rnx + rdy * rny + rdz * rnz), 0.0, 1.0)
            total = t[widx] + rt
            ratten = 1.0 / (1.0 + (total / (s.reach * (0.32 + 0.68 * light)))
                            ** 2 * 2.6)
            refl = 0.85 * light * rdiff * ratten * rhit
            # grazing angles reflect more, the way water does
            fres = 0.34 + 0.66 * (1.0 - np.clip(-dy[widx], 0.0, 1.0)) ** 2.5
            lit[widx] = lit[widx] * (0.06 if s.clear else 0.13) + refl * fres * (
                1.5 if s.clear else 1.0)
            if s.clear and hasattr(coarse, "dry"):
                # Clear water: the beam goes down into it, bent at the
                # surface, and shows the rock and whatever else is under.
                k = 1.0 / 1.33
                if s.flow:
                    # bent through the ripples, so the bed wavers
                    cosi = np.clip(-dn, 0.0, 1.0)
                    sin2 = k * k * (1.0 - cosi * cosi)
                    cost = np.sqrt(np.maximum(1.0 - sin2, 0.0))
                    bend = k * cosi - cost
                    ux, uy, uz = (dx[widx] * k + bend * wnx,
                                  dy[widx] * k + bend * wny,
                                  dz[widx] * k + bend * wnz)
                else:
                    cosi = np.clip(-dy[widx], 0.0, 1.0)
                    sin2 = k * k * (1.0 - cosi * cosi)
                    cost = np.sqrt(np.maximum(1.0 - sin2, 0.0))
                    ux, uy, uz = (dx[widx] * k, dy[widx] * k - (cost - k * cosi),
                                  dz[widx] * k)
                uy = np.minimum(uy, -0.05)
                ln_ = np.sqrt(ux * ux + uy * uy + uz * uz)
                ux, uy, uz = ux / ln_, uy / ln_, uz / ln_
                oy2 = np.full(widx.size, s.water - 0.03, dtype=F32)
                ut, uhit = _march(coarse.dry, ux, uy, uz, steps=48, tmax=12.0,
                                  org=(ox, oy2, oz), factor=0.75, eps=0.004)
                ux2, uy2, uz2 = ox + ux * ut, oy2 + uy * ut, oz + uz * ut
                unx, uny, unz = _normal(coarse.dry, ux2, uy2, uz2)
                udiff = np.clip(-(ux * unx + uy * uny + uz * unz), 0.0, 1.0)
                utot = t[widx] + ut
                uatt = 1.0 / (1.0 + (utot / (s.reach * (0.32 + 0.68 * light)))
                              ** 2 * 2.6)
                under = (0.9 * light * udiff * uatt * uhit
                         * np.exp(-ut / s.clear) * (0.30 + 0.52 * _fbm(
                             ux2 * 2.4, uy2 * 2.4, uz2 * 2.4, 2)))
                if s.flow:
                    # the ripples gather the lamp into a wavering net of
                    # bright lines on the bed: the sign of water running
                    net = 1.0 - np.abs(2.0 * _noise(ux2 * 5.0 + s.var, uy2,
                                                    uz2 * 2.6) - 1.0)
                    under = under * (0.55 + 1.6 * net ** 6)
                # (a hand's depth of running water hides almost nothing)
                lit[widx] = lit[widx] + under * (1.0 - fres) * (2.0 if s.flow else 0.7)
                if mat is not None:
                    umat = coarse.material(ux2, uy2, uz2)
                    tinted = np.isin(umat, list(_TINT)) & uhit
                    mat[widx] = np.where(tinted, umat, mat[widx])

    if surface:
        lit = np.where(hit, lit, s.sky * 1.9 + light * 0.03)
    else:
        lit = np.where(hit, lit, 0.0)
    if mat is not None:
        lit = np.where(mat == _M_LAMP, 3.0, lit)     # lamps, burning
        lit = np.where(mat == _M_DAWN, 1.3, lit)     # the gray, leaking in

    # scatter: haze between the trees, or dust hanging in the beam
    fade = np.exp(-t / s.fog)
    if s.kind == "forest":
        # Deep in a stand almost no ray reaches open sky, so the haze has to
        # carry the evening: distant trunks go pale into the glow the way
        # they do at dusk, and the near ones stand dark against it.
        haze = s.sky * (1.45 + 0.55 * np.clip(dy * 5.0 + 0.3, 0.0, 1.0))
        if s.camp:
            # no evening gets down the sink: the air in it is dark
            level = s.floor + _rise(s, hz)
            haze = haze * np.clip(1.0 + (hy - level) / 2.5, 0.0, 1.0)
        lit = lit * fade + (haze + light * 0.03) * (1.0 - fade)
        if camp is not None and s.lights:
            # The lamps light the air round them as well as the ground: the
            # damp under the hemlocks takes their glare and holds it. This
            # is the light scattered along each ray up to what it hit, which
            # has a closed form for a point lamp.
            # none of it lights the air down the hole: stop at the lip
            lip = s.floor + float(_rise(s, np.float32(_SINK[1]))) - 0.3
            t_air = np.where(hy < lip, np.minimum(
                t, (lip - ey) / np.minimum(dy, -1e-4)), t)
            t_air = np.maximum(t_air, 0.0)
            for lx, ly, lz, power, _ in camp.lamps:
                qx, qy, qz = lx - ex, ly - ey, lz - ez
                b = qx * dx + qy * dy + qz * dz
                hh = np.sqrt(np.maximum(qx * qx + qy * qy + qz * qz - b * b,
                                        0.0)) + 0.12
                glow = (np.arctan((t_air - b) / hh) + np.arctan(b / hh)) / hh
                lit = lit + s.lights * power * 0.010 * glow
    elif surface:
        lit = lit * fade + (s.sky * 1.25 + light * 0.03) * (1.0 - fade)
    else:
        lit = lit + 0.075 * light * fade * np.clip((near_axis - 0.52) / 0.48,
                                                   0.0, 1.0)
        for gx, gy, gz, power, _ in s.glow:
            # a light of its own lights the air round it, too
            gx, gy, gz = gx - ex, gy - ey, gz - ez
            b = gx * dx + gy * dy + gz * dz
            hh = np.sqrt(np.maximum(gx * gx + gy * gy + gz * gz - b * b, 0.0)) + 0.08
            lit = lit + power * 0.02 * (np.arctan((t - b) / hh)
                                        + np.arctan(b / hh)) / hh
        if s.murk:
            # Bad air pooled in the low places, the way water would. The
            # lamp shows it as a pale layer lying on the floor.
            level = s.floor + s.murk - ey
            t_in = np.where(dy < -1e-4, level / np.minimum(dy, -1e-4), np.inf)
            deep = np.clip(t - np.maximum(t_in, 0.0), 0.0, None)
            haze = 1.0 - np.exp(-deep / 1.4)
            glow = light * 0.5 / (1.0 + (np.maximum(t_in, 0.0) / 2.5) ** 2)
            lit = lit * (1.0 - 0.45 * haze) + haze * glow * _cone_of(near_axis)
        if s.kind == "under":
            # Underwater the beam is a thing in itself: silt hangs in it
            # and lights up all the way out to where it gives up.
            rch = s.reach * (0.32 + 0.68 * light)
            lit = lit + 0.14 * light * rch * np.arctan(t / rch) * \
                _cone_of(near_axis) ** 1.5
        if s.absorb:
            # Something the beam goes into and does not come out of. Not a
            # surface: wherever a ray passes through it, what lies behind
            # comes back as nothing. Three lumps of it, overlapping, none of
            # them a shape you could name — it is not quite all there.
            ax, ay, az, rx, ry, rz = s.absorb
            chord = np.zeros_like(t)
            for (fx, fy, fz, fr) in ((0.0, 0.0, 0.0, 1.0), (0.55, 0.25, 0.3, 0.7),
                                     (-0.5, -0.2, -0.2, 0.75)):
                cx, cy, cz = ax + fx * rx, ay + fy * ry, az + fz * rz
                ox, oy, oz = ((ex - cx) / (rx * fr), (ey - cy) / (ry * fr),
                              (ez - cz) / (rz * fr))
                ux, uy, uz = dx / (rx * fr), dy / (ry * fr), dz / (rz * fr)
                qa = ux * ux + uy * uy + uz * uz
                qb = ox * ux + oy * uy + oz * uz
                qc = ox * ox + oy * oy + oz * oz - 1.0
                disc = np.maximum(qb * qb - qa * qc, 0.0)
                t0 = np.clip((-qb - np.sqrt(disc)) / qa, 0.0, t)
                t1 = np.clip((-qb + np.sqrt(disc)) / qa, 0.0, t)
                chord = np.maximum(chord, np.where(qb * qb - qa * qc > 0.0,
                                                   t1 - t0, 0.0))
            uneven = 0.2 + 1.2 * _fbm(dx * 7.0 + 3.0, dy * 7.0, dz * 7.0, 2)
            lit = lit * np.exp(-(chord * uneven) ** 2 * 0.7)

    lit = lit.reshape(h, w)
    if s.exposure:
        # You have been standing over it long enough for your eyes to open
        # up: the same dusk, but you can see into it now.
        lit = lit * s.exposure

    vy, vx = np.mgrid[0:h, 0:w].astype(F32)
    r2 = (((vx / w) - 0.5) * 2.0) ** 2 + (((vy / h) - 0.5) * 2.0) ** 2
    lit = lit * np.clip(1.14 - 0.36 * r2, 0.0, 1.2)

    lit = lit / (1.0 + lit * 0.85)
    lit = np.clip(lit * 1.15, 0.0, 1.0) ** 0.82
    gr = np.random.default_rng(int(s.var * 977) + int(light * 40)).normal(
        0.0, 1.0, lit.shape).astype(F32)
    lit = np.clip(lit + gr * (0.014 + 0.048 * (1.0 - lit)), 0.0, 1.0)

    idx = (lit * 255.0).astype(np.uint8)
    rgb = _lut(s.palette)[idx]
    if mat is not None:
        m = mat.reshape(h, w)
        for code, colour in _TINT.items():
            k = m == code
            if k.any():
                c = np.array(colour, dtype=F32)
                rgb[k] = (rgb[k] * 0.2 + c * np.clip(
                    0.25 + 1.1 * lit[k], 0.0, 1.0)[:, None] * 0.8)
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")


# --------------------------------------------------------------------------
#  THE PLACES — one Scene per room. Data, like content.py.
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
#  what is in the rooms — each built once, and kept as data on its Scene
# --------------------------------------------------------------------------

def _cairn(x, z, fl, k=1.35):
    """Four stones off the cobble floor, stacked knee-high — the top one
    still pale where it was lifted."""
    def stone(mat, dx, y, dz, half, r, **turn):
        return _box(mat, (x + dx * k, fl + y * k, z + dz * k),
                    tuple(h * k for h in half), r * k, **turn)
    return (stone(_M_ROCK, 0.0, 0.08, 0.0, (0.22, 0.09, 0.17), 0.07, yaw=20),
            stone(_M_ROCK, 0.02, 0.24, 0.0, (0.16, 0.07, 0.13), 0.06,
                  yaw=-15, roll=5),
            stone(_M_ROCK, -0.01, 0.36, 0.01, (0.12, 0.06, 0.10), 0.05,
                  yaw=40, pitch=-6),
            stone(_M_PALE, 0.0, 0.46, 0.0, (0.08, 0.05, 0.07), 0.04, yaw=10))


def _cache(x, z, fl, seed, yaw, pitch=3.0, roll=-4.0, twist=0.0):
    """A red forty-litre pack, set down upright against a block that came
    down out of the breakdown, closed — the way you leave a pack you are
    coming straight back to — and what broke off the block round its foot.

    The block is whatever `seed` breaks it into, turned `yaw`; the pack
    stands at `x`, `z` with its back to the face of it there, leaning on
    that face at the face's own angle."""
    block = _Rock((0.85, 0.42, 0.6), seed, yaw=yaw, pitch=pitch, roll=roll, chips=4)
    block.put(x + 0.15, fl - block.local[:, 1].min() - 0.07, z + 0.9)
    # the face the pack leans on: where a line from in front, at the height
    # its back rests, first goes into the block
    p0 = np.array([x, fl + 0.42, z - 2.0])
    offs = block.offsets + block.normals @ block.at
    facing = block.normals[:, 2] < -1e-6
    t = (offs[facing] - block.normals[facing] @ p0) / block.normals[facing][:, 2]
    k = int(np.argmax(t))
    hit, n = p0 + np.array([0.0, 0.0, t[k]]), block.normals[facing][k]
    turn = math.degrees(math.atan2(-n[0], -n[2])) + twist
    lean = float(np.clip(math.degrees(math.asin(n[1])), 9.0, 15.0))
    R = _rot(turn, lean)
    # its own frame: x across it, y up from the ground, +z the back panel
    back = np.array([0.0, 0.4, 0.12])
    base = hit - R @ back
    base[1] = fl - 0.01

    def at(p):
        return tuple(float(q) for q in base + R @ np.array(p, float))

    def bag(c, half, r):
        return _box(_M_RED, at(c), half, r, yaw=turn, pitch=lean)

    def strap(a, b, r=0.01, mat=_M_TYRE):
        return _cap(mat, at(a), at(b), r)

    def flat(a, b, r=0.009, mat=_M_TYRE):
        """A strap's tail lying on the floor, whatever the pack leans."""
        a, b = at(a), at(b)
        return _cap(mat, (a[0], fl + r, a[2]), (b[0], fl + r, b[2]), r)

    pack = [bag((0.0, 0.27, 0.0), (0.16, 0.26, 0.115), 0.075),
            # the lid, stuffed round and hanging over the front a little
            bag((0.0, 0.575, -0.015), (0.165, 0.06, 0.13), 0.05),
            bag((0.0, 0.22, -0.123), (0.12, 0.13, 0.03), 0.03)]
    for sx in (-1.0, 1.0):
        pack += [# a stretch pocket low on each side, and the straps that
                 # cinch the load
                 bag((0.162 * sx, 0.13, 0.0), (0.03, 0.1, 0.085), 0.03),
                 strap((0.075 * sx, 0.6, -0.148), (0.075 * sx, 0.33, -0.162), 0.014),
                 strap((0.166 * sx, 0.3, -0.1), (0.166 * sx, 0.31, 0.1), 0.012),
                 strap((0.162 * sx, 0.45, -0.095), (0.162 * sx, 0.46, 0.095), 0.012),
                 # the shoulder straps, against the rock
                 strap((0.07 * sx, 0.52, 0.12), (0.13 * sx, 0.32, 0.15), 0.022),
                 strap((0.13 * sx, 0.32, 0.15), (0.15 * sx, 0.12, 0.125), 0.022),
                 # the hip belt, undone, its wings fallen forward and the
                 # webbing lying out on the floor off the ends of them
                 strap((0.13 * sx, 0.08, 0.1), (0.22 * sx, 0.05, -0.01), 0.035),
                 flat((0.25 * sx, 0.0, -0.03), (0.3 * sx, 0.0, -0.2))]

    # what broke off the block when it came down, lying round the foot of it
    rng = np.random.default_rng(seed + 1)
    feet = block.corners()
    feet = feet[np.argsort(feet[:, 1])[:5]]
    spall = []
    for fx, _, fz in feet:
        a, c = rng.uniform(0.07, 0.22, 2)
        chip = _Rock((a, max(a, c) * rng.uniform(0.4, 0.8), c),
                     int(rng.integers(1 << 30)), yaw=rng.uniform(0.0, 180.0),
                     pitch=rng.normal(0.0, 12.0), roll=rng.normal(0.0, 12.0),
                     chips=2)
        cx, cz = fx + rng.normal(0.0, 0.25), fz + rng.normal(0.0, 0.25) - 0.1
        if math.hypot(cx - base[0], cz - base[2]) < 0.45:
            continue
        spall.append(chip.put(cx, fl - chip.local[:, 1].min() - 0.02, cz).data())
    return (block.data(),), tuple(pack), tuple(spall)


def _strew(seed, fl, cz, wall, count, keep):
    """Spall across a chamber's floor: what has come off the roof one piece
    at a time since the room was a room, most of it small, the bigger
    pieces out toward the walls where nothing has kicked them aside. Kept
    `keep` = ((x, z, radius), ...) clear — where you are, what is set down."""
    rng = np.random.default_rng(seed)
    lots = {}
    for _ in range(count * 30):
        if sum(map(len, lots.values())) == count:
            break
        e = math.sqrt(rng.uniform(0.02, 1.0)) * 0.86
        a = rng.uniform(0.0, 2.0 * math.pi)
        x, z = wall * e * math.sin(a), cz + wall * e * math.cos(a)
        if any(math.hypot(x - kx, z - kz) < kr for kx, kz, kr in keep):
            continue
        big = 0.05 + 0.3 * rng.random() ** 2.5 * (0.4 + e)
        long = rng.uniform(1.0, 1.8)
        half = (big * long, big * rng.uniform(0.25, 0.55), big / long)
        rock = _Rock(half, int(rng.integers(1 << 30)), yaw=rng.uniform(0.0, 180.0),
                     pitch=rng.normal(0.0, 12.0), roll=rng.normal(0.0, 12.0),
                     chips=3 if big < 0.15 else 5)
        rock.put(x, fl - rock.local[:, 1].min() - half[1] * rng.uniform(0.1, 0.4), z)
        lots.setdefault((int(x // 1.6), int(z // 1.6)), []).append(rock.data())
    return tuple(tuple(lot) for _, lot in sorted(lots.items()))


def _lips(bearing, wall, cz, fl, tall, high, half):
    """Fresh scuffing on both lips of a slot out of a dome, `high` over
    the floor: where the rock is rubbed pale by a body going through."""
    sx, sz = math.sin(math.radians(bearing)), math.cos(math.radians(bearing))
    out = wall * math.sqrt(1.0 - (high / tall) ** 2)
    return tuple(("scuff", out * sx + side * half * sz, fl + high,
                  cz + out * sz - side * half * sx, 0.3, 0.9)
                 for side in (-1.0, 1.0))


def _rope(x, z, top, fl):
    """The rope hanging free out of the hole in the roof, and the tail of it
    lying in loose coils where it reached the floor."""
    hang = (_cap(_M_ROPE, (x, top, z), (x + 0.03, fl + 0.06, z + 0.02), 0.02),)
    coils = []
    for k, (cx, cz, r) in enumerate(((0.12, 0.25, 0.28), (0.2, 0.3, 0.24),
                                     (0.05, 0.36, 0.3))):
        pts = [(x + cx + r * math.cos(a), fl + 0.03 + 0.02 * k,
                z + cz + r * 0.8 * math.sin(a))
               for a in np.linspace(0.3 * k, 0.3 * k + 2 * math.pi, 9)]
        coils += [_cap(_M_ROPE, pts[i], pts[i + 1], 0.017) for i in range(8)]
    return hang, tuple(coils)


def _tag(x, y, z, yaw, mat=_M_TAG):
    """A small plate hammered into the rock — a survey station, a
    reflector. Deep enough to stand proud of any lump in the wall."""
    return _box(mat, (x, y, z), (0.07, 0.022, 0.034), 0.003, yaw=yaw)


def _rift_wall(s, y, z, side):
    """Where a rift's wall is, at height `y` and distance `z`, on `side`."""
    v = s.var
    xc = s.bend * (math.sin(z * 0.35 + v) + 0.35 * math.sin(z * 0.9 + v * 2))
    rel = min(max((y - s.floor) / (s.ceil - s.floor), 0.0), 1.0)
    return xc + side * (s.rx + (s.ry - s.rx) * rel) * 0.5


def _rungs(x, wall, y0, n, gap):
    """Iron staples driven into the wall ahead, one above the next, each its
    own little cluster: two legs into the rock and a bar to stand on."""
    out = []
    for k in range(n):
        y = y0 + k * gap
        bar = wall - 0.14
        out.append((_cap(_M_IRON, (x - 0.18, y, bar), (x + 0.18, y, bar), 0.017),
                    _cap(_M_IRON, (x - 0.18, y, bar), (x - 0.18, y, wall + 0.3), 0.014),
                    _cap(_M_IRON, (x + 0.18, y, bar), (x + 0.18, y, wall + 0.3),
                         0.014)))
    return tuple(out)


def _sets(fl, slope, half, tall, zs):
    """Square-set timber: two posts and a cap, adzed, every so often."""
    out = []
    for z in zs:
        b = fl + slope * z
        out.append((_box(_M_TIMBER, (-half + 0.11, b + tall / 2, z),
                         (0.1, tall / 2, 0.1), 0.02, roll=2),
                    _box(_M_TIMBER, (half - 0.11, b + tall / 2, z),
                         (0.1, tall / 2, 0.1), 0.02, roll=-2),
                    _box(_M_TIMBER, (0.0, b + tall - 0.1, z),
                         (half, 0.1, 0.11), 0.02)))
    return tuple(out)


def _track(fl, slope, z0, z1):
    """A rail each side and the sleepers under them."""
    rails = tuple(_cap(_M_IRON, (x, fl + slope * z0 + 0.06, z0),
                       (x, fl + slope * z1 + 0.06, z1), 0.025) for x in (-0.3, 0.3))
    sleepers = []
    for g in np.arange(z0, z1, 3.0):
        sleepers.append(tuple(_box(_M_TIMBER, (0.0, fl + slope * z + 0.02, z),
                                   (0.45, 0.03, 0.07), 0.01)
                              for z in np.arange(g, min(g + 3.0, z1), 0.6)))
    return (rails,) + tuple(sleepers)


def _left_behind(x, z, fl):
    """Her oversuit folded on the silt, and her helmet on top of it with the
    lamp still burning, turned a little toward you."""
    return (_box(_M_CLOTH, (x, fl + 0.07, z), (0.27, 0.07, 0.2), 0.05, yaw=8),
            _box(_M_CLOTH, (x - 0.02, fl + 0.155, z + 0.02), (0.22, 0.03, 0.16),
                 0.03, yaw=14),
            _cap(_M_SUIT, (x, fl + 0.3, z), (x, fl + 0.3, z), 0.14),
            _box(_M_LAMP, (x - 0.03, fl + 0.34, z - 0.135), (0.035, 0.026, 0.012),
                 0.01, yaw=-15))


def _sitting(x, z, fl):
    """Upright against the wall with her knees drawn up, facing the way
    you came in."""
    sh = fl + 0.78
    out = [_box(_M_CLOTH, (x, fl + 0.5, z), (0.19, 0.3, 0.11), 0.09, pitch=-10),
           _cap(_M_PALE, (x, fl + 0.96, z - 0.03), (x, fl + 0.96, z - 0.03), 0.1)]
    for side in (-1.0, 1.0):
        hip, knee = (x + side * 0.1, fl + 0.16, z), (x + side * 0.11, fl + 0.55, z - 0.4)
        foot = (x + side * 0.1, fl + 0.06, z - 0.58)
        out += [_cap(_M_CLOTH, hip, knee, 0.075), _cap(_M_CLOTH, knee, foot, 0.06),
                _cap(_M_CLOTH, (x + side * 0.2, sh, z), (x + side * 0.08, fl + 0.5,
                                                         z - 0.38), 0.05)]
    return tuple(out)


def _flood_ledge(s, z0, z1, y, side):
    """The flood line's shelf: old debris packed into it — twigs, a shred of
    blue tarp, a bone you decide is a deer's."""
    out = []
    for z in np.arange(z0, z1, 0.5):
        w = _rift_wall(s, y, z, side)
        out.append(_box(_M_ROCK, (w - side * 0.08, y, z + 0.25), (0.1, 0.035, 0.27),
                        0.02))
    zm = (z0 + z1) / 2
    w = _rift_wall(s, y, zm, side) - side * 0.12
    out += [_cap(_M_TIMBER, (w, y + 0.05, zm - 0.4), (w - side * 0.05, y + 0.07,
                                                     zm + 0.1), 0.012),
            _cap(_M_TIMBER, (w + side * 0.02, y + 0.05, zm - 0.1),
                 (w - side * 0.03, y + 0.09, zm + 0.45), 0.01),
            _box(_M_BLUE, (w, y + 0.06, zm + 0.55), (0.06, 0.012, 0.09), 0.01,
                 yaw=30, roll=10),
            _cap(_M_PALE, (w - side * 0.02, y + 0.055, zm - 0.7),
                 (w - side * 0.03, y + 0.06, zm - 0.35), 0.018)]
    return tuple(out)


def _salamander(x, y, z, heading=0.0):
    """A salamander no longer than your finger, holding still, its head
    `heading` degrees right of straight away from you."""
    c, sn = math.cos(math.radians(heading)), math.sin(math.radians(heading))

    def at(u, w):
        """u along its body, toward the tail; w across it."""
        return (x - u * sn + w * c, y, z - u * c - w * sn)
    return (_cap(_M_PALE, at(0.0, 0.0), at(0.05, 0.01), 0.008),
            _cap(_M_PALE, at(0.05, 0.01), at(0.1, 0.03), 0.004),
            _cap(_M_PALE, at(-0.004, -0.003), at(-0.018, -0.006), 0.006))


def _dive_line(x, z, water):
    """Blue polypropylene knotted to a rock thread on the wall at the
    water's edge, going into the water and down."""
    y = water + 0.16
    thread = [(x, y + 0.12 * math.sin(a), z + 0.12 * math.cos(a))
              for a in np.linspace(0.0, math.pi, 6)]
    out = [_cap(_M_ROCK, thread[i], thread[i + 1], 0.05) for i in range(5)]
    line = [(x - 0.05, y + 0.1, z), (x - 0.3, water - 0.05, z + 0.5),
            (x - 0.6, water - 1.0, z + 2.0), (x - 0.8, water - 2.4, z + 4.0)]
    out += [_cap(_M_BLUE, line[i], line[i + 1], 0.014) for i in range(3)]
    return tuple(out)


def _flagged_hole(x, z, fl):
    """A projection at the far end with orange tape tied round it."""
    return (_box(_M_ROCK, (x, fl + 0.55, z), (0.14, 0.3, 0.12), 0.06, yaw=15),
            _box(_M_FLAG, (x, fl + 0.72, z), (0.16, 0.025, 0.14), 0.01, yaw=15),
            _box(_M_FLAG, (x + 0.12, fl + 0.55, z - 0.11), (0.012, 0.16, 0.004),
                 0.002, yaw=15, roll=6))


_RUBBLE = 0.45    # how high a `rubble` floor heaps, at the most


def _pile(seed, fl, ceil, wall, z0, z1, gap, bend, v, freq, slabs=12,
          blocks=18, spall=30, open_to=3.0, slope=0.0, size=1.0,
          eyes=((0.0, 0.0, 0.0),), clear=1.6, sides=False):
    """A collapse: the beds of one roof, come down all at once, and what
    broke off them when they hit.

    The slabs came first and lie tilted where they landed, half sunk in
    their own rubble; the blocks came down on top of them and lie on
    whatever they hit; the spall is heaped round the bottoms of both.
    Each rock is dropped onto what is already there — the heaped floor
    as the room draws it (`rubble`, at the room's `freq` and `var`), or a
    rock that landed first — so they rest on one another rather than
    float. Nothing comes within `clear` of any of the `eyes` the room is
    seen from, and up to `open_to` there is a way through, because
    finding one is why you are here.

    On a `slope` — a choke climbing through the hill — the floor and roof
    climb with it and every rock lies tilted with the hill; `size` scales
    the slabs and blocks to a narrower passage, and `sides` drops them off
    to one side of the way or the other: in a passage that narrow, one
    dropped anywhere across it nearly always blocks it and is thrown out.
    """
    rng = np.random.default_rng(seed)
    placed = []
    lean = -math.degrees(math.atan(slope))

    def route(z):
        return bend * np.sin(z * 0.3 + v)

    def ground(x, z):
        """The heaped floor under each of the points (x, z)."""
        x, z = np.atleast_1d(x), np.atleast_1d(z)
        base = fl + slope * np.maximum(z, 0.0)
        return base + _RUBBLE * _noise(x * freq + v, base * freq, z * freq)

    def fits(rock):
        pts = rock.corners()
        roof = ceil + slope * np.maximum(pts[:, 2], 0.0)
        if (np.any(pts[:, 1] > roof - 0.25)
                or min(rock.clear_of(*e) for e in eyes) < clear):
            return False
        if pts[:, 2].min() > open_to:
            return True
        off = pts[:, 0] - route(pts[:, 2])
        # convex, so a rock with corners on both sides spans the way
        return (np.all(off > gap) or np.all(off < -gap)
                or pts[:, 1].max() < ground(rock.at[0], rock.at[2])[0] + 0.25)

    def drop(rock, x, z, sink):
        """Let it down until a corner meets the floor or a rock already
        there, then sink it a little into whatever that was."""
        cx, cy, cz = rock.local.T
        under = ground(x + cx, z + cz)
        for r in placed:
            if math.hypot(r.at[0] - x, r.at[2] - z) < r.reach + rock.reach:
                under = np.maximum(under, r.top(x + cx, z + cz))
        return rock.put(x, float(np.max(under - cy)) - sink, z)

    def tilt(most):
        return float(np.clip(rng.normal(0.0, most * 0.5), -most, most))

    def settle(half, seed, turn, chips, x, z, sink, draft=None):
        """The rock, set down at (x, z), or None if it will not go there.
        With `sides`, it is tried first without its chips — they only
        ever make a rock smaller — and cut only once it fits, since most
        tries in a narrow choke do not."""
        if sides:
            first = drop(draft or _Rock(half, seed, chips=0, **turn), x, z, sink)
            if not fits(first):
                return None
        rock = drop(_Rock(half, seed, chips=chips, **turn), x, z, sink)
        return rock if fits(rock) else None

    for kind, count, (lo, hi), (f0, f1), most, bury in (
            ("slab", slabs, (0.9, 2.0), (0.2, 0.34), 26.0, (0.2, 0.5)),
            ("block", blocks, (0.4, 1.0), (0.45, 0.85), 38.0, (0.03, 0.15))):
        made = 0
        for _ in range(count * 40):
            if made == count:
                break
            a, c = rng.uniform(lo, hi, 2) * size
            b = max(a, c) * rng.uniform(f0, f1)
            seed_ = int(rng.integers(1 << 30))
            turn = dict(yaw=rng.uniform(0.0, 180.0), pitch=tilt(most),
                        roll=tilt(most), lean=lean)
            chips = int(rng.integers(3, 7))
            z = rng.uniform(z0, z1)
            draft = None
            if sides:
                # its near edge clear of the way, on one side of it; the
                # far side of a big one goes into the wall, the way a
                # choke's walls are its own blocks
                draft = _Rock((a, b, c), seed_, chips=0, **turn)
                side = 1.0 if rng.random() < 0.5 else -1.0
                x = route(z) + side * (gap + draft.reach * rng.uniform(1.0, 1.25))
            else:
                x = route(z) + rng.uniform(-wall, wall)
            rock = settle((a, b, c), seed_, turn, chips, x, z,
                          b * rng.uniform(*bury), draft)
            if rock is None:
                continue
            placed.append(rock)
            made += 1

    # the spall, heaped round the feet of what came down, and a scatter of
    # it down the line you walk, where nobody has cleared it
    heap = []
    for n in range(spall * 40):
        if len(heap) == spall:
            break
        if n % 3 == 0:
            fz = rng.uniform(1.2, z1)
            fx = route(fz) + rng.normal(0.0, gap)
        else:
            base = placed[int(rng.integers(len(placed)))].corners()
            foot = base[np.argsort(base[:, 1])[:4]]
            fx, _, fz = foot[int(rng.integers(len(foot)))]
        a, c = rng.uniform(0.1, 0.3, 2)
        half = (a, max(a, c) * rng.uniform(0.4, 0.9), c)
        seed_ = int(rng.integers(1 << 30))
        turn = dict(yaw=rng.uniform(0.0, 180.0), pitch=tilt(40.0),
                    roll=tilt(40.0), lean=lean)
        rock = settle(half, seed_, turn, 2, fx + rng.normal(0.0, 0.3),
                      fz + rng.normal(0.0, 0.3), 0.03)
        if rock is not None:
            heap.append(rock)
    # Clustered by where they lie, a few metres of pile to a cluster: a ray
    # far from one pays a single distance for it, and one close by measures
    # all of its rocks in one product.
    lots = {}
    for r in placed + heap:
        side = r.at[0] > route(r.at[2])
        lots.setdefault((int(r.at[2] // 2.0), side), []).append(r.data())
    return tuple(tuple(lot) for _, lot in sorted(lots.items()))


def _buttress(x, z, fl, half, seed, yaw):
    """A standing mass of jointed limestone, floor to roof, where a chamber
    forks round it: flat faces and hard edges, the way rock the water has
    not smoothed stands."""
    rock = _Rock(half, seed, yaw=yaw, pitch=2.0, roll=-3.0, chips=5)
    return (rock.put(x, fl - rock.local[:, 1].min() - 0.6, z).data(),)


def _marked_block(x, z, fl, half, seed, yaw, high, eye=(0.0, 0.0, 0.0)):
    """A broken block set down on the floor, and a reflective tag driven
    into the face of it you can see from `eye`, `high` above the floor."""
    rock = _Rock(half, seed, yaw=yaw, pitch=4.0, roll=-3.0, chips=4)
    rock.put(x, fl - rock.local[:, 1].min() - 0.08, z)
    # where the line from your eye to the block's middle, at tag height,
    # goes into it: the face it meets there is the one that faces you
    p0 = np.array([eye[0], fl + high, eye[2]])
    ray = np.array([x, fl + high, z]) - p0
    ray /= np.linalg.norm(ray)
    offs = rock.offsets + rock.normals @ rock.at
    facing = rock.normals @ ray < -1e-6
    t = (offs[facing] - rock.normals[facing] @ p0) / (rock.normals[facing] @ ray)
    k = int(np.argmax(t))
    hit = p0 + ray * t[k]
    n = rock.normals[facing][k]
    return (rock.data(), _tag(*hit, math.degrees(math.atan2(n[0], n[2])), _M_GLINT))


# --------------------------------------------------------------------------
#  the homestead in Sander's Hollow — what you go over and look at there
# --------------------------------------------------------------------------
#
# Each is its own picture, from where you would stand to look at it, set
# into the hollow's woods. Laid in the scene's own frame: you at the origin,
# facing +z, the ground rising `rise` a metre past four metres out.

def _hill(fl, rise, z):
    """The hollow's ground at `z`, before its lumps."""
    return fl + rise * max(z - 4.0, 0.0)


def _fieldstone(rng, x, y, z, size, mat=_M_FIELD):
    """One stone picked off a field: rounded by the weather, longer than it
    is wide and flatter than either, lying however it came to rest. Grayed
    with lichen, like all the stone here: paler than the leaf litter, which
    is how you see any of it at dusk."""
    half = (size * rng.uniform(1.0, 1.6), size * rng.uniform(0.45, 0.7),
            size * rng.uniform(0.7, 1.05))
    return _box(mat, (x, y + half[1] * 0.6, z), half, size * 0.4,
                yaw=rng.uniform(0.0, 180.0), pitch=rng.normal(0.0, 8.0),
                roll=rng.normal(0.0, 8.0))


def _chimney_fall(fl, rise, seed):
    """The chimney, from where the house stood in front of its hearth: the
    firebox still standing, the dressed lintel over it, and the rest of the
    stack come down across the leaf litter beside it. Two courses of the
    foundation run back past you on either side, under the leaves."""
    rng = np.random.default_rng(seed)
    cx, front = 0.25, 3.7
    g = _hill(fl, rise, front + 0.5)

    def mass(x, y0, y1, hx, z=front + 0.5, hz=0.5, r=0.05):
        return _box(_M_FIELD, (x, g + (y0 + y1) / 2, z), (hx, (y1 - y0) / 2, hz), r)

    stack = (mass(cx - 0.76, 0.0, 0.74, 0.26),          # the jambs
             mass(cx + 0.76, 0.0, 0.74, 0.26),
             mass(cx, 0.0, 0.72, 0.5, z=front + 0.84, hz=0.13),   # fireback
             mass(cx, 0.98, 1.7, 1.02),                  # the breast over it
             mass(cx - 0.45, 1.7, 2.15, 0.57, hz=0.44),  # and what is left
             mass(cx + 0.5, 1.7, 1.88, 0.47, hz=0.42),   # of the stack, broken
             _box(_M_DRESSED, (cx, g + 0.86, front + 0.14), (0.72, 0.12, 0.16),
                  0.012),                                # the lintel
             _box(_M_FIELD, (cx, g + 0.02, front - 0.24), (0.66, 0.04, 0.26),
                  0.02, yaw=2.0))                        # the hearthstone
    # the broken top: stones left sitting loose on it
    top = [_fieldstone(rng, cx + rng.uniform(-0.9, 0.8), g + 2.15 - (
        0.27 if i % 2 else 0.0), front + rng.uniform(0.2, 0.8),
        rng.uniform(0.1, 0.16)) for i in range(5)]
    # The rest of the stack came down to the right, away from the house:
    # most of it in a heap against what still stands, the rest thrown out
    # along the line it fell.
    heap, tail = [], []
    hx, hz = cx + 1.55, front + 0.8
    for _ in range(44):
        u = rng.random() ** 1.7
        ang = rng.normal(0.3, 0.45)
        x = hx + u * 3.0 * math.cos(ang)
        z = hz + u * 3.0 * math.sin(ang)
        up = 0.55 * math.exp(-(u * 3.0 / 0.95) ** 2) * rng.uniform(0.25, 1.0)
        stone = _fieldstone(rng, x, _hill(fl, rise, z) - 0.04 + up, z,
                            rng.uniform(0.12, 0.22) * (1.0 - 0.35 * u))
        (heap if u < 0.35 else tail).append(stone)
    # the foundation, a rectangle of stone under the leaf litter
    walls = []
    for side, x in ((-1, -2.3), (1, 2.9)):
        run = []
        for z in np.arange(0.9, front, 0.42):
            run.append(_fieldstone(rng, x + rng.normal(0.0, 0.06),
                                   _hill(fl, rise, z) - 0.09, z + rng.normal(0.0, 0.05),
                                   rng.uniform(0.13, 0.18)))
        walls.append(tuple(run))
    return (stack + tuple(top), tuple(heap), tuple(tail)) + tuple(walls)


def _springhouse(fl, rise, seed):
    """The springhouse fallen in on itself over the spring; the run out of
    it, eight feet of cold water; and where the water goes back into the
    ground, a course of the same fieldstone laid over the hole, mortared,
    long after the house went."""
    rng = np.random.default_rng(seed)
    sx, sz, half, th = 0.9, 5.7, 1.2, 0.18
    g = _hill(fl, rise, sz)
    walls = []
    # each wall stands to its own height where it has not come down, and the
    # front one is gone to the ground where the water comes out
    for (x0, z0, x1, z1), tops in (
            ((-half, -half, -0.45, -half), (0.7, 0.45)),
            ((0.05, -half, half, -half), (0.35, 0.9)),
            ((-half, half, half, half), (1.1, 0.8, 1.05)),
            ((-half, -half, -half, half), (0.95, 0.5, 0.75)),
            ((half, -half, half, half), (0.85, 1.1, 0.6))):
        n = len(tops)
        for k, top in enumerate(tops):
            a0, a1 = k / n, (k + 1) / n
            xa, xb = x0 + (x1 - x0) * a0, x0 + (x1 - x0) * a1
            za, zb = z0 + (z1 - z0) * a0, z0 + (z1 - z0) * a1
            hx = max(abs(xb - xa) / 2, th)
            hz = max(abs(zb - za) / 2, th)
            walls.append(_box(_M_FIELD, (sx + (xa + xb) / 2, g + top / 2 - 0.05,
                                        sz + (za + zb) / 2),
                              (hx, top / 2, hz), 0.05))
    # what came down, inside and out
    rubble = [_fieldstone(rng, sx + rng.uniform(-1.6, 1.6), g - 0.04,
                          sz + rng.uniform(-1.6, 1.6), rng.uniform(0.1, 0.2))
              for _ in range(16)]
    # the run: out through the gap in the front wall and down to the hole,
    # wandering the way a trickle does between the roots
    run = [(sx - 0.2, sz - half + 0.1), (sx - 0.34, sz - half - 0.45),
           (sx - 0.62, sz - half - 0.9), (sx - 0.78, sz - half - 1.35),
           (sx - 1.08, sz - half - 1.85), (sx - 1.3, sz - half - 2.35)]
    water = []
    for (ax, az), (bx, bz) in zip(run, run[1:]):
        mx, mz = (ax + bx) / 2, (az + bz) / 2
        yaw = math.degrees(math.atan2(bx - ax, bz - az))
        water.append(_box(_M_WATER, (mx, _hill(fl, rise, mz) + 0.035, mz),
                          (0.11, 0.01, math.hypot(bx - ax, bz - az) / 2 + 0.06),
                          0.01, yaw=yaw))
    (px_, pz_), (ex, ez) = run[-2], run[-1]
    eg = _hill(fl, rise, ez)
    # where it stands against the course before it finds its way through
    water.append(_box(_M_WATER, (ex, eg + 0.035, ez), (0.24, 0.01, 0.17),
                      0.1, yaw=math.degrees(math.atan2(ex - px_, ez - pz_))))
    # a few stones along the banks, where it has washed the soil off them
    bank = []
    for (ax, az), (bx, bz) in zip(run, run[1:]):
        t = math.atan2(bx - ax, bz - az)
        side = 1.0 if rng.random() < 0.5 else -1.0
        x, z = (ax + bx) / 2, (az + bz) / 2
        bank.append(_fieldstone(rng, x + side * 0.3 * math.cos(t),
                                _hill(fl, rise, z) - 0.03,
                                z - side * 0.3 * math.sin(t), rng.uniform(0.07, 0.1)))
    # The course over the hole: the same stone, set level across the end
    # of the run in a bed of lime mortar, pale in every joint.
    dx, dz = ex - px_, ez - pz_
    n = math.hypot(dx, dz)
    dx, dz = dx / n, dz / n
    qx, qz = dz, -dx                              # across the run
    turn = math.degrees(math.atan2(-qz, qx))
    cx_, cz_ = ex + dx * 0.34, ez + dz * 0.34
    course = [_box(_M_MORTAR, (cx_, eg + 0.05, cz_), (0.56, 0.06, 0.08), 0.02,
                   yaw=turn)]
    for k in range(5):
        s_ = (k - 2) * 0.23
        course.append(_box(_M_FIELD, (cx_ + qx * s_ - dx * 0.02 * s_ * s_,
                                      eg + 0.1 + 0.015 * rng.random(),
                                      cz_ + qz * s_ - dz * 0.02 * s_ * s_),
                           (0.1, 0.07, 0.11), 0.04,
                           yaw=turn + rng.normal(0.0, 4.0)))
    return (tuple(walls[:6]), tuple(walls[6:]), tuple(rubble), tuple(water),
            tuple(bank), tuple(course))


def _chimney_marks(fl, rise):
    """The laid stone of the chimney, and the two dates on its lintel: 1889
    cut properly with a chisel, and under it 1911, scratched shallow and
    small in a different hand."""
    cx, front = 0.25, 3.7
    g = _hill(fl, rise, front + 0.5)
    face = front - 0.02
    return (("stones", cx - 1.1, cx + 1.1, g, g + 0.74, front - 0.1, front + 1.1, 0.55),
            ("stones", cx - 1.1, cx + 1.1, g + 0.98, g + 2.3, front - 0.1,
             front + 1.1, 0.55),
            ("text", "1889", cx - 0.17, g + 0.865, face, 0.085, 0.0, 0.85, 0.04),
            ("text", "1911", cx - 0.09, g + 0.775, face, 0.058, 0.0, 0.45, 0.04))


def _springhouse_marks(fl, rise):
    """Its walls laid dry, and the course over the hole mortared."""
    sx, sz, half = 0.9, 5.7, 1.2
    g = _hill(fl, rise, sz)
    return (("stones", sx - half - 0.3, sx + half + 0.3, g - 0.1, g + 1.2,
             sz - half - 0.3, sz + half + 0.3, 0.5),)


_HERE = (-0.8, 4.4, 0.34, 0.46, 0.075, 10.0)   # x, z, half w/h/d, yaw


def _here_marks(fl):
    """What is cut in the thirteenth stone: no name; HERE, and under it the
    date. Cut very carefully."""
    x, z, hw, hh, hd, yaw = _HERE
    c, sn = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    tall = 0.12
    wide = 4.27 * tall                  # four glyphs of the lettering hand
    # the face toward you, and the start of a line centred across it
    fx, fz = x - sn * hd, z - c * hd
    ox, oz = fx - c * wide / 2, fz + sn * wide / 2
    return (("text", "HERE", ox, fl + 0.52, oz, tall, yaw, 0.8, 0.06),
            ("text", "1911", ox, fl + 0.3, oz, tall, yaw, 0.8, 0.06))


def _graves(fl, rise, seed):
    """Thirteen stones on the rise. Twelve of them in their rows, field-cut,
    leaning, turned to face the house over the top of the rise — so you see
    their backs — four of them small. The thirteenth a good twenty feet
    down from the rest, cut square and careful, and turned the other way,
    downhill, toward the sink: toward you."""
    rng = np.random.default_rng(seed)
    rows = []
    for r, z in enumerate((8.2, 9.2, 10.2)):
        row = []
        for c in range(4):
            x = 1.4 + c * 1.25 + rng.normal(0.0, 0.15) + (0.35 if r % 2 else 0.0)
            zz = z + rng.normal(0.0, 0.12)
            small = (r, c) in ((1, 1), (1, 2), (2, 0), (2, 3))
            w, h = ((rng.uniform(0.17, 0.22), rng.uniform(0.24, 0.3)) if small else
                    (rng.uniform(0.28, 0.38), rng.uniform(0.42, 0.58)))
            stone = _Rock((w, h, rng.uniform(0.06, 0.09)), int(rng.integers(1 << 30)),
                          yaw=rng.normal(0.0, 7.0), pitch=rng.normal(0.0, 7.0),
                          roll=rng.normal(0.0, 6.0), chips=3)
            gz = _hill(fl, rise, zz)
            row.append(stone.put(x, gz + h * 0.7, zz).data(_M_FIELD))
        rows.append(tuple(row))
    x, z, hw, hh, hd, yaw = _HERE
    lone = (_box(_M_FIELD, (x, fl + hh - 0.06, z), (hw, hh, hd), 0.02,
                 yaw=yaw),)
    return (lone,) + tuple(rows)


# rooms whose furniture has to know their own shape
# Standing in it, looking downstream: water you can see the cobble through,
# running, between walls scooped by it and ruled with the beds it cut down
# through, the canyon bending away out of the light.
_STREAM = Scene(kind="rift", floor=-1.6, rx=2.1, ry=0.7, ceil=4.2, bend=1.0,
                water=-1.48, clear=2.0, flow=1.0, ground="cobble",
                scallop=0.06, ledges=0.06, rough=0.45, freq=0.8,
                marks=(("band", 0.0, 1.3, 0.25),), tilt=-0.2,
                reach=8.0, fog=12.0, var=3.0)
_LADDER = Scene(kind="rift", floor=-1.4, rx=2.2, ry=0.6, ceil=7.5, far=2.6,
                bend=0.25, rough=0.35, bed=0.22, freq=0.6, tilt=0.5,
                reach=8.0, fog=13.0, var=14.0)
# The choke: the forty tons the miners brought down behind them in 1911,
# fifteen metres of it at forty degrees, and the gray at the top. The Choke
# looks up it from the foot; the Grip is six metres up, turning, with the
# lens throwing its light about — so the rock keeps clear of both, and of
# the lens.
_CHOKE_EYES = ((0.0, 0.0, 0.0), (0.2, 0.84 * 6.5, 6.5), (0.5, 5.2, 7.0))


def _choke_props():
    """The fill, and the hand's width of gray at the top of it."""
    return (_pile(19, -1.2, 1.2, 1.5, 0.3, 13.5, 0.35, 0.3, 19.0, 0.6,
                  slabs=18, blocks=34, spall=45, open_to=15.0, slope=0.84,
                  size=0.55, eyes=_CHOKE_EYES, clear=0.7, sides=True)
            + ((_box(_M_DAWN, (0.0, -1.2 + 0.84 * 14.7 + 1.0, 14.75),
                     (0.4, 0.035, 0.02), 0.01),),))


_CHOKE = dict(kind="jumble", floor=-1.2, ceil=1.2, wall=1.5, far=15.0,
              slope=0.84, bend=0.3, rough=0.9, freq=0.6, ground="scree",
              scar=0.35, props=_Later(_choke_props),
              glow=((0.0, -1.2 + 0.84 * 14.4 + 1.0, 14.4, 0.6, _M_DAWN),),
              reach=7.0, fog=10.0, var=19.0)


def _cache_props():
    """Her pack against its block, and the spall across the junction."""
    return (_cache(-0.25, 1.75, -1.0, 37, 20.0, pitch=7.0, roll=-9.0, twist=-22.0)
            + _strew(111, -1.0, 2.0, 3.2, 22, ((0.0, 0.0, 1.7), (-0.1, 2.5, 1.2))))


_CRAWL = dict(kind="tube", bend=0.14, rough=0.22, bed=0.05, freq=0.8)
_PASS = dict(kind="tube", bend=0.55, rough=0.48, bed=0.10)

SCENES = {

# ----- the park, at dusk ---------------------------------------------------
"trailhead": Scene(kind="forest", trees=360, canopy=6.6, understory=0.9,
                   broadleaf=0.55, path=1.7, rise=0.14, floor=-1.5, rough=0.30,
                   freq=0.6, tilt=0.02, palette="dusk", sky=0.42, fog=30.0,
                   var=21.0),
"ridge_trail": Scene(kind="forest", trees=420, canopy=4.6, understory=1.4,
                     broadleaf=0.15, path=1.35, rise=0.11, floor=-1.4,
                     rough=0.42, freq=0.7, tilt=0.02, palette="dusk", sky=0.36,
                     fog=26.0, var=22.0),
"blowdown": Scene(kind="forest", trees=320, deadwood=True, path=2.4, rise=0.13,
                  floor=-1.3, rough=0.34, freq=0.5, tilt=0.05, palette="dusk",
                  sky=0.40, fog=30.0, var=23.0),
"hollow": Scene(kind="forest", trees=380, canopy=5.2, understory=1.1,
                broadleaf=0.35, path=1.2, rise=0.20, floor=-1.35, rough=0.55,
                freq=0.55, tilt=0.02, palette="dusk", sky=0.22, fog=20.0,
                var=24.0),
# What you go over and look at in the hollow, each from where you would
# stand to look at it: the hearth from inside the house that was; the
# springhouse from down the run; the thirteenth stone from below it.
"hollow_chimney": Scene(kind="forest", trees=320, canopy=5.2, understory=0.7,
                        broadleaf=0.35, rise=0.05, floor=-1.55, rough=0.22,
                        freq=0.55, tilt=-0.15, lens=1.3, palette="dusk",
                        sky=0.3, exposure=3.0, fog=20.0, var=24.3,
                        clearing=((0.3, 2.2, 3.4), (2.6, 5.0, 2.4),
                                  (5.6, 8.1, 1.3)),
                        props=_Later(_chimney_fall, -1.55, 0.05, 31),
                        marks=_chimney_marks(-1.55, 0.05)),
"hollow_spring": Scene(kind="forest", trees=320, canopy=5.2, understory=0.7,
                       broadleaf=0.35, rise=0.04, floor=-1.55, rough=0.2,
                       freq=0.55, tilt=-0.3, lens=1.3, palette="dusk",
                       sky=0.3, exposure=3.0, fog=20.0, var=24.6,
                       clearing=((0.9, 5.7, 2.6), (0.1, 2.9, 1.9)),
                       props=_Later(_springhouse, -1.55, 0.04, 47),
                       marks=_springhouse_marks(-1.55, 0.04)),
"hollow_graves": Scene(kind="forest", trees=320, canopy=5.2, understory=0.6,
                       broadleaf=0.35, rise=0.2, floor=-1.55, rough=0.22,
                       freq=0.55, tilt=-0.14, lens=1.0, palette="dusk",
                       sky=0.3, exposure=3.0, fog=20.0, var=24.9,
                       clearing=((-0.8, 4.4, 2.2), (1.0, 6.4, 2.2), (3.3, 9.2, 3.8)),
                       props=_Later(_graves, -1.55, 0.2, 13),
                       marks=_here_marks(-1.55)),
# Wolf Sink, from where you come into the camp: the table and its people
# under the work lights, and the hole a dozen yards off under the hemlocks.
"basecamp": Scene(kind="forest", camp=True, crowd=True, trees=340, canopy=5.4,
                  understory=0.5, rise=0.08, floor=-1.5, rough=0.36, freq=0.6,
                  lights=2.4, tilt=0.02, palette="dusk", sky=0.24, fog=24.0,
                  reach=8.0, var=25.0),

# ----- the cave ------------------------------------------------------------
# The same place at two in the morning, from the lip by the generator,
# looking down across the hole: the lights are behind you now, and nobody
# is at the table.
"sink": Scene(kind="forest", camp=True, at=(2.5, 8.1), face=-31.7,
              trees=340, canopy=5.4, understory=0.5, rise=0.08, floor=-1.5,
              rough=0.36, freq=0.6, lights=2.8, tilt=-0.22, palette="night",
              sky=0.020, fog=24.0, reach=7.5, var=25.0),
# a bedding-plane crawl, on your side, the pack pushed ahead
"letterbox": Scene(kind="crawl", floor=-0.22, rough=0.3, lens=1.6, tilt=-0.08,
                   reach=3.6, fog=7.0, var=1.0),
# You climb down out of the Letterbox, stand, and turn round: the slot you
# came out of, knee-high in the far wall; the stream's canyon off to the
# west with the cairn at its foot; the gallery's arch to the east; the
# crickets at head height; the walls drawing in overhead. All three ways
# in one look, because the prose offers three.
"bell": Scene(kind="dome", floor=-1.55, wall=3.0, ceil=3.4, far=2.3,
              at=(0.0, 0.4), bell=0.45, chimney=0.85, ground="cobble",
              # (a way sunk below the floor is cut off by it: an arch, a
              # canyon running down into the cobble, not a hole in the wall)
              ways=((-65.0, 0.9, 4.2, -0.5), (0.0, 2.8, 0.5, 0.55),
                    (65.0, 2.1, 2.1, -0.65)),
              rough=0.7, freq=0.6, bed=0.1, tilt=-0.2,
              props=(_cairn(-1.5, 2.9, -1.55),),
              marks=(("specks", 1.2, 2.0, 0.15, 0.8),),
              reach=8.5, fog=13.0, var=2.0),
"stream": replace(_STREAM, props=(
    _flood_ledge(_STREAM, 1.2, 4.4, _STREAM.floor + 1.35, -1.0),
    _salamander(-0.25, _STREAM.water + 0.012, 2.75, heading=-80.0))),
"sump": Scene(kind="jumble", floor=-1.5, ceil=0.7, wall=1.6, far=14.0,
              slope=-0.33, bend=0.2, water=-1.75, clear=1.6,
              rough=0.34, freq=0.6, bed=0.14, tilt=-0.2,
              props=(_dive_line(1.45, 2.8, -1.75),),
              reach=9.0, fog=15.0, var=4.0),
"gallery": Scene(kind="hall", floor=-1.4, wall=2.1, ceil=1.2, far=16.0,
                 ground="dust", pit=(0.3, 13.6, 0.75),
                 rough=0.22, freq=0.5, bed=0.08, tilt=-0.06,
                 props=((_tag(2.05, -0.12, 3.4, 0.0),),
                        (_tag(2.05, -0.18, 6.3, 0.0),),
                        _flagged_hole(-0.45, 12.8, -1.4)),
                 # small boots, in and out, trip after trip — and on top of
                 # them one fresh set, just beside yours, going the same way
                 marks=(("prints", 0.05, 0.6, 0.0, 0.34, 40, 0.28),
                        ("prints", -0.18, 0.9, 0.5, 0.36, 36, 0.28),
                        ("prints", 0.5, 0.5, 1.0, 0.7, 18, 0.6)),
                 reach=10.0, fog=15.0, var=5.0),
# flat on your stomach, head over the lip, looking down the free hang
"pitch_head": Scene(kind="drop", floor=-0.4, hole_r=0.75, hole_z=0.8,
                    depth_below=12.0, rough=0.16, freq=1.4, tilt=-0.85,
                    reach=8.5, fog=12.0, var=6.0),
# Off the rope and looking out: the chamber forks round a buttress of rock
# and runs off both ways into more dark than the beam can find, the air
# coming out of both. The rope hangs out of its hole in the roof onto the
# shattered plate, the tail of it coiled where it landed, and beside it the
# block you tagged at knee height so you can find the way out.
"pitch_bottom": Scene(kind="hall", floor=-1.5, wall=3.0, ceil=4.5, far=5.0,
                      chimney=0.8, hole_z=2.4, ground="plate",
                      ways=((-46.0, 5.4, 5.2, -1.2), (48.0, 5.0, 4.8, -1.2)),
                      rough=0.6, freq=0.5, bed=0.3, tilt=-0.27,
                      props=(*_rope(0.1, 2.4, 9.0, -1.5),
                             _marked_block(1.0, 2.2, -1.5, (0.5, 0.36, 0.42),
                                           707, 25.0, 0.5),
                             _buttress(0.2, 4.1, -1.5, (1.6, 3.3, 1.1), 71, 15.0)),
                      reach=10.5, fog=16.0, var=7.0),
"breakdown": Scene(kind="jumble", floor=-1.4, ceil=2.6, wall=3.6, far=14.0,
                   bend=0.5, rough=0.9, freq=0.62, bed=0.05, ground="rubble",
                   scar=0.45,
                   props=_Later(_pile, 81, -1.4, 2.6, 3.6, 1.0, 13.0, 0.55, 0.5,
                                8.0, 0.62),
                   reach=7.5, fog=11.0, var=8.0),
"roost": Scene(kind="dome", floor=-1.6, wall=3.4, ceil=2.6, far=2.8,
               pockets=26, ground="guano", ways=((180.0, 1.2, 1.5),),
               rough=0.5, freq=0.44, tilt=0.42,
               reach=8.0, fog=12.0, var=9.0),
"badair": Scene(kind="hall", floor=-0.5, wall=1.9, ceil=0.5, far=14.0,
                ground="silt", murk=0.32, palette="sallow",
                rough=0.3, freq=0.7, bed=0.08, tilt=-0.05,
                reach=4.2, fog=8.0, var=10.0),
# Down on one knee by her pack, in the middle of the junction, where it
# stands against a block come out of the breakdown behind you. The sallow
# air's way goes off low along a bed to the left; the slot is in the far
# wall off to the right, running into the rock at an angle, so it stays a
# hole and never a figure standing there, and rubbed pale on both lips at
# hip height.
"pack": Scene(kind="dome", floor=-1.0, wall=3.2, ceil=1.8, far=2.0,
              ways=((-72.0, 2.4, 0.8, 0.0, "bedding"),
                    (55.0, 0.46, 1.6, 0.0, "keyhole", 40.0)),
              ground="silt", fill=0.6, gloom=1.1, ledges=0.03, bed=0.08,
              rough=0.6, freq=0.45, lens=1.6, tilt=-0.33,
              props=_Later(_cache_props),
              marks=_lips(55.0, 3.2, 2.0, -1.0, 2.8, 0.9, 0.17),
              reach=8.5, fog=13.0, var=11.0),
# The far wall of the cache, bedded limestone, and the slot in it: a round
# tube shoulder-wide at the top and a hip-wide cut under it, snaking off
# into the rock, rubbed pale on both lips at hip height where someone has
# been through it lately.
"squeeze": Scene(kind="hall", floor=-1.45, wall=2.4, ceil=0.9, far=2.6,
                 ways=((0.0, 0.46, 1.6, 0.0, "keyhole"),),
                 at=(-0.8, 0.5), face=21.0,
                 ledges=0.03, bed=0.06, rough=0.5, freq=0.6, tilt=-0.22,
                 marks=(("joint", 0.0, 2.6, 0.1, 0.9, 0.7),
                        ("scuff", -0.17, -0.55, 2.62, 0.32, 0.9),
                        ("scuff", 0.17, -0.6, 2.62, 0.28, 0.8)),
                 reach=6.0, fog=9.0, var=12.0),
"long_room": Scene(kind="hall", floor=-1.6, wall=40.0, ceil=20.0, far=70.0,
                   ground="silt", rough=0.4, freq=0.22, tilt=-0.1,
                   marks=(("prints", 0.35, 1.2, 4.0, 0.72, 60, 0.8),),
                   reach=17.0, fog=26.0, var=13.0),
"ladder": replace(_LADDER, props=_rungs(0.1, 2.6, -1.1, 10, 0.32),
                  marks=(("soot", 0.0, 2.2, 2.6, 0.9, 0.75),
                         ("soot", -0.6, 1.4, 2.6, 0.6, 0.6),
                         ("soot", 0.7, 2.7, 2.6, 0.5, 0.55),
                         ("text", "1911", -0.45, 2.55, 2.6, 0.26, 0.0, 0.9),
                         ("text", str(time.localtime().tm_year), -0.45, 2.15,
                          2.6, 0.26, 0.0, 0.9))),
"deep": Scene(kind="hall", floor=-1.55, wall=30.0, ceil=16.0, far=50.0,
              ground="silt", rough=0.5, freq=0.24, tilt=-0.1,
              marks=(("prints", 0.3, 1.0, 2.0, 0.72, 10, 0.8),),
              props=(_left_behind(0.55, 8.6, -1.55),),
              glow=((0.52, -1.21, 8.3, 1.8, _M_LAMP),),
              reach=15.0, fog=24.0, var=15.0),

# ----- the rescue ----------------------------------------------------------
# The nest's floor is worked smooth; the adit is cut, not dissolved, so it
# runs straight and square; the choke is broken rock climbing at forty
# degrees, so the camera looks up it.
"nest": Scene(kind="dome", floor=-1.5, wall=6.0, ceil=3.0, far=4.3,
              ground="bone", ways=((180.0, 0.9, 1.2),),
              rough=0.4, freq=0.3, bed=0.03,
              props=(_sitting(2.9, 9.4, -1.5),),
              absorb=(-0.5, -0.5, 4.6, 1.0, 0.95, 1.1),
              reach=12.0, fog=16.0, var=17.0),
"adit": Scene(kind="mine", floor=-1.3, rx=0.95, ry=2.0, slope=0.09, far=26.0,
              rough=0.12, freq=0.9, tilt=0.1,
              props=(_sets(-1.3, 0.09, 0.95, 2.0, np.arange(1.2, 25.0, 1.6))
                     + _track(-1.3, 0.09, 0.3, 25.5)
                     + ((_box(_M_DAWN, (0.1, -1.3 + 0.09 * 25.95 + 1.1, 25.95),
                              (0.03, 0.45, 0.02), 0.01),),)),
              glow=((0.1, -1.3 + 0.09 * 25.5 + 1.1, 25.5, 0.35, _M_DAWN),),
              marks=tuple(("soot", 0.0, -1.3 + 0.09 * z + 1.9, z, 0.45, 0.6)
                          for z in np.arange(1.2, 25.0, 1.6)),
              reach=9.0, fog=14.0, var=18.0),
"choke": Scene(**_CHOKE, tilt=0.62),
# the same look up the fill a moment later, if you take the lens out: held
# in the gray, it flares white
"point": Scene(**{**_CHOKE, "glow": _CHOKE["glow"] + (
                   (0.1, -1.2 + 0.84 * 13.9 + 0.85, 13.8, 3.5, _M_LAMP),)},
               tilt=0.62),
"grip": Scene(**{**_CHOKE, "glow": _CHOKE["glow"] + ((0.5, 5.2, 7.0, 0.7, _M_LAMP),)},
              at=(0.2, 6.5), tilt=0.55, roll=-0.3),

# ----- terminal ------------------------------------------------------------
"drowned": Scene(kind="under", rx=1.6, ry=1.6, bend=0.5, rough=0.5, freq=0.7,
                 palette="under", reach=2.6, fog=3.4, var=16.0),
"stay": Scene(kind="void", palette="cave"),
}

_DEFAULT = Scene(**_PASS, rx=1.8, ry=1.4, floor=-1.3, reach=8.0, var=99.0)

# Quantised so the cache actually hits: the picture only has to change when
# you have visibly more or less light, not on every burnt tenth of a percent.
_LIGHT_STEPS = (0.04, 0.15, 0.30, 0.52, 0.76, 1.00)
_SKY_STEPS = (0.05, 0.22, 0.45, 0.72, 1.00)


def light_band(reach):
    """reach is 0-100, as the engine's `Game.reach` reports it."""
    for i, edge in enumerate((3.0, 12.0, 26.0, 48.0, 74.0)):
        if reach < edge:
            return i
    return 5


def sky_band(daylight):
    """daylight is 0-100."""
    for i, edge in enumerate((10.0, 32.0, 58.0, 82.0)):
        if daylight < edge:
            return i
    return 4


# A stand is a few dozen trunks and crowns, and every one of them is another
# distance to every marched ray, over a lot of steps. Rather than thin the
# woods out, render forests on a coarser grid and let the upscale blur it —
# which is close to what dusk under a canopy actually looks like. The cave
# rooms take the same cap: a furnished room is dozens of props and marks,
# and a helmet lamp in a cave never made anything sharper than this anyway.
_FOREST_BUDGET = 44_000


@lru_cache(maxsize=72)
def frame(room_id, band, sky, w, h):
    """The lamp's-eye view of a room. Cached; safe to call from a thread."""
    s = SCENES.get(room_id, _DEFAULT)
    if s.sky:
        s = replace(s, sky=s.sky * _SKY_STEPS[sky], day=_SKY_STEPS[sky])

    rw, rh = w, h
    if (s.kind in ("forest", "crawl") or s.kind in _ROOMS) and \
            w * h > _FOREST_BUDGET:
        k = (_FOREST_BUDGET / (w * h)) ** 0.5
        rw, rh = max(8, round(w * k)), max(8, round(h * k))

    img = _render(s, _LIGHT_STEPS[band], rw, rh)
    if (rw, rh) != (w, h):
        img = img.resize((w, h), Image.BILINEAR)
    return img
