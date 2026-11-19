"""CAM 1 - THE NURSERY ("Nobody's Nursery"), 1824 x 1026.

A Victorian night nursery seen from a camera high by the door: William Morris
'Daisy' paper above a painted beadboard dado, Walter Crane's 1876 'Nursery
Rhymes' paper as a frieze under the cornice, painted floorboards and the Met's
Lotto carpet. Under the window stands an empty crib with a red wool quilt; a
mobile of paper moons and brass stars hangs over it. A dappled rocking horse
waits in the middle of the room, wooden letter blocks lie on the rug, and a
little oil lamp on the chest of drawers burns low. The moon - far too big -
fills the window and lays the panes across the floor.

    camera  f = 760, eye 2.4 m at x = 0, horizon y = 300 (vanishing point 912, 300)
    room    x = -1.7 .. 2.5, z = 0.3 .. 5.6 (back wall), ceiling 3.0 m
    window  back wall x = 0.0 .. 1.0, sill 0.85, head 2.45
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import camkit as K
import meshkit as M
from camkit import Plane, PointLight, ZScene, draw_plane, zbreaks, so  # noqa: F401
from common import (ApertureLight, blur, edge_ao, f32, font, load, pil, rect_mask, resize_f, save_jpeg, smoothstep,
                    tile, value_noise, LANCZOS)

OUT = 'cam1_nursery.jpg'
F, CX, CY, EYE = 760.0, 912.0, 240.0, 2.55
XL, XR, ZBK, CEIL = -1.5, 2.1, 4.9, 2.95
DADO, SKIRT, RAIL, FRIEZE0 = 1.0, 0.15, 2.45, 2.47
WX0, WX1, WY0, WY1 = 0.15, 1.05, 0.85, 2.40
MOON_DIR = (-0.16, -0.76, -0.63)
CRIB = (-1.30, -0.05, 4.08, 4.80, 1.0)      # x0, x1, z0, z1, rail height
CHEST = (1.46, 2.08, 3.88, 4.50, 0.80)        # the painted chest by the right wall (a real model, see chest_and_lamp)
LAMP = (1.80, CHEST[4] + 0.20, 4.20)
HORSE = (0.62, 1.58, 3.25)                   # x0, x1, plane z (the horse's side faces the camera)
RUG = (-0.95, 1.45, 2.55, 4.15)
PAPER = {}


def daisy():
    if 'd' not in PAPER:
        a = K.flatten_light(K.f32(K.load('wallpaper_morris-daisy')), 120)
        t = K.make_seamless(a, blend=0.08)
        PAPER['d'] = K.match_albedo(t, sat=0.60, tint=(1.0, 0.98, 0.94), mean=0.38, contrast=1.15)
    return PAPER['d']


def rhymes():
    """Walter Crane's nursery paper as a frieze strip: crop the clean part, blend its ends so it repeats."""
    if 'r' not in PAPER:
        a = K.f32(K.load('wallpaper_nursery-rhymes-1876'))
        a = a[60:975, 70:1585]                    # off the torn top edge and the selvedge
        a = K.flatten_light(a, 150)
        w = a.shape[1]
        bl = int(w * 0.07)
        ramp = np.linspace(0, 1, bl, dtype=np.float32)[None, :, None]
        a2 = a[:, :w - bl].copy()
        a2[:, :bl] = a[:, w - bl:] * (1 - ramp) + a[:, :bl] * ramp
        PAPER['r'] = K.match_albedo(a2, sat=0.62, tint=(1.0, 0.98, 0.95), mean=0.40, contrast=1.05)
    return PAPER['r']


def frieze_band(b, Y0, Y1):
    """the nursery-rhyme frieze, repeating sideways only (one sheet tall)."""
    ys, xs = b.sl(b.x0, b.x1, Y0, Y1)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    if hh < 2 or ww < 2:
        return
    t = rhymes()
    rep_w = (Y1 - Y0) * t.shape[1] / t.shape[0]
    tt = K.at_res(('rhymes', round(Y1 - Y0, 3)), t, rep_w, b.res, h_m=Y1 - Y0)
    ox = int(math.floor(b.x0 * b.res)) + xs.start
    xi = (ox + np.arange(ww)) % tt.shape[1]
    yi = np.clip(np.arange(hh), 0, tt.shape[0] - 1)
    band = tt[yi][:, xi]
    band = band * K.stain_map(b, ys, xs, 9, size_m=3.0, strength=0.35)[..., None]
    b.alb[ys, xs] = np.clip(band, 0, 1)


def beadboard(b, top=DADO, skirt=SKIRT):
    t = K.mat('panel_beadboard-painted', mean=0.40, sat=0.25, tint=(1.0, 0.97, 0.90))
    tt = K.at_res(('bead',), t, 1.8, b.res)
    ys, xs = b.sl(b.x0, b.x1, skirt + 0.01, top - 0.04)
    if ys.stop > ys.start and xs.stop > xs.start:
        b.alb[ys, xs] = K.wtile(tt, b, ys, xs) * K.stain_map(b, ys, xs, 3, size_m=2.0, strength=0.3)[..., None]
    K.hmoulding_w(b, top - 0.04, top, [0, .6, 1, .9, .5, .7, .3, 0], wood_name='wood_painted-green', mean=0.42,
                  shadow=0.35)
    K.hmoulding_w(b, 0.0, skirt, [.9, 1, .7, .62, .6, .6, .6, .6, .6, .6, .58, .55], wood_name='wood_painted-green',
                  mean=0.36, shadow=0.0)
    ys = np.arange(b.h)
    b.ao *= (1 - 0.35 * np.exp(-np.clip(b.py(0) - ys, 0, None) / (0.05 * b.res)))[:, None]


