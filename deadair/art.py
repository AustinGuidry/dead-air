"""
DEAD AIR — procedural scene art.

Every frame is raymarched from a signed-distance description of the place you
are standing in, then lit by your actual lamp. Nothing here is a picture file:
the beam is a light in the scene, so when the battery dies the image loses reach
and detail for the same reason the prose does.

Pure rendering. It knows about rooms only through SCENES, which is data.
"""

from __future__ import annotations

import math
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
    kind: str = "tube"          # tube | chamber | hole | forest | void
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
    hole_r: float = 2.6         # hole radius for kind="hole"
    hole_z: float = 5.2         # how far ahead the hole sits
    depth_below: float = 12.0   # how deep the hole goes before rock
    trees: int = 0              # trunks in view — a stand, or around a hole
    canopy: float = 0.0         # height of the lowest branches, 0 = bare
    understory: float = 0.0     # how thick the brush is, 1.0 = walls the path
    path: float = 0.0           # half-width of a cleared path, 0 = none
    rise: float = 0.0           # ground slope away from you — the ridge going up
    deadwood: bool = False      # bare standing trunks — no crowns, no brush
    broadleaf: float = 0.0      # share of the canopy that is oak, not hemlock
    lights: float = 0.0         # work lights on a generator, behind your back
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

    def nearest(self, cell, fn):
        """Distance from each point to the nearest thing of this kind; 1e3
        where its cell lists nothing.

        `fn(j, fields)` measures points `j` against the fields of what their
        cells list — x, z, then the params in the order given, each one
        column per listed thing. Points go through grouped by how full their
        cell is, so a sparse cell never pays for the fullest one.
        """
        out = np.full(cell.shape, 1.0e3, dtype=F32)
        cnt = self.count[cell]
        lo = 0
        for hi in self.tiers:
            j = np.flatnonzero((cnt > lo) & (cnt <= hi))
            if j.size:
                b = self.blk[cell[j], :, :hi]
                out[j] = fn(j, [b[:, f] for f in range(b.shape[1])]).min(axis=1)
            lo = hi
        return out


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

        # nothing on the path, and nothing standing in the camera's lap
        clear = ~((tz < 2.2) & (np.abs(tx) < 1.4))
        if s.path:
            clear &= np.abs(tx - _path_x(s, tz)) > s.path + tr + 0.5
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
        nh = 0 if s.deadwood else int(28 * s.understory)
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
        if s.path:
            clear &= np.abs(bx - _path_x(s, bz)) > s.path + br * 0.35
        bx, bz, br, bh = bx[clear], bz[clear], br[clear], bh[clear]
        bry = bh / 1.35                         # a third of it sunk in the dirt
        self.brush = _Kind(bx, bz, br, lo=0.0, hi=np.max(bh, initial=0.0),
                           margin=0.6,
                           cy=s.floor + _rise(s, bz) + bry * 0.35,
                           inv=1.0 / br, yinv=1.0 / bry,
                           scale=np.minimum(br, bry))


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


