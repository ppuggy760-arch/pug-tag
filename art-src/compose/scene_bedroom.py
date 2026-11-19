"""YOUR BEDROOM (the real world), seen from your bed: bedroom.jpg (night) and bedroom_morning.jpg
(the same room in early sun through the blinds), both 1600 x 900.

The geometry is the game's bedroom stand-in (paintBedroom) made real:
    camera    f = 1000 px, centre x 800, horizon y = 364, eye 1.1 m (sitting up in bed)
    BACK WALL z = 3.846 m (260 px per metre): floor line y = 650, skirting 632..650,
              the closet door exactly at EVIDENCE_SPOTS[2] (150.4, 150.3, 270.4 x 500.4),
              the framed moon print at 600,190 170 x 140, the window with blinds at WINDOW_PX
              (1050, 150, 300 x 320), a radiator under it
    TABLE     the bedside table on the right: its top (0.604 m) is at y = 600 where things stand
              (EVIDENCE_SPOTS[3] and the small night clock at (1500, 566) stand on it); no clock is baked
    FLOOR     dark oak boards (the same as the dream's desk room), an oval carpet around (760, 742);
              EVIDENCE_SPOTS[4] (240..360 x 686..720) is clear floor
    QUILT     your quilt over your feet along the bottom (top edge 812 at the left, 776 in the middle,
              770 at the right); the morning alarm clock (800, 770, r 92) is drawn on it by the game
Night: moonlight through the blinds (stripes on the floor and rug), a little warm night-light by the skirting.
Morning: low warm sun through the blinds (stripes on the floor, rug and quilt, dusty shafts), bright sky.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scene_office as so  # noqa: E402
from common import (Camera, Scene, PointLight, ApertureLight, blur, edge_ao, f32, hexcol, lin2srgb, load, lum,  # noqa: E402
                    match_albedo, paste_over, pil, rect_mask, resize_f, save_jpeg, smoothstep, srgb2lin, tile,
                    value_noise, LANCZOS)
from grade import finish  # noqa: E402
from scenekit import draw_lod, ellipse_mask, mean_lum255, panel_door, paper, relief, src, wood_grain  # noqa: E402

OUT = 'bedroom.jpg'
OUT_MORNING = 'bedroom_morning.jpg'
W, H, SS = 1600, 900, 2
F, CX, CY, EYE = 1000.0, 800.0, 364.0, 1.1
ZB = F / 260.0                     # back wall: 260 px per metre
XL, XR = -2.85, 2.60               # side walls
RES_B = 520                        # back wall board px/m (= screen ss density)

GEOMETRY = dict(
    closet=(150.4, 150.3, 270.4, 500.4),          # EVIDENCE_SPOTS[2] * (1600, 900)
    table_spot=(1408.0, 459.0, 112.0, 141.3),     # EVIDENCE_SPOTS[3]
    floor_spot=(240.0, 685.8, 120.0, 34.2),       # EVIDENCE_SPOTS[4]
    window=(1050, 150, 300, 320), moon_print=(600, 190, 170, 140),
    table_top_y=600, night_clock=(1500, 566, 30), morning_clock=(800, 770, 92),
    floor_line_y=650, skirting=(632, 650), rug=(760, 742, 390, 62),
)


def X_at(u, Z):
    return (u - CX) * Z / F


def Y_at(v, Z):
    return EYE - (v - CY) * Z / F


def Z_floor(v, Y=0.0):
    return F * (EYE - Y) / (v - CY)


AMB_NIGHT = np.array(so.AMBIENT, np.float32) * 0.46
MOON = hexcol('#cfc8ff')
AMBER = hexcol('#ffb466') * np.array([1.0, 0.93, 0.80], np.float32)
SUN = np.array([1.0, 0.80, 0.56], np.float32)

# the window and its blinds (world, on the back wall)
WX0, WX1 = X_at(1050, ZB), X_at(1350, ZB)
WY1, WY0 = Y_at(150, ZB), Y_at(470, ZB)
SLAT_PITCH = 21 / 260.0            # the stand-in's slat spacing (21 px)


def slat_gap(Y, open_frac):
    """1 where light passes between the slats (Y on the window plane)."""
    ph = ((WY1 - 0.015 - Y) / SLAT_PITCH) % 1.0
    return smoothstep(1 - open_frac - 0.06, 1 - open_frac + 0.02, ph) * (1 - smoothstep(0.96, 1.0, ph))


# ==========================================================================
# the back wall
# ==========================================================================
DOOR = {}


def back_wall(mode, ajar=False):
    b = so.Board(XL - 0.02, XR + 0.02, 0.0, 2.62, RES_B)
    res = b.res
    # Morris 'Trellis' (roses and little birds) from the skirting to the picture rail, a plain painted frieze above
    t = paper('misc_wallpaper-morris-trellis', 0.53, res, py=1026, sat=0.58, tint=(1.0, 0.98, 0.96), mean=0.51, contrast=0.92)
    ys, xs = b.sl(b.x0, b.x1, 0.07, 2.30)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    p = tile(t, ww, hh, seed=11, offset=(37, 120), tone_var=0.05, tone_cell=res * 0.9)
    X = (np.arange(ww) + 0.5) / res + b.x0
    seam = np.abs((X / 0.53) % 1.0)
    seam = np.minimum(seam, 1 - seam) * 0.53 * res
    p *= (1 - 0.07 * np.exp(-(seam / 1.2) ** 2))[None, :, None]
    # a lived-in room: faint fading, a little grime low down and by the light switch height
    n = value_noise(ww, hh, res * 0.8, 21, octaves=3)
    p *= (0.95 + 0.08 * n)[..., None]
    Yv = 2.30 - (np.arange(hh) + 0.5) / res
    p *= (1 - 0.08 * smoothstep(0.5, 0.07, Yv))[:, None, None]
    b.alb[ys, xs] = np.clip(p, 0, 1)
    paint = np.array([0.56, 0.54, 0.50], np.float32)
    ys, xs = b.sl(b.x0, b.x1, 2.30, b.y1)
    fz = np.zeros((ys.stop - ys.start, xs.stop - xs.start, 3), np.float32) + paint * 0.98
    b.alb[ys, xs] = fz * (0.95 + 0.07 * value_noise(fz.shape[1], fz.shape[0], 60, 3, 3))[..., None]
    # picture rail and skirting (painted, like the woodwork of a child's room)
    painted_moulding(b, 2.285, 2.32, [.2, .7, 1, .8, .4, .6, .2], paint * 0.95, seed=5)
    painted_moulding(b, 0.0, 0.07, [.9, 1, .75, .65, .62, .6, .6, .6, .58], paint * 0.92, seed=6, shadow=0.0)
    b.shadow(b.x0, b.x1, 0.0, 0.07, 0.25, 0.01, dy=0.0)
    # ---- the closet door (exactly the evidence spot), painted, knob on the right
    cx0, cx1 = X_at(150.4, ZB), X_at(150.4 + 270.4, ZB)
    ctop = Y_at(150.3, ZB)
    casing(b, cx0, cx1, ctop, paint, seed=31)
    alb, ao, _ = panel_door(cx1 - cx0, ctop, res, leaves=1, seed=41, cols=2, knob='right', knob_y=0.98,
                            rows=[(0.20, 0.86), (1.00, ctop - 0.13)], light=(0.35, 0.55, 0.75), mean=0.30,
                            paint=np.array([0.60, 0.59, 0.55], np.float32), grime=0.7)
    ys, xs = b.sl(cx0, cx1, 0.0, ctop)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    b.alb[ys, xs] = resize_f(alb, ww, hh)
    b.ao[ys, xs] *= resize_f(ao, ww, hh)
    DOOR.update(alb=b.alb[ys, xs].copy(), ao=b.ao[ys, xs].copy(), x0=cx0, x1=cx1, top=ctop)
    if ajar:                                      # (the morning after Night 2: the door is drawn on its own, open)
        b.alpha[ys, xs] = 0
    # ---- the window opening, its casing, sill and apron
    casing(b, WX0, WX1, WY1, paint, seed=51, floor=False, bottom=WY0)
    ys, xs = b.sl(WX0, WX1, WY0, WY1)
    b.alpha[ys, xs] = 0
    # apron under the sill
    ys, xs = b.sl(WX0 - 0.07, WX1 + 0.07, WY0 - 0.11, WY0 - 0.03)
    ap = np.zeros((ys.stop - ys.start, xs.stop - xs.start, 3), np.float32) + paint * 0.95
    ap *= profile_rows(ap.shape[0], [1, .8, .9, .6])[:, None, None]
    b.alb[ys, xs] = ap
    b.shadow(WX0 - 0.07, WX1 + 0.07, WY0 - 0.11, WY0 - 0.03, 0.35, 0.015, dy=-0.012)
    # ---- the framed moon print
    moon_print(b, mode)
    # ---- a night-light plugged in low on the wall (it glows at night)
    nx, ny = X_at(905, ZB), 0.30
    plate = rect_mask(b.w, b.h, b.px(nx - 0.04), b.py(ny + 0.06), b.px(nx + 0.04), b.py(ny - 0.06), soft=2)
    b.alb = b.alb * (1 - plate[..., None]) + np.array([0.62, 0.60, 0.55]) * plate[..., None]
    b.shadow(nx - 0.04, nx + 0.04, ny - 0.06, ny + 0.06, 0.35, 0.008, dx=0.004, dy=-0.006)
    # creases: floor, corners
    b.ao *= edge_ao(b.x1 - b.x0, b.y1 - b.y0, res, {'bottom': (0.35, 0.05), 'left': (0.45, 0.12),
                                                   'right': (0.45, 0.12)})[:b.h, :b.w]
    return b


def profile_rows(n, prof):
    p = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(prof)), prof).astype(np.float32)
    return 0.75 + 0.35 * p


def painted_moulding(b, Y0, Y1, prof, col, seed, shadow=0.3):
    ys, xs = b.sl(b.x0, b.x1, Y0, Y1)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    if hh <= 0:
        return
    n = value_noise(ww, hh, 30, seed, octaves=2)
    t = np.zeros((hh, ww, 3), np.float32) + col
    t *= (0.94 + 0.1 * n)[..., None]
    t *= so.profile_shade(hh, np.interp(np.linspace(0, 1, hh), np.linspace(0, 1, len(prof)), prof))[:, None, None]
    b.alb[ys, xs] = np.clip(t, 0, 1)
    if shadow:
        b.shadow(b.x0, b.x1, Y0, Y1, shadow, 0.01, dy=-0.01)


def casing(b, X0, X1, Ytop, col, seed, floor=True, bottom=0.0, cw=0.07):
    """a plain painted architrave round an opening (outside X0..X1, up to Ytop)."""
    y0 = 0.0 if floor else bottom - 0.03
    for (a, c) in ((X0 - cw, X0), (X1, X1 + cw)):
        ys, xs = b.sl(a, c, y0, Ytop + cw)
        hh, ww = ys.stop - ys.start, xs.stop - xs.start
        t = np.zeros((hh, ww, 3), np.float32) + col
        prof = so.profile_shade(ww, [.5, .9, 1, .95, .8, .7, .7, .65, .5])
        t *= prof[None, :, None] * (0.95 + 0.08 * value_noise(ww, hh, 40, seed, 2))[..., None]
        b.alb[ys, xs] = np.clip(t, 0, 1)
        b.shadow(a, c, y0, Ytop + cw, 0.30, 0.012, dx=0.0, dy=-0.004)
    ys, xs = b.sl(X0 - cw, X1 + cw, Ytop, Ytop + cw)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    t = np.zeros((hh, ww, 3), np.float32) + col
    t *= so.profile_shade(hh, [.5, .9, 1, .95, .8, .7, .7, .65, .5])[:, None, None]
    b.alb[ys, xs] = np.clip(t, 0, 1)
    b.shadow(X0 - cw, X1 + cw, Ytop, Ytop + cw, 0.30, 0.012, dy=-0.008)


def moon_print(b, mode):
    """a framed print of the moon (NASA photo on a deep blue night, a cream mat, a thin dark frame)."""
    res = b.res
    X0, X1 = X_at(600, ZB), X_at(770, ZB)
    Y1, Y0 = Y_at(190, ZB), Y_at(330, ZB)
    w, h = int(round((X1 - X0) * res)), int(round((Y1 - Y0) * res))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    fr = int(0.028 * res)
    mat_w = int(0.07 * res)
    frame = so.wood('wood_dark-varnished', w, h, res, 2.0, seed=61, mean=0.16)
    d = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy))
    frame *= (0.75 + 0.4 * np.sin(np.clip(d / fr, 0, 1) * math.pi))[..., None]
    matc = src('paper_offwhite-grain', mean=0.62, sat=0.3, tint=(1.0, 0.97, 0.9))
    mt = tile(matc, w, h, seed=62, scale=0.4)
    # bevel of the mat opening catches light
    inner = rect_mask(w, h, fr + mat_w, fr + mat_w, w - fr - mat_w, h - fr - mat_w, soft=1)
    iw, ih = w - 2 * (fr + mat_w), h - 2 * (fr + mat_w)
    # the print: a dark blue night with real stars and the moon
    sky = f32(load('sky_ph-milky-way'))[200:200 + 500, 300:300 + 700]
    sky = resize_f(sky, iw, ih, LANCZOS)
    Ls = lum(sky)
    st = np.clip((Ls - 0.40) * 2.5, 0, 1)
    pr = np.zeros((ih, iw, 3), np.float32) + hexcol('#18204a', False)
    pr = pr * (0.8 + 0.3 * (np.arange(ih) / ih))[:, None, None] + st[..., None] * 0.7
    moon = f32(load('moon_nasa-lro-nearside'))
    ml = lum(moon)
    yy3, xx3 = np.where(ml > 0.06)
    moon = moon[yy3.min():yy3.max(), xx3.min():xx3.max()]
    mr = int(min(iw, ih) * 0.30)
    moon = resize_f(match_albedo(moon, sat=0.15, tint=(1.0, 0.97, 0.88)), 2 * mr, 2 * mr, LANCZOS)
    g = np.mgrid[0:2 * mr, 0:2 * mr].astype(np.float32)
    rr = np.sqrt((g[1] - mr + .5) ** 2 + (g[0] - mr + .5) ** 2)
    mm = np.clip((mr - 0.5 - rr) / 1.2, 0, 1)
    paste_over(pr, np.clip(0.15 + 0.9 * moon, 0, 1), mm, int(iw * 0.58 - mr), int(ih * 0.42 - mr))
    full = frame.copy()
    mat_m = rect_mask(w, h, fr, fr, w - fr, h - fr, soft=1)
    full = full * (1 - mat_m[..., None]) + mt * mat_m[..., None]
    paste_over(full, pr, np.ones((ih, iw), np.float32), fr + mat_w, fr + mat_w)
    # inner shadow of the frame on the mat; a faint sheen on the glass
    lip = 1 - 0.35 * blur(1 - mat_m, 3)
    full *= lip[..., None]
    b.shadow(X0, X1, Y0, Y1, 0.5, 0.02, dx=0.008, dy=-0.02)
    b.put(X0, X1, Y0, Y1, np.clip(full, 0, 1))


# ==========================================================================
# the scene
# ==========================================================================
def ambient_night(P, N):
    up = 0.80 + 0.20 * np.clip(N[:, 1], -1, 1)
    side = 1.0 + 0.08 * np.clip((P[:, 0] - 0.5) / 2.0, -1, 1)
    return AMB_NIGHT[None, :] * (up * side)[:, None]


def ambient_day(P, N):
    up = 0.80 + 0.20 * np.clip(N[:, 1], -1, 1)
    side = 1.0 + 0.12 * np.clip((P[:, 0] - 0.5) / 2.0, -1, 1)
    return np.array([0.44, 0.38, 0.31], np.float32)[None, :] * (up * side)[:, None]


def make_lights(sc, mode):
    day = mode == 'morning'
    open_frac = 0.55 if day else 0.42
    direction = (-0.50, -1.00, -1.0) if day else (-0.32, -1.10, -1.0)

    def ap(Q):
        x, y = Q[:, 0], Q[:, 1]
        e = np.minimum(np.minimum(x - WX0 - 0.02, WX1 - 0.02 - x), np.minimum(y - WY0 - 0.02, WY1 - 0.02 - y))
        inside = np.clip(e / 0.01 + 0.5, 0, 1)
        return inside * slat_gap(y, open_frac)

    wc = np.array([(WX0 + WX1) / 2, (WY0 + WY1) / 2, ZB - 0.15], np.float32)
    toward_room = lambda d: np.clip(-d[:, 2], 0, 1) ** 1.2
    if day:
        sc.lights.append(ApertureLight(direction, SUN, power=12.0, plane_z=ZB + 0.03, aperture=ap, shadow_px=1.5,
                                       name='sun'))
        sc.lights.append(PointLight(wc, np.array([1.0, 0.94, 0.86], np.float32), 8.0, soft=0.7, pattern=toward_room,
                                    wrap=0.3, shadow_px=4.0, name='sky'))
        # sunlight bouncing off the lit floor patch warms the wall and the room
        sc.lights.append(PointLight((0.9, 0.25, 2.9), SUN * 0.9, 1.6, soft=1.0, wrap=0.4, shadow_px=None,
                                    pattern=lambda d: np.clip(d[:, 1] + 0.5, 0, 1), name='bounce'))
        sc.lights.append(PointLight((0.3, 1.6, -1.0), np.array([0.95, 0.88, 0.80], np.float32), 2.6, soft=1.5, wrap=0.3,
                                    shadow_px=None, name='fill'))
    else:
        sc.lights.append(ApertureLight(direction, MOON * np.array([0.85, 0.90, 1.15], np.float32), power=4.2,
                                       plane_z=ZB + 0.03, aperture=ap, shadow_px=1.5, name='moon'))
        sc.lights.append(PointLight(wc, MOON * 0.9, 1.3, soft=0.6, pattern=toward_room, wrap=0.3, shadow_px=4.0,
                                    name='window'))
        sc.lights.append(PointLight((X_at(905, ZB), 0.30, ZB - 0.05), AMBER, 0.08, soft=0.05, wrap=0.3,
                                    pattern=lambda d: np.clip(-d[:, 2] + 0.2, 0, 1), shadow_px=2.0, name='nightlight'))
        # ... and its glow on its own wall plate and the wallpaper round it (so it reads as a plug-in night-light,
        # not a firefly floating in the dark)
        sc.lights.append(PointLight((X_at(905, ZB), 0.315, ZB - 0.022), AMBER, 0.0040, soft=0.035, wrap=0.6,
                                    pattern=lambda d: np.clip(d[:, 2] * 1.4 + 0.3, 0, 1), shadow_px=None,
                                    name='nightlight_wall'))
        sc.lights.append(PointLight((0.9, 0.2, 3.0), MOON * 0.9, 0.45, soft=1.0, wrap=0.4, shadow_px=None,
                                    pattern=lambda d: np.clip(d[:, 1] + 0.5, 0, 1), name='moon_bounce'))
        sc.lights.append(PointLight((0.4, 1.2, -1.0), MOON * np.array([0.85, 0.85, 1.0], np.float32), 0.65, soft=1.5,
                                    wrap=0.3, shadow_px=None, name='fill'))
    return direction, open_frac


def draw_sky(sc, mode):
    """outside the window: night sky with a big moon over misty pines, or a pale morning sky."""
    Z = ZB + 0.9
    u0, u1, v0, v1 = 1020, 1380, 120, 500
    X0, X1 = X_at(u0, Z), X_at(u1, Z)
    Y1, Y0 = Y_at(v0, Z), Y_at(v1, Z)
    s = 2
    w, h = (u1 - u0) * s, (v1 - v0) * s
    yy = np.linspace(0, 1, h)[:, None, None]
    pines = f32(load('fog_ph-misty-pines'))[100:1300, 300:1900]
    pl = lum(pines)
    pl = resize_f(pl, w, int(w * pl.shape[0] / pl.shape[1]), LANCZOS)
    ph = pl.shape[0]
    if mode == 'morning':
        img = hexcol('#a9c4dc', False) * (1 - yy) + hexcol('#f6e6cf', False) * yy
        yy2, xx2 = np.mgrid[0:h, 0:w].astype(np.float32)
        sun = np.exp(-(((xx2 - w * 0.85) / (w * 0.35)) ** 2 + ((yy2 - h * 0.62) / (h * 0.35)) ** 2))
        img = img + sun[..., None] * np.array([1.0, 0.85, 0.6]) * 0.35
        # the misty pines in the morning: soft blue-grey trunks in fog
        top = int(h - ph * 0.85)
        reg = img[max(0, top):]
        s2 = np.clip((0.85 - pl[:reg.shape[0]]) * 1.6, 0, 1)
        a = s2[..., None] * 0.55
        reg[:] = reg * (1 - a) + np.array([0.48, 0.52, 0.55]) * a
        emit = 2.2
    else:
        sky = f32(load('sky_ph-milky-way'))[300:300 + 900, 900:900 + 860]
        sky = resize_f(sky, w, h, LANCZOS)
        Lsk = lum(sky)
        stars = np.clip((Lsk - 0.42) * 3.0, 0, 1) ** 1.2
        img = hexcol('#070b22', False) * (1 - yy) + hexcol('#1d1846', False) * yy
        img = img + stars[..., None] * np.array([0.8, 0.8, 0.95]) * 0.8
        # the moon, too big, upper right of the window
        mc = ((1290 - u0) * s, (215 - v0) * s)
        mr = 52 * s
        yy2, xx2 = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt((xx2 - mc[0]) ** 2 + (yy2 - mc[1]) ** 2)
        halo = np.exp(-((d - mr).clip(0) / (mr * 0.35))) * 0.45 + np.exp(-((d - mr).clip(0) / (mr * 1.4))) * 0.22
        img = img + halo[..., None] * hexcol('#cfc8ff', False)[None, None, :] * 0.55
        moon = f32(load('moon_nasa-full-moon-photo'))
        ml = lum(moon)
        yy3, xx3 = np.where(ml > 0.08)
        moon = moon[yy3.min():yy3.max(), xx3.min():xx3.max()]
        moon = resize_f(match_albedo(moon, sat=0.1, tint=(0.95, 0.93, 1.0)), 2 * mr, 2 * mr, LANCZOS)
        g = np.mgrid[0:2 * mr, 0:2 * mr].astype(np.float32)
        rr = np.sqrt((g[1] - mr + .5) ** 2 + (g[0] - mr + .5) ** 2)
        mm = np.clip((mr - 1.0 - rr) / 1.5, 0, 1)
        moon = (0.22 + 0.85 * moon) * (1 - 0.25 * (rr / mr) ** 4)[..., None]
        paste_over(img, moon, mm, int(mc[0] - mr), int(mc[1] - mr))
        top = int(h - ph * 0.6)
        reg = img[max(0, top):]
        s2 = np.clip((0.80 - pl[:reg.shape[0]]) * 2.0, 0, 1)
        fade = np.clip(np.linspace(-0.2, 1.4, reg.shape[0]), 0, 1)[:, None]
        a = (s2 * fade)[..., None] * 0.95
        fog = hexcol('#2a2650', False)
        reg[:] = reg * (1 - a) + (fog * 0.30)[None, None, :] * a
        emit = 1.0
    sc.draw_quad([(X0, Y1, Z), (X1, Y1, Z), (X1, Y0, Z), (X0, Y0, Z)], np.clip(img, 0, 1), lit=False, emit=emit,
                 name='sky')


def draw_window(sc, mode, open_frac):
    day = mode == 'morning'
    paint = np.array([0.58, 0.56, 0.52], np.float32)
    res = 600
    # the right reveal (faces the room's left) and the head of the opening
    rv = np.zeros((int(0.9 * res), int(0.2 * res), 3), np.float32) + paint * 0.9
    rv *= (0.9 + 0.15 * value_noise(rv.shape[1], rv.shape[0], 30, 4, 2))[..., None]
    sc.draw_quad([(WX1, WY1, ZB), (WX1, WY1, ZB + 0.2), (WX1, WY0, ZB + 0.2), (WX1, WY0, ZB)], rv, name='reveal_r',
                 ao=edge_ao(0.2, WY1 - WY0, 100, {'right': (0.4, 0.04), 'top': (0.4, 0.05)}))
    sc.draw_quad([(WX0, WY1, ZB + 0.2), (WX1, WY1, ZB + 0.2), (WX1, WY1, ZB), (WX0, WY1, ZB)],
                 rv[:int(0.2 * res)].transpose(1, 0, 2).copy() * 0.95, name='reveal_t',
                 ao=edge_ao(WX1 - WX0, 0.2, 100, {'top': (0.45, 0.04)}))
    # the sash: a white-painted frame with a meeting rail, glass beyond the blinds
    sw, sh = int((WX1 - WX0) * res), int((WY1 - WY0) * res)
    sash = np.zeros((sh, sw, 3), np.float32) + paint
    a = np.zeros((sh, sw), np.float32)
    fr = int(0.05 * res)
    a[:fr] = 1; a[-fr:] = 1; a[:, :fr] = 1; a[:, -fr:] = 1
    a[sh // 2 - int(0.022 * res): sh // 2 + int(0.022 * res)] = 1
    a = blur(a, 0.8)
    sash *= (0.75 + 0.25 * blur(a, 3))[..., None]
    sc.draw_quad([(WX0, WY1, ZB + 0.14), (WX1, WY1, ZB + 0.14), (WX1, WY0, ZB + 0.14), (WX0, WY0, ZB + 0.14)], sash,
                 alpha=a, name='sash')
    # the sill (top face)
    sill = np.zeros((int(0.2 * res), int((WX1 - WX0 + 0.2) * res), 3), np.float32) + paint
    sill *= (0.92 + 0.12 * value_noise(sill.shape[1], sill.shape[0], 30, 7, 2))[..., None]
    sc.draw_quad([(WX0 - 0.1, WY0, ZB + 0.16), (WX1 + 0.1, WY0, ZB + 0.16), (WX1 + 0.1, WY0, ZB - 0.05),
                  (WX0 - 0.1, WY0, ZB - 0.05)], sill, name='sill',
                 ao=edge_ao(WX1 - WX0 + 0.2, 0.21, 100, {'top': (0.4, 0.04)}))
    sc.draw_quad([(WX0 - 0.1, WY0, ZB - 0.05), (WX1 + 0.1, WY0, ZB - 0.05), (WX1 + 0.1, WY0 - 0.03, ZB - 0.05),
                  (WX0 - 0.1, WY0 - 0.03, ZB - 0.05)], sill[:20] * 0.9, name='sill_edge')
    # venetian blinds (inside the reveal, near the room): slats with gaps, two ladder cords, a head rail
    bw, bh = int((WX1 - WX0) * res), int((WY1 - WY0) * res)
    Yv = WY1 - (np.arange(bh) + 0.5) / res
    gapm = slat_gap(Yv, open_frac)[:, None] * np.ones((1, bw), np.float32)
    slat = 1 - gapm
    ph = ((WY1 - 0.015 - Yv) / SLAT_PITCH) % 1.0
    curve = 0.75 + 0.35 * np.sin(np.clip(ph / (1 - open_frac), 0, 1) * math.pi)       # each slat is a shallow curve
    col = np.zeros((bh, bw, 3), np.float32) + np.array([0.62, 0.60, 0.56])
    col *= curve[:, None, None] * (0.95 + 0.08 * value_noise(bw, bh, 25, 9, 2))[..., None]
    for fx in (0.22, 0.78):
        xc = int(bw * fx)
        cord = np.zeros(bw, np.float32)
        cord[xc - 1:xc + 2] = 1
        slat = np.maximum(slat, cord[None, :] * 0.85)
        col[:, xc - 1:xc + 2] *= 0.8
    slat[:int(0.045 * res)] = 1                                   # head rail
    col[:int(0.045 * res)] *= 0.85
    slat[-int(0.03 * res):] = 1                                   # bottom rail
    slat = np.clip(slat, 0, 1)
    em = None
    if day:      # thin slats glow with the sun behind them
        em = col * np.array([1.0, 0.85, 0.65]) * 0.35 * (1 - gapm)[..., None]
    sc.draw_quad([(WX0 + 0.005, WY1 - 0.005, ZB + 0.05), (WX1 - 0.005, WY1 - 0.005, ZB + 0.05),
                  (WX1 - 0.005, WY0 + 0.01, ZB + 0.05), (WX0 + 0.005, WY0 + 0.01, ZB + 0.05)], col, alpha=slat,
                 emissive=em, emit=1.0, name='blinds')


def floor_tex(res=420, mode='night'):
    x0, x1, z0, z1 = XL, XR, 0.55, ZB + 0.03
    w, h = int((x1 - x0) * res), int((z1 - z0) * res)
    if mode == 'morning':
        t = src('floor_old-oak-dark', mean=0.30, sat=0.70, tint=(1.0, 0.93, 0.88))
    else:   # under the moon the same boards: less orange, so moonlight on them reads silver, not amber
        t = src('floor_old-oak-dark', mean=0.29, sat=0.42, tint=(0.95, 0.93, 0.98))
    t = np.ascontiguousarray(np.rot90(t))
    fl = tile(t, w, h, seed=71, tone_var=0.12, scale=2.03 * res / t.shape[1])
    # the oval carpet (Met Spanish carpet), worn, with a dark border band and a short fringe of braid
    rcx, rcz, rrx, rrz = -0.12, 2.99, 1.13, 0.49
    rug = src('rug_spanish-medallions', mean=0.27, sat=0.60, tint=(1.0, 0.90, 0.95))
    rw, rd = int(2 * rrx * res), int(2 * rrz * res)
    rr_ = resize_f(rug[60:60 + int(rug.shape[1] * rd / rw * 1.0), :], rw, rd, LANCZOS)
    m = ellipse_mask(rw, rd, rw / 2, rd / 2, rw / 2, rd / 2, soft=2.0)
    band = ellipse_mask(rw, rd, rw / 2, rd / 2, rw / 2 - 0.07 * res, rd / 2 - 0.07 * res, soft=2.0)
    border = src('rug_spanish-end-border', mean=0.18, sat=0.55, tint=(1.0, 0.9, 0.95))
    bt = resize_f(border[:200, :], rw, rd, LANCZOS)
    rr_ = rr_ * band[..., None] + bt * (1 - band[..., None])
    rr_ *= (0.82 + 0.28 * value_noise(rw, rd, 120, 72, 3))[..., None]
    px0, pz0 = int((rcx - rrx - x0) * res), int((z1 - (rcz + rrz)) * res)
    reg = fl[pz0:pz0 + rd, px0:px0 + rw]
    reg[:] = rr_ * m[..., None] + reg * (1 - m[..., None])
    return fl, (x0, x1, z0, z1, res), (rcx, rcz, rrx, rrz)


def draw_floor(sc, mode):
    fl, (x0, x1, z0, z1, res), _ = floor_tex(mode=mode)
    w_m, d_m = x1 - x0, z1 - z0
    tz = lambda z: z1 - z
    rects = [(1.17 - x0, tz(2.32), 1.62 - x0, tz(1.92), 0.6, 0.06),           # under the bedside table
             (X_at(1050, ZB) - x0, 0.0, X_at(1350, ZB) - x0, 0.14, 0.5, 0.05)]  # under the radiator
    blobs = [(X_at(905, ZB) - x0, 0.03, 0.10, 0.05, 0.2)]
    ao = edge_ao(w_m, d_m, 60, {'top': (0.45, 0.06), 'left': (0.4, 0.1), 'right': (0.4, 0.1)}, rects=rects,
                 blobs=blobs)
    draw_lod(sc, [(x0, 0, z1), (x1, 0, z1), (x1, 0, z0), (x0, 0, z0)], fl, ao=ao, axis=0, n=5, power=0.7,
             spec=0.30, gloss=26, name='floor')


def closet_ajar(sc, angle_deg=13.0):
    """Night 2's morning: the closet door stands open a hand's width (hinged on the left, swung out into the room),
    and the dark inside of the closet shows in the gap: a recess with a coat on a hook, the door's own edge."""
    x0, x1, top = DOOR['x0'], DOOR['x1'], DOOR['top']
    depth = 0.55
    # the inside of the closet (behind the wall): dark back and sides, a coat, lit only by what spills in
    t = np.zeros((300, 200, 3), np.float32) + np.array([0.20, 0.18, 0.16], np.float32)
    t *= (0.7 + 0.3 * value_noise(200, 300, 40, 61, 3))[..., None]
    yy, xx = np.mgrid[0:300, 0:200].astype(np.float32)
    coat = ((xx - 150) / 38) ** 2 + ((yy - 140) / 95) ** 2 < 1
    t[coat] *= 0.45
    sc.draw_quad([(x0, top, ZB + depth), (x1, top, ZB + depth), (x1, 0, ZB + depth), (x0, 0, ZB + depth)], t,
                 ao=edge_ao(x1 - x0, top, 60, {'left': (0.6, 0.15), 'right': (0.6, 0.15), 'top': (0.6, 0.2),
                                                'bottom': (0.5, 0.1)}), name='closet_back')
    for X in (x0, x1):
        st = np.zeros((300, 100, 3), np.float32) + np.array([0.24, 0.22, 0.20], np.float32)
        sc.draw_quad([(X, top, ZB), (X, top, ZB + depth), (X, 0, ZB + depth), (X, 0, ZB)], st, name='closet_side')
    return angle_deg


