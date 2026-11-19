"""THE MENU: menu.jpg (1600 x 900) + menu_light.png + menu_fog.png. No monster anywhere.

The dark upstairs hall at night, seen standing at its near end. Too long (15.5 m). Halfway down on the
right a door stands ajar and warm lamplight spills out of the gap: a wedge of amber across the floorboards
and the crimson runner, climbing the opposite wall. At the far end a tall window holds a moon far too big;
its cold light lies on the floor in front of it, and fog hangs low in the far half of the hall.

    camera    f = 900 px, centre x 1060 (the vanishing point sits right of centre), horizon y 405, eye 1.55 m
    the left ~45 % (x < 720) is the near left wall in deep shadow: calm and dark for the title and buttons
    the door gap and its light: x ~1235..1290, y ~290..690; the warm wedge on the floor y ~595..690

menu.jpg has the warm light baked in at 80 %. menu_light.png is the warm light on its own (RGBA, made for
globalCompositeOperation 'lighter': adding it at globalAlpha a gives the light at 80 % + a x 100 %), so the
game can let it breathe/flicker between ~80 % (a = 0) and ~105 % (a = 0.25).
menu_fog.png is a soft lavender fog band (1600 x 420, seamless left-right) to drift slowly across the floor.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scene_office as so  # noqa: E402
import scene_doors as sd  # noqa: E402
from common import (Camera, PointLight, ApertureLight, blur, edge_ao, f32, hexcol, lin2srgb, load, lum,  # noqa: E402
                    match_albedo, paste_over, pil, rect_mask, resize_f, save_jpeg, smoothstep, srgb2lin, tile,
                    value_noise, LANCZOS)
from grade import finish  # noqa: E402
from scenekit import (DepthScene, draw_lod, mean_lum255, panel_door, paper, src, wood_grain)  # noqa: E402

OUT = 'menu.jpg'
OUT_LIGHT = 'menu_light.png'
OUT_FOG = 'menu_fog.png'
W, H, SS = 1600, 900, 2
F, CX, CY, EYE = 900.0, 1060.0, 405.0, 1.55
HX0, HX1, YC = -1.15, 1.15, 3.05
Z0, ZE = 0.9, 15.5
DOOR_B = (5.0, 5.9)                 # the door left ajar (right wall)
AJAR = math.radians(15)
LAMP = np.array([2.35, 1.30, 6.75], np.float32)     # the lamp inside that room (beyond the door)
MOON = hexcol('#cfc8ff')
AMBER = hexcol('#ffb466') * np.array([1.0, 0.93, 0.80], np.float32)
BAKED_WARM = 0.80
GAIN = 2.9                          # overall exposure of the hall (all lights and glows together)

GEOMETRY = dict(size=(W, H), vp=(CX, CY), calm_left_until=720, door_gap=(1235, 290, 55, 400),
                warm_wedge_y=(595, 690), window=None)


def X_at(u, Z):
    return (u - CX) * Z / F


def latch():
    """the leaf hangs on its near edge (z 5.0) and has swung 15 degrees into the room: its free edge (x, z)."""
    return np.array([HX1 + 0.9 * math.sin(AJAR), DOOR_B[0] + 0.9 * math.cos(AJAR)], np.float32)


def gap_pattern():
    """the warm lamp only reaches the hall through the part of the doorway the leaf does not cover."""
    Lx, Lz = LAMP[0], LAMP[2]
    lx, lz = latch()
    # the line from the lamp past the leaf's latch edge meets the wall plane at z*
    t = (HX1 - Lx) / (lx - Lx)
    zstar = Lz + t * (lz - Lz)

    def pat(d):
        dx = np.where(np.abs(d[:, 0]) < 1e-6, -1e-6, d[:, 0])
        t = (HX1 - LAMP[0]) / dx
        qz = LAMP[2] + d[:, 2] * t
        qy = LAMP[1] + d[:, 1] * t
        e = np.minimum(np.minimum(qz - zstar, DOOR_B[1] - qz), np.minimum(qy, 2.12 - qy))
        shade = 0.30 + 0.70 * np.clip(0.6 - d[:, 1] * 2.0, 0, 1)        # a lamp shade: little goes up
        return (np.clip(e / 0.025 + 0.5, 0, 1) * (t > 0) * shade).astype(np.float32)
    return pat, zstar


# ==========================================================================
def side_board(which, seed):
    res = 300
    b = so.Board(Z0, ZE + 0.02, 0.0, YC, res)
    sd.paper_band(b, 'wallpaper_rijks-dark-umbel-design', 0.53, so.DADO_Y, 2.40, seed, mean=0.20, sat=0.55,
                  tint=(1.0, 0.98, 1.0), contrast=1.15, px=988, py=870)
    so.dado(b, seed=seed + 2)
    so.frieze(b, 2.40, YC, seed=seed + 1)
    so.hmoulding(b, 2.38, 2.425, [.2, .7, 1, .8, .4, .6, .2], seed + 3, mean=0.30)
    so.hmoulding(b, YC - 0.12, YC, [.1, .3, .6, .9, 1, .9, .7, .5, .3], seed + 4, mean=0.32, shadow=0.0)
    lt = (0.4, 0.5, 0.75)
    if which == 'left':
        sd.hang_painting(b, 'painting_kuindzhi-night-on-the-dnieper', 3.30, 4.45, 1.25, 2.05, seed + 10)
        sd.side_door(b, 6.10, 7.00, seed + 20, light=lt)
        sd.hang_painting(b, 'painting_hammershoi-white-doors', 8.30, 8.95, 1.30, 1.98, seed + 30)
        sd.side_door(b, 10.60, 11.50, seed + 40, light=lt)
    else:
        sd.side_door(b, 2.20, 3.10, seed + 50, light=lt)
        # the door left ajar: its casing, and a hole where the doorway is
        so.door_trim(b, DOOR_B[0], DOOR_B[1], 2.12, seed=seed + 60)
        ys, xs = b.sl(DOOR_B[0], DOOR_B[1], -0.01, 2.12)
        b.alpha[ys, xs] = 0
        sd.hang_painting(b, 'painting_grimshaw-street-moonlight', 7.10, 8.45, 1.45, 1.97, seed + 70)
        sd.side_door(b, 10.30, 11.20, seed + 80, light=lt)
    b.ao *= edge_ao(b.x1 - b.x0, b.y1 - b.y0, res, {'bottom': (0.45, 0.06), 'top': (0.35, 0.10),
                                                   'right': (0.4, 0.15)})[:b.h, :b.w]
    return b


def draw_walls(sc):
    for which, X in (('left', HX0), ('right', HX1)):
        b = side_board(which, 300 if which == 'left' else 400)
        if which == 'left':
            corners = [(X, b.y1, b.x0), (X, b.y1, b.x1), (X, 0.0, b.x1), (X, 0.0, b.x0)]
            alb, ao, al = b.alb, b.ao, b.alpha
        else:
            corners = [(X, b.y1, b.x1), (X, b.y1, b.x0), (X, 0.0, b.x0), (X, 0.0, b.x1)]
            alb, ao, al = b.alb[:, ::-1], b.ao[:, ::-1], b.alpha[:, ::-1]
        draw_lod(sc, corners, np.ascontiguousarray(alb), ao=np.ascontiguousarray(ao), alpha=np.ascontiguousarray(al),
                 axis=1, n=8, power=1.8 if which == 'left' else 0.55, name=f'wall_{which}')


def draw_end_wall(sc):
    """the far end: a tall window with velvet curtains, the moon in it."""
    res = 260
    b = so.Board(HX0 - 0.02, HX1 + 0.02, 0.0, YC, res)
    sd.paper_band(b, 'wallpaper_rijks-dark-umbel-design', 0.53, so.DADO_Y, 2.40, 905, mean=0.20, sat=0.55,
                  contrast=1.15, px=988, py=870)
    so.dado(b, seed=906)
    so.frieze(b, 2.40, YC, seed=907)
    wx0, wx1, wy0, wy1 = -0.55, 0.55, 0.62, 2.62
    window_and_curtains(b, wx0, wx1, wy0, wy1)
    b.ao *= edge_ao(b.x1 - b.x0, b.y1 - b.y0, res, {'left': (0.5, 0.1), 'right': (0.5, 0.1), 'top': (0.4, 0.1),
                                                   'bottom': (0.45, 0.06)})[:b.h, :b.w]
    # sky beyond (emissive): stars, the too-big moon, pines in mist
    Zs = ZE + 0.8
    s = 600
    sw, sh = int(1.9 * s / 2), int(2.6 * s / 2)
    sky = f32(load('sky_ph-milky-way'))[150:150 + 900, 700:700 + 660]
    sky = resize_f(sky, sw, sh, LANCZOS)
    Lsk = lum(sky)
    stars = np.clip((Lsk - 0.42) * 3.0, 0, 1) ** 1.2
    yy = np.linspace(0, 1, sh)[:, None, None]
    img = hexcol('#080c26', False) * (1 - yy) + hexcol('#211b4c', False) * yy + stars[..., None] * 0.7
    mr = int(sw * 0.26)
    mc = (int(sw * 0.56), int(sh * 0.30))
    yy2, xx2 = np.mgrid[0:sh, 0:sw].astype(np.float32)
    d = np.sqrt((xx2 - mc[0]) ** 2 + (yy2 - mc[1]) ** 2)
    halo = np.exp(-((d - mr).clip(0) / (mr * 0.35))) * 0.5 + np.exp(-((d - mr).clip(0) / (mr * 1.5))) * 0.25
    img = img + halo[..., None] * hexcol('#cfc8ff', False) * 0.55
    moon = f32(load('moon_nasa-full-moon-photo'))
    ml = lum(moon)
    y3, x3 = np.where(ml > 0.08)
    moon = moon[y3.min():y3.max(), x3.min():x3.max()]
    moon = resize_f(match_albedo(moon, sat=0.1, tint=(0.95, 0.93, 1.0)), 2 * mr, 2 * mr, LANCZOS)
    g = np.mgrid[0:2 * mr, 0:2 * mr].astype(np.float32)
    rr = np.sqrt((g[1] - mr + .5) ** 2 + (g[0] - mr + .5) ** 2)
    mm = np.clip((mr - 1.0 - rr) / 1.5, 0, 1)
    paste_over(img, (0.25 + 0.85 * moon) * (1 - 0.25 * (rr / mr) ** 4)[..., None], mm, mc[0] - mr, mc[1] - mr)
    pines = f32(load('fog_ph-misty-pines'))[150:1350, 400:1700]
    pl = resize_f(lum(pines), sw, int(sw * 1200 / 1300), LANCZOS)
    top = sh - pl.shape[0] // 2
    reg = img[top:]
    s2 = np.clip((0.8 - pl[:reg.shape[0]]) * 2.0, 0, 1) * np.clip(np.linspace(-0.2, 1.4, reg.shape[0]), 0, 1)[:, None]
    reg[:] = reg * (1 - s2[..., None] * 0.95) + hexcol('#2a2650', False) * 0.3 * s2[..., None] * 0.95
    sc.draw_quad([(-0.95, 2.95, Zs), (0.95, 2.95, Zs), (0.95, 0.35, Zs), (-0.95, 0.35, Zs)], np.clip(img, 0, 1),
                 lit=False, emit=1.6, name='sky')
    # the sash bars
    sash = np.zeros((int(2.0 * 300), int(1.1 * 300), 3), np.float32) + 0.20
    a = np.zeros(sash.shape[:2], np.float32)
    fr = 14
    a[:fr] = 1; a[-fr:] = 1; a[:, :fr] = 1; a[:, -fr:] = 1
    for k in (1, 2, 3):
        a[int(a.shape[0] * k / 4) - 4:int(a.shape[0] * k / 4) + 4] = 1
    a[:, a.shape[1] // 2 - 5:a.shape[1] // 2 + 5] = 1
    sc.draw_quad([(wx0, wy1, ZE + 0.10), (wx1, wy1, ZE + 0.10), (wx1, wy0, ZE + 0.10), (wx0, wy0, ZE + 0.10)], sash,
                 alpha=blur(a, 0.8), name='sash')
    sc.draw_quad([(b.x0, b.y1, ZE), (b.x1, b.y1, ZE), (b.x1, 0, ZE), (b.x0, 0, ZE)], b.alb, alpha=b.alpha, ao=b.ao,
                 name='end_wall')
    return (wx0, wx1, wy0, wy1)


def window_and_curtains(b, X0, X1, Y0, Y1):
    """a hole in the board, the office's fluted casing round it, velvet drapes drawn back on a brass rod."""
    res = b.res
    ys, xs = b.sl(X0, X1, Y0, Y1)
    b.alpha[ys, xs] = 0
    cw = 0.085
    for a, c in ((X0 - cw, X0), (X1, X1 + cw)):
        ys, xs = b.sl(a, c, Y0 - 0.06, Y1 + cw)
        b.alb[ys, xs] = so.fluted(xs.stop - xs.start, ys.stop - ys.start, 141, flutes=2)
        b.shadow(a, c, Y0 - 0.06, Y1 + cw, 0.4, 0.015, dy=-0.004)
    ys, xs = b.sl(X0, X1, Y1, Y1 + cw)
    b.alb[ys, xs] = so.fluted(xs.stop - xs.start, ys.stop - ys.start, 143, vertical=False, flutes=2)
    rod_y = Y1 + 0.13
    brass = src('metal_brass-brushed', mean=0.45, sat=0.5, tint=(1.0, 0.9, 0.72))
    ys, xs = b.sl(X0 - 0.32, X1 + 0.32, rod_y - 0.012, rod_y + 0.012)
    b.alb[ys, xs] = tile(brass, xs.stop - xs.start, ys.stop - ys.start, seed=5, scale=0.4)
    for k, (Xa, Xb) in enumerate(((X0 - 0.30, X0 + 0.10), (X1 - 0.10, X1 + 0.30))):
        ys, xs = b.sl(Xa, Xb, 0.05, rod_y + 0.01)
        hh, ww = ys.stop - ys.start, xs.stop - xs.start
        t, a = so.velvet_curtain(ww, hh, res, 70 + k, inner_right=(k == 0))
        b.alb[ys, xs] = t * a[..., None] + b.alb[ys, xs] * (1 - a[..., None])
        b.alpha[ys, xs] = np.maximum(b.alpha[ys, xs], a)
        sh = np.zeros((b.h, b.w), np.float32)
        sh[ys, xs] = a
        b.ao *= 1 - 0.4 * blur(np.roll(sh, int(0.015 * res), 0), 0.03 * res) * (1 - sh)


