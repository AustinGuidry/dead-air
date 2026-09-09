"""
DEAD AIR — procedural scene art.

Every frame is raymarched from a signed-distance description of the place you
are standing in, then lit by your actual lamp. Nothing here is a picture file:
the beam is a light in the scene, so when the cell dies the image loses reach
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
    trees: int = 0              # trunk count for kind="forest"
    canopy: float = 0.0         # crown-centre height above the floor, 0 = bare
    understory: float = 0.0     # low-brush density, as a multiple of `trees`
    path: float = 0.0           # half-width of a cleared path, 0 = none
    rise: float = 0.0           # ground slope away from you — the ridge going up
    deadwood: bool = False      # bare standing trunks — no crowns, no brush
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
        rng = np.random.default_rng(int(v * 1000) + 7)
        n_t = max(1, s.trees)

        def centreline(z):
            """Where the path runs, as it wanders off ahead of you."""
            return 1.1 * np.sin(z * 0.13 + v) + 0.5 * np.sin(z * 0.37 + v * 1.7)

        # The ground goes up behind you. This is in the prose — nineteen
        # hundred feet of ridge — but it is also what makes the far ground
        # drawable at all: a ray aimed along a flat plane grazes it and the
        # march creeps a few centimetres a step, so the ground ran out around
        # ten metres and every tree behind that hung in the air. A slope is
        # something a ray can actually hit.
        def rise(z):
            return s.rise * np.maximum(z - 4.0, 0.0)

        # the tilt costs the plane SDF its unit gradient; keep it conservative
        rise_norm = math.sqrt(1.0 + s.rise * s.rise)

        # Trunks. A mild pull toward the distance so the stand closes up ahead
        # of you, then two thick ones planted close on either side of the path
        # so you are looking *into* the forest, not at a clearing edge.
        u = rng.random(n_t).astype(F32)
        tz = (2.4 + u ** 1.25 * _TREE_DEPTH).astype(F32)
        tx = rng.uniform(-13.0, 13.0, n_t).astype(F32)
        tr = (rng.uniform(0.11, 0.24, n_t) * (1.0 + tz / 22.0)).astype(F32)
        tls = rng.uniform(-0.05, 0.05, n_t).astype(F32)      # per-trunk lean
        crown_h = (s.canopy + rng.uniform(-0.7, 1.6, n_t)).astype(F32)
        crown_r = rng.uniform(1.7, 3.1, n_t).astype(F32)

        if n_t >= 5:
            fr = np.argsort(tz)[:2]
            tz[fr] = rng.uniform(3.2, 5.2, 2)
            tr[fr] = rng.uniform(0.16, 0.24, 2)
            tls[fr] = rng.uniform(-0.02, 0.02, 2)
            side = np.array([-1.0, 1.0], dtype=F32)
            tx[fr] = side * ((s.path or 1.4) + rng.uniform(1.2, 2.8, 2))
            crown_h[fr] = s.canopy + rng.uniform(0.0, 1.4, 2)

        top_h = crown_h + (2.8 if s.canopy else 6.0)
        near = (np.abs(tx) < 0.7) & (tz < 2.8)       # not in the camera's lap
        tx[near] = tx[near] + 2.6
        if s.path:
            cx = centreline(tz)
            margin = s.path + tr + 0.35
            off = tx - cx
            hit = np.abs(off) < margin
            tx[hit] = cx[hit] + np.where(off[hit] < 0, -1.0, 1.0) * margin[hit]
        TX, TZ, TR, TLS = tx[None, :], tz[None, :], tr[None, :], tls[None, :]
        # everything a tree carries sits on the ground where that tree stands
        t_rise = rise(tz)
        RISE_T = t_rise[None, :]
        CY, CR, TOP = ((s.floor + t_rise + crown_h)[None, :], crown_r[None, :],
                       (t_rise + top_h)[None, :])

        n_b = 0 if s.deadwood else int(n_t * s.understory)
        if n_b:
            bz = (1.4 + rng.random(n_b).astype(F32) ** 1.3 * 21.0)
            bx = rng.uniform(-12.0, 12.0, n_b).astype(F32)
            br = rng.uniform(0.55, 1.5, n_b).astype(F32)
            bh = rng.uniform(0.45, 1.25, n_b).astype(F32)
            if s.path:                       # brush lines the path, not on it
                cxb = centreline(bz)
                mb = s.path + br * 0.45
                ob = bx - cxb
                hb = np.abs(ob) < mb
                bx[hb] = cxb[hb] + np.where(ob[hb] < 0, -1.0, 1.0) * mb[hb]
            BX, BZ = bx[None, :], bz[None, :]
            BCY = (s.floor + rise(bz) + bh * 0.3)[None, :]
            bry = bh * 0.6
            BINV, BYINV = (1.0 / br)[None, :], (1.0 / bry)[None, :]
            BSCALE = np.minimum(br, bry)[None, :]

        def air(px, py, pz):
            # height over the ground under this point, and — per tree — over
            # the ground where that tree stands: a trunk is as tall as its
            # own patch of hill, not as tall as the bottom of the slope
            g = py - s.floor - rise(pz)
            yb = (py - s.floor)[:, None] - RISE_T
            disp = rock(px, py, pz) * 0.6
            if s.path:
                c = centreline(pz)
                onp = 1.0 / (1.0 + ((px - c) / s.path) ** 2 * 1.6)
                ground = g - disp * (1.0 - 0.7 * onp) - 0.10 * onp
            else:
                ground = g - disp
            ground = ground / rise_norm

            # trunks: a per-trunk lean, a taper up, a flare at the root
            ybc = np.clip(yb, 0.0, 9.0)
            hx = px[:, None] - TX - TLS * ybc
            hz = pz[:, None] - TZ
            trad = TR * (1.12 - 0.4 * np.clip(yb / 9.0, 0.0, 1.0)
                         - 0.5 * np.clip(yb - 0.9, -0.9, 0.0))
            trunk = np.sqrt(hx * hx + hz * hz) - trad
            trunk = np.maximum(trunk, yb - TOP)
            a = _smin(ground, trunk.min(axis=1), 0.25)

            if s.canopy and not s.deadwood:
                # crowns share the trunk offset — a flattened blob per tree,
                # merged soft so the stand carries one ragged canopy
                cdy = (py[:, None] - CY) * 1.6
                crown = np.sqrt(hx * hx + cdy * cdy + hz * hz) - CR
                # one cheap tap, and it only ever carves the crown back, never
                # bulges it — a bulge hangs threads off the underside
                crown = crown.min(axis=1) + np.clip(
                    0.55 - _noise(px * 0.5 + v, py * 0.4, pz * 0.5),
                    0.0, 0.55) * 2.2
                a = _smin(a, crown, 0.55)

            if n_b:
                qx = (px[:, None] - BX) * BINV
                qy = (py[:, None] - BCY) * BYINV
                qz = (pz[:, None] - BZ) * BINV
                bush = (np.sqrt(qx * qx + qy * qy + qz * qz) - 1.0) * BSCALE
                bush = bush.min(axis=1)
                if detail:
                    bush = bush - (
                        _noise(px * 0.8 - v, py * 0.7, pz * 0.8) - 0.5) * 0.8
                a = _smin(a, bush, 0.3)
            return a

    else:                                            # "void"
        def air(px, py, pz):
            return np.full_like(px, 1.0)

    return air


# --------------------------------------------------------------------------
#  raymarch
# --------------------------------------------------------------------------

def _march(air, dx, dy, dz, steps=44, tmax=34.0, org=None,
           factor=0.62, eps=0.012):
    """Sphere-trace, compacting away rays that have already landed.

    Most rays in a cave hit rock within a few metres, so carrying the whole
    frame through all the steps would be almost entirely wasted work.
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
        landed = a < eps
        t[live] = lt
        hit[live] = landed
        keep = ~(landed | (lt >= tmax))
        if not keep.any():
            break
        live = live[keep]
        # the displacement breaks the Lipschitz bound, so step conservatively
        lt = lt[keep] + np.clip(a[keep] * factor, 0.05, 1.7)
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
_TREE_DEPTH = 30.0    # how far back the stand is planted


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
    if s.kind == "forest":
        mp = dict(steps=44, factor=0.92, eps=0.045)
    elif surface:
        mp = dict(steps=30, factor=0.92, eps=0.03)
    else:
        mp = {}
    t, hit = _march(coarse, dx, dy, dz, **mp)

    hx, hy, hz = dx * t, dy * t, dz * t
    nx, ny, nz = _normal(fine, hx, hy, hz)

    grain = _fbm(hx * 2.4 + s.var, hy * 2.4, hz * 2.4, 3)
    albedo = 0.30 + 0.52 * grain

    if surface:
        # `sky` is the radiance of the sky itself; surfaces get a fraction of
        # it, and how much depends on how much sky they can still see — which
        # is none at all, down a hole.
        sky_occ = np.clip((hy - (s.floor - 1.2)) / 1.5, 0.0, 1.0) ** 1.7
        sky_amt = (0.45 + 0.55 * ny) * sky_occ
        sun = np.clip(nx * -0.70 + ny * 0.34 + nz * -0.62, 0.0, 1.0)
        lit = albedo * s.sky * (0.85 * sky_amt + 0.70 * sun ** 1.6 * sky_occ)
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
    if surface:
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
"trailhead": Scene(kind="forest", trees=19, canopy=6.6, understory=0.9, path=1.7,
                   rise=0.14, floor=-1.5, rough=0.30, freq=0.6, tilt=0.08,
                   palette="dusk", sky=0.42, fog=48.0, var=21.0),
"ridge_trail": Scene(kind="forest", trees=21, canopy=3.4, understory=1.2,
                     path=1.35, rise=0.11, floor=-1.4, rough=0.42, freq=0.7,
                     tilt=0.06, palette="dusk", sky=0.36, fog=40.0, var=22.0),
"blowdown": Scene(kind="forest", trees=30, canopy=7.5, deadwood=True, path=2.4,
                  rise=0.13, floor=-1.3, rough=0.34, freq=0.5, tilt=0.05,
                  palette="dusk", sky=0.40, fog=42.0, var=23.0),
"hollow": Scene(kind="forest", trees=19, canopy=5.2, understory=1.1, path=1.2,
                rise=0.20, floor=-1.35, rough=0.55, freq=0.55, tilt=0.06,
                palette="dusk", sky=0.22, fog=28.0, var=24.0),
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