def draw_door_leaf(sc, angle_deg):
    x0, x1, top = DOOR['x0'], DOOR['x1'], DOOR['top']
    w = x1 - x0
    a = math.radians(angle_deg)
    ex, ez = x0 + w * math.cos(a), ZB - w * math.sin(a)          # the free edge, swung out toward us
    sc.draw_quad([(x0, top, ZB - 0.004), (ex, top, ez), (ex, 0.002, ez), (x0, 0.002, ZB - 0.004)], DOOR['alb'],
                 ao=DOOR['ao'], spec=0.15, gloss=20, name='closet_door')
    th = 0.035                                                 # the door's edge, facing the light from the window
    nx, nz = math.cos(a), -math.sin(a)
    ed = np.zeros((300, 12, 3), np.float32) + np.array([0.50, 0.49, 0.45], np.float32)
    sc.draw_quad([(ex, top, ez), (ex + th * math.sin(a), top, ez + th * math.cos(a)),
                  (ex + th * math.sin(a), 0.002, ez + th * math.cos(a)), (ex, 0.002, ez)], ed, name='door_edge')
    # its shadow on the floor in the gap (the sun is on the other side of the room)
    sh = edge_ao(1.0, 1.0, 60, rects=[(0.2, 0.0, 0.8, 0.6, 0.7, 0.15)])
    sc.draw_quad([(x0, 0.003, ZB + 0.02), (ex + 0.1, 0.003, ZB + 0.02), (ex + 0.1, 0.003, ez - 0.25),
                  (x0, 0.003, ez - 0.25)], np.zeros((60, 60, 3), np.float32), alpha=(1 - sh) * 0.55, name='door_shadow')


