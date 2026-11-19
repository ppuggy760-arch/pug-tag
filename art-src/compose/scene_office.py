"""THE DESK ROOM (office) - the hero scene, 2400 x 900.

A photographic composite of a Victorian study at night, built as a small 3-D
set so every surface shares one camera and one set of lights:

    camera    f = 1200 px (90 deg across the 2400 px panorama), horizon y = 430,
              eye 1.2 m above the floor (seated)
    NEAR WALL z = 4.0 m  (300 px per metre): both doorways, the window,
              the pinned-drawing spot and the scratched WAKE UP
    ALCOVE    a recess behind the desk, back wall z = 5.106 m: its floor line
              is y = 712 and its ceiling line y = 58 (the old stand-in's
              skirting / ceiling band), side walls at x = 900..965 and 1505..1590
    DESK      top at 0.76 m, back edge y = 620 (x 863..1558), front edge y = 670

The geometry the game's live overlays rely on (door boxes, window box, clock
spot, lamp spot, monitor, pinned drawing) is listed in GEOMETRY below and
drawn by tools/office_overlay.py style checks (see build(..., overlay=...)).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (Camera, Scene, PointLight, ApertureLight, blur, edge_ao, f32, flatten_light, font,
                    hexcol, load, lum, make_seamless, match_albedo, paste_over, pil, rect_mask,
                    resize_f, save_jpeg, smoothstep, srgb2lin, text_mask, tile, value_noise, BICUBIC,
                    LANCZOS)
from grade import finish

OUT = 'office.jpg'
W, H, SS = 2400, 900, 2
F, CX, CY, EYE = 1200.0, 1200.0, 430.0, 1.2
ZN = 4.0                                   # near wall
ZB = F * EYE / (712 - CY)                  # alcove back wall (floor line at y = 712)
CEIL = EYE + (CY - 58) * ZB / F            # ceiling height (ceiling line y = 58 on the back wall)
XAL, XAR = (900 - CX) * ZN / F, (1590 - CX) * ZN / F   # alcove opening (near-wall x 900 .. 1590)
DESK_Y = 0.76
DESK_ZB = F * (EYE - DESK_Y) / (620 - CY)  # back edge of the desk top at y = 620
DESK_ZF = F * (EYE - DESK_Y) / (670 - CY)  # front edge at y = 670
RAIL_Y, DADO_Y, PICT_Y = 0.14, 0.585, 2.35  # skirting top, chair rail top, picture rail

# what the game needs to line up with (output pixels)
GEOMETRY = dict(
    door_left=(72, 160.2, 360, 630), door_right=(1968, 160.2, 360, 630),
    window=(560, 160, 250, 270), lamp=(950, 510), lamp_shade=(905, 445, 100, 55),
    monitor=(1060, 438, 280, 190), clock=(1449.6, 585.9, 26.1), clock_shadow=(1452, 623),
    desk=(860, 620, 700), drawing_clear=(1700, 190, 190, 230), wake_up=(1610, 600),
)

# light levels (linear irradiance units)
AMBIENT = (0.25, 0.28, 0.56)     # violet night fill
LAMP_POWER, WINDOW_POWER, MOON_POWER, CRT_POWER, FILL_POWER, WASH_POWER = 9.0, 2.0, 2.4, 0.35, 2.2, 0.55

RNG = np.random.default_rng(1871)
CACHE = {}


def X_at(u, Z):
    return (u - CX) * Z / F


def Y_at(v, Z):
    return EYE - (v - CY) * Z / F


# ==========================================================================
# materials (all colour-matched once, cached)
# ==========================================================================
def mat(name, key=None, **kw):
    k = (name, key, tuple(sorted(kw.items())))
    if k not in CACHE:
        CACHE[k] = match_albedo(f32(load(name)), **kw)
    return CACHE[k]


def damask_tile(res):
    """one seamless repeat of the dark green damask (0.53 m wide roll) at `res` px/m."""
    k = ('damask', res)
    if k in CACHE:
        return CACHE[k]
    a = f32(load('wallpaper_dark-green-damask'))
    a = flatten_light(a, 120)
    # the sheet is one roll width (it already matches side to side); its vertical repeat is 1390 px
    # (found by autocorrelation); start below the torn top edge and crossfade one repeat
    t = make_seamless(a[24:24 + 1390 + 90, :], px=None, py=1390, blend=0.06)
    wpx = int(round(0.53 * res))
    hpx = int(round(0.53 * res * t.shape[0] / t.shape[1]))
    t = resize_f(t, wpx, hpx, LANCZOS)
    # into the palette: a dark sage-teal damask, the pattern still readable
    t = match_albedo(t, sat=0.62, tint=(0.92, 1.0, 1.02), mean=0.34, contrast=1.25)
    CACHE[k] = t
    return t


def wood(name, w, h, res, real_m, rot=False, seed=0, mean=0.30, sat=0.50, tone=0.10, tint=(0.84, 0.90, 0.80),
         contrast=None):
    """a wood texture tiled to w x h px at res px/m (texture covers real_m metres)."""
    t = mat(name, mean=mean, sat=sat, tint=tint, contrast=contrast)
    if rot:
        t = np.ascontiguousarray(np.rot90(t))
    s = real_m * res / t.shape[1]
    return tile(t, w, h, seed=seed, tone_var=tone, scale=s)


def profile_shade(n, profile, light=0.9):
    """shading (n,) across a moulding from a height profile (n,): lit from the 'start' side."""
    p = np.asarray(profile, np.float32)
    if len(p) != n:
        p = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(p)), p).astype(np.float32)
    g = np.gradient(p)
    g = g / (np.abs(g).max() + 1e-6)
    cav = p - blur(p[None, :], max(1.0, n / 14))[0]
    return np.clip(1 - light * 0.35 * g + 0.5 * cav, 0.45, 1.4)


# ==========================================================================
# a 2-D board in the plane of a frontal wall (X right, Y up; res px per metre)
# ==========================================================================
class Board:
    def __init__(self, x0, x1, y0, y1, res):
        self.x0, self.x1, self.y0, self.y1, self.res = x0, x1, y0, y1, res
        self.w, self.h = int(round((x1 - x0) * res)), int(round((y1 - y0) * res))
        self.alb = np.zeros((self.h, self.w, 3), np.float32)
        self.alpha = np.ones((self.h, self.w), np.float32)
        self.ao = np.ones((self.h, self.w), np.float32)
        self.emis = None

    def px(self, X):
        return (X - self.x0) * self.res

    def py(self, Y):
        return (self.y1 - Y) * self.res

    def sl(self, X0, X1, Y0, Y1):
        a, b = int(round(self.px(X0))), int(round(self.px(X1)))
        c, d = int(round(self.py(Y1))), int(round(self.py(Y0)))
        return slice(max(0, c), min(self.h, d)), slice(max(0, a), min(self.w, b))

    def put(self, X0, X1, Y0, Y1, arr, alpha=None):
        ys, xs = self.sl(X0, X1, Y0, Y1)
        hh, ww = ys.stop - ys.start, xs.stop - xs.start
        if hh <= 0 or ww <= 0:
            return
        a = arr[:hh, :ww] if arr.shape[0] >= hh and arr.shape[1] >= ww else resize_f(arr, ww, hh)
        if alpha is None:
            self.alb[ys, xs] = a
        else:
            m = alpha[:hh, :ww] if alpha.shape[0] >= hh else resize_f(alpha, ww, hh)
            self.alb[ys, xs] = a * m[..., None] + self.alb[ys, xs] * (1 - m[..., None])

    def shadow(self, X0, X1, Y0, Y1, strength, soft_m, dx=0.0, dy=-0.01):
        """soft drop shadow / AO of a frontal object onto the board (offset dx, dy metres)."""
        m = np.zeros((self.h, self.w), np.float32)
        ys, xs = self.sl(X0 + dx, X1 + dx, Y0 + dy, Y1 + dy)
        m[ys, xs] = 1
        m = blur(m, soft_m * self.res)
        self.ao *= 1 - strength * m


# ==========================================================================
# wall dressing
# ==========================================================================
def paper_wall(b: Board, Y0, Y1, seed, stains=True):
    """damask wallpaper between heights Y0..Y1, aged: seams, water stains, dirt, fading."""
    res = b.res
    t = damask_tile(res)
    ys, xs = b.sl(b.x0, b.x1, Y0, Y1)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    # roll seams line up with the pattern repeat
    ox = int((b.x0 * res) % t.shape[1])
    paper = tile(t, ww, hh, seed=seed, offset=(ox, int(RNG.integers(0, t.shape[0]))), tone_var=0.07,
                 tone_cell=res * 0.9)
    X = (np.arange(ww) + 0.5) / res + b.x0
    seam = np.abs(((X + 0.0) / 0.53) % 1.0 - 0.0)
    seam = np.minimum(seam, 1 - seam) * 0.53 * res          # px distance to the nearest seam
    sh = 1 - 0.10 * np.exp(-(seam / 1.2) ** 2)               # the dark butt-joint line
    paper *= sh[None, :, None]
    if stains:
        # water stains (real photo), as a multiply on the paper
        st = f32(load('plaster_damp-stained'))
        sL = lum(st)
        sL = sL / sL.mean()
        sm = tile(sL[..., None].repeat(3, -1), ww, hh, seed=seed + 5, scale=4.0 * res / st.shape[1])[..., 0]
        paper *= np.clip(0.55 + 0.45 * sm, 0.5, 1.15)[..., None] * np.array([1.0, 0.98, 0.95], np.float32)
        # tide marks: a few slow blooms of darker damp with a crisp-ish edge
        n = value_noise(ww, hh, res * 0.7, seed + 9, octaves=3)
        tide = smoothstep(0.66, 0.72, n) * 0.18 + smoothstep(0.72, 0.9, n) * 0.12
        paper *= (1 - tide)[..., None] * 1.0
        # grime: darker toward the top (lamp smoke) and toward the dado (hands, chairs)
        Yv = Y1 - (np.arange(hh) + 0.5) / res
        g = 1 - 0.22 * smoothstep(Y1 - 0.6, Y1, Yv) - 0.12 * smoothstep(Y0 + 0.35, Y0, Yv)
        paper *= g[:, None, None]
        # streaks running down from the cornice
        sx = value_noise(ww, 1, res * 0.05, seed + 11)[0]
        streak = smoothstep(0.78, 0.95, sx)[None, :] * smoothstep(Y1 - 1.4, Y1, Yv)[:, None]
        paper *= (1 - 0.22 * streak)[..., None]
    b.alb[ys, xs] = np.clip(paper, 0, 1)


def frieze(b: Board, Y0, Y1, seed):
    ys, xs = b.sl(b.x0, b.x1, Y0, Y1)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    p = mat('plaster_aged-worn', mean=0.30, sat=0.45, tint=(0.95, 0.93, 1.0))
    t = tile(p, ww, hh, seed=seed, tone_var=0.12, scale=1.8 * b.res / p.shape[1])
    Yv = Y1 - (np.arange(hh) + 0.5) / b.res
    t *= (1 - 0.35 * smoothstep(Y1 - 0.3, Y1, Yv))[:, None, None]   # sooty under the cornice
    b.alb[ys, xs] = t


def hmoulding(b: Board, Y0, Y1, profile, seed, wood_name='wood_dark-varnished', mean=0.30, shadow=0.35):
    """a horizontal wooden moulding (picture rail, chair rail, skirting cap) across the board."""
    ys, xs = b.sl(b.x0, b.x1, Y0, Y1)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    if hh <= 0:
        return
    t = wood(wood_name, ww, hh, b.res, 2.0, seed=seed, mean=mean)
    pr = np.interp(np.linspace(0, 1, hh), np.linspace(0, 1, len(profile)), profile)
    t *= profile_shade(hh, pr)[:, None, None]
    b.alb[ys, xs] = t
    b.shadow(b.x0, b.x1, Y0, Y1, shadow, 0.012, dy=-0.012)


def dado(b: Board, seed):
    """panelled wainscot from the floor to the chair rail."""
    res = b.res
    # one row of raised panels from the real wainscot texture (5 rows in 2.1 m)
    pan = mat('panel_wainscot-raised', mean=0.27, sat=0.50, tint=(0.84, 0.90, 0.80))
    ao = f32(load('panel_wainscot-raised_ao'))[..., 0]
    ao = resize_f(ao, pan.shape[1], pan.shape[0])
    rows = pan.shape[0] / 5
    r0 = int(rows * 1 - rows * 0.08)
    r1 = int(rows * 2 + rows * 0.02)
    row = pan[r0:r1] * (0.55 + 0.45 * ao[r0:r1])[..., None]
    Ypan0, Ypan1 = RAIL_Y + 0.01, DADO_Y - 0.035
    ys, xs = b.sl(b.x0, b.x1, Ypan0, Ypan1)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    s = hh / row.shape[0]
    rr = resize_f(row, max(2, int(row.shape[1] * s)), hh, LANCZOS)
    b.alb[ys, xs] = tile(rr, ww, hh, seed=seed, offset=(int(RNG.integers(0, rr.shape[1])), 0), tone_var=0.08)
    # chair rail and skirting
    hmoulding(b, DADO_Y - 0.035, DADO_Y, [0, .6, 1, .9, .5, .7, .3, 0], seed + 1, mean=0.28, shadow=0.45)
    hmoulding(b, 0.0, RAIL_Y, [.9, 1, .7, .62, .6, .6, .6, .6, .6, .6, .58, .55], seed + 2, mean=0.22, shadow=0.0)
    b.ao *= 1 - 0.35 * np.exp(-np.clip(b.py(0) - np.arange(b.h), 0, None) / (0.05 * res))[:, None]


# ---- Victorian door / window trim: fluted casings, bullseye corner blocks, plinths
def rosette(size, seed):
    n = size
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    r = np.sqrt((xx - n / 2 + .5) ** 2 + (yy - n / 2 + .5) ** 2) / (n / 2)
    t = wood('wood_dark-varnished', n, n, n / 0.14, 2.0, seed=seed, mean=0.30)
    rings = 0.5 + 0.5 * np.cos(r * math.pi * 5.0)
    shade = 1 - 0.45 * rings * (r < 0.86) - 0.35 * (np.abs(r - 0.9) < 0.05) + 0.25 * (r < 0.18)
    # light from above: upper half of each ring a touch brighter
    shade *= 1 + 0.12 * ((yy - n / 2) / (n / 2)) * -1 * (r < 0.9)
    edge = rect_mask(n, n, 0, 0, n, n, soft=n * 0.06)
    bevel = 1 - 0.25 * (1 - edge)
    return np.clip(t * (shade * bevel)[..., None], 0, 1)


def eye_roundel(size, seed):
    """the old sigil, now a small carved wooden roundel: a ring around an almond eye."""
    n = size
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    cx = cy = n / 2 - 0.5
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (n / 2)
    t = wood('wood_dark-varnished', n, n, n / 0.12, 2.0, seed=seed, mean=0.34)
    ex, ey = (xx - cx) / (n * 0.36), (yy - cy) / (n * 0.20)
    almond = np.clip((1 - (np.abs(ex) ** 1.3 + np.abs(ey) ** 1.0 * (1 + np.abs(ex)))) * 6, 0, 1)
    pupil = np.clip((n * 0.075 - np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)) / 1.2, 0, 1)
    ring = np.exp(-((r - 0.82) / 0.07) ** 2)
    h = 0.6 * ring + 0.55 * almond - 0.9 * pupil + 0.25 * (r < 0.95)
    g = np.gradient(blur(h, 1.0), axis=0)
    shade = 1 - 12.0 * g / max(1, n / 20) * 0.35 + 0.25 * h - 0.35 * pupil
    shade *= np.where(r < 0.97, 1.0, 0.0) + np.where(r >= 0.97, 1.0, 0.0)
    m = np.clip((1 - r) * n * 0.5, 0, 1)
    return np.clip(t * shade[..., None], 0, 1), m


def fluted(w, h, seed, vertical=True, flutes=3):
    t = wood('wood_dark-varnished', w if vertical else w, h, (w if vertical else h) / 0.12, 2.0,
             rot=vertical, seed=seed, mean=0.38)
    n = w if vertical else h
    u = np.linspace(0, 1, n)
    prof = np.ones(n, np.float32)
    for k in range(flutes):
        c = (k + 1) / (flutes + 1)
        prof -= 0.8 * np.exp(-((u - c) / (0.22 / flutes)) ** 2)
    prof[:max(1, n // 14)] *= 0.6
    prof[-max(1, n // 14):] *= 0.6
    s = profile_shade(n, prof * 4)
    s *= 0.85 + 0.15 * prof
    return t * (s[None, :, None] if vertical else s[:, None, None])


def door_trim(b: Board, X0, X1, Y_top, seed, Z=ZN, plinth=True, cap=True):
    """casing around an opening X0..X1 (world, the opening edges), from the floor to Y_top."""
    res = b.res
    cw = 0.125                                  # casing width
    # side casings
    for side, (a, c) in enumerate(((X0 - cw, X0), (X1, X1 + cw))):
        ys, xs = b.sl(a, c, 0.0, Y_top + cw)
        hh, ww = ys.stop - ys.start, xs.stop - xs.start
        b.alb[ys, xs] = fluted(ww, hh, seed + side)
        b.alpha[ys, xs] = 1
        b.shadow(a, c, 0, Y_top + cw, 0.45, 0.018, dx=0.0, dy=-0.004)
    # head casing (horizontal flutes)
    ys, xs = b.sl(X0, X1, Y_top, Y_top + cw)
    b.alb[ys, xs] = fluted(xs.stop - xs.start, ys.stop - ys.start, seed + 3, vertical=False)
    b.shadow(X0 - cw, X1 + cw, Y_top, Y_top + cw, 0.45, 0.02, dy=-0.006)
    # bullseye corner blocks
    rs = int(round((cw + 0.012) * res))
    for xc in (X0 - cw / 2, X1 + cw / 2):
        b.put(xc - (cw + 0.012) / 2, xc + (cw + 0.012) / 2, Y_top - 0.006, Y_top + cw + 0.006,
              rosette(rs + 2, seed + int(abs(xc) * 10)))
    # the carved eye roundel in the middle of the head casing (what is left of the old sigil)
    rs2 = int(round(cw * 0.95 * res))
    er, em = eye_roundel(rs2, seed + 5)
    xc = (X0 + X1) / 2
    x0p, y0p = int(b.px(xc) - rs2 / 2), int(b.py(Y_top + cw / 2) - rs2 / 2)
    paste_over(b.alb, er, em, x0p, y0p)
    sh = np.zeros((b.h, b.w), np.float32)
    paste_over(sh, np.ones_like(em), em, x0p + int(0.004 * res), y0p + int(0.008 * res))
    b.ao *= 1 - 0.45 * blur(sh, 0.01 * res) * (1 - np.pad(em, ((max(0, y0p), max(0, b.h - y0p - rs2)), (max(0, x0p), max(0, b.w - x0p - rs2))))[:b.h, :b.w])
    # cornice cap over the head
    if cap:
        Yc = Y_top + cw + 0.006
        ys, xs = b.sl(X0 - cw - 0.02, X1 + cw + 0.02, Yc, Yc + 0.075)
        hh, ww = ys.stop - ys.start, xs.stop - xs.start
        t = wood('wood_dark-varnished', ww, hh, res, 2.0, seed=seed + 7, mean=0.30)
        pr = np.interp(np.linspace(0, 1, hh), np.linspace(0, 1, 9), [.9, 1, .8, .5, .7, .9, .6, .3, .2])
        b.alb[ys, xs] = t * profile_shade(hh, pr * 3)[:, None, None]
        b.shadow(X0 - cw - 0.02, X1 + cw + 0.02, Yc, Yc + 0.075, 0.55, 0.025, dy=-0.02)
    # plinth blocks
    if plinth:
        for a, c in ((X0 - cw - 0.008, X0 + 0.0), (X1 - 0.0, X1 + cw + 0.008)):
            ys, xs = b.sl(a, c, 0.0, 0.24)
            hh, ww = ys.stop - ys.start, xs.stop - xs.start
            t = wood('wood_dark-varnished', ww, hh, res, 2.0, seed=seed + 9, mean=0.26)
            e = rect_mask(ww, hh, 0, 0, ww, hh, soft=max(2, ww * 0.08))
            t *= (0.75 + 0.25 * e)[..., None]
            t[:max(2, hh // 18)] *= 1.25
            b.alb[ys, xs] = np.clip(t, 0, 1)


# ==========================================================================
# the scene
# ==========================================================================
def make_lights(sc: Scene):
    amber = hexcol('#ffb466') * np.array([1.0, 0.93, 0.80], np.float32)
    moon = hexcol('#cfc8ff')
    bulb = np.array([-0.541, 1.105, 2.65], np.float32)

    def shade_pattern(d):
        down = np.clip(-d[:, 1], -1, 1)
        up = np.clip(d[:, 1], -1, 1)
        th_d = np.degrees(np.arccos(down))
        th_u = np.degrees(np.arccos(up))
        p = 0.30 + 0.70 * (1 - smoothstep(54, 64, th_d)) + 0.45 * (1 - smoothstep(42, 52, th_u))
        return p.astype(np.float32)

    lamp = PointLight(bulb, amber, power=LAMP_POWER, soft=0.50, pattern=shade_pattern, wrap=0.1, shadow_px=2.5,
                      ignore=('lamp',), name='lamp')

    # the window: moonlight entering through the panes (a shaft that lands on the floor)
    wx0, wx1 = X_at(560, ZN), X_at(810, ZN)
    wy0, wy1 = 1.2, 2.1

    def aperture(Q):
        x, y = Q[:, 0], Q[:, 1]
        inside = (x > wx0 + 0.03) & (x < wx1 - 0.03) & (y > wy0 + 0.03) & (y < wy1 - 0.03)
        xm, ym = (wx0 + wx1) / 2, (wy0 + wy1) / 2
        bars = (np.abs(x - xm) < 0.018) | (np.abs(y - ym) < 0.016)
        return (inside & ~bars).astype(np.float32)

    moonbeam = ApertureLight((0.30, -0.88, -0.36), moon, power=MOON_POWER, plane_z=ZN + 0.1, aperture=aperture,
                             shadow_px=2.0, name='moon')
    # the window glass itself glows a little into the room (sky and moon)
    wc = np.array([(wx0 + wx1) / 2, 1.62, ZN - 0.22], np.float32)
    winglow = PointLight(wc, moon * np.array([0.9, 0.92, 1.0], np.float32), power=WINDOW_POWER, soft=0.55,
                         pattern=lambda d: np.clip(-d[:, 2], 0, 1) ** 1.2, wrap=0.3, shadow_px=4.0,
                         ignore=('lamp',), name='window')
    # the CRT: a dim green-cyan wash on whatever is in front of it
    crt = PointLight((0.0, 0.99, 2.38), hexcol('#6cf0c0'), power=CRT_POWER, soft=0.32,
                     pattern=lambda d: np.clip(-d[:, 2], 0, 1) ** 1.5, wrap=0.2, shadow_px=3.0,
                     ignore=('crt',), name='crt')
    # a soft cool fill from behind the viewer (a moonlit window at our back) so the far ends still read
    fill = PointLight((0.0, 2.3, -0.8), moon * np.array([0.85, 0.85, 1.0], np.float32), power=FILL_POWER, soft=1.5,
                      wrap=0.3, shadow_px=None, name='fill')
    # the lamp's glow on the alcove behind the desk (a motivated cheat: only lights surfaces facing the eye
    # from behind the desk, i.e. the alcove back wall and its side walls)
    wash = PointLight((-0.45, 1.25, 4.55), amber * np.array([1.0, 0.92, 0.85], np.float32), power=WASH_POWER, soft=0.55,
                      pattern=lambda d: np.clip(d[:, 2] + 0.35, 0, 1), wrap=0.1, shadow_px=None, name='wash')
    sc.lights += [lamp, moonbeam, winglow, crt, fill, wash]
    return dict(bulb=bulb, amber=amber, moon=moon)


def ambient_fn(P, N):
    """violet night ambient: a little more from above and from the window side."""
    base = np.array(AMBIENT, np.float32)
    up = 0.82 + 0.18 * np.clip(N[:, 1], -1, 1)
    side = 1.0 + 0.06 * np.clip(-(P[:, 0] + 1.5) / 3.0, -1, 1)
    k = (up * side)[:, None]
    return base[None, :] * k


def build_scene():
    cam = Camera(W, H, F, CX, CY, EYE, ss=SS)
    sc = Scene(cam, ambient_fn)
    L = make_lights(sc)
    # occluders (shadow casters) are registered before anything is drawn
    sc.add_occluder('desk_top', (-0.80, DESK_Y - 0.03, DESK_ZF - 0.02), (0.85, DESK_Y, DESK_ZB + 0.01))
    sc.add_occluder('crt', (-0.36, DESK_Y, 2.45), (0.43, 1.235, 2.78))
    sc.add_occluder('books', (-0.77, DESK_Y, 2.26), (-0.60, 0.87, 2.50))
    sc.add_occluder('ped_l', (-0.74, 0.0, 2.22), (-0.30, DESK_Y - 0.03, 2.75))
    sc.add_occluder('ped_r', (0.39, 0.0, 2.22), (0.79, DESK_Y - 0.03, 2.75))
    sc.add_occluder('lamp', (-0.65, DESK_Y, 2.54), (-0.43, 1.17, 2.76))

    draw_sky(sc)
    draw_window_box(sc)
    draw_alcove(sc)
    draw_floor(sc)
    draw_near_walls(sc)
    draw_desk(sc)
    draw_crt(sc)
    draw_lamp(sc, L)
    draw_desk_things(sc)
    draw_air(sc, L)
    return sc


# ---------------------------------------------------------------- sky + moon
def draw_sky(sc: Scene):
    """night sky behind the window (unlit, emissive): stars, a too-big moon, misty pines."""
    Z = ZN + 0.6
    u0, u1, v0, v1 = 540, 840, 140, 450
    X0, X1 = X_at(u0, Z), X_at(u1, Z)
    Y1, Y0 = Y_at(v0, Z), Y_at(v1, Z)
    s = 2
    w, h = (u1 - u0) * s, (v1 - v0) * s
    sky = f32(load('sky_ph-milky-way'))
    sky = sky[100:100 + 700, 1100:1100 + 700]
    sky = resize_f(sky, w, h, LANCZOS)
    Lsk = lum(sky)
    stars = np.clip((Lsk - 0.42) * 3.0, 0, 1) ** 1.2              # only the brighter stars
    neb = blur(Lsk, 12) * 0.10
    yy = np.linspace(0, 1, h)[:, None, None]
    grad = hexcol('#070b22', False) * (1 - yy) + hexcol('#1b1640', False) * yy
    img = grad + stars[..., None] * np.array([0.80, 0.80, 0.95]) * 0.8 + neb[..., None] * np.array([0.4, 0.4, 0.8])
    # the moon (NASA photo), far too big, with a lavender halo
    mc = ((724 - u0) * s, (258 - v0) * s)
    mr = 76 * s
    yy2, xx2 = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xx2 - mc[0]) ** 2 + (yy2 - mc[1]) ** 2)
    halo = np.exp(-((d - mr).clip(0) / (mr * 0.35))) * 0.45 + np.exp(-((d - mr).clip(0) / (mr * 1.4))) * 0.22
    img = img + halo[..., None] * hexcol('#cfc8ff', False)[None, None, :] * 0.55
    moon = f32(load('moon_nasa-full-moon-photo'))
    ml = lum(moon)
    yy3, xx3 = np.where(ml > 0.08)
    moon = moon[yy3.min():yy3.max(), xx3.min():xx3.max()]
    msz = 2 * mr
    moon = resize_f(moon, msz, msz, LANCZOS)
    moon = match_albedo(moon, sat=0.10, tint=(0.95, 0.93, 1.0))
    g = np.mgrid[0:msz, 0:msz].astype(np.float32)
    rr = np.sqrt((g[1] - msz / 2 + .5) ** 2 + (g[0] - msz / 2 + .5) ** 2)
    mm = np.clip((mr - 1.0 - rr) / 1.5, 0, 1)
    limb = 1 - 0.25 * (rr / mr) ** 4                             # a soft limb darkening
    moon = (0.22 + 0.85 * moon) * limb[..., None]
    paste_over(img, moon, mm, int(mc[0] - mr), int(mc[1] - mr))
    # thin cloud wisps drifting across the lower half of the moon
    cl = value_noise(w, h, 60, 77, octaves=4)
    band = np.exp(-((yy2 - (mc[1] + mr * 0.55)) / (mr * 0.45)) ** 2)
    wisp = smoothstep(0.5, 0.85, cl) * band * 0.8
    img = img * (1 - wisp[..., None] * 0.5) + wisp[..., None] * np.array([0.32, 0.30, 0.45]) * 0.35
    # misty pines along the bottom: the forest photo turned into night silhouettes
    pines = f32(load('fog_ph-misty-pines'))
    pines = pines[150:1350, 200:2000]
    pl = lum(pines)
    pl = resize_f(pl, w, int(w * pl.shape[0] / pl.shape[1]), LANCZOS)
    sil = np.clip((0.80 - pl) * 2.0, 0, 1)
    ph = pl.shape[0]
    top = int(h - ph * 0.55)
    reg = img[max(0, top):]
    s2 = sil[:reg.shape[0]]
    fade = np.clip(np.linspace(-0.2, 1.4, reg.shape[0]), 0, 1)[:, None]
    a = (s2 * fade)[..., None] * 0.95
    fog = hexcol('#2a2650', False)
    reg[:] = reg * (1 - a) + (fog * 0.30)[None, None, :] * a
    mist = np.clip(np.linspace(-0.3, 1.0, reg.shape[0]), 0, 1)[:, None, None] * 0.35
    reg[:] = reg * (1 - mist) + mist * fog[None, None, :] * 0.9
    sc.draw_quad([(X0, Y1, Z), (X1, Y1, Z), (X1, Y0, Z), (X0, Y0, Z)], np.clip(img, 0, 1), lit=False,
                 emit=1.0, name='sky')


def draw_window_box(sc: Scene):
    """reveal (the wall's thickness), sill and the sash with its cross bars."""
    x0, x1 = X_at(560, ZN), X_at(810, ZN)
    y0, y1 = 1.2, 2.1
    Zs = ZN + 0.11
    res = 700
    plaster = mat('plaster_aged-beige', mean=0.40, sat=0.45, tint=(0.95, 0.95, 1.0))
    # left reveal (faces +x) and head reveal (faces down)
    def ptex(w, h, seed):
        return tile(plaster, w, h, seed=seed, tone_var=0.1, scale=1.0 * res / plaster.shape[1])
    wl = int(0.11 * res); hl = int(0.9 * res)
    sc.draw_quad([(x0, y1, Zs), (x0, y1, ZN), (x0, y0, ZN), (x0, y0, Zs)], ptex(wl, hl, 3),
                 ao=edge_ao(0.11, 0.9, 100, {'left': (0.5, 0.03), 'top': (0.3, 0.05)}), name='reveal_l')
    sc.draw_quad([(x0, y1, Zs), (x1, y1, Zs), (x1, y1, ZN), (x0, y1, ZN)], ptex(int(0.83 * res), wl, 4),
                 ao=edge_ao(0.83, 0.11, 100, {'top': (0.5, 0.03)}), name='reveal_t')
    # sash: frame + cross bars (painted wood), the glass is the hole
    sw, sh = int((x1 - x0) * res), int((y1 - y0) * res)
    paint = mat('wood_painted-green', mean=0.24, sat=0.35, tint=(0.9, 0.92, 1.0))
    sash = tile(paint, sw, sh, seed=8, scale=1.5 * res / paint.shape[1], tone_var=0.15)
    a = np.zeros((sh, sw), np.float32)
    fr = int(0.055 * res)
    a[:fr] = 1; a[-fr:] = 1; a[:, :fr] = 1; a[:, -fr:] = 1
    bw = int(0.032 * res)
    a[:, sw // 2 - bw // 2: sw // 2 + bw // 2] = 1
    a[sh // 2 - bw // 2: sh // 2 + bw // 2] = 1
    # meeting rail of a sash window is thicker
    a[sh // 2 - bw: sh // 2 + bw] = 1
    a = blur(a, 0.8)
    edge = blur(a, 3)
    sash *= (0.7 + 0.3 * edge)[..., None]
    sc.draw_quad([(x0, y1, Zs), (x1, y1, Zs), (x1, y0, Zs), (x0, y0, Zs)], sash, alpha=a, name='sash',
                 spec=0.15, gloss=20)
    # faint grime on the glass, catching the moon
    g = value_noise(sw, sh, 40, 31, octaves=3)
    grime = np.clip((g - 0.45) * 0.6, 0, 1) * (1 - a)
    gl = np.zeros((sh, sw, 3), np.float32) + hexcol('#cfc8ff', False)
    sc.draw_quad([(x0, y1, Zs - 0.005), (x1, y1, Zs - 0.005), (x1, y0, Zs - 0.005), (x0, y0, Zs - 0.005)], gl,
                 alpha=grime * 0.35, lit=False, emit=0.10, name='glass_grime')
    # sill (top face visible just below eye level)
    sill = wood('wood_painted-green', int(1.0 * res), int(0.16 * res), res, 1.5, seed=12, mean=0.25, sat=0.35)
    sc.draw_quad([(x0 - 0.08, 1.185, ZN + 0.11), (x1 + 0.08, 1.185, ZN + 0.11), (x1 + 0.08, 1.185, ZN - 0.05),
                  (x0 - 0.08, 1.185, ZN - 0.05)], sill, name='sill')


# ---------------------------------------------------------------- alcove
def draw_alcove(sc: Scene):
    res = 520
    # ceiling of the alcove
    cw, cd = XAR - XAL, ZB - ZN + 0.3
    ceil = mat('plaster_ceiling-textured', mean=0.27, sat=0.30, tint=(0.95, 0.95, 1.0))
    ct = tile(ceil, int(cw * res), int(cd * res), seed=2, tone_var=0.15, scale=2.0 * res / ceil.shape[1])
    sc.draw_quad([(XAL, CEIL, ZB), (XAR, CEIL, ZB), (XAR, CEIL, ZN - 0.3), (XAL, CEIL, ZN - 0.3)], ct,
                 ao=edge_ao(cw, cd, 60, {'top': (0.55, 0.12), 'left': (0.4, 0.1), 'right': (0.4, 0.1)}),
                 name='alcove_ceiling')
    # back wall
    b = Board(XAL - 0.02, XAR + 0.02, 0.0, CEIL, res)
    paper_wall(b, DADO_Y, PICT_Y, seed=21)
    frieze(b, PICT_Y, CEIL, seed=22)
    dado(b, seed=23)
    hmoulding(b, PICT_Y - 0.02, PICT_Y + 0.025, [.2, .7, 1, .8, .4, .6, .2], 24, mean=0.30)
    hmoulding(b, CEIL - 0.10, CEIL, [.1, .3, .6, .9, 1, .9, .7, .5, .3], 25, mean=0.33, shadow=0.0)
    hang_paintings(b)
    b.ao *= edge_ao(b.x1 - b.x0, b.y1 - b.y0, res, {'left': (0.45, 0.10), 'right': (0.45, 0.10),
                                                   'top': (0.35, 0.10), 'bottom': (0.4, 0.06)})[:b.h, :b.w]
    sc.draw_quad([(b.x0, b.y1, ZB), (b.x1, b.y1, ZB), (b.x1, b.y0, ZB), (b.x0, b.y0, ZB)], b.alb, ao=b.ao,
                 name='alcove_back')
    draw_frames(sc)
    # side walls of the alcove (returns)
    for X, sgn in ((XAL, 1), (XAR, -1)):
        d = ZB - ZN
        r = Board(0, d + 0.02, 0, CEIL, 600)
        paper_wall(r, DADO_Y, PICT_Y, seed=31 + sgn)
        frieze(r, PICT_Y, CEIL, seed=33 + sgn)
        dado(r, seed=35 + sgn)
        hmoulding(r, PICT_Y - 0.02, PICT_Y + 0.025, [.2, .7, 1, .8, .4, .6, .2], 37, mean=0.30)
        hmoulding(r, CEIL - 0.10, CEIL, [.1, .3, .6, .9, 1, .9, .7, .5, .3], 38, mean=0.33, shadow=0.0)
        # the far end (inner corner) is darker
        r.ao *= edge_ao(r.x1, r.y1, 600, {'right': (0.5, 0.12), 'top': (0.3, 0.1), 'bottom': (0.4, 0.06)})[:r.h, :r.w]
        if sgn == 1:  # left return: texture runs from the near edge (z=ZN) to the corner (z=ZB)
            corners = [(X, CEIL, ZN - 0.0), (X, CEIL, ZB + 0.02), (X, 0, ZB + 0.02), (X, 0, ZN)]
        else:
            corners = [(X, CEIL, ZB + 0.02), (X, CEIL, ZN), (X, 0, ZN), (X, 0, ZB + 0.02)]
            r.alb = r.alb[:, ::-1].copy(); r.ao = r.ao[:, ::-1].copy()
        sc.draw_quad(corners, r.alb, ao=r.ao, name=f'return_{sgn}')
    # alcove floor (mostly behind the desk)
    fl = floor_tex(XAR - XAL, ZB - ZN + 0.1, 500, seed=41)
    sc.draw_quad([(XAL, 0, ZB), (XAR, 0, ZB), (XAR, 0, ZN - 0.1), (XAL, 0, ZN - 0.1)], fl, spec=0.25, gloss=25,
                 ao=edge_ao(XAR - XAL, ZB - ZN + 0.1, 60, {'top': (0.5, 0.08)}), name='alcove_floor')


PAINT = {}


def gilt_frame(w, h, border, seed, inner_lip=0.18, res=900):
    """a carved gilt picture frame (w x h px, border px, res px/m): a real moulding profile (outer bead, a deep cove
    carved with acanthus leaves taken from a William Morris wallpaper's pattern, an ogee, a sight-edge bead), shaded
    from its height field with the light from the upper left, gold leaf worn through to the red bole in the hollows.
    Returns rgb, alpha (the hole)."""
    from scenekit import relief
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy)) / border   # 0 outside .. 1 inner
    dm = d * border / res                                                              # metres from the outer edge
    bm = border / res
    u = np.clip(d, 0, 1)
    # the profile (height in metres): bead, cove, ogee, sight bead, stepping down toward the picture
    prof = (0.022 * np.exp(-((u - 0.08) / 0.07) ** 2)                 # outer bead
            + 0.010 * (1 - np.exp(-((u - 0.40) / 0.16) ** 2))         # the cove (a hollow)
            + 0.016 * np.exp(-((u - 0.66) / 0.09) ** 2)               # ogee
            + 0.010 * np.exp(-((u - 0.90) / 0.04) ** 2)               # sight-edge bead
            + 0.008 * (1 - u))
    # carving in the cove: the acanthus pattern of a wallpaper used as a relief, running round the frame
    pat = lum(f32(load('wallpaper_morris-st-james-acanthus')))
    ph, pw = pat.shape
    along = np.where(np.minimum(yy, h - 1 - yy) < np.minimum(xx, w - 1 - xx), xx, yy)   # distance along the side
    across = np.clip((u - 0.22) / 0.36, 0, 1)
    py = ((along / (0.18 * res)) * pw * 0.25).astype(np.int64) % pw
    px_ = (across * ph * 0.20).astype(np.int64) % ph
    carve = pat[px_, py]
    carve = (carve - carve.mean()) / (carve.std() + 1e-6)
    cove = np.exp(-((u - 0.40) / 0.15) ** 2)
    Hm = prof + 0.0035 * blur(carve, 0.8) * cove
    shade, ao = relief(Hm, res, light=(-0.5, 0.6, 0.62), strength=1.4, cavity=0.7)
    # light from the top-left on the frame's four sides (the top and left mitres face it)
    tl = ((yy < xx * h / w) & (yy < (w - xx) * h / w)) | ((xx < yy) & (xx < h - yy))
    shade *= np.where(tl, 1.06, 0.90)
    brass = mat('metal_brass-brushed', mean=0.46, sat=0.6, tint=(1.0, 0.90, 0.68))
    gold = tile(brass, w, h, seed=seed, tone_var=0.2, scale=0.6)
    bole = np.array([0.30, 0.12, 0.08], np.float32)                     # the red clay under the gold leaf
    worn = smoothstep(0.62, 0.80, value_noise(w, h, border * 0.35, seed + 3, octaves=3)) * (0.5 + 0.5 * (1 - ao))
    t = gold * (1 - worn[..., None] * 0.7) + bole * worn[..., None] * 0.7
    t = t * (shade * ao)[..., None] * (0.82 + 0.25 * value_noise(w, h, border * 1.3, seed + 5, octaves=3))[..., None]
    t = t * (1 - 0.30 * (d < 0.03))[..., None]
    alpha = (d < 1.0).astype(np.float32)
    return np.clip(t, 0, 1), alpha


def gilt_frame_soft(w, h, border, seed, inner_lip=0.18):
    """(the old soft gilt frame, kept for reference)"""
    brass = mat('metal_brass-brushed', mean=0.42, sat=0.55, tint=(1.0, 0.92, 0.75))
    t = tile(brass, w, h, seed=seed, tone_var=0.25, scale=0.6)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy)) / border   # 0 outside .. 1 inner
    prof = (0.55 + 0.45 * np.sin(np.clip(d, 0, 1) * math.pi * 2.2) ** 2) * (1 - 0.45 * smoothstep(0.85, 1.0, d))
    prof *= 1 - 0.35 * (d < 0.08)
    # light from the top-left: the top/left inner bevels catch it
    tl = ((yy < xx * h / w) & (yy < (w - xx) * h / w)) | ((xx < yy) & (xx < h - yy))
    prof *= np.where(tl, 1.08, 0.88)
    # tarnish
    n = value_noise(w, h, border * 1.3, seed + 3, octaves=3)
    prof *= 0.75 + 0.35 * n
    rgb = t * prof[..., None]
    alpha = (d < 1.0).astype(np.float32)
    return np.clip(rgb, 0, 1), alpha