def _air_fn(s: Scene, detail=False):
    """Signed distance for a scene: positive in open space, negative in rock.

    `detail` adds the second noise octave. The march runs without it — it only
    needs to know roughly where the rock is — and the normals are taken with
    it, which is where the texture actually shows up.
    """
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
        # The sink opens under a stand of hemlock, so the hole can carry
        # trunks too — without them the lip is a dent in an empty field and
        # nothing in the picture agrees with the prose.
        n_t = s.trees
        if n_t:
            hrng = np.random.default_rng(int(v * 1000) + 11)
            tz = hrng.uniform(-2.0, 17.0, n_t).astype(F32)
            tx = hrng.uniform(-10.0, 10.0, n_t).astype(F32)
            tr = hrng.uniform(0.17, 0.36, n_t).astype(F32)
            # not standing in the hole, and not in the camera's lap
            hd = np.sqrt(tx ** 2 + (tz - s.hole_z) ** 2)
            push = hd < s.hole_r + 1.3
            scale = np.where(push, (s.hole_r + 1.3) / np.maximum(hd, 0.2), 1.0)
            tx = (tx * scale).astype(F32)
            tz = (s.hole_z + (tz - s.hole_z) * scale).astype(F32)
            lap = (np.abs(tx) < 1.1) & (tz < 1.6)
            tx[lap] = tx[lap] + 2.4
            TX, TZ, TR = tx[None, :], tz[None, :], tr[None, :]

        def air(px, py, pz):
            ground = py - s.floor - rock(px, py, pz)
            ang = np.arctan2(px, pz - s.hole_z)
            r = np.sqrt(px ** 2 + (pz - s.hole_z) ** 2)
            rim = s.hole_r * (1.0 + 0.26 * np.sin(ang * 3.0 + v)
                              + 0.12 * np.sin(ang * 7.0 - v))
            shaft = np.minimum(rim - r, py - (s.floor - s.depth_below))
            a = np.maximum(ground, shaft)
            if n_t:
                yb = (py - s.floor)[:, None]
                hx = px[:, None] - TX
                hz = pz[:, None] - TZ
                trad = TR * (1.10 - 0.5 * np.clip(yb - 0.9, -0.9, 0.0))
                trunk = np.sqrt(hx * hx + hz * hz) - trad
                trunk = np.maximum(trunk, yb - 11.0)
                a = _smin(a, trunk.min(axis=1), 0.25)
            return a

    elif s.kind == "forest":
        st = _stand(s)
        # the tilt costs the plane SDF its unit gradient; keep it conservative
        rise_norm = math.sqrt(1.0 + s.rise * s.rise)
        inv_cell = 1.0 / _CELL

        def band(k, g):
            """The points close enough in height to meet something of kind k.

            Anything skipped is more than a full stride away, which the march
            never steps; the give is the hill rising under the thing's reach.
            """
            slop = _STRIDE + s.rise * (k.reach + _STRIDE)
            return np.flatnonzero((g > k.lo - slop) & (g < k.hi + slop))

        def parts(px, py, pz):
            """Distances to the ground, the nearest trunk, the leaves and the
            brush, kept apart — plus the step bound. 1e3 means none near."""
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
            return ground, trunk, leaves, bush, bound

        def air(px, py, pz):
            ground, trunk, leaves, bush, bound = parts(px, py, pz)
            a = _smin(ground, trunk, 0.25)
            i = np.flatnonzero(leaves < 2.0)
            if i.size:
                a[i] = _smin(a[i], leaves[i], 0.40)
            i = np.flatnonzero(bush < 2.0)
            if i.size:
                a[i] = _smin(a[i], bush[i], 0.3)
            return np.minimum(a, bound)

        def material(px, py, pz):
            """What a point on the surface is: 0 ground, 1 bark, 2 leaves,
            3 brush."""
            return np.argmin(np.stack(parts(px, py, pz)[:4]), axis=0)

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


def _ground_t(s, dy, dz):
    """Where a ray from the eye meets the bare hillside, or inf if it never does."""
    tg = np.full(dy.shape, np.inf, dtype=F32)
    down = dy < -1e-4
    flat = s.floor / np.where(down, dy, -1.0)
    near = down & (dz * flat < 4.0)
    tg[near] = flat[near]
    den = dy - s.rise * dz
    up = (den < -1e-4) & ~near
    slope = (s.floor - 4.0 * s.rise) / np.where(up, den, -1.0)
    far = up & (dz * slope >= 4.0)
    tg[far] = slope[far]
    return tg