def collar_scrap(sc):
    """Night 4's morning: a torn scrap of a pink leather collar on the floor, its brass ring, a soft shadow."""
    cam = sc.cam
    fx, fy, fw, fh = GEOMETRY['floor_spot']
    P = cam.on_plane_y(fx + fw * 0.5, fy + fh * 0.55, 0.0)
    cx, cz = P[0], P[2]
    L, Wd, rot = 0.44, 0.07, math.radians(-12)
    res = 1600
    tw, th = int(L * res), int(Wd * res)
    t = tile(src('fabric_leather-brown', mean=0.50, sat=0.55, tint=(1.0, 0.62, 0.70)), tw, th, seed=4, scale=0.25)
    yy, xx = np.mgrid[0:th, 0:tw].astype(np.float32)
    v = yy / th
    t *= (0.78 + 0.32 * np.sin(np.pi * v) ** 0.5)[..., None]                  # rounded edges of the strap
    stitch = (np.abs(v - 0.18) < 0.035) | (np.abs(v - 0.82) < 0.035)
    stitch &= ((xx / (0.006 * res)) % 1.0) < 0.55
    t[stitch] = t[stitch] * 0.55 + 0.35
    # torn end on the left: a ragged edge; the buckle end on the right with a brass D-ring
    rag = 0.10 * th + 0.18 * tw * value_noise(1, th, 3, 7, 2)[:, 0][:, None] * np.ones((1, tw))
    a = (xx > rag).astype(np.float32)
    ring_c, ring_r = (tw * 0.90, th * 0.5), th * 0.42
    rr = np.sqrt((xx - ring_c[0]) ** 2 + (yy - ring_c[1]) ** 2)
    ring = np.abs(rr - ring_r) < th * 0.09
    brass = np.array([0.62, 0.50, 0.30], np.float32)
    t[ring] = brass
    a = np.clip(np.where(xx > tw * 0.86, ring.astype(np.float32) + (xx < tw * 0.88), a), 0, 1)
    a = blur(a, 0.8)
    c, s_ = math.cos(rot), math.sin(rot)

    def pt(u, w_):
        return (cx + u * c - w_ * s_, 0.004, cz + u * s_ + w_ * c)
    # soft contact shadow first, then the scrap
    sh = edge_ao(1.0, 1.0, 60, rects=[(0.25, 0.3, 0.75, 0.7, 0.9, 0.12)])
    sc.draw_quad([pt(-L * 0.7, Wd * 3), pt(L * 0.7, Wd * 3), pt(L * 0.7, -Wd * 3), pt(-L * 0.7, -Wd * 3)],
                 np.zeros((60, 60, 3), np.float32), alpha=(1 - sh) * 0.6, name='scrap_shadow')
    sc.draw_quad([pt(-L / 2, Wd / 2), pt(L / 2, Wd / 2), pt(L / 2, -Wd / 2), pt(-L / 2, -Wd / 2)], np.clip(t, 0, 1),
                 alpha=a, spec=0.35, gloss=30, name='collar')


