"""Shared parts for the six CAMERA ROOMS (1824 x 1026, the size camera pictures are fitted to).

The camera rooms are small 3-D sets built with the same toolkit as the office
(common.py) and finished with the same grade (grade.finish(..., 'cam')).
What this file adds for long rooms seen from a high security camera:

  * ZScene      Scene + a depth buffer (distance fog, water, debug overlays)
  * world noise value noise anchored to world metres (the same stain is in
                the same place whatever resolution a wall piece is painted at)
  * Plane       a floor / ceiling / side wall / back wall painted by a function
                of WORLD coordinates and drawn in depth segments; each segment
                is painted at the resolution it needs and pre-filtered on both
                axes (LANCZOS), so a 40 m hall has no moire and no blurry
                close-ups
  * painters    world-anchored wallpaper (roll seams, stains, tide marks, grime),
                wainscot, mouldings, floor boards, runners, plaster ceilings,
                panel doors and casings
  * dressing    pendant bulbs, framed paintings, night sky with the NASA moon
  * finish_cam  edge darkening + the shared finish (kind 'cam')

Coordinates as in common.py: X right, Y up (floor 0), Z away from the eye,
which sits at (0, eye, 0). A scene can shift its camera sideways by placing
the room off-centre (the eye is always at X = 0).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (Camera, Scene, PointLight, ApertureLight, _ray_box_block, blur, edge_ao, f32, flatten_light, hexcol,  # noqa: F401
                    load, lum, make_seamless, match_albedo, paste_over, persp_coeffs, pil, rect_mask, resize_f,
                    save_jpeg, smoothstep, srgb2lin, lin2srgb, tile, value_noise, find_period, BICUBIC, BILINEAR,
                    LANCZOS, PERSPECTIVE)
from grade import finish
import scene_office as so                      # Board, wood, profile_shade, fluted, rosette, gilt_frame, painting ...

class Board(so.Board):
    """scene_office's Board with slices clamped on both ends (a rectangle wholly outside the board gives an
    empty slice instead of a negative index that would wrap round)."""

    def sl(self, X0, X1, Y0, Y1):
        a, b = int(round(self.px(X0))), int(round(self.px(X1)))
        c, d = int(round(self.py(Y1))), int(round(self.py(Y0)))
        a, b = min(max(0, a), self.w), min(max(0, b), self.w)
        c, d = min(max(0, c), self.h), min(max(0, d), self.h)
        return slice(c, max(c, d)), slice(a, max(a, b))
CW, CH, SS = 1824, 1026, 2                    # camera pictures: W * CAM_ZOOM x H * CAM_ZOOM (1600 x 900 x 1.14)
AMBIENT = np.array((0.25, 0.28, 0.56), np.float32)   # LOOK.md: violet night fill
AMBER = hexcol('#ffb466') * np.array([1.0, 0.93, 0.80], np.float32)
MOON = hexcol('#cfc8ff')
CACHE: dict = {}


# ==========================================================================
# the depth-buffered scene
# ==========================================================================
class ZScene(Scene):
    """Scene that also records the depth (z, metres) of the last surface drawn over each ss pixel."""

    def __init__(self, cam, ambient, background=(0, 0, 0)):
        super().__init__(cam, ambient, background)
        self.zbuf = np.full((cam.H, cam.W), np.float32(1e4), np.float32)

    def draw_quad(self, corners, tex, *, alpha=None, opacity=1.0, zwrite=True, **kw):
        n0 = len(self.log)
        try:
            super().draw_quad(corners, tex, alpha=alpha, opacity=opacity, **kw)
        except np.linalg.LinAlgError:          # a plane seen exactly edge-on projects to a line: nothing to draw
            return
        if not zwrite or len(self.log) == n0:
            return
        _, x0, y0, bw, bh = self.log[-1]
        cam = self.cam
        C = np.asarray(corners, np.float64)
        S = cam.project_ss(C)
        if isinstance(tex, Image.Image):
            tw, th = tex.size
        else:
            th, tw = np.asarray(tex).shape[:2]
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

    def depth_out(self):
        """depth at output resolution (min over each ss block)."""
        s = self.cam.ss
        H, W = self.cam.height, self.cam.width
        return self.zbuf[:H * s, :W * s].reshape(H, s, W, s).min((1, 3))


def make_camera(f, cx, cy, eye):
    return Camera(CW, CH, f, cx, cy, eye, ss=SS)


def ambient_fn(P, N):
    """the violet night fill of LOOK.md: x0.64 facing down, x0.82 walls, x1.0 facing up."""
    up = 0.82 + 0.18 * np.clip(N[:, 1], -1, 1)
    return AMBIENT[None, :] * up[:, None]


# ==========================================================================
# world-anchored noise
# ==========================================================================
def _hash(ix, iy, seed):
    v = np.sin(ix * 127.1 + iy * 311.7 + seed * 74.7 + 0.5) * 43758.5453
    return v - np.floor(v)


def wnoise(U, V, cell, seed, octaves=3, persistence=0.5):
    """smooth value noise (about 0..1, mean 0.5) at world coordinates U, V (metres)."""
    U = np.asarray(U, np.float64)
    V = np.asarray(V, np.float64)
    total = np.zeros(np.broadcast(U, V).shape, np.float64)
    amp, norm, c = 1.0, 0.0, float(cell)
    for o in range(octaves):
        gx, gy = U / c, V / c
        ix, iy = np.floor(gx), np.floor(gy)
        fx, fy = gx - ix, gy - iy
        sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        s = seed + o * 131
        a, b = _hash(ix, iy, s), _hash(ix + 1, iy, s)
        cc, d = _hash(ix, iy + 1, s), _hash(ix + 1, iy + 1, s)
        total += amp * (a + (b - a) * sx + (cc - a) * sy + (a - b - cc + d) * sx * sy)
        norm += amp
        amp *= persistence
        c /= 2.0
    return (total / norm).astype(np.float32)


def bgrid(b: Board, step=1):
    """board coordinates (U along the board's X, V = height) of every (step-th) pixel centre."""
    u = b.x0 + (np.arange(0, b.w, step) + 0.5 * step) / b.res
    v = b.y1 - (np.arange(0, b.h, step) + 0.5 * step) / b.res
    return np.meshgrid(u, v)


def bnoise(b: Board, cell, seed, octaves=3, coarse=None):
    """world noise over a board (evaluated on a coarse grid when the cell is large, then upsampled)."""
    step = coarse or max(1, min(8, int(cell * b.res / 10)))
    U, V = bgrid(b, step)
    n = wnoise(U, V, cell, seed, octaves)
    if step > 1:
        n = resize_f(n, b.w, b.h, BILINEAR)
    return n


# ==========================================================================
# materials
# ==========================================================================
def mat(name, **kw):
    """a source texture colour-matched once (cached)."""
    k = ('mat', name, tuple(sorted(kw.items())))
    if k not in CACHE:
        CACHE[k] = match_albedo(f32(load(name)), **kw)
    return CACHE[k]


def at_res(key, tex, w_m, res, h_m=None):
    """a seamless tile resized to cover w_m (x h_m) metres at `res` px/m (cached, LANCZOS)."""
    h_m = h_m if h_m is not None else w_m * tex.shape[0] / tex.shape[1]
    k = ('res', key, round(res, 3), round(w_m, 4), round(h_m, 4))
    if k not in CACHE:
        CACHE[k] = resize_f(tex, max(2, int(round(w_m * res))), max(2, int(round(h_m * res))), LANCZOS)
    return CACHE[k]


def wtile(t, b: Board, ys: slice, xs: slice, rot=False):
    """world-anchored tiling of the (already resized) tile t over the board region ys, xs."""
    th, tw = t.shape[:2]
    ox = int(math.floor(b.x0 * b.res)) + xs.start
    oy = int(math.floor(-b.y1 * b.res)) + ys.start
    yi = (oy + np.arange(ys.stop - ys.start)) % th
    xi = (ox + np.arange(xs.stop - xs.start)) % tw
    return t[yi][:, xi]


def seamless_paper(name, period_y=None, crop=None, blend=0.08, flatten=120):
    """a wallpaper photo turned into one seamless repeat (whole sheet width = one roll width)."""
    k = ('paper', name, period_y, crop)
    if k in CACHE:
        return CACHE[k]
    a = f32(load(name))
    if crop:
        x0, y0, x1, y1 = crop
        a = a[y0:y1, x0:x1]
    if flatten:
        a = flatten_light(a, flatten)
    if period_y is None:
        t = make_seamless(a, blend=blend)
    else:
        t = make_seamless(a[:period_y + int(period_y * blend) + 2], px=None, py=period_y, blend=blend)
    CACHE[k] = t
    return t


def stain_map(b: Board, ys, xs, seed=5, size_m=4.0, strength=0.45):
    """the real damp-stain photo as a multiplier, world-anchored."""
    st = f32(load('plaster_damp-stained'))
    sL = lum(st)
    sL = (sL / sL.mean())[..., None]
    t = at_res(('stainL',), sL, size_m, b.res)
    m = wtile(t, b, ys, xs)[..., 0]
    return np.clip(1 - strength + strength * m, 0.45, 1.2)


# ==========================================================================
# planes painted in world coordinates and drawn in depth segments
# ==========================================================================
class Plane:
    """kind: 'floor' | 'ceil' (Y = fixed; board X = world x, board Y = world z, row 0 = far end)
             'lwall' (X = fixed, faces +x; board X = z)  'rwall' (X = fixed, faces -x; board X = -z)
             'back'  (Z = fixed, frontal; board X = x, board Y = Y)
    a0..a1: the extent along the board X axis IN WORLD terms (x for floor/ceil/back, z for walls),
    b0..b1: along the board Y axis (z for floor/ceil, Y for walls/back)."""

    def __init__(self, kind, fixed, a0, a1, b0, b1, name=''):
        self.kind, self.fixed, self.a0, self.a1, self.b0, self.b1 = kind, fixed, a0, a1, b0, b1
        self.name = name or kind

    def segment(self, z0, z1):
        """board extents (x0, x1, y0, y1) and world corners TL, TR, BR, BL of the slice z0..z1."""
        k, F = self.kind, self.fixed
        if k in ('floor', 'ceil'):
            x0, x1, y0, y1 = self.a0, self.a1, z0, z1
            C = [(x0, F, z1), (x1, F, z1), (x1, F, z0), (x0, F, z0)]
        elif k == 'lwall':
            x0, x1, y0, y1 = z0, z1, self.b0, self.b1
            C = [(F, y1, z0), (F, y1, z1), (F, y0, z1), (F, y0, z0)]
        elif k == 'rwall':
            x0, x1, y0, y1 = -z1, -z0, self.b0, self.b1
            C = [(F, y1, z1), (F, y1, z0), (F, y0, z0), (F, y0, z1)]
        else:
            x0, x1, y0, y1 = self.a0, self.a1, self.b0, self.b1
            C = [(x0, y1, F), (x1, y1, F), (x1, y0, F), (x0, y0, F)]
        return (x0, x1, y0, y1), C

    def zrange(self):
        if self.kind in ('floor', 'ceil'):
            return self.b0, self.b1
        if self.kind in ('lwall', 'rwall'):
            return self.a0, self.a1
        return self.fixed, self.fixed

    def world(self, b: Board, step=1):
        """world (X, Y, Z) arrays for the board's pixel centres."""
        U, V = bgrid(b, step)
        F = self.fixed
        if self.kind in ('floor', 'ceil'):
            return U, np.full_like(U, F), V
        if self.kind == 'lwall':
            return np.full_like(U, F), V, U
        if self.kind == 'rwall':
            return np.full_like(U, F), V, -U
        return U, V, np.full_like(U, F)


def zbreaks(z0, z1, ratio=1.42, first=None):
    out = [z0]
    z = first or z0 * ratio
    while z < z1:
        out.append(z)
        z *= ratio
    out.append(z1)
    return out


def _px_per_m(cam, P, e):
    P = np.asarray(P, np.float64)
    a = cam.project_ss(P)
    b = cam.project_ss(P + np.asarray(e, np.float64) * 0.01)
    return float(np.hypot(*(b - a))) * 100.0


def draw_plane(sc: ZScene, plane: Plane, painter, breaks=None, max_res=700, min_res=24, overlap=0.04,
               aniso=1.15, **quad_kw):
    """paint and draw a plane, far segments first. painter(board, plane) fills board.alb/.ao/.alpha.
    Each segment is painted at the (capped) resolution its near end needs and then resampled with
    LANCZOS to the resolution each texture axis actually needs (no moire at grazing angles)."""
    cam = sc.cam
    zr0, zr1 = plane.zrange()
    if plane.kind == 'back' or breaks is None:
        breaks = [zr0, zr1] if plane.kind != 'back' else [zr0, zr0]
    segs = list(zip(breaks[:-1], breaks[1:]))
    for i, (s0, s1) in reversed(list(enumerate(segs))):
        e0 = s0 if i == 0 else max(zr0, s0 - overlap)
        (x0, x1, y0, y1), C = plane.segment(e0, s1)
        Cn = np.asarray(C, np.float64)
        ex = (Cn[1] - Cn[0]) / max(1e-6, np.linalg.norm(Cn[1] - Cn[0]))
        ey = (Cn[0] - Cn[3]) / max(1e-6, np.linalg.norm(Cn[0] - Cn[3]))
        ra = max(_px_per_m(cam, P, ex) for P in Cn if P[2] > 0.05)
        rb = max(_px_per_m(cam, P, ey) for P in Cn if P[2] > 0.05)
        R = float(np.clip(max(ra, rb), min_res, max_res))
        b = Board(x0, x1, y0, y1, R)
        painter(b, plane)
        alb, ao, al, em = b.alb, b.ao, b.alpha, b.emis
        wt = max(2, int(round((x1 - x0) * min(R, max(min_res, ra * aniso)))))
        ht = max(2, int(round((y1 - y0) * min(R, max(min_res, rb * aniso)))))
        if wt < b.w or ht < b.h:
            wt, ht = min(wt, b.w), min(ht, b.h)
            alb = resize_f(alb, wt, ht, LANCZOS)
            ao = resize_f(ao, wt, ht, LANCZOS)
            al = resize_f(al, wt, ht, LANCZOS)
            if em is not None:
                em = resize_f(em, wt, ht, LANCZOS)
        kw = dict(quad_kw)
        if em is not None and em.max() > 0:
            kw['emissive'] = np.clip(em, 0, 1)
            kw.setdefault('emit', 1.0)
        sc.draw_quad(C, np.clip(alb, 0, 1), ao=np.clip(ao, 0, 1),
                     alpha=(np.clip(al, 0, 1) if al.min() < 0.999 else None),
                     name=f'{plane.name}[{i}]', **kw)


# ==========================================================================
# painters (world coordinates)
# ==========================================================================
def wood_tile(name, real_m, res, mean=0.30, sat=0.50, tint=(0.84, 0.90, 0.80), contrast=None, rot=False):
    t = mat(name, mean=mean, sat=sat, tint=tint, contrast=contrast)
    if rot:
        t = np.ascontiguousarray(np.rot90(t))
    return at_res((name, mean, sat, tint, contrast, rot), t, real_m, res)


def hmoulding_w(b: Board, Y0, Y1, profile, wood_name='wood_dark-varnished', mean=0.30, shadow=0.35, real_m=2.0):
    ys, xs = b.sl(b.x0, b.x1, Y0, Y1)
    hh = ys.stop - ys.start
    if hh <= 0 or xs.stop <= xs.start:
        return
    t = wtile(wood_tile(wood_name, real_m, b.res, mean=mean), b, ys, xs)
    if hh >= 3:
        pr = np.interp(np.linspace(0, 1, hh), np.linspace(0, 1, len(profile)), profile)
        t = t * so.profile_shade(hh, pr)[:, None, None]
    else:
        t = t * 0.85
    b.alb[ys, xs] = np.clip(t, 0, 1)
    if shadow:
        b.shadow(b.x0, b.x1, Y0, Y1, shadow, 0.012, dy=-0.012)


def paper_band(b: Board, Y0, Y1, tile_srgb, roll_w, seed, age=1.0, seams=True, stains=True, key='paper',
               repeat_w=None):
    """wallpaper between heights Y0..Y1: world-anchored repeat, roll seams, damp stains, tide marks,
    grime toward the cornice and the dado, streaks."""
    ys, xs = b.sl(b.x0, b.x1, Y0, Y1)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    if hh <= 0 or ww <= 0:
        return
    t = at_res(('paper', key, repeat_w or roll_w), tile_srgb, repeat_w or roll_w, b.res)
    paper = wtile(t, b, ys, xs).copy()
    U = b.x0 + (np.arange(xs.start, xs.stop) + 0.5) / b.res
    Yv = b.y1 - (np.arange(ys.start, ys.stop) + 0.5) / b.res
    UU, YY = np.meshgrid(U, Yv)
    if seams:
        sd = np.abs((U / roll_w) % 1.0)
        sd = np.minimum(sd, 1 - sd) * roll_w * b.res
        paper *= (1 - 0.10 * np.exp(-(sd / 1.2) ** 2))[None, :, None]
    # slow tone variation (fading, sun-bleach)
    tv = wnoise(UU[::4, ::4], YY[::4, ::4], 1.1, seed + 3, 2)
    tv = resize_f(tv, ww, hh, BILINEAR)
    paper *= (1 + 0.10 * age * (tv * 2 - 1))[..., None]
    if stains:
        paper *= stain_map(b, ys, xs, seed, strength=0.40 * age)[..., None] * np.array([1.0, 0.98, 0.95], np.float32)
        n = wnoise(UU[::2, ::2], YY[::2, ::2], 0.75, seed + 9, 3)
        n = resize_f(n, ww, hh, BILINEAR)
        tide = smoothstep(0.66, 0.70, n) * 0.16 + smoothstep(0.70, 0.88, n) * 0.12
        paper *= (1 - tide * age)[..., None]
        g = 1 - 0.22 * smoothstep(Y1 - 0.6, Y1, YY) - 0.12 * smoothstep(Y0 + 0.35, Y0, YY)
        paper *= g[..., None]
        sx = wnoise(U, np.zeros_like(U), 0.06, seed + 11, 1)
        streak = smoothstep(0.80, 0.95, sx)[None, :] * smoothstep(Y1 - 1.4, Y1, YY)
        paper *= (1 - 0.22 * age * streak)[..., None]
    b.alb[ys, xs] = np.clip(paper, 0, 1)


def plaster_band(b: Board, Y0, Y1, name='plaster_aged-worn', size_m=1.8, mean=0.30, sat=0.45,
                 tint=(0.95, 0.93, 1.0), seed=0, soot=0.35):
    ys, xs = b.sl(b.x0, b.x1, Y0, Y1)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    if hh <= 0 or ww <= 0:
        return
    p = mat(name, mean=mean, sat=sat, tint=tint)
    t = wtile(at_res((name, mean, sat, tint), p, size_m, b.res), b, ys, xs)
    Yv = b.y1 - (np.arange(ys.start, ys.stop) + 0.5) / b.res
    t = t * (1 - soot * smoothstep(Y1 - 0.3, Y1, Yv))[:, None, None]
    b.alb[ys, xs] = np.clip(t, 0, 1)


def wainscot_row(b: Board, Y0, Y1, mean=0.27, sat=0.5, rows=1, panel_w=None):
    """raised panels from the real wainscot photo-texture (one or more rows), world-anchored."""
    pan = mat('panel_wainscot-raised', mean=mean, sat=sat, tint=(0.84, 0.90, 0.80))
    key = ('aoW',)
    if key not in CACHE:
        ao = f32(load('panel_wainscot-raised_ao'))[..., 0]
        CACHE[key] = resize_f(ao, pan.shape[1], pan.shape[0])
    ao = CACHE[key]
    r = pan.shape[0] / 5
    r0, r1 = int(r * 1 - r * 0.08), int(r * 1 + r * rows + r * 0.02)
    row = pan[r0:r1] * (0.55 + 0.45 * ao[r0:r1])[..., None]
    ys, xs = b.sl(b.x0, b.x1, Y0, Y1)
    hh = ys.stop - ys.start
    if hh <= 0:
        return
    # the texture is 2.1 m square with 2 panel columns: a panel is ~1.05 m wide at real scale;
    # panel_w (m) squeezes the columns to narrower panels
    real_w = 2.1 * (row.shape[1] / pan.shape[1])
    if panel_w:
        real_w = panel_w * 2
    t = at_res(('wain', mean, sat, rows, panel_w, round(Y1 - Y0, 4)), row, real_w, b.res, h_m=(Y1 - Y0))
    # anchor vertically to the row itself (not the world), horizontally to the world
    th, tw = t.shape[:2]
    ox = int(math.floor(b.x0 * b.res)) + xs.start
    xi = (ox + np.arange(xs.stop - xs.start)) % tw
    yi = np.clip(np.arange(hh), 0, th - 1)
    b.alb[ys, xs] = t[yi][:, xi]


def dado_w(b: Board, top=0.92, skirt=0.16, seed=0, mean=0.27):
    wainscot_row(b, skirt + 0.01, top - 0.04, mean=mean)
    hmoulding_w(b, top - 0.04, top, [0, .6, 1, .9, .5, .7, .3, 0], mean=0.28, shadow=0.45)
    hmoulding_w(b, 0.0, skirt, [.9, 1, .7, .62, .6, .6, .6, .6, .6, .6, .58, .55], mean=0.22, shadow=0.0)
    ys = np.arange(b.h)
    b.ao *= (1 - 0.35 * np.exp(-np.clip(b.py(0) - ys, 0, None) / (0.05 * b.res)))[:, None]


# which way the planks run in each floor source image ('h' = across the image, 'v' = up/down)
PLANKS = {'floor_old-oak-dark': 'h', 'floor_dark-planks-grey': 'h', 'floor_old-worn-dark': 'h',
          'floor_worn-planks-weathered': 'v', 'floor_painted-distressed': 'v', 'floor_painted-black': 'v',
          'floor_stair-treads': 'v', 'floor_dark-varnished': 'v'}


def floor_boards(b: Board, name='floor_old-oak-dark', real_m=2.03, mean=0.30, sat=0.75, tint=(1.0, 0.93, 0.88),
                 along_z=True, seed=0):
    """boards running along z (or across when along_z=False), whatever way the source photo has them."""
    t = mat(name, mean=mean, sat=sat, tint=tint)
    runs = PLANKS.get(name, 'h')
    # board texture: x = world x, y = world z -> planks along z means 'v' in the texture
    if (along_z and runs == 'h') or (not along_z and runs == 'v'):
        t = np.ascontiguousarray(np.rot90(t))
    tt = at_res(('floor', name, mean, sat, tint, along_z), t, real_m, b.res)
    ys, xs = slice(0, b.h), slice(0, b.w)
    out = wtile(tt, b, ys, xs).copy()
    n = bnoise(b, 1.3, seed + 1, 2)
    out *= (1 + 0.12 * (n * 2 - 1))[..., None]
    b.alb[:] = np.clip(out, 0, 1)


def runner(b: Board, x0, x1, src='rug_star-ushak', mean=0.24, sat=0.62, tint=(1.0, 0.86, 0.90), repeat_m=2.2,
           seed=0, wear=0.25):
    """a long carpet runner along z between x0..x1 (world), pattern repeating every repeat_m metres."""
    k = ('runner', src, mean, sat, tint)
    if k not in CACHE:
        r = f32(load(src))
        if r.shape[1] > r.shape[0]:
            r = np.ascontiguousarray(np.rot90(r))         # long axis along z
        r = match_albedo(r, mean=mean, sat=sat, tint=tint)
        r = make_seamless(r, blend=0.10)
        CACHE[k] = r
    r = CACHE[k]
    w_m = x1 - x0
    t = at_res(k + (w_m, repeat_m), r, w_m, b.res, h_m=repeat_m)
    ys, xs = b.sl(x0, x1, b.y0, b.y1)
    if xs.stop <= xs.start:
        return
    th, tw = t.shape[:2]
    oy = int(math.floor(-b.y1 * b.res)) + ys.start
    yi = (oy + np.arange(ys.stop - ys.start)) % th
    xi = np.clip(np.round((b.x0 + (np.arange(xs.start, xs.stop) + 0.5) / b.res - x0) * b.res - 0.5).astype(int),
                 0, tw - 1)
    rr = t[yi][:, xi].copy()
    U, V = bgrid(b)
    U, V = U[ys, xs], V[ys, xs]
    n = wnoise(U[::3, ::3], V[::3, ::3], 0.5, seed + 7, 3)
    n = resize_f(n, rr.shape[1], rr.shape[0], BILINEAR)
    centre = 1 - np.abs((U - (x0 + x1) / 2) / (w_m / 2))
    rr *= (1 - wear * smoothstep(0.45, 0.8, n) * smoothstep(0.2, 0.7, centre))[..., None]   # trodden path
    edge = np.clip(np.minimum(U - x0, x1 - U) * b.res / 1.5, 0, 1)
    b.alb[ys, xs] = rr * edge[..., None] + b.alb[ys, xs] * (1 - edge[..., None])
    # the runner's edges throw a hairline shadow / the boards beside it are darker (dust)
    ao = np.exp(-np.maximum(0, np.minimum(np.abs(U - x0), np.abs(U - x1))) / 0.02)
    b.ao[ys, xs] *= 1 - 0.25 * ao * (1 - edge)


def ceiling_plaster(b: Board, name='plaster_ceiling-textured', size_m=2.0, mean=0.27, seed=0, cracks=True):
    p = mat(name, mean=mean, sat=0.30, tint=(0.95, 0.95, 1.0))
    t = wtile(at_res((name, mean), p, size_m, b.res), b, slice(0, b.h), slice(0, b.w)).copy()
    n = bnoise(b, 1.5, seed + 3, 3)
    t *= (1 + 0.15 * (n * 2 - 1))[..., None]
    if cracks:
        st = stain_map(b, slice(0, b.h), slice(0, b.w), seed + 1, size_m=3.0, strength=0.35)
        t *= st[..., None]
    b.alb[:] = np.clip(t, 0, 1)


# ---------------------------------------------------------------- doors
def panel_door(w, h, res_unused=None, mean=0.25, cols=2, rows=4, wood_name='wood_dark-varnished', seed=0,
               painted=None):
    """a raised-panel door leaf (w x h px) cut from the real wainscot photo-texture (+ AO), with a knob."""
    pan = mat('panel_wainscot-raised', mean=mean, sat=0.5, tint=(0.84, 0.90, 0.80))
    key = ('aoW',)
    if key not in CACHE:
        ao = f32(load('panel_wainscot-raised_ao'))[..., 0]
        CACHE[key] = resize_f(ao, pan.shape[1], pan.shape[0])
    ao = CACHE[key]
    a = pan * (0.5 + 0.5 * ao)[..., None]
    # the texture is 2 columns x 5 rows of panels; take `rows` rows and both columns
    r = a.shape[0] / 5
    blk = a[int(r * 0.5):int(r * (0.5 + rows))]
    if cols == 1:
        blk = blk[:, :blk.shape[1] // 2 + 8]
    # stiles/rails: a margin of plain wood round the panels
    mx, my = int(w * 0.10), int(h * 0.05)
    t = so.wood(wood_name, w, h, w / 0.9, 2.0, rot=True, seed=seed, mean=mean)
    inner = resize_f(blk, w - 2 * mx, h - 2 * my, LANCZOS)
    t[my:h - my, mx:w - mx] = inner
    if painted is not None:
        L = lum(t)[..., None]
        t = np.clip(L / max(1e-3, float(L.mean())) * np.asarray(painted, np.float32), 0, 1)
    # edge bevel + a brass knob
    e = rect_mask(w, h, 0, 0, w, h, soft=max(2, w * 0.02))
    t *= (0.8 + 0.2 * e)[..., None]
    kx, ky, kr = int(w * 0.86), int(h * 0.52), max(2, int(w * 0.035))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xx - kx) ** 2 + (yy - ky) ** 2)
    km = np.clip(kr - d + 0.5, 0, 1)
    brass = np.array([0.55, 0.42, 0.22], np.float32) * (0.7 + 0.6 * np.clip(1 - d / kr, 0, 1))[..., None]
    t = t * (1 - km[..., None]) + brass * km[..., None]
    plate = rect_mask(w, h, kx - kr * 0.8, ky + kr * 1.6, kx + kr * 0.8, ky + kr * 3.6, soft=1)
    t = t * (1 - 0.5 * plate[..., None]) + plate[..., None] * np.array([0.30, 0.24, 0.14]) * 0.5
    return np.clip(t, 0, 1)