def wall_common(b, seed):
    K.plaster_band(b, FRIEZE0 + 0.36, CEIL, name='plaster_aged-beige', size_m=1.0, mean=0.36, sat=0.3, seed=seed,
                   soot=0.25)
    K.paper_band(b, DADO, RAIL, daisy(), 0.55, seed=seed + 1, key='daisy', age=0.9)
    frieze_band(b, FRIEZE0, FRIEZE0 + 0.36)
    K.hmoulding_w(b, RAIL - 0.02, FRIEZE0, [.2, .7, 1, .8, .4, .6, .2], wood_name='wood_painted-green', mean=0.40)
    K.hmoulding_w(b, FRIEZE0 + 0.36, FRIEZE0 + 0.41, [.2, .7, 1, .8, .4], wood_name='wood_painted-green', mean=0.40)
    K.hmoulding_w(b, CEIL - 0.10, CEIL, [.1, .3, .6, .9, 1, .9, .7, .5, .3], wood_name='wood_painted-green',
                  mean=0.42, shadow=0.0)
    beadboard(b)


def finish_wall(b):
    Yv = b.y1 - (np.arange(b.h) + 0.5) / b.res
    b.ao *= (1 - 0.40 * np.exp(-(CEIL - Yv) / 0.12) - 0.35 * np.exp(-Yv / 0.06))[:, None]


def back_painter(b, plane):
    wall_common(b, 11)
    # the window: casing, apron, hole
    cw = 0.09
    for a, c in ((WX0 - cw, WX0), (WX1, WX1 + cw)):
        ys, xs = b.sl(a, c, WY0 - 0.06, WY1 + cw)
        if ys.stop - ys.start > 3 and xs.stop - xs.start > 3:
            t = so.fluted(xs.stop - xs.start, ys.stop - ys.start, 141, flutes=2)
            L = K.lum(t)[..., None]
            b.alb[ys, xs] = np.clip(L / max(1e-3, float(L.mean())) * np.array([0.42, 0.42, 0.38]), 0, 1)
        b.shadow(a, c, WY0 - 0.06, WY1 + cw, 0.4, 0.015, dy=-0.004)
    ys, xs = b.sl(WX0, WX1, WY1, WY1 + cw)
    if ys.stop - ys.start > 3:
        t = so.fluted(xs.stop - xs.start, ys.stop - ys.start, 143, vertical=False, flutes=2)
        L = K.lum(t)[..., None]
        b.alb[ys, xs] = np.clip(L / max(1e-3, float(L.mean())) * np.array([0.42, 0.42, 0.38]), 0, 1)
    ys, xs = b.sl(WX0 - cw, WX1 + cw, WY0 - 0.12, WY0 - 0.02)
    if ys.stop - ys.start > 3 and xs.stop - xs.start > 3:
        t = K.wtile(K.wood_tile('wood_painted-green', 1.5, b.res, mean=0.40, sat=0.25), b, ys, xs)
        b.alb[ys, xs] = t * so.profile_shade(ys.stop - ys.start, [1, .7, .9, .4])[:, None, None]
    ys, xs = b.sl(WX0, WX1, WY0, WY1)
    b.alpha[ys, xs] = 0.0
    # the crib and the chest throw soft contact shadows on the wall
    x0, x1, _, _, hgt = CRIB
    b.shadow(x0, x1, 0.0, hgt, 0.35, 0.06, dy=-0.01)
    b.shadow(CHEST[0], CHEST[1], 0.0, CHEST[4], 0.4, 0.06, dy=-0.01)
    b.ao *= edge_ao(b.x1 - b.x0, b.y1 - b.y0, b.res, {'left': (0.45, 0.12), 'right': (0.45, 0.12)})[:b.h, :b.w]
    finish_wall(b)


def left_painter(b, plane):
    wall_common(b, 21)
    z0, z1, y0, y1 = 2.75, 3.23, 1.30, 1.92
    b.shadow(z0 + 0.03, z1 - 0.03, y0, y1 - 0.02, 0.5, 0.03, dy=-0.025)
    finish_wall(b)


def right_painter(b, plane):
    wall_common(b, 31)
    b.shadow(-CHEST[3], -CHEST[2], 0.0, CHEST[4], 0.45, 0.05, dy=-0.01)
    finish_wall(b)


def floor_painter(b, plane):
    K.floor_boards(b, 'floor_painted-distressed', 1.6, mean=0.36, sat=0.40, tint=(0.95, 0.98, 1.0), seed=7)
    X, _, Z = plane.world(b)
    # the Lotto carpet
    rx0, rx1, rz0, rz1 = RUG
    ys, xs = b.sl(rx0, rx1, rz0, rz1)
    if ys.stop > ys.start and xs.stop > xs.start:
        full_w, full_h = int(round((rx1 - rx0) * b.res)), int(round((rz1 - rz0) * b.res))
        k = ('rugN', full_w, full_h)
        if k not in K.CACHE:                       # (real knot size, a border and a guard stripe: scenekit.rug_field)
            from scenekit import rug_field
            K.CACHE[k] = rug_field(max(2, full_w), max(2, full_h), b.res, seed=5, mean=0.27, tint=(1.0, 0.90, 0.92),
                                   border_m=0.16)
        rr = K.CACHE[k]
        ox = int(round((b.x0 - rx0) * b.res)) + xs.start
        oy = int(round((rz1 - b.y1) * b.res)) + ys.start
        sub = rr[max(0, oy):max(0, oy) + (ys.stop - ys.start), max(0, ox):max(0, ox) + (xs.stop - xs.start)]
        hh, ww = sub.shape[:2]
        if hh > 0 and ww > 0:
            Xs, Zs = X[ys, xs][:hh, :ww], Z[ys, xs][:hh, :ww]
            m = np.clip(np.minimum(np.minimum(Xs - rx0, rx1 - Xs), np.minimum(Zs - rz0, rz1 - Zs)) * b.res / 1.5, 0, 1)
            n = K.wnoise(Xs, Zs, 0.4, 5, 3)
            sub = sub * (0.85 + 0.25 * n)[..., None]
            reg = b.alb[ys, xs][:hh, :ww]
            b.alb[ys.start:ys.start + hh, xs.start:xs.start + ww] = sub * m[..., None] + reg * (1 - m[..., None])
    d = np.minimum(X - XL, XR - X)
    b.ao *= 1 - 0.5 * np.exp(-d / 0.10)
    b.ao *= 1 - 0.5 * np.exp(-np.maximum(0, ZBK - Z) / 0.10)
    # contact shadows: crib legs and body, chest, horse rockers, blocks
    x0, x1, z0, z1, _ = CRIB
    dx = np.maximum(np.maximum(x0 - X, X - x1), 0)
    dz = np.maximum(np.maximum(z0 - Z, Z - z1), 0)
    b.ao *= 1 - 0.40 * np.exp(-(np.sqrt(dx ** 2 + dz ** 2) / 0.12) ** 2)
    dx = np.maximum(np.maximum(CHEST[0] - X, X - CHEST[1]), 0)
    dz = np.maximum(np.maximum(CHEST[2] - Z, Z - CHEST[3]), 0)
    b.ao *= 1 - 0.6 * np.exp(-(np.sqrt(dx ** 2 + dz ** 2) / 0.07) ** 2)
    hx0, hx1, hz = HORSE
    b.ao *= 1 - 0.45 * np.exp(-(((X - (hx0 + hx1) / 2) / 0.45) ** 4 + ((Z - hz) / 0.10) ** 2))