def _render(s: Scene, light: float, w: int, h: int) -> Image.Image:
    """Render a scene. `light` is 0..1 — how much lamp you have."""
    aspect = w / h
    tan_x, tan_y = 0.56 * aspect, 0.56
    cap = s.lens or (_FOREST_TAN if s.kind == "forest" else 0.0)
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
    dx, dy, dz = sx, sy, np.ones_like(sx)
    if s.tilt:
        ct, st = math.cos(s.tilt), math.sin(s.tilt)
        dy, dz = dy * ct + dz * st, dz * ct - dy * st
    ln = np.sqrt(dx * dx + dy * dy + dz * dz)
    dx, dy, dz = (dx / ln).ravel(), (dy / ln).ravel(), (dz / ln).ravel()

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
    else:
        mp = {}
    t, hit = _march(coarse, dx, dy, dz, **mp)
    if s.kind == "forest":
        # A ray that skims the hillside closes on it a few centimetres a step
        # and can run out of steps before it lands. Left alone it was drawn
        # as sky — a third of the ground was — and every trunk behind it
        # stood on a strip of nothing. The hill is a known plane, so put
        # those rays down on it.
        tg = _ground_t(s, dy, dz)
        miss = ~hit & np.isfinite(tg)
        t = np.where(miss, tg, t).astype(F32)
        hit = hit | miss

    hx, hy, hz = dx * t, dy * t, dz * t
    nx, ny, nz = _normal(fine, hx, hy, hz)

    grain = _fbm(hx * 2.4 + s.var, hy * 2.4, hz * 2.4, 3)
    albedo = 0.30 + 0.52 * grain
    shade = 1.0
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
        shade = 1.0 - 0.85 * occ
        # What each ray landed on. The woods are all one grey at dusk, so
        # what separates them is what things are made of: needles and
        # rhododendron leaf drink the light, bark less so, and a trail is
        # packed pale dirt with a slot of open sky over it.
        mat = coarse.material(hx, hy, hz)
        tone = np.array([0.85, 0.75, 0.5, 0.55], dtype=F32)
        if s.deadwood:
            tone[1] = 1.45     # the bark is off them and the wood gone silver
        albedo = albedo * tone[mat]
        if s.path:
            onp = 1.0 / (1.0 + ((hx - _path_x(s, hz)) / s.path) ** 2 * 1.6)
            onp = onp * (mat == 0)
            albedo = albedo * (1.0 + 1.3 * onp)
            canopy = canopy + (1.0 - canopy) * 0.7 * onp
        shade = shade * canopy

    if surface:
        # `sky` is the radiance of the sky itself; surfaces get a fraction of
        # it, and how much depends on how much sky they can still see — which
        # is none at all, down a hole.
        sky_occ = np.clip((hy - (s.floor - 1.2)) / 1.5, 0.0, 1.0) ** 1.7
        sky_amt = (0.45 + 0.55 * ny) * sky_occ
        sun = np.clip(nx * -0.70 + ny * 0.34 + nz * -0.62, 0.0, 1.0)
        lit = albedo * s.sky * (0.85 * sky_amt + 0.70 * sun ** 1.6 * sky_occ) * shade
        # A headlamp switched on in daylight does not brighten the hillside;
        # it puts a pale coin on the ground in front of your boots. So the
        # day shortens the lamp's reach rather than dimming it.
        head = np.clip(-(dx * nx + dy * ny + dz * nz), 0.0, 1.0)
        reach = max(0.6, s.reach * (1.0 - 0.86 * s.day))
        lit = lit + albedo * head * light * 2.2 / (1.0 + (t / reach) ** 2 * 2.2)
        if s.lights:
            # A generator and a string of lamps on stands, behind your back.
            # They make a hard white room out of forty feet of hemlock and
            # nothing at all out of the rest of the ridge — which is the
            # line in the prose, and the reason the hole reads as a hole:
            # nothing that goes down it comes back lit.
            for lx, ly, lz in ((-3.4, 2.3, -2.6), (3.8, 2.0, -1.2),
                               (0.4, 2.6, -4.0)):
                wx, wy, wz = lx - hx, ly - hy, lz - hz
                d2 = wx * wx + wy * wy + wz * wz
                inv = 1.0 / np.sqrt(d2)
                ndl = np.clip((nx * wx + ny * wy + nz * wz) * inv, 0.0, 1.0)
                lit = lit + albedo * s.lights * ndl / (1.0 + d2 * 0.035)
    else:
        reach = s.reach * (0.32 + 0.68 * light)
        diff = np.clip(-(dx * nx + dy * ny + dz * nz), 0.0, 1.0)
        cone = np.clip((dz - 0.60) / 0.36, 0.0, 1.0) ** 0.7
        cone = 0.20 + 0.80 * cone
        atten = 1.0 / (1.0 + (t / reach) ** 2 * 2.6)
        lit = albedo * (light * 1.95 * diff * cone * atten + 0.010 * light)

    if s.water is not None:
        # Water is the one surface here that is not rock, so it gets a real
        # second march: mirror the ray in the plane and shade what it finds.
        on_water = (np.abs(hy - s.water) < 0.13) & hit & (dy < -0.02)
        widx = np.flatnonzero(on_water)
        if widx.size:
            ox = hx[widx]
            oy = np.full(widx.size, s.water + 0.03, dtype=F32)
            oz = hz[widx]
            rdx, rdy, rdz = dx[widx], -dy[widx], dz[widx]
            rt, rhit = _march(coarse, rdx, rdy, rdz, steps=26, tmax=18.0,
                              org=(ox, oy, oz), **mp)
            rpx, rpy, rpz = ox + rdx * rt, oy + rdy * rt, oz + rdz * rt
            rnx, rny, rnz = _normal(fine, rpx, rpy, rpz)
            rdiff = np.clip(-(rdx * rnx + rdy * rny + rdz * rnz), 0.0, 1.0)
            total = t[widx] + rt
            ratten = 1.0 / (1.0 + (total / (s.reach * (0.32 + 0.68 * light)))
                            ** 2 * 2.6)
            refl = 0.85 * light * rdiff * ratten * rhit
            # grazing angles reflect more, the way water does
            fres = 0.34 + 0.66 * (1.0 - np.clip(-dy[widx], 0.0, 1.0)) ** 2.5
            lit[widx] = lit[widx] * 0.13 + refl * fres

    if surface:
        lit = np.where(hit, lit, s.sky * 1.9 + light * 0.03)
    else:
        lit = np.where(hit, lit, 0.0)

    # scatter: haze between the trees, or dust hanging in the beam
    fade = np.exp(-t / s.fog)
    if s.kind == "forest":
        # Deep in a stand almost no ray reaches open sky, so the haze has to
        # carry the evening: distant trunks go pale into the glow the way
        # they do at dusk, and the near ones stand dark against it.
        haze = s.sky * (1.45 + 0.55 * np.clip(dy * 5.0 + 0.3, 0.0, 1.0))
        lit = lit * fade + (haze + light * 0.03) * (1.0 - fade)
    elif surface:
        lit = lit * fade + (s.sky * 1.25 + light * 0.03) * (1.0 - fade)
    else:
        lit = lit + 0.075 * light * fade * np.clip((dz - 0.52) / 0.48, 0.0, 1.0)

    lit = lit.reshape(h, w)

    vy, vx = np.mgrid[0:h, 0:w].astype(F32)
    r2 = (((vx / w) - 0.5) * 2.0) ** 2 + (((vy / h) - 0.5) * 2.0) ** 2
    lit = lit * np.clip(1.14 - 0.36 * r2, 0.0, 1.2)

    lit = lit / (1.0 + lit * 0.85)
    lit = np.clip(lit * 1.15, 0.0, 1.0) ** 0.82
    gr = np.random.default_rng(int(s.var * 977) + int(light * 40)).normal(
        0.0, 1.0, lit.shape).astype(F32)
    lit = np.clip(lit + gr * (0.014 + 0.048 * (1.0 - lit)), 0.0, 1.0)

    idx = (lit * 255.0).astype(np.uint8)
    return Image.fromarray(_lut(s.palette)[idx].astype(np.uint8), "RGB")