def painting(name, w, h, seed, craquelure=True):
    """an old oil painting fitted to w x h px: varnish yellowing, darkened, craquelure, dust."""
    p = f32(load(name))
    ph, pw = p.shape[:2]
    k = max(w / pw, h / ph)
    p = resize_f(p, int(pw * k + 1), int(ph * k + 1), LANCZOS)
    oy, ox = (p.shape[0] - h) // 2, (p.shape[1] - w) // 2
    p = p[oy:oy + h, ox:ox + w]
    p = match_albedo(p, sat=0.55, contrast=0.95, mean=0.30)
    p = p * np.array([1.0, 0.95, 0.82]) * 0.92 + 0.03            # old yellowed varnish
    if craquelure:
        n = value_noise(w, h, 7, seed, octaves=2)
        cr = np.abs(n - 0.5) < 0.012
        p *= (1 - 0.18 * blur(cr.astype(np.float32), 0.5))[..., None]
    # dust/bloom toward the bottom of the canvas
    p = p * (1 - 0.15 * np.linspace(0, 1, h)[:, None, None] ** 2)
    return np.clip(p, 0, 1)


def hang_paintings(b: Board):
    """the big moonlit 'Isle of the Dead' over the desk, an oval portrait to its right."""
    res = b.res
    # Isle of the Dead: canvas ~1.0 x 0.61 m, frame 0.11 m
    cx, top = X_at(1145, ZB), Y_at(196, ZB)
    fw, fh, br = 1.24, 0.85, 0.12
    X0, X1, Y1 = cx - fw / 2, cx + fw / 2, top
    Y0 = Y1 - fh
    PAINT['isle'] = (X0, X1, Y0, Y1, br)
    b.shadow(X0, X1, Y0, Y1, 0.55, 0.03, dx=0.012, dy=-0.03)
    # hanging wires up to the picture rail
    draw_wire(b, (X0 + 0.15, Y1 - 0.02), (cx - 0.05, PICT_Y - 0.02))
    draw_wire(b, (X1 - 0.15, Y1 - 0.02), (cx + 0.05, PICT_Y - 0.02))
    # oval portrait of a girl (1840) to the right
    cx2, cy2 = X_at(1398, ZB), Y_at(300, ZB)
    ow, oh = 0.40, 0.52
    PAINT['girl'] = (cx2 - ow / 2, cx2 + ow / 2, cy2 - oh / 2, cy2 + oh / 2)
    b.shadow(cx2 - ow / 2 + 0.03, cx2 + ow / 2 - 0.03, cy2 - oh / 2, cy2 + oh / 2 - 0.02, 0.5, 0.03, dx=0.01, dy=-0.025)
    draw_wire(b, (cx2, cy2 + oh / 2 - 0.03), (cx2, PICT_Y - 0.02))