def ceil_painter(b, plane):
    K.ceiling_plaster(b, 'plaster_ceiling-smooth', 3.2, mean=0.30, seed=5)
    X, _, Z = plane.world(b)
    d = np.minimum(X - XL, XR - X)
    b.ao *= 1 - 0.5 * np.exp(-d / 0.15)
    b.ao *= 1 - 0.5 * np.exp(-np.maximum(0, ZBK - Z) / 0.15)


def sky(sc):
    Zs = ZBK + 3.0
    x0, x1, y0, y1 = -2.0, 3.5, -1.0, 5.5
    res = 120
    w, h = int((x1 - x0) * res), int((y1 - y0) * res)
    # where the camera's ray through the upper right of the window meets the sky plane: the moon
    t = Zs / ZBK
    mx, my = 0.68 * t, EYE + (2.02 - EYE) * t
    img = K.night_sky(w, h, moon_c=((mx - x0) * res, (y1 - my) * res), moon_r=0.62 * res, pines=True)
    sc.draw_quad([(x0, y1, Zs), (x1, y1, Zs), (x1, y0, Zs), (x0, y0, Zs)], img, lit=False, name='sky')


def window_aperture(Q):
    x, y = Q[:, 0], Q[:, 1]
    inside = (x > WX0 + 0.05) & (x < WX1 - 0.05) & (y > WY0 + 0.06) & (y < WY1 - 0.06)
    xm, ym = (WX0 + WX1) / 2, (WY0 + WY1) / 2
    bars = (np.abs(x - xm) < 0.016) | (np.abs(y - ym) < 0.03)
    bars |= (np.abs(y - (WY0 + ym) / 2) < 0.012) | (np.abs(y - (ym + WY1) / 2) < 0.012)
    return (inside & ~bars).astype(np.float32)


def window_parts(sc):
    Zg = ZBK + 0.08
    res = 600
    ww, hh = int((WX1 - WX0) * res), int((WY1 - WY0) * res)
    xx = WX0 + (np.arange(ww) + 0.5) / res
    yy = WY1 - (np.arange(hh) + 0.5) / res
    XX, YY = np.meshgrid(xx, yy)
    Q = np.stack([XX, YY, np.full_like(XX, Zg)], -1).reshape(-1, 3)
    a = blur(1 - window_aperture(Q).reshape(hh, ww), 0.8)
    paint = K.mat('wood_painted-green', mean=0.40, sat=0.22, tint=(1.0, 0.98, 0.94))
    sash = tile(paint, ww, hh, seed=8, scale=1.5 * res / paint.shape[1], tone_var=0.15)
    sash *= (0.7 + 0.3 * blur(a, 3))[..., None]
    sc.draw_quad([(WX0, WY1, Zg), (WX1, WY1, Zg), (WX1, WY0, Zg), (WX0, WY0, Zg)], sash, alpha=a, spec=0.15, gloss=20,
                 name='sash')
    g = value_noise(ww, hh, 40, 31, octaves=3)
    grime = np.clip((g - 0.45) * 0.6, 0, 1) * (1 - a)
    gl = np.zeros((hh, ww, 3), np.float32) + K.hexcol('#cfc8ff', False)
    sc.draw_quad([(WX0, WY1, Zg - 0.005), (WX1, WY1, Zg - 0.005), (WX1, WY0, Zg - 0.005), (WX0, WY0, Zg - 0.005)],
                 gl, alpha=grime * 0.3, lit=False, emit=0.10, name='grime', zwrite=False)
    plaster = K.mat('plaster_aged-beige', mean=0.42, sat=0.30)
    pt = tile(plaster, 60, 400, seed=3, scale=0.4)
    for X in (WX0, WX1):
        sc.draw_quad([(X, WY1, ZBK + 0.14), (X, WY1, ZBK), (X, WY0, ZBK), (X, WY0, ZBK + 0.14)], pt, name='reveal')
    sc.draw_quad([(WX0, WY0, ZBK + 0.14), (WX1, WY0, ZBK + 0.14), (WX1, WY0, ZBK), (WX0, WY0, ZBK)],
                 so.wood('wood_painted-green', 400, 60, 400, 1.5, seed=12, mean=0.40, sat=0.25), name='sill')
    sc.draw_quad([(WX0, WY1, ZBK), (WX1, WY1, ZBK), (WX1, WY1, ZBK + 0.14), (WX0, WY1, ZBK + 0.14)], pt,
                 name='head')