def victorian_door(w, h, paint=(0.50, 0.46, 0.40), seed=0, w_m=0.92, h_m=2.15, wood_name=None, mean=0.26,
                   knob=True, grime=0.35):
    """a classic four-panel door leaf (w x h px): stiles and rails, two tall upper and two lower raised
    panels with bevels lit from the upper left, real wood or painted wood (paint = sRGB albedo colour,
    detail from the wood photo), grime from the damp-stain photo, a brass knob and escutcheon."""
    rx, ry = w / w_m, h / h_m                       # px per metre
    base_name = wood_name or 'wood_fine-grain-old'
    t = so.wood(base_name, w, h, max(rx, ry), 0.6 if wood_name is None else 2.0, rot=True, seed=seed, mean=mean)
    if paint is not None:
        L = lum(t)[..., None]
        L = 1 + 0.55 * (L / max(1e-3, float(L.mean())) - 1)
        t = np.clip(L * np.asarray(paint, np.float32), 0, 1)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    X, Y = (xx + 0.5) / rx, h_m - (yy + 0.5) / ry       # metres, Y up from the bottom
    st, mu = 0.12, 0.10
    panels = [(st, w_m / 2 - mu / 2, 1.17, h_m - 0.13), (w_m / 2 + mu / 2, w_m - st, 1.17, h_m - 0.13),
              (st, w_m / 2 - mu / 2, 0.24, 0.98), (w_m / 2 + mu / 2, w_m - st, 0.24, 0.98)]
    shade = np.ones((h, w), np.float32)
    bev = 0.035
    for (x0, x1, y0, y1) in panels:
        dl, dr, db, dt = X - x0, x1 - X, Y - y0, y1 - Y
        inside = (dl > 0) & (dr > 0) & (db > 0) & (dt > 0)
        d = np.minimum(np.minimum(dl, dr), np.minimum(db, dt))
        inb = inside & (d < bev)
        # which bevel: the nearest edge
        which = np.argmin(np.stack([dl, dr, db, dt]), 0)
        val = np.array([1.12, 0.84, 0.74, 1.20], np.float32)[which]
        shade = np.where(inb, val, shade)
        edge = inside & (d < 0.006)
        shade = np.where(edge, 0.55, shade)
        # the moulding round the panel: a thin dark groove just outside it
        out = (~inside) & (np.maximum(np.maximum(-dl, -dr), np.maximum(-db, -dt)) < 0.008)
        shade = np.where(out, shade * 0.7, shade)
    shade = blur(shade, max(0.5, min(rx, ry) * 0.0025))
    t = t * shade[..., None]
    # grime: the real damp-stain photo, darker toward the bottom and round the knob
    if grime > 0:
        stn = f32(load('plaster_damp-stained'))
        sL = lum(stn)
        sL = sL / sL.mean()
        g = resize_f(sL[(seed * 37) % 300:(seed * 37) % 300 + 500, (seed * 53) % 300:(seed * 53) % 300 + 240], w, h,
                     BILINEAR)
        t *= np.clip(1 - grime + grime * g, 0.4, 1.15)[..., None]
        t *= (1 - 0.18 * smoothstep(0.5, 0.0, Y))[..., None]
        hand = np.exp(-(((X - (w_m - 0.10)) / 0.08) ** 2 + ((Y - 1.02) / 0.14) ** 2))
        t *= (1 - 0.25 * hand)[..., None]
    if knob:
        kx, ky = w_m - 0.075, 1.0
        r = 0.028
        d = np.sqrt((X - kx) ** 2 + (Y - ky) ** 2)
        km = np.clip((r - d) * rx + 0.5, 0, 1)
        brass = np.array([0.55, 0.42, 0.22], np.float32) * (0.6 + 0.7 * np.clip(1 - d / r, 0, 1))[..., None]
        plate = np.clip((0.022 - np.abs(X - kx)) * rx + 0.5, 0, 1) * np.clip((0.09 - np.abs(Y - (ky - 0.03))) * ry + 0.5,
                                                                           0, 1)
        t = t * (1 - 0.6 * plate[..., None]) + plate[..., None] * np.array([0.30, 0.24, 0.14]) * 0.6
        t = t * (1 - km[..., None]) + brass * km[..., None]
    e = rect_mask(w, h, 0, 0, w, h, soft=max(1.5, w * 0.012))
    t *= (0.75 + 0.25 * e)[..., None]
    return np.clip(t, 0, 1)