def draw_wire(b: Board, p0, p1):
    n = 200
    for t in np.linspace(0, 1, n):
        X = p0[0] + (p1[0] - p0[0]) * t
        Y = p0[1] + (p1[1] - p0[1]) * t
        x, y = int(b.px(X)), int(b.py(Y))
        if 0 <= x < b.w - 1 and 0 <= y < b.h - 1:
            b.alb[y, x:x + 2] = b.alb[y, x:x + 2] * 0.3 + np.array([0.35, 0.30, 0.22]) * 0.7


def draw_frames(sc: Scene):
    res = 900                         # (crisper canvas and carving: the focal point of the room)
    Z = ZB - 0.035
    X0, X1, Y0, Y1, br = PAINT['isle']
    w, h = int((X1 - X0) * res), int((Y1 - Y0) * res)
    bp = int(br * res)
    rgb, hole = gilt_frame(w, h, bp, 51, res=res)
    canvas = painting('painting_bocklin-isle-of-the-dead', w - 2 * bp + 8, h - 2 * bp + 8, 52)
    full = rgb.copy()
    paste_over(full, canvas, np.ones(canvas.shape[:2], np.float32), bp - 4, bp - 4)
    # inner shadow of the frame lip on the canvas
    lip = 1 - 0.45 * blur(1 - rect_mask(w, h, bp, bp, w - bp, h - bp), 6)
    full = np.where(hole[..., None] > 0.5, rgb, full * lip[..., None])
    sc.draw_quad([(X0, Y1, Z), (X1, Y1, Z), (X1, Y0, Z), (X0, Y0, Z)], full, spec=0.35, gloss=18,
                 spec_tint=(1.0, 0.85, 0.6), name='isle')
    # oval portrait
    X0, X1, Y0, Y1 = PAINT['girl']
    w, h = int((X1 - X0) * res), int((Y1 - Y0) * res)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    outer = np.clip((1 - r) * w / 2, 0, 1)
    brass = mat('metal_brass-brushed', mean=0.40, sat=0.5, tint=(1.0, 0.9, 0.72))
    fr = tile(brass, w, h, seed=61, tone_var=0.25, scale=0.5)
    ring = 0.6 + 0.4 * np.cos(np.clip((r - 0.80) / 0.2, 0, 1) * math.pi * 3) ** 2
    fr = fr * ring[..., None] * (0.85 + 0.3 * value_noise(w, h, 30, 62, 2))[..., None]
    canvas = painting('painting_paul-portrait-young-girl-1840', w, h, 63)
    # the dark background of the portrait swallows the edges; a little more mystery
    canvas *= (1 - 0.35 * smoothstep(0.35, 0.8, r))[..., None]
    inner = smoothstep(0.80, 0.78, r)
    full = fr * (1 - inner[..., None]) + canvas * inner[..., None]
    full *= (1 - 0.4 * np.exp(-((r - 0.80) / 0.025) ** 2))[..., None]
    sc.draw_quad([(X0, Y1, Z), (X1, Y1, Z), (X1, Y0, Z), (X0, Y0, Z)], full, alpha=outer, spec=0.3, gloss=18,
                 spec_tint=(1.0, 0.85, 0.6), name='girl')