def draw_walls(sc, mode, ajar=False):
    b = back_wall(mode, ajar)
    sc.draw_quad([(b.x0, b.y1, ZB), (b.x1, b.y1, ZB), (b.x1, 0, ZB), (b.x0, 0, ZB)], b.alb, alpha=b.alpha, ao=b.ao,
                 name='back')
    # the right-hand wall, from the corner toward us (only a sliver above the table shows)
    res = 300
    r = so.Board(0.0, ZB - 2.0 + 0.02, 0.0, 2.62, res)
    t = paper('misc_wallpaper-morris-trellis', 0.53, res, py=1026, sat=0.58, tint=(1.0, 0.98, 0.96), mean=0.51, contrast=0.92)
    ys, xs = r.sl(r.x0, r.x1, 0.07, 2.30)
    r.alb[ys, xs] = tile(t, xs.stop - xs.start, ys.stop - ys.start, seed=13, tone_var=0.05)
    paint = np.array([0.56, 0.54, 0.50], np.float32)
    painted_moulding(r, 2.285, 2.32, [.2, .7, 1, .8, .4, .6, .2], paint * 0.95, seed=8)
    painted_moulding(r, 0.0, 0.07, [.9, 1, .75, .65, .62, .6, .6, .6, .58], paint * 0.92, seed=9, shadow=0.0)
    ys, xs = r.sl(r.x0, r.x1, 2.30, r.y1)
    r.alb[ys, xs] = paint * 0.95
    r.ao *= edge_ao(r.x1, r.y1, res, {'left': (0.45, 0.12), 'bottom': (0.35, 0.05)})[:r.h, :r.w]
    # x = distance from the corner toward us
    sc.draw_quad([(XR, r.y1, ZB), (XR, r.y1, 2.0), (XR, 0, 2.0), (XR, 0, ZB)], r.alb, ao=r.ao, name='right_wall')
    # the left-hand wall sliver
    sc.draw_quad([(XL, r.y1, 2.0), (XL, r.y1, ZB), (XL, 0, ZB), (XL, 0, 2.0)], r.alb[:, ::-1].copy(),
                 ao=r.ao[:, ::-1].copy(), name='left_wall')