def door_on_board(b: Board, s0, s1, top, seed, leaf=None, ajar=0.0, casing=0.11, mean=0.25, gap_glow=None,
                  dark=0.03, painted=None):
    """a doorway on a wall board between s0..s1 (board X, metres) up to `top`: fluted casing with
    bullseye blocks and plinths, a panel door leaf (or `leaf`), ajar = fraction of the opening that is a
    dark gap (on the latch side, s1)."""
    res = b.res
    cw = casing
    for side, (a, c) in enumerate(((s0 - cw, s0), (s1, s1 + cw))):
        ys, xs = b.sl(a, c, 0.0, top + cw)
        hh, ww = ys.stop - ys.start, xs.stop - xs.start
        if hh > 3 and ww > 3:
            b.alb[ys, xs] = so.fluted(ww, hh, seed + side)
            b.alpha[ys, xs] = 1
        b.shadow(a, c, 0, top + cw, 0.45, 0.018, dy=-0.004)
    ys, xs = b.sl(s0, s1, top, top + cw)
    if ys.stop - ys.start > 3 and xs.stop - xs.start > 3:
        b.alb[ys, xs] = so.fluted(xs.stop - xs.start, ys.stop - ys.start, seed + 3, vertical=False)
    b.shadow(s0 - cw, s1 + cw, top, top + cw, 0.45, 0.02, dy=-0.006)
    rs = int(round((cw + 0.012) * res))
    if rs >= 4:
        for xc in (s0 - cw / 2, s1 + cw / 2):
            b.put(xc - (cw + 0.012) / 2, xc + (cw + 0.012) / 2, top - 0.006, top + cw + 0.006, so.rosette(rs + 2, seed + 7))
    # cap
    Yc = top + cw + 0.006
    ys, xs = b.sl(s0 - cw - 0.02, s1 + cw + 0.02, Yc, Yc + 0.07)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    if hh > 3 and ww > 3:
        t = so.wood('wood_dark-varnished', ww, hh, res, 2.0, seed=seed + 8, mean=0.30)
        pr = np.interp(np.linspace(0, 1, hh), np.linspace(0, 1, 9), [.9, 1, .8, .5, .7, .9, .6, .3, .2])
        b.alb[ys, xs] = t * so.profile_shade(hh, pr * 3)[:, None, None]
        b.shadow(s0 - cw - 0.02, s1 + cw + 0.02, Yc, Yc + 0.07, 0.55, 0.025, dy=-0.02)
    # plinths
    for a, c in ((s0 - cw - 0.008, s0), (s1, s1 + cw + 0.008)):
        ys, xs = b.sl(a, c, 0.0, 0.24)
        hh, ww = ys.stop - ys.start, xs.stop - xs.start
        if hh > 1 and ww > 1:
            t = so.wood('wood_dark-varnished', ww, hh, res, 2.0, seed=seed + 9, mean=0.24)
            e = rect_mask(ww, hh, 0, 0, ww, hh, soft=max(1, ww * 0.08))
            b.alb[ys, xs] = np.clip(t * (0.75 + 0.25 * e)[..., None], 0, 1)
    # the leaf
    ys, xs = b.sl(s0, s1, 0.0, top)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    if hh > 2 and ww > 2:
        lf = leaf if leaf is not None else victorian_door(ww, hh, paint=painted, seed=seed, w_m=s1 - s0, h_m=top,
                                                          mean=mean)
        if lf.shape[:2] != (hh, ww):
            lf = resize_f(lf, ww, hh, LANCZOS)
        b.alb[ys, xs] = lf
        # inset: the leaf sits back in the frame (soft shadow from the casing on it)
        inset = 1 - 0.55 * (1 - rect_mask(ww, hh, 0, 0, ww, hh + 50, soft=max(1.5, 0.02 * res)))
        b.ao[ys, xs] *= inset
        if ajar > 0:
            g0 = int(round(ww * (1 - ajar)))
            gap = np.zeros((hh, ww), np.float32)
            gap[:, g0:] = 1
            gap = blur(gap, max(0.6, 0.004 * res))
            b.alb[ys, xs] = b.alb[ys, xs] * (1 - gap[..., None]) + dark * gap[..., None]
            b.ao[ys, xs] *= 1 - 0.9 * gap
            if gap_glow is not None:
                if b.emis is None:
                    b.emis = np.zeros_like(b.alb)
                gl = gap * np.linspace(0.6, 1.0, hh)[:, None]
                b.emis[ys, xs] += gl[..., None] * np.asarray(gap_glow, np.float32)
        if gap_glow is not None and ajar <= 0:      # light under the door
            if b.emis is None:
                b.emis = np.zeros_like(b.alb)
            ys2, xs2 = b.sl(s0 + 0.02, s1 - 0.02, 0.0, 0.012)
            if ys2.stop > ys2.start:
                b.emis[ys2, xs2] += np.asarray(gap_glow, np.float32)
    b.ao *= 1 - 0.0