def curtains(sc):
    """light cotton curtains (the old check linen), tied back either side of the window."""
    res = 400
    lin = K.mat('paper_offwhite-grain', mean=0.50, sat=0.30, tint=(1.0, 0.97, 0.93))
    Zc = ZBK - 0.06
    for k, (xa, xb) in enumerate(((WX0 - 0.40, WX0 + 0.06), (WX1 - 0.06, WX1 + 0.40))):
        ya, yb = WY0 - 0.35, WY1 + 0.28
        ww, hh = int((xb - xa) * res), int((yb - ya) * res)
        t, a = so.velvet_curtain(ww, hh, res, 80 + k, inner_right=(k == 0))
        L = K.lum(t)[..., None]
        shade = L / max(1e-3, float(L.mean()))
        cloth = tile(lin, ww, hh, seed=k, scale=0.5 * res / lin.shape[1])
        t = np.clip(cloth * (0.45 + 0.55 * shade), 0, 1)
        sc.draw_quad([(xa, yb, Zc), (xb, yb, Zc), (xb, ya, Zc), (xa, ya, Zc)], t, alpha=a, name=f'curtain{k}')
    brass = K.mat('metal_brass-brushed', mean=0.40, sat=0.5, tint=(1.0, 0.9, 0.72))
    rt = tile(brass, 600, 10, seed=5, scale=0.4) * so.profile_shade(10, np.sin(np.linspace(0, math.pi, 10)) * 2)[:,
                                                                                                           None, None]
    ry = WY1 + 0.30
    sc.draw_quad([(WX0 - 0.48, ry + 0.012, ZBK - 0.07), (WX1 + 0.48, ry + 0.012, ZBK - 0.07),
                  (WX1 + 0.48, ry - 0.012, ZBK - 0.07), (WX0 - 0.48, ry - 0.012, ZBK - 0.07)], np.clip(rt, 0, 1),
                 spec=0.5, gloss=25, name='rod')


def painted_wood(seed, colour=(0.62, 0.60, 0.55), name='wood_fine-grain-old', rot=True):
    def f(wp, hp, face):
        t = so.wood(name, wp, hp, 900, 0.6, rot=rot, seed=seed, mean=0.30)
        L = K.lum(t)[..., None]
        t = np.clip((1 + 0.35 * (L / max(1e-3, float(L.mean())) - 1)) * np.asarray(colour), 0, 1)
        e = rect_mask(wp, hp, 0, 0, wp, hp, soft=max(1.0, min(wp, hp) * 0.08))
        return {'tex': np.clip(t * (0.8 + 0.2 * e)[..., None], 0, 1), 'spec': 0.25, 'gloss': 25}
    return f


COT = {}


def cot_instance():
    """the cot: a real old iron bed frame (Poly Haven 'Old Bed Frame', photoscanned: tubular rails, wire mesh,
    chipped white paint, rust), at a child's size, its length along the wall under the window."""
    if 'm' not in COT:
        COT['m'] = M.Mesh('old_bed_frame', mean=0.40, sat=0.45, tint=(1.0, 0.97, 0.94))
    x0, x1, z0, z1, _ = CRIB
    m = COT['m']
    allP = np.concatenate([p[0] for p in m.prims])
    length = allP.max(0) - allP.min(0)
    s = (x1 - x0) / max(length[0], length[2])
    return m.place(((x0 + x1) / 2, 0.0, (z0 + z1) / 2), yaw=90, scale=s)


def cot(sc):
    """the iron cot with its mattress, red wool quilt and pillow on the wire mesh."""
    x0, x1, z0, z1, hgt = CRIB
    inst = cot_instance()
    lo, hi = inst.bounds()
    base = COT_BASE                                          # the wire mesh's height
    mres = 600
    q = K.mat('fabric_quilt-red-wool', mean=0.30, sat=0.62, tint=(1.0, 0.86, 0.88))
    mx0, mx1, mz0, mz1 = lo[0] + 0.07, hi[0] - 0.07, lo[2] + 0.06, hi[2] - 0.06
    sc.box((mx0, base, mz0), (mx1, base + 0.12, mz1),
           lambda w, h, f: {'tex': np.clip(tile(q, w, h, seed=3, scale=0.6 * mres / q.shape[1]) *
                                           (0.75 + 0.25 * value_noise(w, h, 30, 4, 3))[..., None], 0, 1)},
           res=mres, name='mattress')
    pl = K.mat('fabric_linen-check', mean=0.55, sat=0.3)
    sc.box((mx0 + 0.03, base + 0.12, mz0 + 0.06), (mx0 + 0.33, base + 0.20, mz1 - 0.06),
           lambda w, h, f: {'tex': tile(pl, w, h, seed=5, scale=0.3) * (0.8 + 0.2 * rect_mask(w, h, 0, 0, w, h,
                                                                                              soft=6))[..., None]},
           res=mres, name='pillow')
    M.contact_shadow(sc, inst, strength=0.6, radius=0.07)
    M.draw_mesh(sc, inst, name='crib_frame', spec=0.4)


COT_BASE = 0.31                                  # the wire mesh of the cot (0.48 m on the full-size frame, x 0.625)