def draw_radiator(sc):
    """an old cast-iron column radiator under the window, cream paint gone rusty at the edges."""
    x0, x1 = X_at(1068, ZB) + 0.02, X_at(1332, ZB) - 0.02
    y0, y1 = 0.12, 0.60
    z0 = ZB - 0.13
    res = 700
    w, h = int((x1 - x0) * res), int((y1 - y0) * res)
    t = src('metal_rusty-painted', mean=0.46, sat=0.22, tint=(1.0, 0.97, 0.92), contrast=0.55)
    tt = tile(t, w, h, seed=81, scale=1.0 * res / t.shape[1])
    cols = 0.06
    X = (np.arange(w) + 0.5) / res
    ph = (X / cols) % 1.0
    shade = 0.45 + 0.75 * np.sin(ph * math.pi) ** 0.7                        # rounded columns
    Yv = (np.arange(h) + 0.5) / res
    ends = 1 - 0.45 * (np.exp(-Yv / 0.03) + np.exp(-(Yv[-1] - Yv) / 0.03))  # rounded tops and bottoms
    alpha = np.ones((h, w), np.float32)
    gap = (np.abs(ph - 0.0) < 0.10) | (np.abs(ph - 1.0) < 0.10)
    alpha[:, gap] = 0.0
    alpha[int(h * 0.08):int(h * 0.14)] = 1
    alpha[-int(h * 0.12):-int(h * 0.06)] = 1
    alpha = blur(alpha, 0.8)
    tt *= (shade[None, :] * ends[:, None])[..., None]
    sc.draw_quad([(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)], np.clip(tt, 0, 1), alpha=alpha,
                 spec=0.25, gloss=18, name='radiator')
    # its feet
    for xf in (x0 + 0.04, x1 - 0.06):
        sc.draw_quad([(xf, y0, z0), (xf + 0.02, y0, z0), (xf + 0.02, 0, z0), (xf, 0, z0)], tt[:20, :14] * 0.6,
                     name='rad_foot')