# --------------------------------------------------------------------------
#  THE PLACES — one Scene per room. Data, like content.py.
# --------------------------------------------------------------------------

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
"basecamp": Scene(kind="hole", floor=-1.5, hole_r=3.0, hole_z=5.5,
                  depth_below=13.0, rough=0.45, trees=13, lights=1.5,
                  tilt=-0.34, palette="dusk", sky=0.24, fog=50.0,
                  reach=8.0, var=25.0),

# ----- the cave ------------------------------------------------------------
"sink": Scene(kind="hole", floor=-1.5, hole_r=2.7, hole_z=4.4, depth_below=14.0,
              rough=0.45, trees=11, lights=1.7, tilt=-0.38,
              palette="night", sky=0.020, fog=30.0, reach=7.5, var=26.0),
"letterbox": Scene(**_CRAWL, rx=1.05, ry=0.34, floor=-0.34, reach=3.6,
                   fog=7.0, var=1.0),
"bell": Scene(kind="chamber", floor=-1.5, ceil=6.5, wall=3.4, far=9.0,
              rough=0.85, freq=0.34, bed=0.12, reach=8.5, fog=13.0, var=2.0),
"stream": Scene(kind="tube", rx=1.05, ry=2.6, bend=0.34, rough=0.42, bed=0.20,
                freq=0.55, floor=None, water=-1.15, reach=8.0, fog=12.0,
                var=3.0),
"sump": Scene(kind="tube", rx=1.5, ry=1.8, bend=0.22, rough=0.38, bed=0.14,
              floor=None, water=-0.85, reach=9.0, fog=15.0, var=4.0),
"gallery": Scene(**_PASS, rx=2.3, ry=1.6, floor=-1.35, reach=10.0, fog=15.0,
                 var=5.0),