# ---------------------------------------------------------------- dressing
def bulb_pattern(open_down=62.0, side=0.25, up=0.18):
    """a small glass shade: full light downward within open_down degrees, dimmer to the sides, a little up."""
    def pat(d):
        down = np.degrees(np.arccos(np.clip(-d[:, 1], -1, 1)))
        return (side + (1 - side) * (1 - smoothstep(open_down - 8, open_down + 8, down)) +
                up * smoothstep(100, 150, down)).astype(np.float32)
    return pat


def pendant(sc: ZScene, x, y_bulb, z, ceil_y, glow=1.0, shade='bell', seed=0):
    """a hanging lamp: cord from the ceiling, a small frosted bell shade (emissive), drawn as camera-facing quads."""
    cam = sc.cam
    res = cam.f / z * cam.ss
    # cord
    cw = 0.008
    tex = np.zeros((8, 4, 3), np.float32) + 0.06
    sc.draw_quad([(x - cw, ceil_y, z), (x + cw, ceil_y, z), (x + cw, y_bulb + 0.12, z), (x - cw, y_bulb + 0.12, z)],
                 tex, name='cord', zwrite=False)
    # ceiling rose
    rw = 0.07
    w, h = max(4, int(rw * 2 * res)), max(3, int(0.035 * res))
    brass = mat('metal_brass-brushed', mean=0.35, sat=0.5, tint=(1.0, 0.9, 0.72))
    rt = tile(brass, w, h, seed=seed, scale=0.3)
    sc.draw_quad([(x - rw, ceil_y, z), (x + rw, ceil_y, z), (x + rw, ceil_y - 0.035, z), (x - rw, ceil_y - 0.035, z)],
                 rt, name='rose', zwrite=False)
    # shade: a bell 0.24 m wide, 0.16 m tall; frosted glass lit from inside
    sw, sh = 0.13, 0.17
    w, h = max(6, int(sw * 2 * res)), max(5, int(sh * res))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = yy / max(1, h - 1)
    half = (0.22 + 0.78 * np.sqrt(np.clip(v, 0, 1))) * w / 2
    a = np.clip((half - np.abs(xx - w / 2)) / 1.2, 0, 1) * np.clip((h - 1 - yy) / 1.2 + 1, 0, 1)
    across = (xx - w / 2) / np.maximum(half, 1)
    em = (0.35 + 0.65 * v ** 1.5) * (1 - 0.5 * across ** 2)
    emc = em[..., None] * np.array([1.0, 0.86, 0.62], np.float32)
    rim = (v > 0.9)
    emc *= np.where(rim, 1.35, 1.0)[..., None]
    alb = np.zeros((h, w, 3), np.float32) + 0.4
    sc.draw_quad([(x - sw, y_bulb + sh * 0.6, z), (x + sw, y_bulb + sh * 0.6, z), (x + sw, y_bulb - sh * 0.4, z),
                  (x - sw, y_bulb - sh * 0.4, z)], alb * 0.3, alpha=a, emissive=np.clip(emc, 0, 1), emit=2.2 * glow,
                 lit=False, name='shade', zwrite=False)
    # the hot bulb peeking under the rim
    u, vv = cam.project((x, y_bulb - sh * 0.38, z))
    sc.glow(u, vv, max(2.0, 0.05 * cam.f / z), AMBER * np.array([1.0, 0.95, 0.85]), 1.6 * glow, 1.5)