def draw_table(sc):
    """the bedside table: lacquered cherry, a drawer with a brass knob, two books at the back."""
    x0, x1, z0, z1 = 1.17, 1.62, 1.92, 2.32
    top_y = 0.604
    top = lambda wp, hp, face: wood_grain('wood_worn-table', wp, hp, 900, 0.55, along='x', seed=91, mean=0.30,
                                          sat=0.55, contrast=1.15)

    def body(wp, hp, face):
        t = wood_grain('wood_lacquered-cherry', wp, hp, 700, 1.0, along='y', seed=92, mean=0.26, contrast=1.3)
        if face == 'front':
            # a drawer just under the top: gap, raised front, brass knob
            yy, xx = np.mgrid[0:hp, 0:wp].astype(np.float32)
            dy0, dy1 = 0.035 * 700, 0.165 * 700
            dr = rect_mask(wp, hp, 0.03 * 700, dy0, wp - 0.03 * 700, dy1, soft=1.5)
            ring = rect_mask(wp, hp, 0.025 * 700, dy0 - 3, wp - 0.025 * 700, dy1 + 3, soft=1) - dr
            t *= (1 - 0.7 * np.clip(ring, 0, 1))[..., None]
            kx, ky, kr = wp * 0.5, (dy0 + dy1) / 2, 0.016 * 700
            d = np.sqrt((xx - kx) ** 2 + (yy - ky) ** 2)
            km = np.clip(kr - d + 0.5, 0, 1)
            brass = src('metal_brass-brushed', mean=0.45, sat=0.55, tint=(1.0, 0.9, 0.72))
            kc = tile(brass, wp, hp, seed=3, scale=0.3) * (0.6 + 0.8 * np.clip(1 - d / kr, 0, 1))[..., None]
            t = t * (1 - km[..., None]) + kc * km[..., None]
            t *= (1 - 0.35 * np.exp(-(((xx - kx - 3) / (kr * 1.6)) ** 2 + ((yy - ky - 4) / (kr * 1.6)) ** 2)) * (1 - km))[..., None]
        return t
    sc.box((x0 - 0.01, top_y - 0.035, z0 - 0.015), (x1 + 0.01, top_y, z1), top, res=900, name='table_top',
           spec=0.45, gloss=35, spec_tint=(1.0, 0.92, 0.85))
    sc.box((x0 + 0.01, 0.0, z0 + 0.01), (x1 - 0.01, top_y - 0.035, z1 - 0.01), body, res=700, name='table_body',
           spec=0.3, gloss=30)
    # two old books lying at the back-left of the top (well clear of the evidence spot)
    cloth = [src('fabric_bookcloth-red', mean=0.20, sat=0.5), src('fabric_quilt-green-wholecloth', mean=0.20, sat=0.4)]
    y = top_y
    for i, (th, inset) in enumerate(((0.032, 0.0), (0.026, 0.012))):
        bx0, bx1 = 1.185 + inset * 0.5, 1.285 - inset * 0.3
        bz0, bz1 = 2.14 + inset * 0.5, 2.30 - inset
        cl = cloth[i]

        def faces(wp, hp, face, cl=cl, i=i):
            if face == 'top':
                t = tile(cl, wp, hp, seed=i, scale=0.3)
                return t * (0.85 + 0.15 * rect_mask(wp, hp, 0, 0, wp, hp, soft=3))[..., None]
            if face == 'front':
                t = np.zeros((hp, wp, 3), np.float32) + np.array([0.62, 0.57, 0.47])
                t *= (0.85 + 0.15 * np.sin(np.arange(hp) * 2.1)[:, None])[..., None]
                b = max(1, int(hp * 0.15))
                t[:b] = tile(cl, wp, b, seed=i + 3, scale=0.3)
                t[-b:] = tile(cl, wp, b, seed=i + 4, scale=0.3)
                return t
            return tile(cl, wp, hp, seed=i + 7, scale=0.3) * 1.1
        sc.box((bx0, y, bz0), (bx1, y + th, bz1), faces, res=1400, occluder=False, name=f'book{i}')
        y += th