def draw_floor(sc):
    res = 300
    w_m, d_m = HX1 - HX0, ZE - Z0 + 0.05
    w, h = int(w_m * res), int(d_m * res)
    t = src('floor_dark-varnished', mean=0.22, sat=0.55, tint=(0.95, 0.92, 0.92))
    t = np.ascontiguousarray(np.rot90(t))
    fl = tile(t, w, h, seed=511, tone_var=0.12, scale=2.0 * res / t.shape[1])
    # the crimson runner down the middle (Met Lotto carpet field, end to end, with dark guard borders)
    rug = src('rug_lotto-lattice', mean=0.22, sat=0.60, tint=(1.0, 0.84, 0.90))
    rug = rug[:, :int(rug.shape[1] * 0.80)]
    rug = np.ascontiguousarray(np.rot90(rug))
    rw = int(0.82 * res)
    seg = resize_f(rug, rw, int(rw * rug.shape[0] / rug.shape[1]), LANCZOS)
    run = tile(seg, rw, h, seed=3, offset=(0, 40), tone_var=0.12)
    edge = np.ones(rw, np.float32)
    bw = int(0.06 * res)
    edge[:bw] = 0.45; edge[-bw:] = 0.45
    run *= edge[None, :, None]
    run *= (0.8 + 0.3 * value_noise(rw, h, 120, 7, 3))[..., None]
    x0 = int((0.0 - 0.41 - HX0) * res)
    m = rect_mask(rw, h, 0, 0, rw, h, soft=1.5)
    fl[:, x0:x0 + rw] = run * m[..., None] + fl[:, x0:x0 + rw] * (1 - m[..., None])
    ao = edge_ao(w_m, d_m, 50, {'left': (0.55, 0.08), 'right': (0.55, 0.08), 'top': (0.4, 0.08)})
    draw_lod(sc, [(HX0, 0, ZE + 0.02), (HX1, 0, ZE + 0.02), (HX1, 0, Z0 - 0.03), (HX0, 0, Z0 - 0.03)], fl, ao=ao, axis=0,
             n=8, power=0.5, spec=0.55, gloss=30, name='floor')


