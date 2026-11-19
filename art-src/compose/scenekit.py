"""Shared helpers for the doorway, bedroom, CAM 7 and menu scenes (scene_doors.py,
scene_bedroom.py, scene_cam7.py, scene_menu.py).

Everything here builds on common.py and the office's own helpers, so these
pictures use the same materials, the same lighting model and the same finish:

  * paper(): a seamless wallpaper repeat at a real roll width (pixels per metre)
  * wood_grain(): a wood texture tiled at real size, grain along or across
  * panel_door(): a panelled door leaf (or a pair) from real wood photos, with its
    mouldings shaded from a height field (raised and fielded panels, sticking,
    bevels), brass knobs and keyhole plates, grime, kick marks and crazing
  * draw_lod(): draws one long plane (a hall wall or floor) in slices whose
    texture is shrunk to the screen size it covers, so far parts never alias
  * aperture_pattern(): a point light that only shines through an opening
    (the bulb above your door shining into the hall)
  * office_finish(): grades a doorway picture exactly as if it were part of the
    office picture (same edge darkening, the office's vignette at that spot)

Nothing here changes how the office is built.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from common import (Camera, Scene, blur, f32, flatten_light, load, lum, make_seamless, match_albedo,
                    paste_over, pil, rect_mask, resize_f, smoothstep, srgb2lin, tile, value_noise,
                    LANCZOS, BICUBIC)
from grade import finish

_CACHE = {}


# --------------------------------------------------------------------------
# materials
# --------------------------------------------------------------------------
def src(name, **kw):
    """a source texture as float sRGB, colour-matched with match_albedo(**kw) (cached)."""
    k = ('src', name, tuple(sorted(kw.items())))
    if k not in _CACHE:
        _CACHE[k] = match_albedo(f32(load(name)), **kw)
    return _CACHE[k]


def paper(name, roll_m, res, py=None, px=None, flat=120, blend=0.06, **kw):
    """one seamless repeat of a wallpaper photo at `res` px/m, `roll_m` metres wide.
    py / px: the pattern repeat in source pixels (None = the whole sheet)."""
    k = ('paper', name, roll_m, res, py, px, flat, blend, tuple(sorted(kw.items())))
    if k in _CACHE:
        return _CACHE[k]
    a = f32(load(name))
    if flat:
        a = flatten_light(a, flat)
        # also even out slow column/row banding left by the museum lighting
        L = lum(a)
        col = blur(L.mean(0)[None, :], flat / 2)[0]
        row = blur(L.mean(1)[None, :], flat / 2)[0]
        a = a * (L.mean() / col)[None, :, None] * (L.mean() / row)[:, None, None]
    t = make_seamless(a, px=px, py=py, blend=blend)
    w = int(round(roll_m * res))
    h = int(round(roll_m * res * t.shape[0] / t.shape[1]))
    t = resize_f(t, w, h, LANCZOS)
    t = match_albedo(t, **kw) if kw else t
    _CACHE[k] = np.clip(t, 0, 1)
    return _CACHE[k]


def wood_grain(name, w, h, res, real_m, along='x', seed=0, mean=0.30, sat=0.50, tint=(0.84, 0.90, 0.80),
               tone=0.10, contrast=None):
    """wood tiled over w x h px at res px/m (the texture covers real_m metres).
    along='x': grain runs left-right (the photos' own direction), 'y': up-down."""
    t = src(name, mean=mean, sat=sat, tint=tint, contrast=contrast)
    if along == 'y':
        t = np.ascontiguousarray(np.rot90(t))
    s = real_m * res / t.shape[1]
    return tile(t, w, h, seed=seed, tone_var=tone, scale=s)


# --------------------------------------------------------------------------
# relief shading from a height field (mouldings, panels)
# --------------------------------------------------------------------------
_RUG = {}


def rug_field(w, h, res, seed=0, name='rug_lotto-lattice', tile_m=1.25, border_m=0.20, mean=0.26, sat=0.62,
              tint=(1.0, 0.92, 0.95)):
    """A hand-knotted rug of w x h px at res px/m, at a real knot size: the source (a close-up of an old carpet)
    is made seamless and repeated every tile_m metres (its knots end up ~4 mm instead of ~1.3 cm), softened a
    little like a worn pile, with a darker border band, a pale guard stripe and a little wear."""
    key = (name, mean, sat, tuple(tint))
    if key not in _RUG:
        t = match_albedo(f32(load(name)), mean=mean, sat=sat, tint=tint)
        t = blur(t, 0.8)                                                 # the pile, not a needlepoint grid
        _RUG[key] = make_seamless(t, blend=0.16)
    t = _RUG[key]
    rng = np.random.default_rng(seed)
    fx, fy, gx, gy = rng.random(4)                     # (offsets as fractions: the same rug at any resolution)
    sc_ = tile_m * res / t.shape[1]
    tw, th = max(2, round(t.shape[1] * sc_)), max(2, round(t.shape[0] * sc_))
    field = tile(t, w, h, seed=seed, scale=sc_, offset=(int(fx * tw), int(fy * th)), tone_var=0.07, tone_cell=res * 0.8)
    if border_m > 0:
        b = max(2, int(border_m * res))
        # the border: the same wool in a deeper, denser pattern (the source turned on its side, darker)
        r90 = np.ascontiguousarray(np.rot90(t)); s2 = 0.5 * tile_m * res / t.shape[0]
        side = tile(r90, w, h, seed=seed + 1, scale=s2,
                    offset=(int(gx * max(2, round(r90.shape[1] * s2))), int(gy * max(2, round(r90.shape[0] * s2)))))
        side = side * np.array([0.78, 0.66, 0.70], np.float32)
        X = np.arange(w, dtype=np.float32)[None, :] + 0.5
        Y = np.arange(h, dtype=np.float32)[:, None] + 0.5
        d = np.minimum(np.minimum(X, w - X), np.minimum(Y, h - Y))          # px from the rug's edge
        inb = np.clip((b - d) / 1.5 + 0.5, 0, 1)
        field = field * (1 - inb[..., None]) + side * inb[..., None]
        guard = np.exp(-((d - b) / max(1.0, 0.012 * res)) ** 2)             # a pale guard stripe round the field
        field = field * (1 - 0.45 * guard[..., None]) + np.array([0.62, 0.52, 0.36], np.float32) * 0.45 * guard[..., None]
        edge = np.exp(-(d / max(1.0, 0.01 * res)) ** 2)                     # the bound edge, dark
        field = field * (1 - 0.5 * edge[..., None])
    field *= (0.86 + 0.22 * value_noise(w, h, res * 0.35, seed + 7, octaves=3))[..., None]   # wear, flattened pile
    return np.clip(field, 0, 1)


def relief(Hm, res, light=(0.45, 0.55, 0.70), strength=1.6, cavity=0.6):
    """shade (h, w) and ao (h, w) from a height field in metres at res px/m.
    light: direction TO the light in board space (x right, y up, z out of the surface)."""
    gy, gx = np.gradient(Hm * res)          # metres per metre
    # image rows grow downward, board y grows upward
    nx, ny, nz = -gx, gy, np.ones_like(Hm)
    nrm = np.sqrt(nx * nx + ny * ny + nz * nz)
    l = np.asarray(light, np.float32)
    l = l / np.linalg.norm(l)
    ndl = (nx * l[0] + ny * l[1] + nz * l[2]) / nrm
    flat = l[2]
    shade = 1 + strength * (np.clip(ndl, 0, None) / flat - 1) * 0.75
    # cavities: what sits below its surroundings gets less light
    k = max(1.0, 0.012 * res)
    cav = np.clip((blur(Hm, k) - Hm) / 0.004, 0, 1)
    ao = 1 - cavity * cav
    return np.clip(shade, 0.25, 1.9).astype(np.float32), np.clip(ao, 0, 1).astype(np.float32)


def _panel_height(w, h, res, x0, y0, x1, y1, style='raised'):
    """height field (h, w) of one panel opening in a door frame, in metres (0 = frame face)."""
    X = (np.arange(w, dtype=np.float32) + 0.5) / res
    Y = (np.arange(h, dtype=np.float32) + 0.5) / res
    X, Y = np.meshgrid(X, Y)
    d = np.minimum(np.minimum(X - x0, x1 - X), np.minimum(Y - y0, y1 - Y))      # metres inside the opening
    inside = d > 0
    H = np.zeros_like(X)
    dd = np.clip(d, 0, None)
    # sticking moulding: a small bead, then an ogee curving down into the panel groove
    bead = -0.003 * smoothstep(0.0, 0.004, dd)
    ogee = -0.012 * smoothstep(0.004, 0.022, dd)
    if style == 'raised':
        # raised and fielded panel: the bevel rises from the groove up to the flat field
        rise = 0.016 * smoothstep(0.024, 0.072, dd) ** 0.8
        step = 0.002 * smoothstep(0.072, 0.077, dd)           # the little shoulder round the field
        H = np.where(inside, bead + ogee + rise + step, 0.0)
    else:                                                   # flat recessed panel
        H = np.where(inside, bead + ogee, 0.0)
    return H.astype(np.float32)


def panel_door(w_m, h_m, res, *, leaves=2, seed=0, wood='wood_dark-varnished', mean=0.27, sat=0.5,
               tint=(0.84, 0.90, 0.80), light=(0.45, 0.55, 0.70), rows=None, knob='meet', grime=1.0,
               style='raised', hardware=True, paint=None, cols=1, knob_y=1.0):
    """A panelled door (one leaf or a pair) seen straight on, w_m x h_m metres at res px/m.
    Returns (albedo (h, w, 3) with the relief shading baked in, ao (h, w), spec_mask (h, w)).
    rows: per-leaf list of (y0, y1) panel rows in metres from the floor."""
    rng = np.random.default_rng(seed)
    W, H = int(round(w_m * res)), int(round(h_m * res))
    lw = w_m / leaves
    s = min(0.12, lw * 0.19)                                  # stile width
    if rows is None:
        k = h_m / 2.1
        rows = [(0.235 * k, 0.735 * k), (0.925 * k, 1.205 * k), (1.315 * k, 1.975 * k)]
    # ---- wood: stiles and panels with the grain up-down, rails across
    vert = wood_grain(wood, W, H, res, 2.0, along='y', seed=seed, mean=mean, sat=sat, tint=tint, tone=0.08)
    horz = wood_grain(wood, W, H, res, 2.0, along='x', seed=seed + 1, mean=mean, sat=sat, tint=tint, tone=0.08)
    pan = wood_grain(wood, W, H, res, 2.0, along='y', seed=seed + 2, mean=mean * 0.96, sat=sat, tint=tint,
                     tone=0.10)
    alb = vert.copy()
    Hm = np.zeros((H, W), np.float32)
    rails_m = np.zeros((H, W), np.float32)
    panels_m = np.zeros((H, W), np.float32)
    yrow = lambda Y: int(round((h_m - Y) * res))
    xcol = lambda X: int(round(X * res))
    for L in range(leaves):
        lx0 = L * lw
        # rails: everything between the panel rows (and above / below them) inside the stiles
        edges = [0.0] + [v for r in rows for v in r] + [h_m]
        for i in range(0, len(edges), 2):
            ya, yb = edges[i], edges[i + 1]
            rails_m[yrow(yb):yrow(ya), xcol(lx0 + s):xcol(lx0 + lw - s)] = 1
        inner = lw - 2 * s
        mu = 0.09 if cols > 1 else 0.0
        pw_ = (inner - mu * (cols - 1)) / cols
        for (ya, yb) in rows:
            for c in range(cols):
                px0 = lx0 + s + c * (pw_ + mu)
                ph = _panel_height(W, H, res, px0, ya, px0 + pw_, yb, style)
                Hm = Hm + ph
                panels_m[yrow(yb):yrow(ya), xcol(px0):xcol(px0 + pw_)] = 1
    alb = alb * (1 - rails_m[..., None]) + horz * rails_m[..., None]
    # the panel fields: their own boards (inside the sticking)
    field = blur(panels_m, 0.02 * res)
    alb = alb * (1 - field[..., None] * 0.85) + pan * (field[..., None] * 0.85)
    # each member a slightly different board: tone per stile / rail
    for L in range(leaves):
        for (a, b) in ((L * lw, L * lw + s), (L * lw + lw - s, (L + 1) * lw)):
            alb[:, xcol(a):xcol(b)] *= rng.uniform(0.92, 1.08)
    # leaves meet: a dark gap and a bead on the meeting stile
    gap = np.zeros((H, W), np.float32)
    for L in range(1, leaves):
        xm = xcol(L * lw)
        gap[:, max(0, xm - max(1, int(0.003 * res))):xm + max(1, int(0.003 * res))] = 1
        bead_w = 0.018
        Xs = (np.arange(W) + 0.5) / res - L * lw
        bead = np.clip(1 - (Xs / bead_w) ** 2, 0, 1) * 0.004
        Hm += bead[None, :]
    # the leaf edges: a hair of shadow where the door meets its frame
    edge = 1 - rect_mask(W, H, 0, 0, W, H, soft=max(1.5, 0.004 * res))
    gap = np.maximum(gap, edge * 0.8)
    shade, ao = relief(Hm, res, light=light)
    if paint is not None:                                     # painted door: the paint film over the wood
        pcol = np.asarray(paint, np.float32)
        # paint wears through only at the arrises (moulding edges, leaf edges) and round the knob, in small chips
        edges = np.clip(np.abs(np.gradient(Hm, axis=0)) + np.abs(np.gradient(Hm, axis=1)), 0, None) * res * 4
        edges = np.clip(blur(np.clip(edges, 0, 1), 0.004 * res), 0, 1)
        edges = np.maximum(edges, 1 - rect_mask(W, H, 0, 0, W, H, soft=0.012 * res))
        n = value_noise(W, H, max(3.0, 0.012 * res), seed + 40, octaves=2)
        worn = smoothstep(0.70, 0.86, n) * edges * 0.5
        brush = value_noise(W, H, max(2.0, 0.004 * res), seed + 41, octaves=1)    # brush marks along the grain
        film = pcol * (0.95 + 0.06 * brush[..., None]) * (0.96 + 0.08 * lum(alb)[..., None] / max(1e-3, mean))
        alb = film * (1 - worn[..., None]) + alb * worn[..., None]
    alb = alb * shade[..., None]
    # ---- age: grime round the knobs, kick marks low down, crazing in the varnish, dust in the ledges
    X = (np.arange(W, dtype=np.float32) + 0.5) / res
    Y = h_m - (np.arange(H, dtype=np.float32) + 0.5) / res
    Xg, Yg = np.meshgrid(X, Y)
    knobs = []
    if hardware:
        if leaves == 2:
            knobs = [(lw - s * 0.5, knob_y), (lw + s * 0.5, knob_y)]
        elif knob == 'left':
            knobs = [(s * 0.55, knob_y)]
        else:
            knobs = [(w_m - s * 0.55, knob_y)]
    for kx, ky in knobs:
        g = np.exp(-(((Xg - kx) / 0.10) ** 2 + ((Yg - ky) / 0.22) ** 2))
        alb *= (1 - 0.30 * grime * g)[..., None]
    kick = smoothstep(0.30, 0.0, Yg) * (0.6 + 0.4 * value_noise(W, H, 0.05 * res, seed + 3, 2))
    alb = alb * (1 - 0.10 * grime * kick[..., None]) + np.array([0.30, 0.27, 0.25]) * 0.10 * grime * kick[..., None]
    n = value_noise(W, H, max(3, 0.006 * res), seed + 5, octaves=2)
    craze = np.abs(n - 0.5) < 0.010
    alb *= (1 - 0.12 * grime * blur(craze.astype(np.float32), 0.4))[..., None]
    gy = np.gradient(Hm, axis=0) * res                       # ledges facing up collect a little dust
    dust = np.clip(-gy * 3, 0, 1) * 0.10 * grime
    alb = alb * (1 - dust[..., None]) + np.array([0.42, 0.40, 0.42]) * dust[..., None]
    stains = value_noise(W, H, 0.25 * res, seed + 7, octaves=3)
    alb *= (0.90 + 0.14 * stains)[..., None]
    alb *= (1 - 0.85 * gap)[..., None]
    spec = (0.55 + 0.45 * value_noise(W, H, 0.15 * res, seed + 9, 2)) * (1 - gap)
    # ---- brass: knobs and keyhole plates
    if hardware:
        brass = src('metal_brass-brushed', mean=0.46, sat=0.55, tint=(1.0, 0.9, 0.72))
        for kx, ky in knobs:
            # escutcheon plate below the knob, a vertical rounded plate with a keyhole
            pw, phh = 0.034, 0.12
            px0, py1 = kx - pw / 2, ky - 0.035
            m = rect_mask(W, H, px0 * res, (h_m - py1) * res, (px0 + pw) * res, (h_m - py1 + phh) * res,
                          soft=0.004 * res)
            bt = tile(brass, W, H, seed=seed + 11, scale=0.4) * (0.8 + 0.3 * (1 - (Yg - (py1 - phh)) / phh))[..., None]
            alb = alb * (1 - m[..., None]) + bt * m[..., None]
            kh = (np.abs(Xg - kx) < 0.004) & (Yg < py1 - 0.045) & (Yg > py1 - 0.075)
            kh |= ((Xg - kx) ** 2 + (Yg - (py1 - 0.045)) ** 2) < 0.007 ** 2
            alb[kh] *= 0.12
            # the knob: a brass sphere, lit from the light side, a hot spot and a dark underside
            r = 0.030
            d = np.sqrt((Xg - kx) ** 2 + (Yg - ky) ** 2) / r
            km = np.clip((1 - d) * r * res / 1.2, 0, 1)
            lx, ly = light[0], light[1]
            ndl = np.clip(((Xg - kx) / r * lx + (Yg - ky) / r * ly) * 0.6 + np.sqrt(np.clip(1 - d * d, 0, 1)) * 0.8,
                          0, None)
            col = tile(brass, W, H, seed=seed + 13, scale=0.3) * (0.35 + 0.95 * ndl)[..., None]
            hot = np.exp(-(((Xg - kx - lx * r * 0.45) / (r * 0.22)) ** 2 + ((Yg - ky - ly * r * 0.45) / (r * 0.22)) ** 2))
            col = col + hot[..., None] * np.array([0.55, 0.45, 0.30])
            alb = alb * (1 - km[..., None]) + np.clip(col, 0, 1) * km[..., None]
            spec = spec * (1 - km) + 1.6 * km
            # its shadow on the door, away from the light
            sh = np.exp(-(((Xg - kx + lx * 0.02) / 0.035) ** 2 + ((Yg - ky + ly * 0.02 + 0.012) / 0.035) ** 2))
            ao *= 1 - 0.45 * sh * (1 - km)
    return np.clip(alb, 0, 1), np.clip(ao, 0, 1), np.clip(spec, 0, 2)


# --------------------------------------------------------------------------
# drawing long planes without aliasing
# --------------------------------------------------------------------------
def _lerp(a, b, t):
    return a + (b - a) * t


def draw_lod(sc: Scene, corners, alb, *, ao=None, alpha=None, axis=1, n=6, power=1.6, overlap=3, name='plane',
             **kw):
    """Draw the quad `corners` (TL, TR, BR, BL) with texture `alb`, cut into `n` slices along the texture's
    `axis` (1 = left->right, 0 = top->bottom). Slices are spaced so the far ones are short (power > 1 puts
    more cuts toward t=1, i.e. use when the far end is at the right / bottom; power < 1 for the other way),
    and each slice's texture is shrunk to ~1.4x the screen pixels it covers."""
    C = np.asarray(corners, np.float64)
    TL, TR, BR, BL = C
    hh, ww = alb.shape[:2]
    L = ww if axis == 1 else hh
    ts = np.linspace(0, 1, n + 1) ** power if power >= 1 else 1 - np.linspace(1, 0, n + 1) ** (1 / power)
    cam = sc.cam

    def sub(a, i0, i1):
        if a is None:
            return None
        a = np.asarray(a, np.float32)
        k = (a.shape[1] if axis == 1 else a.shape[0]) / L
        j0 = int(round(i0 * k))
        j1 = max(j0 + 2, int(round(i1 * k)))
        return a[:, j0:j1] if axis == 1 else a[j0:j1]

    for i in range(n):
        p0 = int(round(ts[i] * L))
        p1 = min(L, int(round(ts[i + 1] * L)) + (overlap if i < n - 1 else 0))
        if p1 - p0 < 2:
            continue
        t0, t1 = p0 / L, p1 / L
        if axis == 1:
            cs = [_lerp(TL, TR, t0), _lerp(TL, TR, t1), _lerp(BL, BR, t1), _lerp(BL, BR, t0)]
            a = alb[:, p0:p1]
        else:
            cs = [_lerp(TL, BL, t0), _lerp(TR, BR, t0), _lerp(TR, BR, t1), _lerp(TL, BL, t1)]
            a = alb[p0:p1]
        S = cam.project_ss(np.asarray(cs))
        sw = max(np.linalg.norm(S[1] - S[0]), np.linalg.norm(S[2] - S[3]))
        sh = max(np.linalg.norm(S[3] - S[0]), np.linalg.norm(S[2] - S[1]))
        th, tw = a.shape[:2]
        kw_ = min(1.0, 1.4 * sw / max(1, tw))
        kh_ = min(1.0, 1.4 * sh / max(1, th))
        if kw_ < 0.98 or kh_ < 0.98:
            nw, nh = max(2, int(tw * kw_)), max(2, int(th * kh_))
            a = resize_f(a, nw, nh, Image.Resampling.BOX)
        sc.draw_quad(cs, np.clip(a, 0, 1), ao=sub(ao, p0, p1), alpha=sub(alpha, p0, p1), name=f'{name}{i}', **kw)


# --------------------------------------------------------------------------
# lights
# --------------------------------------------------------------------------
def aperture_pattern(pos, x0, x1, y0, y1, zplane, soft=0.02, cone=None, axis=2):
    """pattern for a PointLight at `pos` that only passes through the rectangle x0..x1, y0..y1 on the
    plane z = zplane (soft edges, metres). cone(d) optionally shapes the beam.
    axis=0: the opening is in the plane X = zplane instead, and x0..x1 are its z extent."""
    pos = np.asarray(pos, np.float32)
    a, b = (2, 1) if axis == 0 else (0, 1)

    def pat(d):
        dz = np.where(np.abs(d[:, axis]) < 1e-6, 1e-6, d[:, axis])
        t = (zplane - pos[axis]) / dz
        qx = pos[a] + d[:, a] * t
        qy = pos[b] + d[:, b] * t
        e = np.minimum(np.minimum(qx - x0, x1 - qx), np.minimum(qy - y0, y1 - qy))
        p = np.clip(e / soft + 0.5, 0, 1) * (t > 0)
        if cone is not None:
            p = p * cone(d)
        return p.astype(np.float32)
    return pat


# --------------------------------------------------------------------------
# finishing a doorway picture as part of the office
# --------------------------------------------------------------------------
OFFICE_W, OFFICE_H = 2400, 900


def office_edge_darkness(img_full):
    u = (np.arange(OFFICE_W) + 0.5) / OFFICE_W
    k = 0.28 * (1 - smoothstep(0.0, 0.2, u)) + 0.28 * smoothstep(0.8, 1.0, u)
    return img_full * ((1 - k) ** 2.2)[None, :, None]


def office_finish(lin, x0, y0, kind='door', seed=1, fill=None):
    """Grade a doorway render (linear, h x w) as the patch of the 2400 x 900 office at (x0, y0):
    the same edge darkening, the same vignette and grain scale as office.jpg. Returns sRGB float."""
    h, w = lin.shape[:2]
    full = np.zeros((OFFICE_H, OFFICE_W, 3), np.float32)
    if fill is not None:
        full[:] = fill
    xi, yi = int(round(x0)), int(round(y0))
    full[yi:yi + h, xi:xi + w] = lin
    full = office_edge_darkness(full)
    y = finish(full, kind, seed=seed, return_array=True)
    return y[yi:yi + h, xi:xi + w]


# --------------------------------------------------------------------------
# small utilities
# --------------------------------------------------------------------------
def mean_lum255(img):
    a = f32(img) if isinstance(img, Image.Image) else img
    return float(lum(a).mean() * 255)


def ellipse_mask(w, h, cx, cy, rx, ry, soft=1.5):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx + 0.5 - cx) / rx) ** 2 + ((yy + 0.5 - cy) / ry) ** 2)
    return np.clip((1 - d) * min(rx, ry) / soft + 0.5, 0, 1)