def quilt_layer(sc, mode, light_dir):
    """the quilt over your feet: a lavender-grey wholecloth quilt (the Met's, re-dyed by the night) on a soft
    height field (your feet, folds, the roll over the end of the bed), lit by the room's lights."""
    Yq = 0.70
    z_far, z_near = 1.12, 0.55
    x0, x1 = -1.75, 1.75
    res = 650
    w, h = int((x1 - x0) * res), int((z_far - z_near) * res)
    q = src('fabric_quilt-green-wholecloth', mean=0.40, sat=0.30, tint=(0.98, 0.80, 0.96), contrast=1.9)
    qt = tile(q, w, h, seed=101, tone_var=0.06, scale=1.5 * res / q.shape[1])
    # texture rows: 0 = far edge (z_far); columns: x
    X = x0 + (np.arange(w, dtype=np.float32) + 0.5) / res
    Z = z_far - (np.arange(h, dtype=np.float32) + 0.5) / res
    Xg, Zg = np.meshgrid(X, Z)
    # the quilt's far edge on screen must follow the stand-in's curve (812 left, 776 middle, 770 right)
    u = CX + F * Xg / Zg
    v = CY + F * (EYE - Yq) / Zg

    def curve(uu):
        # quadratic beziers of paintBedroom: (0,812)-(420,748)-(800,776) and (800,776)-(1180,806)-(1600,770)
        uu = np.clip(uu, 0, 1600)
        t1 = np.clip(uu / 800, 0, 1)
        c1 = (1 - t1) ** 2 * 812 + 2 * (1 - t1) * t1 * 748 + t1 ** 2 * 776
        t2 = np.clip((uu - 800) / 800, 0, 1)
        c2 = (1 - t2) ** 2 * 776 + 2 * (1 - t2) * t2 * 806 + t2 ** 2 * 770
        return np.where(uu < 800, c1, c2)
    edge_px = v - curve(u)                                   # > 0 below the curve (on the quilt)
    alpha = np.clip(edge_px / 2.0 + 0.5, 0, 1)
    # height field: two feet under the quilt, long soft folds, the roll over the bed's end
    Hm = np.zeros_like(Xg)
    for fx in (-0.20, 0.22):
        Hm += 0.10 * np.exp(-(((Xg - fx) / 0.16) ** 2 + ((Zg - 1.0) / 0.22) ** 2))
    rng = np.random.default_rng(7)
    # soft, irregular folds: smooth noise ridges, a few long creases running from the feet toward us
    n1 = value_noise(w, h, 0.22 * res, 11, octaves=3)
    Hm += 0.022 * (n1 - 0.5)
    for k in range(4):
        x_c = rng.uniform(-1.2, 1.2)
        ang = rng.uniform(-0.35, 0.35)
        dist = (Xg - x_c) * math.cos(ang) - (Zg - 1.0) * math.sin(ang)
        Hm += 0.010 * rng.uniform(0.5, 1.0) * np.exp(-(dist / rng.uniform(0.04, 0.09)) ** 2) * smoothstep(0.55, 1.0, Zg)
    roll = smoothstep(0.0, 26.0, edge_px)                    # near the edge the cloth curves over and down
    Hm -= 0.05 * (1 - roll)
    lx, ly, lz = light_dir
    shade, ao = relief(Hm, res, light=(lx, ly, lz), strength=1.4, cavity=0.3)
    qt = qt * shade[..., None] * (0.55 + 0.45 * roll)[..., None]
    # quilting stitches already in the photo; add a darker binding along the edge
    bind = np.exp(-((edge_px - 4.0) / 3.0) ** 2)
    qt *= (1 - 0.25 * bind)[..., None]
    sc.draw_quad([(x0, Yq, z_far), (x1, Yq, z_far), (x1, Yq, z_near), (x0, Yq, z_near)], np.clip(qt, 0, 1),
                 alpha=alpha, ao=ao, name='quilt', direct_ao=0.5)