# ---------------------------------------------------------------- floor
def floor_tex(w_m, d_m, res, seed):
    """dark oak boards running away from the eye (texture: X across, depth down the image)."""
    t = mat('floor_old-oak-dark', mean=0.30, sat=0.75, tint=(1.0, 0.93, 0.88))
    t = np.ascontiguousarray(np.rot90(t))                    # boards run along +z
    s = 2.03 * res / t.shape[1]
    return tile(t, int(w_m * res), int(d_m * res), seed=seed, tone_var=0.12, scale=s)


def draw_floor(sc: Scene):
    res = 760
    x0, x1, z0, z1 = -4.25, 4.25, 2.95, ZN + 0.02
    w_m, d_m = x1 - x0, z1 - z0
    fl = floor_tex(w_m, d_m, res, seed=43)
    # texture row 0 = far edge (z1), last row = near (z0)
    blobs, rects = [], []
    # contact shadows: under the desk, along the near wall, below the door thresholds
    rects.append((0.80 - x0 - 1.6 - 0.05, 0.0, 0.85 - x0 + 0.05, z1 - 2.18, 0.65, 0.12))
    ao = edge_ao(w_m, d_m, 80, {'top': (0.55, 0.10)}, blobs=blobs, rects=rects)
    # rug under the desk (Met Lotto carpet), with fringe
    from scenekit import rug_field                                       # (real knot size, border, wear)
    rx0, rx1, rz0, rz1 = -1.95, 1.95, 2.0, 3.72
    rw, rd = int((rx1 - rx0) * res), int((rz1 - rz0) * res)
    rr = rug_field(rw, rd, res, seed=71)
    m = rect_mask(rw, rd, 0, 0, rw, rd, soft=3)
    # fringe at the far end
    fr_px = int(0.05 * res)
    xs = np.arange(rw)
    fringe = (np.sin(xs * 0.9) * 0.5 + 0.5)[None, :] * np.ones((fr_px, 1))
    px0 = int((rx0 - x0) * res)
    pz0 = int((z1 - rz1) * res)
    reg = fl[pz0:pz0 + rd, px0:px0 + rw]
    reg[:] = rr[:reg.shape[0], :reg.shape[1]] * m[:reg.shape[0], :reg.shape[1], None] + reg * (1 - m[:reg.shape[0], :reg.shape[1], None])
    fz = pz0 - fr_px
    if fz > 0:
        fl[fz:pz0, px0:px0 + rw] = fl[fz:pz0, px0:px0 + rw] * (1 - 0.7 * fringe[..., None]) + \
            np.array([0.42, 0.38, 0.32]) * 0.7 * fringe[..., None]
    sc.draw_quad([(x0, 0, z1), (x1, 0, z1), (x1, 0, z0), (x0, 0, z0)], fl, ao=ao, spec=0.35, gloss=28,
                 name='floor')