def draw_ceiling(sc):
    res = 220
    c = src('plaster_ceiling-textured', mean=0.26, sat=0.3, tint=(0.96, 0.95, 1.0))
    w, h = int((HX1 - HX0) * res), int((ZE - Z0) * res)
    t = tile(c, w, h, seed=7, tone_var=0.15, scale=2.0 * res / c.shape[1])
    ao = edge_ao(HX1 - HX0, ZE - Z0, 50, {'left': (0.55, 0.12), 'right': (0.55, 0.12)})
    draw_lod(sc, [(HX0, YC, ZE), (HX1, YC, ZE), (HX1, YC, Z0), (HX0, YC, Z0)], t, ao=ao, axis=0, n=6, power=0.5,
             name='ceiling')


def draw_ajar_door(sc, warm):
    """the room behind the door (warm, emissive), the leaf standing open a little, the jamb."""
    # the room: a lit far wall and floor seen through the gap
    res = 200
    rw = src('misc_wallpaper-1880-olive-floral', mean=0.45, sat=0.5)
    wall = tile(rw, int(2.6 * res), int(2.5 * res), seed=3, scale=0.5 * res / rw.shape[1] * 1.0)
    yy = np.linspace(0, 1, wall.shape[0])[:, None, None]
    xx = np.linspace(0, 1, wall.shape[1])[None, :, None]
    glow = np.exp(-((xx - 0.25) / 0.35) ** 2 - ((yy - 0.55) / 0.45) ** 2)
    em = wall * (0.25 + 0.9 * glow) * np.array([1.0, 0.78, 0.50])
    # (seen through the doorway at a slant, our eye lands on the room's far wall, z 7.2, facing the hall end)
    sc.draw_quad([(HX1, 2.5, 7.2), (3.6, 2.5, 7.2), (3.6, 0.0, 7.2), (HX1, 0.0, 7.2)], np.zeros_like(em),
                 emissive=np.clip(em, 0, 1), emit=3.4 * warm, lit=False, name='room_wall')
    fl = src('floor_old-oak-dark', mean=0.3, sat=0.6)
    flt = tile(fl, int(1.9 * res), int(2.6 * res), seed=5, scale=2.0 * res / fl.shape[1])
    gl = np.exp(-((np.linspace(0, 1, flt.shape[1])[None, :] - 0.6) / 0.5) ** 2)[..., None]
    sc.draw_quad([(HX1, 0.0, 7.2), (3.6, 0.0, 7.2), (3.6, 0.0, 4.6), (HX1, 0.0, 4.6)], np.zeros_like(flt),
                 emissive=np.clip(flt * gl * np.array([1.0, 0.75, 0.48]) * 1.0, 0, 1), emit=1.6 * warm, lit=False,
                 name='room_floor')
    # the leaf, hung on its near edge and swung 15 degrees into the room: from here we see its room side,
    # lit by the lamp in there
    lx, lz = latch()
    lampl = PointLight(LAMP, AMBER, 7.0, soft=0.35, wrap=0.1, shadow_px=None)
    room_light = lambda P, N: lampl.irradiance(P, N, sc, None) * warm
    alb, ao, _ = panel_door(0.9, 2.1, 400, leaves=1, seed=611, knob='left', rows=[(0.24, 0.80), (0.98, 1.95)],
                            light=(-0.6, 0.4, 0.7))
    sc.draw_quad([(lx, 2.1, lz), (HX1, 2.1, DOOR_B[0]), (HX1, 0.0, DOOR_B[0]), (lx, 0.0, lz)], alb, ao=ao, spec=0.3,
                 gloss=30, name='leaf', extra_light=room_light)
    # the far jamb (faces us), lit from the room
    jamb = wood_grain('wood_dark-varnished', 40, 600, 300, 2.0, along='y', seed=3, mean=0.25)
    sc.draw_quad([(HX1, 2.12, DOOR_B[1]), (HX1 + 0.13, 2.12, DOOR_B[1]), (HX1 + 0.13, 0, DOOR_B[1]), (HX1, 0, DOOR_B[1])],
                 jamb, name='jamb_far', extra_light=room_light)