def crib(sc):
    """(the old painted spindle crib, kept for reference: the scene now uses cot)
    a painted spindle crib: corner posts with ball finials, rails, spindles, a mattress and a red quilt."""
    x0, x1, z0, z1, hgt = CRIB
    post = 0.05
    col = (0.60, 0.58, 0.52)
    # mattress and quilt first (inside the crib), then the back rail, the spindles, the front
    mres = 600
    q = K.mat('fabric_quilt-red-wool', mean=0.30, sat=0.62, tint=(1.0, 0.86, 0.88))
    sc.box((x0 + post, 0.48, z0 + post), (x1 - post, 0.62, z1 - post),
           lambda w, h, f: {'tex': np.clip(tile(q, w, h, seed=3, scale=0.6 * mres / q.shape[1]) *
                                           (0.75 + 0.25 * value_noise(w, h, 30, 4, 3))[..., None], 0, 1)},
           res=mres, name='mattress')
    # a small pillow
    pl = K.mat('fabric_linen-check', mean=0.55, sat=0.3)
    sc.box((x0 + 0.08, 0.62, z0 + 0.12), (x0 + 0.40, 0.70, z1 - 0.12),
           lambda w, h, f: {'tex': tile(pl, w, h, seed=5, scale=0.3) * (0.8 + 0.2 * rect_mask(w, h, 0, 0, w, h,
                                                                                              soft=6))[..., None]},
           res=mres, name='pillow')
    # rails: top and bottom, front and back
    for zr in (z1 - post, z0):
        sc.box((x0, hgt - 0.05, zr), (x1, hgt, zr + post), painted_wood(11, col, rot=False), res=900, name='rail_t')
        sc.box((x0, 0.40, zr), (x1, 0.48, zr + post), painted_wood(12, col, rot=False), res=900, name='rail_b')
    # spindles on the front and the ends
    n = 15
    for i in range(n):
        x = x0 + post + (i + 0.5) * (x1 - x0 - 2 * post) / n
        sc.box((x - 0.012, 0.48, z0 + 0.012), (x + 0.012, hgt - 0.05, z0 + 0.036), painted_wood(20 + i, col), res=900,
               name='spindle')
    for xe in (x0 + 0.012, x1 - 0.036):
        for i in range(5):
            z = z0 + post + (i + 0.5) * (z1 - z0 - 2 * post) / 5
            sc.box((xe, 0.48, z - 0.012), (xe + 0.024, hgt - 0.05, z + 0.012), painted_wood(40 + i, col), res=900,
                   name='spindle_end')
    for (px, pz) in ((x0, z0), (x1 - post, z0), (x0, z1 - post), (x1 - post, z1 - post)):
        sc.box((px, 0.0, pz), (px + post, hgt + 0.08, pz + post), painted_wood(60, col), res=900, name='post')
        # ball finial (camera-facing disc)
        cam = sc.cam
        r = 0.035
        zc = pz + post / 2
        res = cam.f / zc * cam.ss
        w = max(4, int(2 * r * res))
        yy, xx = np.mgrid[0:w, 0:w].astype(np.float32)
        d = np.sqrt((xx - w / 2) ** 2 + (yy - w / 2) ** 2) / (w / 2)
        a = np.clip((1 - d) * w * 0.3, 0, 1)
        sh = (0.55 + 0.6 * np.clip(1 - np.sqrt((xx - w * 0.38) ** 2 + (yy - w * 0.35) ** 2) / (w * 0.6), 0, 1))
        t = np.clip(np.asarray(col) * sh[..., None], 0, 1)
        cx = px + post / 2
        sc.draw_quad([(cx - r, hgt + 0.08 + 2 * r, zc), (cx + r, hgt + 0.08 + 2 * r, zc), (cx + r, hgt + 0.08, zc),
                      (cx - r, hgt + 0.08, zc)], t, alpha=a, spec=0.3, gloss=25, name='finial')


def mobile(sc):
    """a mobile of paper moons and brass stars on threads, hanging from the ceiling over the crib."""
    x0, x1, z0, z1, _ = CRIB
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    cam = sc.cam
    ya = 1.90                                         # the arms
    cz = cz - 0.12
    thread = np.zeros((6, 2, 3), np.float32) + 0.35
    sc.draw_quad([(cx - 0.004, CEIL, cz), (cx + 0.004, CEIL, cz), (cx + 0.004, ya, cz), (cx - 0.004, ya, cz)], thread,
                 name='thread', zwrite=False)
    wood = K.mat('wood_fine-grain-old', mean=0.32, sat=0.4)
    sc.draw_quad([(cx - 0.32, ya + 0.008, cz), (cx + 0.32, ya + 0.008, cz), (cx + 0.32, ya - 0.008, cz),
                  (cx - 0.32, ya - 0.008, cz)], tile(wood, 200, 6, seed=1, scale=0.2), name='arm1', zwrite=False)
    sc.draw_quad([(cx, ya + 0.008, cz - 0.30), (cx, ya + 0.008, cz + 0.30), (cx, ya - 0.008, cz + 0.30),
                  (cx, ya - 0.008, cz - 0.30)], tile(wood, 200, 6, seed=2, scale=0.2), name='arm2', zwrite=False)
    paper = K.mat('paper_old-paper-stained', mean=0.68, sat=0.35)
    brass = K.mat('metal_brass-brushed', mean=0.50, sat=0.6, tint=(1.0, 0.9, 0.7))
    hangs = [(cx - 0.31, cz, 0.30, 'moon', 0.4), (cx + 0.31, cz, 0.42, 'star', 1.1), (cx, cz - 0.29, 0.22, 'star', 0.3),
             (cx, cz + 0.29, 0.36, 'moon', -0.6), (cx + 0.12, cz - 0.1, 0.52, 'star', 0.8)]
    for (hx, hz, drop, kind, rot) in hangs:
        yb = ya - drop
        sc.draw_quad([(hx - 0.003, ya, hz), (hx + 0.003, ya, hz), (hx + 0.003, yb + 0.07, hz), (hx - 0.003, yb + 0.07, hz)],
                     thread, name='thread', zwrite=False)
        s = 0.095
        res = cam.f / hz * cam.ss
        w = max(8, int(2 * s * res))
        im = Image.new('L', (w * 4, w * 4), 0)
        dr = ImageDraw.Draw(im)
        c = w * 2
        R = w * 1.8
        if kind == 'moon':
            dr.ellipse([c - R, c - R, c + R, c + R], fill=255)
            o = R * 0.55
            dr.ellipse([c - R + o * math.cos(rot), c - R - o * math.sin(rot), c + R + o * math.cos(rot),
                        c + R - o * math.sin(rot)], fill=0)
            src = paper
        else:
            pts = []
            for k in range(10):
                a = rot + k * math.pi / 5
                rr = R if k % 2 == 0 else R * 0.45
                pts.append((c + rr * math.sin(a), c - rr * math.cos(a)))
            dr.polygon(pts, fill=255)
            src = brass
        a = np.asarray(im.resize((w, w), Image.Resampling.LANCZOS), np.float32) / 255
        t = tile(src, w, w, seed=int(hx * 100) % 97, scale=0.3)
        sh = 0.8 + 0.3 * (1 - np.linspace(0, 1, w))[:, None]
        sc.draw_quad([(hx - s, yb + s, hz), (hx + s, yb + s, hz), (hx + s, yb - s, hz), (hx - s, yb - s, hz)],
                     np.clip(t * sh[..., None], 0, 1), alpha=a, spec=0.6 if kind == 'star' else 0.0, gloss=20,
                     name='mobile_' + kind, zwrite=False)