# ---------------------------------------------------------------- near walls
def near_board(x0, x1, seed):
    res = 600
    b = Board(x0, x1, 0.0, 2.65, res)
    paper_wall(b, DADO_Y, PICT_Y, seed=seed)
    frieze(b, PICT_Y, 2.65, seed=seed + 1)
    dado(b, seed=seed + 2)
    hmoulding(b, PICT_Y - 0.02, PICT_Y + 0.025, [.2, .7, 1, .8, .4, .6, .2], seed + 3, mean=0.30)
    return b


def door_hole(b: Board, side):
    d = GEOMETRY['door_' + side]
    X0, X1 = X_at(d[0], ZN), X_at(d[0] + d[2], ZN)
    Ytop = Y_at(d[1], ZN)
    door_trim(b, X0, X1, Ytop, seed=101 if side == 'left' else 121)
    ys, xs = b.sl(X0, X1, -0.01, Ytop)
    b.alb[ys, xs] = 0.0
    b.ao[ys, xs] = 0.0


def draw_near_walls(sc: Scene):
    # ---- left: doorway, window with curtains
    L = near_board(-4.02, XAL, 201)
    door_hole(L, 'left')
    wx0, wx1 = X_at(560, ZN), X_at(810, ZN)
    window_trim_and_curtains(L, wx0, wx1, 1.2, 2.1)
    L.ao *= edge_ao(L.x1 - L.x0, L.y1 - L.y0, L.res, {'right': (0.3, 0.05)})[:L.h, :L.w]
    sc.draw_quad([(L.x0, L.y1, ZN), (L.x1, L.y1, ZN), (L.x1, 0, ZN), (L.x0, 0, ZN)], L.alb, alpha=L.alpha,
                 ao=L.ao, name='near_left')
    # ---- right: WAKE UP, room for the pinned drawing, doorway
    R = near_board(XAR, 4.02, 301)
    door_hole(R, 'right')
    scratch_wake_up(R)
    R.ao *= edge_ao(R.x1 - R.x0, R.y1 - R.y0, R.res, {'left': (0.3, 0.05)})[:R.h, :R.w]
    sc.draw_quad([(R.x0, R.y1, ZN), (R.x1, R.y1, ZN), (R.x1, 0, ZN), (R.x0, 0, ZN)], R.alb, alpha=R.alpha,
                 ao=R.ao, name='near_right')


def velvet_curtain(ww, hh, res, seed, inner_right):
    """a hanging velvet drape (albedo, alpha): broad soft folds from a height field, sheen on the ridges."""
    vel = mat('fabric_velvet-red', mean=0.27, sat=0.60, tint=(0.92, 0.80, 0.92))
    t = tile(vel, ww, hh, seed=seed, scale=0.28 * res / vel.shape[1], tone_var=0.06)
    rng = np.random.default_rng(seed)
    u = np.arange(ww, dtype=np.float32) / res                 # metres across
    v = np.arange(hh, dtype=np.float32)[:, None] / res        # metres down
    # height field: folds ~9-14 cm apart, tighter at the top (gathered on the rod), softer at the hem
    hfield = np.zeros((hh, ww), np.float32)
    for k in range(4):
        per = rng.uniform(0.085, 0.14) / (k * 0.6 + 1)
        ph = rng.uniform(0, 2 * math.pi)
        amp = 1.0 / (k + 1)
        wob = 0.25 * np.sin(v * rng.uniform(2, 4) + ph)
        hfield += amp * np.sin((u[None, :] / per) * 2 * math.pi + ph + wob)
    gather = 1.0 + 0.6 * np.exp(-v / 0.12)                     # pleated header
    hfield *= gather
    slope = np.gradient(hfield, axis=1) * res * 0.02
    facing = 1 / np.sqrt(1 + slope ** 2)
    light = (-1 if inner_right else 1)                         # the window side is lit a little more
    diff = np.clip(0.62 * facing + 0.30 * np.tanh(slope * light * 0.8) + 0.2, 0.15, 1.3)
    valley = smoothstep(-1.2, 0.6, hfield)                     # deep folds fall into shadow
    sheen = (1 - facing) ** 1.5 * 0.9                          # velvet glows at grazing angles
    shade = diff * (0.45 + 0.55 * valley) + sheen * 0.35
    edge = (u / u[-1]) if inner_right else (1 - u / u[-1])
    shade *= (0.80 + 0.35 * edge[None, :] ** 4)
    t = t * shade[..., None]
    # hem a little uneven, the edges follow the folds
    hem = hh - 1 - (0.012 + 0.008 * np.sin(u * 61 + seed)) * res
    a = (np.arange(hh)[:, None] < hem[None, :]).astype(np.float32)
    side = np.abs(np.sin(hfield[:, :1] * 0.5)) * 0.008 * res
    a *= np.clip((np.arange(ww)[None, :] - side * (0 if inner_right else 1)) + 1, 0, 1)
    a = blur(a, 0.7)
    return np.clip(t, 0, 1), np.clip(a, 0, 1)