def warm_air(sc, zstar, strength):
    """light scattering in the dusty air: a soft warm wedge from the gap across the hall (screen space)."""
    cam = sc.cam
    pts = []
    for y in (0.0, 2.1):
        for z in (zstar, DOOR_B[1]):
            P = np.array([HX1, y, z])
            d = P - LAMP
            t = (HX0 - LAMP[0]) / d[0]
            pts.append((P, LAMP + d * t))
    acc = np.zeros((cam.H, cam.W), np.float32)
    from PIL import ImageDraw
    img = Image.new('L', (cam.W, cam.H), 0)
    dr = ImageDraw.Draw(img)
    quad = [pts[0][0], pts[1][0], pts[3][0], pts[2][0]]
    farq = [pts[0][1], pts[1][1], pts[3][1], pts[2][1]]
    for k in range(12):
        f = k / 11
        poly = [quad[i] * (1 - f) + farq[i] * f for i in range(4)]
        S = cam.project_ss(np.asarray(poly))
        dr.polygon([tuple(p) for p in S], fill=int(255 * (1 - f) ** 1.6 / 12))
    acc = blur(f32(img), 10 * cam.ss)
    sc.canvas += (acc * strength)[..., None] * AMBER[None, None, :]


def apply_fog(sc, window):
    """low fog in the far half of the hall, faintly lit by the moon window (and, by the warm wedge, warm)."""
    z = np.minimum(sc.zbuf, 40.0)
    cam = sc.cam
    v = (np.arange(cam.H, dtype=np.float32)[:, None] + 0.5) / cam.ss
    Y = EYE - (v - CY) * z / F                                  # height of the surface behind each pixel
    dens = (1 - np.exp(-np.clip(z - 4.0, 0, None) / 14.0)) * (0.35 + 0.65 * np.exp(-np.clip(Y, 0, None) / 0.9))
    n = value_noise(cam.W, cam.H, 120 * cam.ss, 31, octaves=3)
    dens *= 0.75 + 0.5 * n
    wc = cam.project_ss(np.array([0.0, 1.6, ZE]))
    yy, xx = np.mgrid[0:cam.H, 0:cam.W].astype(np.float32)
    near_win = np.exp(-np.sqrt((xx - wc[0]) ** 2 + ((yy - wc[1]) * 1.4) ** 2) / (260 * cam.ss))
    col = np.array([0.020, 0.020, 0.045], np.float32)[None, None, :] + MOON[None, None, :] * (0.10 * near_win)[..., None]
    k = np.clip(dens * 0.85, 0, 0.9)[..., None]
    sc.canvas[:] = sc.canvas * (1 - k) + col * k