def horse_masks(w, h):
    """side view of a dappled rocking horse facing left, on its bow rockers; returns body, mane/tail, saddle,
    rocker masks (w x h px for HORSE width x 1.05 m)."""
    S = 4
    W, Hh = w * S, h * S

    def P(pts):
        return [(x / 100 * W, y / 100 * Hh) for x, y in pts]
    body = Image.new('L', (W, Hh), 0)
    d = ImageDraw.Draw(body)
    d.ellipse(P([(30, 30), (82, 56)]), fill=255)                              # barrel
    d.polygon(P([(36, 40), (30, 32), (24, 16), (22, 9), (30, 7), (36, 15), (44, 30), (46, 40)]), fill=255)  # neck
    d.polygon(P([(30, 7), (22, 6), (14, 11), (8, 20), (9, 24), (15, 24), (21, 19), (26, 15)]), fill=255)   # head
    d.polygon(P([(25, 7), (27, 0.5), (30, 7.5)]), fill=255)                   # ear
    for (top, foot) in (((38, 50), (24, 83)), ((44, 52), (36, 83)), ((70, 50), (80, 83)), ((76, 49), (90, 83))):
        tx, ty = top
        fx, fy = foot
        d.polygon(P([(tx - 3.0, ty), (tx + 3.0, ty), (fx + 1.6, fy), (fx - 1.6, fy)]), fill=255)
        d.polygon(P([(fx - 2.4, fy - 2), (fx + 2.4, fy - 2), (fx + 2.6, fy + 1), (fx - 2.6, fy + 1)]), fill=255)  # hoof
    hair = Image.new('L', (W, Hh), 0)
    dh = ImageDraw.Draw(hair)
    dh.polygon(P([(31, 6), (36, 13), (43, 26), (40, 28), (34, 18), (28, 10)]), fill=255)          # mane
    dh.polygon(P([(80, 36), (88, 40), (92, 52), (94, 66), (89, 60), (85, 48), (79, 42)]), fill=255)  # tail
    sad = Image.new('L', (W, Hh), 0)
    ds = ImageDraw.Draw(sad)
    ds.polygon(P([(48, 30), (64, 30), (66, 36), (62, 44), (50, 44), (46, 36)]), fill=255)
    rock = Image.new('L', (W, Hh), 0)
    dr = ImageDraw.Draw(rock)
    pts_top, pts_bot = [], []
    for k in range(41):
        u = k / 40
        x = 6 + 92 * u
        sag = 10 * (1 - (2 * u - 1) ** 2)
        pts_top.append((x, 82 + sag - 2))
        pts_bot.append((x, 82 + sag + 3))
    dr.polygon(P(pts_top + pts_bot[::-1]), fill=255)
    # stand-offs between the hooves and the bow
    out = []
    for im in (body, hair, sad, rock):
        out.append(np.asarray(im.resize((w, h), Image.Resampling.LANCZOS), np.float32) / 255)
    return out


def horse_cutout():
    """the Smithsonian's folk-art rocking horse (ca. 1900, CC0), cut out of its black museum backdrop:
    (albedo, alpha), cropped to the horse. The cut: brightness above the black, the one piece joined to the seat."""
    k = ('horse_cut',)
    if k in K.CACHE:
        return K.CACHE[k]
    im = f32(load('toy_saam-rocking-horse'))
    L = K.lum(im)
    H_, W_ = L.shape
    m = (blur(L, 1.0) > 0.045).astype(np.uint8) * 255
    mi = Image.fromarray(m, 'L').copy()
    ImageDraw.floodfill(mi, (int(W_ * 0.62), int(H_ * 0.34)), 128)        # the piece joined to the seat
    a = (np.asarray(mi) == 128).astype(np.float32)
    a = np.maximum(a, (blur(a, 2.5) > 0.62).astype(np.float32))            # close the pinholes in the dark paint
    a = blur(a, 0.8)
    ys, xs = np.nonzero(a > 0.05)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    alb = K.match_albedo(im[y0:y1, x0:x1], mean=0.17, sat=0.75, tint=(1.0, 0.94, 0.92))
    K.CACHE[k] = (np.clip(alb, 0, 1), np.clip(a[y0:y1, x0:x1] * 1.05, 0, 1))
    return K.CACHE[k]


def rocking_horse(sc):
    """the rocking horse: a real one (a museum photo, cut out), standing on its rockers on the rug, lit by the
    room's moon and lamp like everything else (its own photo shading gives it its form)."""
    alb, a = horse_cutout()
    x0, x1, z = HORSE
    w_m = (x1 - x0) * 1.12
    h_m = w_m * alb.shape[0] / alb.shape[1]
    cx = (x0 + x1) / 2

    class Feet:                                  # where its rockers touch the rug (for the contact shadow)
        def points(self):
            xs = np.linspace(cx - w_m * 0.42, cx + w_m * 0.45, 24)
            return np.array([(x, 0.0, zz) for x in xs for zz in (z, z + 0.22)])
    M.contact_shadow(sc, Feet(), strength=0.5, radius=0.07)
    sc.draw_quad([(cx - w_m / 2, h_m, z), (cx + w_m / 2, h_m, z), (cx + w_m / 2, 0.0, z), (cx - w_m / 2, 0.0, z)],
                 alb, alpha=a, spec=0.25, gloss=20, name='horse')