def sconce(sc: ZScene, xw, side, y, z, glow=1.0, seed=0, power=1.6):
    """a wall sconce: a dark brass bracket and a frosted tulip shade standing 0.16 m off the wall.
    side = +1 for a wall on the left (shade at xw + 0.16), -1 on the right. Returns the shade centre."""
    cam = sc.cam
    xs = xw + side * 0.16
    res = cam.f / z * cam.ss
    brass = mat('metal_brass-brushed', mean=0.30, sat=0.5, tint=(1.0, 0.9, 0.72))
    # bracket: a short arm from the wall plate to the cup (drawn in the plane z, facing the camera)
    a0, a1 = sorted((xw + side * 0.005, xs))
    t = tile(brass, max(4, int((a1 - a0) * res)), max(3, int(0.025 * res)), seed=seed, scale=0.3) * 0.7
    sc.draw_quad([(a0, y - 0.05, z), (a1, y - 0.05, z), (a1, y - 0.075, z), (a0, y - 0.075, z)], t, name='arm',
                 zwrite=False)
    # back plate on the wall (a small vertical oval)
    pw, ph = 0.05, 0.16
    w, h = max(4, int(pw * 2 * res * 0.2) + 4), max(6, int(ph * res))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    m = np.clip((1 - (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)) * 4, 0, 1)
    pt = tile(brass, w, h, seed=seed + 1, scale=0.3) * 0.8
    zx = xw + side * 0.004
    sc.draw_quad([(zx, y + 0.02, z - pw), (zx, y + 0.02, z + pw), (zx, y - 0.14, z + pw), (zx, y - 0.14, z - pw)],
                 pt, alpha=m, name='plate', zwrite=False)
    _tulip(sc, xs, y, z, glow)
    return np.array([xs, y, z], np.float32)