def render_scene(warm):
    cam = Camera(W, H, F, CX, CY, EYE, ss=SS)
    rng_state = so.RNG.bit_generator.state           # the office's shared RNG (dado / paper offsets):
    so.RNG.bit_generator.state = np.random.default_rng(5400).bit_generator.state   # same start in any build order
    amb = np.array(so.AMBIENT, np.float32) * 0.30
    sc = DepthScene(cam, lambda P, N: np.broadcast_to(amb * (0.8 + 0.2 * np.clip(N[:, 1:2], -1, 1)), P.shape)
                    .astype(np.float32))
    pat, zstar = gap_pattern()
    if warm > 0:
        sc.lights.append(PointLight(LAMP, AMBER, 26.0 * warm, soft=0.35, pattern=pat, wrap=0.1, shadow_px=2.0,
                                    name='lamp'))
    # the moon through the far window, laid down the floor toward us
    wx0, wx1, wy0, wy1 = -0.55, 0.55, 0.62, 2.62

    def ap(Q):
        x, y = Q[:, 0], Q[:, 1]
        e = np.minimum(np.minimum(x - wx0 - 0.05, wx1 - 0.05 - x), np.minimum(y - wy0 - 0.05, wy1 - 0.05 - y))
        inside = np.clip(e / 0.02 + 0.5, 0, 1)
        bars = (np.abs(x) < 0.02) | (np.abs(((y - wy0) / (wy1 - wy0) * 4) % 1 - 0.0) < 0.02 * 4 / (wy1 - wy0))
        return inside * (1 - bars)
    sc.lights.append(ApertureLight((0.10, -0.42, -1.0), MOON, power=3.4, plane_z=ZE + 0.05, aperture=ap,
                                   shadow_px=2.5, name='moon'))
    sc.lights.append(PointLight((0.0, 1.7, ZE - 0.25), MOON * 0.9, 4.5, soft=0.8,
                                pattern=lambda d: np.clip(-d[:, 2], 0, 1) ** 1.3, wrap=0.3, shadow_px=None,
                                name='window'))
    sc.lights.append(PointLight((0.3, 2.2, -1.2), MOON * np.array([0.8, 0.8, 1.0], np.float32), 3.0, soft=1.5,
                                wrap=0.3, shadow_px=None, name='fill'))
    draw_end_wall(sc)
    draw_ceiling(sc)
    draw_ajar_door(sc, warm)
    draw_walls(sc)
    draw_floor(sc)
    apply_fog(sc, (wx0, wx1, wy0, wy1))
    if warm > 0:
        warm_air(sc, zstar, 0.10 * warm)
    so.RNG.bit_generator.state = rng_state
    return sc.downsample()