"pitch_head": Scene(kind="hole", floor=-1.35, hole_r=1.45, hole_z=2.9,
                    depth_below=15.0, rough=0.38, freq=0.6, tilt=-0.46,
                    reach=7.0, fog=14.0, var=6.0),
"pitch_bottom": Scene(kind="chamber", floor=-1.5, ceil=8.0, wall=5.0, far=15.0,
                      rough=0.95, freq=0.30, bed=0.14, reach=10.5, fog=16.0,
                      var=7.0),
"breakdown": Scene(kind="chamber", floor=-1.4, ceil=3.2, wall=4.2, far=11.0,
                   rough=1.5, freq=0.62, bed=0.05, reach=7.5, fog=11.0,
                   var=8.0),
"roost": Scene(kind="chamber", floor=-1.6, ceil=4.4, wall=3.0, far=7.0,
               rough=0.7, freq=0.44, reach=8.0, fog=12.0, var=9.0),
"badair": Scene(**_CRAWL, rx=1.5, ry=0.46, floor=-0.46, reach=4.2, fog=8.0,
                var=10.0),
"pack": Scene(kind="chamber", floor=-1.45, ceil=4.0, wall=3.2, far=8.5,
              rough=0.8, freq=0.40, bed=0.10, reach=8.5, fog=13.0, var=11.0),
"squeeze": Scene(kind="tube", rx=0.42, ry=2.4, bend=0.10, rough=0.26, bed=0.18,
                 freq=0.9, floor=None, reach=4.0, fog=8.0, var=12.0),
"long_room": Scene(kind="chamber", floor=-1.5, ceil=14.0, wall=17.0, far=40.0,
                   rough=1.1, freq=0.22, bed=0.16, reach=17.0, fog=26.0,
                   var=13.0),
"ladder": Scene(kind="tube", rx=1.1, ry=3.4, bend=0.18, rough=0.40, bed=0.22,
                freq=0.6, floor=-1.4, reach=8.0, fog=13.0, var=14.0),
"deep": Scene(kind="chamber", floor=-1.5, ceil=13.0, wall=15.0, far=34.0,
              rough=0.9, freq=0.24, bed=0.12, reach=15.0, fog=24.0, var=15.0),

# ----- the rescue ----------------------------------------------------------
# The nest's floor is worked smooth; the adit is cut, not dissolved, so it
# runs straight and nearly clean; the choke is broken rock climbing at forty
# degrees, so the camera looks up it.
"nest": Scene(kind="chamber", floor=-1.5, ceil=5.0, wall=6.0, far=13.0,
              rough=0.45, freq=0.30, bed=0.03, reach=10.0, fog=14.0,
              var=17.0),
"adit": Scene(kind="tube", rx=1.1, ry=1.3, bend=0.06, rough=0.16, bed=0.02,
              freq=0.9, floor=-1.2, tilt=0.12, reach=9.0, fog=14.0, var=18.0),
"choke": Scene(kind="tube", rx=1.3, ry=1.4, bend=0.22, rough=1.2, freq=0.6,
               floor=None, tilt=0.42, reach=7.0, fog=10.0, var=19.0),
"grip": Scene(kind="tube", rx=1.3, ry=1.4, bend=0.22, rough=1.2, freq=0.6,
              floor=None, tilt=0.42, reach=7.0, fog=10.0, var=19.0),

# ----- terminal ------------------------------------------------------------
"drowned": Scene(kind="tube", rx=1.6, ry=1.6, bend=0.5, rough=0.5, freq=0.7,
                 floor=None, reach=2.6, fog=3.4, var=16.0),
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
# which is close to what dusk under a canopy actually looks like.
_FOREST_BUDGET = 44_000


@lru_cache(maxsize=72)
def frame(room_id, band, sky, w, h):
    """The lamp's-eye view of a room. Cached; safe to call from a thread."""
    s = SCENES.get(room_id, _DEFAULT)
    if s.sky:
        s = replace(s, sky=s.sky * _SKY_STEPS[sky], day=_SKY_STEPS[sky])

    rw, rh = w, h
    if s.kind == "forest" and w * h > _FOREST_BUDGET:
        k = (_FOREST_BUDGET / (w * h)) ** 0.5
        rw, rh = max(8, round(w * k)), max(8, round(h * k))

    img = _render(s, _LIGHT_STEPS[band], rw, rh)
    if (rw, rh) != (w, h):
        img = img.resize((w, h), Image.BILINEAR)
    return img