def _tulip(sc: ZScene, xs, y, z, glow=1.0):
    """the frosted tulip shade (camera-facing), open at the top: seen from above, the rim is an ellipse and
    the bulb glows inside it; the frosted glass is brightest low down, its edges darker (thicker glass)."""
    cam = sc.cam
    res = cam.f / z * cam.ss
    sw, sh = 0.075, 0.15
    w, h = max(6, int(sw * 2 * res)), max(6, int(sh * 1.25 * res))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rim_y = h * 0.20                                   # centre line of the rim ellipse
    v = np.clip((yy - rim_y) / max(1, h - 1 - rim_y), 0, 1)
    half = (1.0 - 0.62 * v ** 1.4) * w / 2 * 0.96
    body = np.clip((half - np.abs(xx - w / 2)) / 1.2, 0, 1) * (yy >= rim_y) * np.clip((h - 1 - yy) / 1.5 + 0.2, 0, 1)
    ell = (((xx - w / 2) / (w / 2 * 0.96)) ** 2 + ((yy - rim_y) / max(1.0, h * 0.13)) ** 2)
    top = np.clip((1 - ell) * 6, 0, 1)
    a = np.maximum(body, top)
    across = (xx - w / 2) / np.maximum(half, 1)
    em = (0.45 + 0.40 * v) * (1 - 0.55 * across ** 2) * body
    inner = np.clip((1 - ell) * 3, 0, 1)
    em = np.maximum(em, 0.35 * top + 0.75 * inner ** 2)
    rimline = np.exp(-((np.sqrt(ell) - 1) / 0.08) ** 2) * (yy < rim_y + h * 0.15)
    em = em * (1 - 0.35 * rimline)
    ribs = 1 - 0.18 * np.cos(np.clip(across, -1, 1) * math.pi * 3.5) ** 6 * body
    em = em * ribs
    # warm frosted glass: amber at the edges, paler where the bulb shines through, white-hot inside the rim
    warm = np.array([1.0, 0.55, 0.22], np.float32)
    pale = np.array([1.0, 0.80, 0.52], np.float32)
    k = np.clip(em, 0, 1)[..., None] ** 2
    emc = em[..., None] * (warm * (1 - k) + pale * k)
    top_y = y + sh * 0.5 + sh * 0.25 * 0.5
    sc.draw_quad([(xs - sw, top_y, z), (xs + sw, top_y, z), (xs + sw, top_y - sh * 1.25, z),
                  (xs - sw, top_y - sh * 1.25, z)], np.zeros((h, w, 3), np.float32), alpha=a,
                 emissive=np.clip(emc, 0, 1), emit=1.5 * glow, lit=False, name='tulip', zwrite=True)


def sconce_front(sc: ZScene, x, y, zw, glow=1.0, seed=0):
    """a wall sconce on a FRONTAL wall z = zw: an oval brass back plate on the wall, a short arm toward the
    camera and the tulip shade 0.16 m in front of the wall."""
    cam = sc.cam
    seed = abs(int(seed))
    zs = zw - 0.16
    res = cam.f / zw * cam.ss
    brass = mat('metal_brass-brushed', mean=0.30, sat=0.5, tint=(1.0, 0.9, 0.72))
    pw, ph = 0.06, 0.17
    w, h = max(4, int(pw * 2 * res)), max(6, int(ph * res))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    m = np.clip((1 - (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)) * 4, 0, 1)
    pt = tile(brass, w, h, seed=seed + 1, scale=0.3) * (0.7 + 0.4 * (1 - yy / h))[..., None]
    sc.draw_quad([(x - pw, y + 0.03, zw - 0.004), (x + pw, y + 0.03, zw - 0.004), (x + pw, y - 0.14, zw - 0.004),
                  (x - pw, y - 0.14, zw - 0.004)], np.clip(pt, 0, 1), alpha=m, name='plate', zwrite=False)
    t = tile(brass, 6, max(4, int(0.16 * res)), seed=seed, scale=0.3) * 0.7
    sc.draw_quad([(x - 0.012, y - 0.06, zw), (x + 0.012, y - 0.06, zw), (x + 0.012, y - 0.06, zs),
                  (x - 0.012, y - 0.06, zs)], t, name='arm', zwrite=False)
    _tulip(sc, x, y, zs, glow)
    return np.array([x, y, zs], np.float32)


def sconce_light(P, side, power=1.6):
    """the sconce's light: frosted glass glows all round, more upward (the open top) and away from the wall."""
    def pat(d):
        up = np.clip(d[:, 1], -1, 1)
        out = np.clip(d[:, 0] * side, -1, 1)
        return (0.55 + 0.35 * smoothstep(0.2, 0.8, up) + 0.15 * out).astype(np.float32)
    return PointLight(P, AMBER, power=power, soft=0.28, pattern=pat, wrap=0.2, shadow_px=None, name='sconce')


class XApertureLight:
    """directional light (the moon) entering through a window in a wall x = plane_x:
    aperture(Q) -> (n,) transmission for points Q on that plane."""

    def __init__(self, direction, color, power, plane_x, aperture, shadow_px=2.0, ignore=(), name='moon'):
        d = np.asarray(direction, np.float32)
        self.dir = d / np.linalg.norm(d)
        self.color = np.asarray(color, np.float32)
        self.power, self.plane_x, self.aperture = power, plane_x, aperture
        self.shadow_px, self.ignore, self.name = shadow_px, set(ignore), name

    def transmit(self, P):
        Ln = -self.dir
        t = (self.plane_x - P[:, 0]) / Ln[0]
        Q = P + Ln[None, :] * t[:, None]
        return np.where(t > 0, self.aperture(Q), 0.0).astype(np.float32), t, Ln

    def irradiance(self, P, N, scene, grid_shape, mask_ignore=()):
        tr, t, Ln = self.transmit(P)
        cos = np.clip((N * Ln[None, :]).sum(1), 0, None)
        e = self.power * cos * tr
        act = e > 1e-5
        if scene is not None and scene.occluders and act.any():
            blk = np.zeros(int(act.sum()), bool)
            Lr = np.broadcast_to(Ln, (int(act.sum()), 3))
            for name, bmin, bmax in scene.occluders:
                if name in self.ignore or name in mask_ignore:
                    continue
                blk |= _ray_box_block(P[act], Lr, t[act], bmin, bmax)
            v = np.ones(P.shape[0], np.float32)
            v[act] = (~blk).astype(np.float32)
            e = e * v
        if self.shadow_px and grid_shape is not None:
            e = blur(e.reshape(grid_shape), self.shadow_px * scene.cam.ss).reshape(-1)
        return e[:, None] * self.color[None, :]