def window_trim_and_curtains(b: Board, X0, X1, Y0, Y1):
    res = b.res
    # the opening is a hole in the wall
    ys, xs = b.sl(X0, X1, Y0, Y1)
    b.alpha[ys, xs] = 0
    # a slim casing around it (same family as the doors, no plinths)
    cw = 0.085
    for a, c in ((X0 - cw, X0), (X1, X1 + cw)):
        ys, xs = b.sl(a, c, Y0 - 0.06, Y1 + cw)
        b.alb[ys, xs] = fluted(xs.stop - xs.start, ys.stop - ys.start, 141, flutes=2)
        b.shadow(a, c, Y0 - 0.06, Y1 + cw, 0.4, 0.015, dy=-0.004)
    ys, xs = b.sl(X0, X1, Y1, Y1 + cw)
    b.alb[ys, xs] = fluted(xs.stop - xs.start, ys.stop - ys.start, 143, vertical=False, flutes=2)
    rs = int(round(cw * res))
    for xc in (X0 - cw / 2, X1 + cw / 2):
        b.put(xc - cw / 2, xc + cw / 2, Y1, Y1 + cw, rosette(rs + 2, 145))
    # apron under the sill
    ys, xs = b.sl(X0 - cw, X1 + cw, Y0 - 0.10, Y0 - 0.015)
    t = wood('wood_dark-varnished', xs.stop - xs.start, ys.stop - ys.start, res, 2.0, seed=147, mean=0.30)
    b.alb[ys, xs] = t * profile_shade(ys.stop - ys.start, [1, .7, .9, .4])[:, None, None]
    b.shadow(X0 - cw, X1 + cw, Y0 - 0.10, Y0 - 0.015, 0.4, 0.02, dy=-0.015)
    # curtain rod with finials (brass)
    rod_y = Y1 + 0.135
    brass = mat('metal_brass-brushed', mean=0.45, sat=0.5, tint=(1.0, 0.9, 0.72))
    ys, xs = b.sl(X0 - 0.30, X1 + 0.27, rod_y - 0.012, rod_y + 0.012)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    rod = tile(brass, ww, hh, seed=5, scale=0.4)
    rod *= profile_shade(hh, np.sin(np.linspace(0, math.pi, hh)) * 2)[:, None, None] * 1.1
    b.alb[ys, xs] = np.clip(rod, 0, 1)
    for xf in (X0 - 0.31, X1 + 0.28):
        n = int(0.06 * res)
        yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
        r = np.sqrt((xx - n / 2) ** 2 + (yy - n / 2) ** 2) / (n / 2)
        m = np.clip((1 - r) * 6, 0, 1)
        f = tile(brass, n, n, seed=7, scale=0.4) * (1.2 - 0.7 * r)[..., None] * (1 - 0.3 * (yy / n))[..., None]
        paste_over(b.alb, np.clip(f, 0, 1), m, int(b.px(xf) - n / 2), int(b.py(rod_y) - n / 2))
    b.shadow(X0 - 0.30, X1 + 0.27, rod_y - 0.012, rod_y + 0.012, 0.5, 0.012, dy=-0.02)
    # velvet curtains drawn back: left 476..590, right 780..886 (screen px), hanging past the sill
    for k, (u0, u1) in enumerate(((476, 590), (780, 886))):
        Xa, Xb = X_at(u0, ZN), X_at(u1, ZN)
        Ya, Yb = Y0 - 0.52, rod_y + 0.015
        ys, xs = b.sl(Xa, Xb, Ya, Yb)
        hh, ww = ys.stop - ys.start, xs.stop - xs.start
        t, a = velvet_curtain(ww, hh, res, 60 + k, inner_right=(k == 0))
        b.alb[ys, xs] = t * a[..., None] + b.alb[ys, xs] * (1 - a[..., None])
        b.alpha[ys, xs] = np.maximum(b.alpha[ys, xs], a)
        # rings on the rod
        for xr in np.linspace(Xa + 0.02, Xb - 0.02, 6):
            n = int(0.035 * res)
            yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
            r = np.sqrt((xx - n / 2) ** 2 + (yy - n / 2) ** 2) / (n / 2)
            m = np.clip((1 - np.abs(r - 0.75) / 0.25) * 2, 0, 1)
            paste_over(b.alb, tile(brass, n, n, seed=9, scale=0.4) * 0.9, m, int(b.px(xr) - n / 2),
                       int(b.py(rod_y) - n / 2))
        # the drape throws a soft shadow onto the wall beside and behind it
        sh = np.zeros((b.h, b.w), np.float32)
        sh[ys, xs] = a
        sh = blur(np.roll(sh, int(0.015 * res), 0), 0.03 * res)
        own = np.zeros((b.h, b.w), np.float32)
        own[ys, xs] = a
        b.ao *= 1 - 0.40 * sh * (1 - own)
        b.ao[ys, xs] *= 1 - 0.25 * np.exp(-np.linspace(0, 1, hh) * 12)[:, None]   # under the rod


def scratch_wake_up(b: Board):
    """'WAKE UP' gouged through the wallpaper: the Eater letterforms are only a guide; the letters are
    made of many knife strokes and a ragged cut outline that shows the pale backing paper."""
    res = b.res
    k = res / 300.0                                # board px per screen px
    fnt = font('Eater-Regular.ttf', int(56 * k))
    pad = int(16 * k)
    m = text_mask('WAKE UP', fnt, pad=pad)
    hh, ww = m.shape
    rng = np.random.default_rng(903)
    shift = (value_noise(ww, 1, 30 * k, 905)[0] - 0.5) * 3 * k     # the hand wobbles
    m = np.stack([np.roll(m[:, i], int(shift[i])) for i in range(ww)], 1)
    soft = blur(m, 1.4 * k)
    inside = smoothstep(0.35, 0.7, soft)
    # dense knife strokes inside the letters (mostly one direction, like a hand dragging a blade)
    strokes = Image.new('L', (ww, hh), 0)
    dr = ImageDraw.Draw(strokes)
    for _ in range(int(4200 * k)):
        x, y = rng.random() * (ww - 1), rng.random() * (hh - 1)
        if inside[int(y), int(x)] < 0.5:
            continue
        ang = math.radians(rng.normal(-72, 9))
        L = rng.uniform(5, 15) * k
        dr.line([(x, y), (x + math.cos(ang) * L, y - math.sin(ang) * L)], fill=int(rng.uniform(150, 255)),
                width=max(1, int(round(rng.uniform(0.8, 1.6) * k))))
    st = f32(strokes) * inside
    # ragged outline: the blade went round each letter first
    n1 = value_noise(ww, hh, 2.5 * k, 901, 2)
    edge = np.clip(1 - np.abs(soft - 0.5 + (n1 - 0.5) * 0.25) / 0.13, 0, 1)
    edge *= smoothstep(0.3, 0.6, value_noise(ww, hh, 9 * k, 906, 2)) * 0.5 + 0.5
    # a few slips that overshoot the letters
    sl = Image.new('L', (ww, hh), 0)
    d2 = ImageDraw.Draw(sl)
    for _ in range(10):
        x, y = rng.random() * ww, hh * rng.uniform(0.3, 0.8)
        ang = math.radians(rng.normal(-73, 5))
        L = rng.uniform(16, 34) * k
        d2.line([(x, y), (x + math.cos(ang) * L, y - math.sin(ang) * L)], fill=150, width=max(1, int(0.9 * k)))
    G = np.clip(np.maximum(st * 1.05, edge * 0.95) + f32(sl) * 0.7, 0, 1)
    G = np.clip(G + inside * 0.25, 0, 1)                 # the paper inside the letters is roughed up too
    rot = lambda a: np.asarray(Image.fromarray(a, 'F').rotate(math.degrees(0.05), resample=BICUBIC, expand=True), np.float32)
    G, S = rot(G), rot(np.clip(st + f32(sl) * 0.7, 0, 1))
    hh, ww = G.shape
    bb = fnt.getbbox('WAKE UP')
    x0 = int(b.px(X_at(1610, ZN)) - pad)
    y0 = int(b.py(Y_at(600, ZN)) - (bb[3] - bb[1]) - pad - 0.025 * ww)
    ys = slice(max(0, y0), min(b.h, y0 + hh))
    xs = slice(max(0, x0), min(b.w, x0 + ww))
    G = G[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0]
    S = S[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0]
    alb = b.alb[ys, xs]
    # pale backing paper / plaster shows in each scratch; grime settles in the deepest ones
    pl = mat('plaster_aged-beige', mean=0.86, sat=0.22)
    pl = tile(pl, G.shape[1], G.shape[0], seed=904, scale=0.5) * np.array([1.0, 0.97, 0.95])
    grime = blur(G, 2.5 * k)
    inside_col = pl * (1 - 0.25 * grime[..., None]) * (0.55 + 0.45 * S[..., None])   # the knife striations
    sh = np.clip(G - np.roll(np.roll(G, int(2.5 * k), 0), int(1.5 * k), 1), 0, 1)     # groove wall in shadow
    lip = np.clip(G - np.roll(np.roll(G, -int(1.5 * k), 0), -int(1 * k), 1), 0, 1)   # torn paper lip
    out = alb * (1 - G[..., None]) + inside_col * G[..., None]
    out = out * (1 - 0.85 * sh[..., None]) + lip[..., None] * 0.06
    halo = np.clip(blur(G, 4 * k) * 1.4 - G, 0, 1)        # dirty fingers round the letters
    out = out * (1 - 0.30 * halo[..., None])
    bleed = blur(G, 2 * k)                                # an old rust-red stain in the cuts
    out = out * (1 - 0.22 * bleed[..., None]) + bleed[..., None] * np.array([0.34, 0.06, 0.08]) * 0.22
    b.alb[ys, xs] = np.clip(out, 0, 1)
    b.ao[ys, xs] *= 1 - 0.15 * G


# ---------------------------------------------------------------- desk
def drawer_front(w, h, seed, res, pulls=True, panel=True):
    t = wood('wood_lacquered-cherry', w, h, res, 1.0, seed=seed, mean=0.29, sat=0.50, tint=(0.86, 0.90, 0.80),
             contrast=1.35)
    if panel:
        e = rect_mask(w, h, 0, 0, w, h, soft=max(2, min(w, h) * 0.05))
        inset = rect_mask(w, h, w * 0.08, h * 0.16, w * 0.92, h * 0.84, soft=2)
        t *= (0.70 + 0.30 * e)[..., None]                     # rounded drawer edges
        # a raised panel: its top bevel catches the light, the bottom bevel falls into shadow
        sm = blur(inset, max(1.5, h * 0.04))
        gy = np.gradient(sm, axis=0) * max(1.5, h * 0.04) * 2.5
        t *= np.clip(1 + 0.9 * gy[..., None] * -1 + 0.08 * inset[..., None], 0.5, 1.5)
    if pulls:
        brass = mat('metal_brass-brushed', mean=0.5, sat=0.6, tint=(1.0, 0.9, 0.7))
        for cxp in (w * 0.5,):
            pw, phh = int(w * 0.16), max(4, int(h * 0.16))
            yy, xx = np.mgrid[0:phh, 0:pw].astype(np.float32)
            arc = np.abs(np.sqrt(((xx - pw / 2) / (pw / 2)) ** 2 + ((yy) / (phh * 0.9)) ** 2) - 0.8) < 0.16
            m = blur(arc.astype(np.float32), 0.8)
            p = tile(brass, pw, phh, seed=seed + 1, scale=0.3) * 1.2
            paste_over(t, p, m, int(cxp - pw / 2), int(h * 0.48))
            # back plates
            for dx in (-pw * 0.45, pw * 0.45):
                r = max(3, int(h * 0.06))
                yy2, xx2 = np.mgrid[0:2 * r, 0:2 * r].astype(np.float32)
                mm = np.clip((r - np.sqrt((xx2 - r) ** 2 + (yy2 - r) ** 2)) / 1.2, 0, 1)
                paste_over(t, tile(brass, 2 * r, 2 * r, seed=seed + 2, scale=0.3) * 1.1, mm,
                           int(cxp + dx - r), int(h * 0.42 - r))
    return np.clip(t, 0, 1)