def night_photo(name, crop=None, size=None, lift=0.0, gamma=1.0, tint=(0.62, 0.58, 1.0), hot=0.82, hot_gain=2.5,
                base=0.06):
    """turn a daylight (often black-and-white) photo into a night plate: everything dim and violet,
    only its brightest parts (windows, the light they throw) keep real light. Linear radiance out."""
    a = f32(load(name))
    if crop is not None:
        x0, y0, x1, y1 = crop
        a = a[y0:y1, x0:x1]
    if size is not None:
        a = resize_f(a, size[0], size[1], LANCZOS)
    L = lum(a)
    Lin = srgb2lin(L) ** gamma
    hl = smoothstep(hot, 1.0, L) * hot_gain
    rad = (base * Lin + hl * Lin + lift)[..., None] * np.asarray(tint, np.float32)
    return rad.astype(np.float32)


# --------------------------------------------------------------------------
# a scene that remembers depth (for fog)
# --------------------------------------------------------------------------
from common import persp_coeffs, PERSPECTIVE, BILINEAR  # noqa: E402


class DepthScene(Scene):
    """Scene that also records the depth (camera z, metres) of the last surface drawn over each ss pixel."""

    def __init__(self, cam, ambient, background=(0, 0, 0)):
        super().__init__(cam, ambient, background)
        self.zbuf = np.full((cam.H, cam.W), np.float32(1e4), np.float32)

    def draw_quad(self, corners, tex, *, alpha=None, opacity=1.0, zwrite=True, **kw):
        n0 = len(self.log)
        super().draw_quad(corners, tex, alpha=alpha, opacity=opacity, **kw)
        if not zwrite or len(self.log) == n0:
            return
        _, x0, y0, bw, bh = self.log[-1]
        cam = self.cam
        C = np.asarray(corners, np.float64)
        S = cam.project_ss(C)
        th, tw = (tex.size[1], tex.size[0]) if isinstance(tex, Image.Image) else np.asarray(tex).shape[:2]
        dst = [(float(S[i, 0] - x0), float(S[i, 1] - y0)) for i in range(4)]
        co = persp_coeffs(dst, [(0.0, 0.0), (float(tw), 0.0), (float(tw), float(th)), (0.0, float(th))])

        def warp(a):
            h_, w_ = a.shape
            k = [co[0] * w_ / tw, co[1] * w_ / tw, co[2] * w_ / tw,
                 co[3] * h_ / th, co[4] * h_ / th, co[5] * h_ / th, co[6], co[7]]
            return np.asarray(Image.fromarray(a.astype(np.float32), 'F').transform((bw, bh), PERSPECTIVE, k,
                                                                                    resample=BILINEAR), np.float32)
        cov = warp(np.ones((th, tw), np.float32))
        if alpha is not None:
            cov = cov * np.clip(warp(np.asarray(alpha, np.float32)), 0, 1)
        m = cov * opacity > 0.5
        n = np.cross(C[1] - C[0], C[3] - C[0])
        D = cam.rays(x0, y0, bw, bh)
        dn = (D * n.astype(np.float32)).sum(-1)
        t = float(np.dot(n, C[0] - cam.origin)) / np.where(np.abs(dn) < 1e-9, 1e-9, dn)
        reg = self.zbuf[y0:y0 + bh, x0:x0 + bw]
        reg[m] = t[m]