def rocking_horse_painted(sc):
    """(the old painted cut-out, kept for reference)
    a dappled-grey rocking horse in profile: painted body with dapples, dark horsehair mane and tail, a red
    leather saddle, dark bow rockers; a slightly offset darker copy behind gives it thickness."""
    x0, x1, z = HORSE
    hh_m = 1.05
    res = 700
    w, h = int((x1 - x0) * res), int(hh_m * res)
    body, hair, sad, rock = horse_masks(w, h)
    paint = np.array([0.66, 0.64, 0.60], np.float32)
    grain = so.wood('wood_fine-grain-old', w, h, res, 0.6, seed=4, mean=0.30)
    L = K.lum(grain)[..., None]
    t = np.clip((1 + 0.25 * (L / L.mean() - 1)) * paint, 0, 1)
    dap = value_noise(w, h, 9, 12, 2)
    dots = smoothstep(0.60, 0.74, blur(dap, 1.5)) * 0.22
    t = t * (1 - dots[..., None]) * 1.0
    # round shading: lighter on the back and the top of the neck, darker under the belly
    yy = np.linspace(0, 1, h)[:, None]
    sh = 1.05 - 0.45 * smoothstep(0.35, 0.58, yy) * (body > 0.5)
    t = t * sh[..., None]
    t = t * (1 - 0.35 * np.clip(blur(1 - body, 3) * body, 0, 1))[..., None]
    hair_c = tile(K.mat('fabric_leather-brown', mean=0.12, sat=0.4), w, h, seed=3, scale=0.2)
    sad_c = tile(K.mat('fabric_velvet-red', mean=0.24, sat=0.65, tint=(0.92, 0.8, 0.9)), w, h, seed=5, scale=0.3)
    rock_c = so.wood('wood_dark-varnished', w, h, res, 2.0, seed=7, mean=0.22)
    alb = t * body[..., None]
    alb = alb * (1 - sad[..., None]) + sad_c * sad[..., None]
    alb = alb * (1 - hair[..., None]) + hair_c * hair[..., None]
    alb = alb * (1 - rock[..., None]) + rock_c * rock[..., None]
    a = np.clip(body + hair + rock, 0, 1)
    # an eye and a bridle line
    alb[int(h * 0.12):int(h * 0.14), int(w * 0.18):int(w * 0.20)] = 0.04
    # thickness: a darker copy 4 cm behind and 1.5 cm to the right
    sc.draw_quad([(x0 + 0.015, hh_m, z + 0.04), (x1 + 0.015, hh_m, z + 0.04), (x1 + 0.015, 0.0, z + 0.04),
                  (x0 + 0.015, 0.0, z + 0.04)], np.clip(alb * 0.45, 0, 1), alpha=a, name='horse_back')
    sc.draw_quad([(x0, hh_m, z), (x1, hh_m, z), (x1, 0.0, z), (x0, 0.0, z)], np.clip(alb, 0, 1), alpha=a, spec=0.35,
                 gloss=25, name='horse')


def chest_and_lamp(sc):
    """a real painted nightstand (Poly Haven 'Painted Wooden Nightstand', photoscanned, worn blue paint) as the
    nursery's chest by the right wall, its drawer toward the room, and the oil lamp burning on it."""
    x0, x1, z0, z1, hgt = CHEST
    inst = M.Mesh('painted_wooden_nightstand', mean=0.30, sat=0.5).place(((x0 + x1) / 2, 0.0, (z0 + z1) / 2), yaw=-90,
                                                                         height=hgt)
    M.contact_shadow(sc, inst, strength=0.6, radius=0.08)
    M.draw_mesh(sc, inst, name='chest', spec=0.35)
    lamp_on(sc, hgt)


def chest_box(sc):
    """(the old box chest, kept for reference)"""
    x0, x1, z0, z1, hgt = CHEST

    def faces(wp, hp, face):
        t = so.wood('wood_lacquered-cherry', wp, hp, 600, 1.0, rot=(face == 'left'), seed=5, mean=0.26, contrast=1.3)
        if face == 'left':                                      # drawer fronts facing the room
            for k in range(3):
                y0, y1 = int(hp * (0.08 + k * 0.30)), int(hp * (0.08 + k * 0.30 + 0.26))
                t[y0:y0 + 2] *= 0.4
                t[y1 - 2:y1] *= 0.4
                for kx in (0.3, 0.7):
                    cx_, cy_ = int(wp * kx), (y0 + y1) // 2
                    t[cy_ - 2:cy_ + 3, cx_ - 2:cx_ + 3] = [0.5, 0.4, 0.22]
        return {'tex': np.clip(t, 0, 1), 'spec': 0.35, 'gloss': 30}
    sc.box((x0, 0.0, z0), (x1, hgt, z1), faces, res=600, name='chest')
    lamp_on(sc, hgt)


def lamp_on(sc, hgt):
    # the oil lamp: brass font and a glass chimney glowing
    lx, ly, lz = LAMP
    cam = sc.cam
    res = cam.f / lz * cam.ss
    brass = K.mat('metal_brass-brushed', mean=0.42, sat=0.6, tint=(1.0, 0.9, 0.7))
    w, h = max(4, int(0.12 * res)), max(4, int(0.10 * res))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = np.clip((1 - (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h * 0.6) / (h * 0.6)) ** 2)) * 4, 0, 1)
    sc.draw_quad([(lx - 0.06, hgt + 0.10, lz), (lx + 0.06, hgt + 0.10, lz), (lx + 0.06, hgt, lz), (lx - 0.06, hgt, lz)],
                 tile(brass, w, h, seed=2, scale=0.3), alpha=a, spec=0.8, gloss=25, name='lamp_font')
    w, h = max(4, int(0.08 * res)), max(6, int(0.17 * res))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = yy / h
    half = (0.35 + 0.65 * np.exp(-((v - 0.7) / 0.25) ** 2)) * w / 2
    a = np.clip((half - np.abs(xx - w / 2)) / 1.0, 0, 1)
    flame = np.exp(-(((xx - w / 2) / (w * 0.10)) ** 2 + ((v - 0.78) / 0.10) ** 2))
    em = (0.25 + 0.4 * (1 - np.abs(xx - w / 2) / (w / 2)))[..., None] * np.array([1.0, 0.70, 0.35]) + \
        flame[..., None] * np.array([1.0, 0.85, 0.55]) * 1.6
    sc.draw_quad([(lx - 0.04, hgt + 0.27, lz), (lx + 0.04, hgt + 0.27, lz), (lx + 0.04, hgt + 0.10, lz),
                  (lx - 0.04, hgt + 0.10, lz)], np.zeros((h, w, 3), np.float32), alpha=a, emissive=np.clip(em, 0, 1),
                 emit=1.6, lit=False, name='chimney')


