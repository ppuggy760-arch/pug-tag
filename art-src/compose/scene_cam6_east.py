"""CAM 6 - EAST HALL (1824 x 1026): the corridor outside your RIGHT door.

The cold twin of the West Hall: tall dark raised panelling to shoulder height,
peeling damp plaster above, worn herringbone parquet, and a tall six-over-six
sash window on the right wall with velvet curtains. The far-too-big moon looks
in and lays the window's panes across the floor and up the left wall. A high-
backed oak settle waits under the panelling; one sconce flickers by the far
door, which stands open a crack onto a dark room.
The camera hangs high near the left-hand wall, so the right wall is seen well.

    camera  f = 860, eye 2.1 m at x = 0, horizon y = 330 (vanishing point 912, 330)
    hall    x = -0.75 .. 1.55 (2.3 m), ceiling 3.0 m, far wall z = 7.0 m
    window  right wall z = 2.85 .. 3.95, sill 0.80, head 2.45
    door    far wall x = -0.58 .. 0.34, 2.15 m, hinged right, open 35 degrees
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import camkit as K
from camkit import Plane, PointLight, ZScene, draw_plane, zbreaks, so  # noqa: F401
from common import blur, edge_ao, f32, load, pil, rect_mask, resize_f, save_jpeg, smoothstep, tile, LANCZOS

OUT = 'cam6_east.jpg'
F, CX, CY, EYE = 860.0, 912.0, 330.0, 2.1
XL, XR, CEIL, ZB = -0.75, 1.55, 3.0, 7.0
PANEL_TOP, SKIRT, RAIL = 1.42, 0.16, 2.40
DX0, DX1, DTOP, DANG = -0.58, 0.34, 2.15, 35.0
WALL_T = 0.14
WZ0, WZ1, WY0, WY1 = 2.85, 3.95, 0.80, 2.45          # the window opening (right wall)
MOON_DIR = (-0.60, -0.55, 0.55)        # moonlight travels away from the camera: the panes land mid-hall
SCONCE_Z = 5.75
SETTLE = (4.45, 5.95)                                 # z range of the bench against the right wall
LEFT_DOOR = (1.55, 2.47)
PAINTINGS = [  # z0, z1, Y0, Y1, source, oval (on the right wall)
    (4.55, 5.75, 1.62, 2.28, 'painting_kuindzhi-night-on-the-dnieper', False),
    (1.45, 1.95, 1.60, 2.25, 'painting_paul-portrait-young-girl-1840', True),
]
BEYOND_MOON = (-1.6, 1.6, 9.6)


def window_aperture(Q):
    """six-over-six sash: frame, a thick meeting rail, two muntins across each sash."""
    z, y = Q[:, 2], Q[:, 1]
    inside = (z > WZ0 + 0.05) & (z < WZ1 - 0.05) & (y > WY0 + 0.06) & (y < WY1 - 0.06)
    zm = (WZ0 + WZ1) / 2
    w3 = (WZ1 - WZ0 - 0.10) / 3
    bars = (np.abs(z - (WZ0 + 0.05 + w3)) < 0.014) | (np.abs(z - (WZ0 + 0.05 + 2 * w3)) < 0.014)
    ym = (WY0 + WY1) / 2
    bars |= np.abs(y - ym) < 0.03
    bars |= (np.abs(y - (WY0 + ym) / 2) < 0.013) | (np.abs(y - (ym + WY1) / 2) < 0.013)
    _ = zm
    return (inside & ~bars).astype(np.float32)


def free_edge():
    th = math.radians(DANG)
    w = DX1 - DX0
    return DX1 - w * math.cos(th), ZB + w * math.sin(th)


def door_aperture(Q):
    lx, ly, lz = BEYOND_MOON
    fx, fz = free_edge()
    x_cut = lx + (fx - lx) * (lz - ZB) / (lz - fz)
    x, y = Q[:, 0], Q[:, 1]
    return (np.clip((x - DX0) / 0.02, 0, 1) * np.clip((x_cut - x) / 0.02, 0, 1) * np.clip((DTOP - y) / 0.02, 0, 1)
            * (y > -0.05))


def panelling(b, top=PANEL_TOP):
    """tall raised panelling: two rows of the real wainscot photo-texture, capped by a moulded rail."""
    K.wainscot_row(b, SKIRT + 0.01, top - 0.05, mean=0.24, rows=2)
    K.hmoulding_w(b, top - 0.05, top, [0, .5, 1, .9, .6, .8, .4, .1], mean=0.27, shadow=0.5)
    K.hmoulding_w(b, 0.0, SKIRT, [.9, 1, .7, .62, .6, .6, .6, .6, .6, .6, .58, .55], mean=0.21, shadow=0.0)
    ys = np.arange(b.h)
    b.ao *= (1 - 0.35 * np.exp(-np.clip(b.py(0) - ys, 0, None) / (0.05 * b.res)))[:, None]


def upper_wall(b, seed):
    K.plaster_band(b, PANEL_TOP, CEIL, name='misc_wallpaper-decrepit', size_m=2.5, mean=0.36, sat=0.35,
                   tint=(1.0, 0.96, 0.90), seed=seed, soot=0.30)
    # damp: the real stain photo plus a rising tide line under the window
    ys, xs = b.sl(b.x0, b.x1, PANEL_TOP, CEIL)
    if ys.stop > ys.start:
        b.alb[ys, xs] *= K.stain_map(b, ys, xs, seed + 1, size_m=3.5, strength=0.5)[..., None]
    K.hmoulding_w(b, RAIL - 0.025, RAIL + 0.025, [.2, .7, 1, .8, .4, .6, .2], mean=0.28)
    K.hmoulding_w(b, CEIL - 0.12, CEIL, [.1, .3, .6, .9, 1, .9, .7, .5, .3, .2], mean=0.32, shadow=0.0)


def finish_wall(b):
    Yv = b.y1 - (np.arange(b.h) + 0.5) / b.res
    b.ao *= (1 - 0.45 * np.exp(-(CEIL - Yv) / 0.12) - 0.35 * np.exp(-Yv / 0.06))[:, None]


def right_painter(b, plane):
    upper_wall(b, 61)
    panelling(b)
    # the window: a hole with a moulded casing round it and a deeper sill
    s0, s1 = -WZ1, -WZ0
    cw = 0.09
    for a, c in ((s0 - cw, s0), (s1, s1 + cw)):
        ys, xs = b.sl(a, c, WY0 - 0.06, WY1 + cw)
        if ys.stop - ys.start > 3 and xs.stop - xs.start > 3:
            b.alb[ys, xs] = so.fluted(xs.stop - xs.start, ys.stop - ys.start, 141, flutes=2)
        b.shadow(a, c, WY0 - 0.06, WY1 + cw, 0.4, 0.015, dy=-0.004)
    ys, xs = b.sl(s0, s1, WY1, WY1 + cw)
    if ys.stop - ys.start > 3 and xs.stop - xs.start > 3:
        b.alb[ys, xs] = so.fluted(xs.stop - xs.start, ys.stop - ys.start, 143, vertical=False, flutes=2)
    ys, xs = b.sl(s0 - cw, s1 + cw, WY0 - 0.12, WY0 - 0.02)
    if ys.stop - ys.start > 3 and xs.stop - xs.start > 3:
        t = so.wood('wood_dark-varnished', xs.stop - xs.start, ys.stop - ys.start, b.res, 2.0, seed=147, mean=0.30)
        b.alb[ys, xs] = t * so.profile_shade(ys.stop - ys.start, [1, .7, .9, .4])[:, None, None]
    ys, xs = b.sl(s0, s1, WY0, WY1)
    b.alpha[ys, xs] = 0.0
    # a damp bloom spreading down from the sill
    X = b.x0 + (np.arange(b.w) + 0.5) / b.res
    Yv = b.y1 - (np.arange(b.h) + 0.5) / b.res
    XX, YY = np.meshgrid(X, Yv)
    n = K.wnoise(XX, YY, 0.25, 71, 3)
    bloom = np.exp(-((XX - (s0 + s1) / 2) / 0.7) ** 2) * smoothstep(WY0 + 0.1, WY0 - 0.9 + 0.5 * n, YY) * (YY < WY0)
    b.alb *= (1 - 0.30 * bloom)[..., None]
    for z0, z1 in (SETTLE,):
        b.shadow(-z1, -z0, 0.0, 0.47, 0.40, 0.05, dx=0.0, dy=-0.02)
    for (z0, z1, y0, y1, _, oval) in PAINTINGS:
        if oval:
            b.shadow(-z1 + 0.03, -z0 - 0.03, y0, y1 - 0.02, 0.5, 0.03, dx=0.0, dy=-0.025)
        else:
            b.shadow(-z1, -z0, y0, y1, 0.55, 0.03, dx=0.0, dy=-0.03)
    finish_wall(b)


def left_painter(b, plane):
    upper_wall(b, 81)
    panelling(b)
    s0, s1 = LEFT_DOOR
    K.door_on_board(b, s0, s1, 2.15, seed=85, mean=0.23)
    finish_wall(b)


def far_painter(b, plane):
    upper_wall(b, 91)
    panelling(b)
    K.door_on_board(b, DX0, DX1, DTOP, seed=97, mean=0.23)
    ys, xs = b.sl(DX0, DX1, -0.01, DTOP)
    b.alpha[ys, xs] = 0.0
    b.ao *= edge_ao(b.x1 - b.x0, b.y1 - b.y0, b.res, {'left': (0.45, 0.12), 'right': (0.45, 0.12)})[:b.h, :b.w]
    finish_wall(b)


def floor_painter(b, plane):
    t = K.mat('floor_herringbone-parquet', mean=0.27, sat=0.55, tint=(0.95, 0.92, 0.90), contrast=1.1)
    tt = K.at_res(('herring',), t, 3.4, b.res)
    out = K.wtile(tt, b, slice(0, b.h), slice(0, b.w)).copy()
    n = K.bnoise(b, 1.3, 13, 2)
    out *= (1 + 0.14 * (n * 2 - 1))[..., None]
    # worn grey path down the middle, dust at the edges
    X, _, Z = plane.world(b)
    mid = (XL + XR) / 2
    path = np.exp(-((X - mid) / 0.45) ** 2)
    nn = K.bnoise(b, 0.4, 17, 3)
    L = K.lum(out)[..., None]
    out = out * (1 - 0.35 * path[..., None] * nn[..., None]) + L * 0.35 * path[..., None] * nn[..., None] * 1.1
    b.alb[:] = np.clip(out, 0, 1)
    d = np.minimum(X - XL, XR - X)
    b.ao *= 1 - 0.55 * np.exp(-d / 0.10)
    b.ao *= 1 - 0.5 * np.exp(-np.maximum(0, ZB - Z) / 0.08)
    # under the settle
    z0, z1 = SETTLE
    dz = np.maximum(np.maximum(z0 - Z, Z - z1), 0)
    dx = np.maximum(XR - 0.40 - X, 0)
    b.ao *= 1 - 0.45 * np.exp(-(np.sqrt(dz ** 2 + dx ** 2) / 0.12) ** 2)


def ceil_painter(b, plane):
    K.ceiling_plaster(b, 'plaster_ceiling-smooth', 3.2, mean=0.29, seed=17)
    X, _, Z = plane.world(b)
    d = np.minimum(X - XL, XR - X)
    b.ao *= 1 - 0.5 * np.exp(-d / 0.15)
    b.ao *= 1 - 0.5 * np.exp(-np.maximum(0, ZB - Z) / 0.15)
    # a brown water stain spreading from the outside wall
    n = K.wnoise(X, Z, 0.5, 23, 3)
    st = smoothstep(0.62, 0.58, np.sqrt(((X - 1.3) / 1.2) ** 2 + ((Z - 4.6) / 1.6) ** 2) * 0.5 + n * 0.35)
    edge = np.exp(-((np.sqrt(((X - 1.3) / 1.2) ** 2 + ((Z - 4.6) / 1.6) ** 2) * 0.5 + n * 0.35 - 0.6) / 0.012) ** 2)
    b.alb[:] = b.alb * (1 - 0.18 * st[..., None]) * np.array([1.0, 0.96, 0.9]) ** st[..., None]
    b.alb[:] = b.alb * (1 - 0.25 * edge[..., None])


def sky(sc):
    # the night sky on a far plane outside (the moon sits where the window's upper panes look)
    Xs = XR + 2.6
    z0, z1, y0, y1 = 3.0, 16.0, -2.0, 7.0
    res = 70
    w, h = int((z1 - z0) * res), int((y1 - y0) * res)
    # where the camera's ray through the upper window meets the sky plane
    t = Xs / XR
    mz, my = 3.75 * t, EYE + (2.10 - EYE) * t
    skyt = K.night_sky(w, h, moon_c=None, pines=False)
    # the moon itself is behind the camera's line of sight (its light falls down the hall); the sky nearest
    # to it, at the near edge of the window, glows lavender
    zz = z0 + (np.arange(w) + 0.5) / res
    yy = y1 - (np.arange(h) + 0.5) / res
    ZZ, YY = np.meshgrid(zz, yy)
    gl = np.exp(-(((ZZ - (z0 - 1.0)) / 3.2) ** 2 + ((YY - (my + 2.5)) / 4.0) ** 2))
    skyt = np.clip(skyt + gl[..., None] * K.hexcol('#cfc8ff', False) * 0.35, 0, 1)
    # misty treetops along the bottom of the view
    pines = f32(load('fog_ph-misty-pines'))[150:1350, 200:2000]
    pl = K.lum(pines)
    pl = resize_f(pl, w, int(w * pl.shape[0] / pl.shape[1] * 0.5), LANCZOS)
    sil = np.clip((0.80 - pl) * 2.0, 0, 1)
    hz = int((y1 - (EYE + (0.9 - EYE) * t)) * res)
    top = max(0, hz - int(pl.shape[0] * 0.6))
    reg = skyt[top:top + pl.shape[0]]
    a = sil[:reg.shape[0]][..., None] * 0.9
    reg[:] = reg * (1 - a) + np.array([0.05, 0.05, 0.10]) * a
    skyt[top + pl.shape[0]:] = np.array([0.05, 0.05, 0.10])
    skyt = skyt[:, ::-1].copy()                              # board X = -z on a right-hand plane
    sc.draw_quad([(Xs, y1, z1), (Xs, y1, z0), (Xs, y0, z0), (Xs, y0, z1)], skyt, lit=False, emit=1.0, name='sky')


def window_parts(sc):
    """the reveals and sill (the wall's thickness), the sash bars, the glass grime."""
    # reveals
    plaster = K.mat('plaster_aged-beige', mean=0.40, sat=0.35, tint=(0.95, 0.95, 1.0))
    pt = tile(plaster, 80, 400, seed=3, scale=0.4)
    sc.draw_quad([(XR + WALL_T, WY1, WZ1), (XR, WY1, WZ1), (XR, WY0, WZ1), (XR + WALL_T, WY0, WZ1)], pt,
                 ao=edge_ao(WALL_T, WY1 - WY0, 200, {'left': (0.5, 0.03)}), name='reveal_far')
    sc.draw_quad([(XR + WALL_T, WY0, WZ1), (XR, WY0, WZ1), (XR, WY0, WZ0), (XR + WALL_T, WY0, WZ0)],
                 so.wood('wood_painted-green', 120, 400, 400, 1.5, seed=12, mean=0.30, sat=0.3), name='sill')
    sc.draw_quad([(XR + WALL_T, WY1, WZ0), (XR, WY1, WZ0), (XR, WY1, WZ1), (XR + WALL_T, WY1, WZ1)], pt,
                 name='reveal_head')
    # the sash (painted wood) with its bars: a quad in the glass plane, the panes are holes
    Xg = XR + WALL_T * 0.6
    res = 600
    ww, hh = int((WZ1 - WZ0) * res), int((WY1 - WY0) * res)
    zz = WZ1 - (np.arange(ww) + 0.5) / res                 # texture x runs from far (WZ1) to near
    yy = WY1 - (np.arange(hh) + 0.5) / res
    ZZ, YY = np.meshgrid(zz, yy)
    Q = np.stack([np.full_like(ZZ, Xg), YY, ZZ], -1).reshape(-1, 3)
    a = 1 - window_aperture(Q).reshape(hh, ww)
    a = blur(a, 0.8)
    paint = K.mat('wood_painted-green', mean=0.30, sat=0.30, tint=(0.92, 0.94, 1.0))
    sash = tile(paint, ww, hh, seed=8, scale=1.5 * res / paint.shape[1], tone_var=0.15)
    sash *= (0.7 + 0.3 * blur(a, 3))[..., None]
    sc.draw_quad([(Xg, WY1, WZ1), (Xg, WY1, WZ0), (Xg, WY0, WZ0), (Xg, WY0, WZ1)], sash, alpha=a, spec=0.15,
                 gloss=20, name='sash')
    # grime on the glass catching the moon
    g = K.value_noise(ww, hh, 40, 31, octaves=3)
    grime = np.clip((g - 0.45) * 0.6, 0, 1) * (1 - a)
    gl = np.zeros((hh, ww, 3), np.float32) + K.hexcol('#cfc8ff', False)
    sc.draw_quad([(Xg - 0.005, WY1, WZ1), (Xg - 0.005, WY1, WZ0), (Xg - 0.005, WY0, WZ0), (Xg - 0.005, WY0, WZ1)],
                 gl, alpha=grime * 0.35, lit=False, emit=0.10, name='grime', zwrite=False)


def curtains(sc):
    """two heavy velvet drapes, tied back, standing a little off the wall."""
    res = 400
    Xc = XR - 0.12
    for k, (za, zb_) in enumerate(((WZ1 - 0.08, WZ1 + 0.46), (WZ0 - 0.44, WZ0 + 0.08))):
        ya, yb = WY0 - 0.55, WY1 + 0.30
        ww, hh = int((zb_ - za) * res), int((yb - ya) * res)
        t, a = so.velvet_curtain(ww, hh, res, 70 + k, inner_right=(k == 0))
        # tied back: pinch the drape toward the outer edge around 1.1 m
        Y = yb - (np.arange(hh) + 0.5) / res
        pinch = np.exp(-((Y - 1.05) / 0.35) ** 2) * 0.45
        u = np.arange(ww, dtype=np.float32) / ww
        keep = (u[None, :] > pinch[:, None]) if k == 0 else (u[None, :] < 1 - pinch[:, None])
        a = a * blur(keep.astype(np.float32), 1.0)
        corners = [(Xc, yb, zb_), (Xc, yb, za), (Xc, ya, za), (Xc, ya, zb_)]
        sc.draw_quad(corners, t, alpha=a, name=f'curtain{k}', spec=0.1, gloss=8)
    # the brass rod
    brass = K.mat('metal_brass-brushed', mean=0.40, sat=0.5, tint=(1.0, 0.9, 0.72))
    rt = tile(brass, 400, 12, seed=5, scale=0.4)
    rt *= so.profile_shade(12, np.sin(np.linspace(0, math.pi, 12)) * 2)[:, None, None]
    ry = WY1 + 0.32
    sc.draw_quad([(XR - 0.05, ry + 0.012, WZ1 + 0.40), (XR - 0.05, ry + 0.012, WZ0 - 0.38),
                  (XR - 0.05, ry - 0.012, WZ0 - 0.38), (XR - 0.05, ry - 0.012, WZ1 + 0.40)], np.clip(rt, 0, 1),
                 name='rod', spec=0.5, gloss=25)


def settle(sc):
    """a long plain oak bench against the right wall: seat, aprons, four square legs (they cast moon shadows)."""
    z0, z1 = SETTLE
    x1 = XR - 0.03
    x0 = x1 - 0.36

    def oak(seed, mean=0.27, rot=False):
        def f(wp, hp, face):
            t = so.wood('wood_dark-varnished', wp, hp, 700, 2.0, rot=rot, seed=seed, mean=mean)
            e = rect_mask(wp, hp, 0, 0, wp, hp, soft=max(1.2, min(wp, hp) * 0.06))
            return {'tex': np.clip(t * (0.75 + 0.25 * e)[..., None], 0, 1), 'spec': 0.3, 'gloss': 30}
        return f
    sc.box((x0, 0.42, z0), (x1, 0.47, z1), oak(31, 0.30), res=700, name='bench_seat')
    sc.box((x0 + 0.03, 0.34, z0 + 0.05), (x0 + 0.05, 0.42, z1 - 0.05), oak(32, 0.24), res=700, name='bench_apron',
           occluder=False)
    for zz in (z0 + 0.05, z1 - 0.10):
        sc.box((x0 + 0.03, 0.34, zz), (x1 - 0.03, 0.42, zz + 0.02), oak(33, 0.24), res=700, name='bench_rail',
               occluder=False)
    for (xa, za) in ((x0 + 0.03, z0 + 0.05), (x1 - 0.08, z0 + 0.05), (x0 + 0.03, z1 - 0.10), (x1 - 0.08, z1 - 0.10)):
        sc.box((xa, 0.0, za), (xa + 0.05, 0.42, za + 0.05), oak(34, 0.25, rot=True), res=700, name='bench_leg')


def beyond(sc):
    """the dark room behind the far door: a cold sliver of moonlit floor and wall."""
    z0, z1 = ZB + WALL_T, ZB + 3.0
    fl = Plane('floor', 0.0, -2.4, 1.6, z0, z1, name='beyond_floor')
    draw_plane(sc, fl, lambda b, p: K.floor_boards(b, 'floor_dark-planks-grey', 2.0, mean=0.30, sat=0.5, seed=4), None,
               max_res=300)
    back = Plane('back', z1, -2.4, 1.6, 0.0, CEIL)
    draw_plane(sc, back, lambda b, p: K.plaster_band(b, 0.0, CEIL, name='plaster_damp-mossy', size_m=1.8, mean=0.38,
                                                     sat=0.3, seed=8, soot=0.2), None, max_res=250)
    lw = Plane('lwall', -2.4, z0, z1, 0.0, CEIL, name='beyond_l')
    draw_plane(sc, lw, lambda b, p: K.plaster_band(b, 0.0, CEIL, name='plaster_damp-mossy', size_m=1.8, mean=0.36,
                                                   sat=0.3, seed=9, soot=0.2), None, max_res=250)
    for X in (DX0, DX1):
        sc.draw_quad([(X, DTOP, ZB), (X, DTOP, ZB + WALL_T), (X, 0, ZB + WALL_T), (X, 0, ZB)],
                     so.wood('wood_dark-varnished', 60, 300, 500, 2.0, rot=True, seed=3, mean=0.24), name='reveal')
    sc.draw_quad([(DX0, DTOP, ZB), (DX1, DTOP, ZB), (DX1, DTOP, ZB + WALL_T), (DX0, DTOP, ZB + WALL_T)],
                 so.wood('wood_dark-varnished', 300, 60, 500, 2.0, seed=4, mean=0.24), name='reveal_top')
    fx, fz = free_edge()
    zt = ZB + WALL_T * 0.5
    w = DX1 - DX0
    leaf = K.victorian_door(int(w * 420), int(DTOP * 420), paint=None, seed=19, w_m=w, h_m=DTOP, mean=0.22)
    leaf = leaf[:, ::-1].copy()                           # hinged on the right: the knob is on the left
    hx = DX1 - 0.01
    sc.draw_quad([(fx, DTOP - 0.005, fz + WALL_T * 0.5), (hx, DTOP - 0.005, zt), (hx, 0.005, zt),
                  (fx, 0.005, fz + WALL_T * 0.5)], leaf, spec=0.25, gloss=25, name='leaf')


def build_scene():
    cam = K.make_camera(F, CX, CY, EYE)
    sc = ZScene(cam, K.ambient_fn)
    moon = K.MOON
    sc.lights.append(K.XApertureLight(MOON_DIR, moon, power=3.2, plane_x=XR + WALL_T * 0.6, aperture=window_aperture,
                                      shadow_px=1.5, name='moon'))
    wc = np.array([XR - 0.25, (WY0 + WY1) / 2, (WZ0 + WZ1) / 2], np.float32)
    sc.lights.append(PointLight(wc, moon * np.array([0.9, 0.92, 1.0]), power=1.8, soft=0.6,
                                pattern=lambda d: np.clip(-d[:, 0], 0, 1) ** 1.2, wrap=0.3, shadow_px=None,
                                name='window_glow'))
    sP = np.array([XL + 0.16, 1.95, SCONCE_Z], np.float32)
    sc.lights.append(K.sconce_light(sP, +1, power=4.0))
    sc.lights.append(PointLight((0.1, 1.6, SCONCE_Z + 0.4), K.AMBER, power=2.0, soft=1.0, wrap=0.4, shadow_px=None,
                                name='bounce'))
    sc.lights.append(K.PortalLight(BEYOND_MOON, moon * np.array([0.8, 0.85, 1.0]), power=6.0, plane_z=ZB,
                                   aperture=door_aperture, soft=0.6, wrap=0.0, soft_px=2.5, name='beyond'))
    sc.lights.append(PointLight((0.0, 2.4, -0.6), moon * np.array([0.85, 0.85, 1.0]), power=2.2, soft=1.5, wrap=0.3,
                                shadow_px=None, name='fill'))
    z0, z1 = SETTLE
    sc.add_occluder('bench_top', (XR - 0.39, 0.40, z0), (XR - 0.03, 0.47, z1))
    sky(sc)
    beyond(sc)
    draw_plane(sc, Plane('back', ZB, XL, XR, 0.0, CEIL), far_painter, None, max_res=450)
    draw_plane(sc, Plane('ceil', CEIL, XL, XR, 0.6, ZB), ceil_painter, zbreaks(0.6, ZB, 1.42), max_res=520)
    draw_plane(sc, Plane('floor', 0.0, XL, XR, 1.8, ZB), floor_painter, zbreaks(1.8, ZB, 1.42), max_res=700,
               spec=0.3, gloss=30)
    window_parts(sc)
    draw_plane(sc, Plane('lwall', XL, 0.3, ZB, 0.0, CEIL), left_painter, zbreaks(0.3, ZB, 1.42), max_res=650)
    draw_plane(sc, Plane('rwall', XR, 0.3, ZB, 0.0, CEIL), right_painter, zbreaks(0.3, ZB, 1.42), max_res=650)
    curtains(sc)
    settle(sc)
    for (z0, z1, y0, y1, name, oval) in PAINTINGS:
        X = XR - 0.03
        C = [(X, y1, z1), (X, y1, z0), (X, y0, z0), (X, y0, z1)]
        K.framed_painting(sc, C, name, z1 - z0, y1 - y0, res=520, frame=0.075, seed=int(z0 * 10), oval=oval)
    K.sconce(sc, XL, +1, 1.95, SCONCE_Z, seed=5)
    return sc


def render(seed=61):
    sc = build_scene()
    K.halo(sc, (XL + 0.16, 1.97, SCONCE_Z), 0.6, 0.20, K.AMBER * np.array([1.0, 0.9, 0.75]))
    K.halo(sc, (XL + 0.16, 1.95, SCONCE_Z), 0.12, 0.45, K.AMBER)
    lin = sc.downsample()
    moonL = [l for l in sc.lights if l.name == 'moon'][0]
    lin = lin + K.volumetric(sc.cam, sc.depth_out(), moonL, 0.8, ZB, n=40, density=0.010)
    y = K.finish_cam(lin, seed)
    return y, lin, sc


def poses():
    cam = K.make_camera(F, CX, CY, EYE)
    return [K.pose_for(cam, 0.35, 3.05), K.pose_for(cam, 0.45, 4.6), K.pose_for(cam, -0.15, 6.35)]


def build(out_path):
    y, _, _ = render()
    save_jpeg(pil(y), out_path, quality=84, max_kb=880)
    return out_path


if __name__ == '__main__':
    import time
    t = time.time()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/cam6.png')
    y, lin, sc = render()
    pil(y).save(out)
    K.overlay(y, sc.cam, poses(), vp=(CX, CY)).save(str(out).replace('.png', '_ov.png'))
    print('saved', out, f'{time.time() - t:.1f}s')