def left_calm(lin):
    """the title and buttons live on the left ~45 %: keep it calmer and darker there."""
    u = (np.arange(W) + 0.5) / W
    k = 0.25 * (1 - smoothstep(0.15, 0.48, u))
    return lin * (1 - k)[None, :, None]


def fog_layer(seed=41):
    """menu_fog.png: a soft, wispy band of lavender fog, seamless left-right, alpha only where it is thick."""
    w, h = W, 420
    # wisps stretched sideways: noise made at half width, then pulled out to the full width
    big = resize_f(value_noise(w // 4, h, 70, seed, octaves=5, persistence=0.55), w, h)
    fine = value_noise(w, h, 50, seed + 1, octaves=3)
    n = big * 0.78 + fine * 0.22
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    band = np.exp(-((yy - 0.62) / 0.30) ** 2)
    a = smoothstep(0.35, 0.85, n) * band * 0.42
    a = blur(a, 3)
    col = np.array([0.62, 0.58, 0.78], np.float32)
    rgba = np.concatenate([np.broadcast_to(col, (h, w, 3)), a[..., None]], -1)
    return rgba


def seamless_x(a):
    """cross-fade so the left and right edges meet (for a band that scrolls sideways)."""
    w = a.shape[1]
    half = w // 2
    b = np.roll(a, half, axis=1)
    ramp = np.abs(np.linspace(-1, 1, w, dtype=np.float32))[None, :]
    ramp = smoothstep(0.0, 1.0, ramp)
    if a.ndim == 3:
        ramp = ramp[..., None]
    return a * (1 - ramp) + b * ramp


def render_all(seed=9):
    on = render_scene(1.0) * GAIN
    off = render_scene(0.0) * GAIN
    on, off = left_calm(on), left_calm(off)
    base = off + (on - off) * BAKED_WARM
    y_base = finish(base, 'menu', seed=seed, return_array=True)
    y_on = finish(on, 'menu', seed=seed, return_array=True)
    y_off = finish(off, 'menu', seed=seed, return_array=True)
    d = np.clip(y_on - y_off, 0, 1)
    d = blur(d, 1.2)                         # the grain cancels out; keep the light itself
    A = np.clip(d.max(-1), 0, 1)
    rgb = np.where(A[..., None] > 1e-4, d / np.maximum(A[..., None], 1e-4), 0)
    light = np.concatenate([np.clip(rgb, 0, 1), A[..., None]], -1)
    fog = fog_layer()
    fog[..., 3] = seamless_x(fog[..., 3])
    return y_base, light, fog


def build(out_path):
    out_dir = Path(out_path).parent
    y, light, fog = render_all()
    save_jpeg(pil(y), out_dir / OUT, quality=84, max_kb=880)
    Image.fromarray((np.clip(light, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA').save(out_dir / OUT_LIGHT, optimize=True)
    Image.fromarray((np.clip(fog, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA').save(out_dir / OUT_FOG, optimize=True)
    return out_path


if __name__ == '__main__':
    import time
    t = time.time()
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/menu')
    outdir.mkdir(parents=True, exist_ok=True)
    y, light, fog = render_all()
    pil(y).save(outdir / 'menu.png')
    Image.fromarray((np.clip(light, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA').save(outdir / 'menu_light.png')
    Image.fromarray((np.clip(fog, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA').save(outdir / 'menu_fog.png')
    print(f'mean {mean_lum255(y):.1f}', f'{time.time() - t:.1f}s')