def draw_desk(sc: Scene):
    res = 900
    zf, zb = DESK_ZF, DESK_ZB
    x0, x1 = -0.80, 0.85
    top_t = DESK_Y
    # kneehole back panel
    sc.draw_quad([(-0.30, DESK_Y - 0.03, 2.70), (0.39, DESK_Y - 0.03, 2.70), (0.39, 0, 2.70), (-0.30, 0, 2.70)],
                 wood('wood_lacquered-cherry', int(0.69 * res), int(0.73 * res), res, 1.0, seed=2, mean=0.18),
                 ao=edge_ao(0.69, 0.73, 80, {'top': (0.7, 0.15), 'left': (0.5, 0.1), 'right': (0.5, 0.1)}),
                 name='kneehole_back')
    # pedestal inner sides
    for X, nm in ((-0.30, 'l'), (0.39, 'r')):
        sc.draw_quad([(X, DESK_Y - 0.03, 2.22), (X, DESK_Y - 0.03, 2.70), (X, 0, 2.70), (X, 0, 2.22)],
                     wood('wood_lacquered-cherry', int(0.48 * res), int(0.73 * res), res, 1.0, seed=3, mean=0.18),
                     ao=edge_ao(0.48, 0.73, 80, {'top': (0.6, 0.12), 'right': (0.4, 0.1)}), name='ped_in_' + nm)
    # pedestal fronts with three drawers each
    for (a, c), nm in (((-0.74, -0.30), 'l'), ((0.39, 0.79), 'r')):
        wpx, hpx = int((c - a) * res), int((DESK_Y - 0.03) * res)
        t = wood('wood_lacquered-cherry', wpx, hpx, res, 1.0, seed=5, mean=0.27, contrast=1.35)
        hs = [0.17, 0.22, 0.27]
        y = int(0.035 * res)
        for i, hh in enumerate(hs):
            dh = int(hh * res)
            df = drawer_front(int(wpx - 0.05 * res), dh - int(0.02 * res), 10 + i, res)
            gx, gy = int(0.025 * res), y
            g = int(0.006 * res)
            t[gy - g:gy + df.shape[0] + g, gx - g:gx + df.shape[1] + g] *= 0.25     # the dark gap round a drawer
            t[gy:gy + df.shape[0], gx:gx + df.shape[1]] = df
            y += dh
        sc.draw_quad([(a, DESK_Y - 0.03, 2.22), (c, DESK_Y - 0.03, 2.22), (c, 0, 2.22), (a, 0, 2.22)], t,
                     spec=0.3, gloss=30, ao=edge_ao(c - a, DESK_Y - 0.03, 80, {'top': (0.65, 0.05), 'left': (0.3, 0.015),
                                                                         'right': (0.3, 0.015), 'bottom': (0.4, 0.1)}),
                     name='ped_front_' + nm)
    # centre drawer / apron over the kneehole
    t = drawer_front(int(0.69 * res), int(0.1 * res), 20, res)
    sc.draw_quad([(-0.30, DESK_Y - 0.03, 2.22), (0.39, DESK_Y - 0.03, 2.22), (0.39, DESK_Y - 0.13, 2.22),
                  (-0.30, DESK_Y - 0.13, 2.22)], t, spec=0.3, gloss=30, name='apron')
    # the top: thick front edge + surface with a leather writing inset
    edge = wood('wood_lacquered-cherry', int((x1 - x0) * res), int(0.03 * res), res, 1.0, seed=6, mean=0.26)
    edge *= profile_shade(edge.shape[0], [1, .9, .7, .5])[:, None, None]
    sc.draw_quad([(x0, top_t, zf), (x1, top_t, zf), (x1, top_t - 0.03, zf), (x0, top_t - 0.03, zf)], edge,
                 spec=0.4, gloss=30, name='desk_edge')
    wpx, dpx = int((x1 - x0) * res), int((zb - zf) * res)
    top = wood('wood_lacquered-cherry', wpx, dpx, res, 1.0, seed=7, mean=0.27, contrast=1.3)
    # leather inset with a gilt tooled line
    lx0, lx1, lz0, lz1 = 0.07, (x1 - x0) - 0.07, 0.07, (zb - zf) - 0.06
    lea = mat('fabric_leather-brown', mean=0.24, sat=0.65, tint=(0.85, 0.95, 0.85))
    lt = tile(lea, int((lx1 - lx0) * res), int((lz1 - lz0) * res), seed=8, scale=0.4 * res / lea.shape[1],
              tone_var=0.2)
    m = rect_mask(lt.shape[1], lt.shape[0], 0, 0, lt.shape[1], lt.shape[0], soft=1.5)
    line = rect_mask(lt.shape[1], lt.shape[0], 10, 10, lt.shape[1] - 10, lt.shape[0] - 10, soft=0.8) - \
        rect_mask(lt.shape[1], lt.shape[0], 13, 13, lt.shape[1] - 13, lt.shape[0] - 13, soft=0.8)
    lt = lt * (1 - line[..., None]) + np.array([0.55, 0.42, 0.22]) * line[..., None] * 0.7
    paste_over(top, lt, m, int(lx0 * res), int(lz0 * res))
    # scuffs and an ink ring
    n = value_noise(wpx, dpx, 60, 9, 3)
    top *= (0.9 + 0.2 * n)[..., None]
    # contact shadows: lamp base, CRT, books, the alarm clock (the clock itself is drawn by the game)
    cz = F * (EYE - DESK_Y) / (623 - CY)
    cxw = X_at(1452, cz)
    blobs = [
        (cxw - x0, zb - cz, 0.085, 0.05, 0.55),                    # alarm clock contact shadow
        (-0.541 - x0, zb - 2.65, 0.10, 0.08, 0.6),                 # lamp base
    ]
    rects = [(-0.36 - x0, zb - 2.78, 0.36 - x0, zb - 2.45, 0.75, 0.035),   # CRT
             (-0.77 - x0, zb - 2.50, -0.60 - x0, zb - 2.26, 0.6, 0.02)]   # books
    ao = edge_ao(x1 - x0, zb - zf, 200, {'top': (0.25, 0.03)}, blobs=blobs, rects=rects)
    sc.draw_quad([(x0, top_t, zb), (x1, top_t, zb), (x1, top_t, zf), (x0, top_t, zf)], top, ao=ao, spec=0.55,
                 gloss=40, spec_tint=(1.0, 0.92, 0.85), name='desk_top', direct_ao=0.8)


def draw_crt(sc: Scene):
    """an old wood-cased CRT on the desk (knobs and a speaker grille at the right);
    the screen shows a dim green 'z z z'."""
    Z = 2.45
    X0, X1, Y0, Y1 = -0.36, 0.43, DESK_Y, 1.235
    res = F / Z * SS                                   # texture px == screen ss px
    w, h = int((X1 - X0) * res), int((Y1 - Y0) * res)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cab = wood('wood_fine-grain-old', w, h, res, 0.6, seed=4, mean=0.32, sat=0.7, tint=(1.0, 0.92, 0.84))
    # rounded cabinet corners + a bevel catching the light along the top and left edges
    rc = 0.03 * res
    dx = np.maximum(np.maximum(rc - xx, xx - (w - 1 - rc)), 0)
    dy = np.maximum(np.maximum(rc - yy, yy - (h - 1 - rc)), 0)
    alpha = np.clip(rc - np.sqrt(dx * dx + dy * dy) + 0.5, 0, 1)
    d_edge = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy))
    bevel = np.exp(-d_edge / (0.012 * res))
    lit_side = ((yy < h * 0.5) & (yy < xx)) | (xx < yy) & (xx < w * 0.2)
    cab *= (1 + bevel * np.where(lit_side, 0.16, -0.30))[..., None]
    # screen box in texture px
    sx0, sx1 = (X_at(1060, Z) - X0) * res, (X_at(1340, Z) - X0) * res
    sy0, sy1 = (Y1 - Y_at(438, Z)) * res, (Y1 - Y_at(628, Z)) * res
    pad = 0.026 * res
    bez = np.clip(rect_mask(w, h, sx0 - pad, sy0 - pad, sx1 + pad, sy1 + pad, soft=5), 0, 1)
    plastic = np.zeros((h, w, 3), np.float32) + np.array([0.085, 0.078, 0.085])
    plastic *= (0.85 + 0.3 * value_noise(w, h, 40, 5, 2))[..., None]
    # the bezel slopes in toward the glass: lighter top/left, darker bottom/right
    inner = rect_mask(w, h, sx0 - pad * 0.35, sy0 - pad * 0.35, sx1 + pad * 0.35, sy1 + pad * 0.35, soft=4)
    slope = np.clip(bez - inner, 0, 1)
    plastic *= (1 + slope * np.where(yy < (sy0 + sy1) / 2, 0.5, -0.4))[..., None]
    alb = cab * (1 - bez[..., None]) + plastic * bez[..., None]
    # rounded glass (a slightly convex tube face)
    rx, ry = (sx1 - sx0) / 2, (sy1 - sy0) / 2
    cxs, cys = (sx0 + sx1) / 2, (sy0 + sy1) / 2
    q = np.abs((xx - cxs) / rx) ** 7 + np.abs((yy - cys) / ry) ** 7
    glass = np.clip((1 - q) * 25, 0, 1)
    alb = alb * (1 - glass[..., None]) + np.array([0.025, 0.035, 0.035]) * glass[..., None]
    # control column to the right of the tube: two knobs over a speaker grille
    kx = (sx1 + pad + w) / 2
    for i, ky in enumerate((sy0 + 0.05 * res, sy0 + 0.12 * res)):
        r = 0.020 * res
        d = np.sqrt((xx - kx) ** 2 + (yy - ky) ** 2)
        m = np.clip(r - d + 0.5, 0, 1)
        shade = 0.55 + 0.6 * np.clip(1 - d / r, 0, 1) - 0.25 * ((yy - ky) / r)
        knob = np.stack([shade * 0.16, shade * 0.14, shade * 0.13], -1)
        ring = np.clip(1 - np.abs(d - r * 1.25) / (0.004 * res), 0, 1)
        alb = alb * (1 - ring[..., None] * 0.5)
        alb = alb * (1 - m[..., None]) + knob * m[..., None]
    gx0, gx1 = sx1 + pad + 0.012 * res, w - 0.016 * res
    gy0, gy1 = sy0 + 0.17 * res, sy1 - 0.0 * res
    grille = rect_mask(w, h, gx0, gy0, gx1, gy1, soft=1.5)
    slots = 0.5 + 0.5 * np.sign(np.sin((yy - gy0) / (0.007 * res) * math.pi))
    gcol = mat('fabric_linen-check', mean=0.20, sat=0.2)
    gt = tile(gcol, w, h, seed=3, scale=0.15)
    alb = alb * (1 - grille[..., None]) + (gt * (0.45 + 0.4 * slots[..., None])) * grille[..., None]
    # emissive screen: dim green phosphor, vignetted, "z z z" in VT323
    r = np.sqrt(((xx - cxs) / rx) ** 2 + ((yy - cys) / ry) ** 2)
    g0, g1 = hexcol('#2c4a46', False), hexcol('#0a1614', False)
    k = np.clip(r, 0, 1)[..., None]
    scr = g0 * (1 - k) + g1 * k
    fnt = font('VT323-Regular.ttf', int(30 * res / (F / Z)))
    tm = text_mask('z z z', fnt, pad=4)
    th, tw = tm.shape
    tx, ty = int(cxs - tw / 2), int(cys - th / 2 + 2)
    glowm = np.zeros((h, w), np.float32)
    paste_over(glowm, np.ones_like(tm), tm, tx, ty)
    col = np.array([180, 255, 220], np.float32) / 255
    scr = scr + glowm[..., None] * col * 0.60 + blur(glowm, 7)[..., None] * col * 0.30
    lines = 0.95 + 0.05 * (np.sin(yy * math.pi / 2.0) ** 2)
    scr *= lines[..., None]
    # reflections on the glass: the window (cool, upper left) and the lamp (warm dot, left)
    refl = np.exp(-(((xx - (sx0 + rx * 0.42)) / (rx * 0.30)) ** 2 + ((yy - (sy0 + ry * 0.50)) / (ry * 0.40)) ** 2))
    scr = scr + refl[..., None] * hexcol('#cfc8ff', False) * 0.06
    lamp_r = np.exp(-(((xx - sx0) / (rx * 0.35)) ** 2)) * np.exp(-(((yy - (sy0 + ry * 1.5)) / (ry * 0.6)) ** 2))
    scr = scr + lamp_r[..., None] * np.array([1.0, 0.75, 0.45]) * 0.05     # the lamp's warmth on the glass
    edge_hl = np.exp(-((q - 0.55) / 0.12) ** 2) * (yy < cys) * 0.04
    scr = scr + edge_hl[..., None]
    scr *= glass[..., None]
    sc.draw_quad([(X0, Y1, Z), (X1, Y1, Z), (X1, Y0, Z), (X0, Y0, Z)], np.clip(alb, 0, 1), alpha=alpha,
                 emissive=np.clip(scr, 0, 1), emit=0.85, spec=0.2, gloss=60, name='crt')