def god_rays(sc, direction, color, strength, open_frac):
    """dusty light shafts from the window along the light direction (screen space, additive)."""
    cam = sc.cam
    d = np.asarray(direction, np.float64)
    d = d / np.linalg.norm(d)
    acc = np.zeros((cam.H, cam.W), np.float32)
    img = Image.new('L', (cam.W, cam.H), 0)
    dr = ImageDraw.Draw(img)
    ys = np.arange(WY1 - 0.02, WY0 + 0.02, -SLAT_PITCH * 0.25)
    for Y in ys:
        g = float(slat_gap(np.array([Y]), open_frac)[0])
        if g < 0.3:
            continue
        P0 = np.array([[WX0 + 0.03, Y, ZB], [WX1 - 0.03, Y, ZB]])
        t = min((Y - 0.0) / -d[1], (ZB - 0.9) / -d[2])
        P1 = P0 + d[None, :] * t
        S = cam.project_ss(np.concatenate([P0, P1[::-1]]))
        dr.polygon([tuple(p) for p in S], fill=int(40 * g))
    acc = f32(img)
    acc = blur(acc, 6 * cam.ss)
    # fade along the shaft: strongest near the window
    yy, xx = np.mgrid[0:cam.H, 0:cam.W].astype(np.float32)
    wc = cam.project_ss(np.array([(WX0 + WX1) / 2, (WY0 + WY1) / 2, ZB]))
    dist = np.sqrt((xx - wc[0]) ** 2 + (yy - wc[1]) ** 2) / cam.ss
    fade = np.exp(-dist / 700.0)
    sc.canvas += (acc * fade * strength)[..., None] * np.asarray(color, np.float32)[None, None, :]


EV_PATCH = {2: (96, 110, 470, 690), 4: (200, 650, 420, 760)}   # the crops saved as bedroom_ev2/4.jpg (x0, y0, x1, y1)


def render(mode='night', seed=5, evidence=None):
    cam = Camera(W, H, F, CX, CY, EYE, ss=SS)
    rng_state = so.RNG.bit_generator.state           # the office's shared RNG (dado / paper offsets):
    so.RNG.bit_generator.state = np.random.default_rng(5200).bit_generator.state   # same start in any build order
    sc = Scene(cam, ambient_day if mode == 'morning' else ambient_night)
    direction, open_frac = make_lights(sc, mode)
    sc.add_occluder('table', (1.17, 0.0, 1.92), (1.62, 0.604, 2.32))
    sc.add_occluder('radiator', (X_at(1068, ZB), 0.12, ZB - 0.13), (X_at(1332, ZB), 0.60, ZB - 0.05))
    draw_sky(sc, mode)
    draw_window(sc, mode, open_frac)
    ang = None
    if evidence == 2:
        back_wall(mode)                                  # (fills DOOR: the door's own texture)
        ang = closet_ajar(sc)
    draw_walls(sc, mode, ajar=evidence == 2)
    draw_floor(sc, mode)
    if ang is not None:
        draw_door_leaf(sc, ang)
    if evidence == 4:
        collar_scrap(sc)
    draw_radiator(sc)
    draw_table(sc)
    # the night-light itself (a little glowing shell)
    if mode != 'morning':
        nx = X_at(905, ZB)
        r = 60
        yy, xx = np.mgrid[0:r, 0:r].astype(np.float32)
        m = np.clip((1 - np.sqrt(((xx - r / 2) / (r / 2)) ** 2 + ((yy - r * 0.55) / (r * 0.45)) ** 2)) * 8, 0, 1)
        ribs = 0.8 + 0.2 * np.cos(np.arctan2(xx - r / 2, r - yy) * 9) ** 2
        em = np.stack([m * ribs, m * ribs * 0.80, m * ribs * 0.55], -1)
        sc.draw_quad([(nx - 0.022, 0.335, ZB - 0.012), (nx + 0.022, 0.335, ZB - 0.012), (nx + 0.022, 0.29, ZB - 0.012),
                      (nx - 0.022, 0.29, ZB - 0.012)], np.zeros_like(em), alpha=m, emissive=em, emit=2.6,
                     lit=False, name='nightlight')
        sc.glow(905, 645, 40, AMBER, 0.06, 1.8)
    # the quilt (lit from the window side), then a touch of depth of field on it
    lt = (0.45, 0.80, 0.30) if mode == 'morning' else (0.40, 0.85, 0.25)
    before = sc.canvas.copy()
    quilt_layer(sc, mode, lt)
    qmask = np.clip(np.abs(sc.canvas - before).sum(-1) * 50, 0, 1)
    qmask = blur(qmask, 3 * SS)
    sc.canvas = sc.canvas * (1 - qmask[..., None] * 0.85) + blur(sc.canvas, 1.3 * SS) * (qmask[..., None] * 0.85)
    if mode == 'morning':
        god_rays(sc, direction, SUN, 0.016, open_frac)
    else:
        god_rays(sc, direction, MOON, 0.0060, open_frac)
    so.RNG.bit_generator.state = rng_state
    lin = sc.downsample()
    y = finish(lin, 'bedroom_day' if mode == 'morning' else 'bedroom_night', seed=seed, return_array=True)
    return y, lin


def build(out_path):
    out_dir = Path(out_path).parent
    y, _ = render('night', seed=5)
    save_jpeg(pil(y), out_dir / OUT, quality=84, max_kb=880)
    y, _ = render('morning', seed=6)
    save_jpeg(pil(y), out_dir / OUT_MORNING, quality=84, max_kb=880)
    # the mornings with something that followed you out of the dream: just the piece of the picture that differs
    # (the game lays it over bedroom_morning.jpg at EV_PATCH's corner)
    for n in (2, 4):
        ye, _ = render('morning', seed=6, evidence=n)
        x0, y0, x1, y1 = EV_PATCH[n]
        save_jpeg(pil(ye[y0:y1, x0:x1]), out_dir / f'bedroom_ev{n}.jpg', quality=88, max_kb=200)
        d = np.abs(ye - y).max(-1) > 0.02
        ys, xs = np.nonzero(d)
        if len(ys) and (xs.min() < x0 or ys.min() < y0 or xs.max() >= x1 or ys.max() >= y1):
            print(f'  WARNING: bedroom_ev{n}: the change reaches outside EV_PATCH', (xs.min(), ys.min(), xs.max(), ys.max()))
    return out_path


if __name__ == '__main__':
    import time
    t = time.time()
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/bedroom')
    modes = sys.argv[2].split(',') if len(sys.argv) > 2 else ['night', 'morning']
    outdir.mkdir(parents=True, exist_ok=True)
    for m in modes:
        y, lin = render(m)
        pil(y).save(outdir / f'bedroom_{m}.png')
        print(m, f'mean {mean_lum255(y):.1f}', f'{time.time() - t:.1f}s')