def blocks(sc):
    """wooden letter blocks on the rug (A, B, C and a fallen one)."""
    fnt = font('IMFellEnglishSC-Regular.ttf', 120)
    cols = [(0.62, 0.20, 0.18), (0.20, 0.32, 0.55), (0.62, 0.52, 0.20), (0.24, 0.42, 0.28)]
    spots = [(-0.10, 2.92, 'A', 0), (0.03, 2.94, 'B', 1), (-0.04, 2.93, 'C', 2), (0.34, 3.12, 'Z', 3), (0.58, 2.86, 'Q', 1)]
    s = 0.10
    for i, (bx, bz, ch, ci) in enumerate(spots):
        y0 = 0.0 if i != 2 else s                           # C sits on top of A and B
        bx0 = bx - s / 2 if i != 2 else -0.085

        def faces(wp, hp, face, ch=ch, ci=ci):
            base = so.wood('wood_fine-grain-old', wp, hp, 1200, 0.6, seed=ci, mean=0.45)
            L = K.lum(base)[..., None]
            t = np.clip(L / max(1e-3, float(L.mean())) * np.array([0.62, 0.55, 0.42]), 0, 1)
            if face in ('front', 'top'):
                im = Image.new('L', (128, 128), 0)
                ImageDraw.Draw(im).text((64, 70), ch, font=fnt, fill=255, anchor='mm')
                m = np.asarray(im.resize((wp, hp), Image.Resampling.LANCZOS), np.float32) / 255
                fr = 1 - rect_mask(wp, hp, wp * 0.08, hp * 0.08, wp * 0.92, hp * 0.92, soft=1.0)
                ink = np.clip(m + fr, 0, 1)[..., None]
                t = t * (1 - ink) + np.asarray(cols[ci]) * ink
            e = rect_mask(wp, hp, 0, 0, wp, hp, soft=max(1.0, wp * 0.06))
            return {'tex': np.clip(t * (0.8 + 0.2 * e)[..., None], 0, 1), 'spec': 0.2, 'gloss': 20}
        sc.box((bx0, y0, bz), (bx0 + s, y0 + s, bz + s), faces, res=1200, occluder=False, name=f'block_{ch}')


def build_scene():
    cam = K.make_camera(F, CX, CY, EYE)
    sc = ZScene(cam, K.ambient_fn)
    moon = K.MOON

    sc.lights.append(ApertureLight(MOON_DIR, moon, power=3.6, plane_z=ZBK + 0.08, aperture=window_aperture,
                                   shadow_px=1.5, name='moon'))
    sc.lights.append(PointLight(((WX0 + WX1) / 2, (WY0 + WY1) / 2, ZBK - 0.25), moon * np.array([0.9, 0.92, 1.0]),
                                power=1.9, soft=0.6, pattern=lambda d: np.clip(-d[:, 2], 0, 1) ** 1.2, wrap=0.3,
                                shadow_px=None, ignore=('crib_body',), name='window_glow'))
    sc.lights.append(PointLight(LAMP, K.AMBER, power=2.2, soft=0.25, wrap=0.15, shadow_px=None, name='oil_lamp'))
    sc.lights.append(PointLight((1.3, 1.4, 4.0), K.AMBER, power=0.7, soft=1.0, wrap=0.4, shadow_px=None,
                                name='lamp_bounce'))
    sc.lights.append(PointLight((0.0, 2.6, -0.6), moon * np.array([0.85, 0.85, 1.0]), power=1.0, soft=1.5, wrap=0.3,
                                shadow_px=None, name='fill'))
    lo, hi = cot_instance().bounds()
    sc.add_occluder('crib_body', (lo[0] + 0.05, COT_BASE, lo[2] + 0.05), (hi[0] - 0.05, COT_BASE + 0.14, hi[2] - 0.05))
    hx0, hx1, hz = HORSE
    sc.add_occluder('horse', (hx0 + 0.25, 0.25, hz), (hx1 - 0.2, 0.85, hz + 0.04))
    sc.add_occluder('chest', CHEST[0:1] + (0.0, CHEST[2]), (CHEST[1], CHEST[4], CHEST[3]))

    sky(sc)
    window_parts(sc)
    draw_plane(sc, Plane('back', ZBK, XL, XR, 0.0, CEIL), back_painter, None, max_res=420)
    draw_plane(sc, Plane('ceil', CEIL, XL, XR, 0.6, ZBK), ceil_painter, zbreaks(0.6, ZBK, 1.42), max_res=500)
    draw_plane(sc, Plane('floor', 0.0, XL, XR, 2.0, ZBK), floor_painter, zbreaks(2.0, ZBK, 1.42), max_res=650,
               spec=0.2, gloss=25)
    draw_plane(sc, Plane('lwall', XL, 0.3, ZBK, 0.0, CEIL), left_painter, zbreaks(0.3, ZBK, 1.42), max_res=600)
    draw_plane(sc, Plane('rwall', XR, 0.3, ZBK, 0.0, CEIL), right_painter, zbreaks(0.3, ZBK, 1.42), max_res=600)
    curtains(sc)
    chest_and_lamp(sc)
    cot(sc)
    mobile(sc)
    rocking_horse(sc)
    blocks(sc)
    X = XL + 0.03
    K.framed_painting(sc, [(X, 1.92, 2.75), (X, 1.92, 3.23), (X, 1.30, 3.23), (X, 1.30, 2.75)],
                      'painting_paul-portrait-young-girl-1840', 0.48, 0.62, res=520, frame=0.06, seed=7, oval=True)
    return sc


def render(seed=11):
    sc = build_scene()
    lx, ly, lz = LAMP
    K.halo(sc, (lx, ly + 0.02, lz), 0.40, 0.18, K.AMBER * np.array([1.0, 0.9, 0.75]))
    K.halo(sc, (lx, ly, lz), 0.10, 0.40, K.AMBER)
    lin = sc.downsample()
    moonL = [l for l in sc.lights if l.name == 'moon'][0]
    lin = lin + K.volumetric(sc.cam, sc.depth_out(), moonL, 1.0, ZBK, n=40, density=0.006)
    y = K.finish_cam(lin, seed)
    return y, lin, sc


def poses():
    cam = K.make_camera(F, CX, CY, EYE)
    return [K.pose_for(cam, 0.35, 2.80), K.pose_for(cam, -0.25, 3.62), K.pose_for(cam, 0.60, 4.45)]


def build(out_path):
    y, _, _ = render()
    save_jpeg(pil(y), out_path, quality=84, max_kb=880)
    return out_path


if __name__ == '__main__':
    import time
    t = time.time()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/cam1.png')
    y, lin, sc = render()
    pil(y).save(out)
    K.overlay(y, sc.cam, poses(), vp=(CX, CY)).save(str(out).replace('.png', '_ov.png'))
    print('saved', out, f'{time.time() - t:.1f}s')