class PortalLight(PointLight):
    """a point light in a room beyond the wall z = plane_z: it lights everything beyond the wall fully and
    the near side only through aperture(Q) (Q = where the ray to the light crosses the wall plane, 0..1).
    soft_px blurs the transmission into a penumbra."""

    def __init__(self, pos, color, power, plane_z, aperture, soft=0.2, pattern=None, wrap=0.15, soft_px=3.0,
                 name='portal'):
        super().__init__(pos, color, power, soft=soft, pattern=pattern, wrap=wrap, shadow_px=None, name=name)
        self.plane_z, self.aperture, self.soft_px = plane_z, aperture, soft_px

    def irradiance(self, P, N, scene, grid_shape, mask_ignore=()):
        e = super().irradiance(P, N, scene, grid_shape, mask_ignore)
        near = P[:, 2] < self.plane_z - 1e-3
        if near.any():
            tr = np.ones(P.shape[0], np.float32)
            Pn = P[near]
            L = self.pos[None, :] - Pn
            t = (self.plane_z - Pn[:, 2]) / np.where(np.abs(L[:, 2]) < 1e-6, 1e-6, L[:, 2])
            Q = Pn + L * t[:, None]
            tr[near] = np.clip(self.aperture(Q), 0, 1)
            if self.soft_px and grid_shape is not None:
                tr = blur(tr.reshape(grid_shape), self.soft_px * scene.cam.ss).reshape(-1)
            e = e * tr[:, None]
        return e


def bare_bulb(sc: ZScene, x, y, z, ceil_y, glow=1.0):
    """a bare bulb on a twisted flex: the flex, a small brass lampholder and a glowing pear-shaped bulb."""
    cam = sc.cam
    res = cam.f / z * cam.ss
    cw = 0.006
    tex = np.zeros((8, 4, 3), np.float32) + 0.05
    sc.draw_quad([(x - cw, ceil_y, z), (x + cw, ceil_y, z), (x + cw, y + 0.09, z), (x - cw, y + 0.09, z)], tex,
                 name='flex', zwrite=False)
    hw_, hh_ = 0.022, 0.05
    brass = mat('metal_brass-brushed', mean=0.30, sat=0.5, tint=(1.0, 0.9, 0.72))
    t = tile(brass, max(3, int(hw_ * 2 * res)), max(3, int(hh_ * res)), seed=3, scale=0.3)
    sc.draw_quad([(x - hw_, y + 0.10, z), (x + hw_, y + 0.10, z), (x + hw_, y + 0.05, z), (x - hw_, y + 0.05, z)], t,
                 name='holder', zwrite=False)
    bw_, bh_ = 0.032, 0.085
    w, h = max(5, int(bw_ * 2 * res)), max(6, int(bh_ * res))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = yy / max(1, h - 1)
    half = (0.45 + 0.55 * np.sin(np.clip(v, 0, 1) * math.pi * 0.85 + 0.25)) * w / 2
    a = np.clip((half - np.abs(xx - w / 2)) / 1.0, 0, 1)
    em = (0.8 + 0.2 * (1 - np.abs(xx - w / 2) / (w / 2)))[..., None] * np.array([1.0, 0.85, 0.62], np.float32)
    sc.draw_quad([(x - bw_, y + 0.05, z), (x + bw_, y + 0.05, z), (x + bw_, y + 0.05 - bh_, z),
                  (x - bw_, y + 0.05 - bh_, z)], np.zeros((h, w, 3), np.float32), alpha=a,
                 emissive=np.clip(em, 0, 1), emit=4.0 * glow, lit=False, name='bulb', zwrite=True)
    return np.array([x, y, z], np.float32)


def halo(sc: ZScene, P, radius_m, strength, color=None, falloff=1.7):
    """a screen-space bloom halo round a light at world point P (size shrinks with distance)."""
    cam = sc.cam
    u, v = cam.project(P)
    r = radius_m * cam.f / P[2]
    sc.glow(u, v, r, AMBER if color is None else color, strength, falloff)


def framed_painting(sc: ZScene, corners, name, w_m, h_m, res=500, frame=0.08, seed=0, oval=False, **kw):
    """a gilt-framed old painting on a quad (corners TL, TR, BR, BL in world)."""
    w, h = max(8, int(w_m * res)), max(8, int(h_m * res))
    bp = max(3, int(frame * res))
    if oval:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        outer = np.clip((1 - r) * w / 2, 0, 1)
        brass = mat('metal_brass-brushed', mean=0.40, sat=0.5, tint=(1.0, 0.9, 0.72))
        fr = tile(brass, w, h, seed=seed, tone_var=0.25, scale=0.5)
        ring = 0.6 + 0.4 * np.cos(np.clip((r - 0.80) / 0.2, 0, 1) * math.pi * 3) ** 2
        fr = fr * ring[..., None] * (0.85 + 0.3 * value_noise(w, h, 30, seed + 1, 2))[..., None]
        canvas = so.painting(name, w, h, seed + 2)
        canvas *= (1 - 0.35 * smoothstep(0.35, 0.8, r))[..., None]
        inner = smoothstep(0.80, 0.78, r)
        full = fr * (1 - inner[..., None]) + canvas * inner[..., None]
        full *= (1 - 0.4 * np.exp(-((r - 0.80) / 0.025) ** 2))[..., None]
        sc.draw_quad(corners, np.clip(full, 0, 1), alpha=outer, spec=0.3, gloss=18, spec_tint=(1.0, 0.85, 0.6),
                     name='oval_' + name, **kw)
        return
    rgb, hole = so.gilt_frame(w, h, bp, seed, res=res)
    canvas = so.painting(name, w - 2 * bp + 8, h - 2 * bp + 8, seed + 1)
    full = rgb.copy()
    paste_over(full, canvas, np.ones(canvas.shape[:2], np.float32), bp - 4, bp - 4)
    lip = 1 - 0.45 * blur(1 - rect_mask(w, h, bp, bp, w - bp, h - bp), max(1.0, bp * 0.12))
    full = np.where(hole[..., None] > 0.5, rgb, full * lip[..., None])
    sc.draw_quad(corners, np.clip(full, 0, 1), spec=0.35, gloss=18, spec_tint=(1.0, 0.85, 0.6), name='painting_' + name,
                 **kw)


def night_sky(w, h, moon_c=None, moon_r=None, pines=True, seed=77, sky_crop=(100, 1100)):
    """sRGB night sky: Poly Haven Milky Way stars, a lavender gradient, the NASA moon (too big), misty pines."""
    sky = f32(load('sky_ph-milky-way'))
    y0, x0 = sky_crop
    sz = min(sky.shape[0] - y0, sky.shape[1] - x0, 900)
    sky = resize_f(sky[y0:y0 + sz, x0:x0 + sz], w, h, LANCZOS)
    Lsk = lum(sky)
    stars = np.clip((Lsk - 0.42) * 3.0, 0, 1) ** 1.2
    neb = blur(Lsk, max(1, w / 50)) * 0.10
    yy = np.linspace(0, 1, h)[:, None, None]
    grad = hexcol('#070b22', False) * (1 - yy) + hexcol('#1b1640', False) * yy
    img = grad + stars[..., None] * np.array([0.80, 0.80, 0.95]) * 0.8 + neb[..., None] * np.array([0.4, 0.4, 0.8])
    if moon_c is not None:
        mr = moon_r
        yy2, xx2 = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt((xx2 - moon_c[0]) ** 2 + (yy2 - moon_c[1]) ** 2)
        hal = np.exp(-((d - mr).clip(0) / (mr * 0.35))) * 0.45 + np.exp(-((d - mr).clip(0) / (mr * 1.4))) * 0.22
        img = img + hal[..., None] * hexcol('#cfc8ff', False)[None, None, :] * 0.55
        moon = f32(load('moon_nasa-full-moon-photo'))
        ml = lum(moon)
        y3, x3 = np.where(ml > 0.08)
        moon = moon[y3.min():y3.max(), x3.min():x3.max()]
        msz = max(4, int(2 * mr))
        moon = resize_f(moon, msz, msz, LANCZOS)
        moon = match_albedo(moon, sat=0.10, tint=(0.95, 0.93, 1.0))
        g = np.mgrid[0:msz, 0:msz].astype(np.float32)
        rr = np.sqrt((g[1] - msz / 2 + .5) ** 2 + (g[0] - msz / 2 + .5) ** 2)
        mm = np.clip((mr - 1.0 - rr) / 1.5, 0, 1)
        limb = 1 - 0.25 * (rr / mr) ** 4
        moon = (0.22 + 0.85 * moon) * limb[..., None]
        paste_over(img, moon, mm, int(moon_c[0] - mr), int(moon_c[1] - mr))
        cl = value_noise(w, h, max(8, w / 10), seed, octaves=4)
        band = np.exp(-((yy2 - (moon_c[1] + mr * 0.55)) / (mr * 0.45)) ** 2)
        wisp = smoothstep(0.5, 0.85, cl) * band * 0.8
        img = img * (1 - wisp[..., None] * 0.5) + wisp[..., None] * np.array([0.32, 0.30, 0.45]) * 0.35
    if pines:
        p = f32(load('fog_ph-misty-pines'))[150:1350, 200:2000]
        pl = lum(p)
        pl = resize_f(pl, w, int(w * pl.shape[0] / pl.shape[1]), LANCZOS)
        sil = np.clip((0.80 - pl) * 2.0, 0, 1)
        top = int(h - pl.shape[0] * 0.55)
        reg = img[max(0, top):]
        s2 = sil[:reg.shape[0]]
        fade = np.clip(np.linspace(-0.2, 1.4, reg.shape[0]), 0, 1)[:, None]
        a = (s2 * fade)[..., None] * 0.95
        fog = hexcol('#2a2650', False)
        reg[:] = reg * (1 - a) + (fog * 0.30)[None, None, :] * a
        mist = np.clip(np.linspace(-0.3, 1.0, reg.shape[0]), 0, 1)[:, None, None] * 0.35
        reg[:] = reg * (1 - mist) + mist * fog[None, None, :] * 0.9
    return np.clip(img, 0, 1)