def draw_lamp(sc: Scene, Lt):
    """brass desk lamp with a glowing fabric shade."""
    Z = 2.65
    bx = -0.541
    res = F / Z * SS
    brass = mat('metal_brass-brushed', mean=0.45, sat=0.6, tint=(1.0, 0.9, 0.7))
    # base (a short drum) and stem
    bw, bh = 0.18, 0.035
    t = tile(brass, int(bw * res), int(bh * res), seed=3, scale=0.3)
    t *= profile_shade(t.shape[0], [1.0, 0.9, 0.6, 0.4])[:, None, None]
    sc.draw_quad([(bx - bw / 2, DESK_Y + bh, Z - 0.05), (bx + bw / 2, DESK_Y + bh, Z - 0.05),
                  (bx + bw / 2, DESK_Y, Z - 0.05), (bx - bw / 2, DESK_Y, Z - 0.05)], t, spec=0.8, gloss=25,
                 spec_tint=(1, .85, .6), name='lamp_base')
    sw = 0.022
    t = tile(brass, int(sw * res) + 2, int(0.3 * res), seed=4, scale=0.3)
    xs = np.linspace(-1, 1, t.shape[1])
    t *= (0.55 + 0.6 * np.sqrt(np.clip(1 - xs ** 2, 0, 1)) + 0.3 * np.exp(-((xs + 0.35) / 0.2) ** 2))[None, :, None]
    sc.draw_quad([(bx - sw / 2, 1.06, Z), (bx + sw / 2, 1.06, Z), (bx + sw / 2, DESK_Y + bh, Z),
                  (bx - sw / 2, DESK_Y + bh, Z)], np.clip(t, 0, 1), spec=0.8, gloss=25, name='lamp_stem')
    # shade: trapezoid 905..1005 at the bottom (y=500), narrower at the top (y=445)
    Zs = 2.60
    ys_top, ys_bot = Y_at(445, Zs), Y_at(500, Zs)
    xb0, xb1 = X_at(905, Zs), X_at(1005, Zs)
    xt0, xt1 = X_at(927, Zs), X_at(983, Zs)
    w, h = int((xb1 - xb0) * res), int((ys_top - ys_bot) * res)
    cloth = mat('paper_offwhite-grain', mean=0.60, sat=0.3, tint=(1.0, 0.92, 0.80))
    ct = tile(cloth, w, h, seed=9, scale=0.5)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = yy / h
    half = (0.28 + 0.22 * v) * w                       # trapezoid half-width (top 56/100 .. bottom 100/100)
    cxp = w / 2
    a = np.clip((half - np.abs(xx - cxp)) / 1.5, 0, 1)
    # bottom edge: an ellipse (the rim seen from slightly above)
    a *= np.clip((h - 1 - yy + 0.0) / 1.5, 0, 1)
    across = (xx - cxp) / np.maximum(half, 1)
    # transmitted glow: brightest low in the shade, falling to the sides (a lit drum)
    glow = (0.45 + 0.55 * v ** 1.4) * (1 - 0.55 * across ** 2)
    ribs = 1 - 0.10 * (np.cos(across * math.pi * 3.5) ** 8)
    em = ct * (glow * ribs)[..., None] * np.array([1.0, 0.82, 0.55])
    # a darker trim band at the top and bottom rims
    rim = (yy < h * 0.08) | (yy > h * 0.92)
    em *= np.where(rim, 0.55, 1.0)[..., None]
    sc.draw_quad([(xb0, ys_top, Zs), (xb1, ys_top, Zs), (xb1, ys_bot, Zs), (xb0, ys_bot, Zs)], ct * 0.5,
                 alpha=a, emissive=np.clip(em, 0, 1), emit=3.2, name='lamp_shade')


def draw_desk_things(sc: Scene):
    """papers, a stack of old books, a pen."""
    res = 1100
    paper = f32(load('paper_old-paper-stained'))
    paper = match_albedo(paper, mean=0.74, sat=0.40)
    rng = np.random.default_rng(55)
    sheets = [(1172, 641, 0.20, -0.18), (1236, 646, 0.18, 0.12), (1306, 638, 0.21, -0.05), (1372, 645, 0.17, 0.22)]
    for i, (u, v, sz, rot) in enumerate(sheets):
        P = np.array(  # centre on the desk top
            [X_at(u, F * (EYE - DESK_Y) / (v - CY)), DESK_Y + 0.001 + i * 0.0006, F * (EYE - DESK_Y) / (v - CY)])
        wv, dv = sz, sz * 1.3
        c, s = math.cos(rot), math.sin(rot)
        pts = []
        for (dx, dz) in ((-wv / 2, dv / 2), (wv / 2, dv / 2), (wv / 2, -dv / 2), (-wv / 2, -dv / 2)):
            pts.append((P[0] + dx * c - dz * s, P[1], P[2] + dx * s + dz * c))
        pw, ph = int(wv * res), int(dv * res)
        y0 = rng.integers(0, paper.shape[0] - 200)
        x0 = rng.integers(0, paper.shape[1] - 200)
        t = resize_f(paper[y0:y0 + 300, x0:x0 + 230], pw, ph)
        # pencil lines / handwriting scribbles (no words)
        im = Image.fromarray((t * 255).astype(np.uint8))
        dr = ImageDraw.Draw(im)
        for ln in range(5 + i % 3):
            yl = int(ph * (0.15 + ln * 0.12))
            xl = int(pw * 0.1)
            while xl < pw * 0.88:
                wl = int(rng.uniform(0.05, 0.16) * pw)
                pts_l = [(xl + j, yl + math.sin(j * 0.9 + ln) * 1.2) for j in range(0, wl, 2)]
                if len(pts_l) > 1:
                    dr.line(pts_l, fill=(70, 62, 70), width=1)
                xl += wl + int(0.03 * pw)
        t = f32(im)
        # a soft shadow decal under the sheet, then the sheet a hair above it (slightly curled edges)
        sh_pts = [(p[0] + 0.006, DESK_Y + 0.0004, p[2] + 0.008) for p in pts]
        sa = blur(rect_mask(64, 80, 6, 6, 58, 74), 4)
        sc.draw_quad(sh_pts, np.zeros((80, 64, 3), np.float32), alpha=sa * 0.55, name=f'paper_sh{i}')
        curl = 1 - 0.18 * (1 - rect_mask(pw, ph, 0, 0, pw, ph, soft=max(2, pw * 0.05)))
        sc.draw_quad(pts, t * curl[..., None], name=f'paper{i}', direct_ao=0.2)
    # books: a stack of three on the desk's left front corner
    cloth = [mat('fabric_bookcloth-red', mean=0.16, sat=0.55), mat('fabric_leather-brown', mean=0.18, sat=0.6),
             mat('fabric_quilt-green-wholecloth', mean=0.16, sat=0.4)]
    y = DESK_Y
    for i, (th, inset, ci) in enumerate(((0.045, 0.0, 0), (0.035, 0.01, 1), (0.03, 0.02, 2))):
        x0b, x1b = -0.77 + inset, -0.60 - inset * 0.5
        z0b, z1b = 2.26 + inset * 0.5, 2.50 - inset
        cl = cloth[ci]

        def faces(wp, hp, face, cl=cl, i=i):
            if face == 'top':
                t = tile(cl, wp, hp, seed=i, scale=0.3)
                t *= (0.85 + 0.15 * rect_mask(wp, hp, 0, 0, wp, hp, soft=4))[..., None]
                return t
            if face == 'front':                       # the spine faces us: cloth with gilt bands
                t = tile(cl, wp, hp, seed=i + 7, scale=0.3) * 1.15
                for fx in (0.12, 0.2, 0.8, 0.88):
                    xg = int(wp * fx)
                    t[:, xg:xg + max(1, wp // 90)] = np.array([0.55, 0.42, 0.20])
                t *= (0.75 + 0.25 * np.sin(np.linspace(0, math.pi, hp)))[:, None, None]
                return t
            # page edges (side): cream paper block with a cloth border
            t = np.zeros((hp, wp, 3), np.float32) + np.array([0.66, 0.60, 0.48])
            lines = 0.85 + 0.15 * np.sin(np.arange(hp) * 2.1)[:, None]
            t *= lines[..., None]
            b = max(1, int(hp * 0.16))
            t[:b] = tile(cl, wp, b, seed=i + 3, scale=0.3)
            t[-b:] = tile(cl, wp, b, seed=i + 4, scale=0.3)
            return t
        sc.box((x0b, y, z0b), (x1b, y + th, z1b), faces, res=1400, occluder=False, name=f'book{i}')
        y += th
    # a fountain pen lying on the leather
    pz = 2.33
    pts = [(0.48, DESK_Y + 0.006, pz + 0.02), (0.62, DESK_Y + 0.006, pz - 0.01),
           (0.62, DESK_Y + 0.006, pz - 0.022), (0.48, DESK_Y + 0.006, pz + 0.008)]
    pen = np.zeros((20, 200, 3), np.float32) + np.array([0.05, 0.04, 0.05])
    pen[:, 150:160] = [0.5, 0.42, 0.25]
    pen[:6] *= 2.5
    sc.draw_quad(pts, pen, spec=1.0, gloss=60, name='pen')


def draw_air(sc: Scene, L):
    """screen-space light: lamp bloom halo, moon shaft from the window to the floor."""
    # warm haze around the shade and a hot spot under it
    sc.glow(955, 470, 150, L['amber'] * np.array([1.0, 0.85, 0.65]), 0.10, 1.6)
    sc.glow(955, 505, 60, L['amber'], 0.25, 2.0)
    # moon shaft: from the window panes down-right to the patch on the floor
    m = sc.poly_mask([(585, 175), (800, 175), (1010, 905), (640, 905)], blur_px=26)
    yy = np.linspace(0, 1, sc.cam.H)[:, None]
    m *= (0.15 + 0.85 * np.exp(-((yy - 0.55) / 0.35) ** 2)) * 0.16
    sc.canvas += m[..., None] * L['moon'][None, None, :]


# ==========================================================================
def edge_darkness(img):
    u = (np.arange(W) + 0.5) / W
    k = 0.28 * (1 - smoothstep(0.0, 0.2, u)) + 0.28 * smoothstep(0.8, 1.0, u)
    return img * ((1 - k) ** 2.2)[None, :, None]


def fill_door_boxes(img: np.ndarray, color) -> np.ndarray:
    """pure darkness exactly inside the two door boxes (the game draws the doorway there)."""
    for side in ('left', 'right'):
        x, y, w, h = GEOMETRY['door_' + side]
        X = np.arange(W) + 0.5
        Yy = np.arange(H) + 0.5
        cx = np.clip(np.minimum(X - x, x + w - X) + 0.5, 0, 1)
        cy = np.clip(np.minimum(Yy - y, y + h - Yy) + 0.5, 0, 1)
        a = cy[:, None] * cx[None, :]
        img = img * (1 - a[..., None]) + np.asarray(color, np.float32) * a[..., None]
    return img


def render(seed=7):
    sc = build_scene()
    lin = sc.downsample()
    lin = edge_darkness(lin)
    y = finish(lin, 'room', seed=seed, return_array=True)
    y = fill_door_boxes(y, np.array([5, 3, 9], np.float32) / 255)
    return y, lin


def build(out_path):
    y, _ = render()
    img = pil(y)
    save_jpeg(img, out_path, quality=84, max_kb=880)
    return out_path


if __name__ == '__main__':
    import time
    t = time.time()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/office_test.png')
    y, lin = render()
    pil(y).save(out)
    np.save(str(out) + '.lin.npy', lin.astype(np.float16))
    print('saved', out, f'{time.time() - t:.1f}s')