# ==========================================================================
# finishing
# ==========================================================================
def volumetric(cam: Camera, depth, light, t0, t1, n=32, density=0.02, seed=3):
    """in-scattered light (linear, output resolution) along every camera ray from depth t0 to t1 (or the
    surface in the depth buffer): dust in the air lit by a PortalLight / PointLight / ApertureLight.
    Jittered samples, so no banding."""
    H, W = depth.shape
    xs = (np.arange(W, dtype=np.float32) + 0.5 - cam.cx) / cam.f
    ys = -(np.arange(H, dtype=np.float32) + 0.5 - cam.cy) / cam.f
    rng = np.random.default_rng(seed)
    acc = np.zeros((H, W), np.float32)
    dt = (t1 - t0) / n
    jit = rng.random((H, W)).astype(np.float32)
    for k in range(n):
        t = t0 + (k + jit) * dt                                   # (H, W) jittered depth
        X = xs[None, :] * t
        Y = cam.eye + ys[:, None] * t
        Z = t
        vis = (t < depth).astype(np.float32)
        if vis.max() == 0:
            continue
        P = np.stack([X, Y, Z], -1).reshape(-1, 3)
        if isinstance(light, XApertureLight):
            e = light.transmit(P)[0] * light.power
        elif isinstance(light, ApertureLight):
            Ln = -light.dir
            tt = (light.plane_z - P[:, 2]) / Ln[2]
            Q = P + Ln[None, :] * tt[:, None]
            e = np.where(tt > 0, light.aperture(Q), 0.0) * light.power
        else:
            L = light.pos[None, :] - P
            d2 = (L * L).sum(1)
            e = light.power / (d2 + light.soft ** 2)
            if light.pattern is not None:
                e = e * light.pattern(-L / np.sqrt(d2 + 1e-9)[:, None])
            if isinstance(light, PortalLight):
                near = P[:, 2] < light.plane_z
                tq = (light.plane_z - P[:, 2]) / np.where(np.abs(L[:, 2]) < 1e-6, 1e-6, L[:, 2])
                Q = P + L * tq[:, None]
                tr = np.where(near, np.clip(light.aperture(Q), 0, 1), 0.0)
                e = e * tr
        acc += e.reshape(H, W).astype(np.float32) * vis * dt
    # the dust is not sharp: blur it a little (the bars' shadows in the beam stay soft)
    acc = blur(acc, 2.5)
    return acc[..., None] * np.asarray(light.color, np.float32)[None, None, :] * density


def apply_fog(sc: ZScene, start, scale, color_lin, amount=1.0):
    """distance fog on the ss canvas from the depth buffer: radiance -> fog colour with depth."""
    z = sc.zbuf
    k = (1 - np.exp(-np.clip(z - start, 0, None) / scale)) * amount
    sc.canvas[:] = sc.canvas * (1 - k[..., None]) + np.asarray(color_lin, np.float32) * k[..., None]


def edge_dark(lin, amount=0.18):
    """a gentle darkening at the far left/right (the feed pans: its edges come and go)."""
    u = (np.arange(lin.shape[1]) + 0.5) / lin.shape[1]
    k = amount * (1 - smoothstep(0.0, 0.12, u)) + amount * smoothstep(0.88, 1.0, u)
    return lin * ((1 - k) ** 2.0)[None, :, None]


def mid_tint(y):
    """the night tint of a finished picture: mean B - R (0..255) of its mid-tones, warm practical light left out."""
    L = lum(y)
    warm = (y[..., 0] - y[..., 2] > 0.06) & (L > 0.22)
    m = (L > 0.08) & (L < 0.5) & ~warm
    return float((y[..., 2] - y[..., 0])[m].mean() * 255) if m.any() else 0.0


def night_balance(lin, a):
    """lean the cool (non-practical) light of a linear render toward the night violet by a (R x (1 - a), B x (1 + a)),
    leaving the warm pools round lamps, sconces and bulbs as they are."""
    R, B = lin[..., 0], lin[..., 2]
    Lm = lum(lin)
    warm = smoothstep(0.18, 0.55, (R - B) / (R + B + 1e-4)) * smoothstep(0.03, 0.2, Lm)
    k = (1 - warm)[..., None]
    gain = np.array([1 - a, 1 - 0.25 * a, 1 + a], np.float32)
    return lin * (1 + (gain - 1) * k)


TINT_MIN, TINT_AIM = 3.0, 7.5     # every camera room's mid-tones lean violet: B - R at least +3 (aim +7.5, LOOK.md)


def finish_cam(lin, seed=11):
    """the shared finish for camera rooms (kind 'cam'). A room whose own lights left it too warm overall (olive
    mid-tones) is first leaned back to the night violet the other cameras have (night_balance), so flipping between
    cameras looks like one house at one time of night."""
    lin = edge_dark(lin)
    y = finish(lin, 'cam', seed=seed, return_array=True)
    t = mid_tint(y)
    if t >= TINT_MIN:
        return y
    a0, t0, a1 = 0.0, t, 0.12
    for _ in range(4):                                   # (secant steps on a: B - R grows smoothly with it)
        y = finish(night_balance(lin, a1), 'cam', seed=seed, return_array=True)
        t1 = mid_tint(y)
        if abs(t1 - TINT_AIM) < 0.8 or t1 == t0:
            break
        a0, t0, a1 = a1, t1, float(np.clip(a1 + (TINT_AIM - t1) * (a1 - a0) / (t1 - t0), 0.0, 0.6))
    return y


def pose_for(cam: Camera, X, Z, height=1.9, ground=0.0):
    """game pose (fractions of the picture) of a figure standing with its feet at (X, ground, Z)."""
    u, v = cam.project((X, ground, Z))
    _, vt = cam.project((X, ground + height, Z))
    return dict(x=round(float(u / cam.width), 3), y=round(float(v / cam.height), 3),
                h=round(float((v - vt) / cam.height), 3))


def overlay(y_srgb, cam: Camera, poses, floor_pts=None, vp=None):
    """debug picture: 1.9 m figure boxes at the suggested poses, the floor line and the vanishing point."""
    img = pil(y_srgb).convert('RGB')
    d = ImageDraw.Draw(img)
    W, H = img.size
    d.rectangle([(1824 - 1600) / 2, 63, (1824 + 1600) / 2, 963], outline=(80, 200, 255))
    for p in poses:
        x, y, h = p['x'] * W, p['y'] * H, p['h'] * H
        w = h * 0.42
        d.rectangle([x - w / 2, y - h, x + w / 2, y], outline=(255, 80, 80), width=2)
        d.ellipse([x - 6, y - 3, x + 6, y + 3], outline=(255, 255, 0), width=2)
    if floor_pts:
        d.line(floor_pts, fill=(0, 255, 120), width=2)
    if vp:
        d.ellipse([vp[0] - 6, vp[1] - 6, vp[0] + 6, vp[1] + 6], outline=(255, 0, 255), width=2)
    return img
