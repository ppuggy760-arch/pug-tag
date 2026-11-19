"""CAM 4 - STAIRS TO NOWHERE (1824 x 1026).

A straight Victorian staircase seen from the hall below: varnished treads under
a worn crimson runner held by brass stair rods, a turned-baluster banister with
a newel lamp at its foot, William Morris 'Blackthorn' paper above a raking
panelled dado. Moonlight from a tall window across the stairwell lays the
window panes and the baluster shadows over the steps. Sixteen steps climb to a
landing that leads nowhere: a blank papered wall with the faint, unfaded
outline of a door that is not there any more. Above it all, darkness.

    camera  f = 950, eye 1.6 m at x = 0, horizon y = 700 (vanishing point 912, 700): looking up
    opening the stair hall is seen through a cased opening in the near wall z = 2.9 (x -1.0 .. 1.5, 3.3 m)
    stairs  x = -1.00 .. 0.35, first riser z = 3.4, 16 risers of 0.185 m, goings 0.27 m
    landing Y = 2.96, z = 7.72 .. 8.9; blank wall z = 8.9; stairwell right wall x = 1.5
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

OUT = 'cam4_stairs.jpg'
F, CX, CY, EYE = 950.0, 912.0, 700.0, 1.6
XL, XS, XR = -1.00, 0.35, 1.50           # left wall, banister line (stair edge), stairwell right wall
STZ, RISE, GOING, NSTEP = 3.4, 0.185, 0.27, 16
ZA, XA0, XA1, YA, HA = 2.9, -2.6, 2.6, 3.3, 3.6    # near wall with the cased opening; opening height; hall ceiling
TOPY = RISE * NSTEP                       # landing height 2.96
ZTOP = STZ + GOING * NSTEP                # 8.52 ... landing front edge
ZW = ZTOP + 1.15                          # the blank wall at the top
H_ALL = 6.6                               # stairwell ceiling (lost in darkness)
CEIL0 = 3.0                               # the hall ceiling over the foot of the stairs
CEIL0_Z = 4.55                            # where the hall ceiling ends (the stairwell opens above)
RUN_X = (-0.66, 0.02)                     # the stair runner
WIN = (4.6, 5.9, 1.9, 3.9)                # window on the right wall: z0, z1, Y0, Y1
MOON_DIR = (-0.80, -0.50, -0.12)
NEWEL = (0.30, 3.32)                      # x, z of the newel post
ARCH_SCONCES = ((-1.40, 2.05), (1.90, 2.05))   # x, Y of the sconces on the near wall either side of the opening
ARCH_PAINTINGS = ((-2.45, -1.65, 1.22, 1.86, 'painting_friedrich-moonrise-sea'),
                  (2.13, 2.55, 1.18, 1.90, 'painting_whistler-nocturne-chelsea'))
BAL_PER_TREAD = 2


def step_y(z):
    """height of the tread surface under world z (0 before the stairs, the landing after)."""
    k = np.floor((np.asarray(z) - STZ) / GOING)
    return np.clip((k + 1) * RISE, 0, TOPY) * (np.asarray(z) >= STZ)


def nosing_y(z):
    """the line through the nosings (the pitch line) at z."""
    return np.clip((np.asarray(z) - STZ) / GOING * RISE, 0, TOPY)


def window_aperture(Q):
    z, y = Q[:, 2], Q[:, 1]
    z0, z1, y0, y1 = WIN
    inside = (z > z0 + 0.05) & (z < z1 - 0.05) & (y > y0 + 0.05) & (y < y1 - 0.05)
    zm = (z0 + z1) / 2
    bars = (np.abs(z - zm) < 0.016) | (np.abs(y - (y0 + (y1 - y0) * 0.36)) < 0.022)
    bars |= np.abs(y - (y0 + (y1 - y0) * 0.70)) < 0.012
    # an arched head: the corners above the arch are wall
    ya = y1 - (z1 - z0) / 2
    arch = (y > ya) & (((z - zm) / ((z1 - z0) / 2 - 0.05)) ** 2 + ((y - ya) / (y1 - ya - 0.05)) ** 2 > 1)
    return (inside & ~bars & ~arch).astype(np.float32)


PAPER = {}


def blackthorn():
    if 'b' not in PAPER:
        a = K.f32(K.load('misc_wallpaper-morris-blackthorn'))
        a = K.flatten_light(a, 120)
        t = K.make_seamless(a, px=None, py=487 * 2 if a.shape[0] > 487 * 2 + 60 else None, blend=0.08)
        PAPER['b'] = K.match_albedo(t, sat=0.55, tint=(0.95, 1.0, 0.98), mean=0.27, contrast=1.2)
    return PAPER['b']


def left_wall_painter(b, plane):
    """stair wall: paper above a raking dado that follows the pitch, a wall string along the steps."""
    res = b.res
    K.plaster_band(b, 0.0, H_ALL, name='plaster_aged-worn', size_m=1.8, mean=0.28, sat=0.4, seed=5, soot=0.0)
    K.paper_band(b, 0.0, H_ALL - 0.4, blackthorn(), 0.50, seed=7, key='blackthorn')
    U = b.x0 + (np.arange(b.w) + 0.5) / res               # world z
    Yv = b.y1 - (np.arange(b.h) + 0.5) / res
    ZZ, YY = np.meshgrid(U, Yv)
    base = np.where(ZZ < STZ, 0.0, np.where(ZZ > ZTOP, TOPY, nosing_y(ZZ)))
    rail = base + 0.95
    # dado panelling below the raking rail (dark wood with a raking panel moulding)
    wood = K.wtile(K.wood_tile('wood_dark-varnished', 2.0, res, mean=0.24), b, slice(0, b.h), slice(0, b.w))
    below = smoothstep(rail + 0.004, rail - 0.004, YY)
    rel = (YY - base) / 0.95
    panel = (rel > 0.18) & (rel < 0.82)
    edge = np.abs(rel - 0.18) < 0.012 / 0.95 * 1.0
    edge |= np.abs(rel - 0.82) < 0.012
    sh = np.where(panel, 0.92, 1.05) * np.where(edge, 0.62, 1.0)
    alb = b.alb * (1 - below[..., None]) + wood * sh[..., None] * below[..., None]
    # the raking dado rail and the wall string (a broad board along the nosing line)
    rail_band = np.exp(-((YY - rail) / 0.018) ** 2)
    alb = alb * (1 - 0.5 * rail_band[..., None]) + wood * 1.25 * rail_band[..., None] * 0.5
    string = (YY > base - 0.06) & (YY < base + 0.20)
    alb = np.where(string[..., None], wood * 0.85, alb)
    b.alb[:] = np.clip(alb, 0, 1)
    b.ao *= 1 - 0.35 * np.exp(-np.clip(YY - base, 0, None) / 0.05) * (ZZ >= STZ - 0.3)
    b.ao *= 1 - 0.45 * np.exp(-np.clip(base + 0.20 - YY, 0, None) / 0.02) * string * 0
    # ghost of a door on the stair wall halfway up: a rectangle of less faded paper
    b.ao *= (1 - 0.45 * np.exp(-(H_ALL - YY) / 0.4))


def top_wall_painter(b, plane):
    """the blank wall at the top of the stairs - with the clean outline of a door that is not there."""
    K.plaster_band(b, 0.0, H_ALL, name='plaster_aged-worn', size_m=1.8, mean=0.28, sat=0.4, seed=11, soot=0.0)
    K.paper_band(b, TOPY + 0.9, H_ALL - 0.4, blackthorn(), 0.50, seed=13, key='blackthorn')
    K.paper_band(b, 0.0, TOPY + 0.9, blackthorn(), 0.50, seed=13, key='blackthorn')
    # skirting at the landing
    K.hmoulding_w(b, TOPY, TOPY + 0.16, [.9, 1, .7, .62, .6, .6, .6, .58, .55], mean=0.22, shadow=0.0)
    # the ghost door: the paper where a door and its casing used to be is darker and cleaner, with
    # nail holes where the casing was fixed
    dx0, dx1 = -0.78, 0.06
    X = b.x0 + (np.arange(b.w) + 0.5) / b.res
    Yv = b.y1 - (np.arange(b.h) + 0.5) / b.res
    XX, YY = np.meshgrid(X, Yv)
    inside = (XX > dx0 - 0.11) & (XX < dx1 + 0.11) & (YY > TOPY) & (YY < TOPY + 2.25)
    m = blur(inside.astype(np.float32), 0.012 * b.res)
    b.alb[:] = np.clip(b.alb * (1 + 0.16 * m[..., None]) * (1 + m[..., None] * np.array([0.0, 0.03, 0.05])), 0, 1)
    edge = np.exp(-(np.minimum(np.minimum(np.abs(XX - (dx0 - 0.11)), np.abs(XX - (dx1 + 0.11))),
                               np.abs(YY - (TOPY + 2.25))) / 0.006) ** 2) * inside
    b.alb[:] = b.alb * (1 - 0.35 * edge[..., None])
    Yr = b.y1 - (np.arange(b.h) + 0.5) / b.res
    b.ao *= (1 - 0.45 * np.exp(-(H_ALL - Yr) / 0.4))[:, None]
    b.ao *= (1 - 0.35 * np.exp(-np.clip(Yr - TOPY, 0, None) / 0.06) * (Yr > TOPY - 0.01))[:, None]


def right_wall_painter(b, plane):
    K.plaster_band(b, 0.0, H_ALL, name='plaster_aged-worn', size_m=1.8, mean=0.28, sat=0.4, seed=21, soot=0.0)
    K.paper_band(b, 0.95, H_ALL - 0.4, blackthorn(), 0.50, seed=23, key='blackthorn')
    K.dado_w(b, top=0.95, skirt=0.16, mean=0.24)
    z0, z1, y0, y1 = WIN
    s0, s1 = -z1, -z0
    cw = 0.09
    for a, c in ((s0 - cw, s0), (s1, s1 + cw)):
        ys, xs = b.sl(a, c, y0 - 0.06, y1 + cw)
        if ys.stop - ys.start > 3 and xs.stop - xs.start > 3:
            b.alb[ys, xs] = so.fluted(xs.stop - xs.start, ys.stop - ys.start, 141, flutes=2)
    X = b.x0 + (np.arange(b.w) + 0.5) / b.res
    Yv = b.y1 - (np.arange(b.h) + 0.5) / b.res
    XX, YY = np.meshgrid(X, Yv)
    Q = np.stack([np.full_like(XX, XR), YY, -XX], -1).reshape(-1, 3)
    zm = (z0 + z1) / 2
    ya = y1 - (z1 - z0) / 2
    hole = ((-XX > z0) & (-XX < z1) & (YY > y0) & (YY < y1) &
            ~((YY > ya) & (((-XX - zm) / ((z1 - z0) / 2)) ** 2 + ((YY - ya) / (y1 - ya)) ** 2 > 1)))
    b.alpha[:] = np.where(hole, 0.0, b.alpha)
    _ = Q
    Yr = Yv
    b.ao *= (1 - 0.45 * np.exp(-(H_ALL - Yr) / 0.4))[:, None]
    b.ao *= (1 - 0.35 * np.exp(-Yr / 0.06))[:, None]


def arch_wall_painter(b, plane):
    """the near wall of the stair hall, with the tall cased opening the camera looks through."""
    K.plaster_band(b, 2.45, HA, name='plaster_aged-beige', size_m=1.0, mean=0.34, sat=0.35, seed=31, soot=0.3)
    K.paper_band(b, 0.95, 2.45, blackthorn(), 0.50, seed=33, key='blackthorn')
    K.dado_w(b, top=0.95, skirt=0.16, mean=0.24)
    K.hmoulding_w(b, 2.42, 2.47, [.2, .7, 1, .8, .4, .6, .2], mean=0.30)
    K.hmoulding_w(b, HA - 0.12, HA, [.1, .3, .6, .9, 1, .9, .7, .5, .3, .2], mean=0.32, shadow=0.0)
    for (x0, x1, y0, y1, _) in ARCH_PAINTINGS:
        b.shadow(x0, x1, y0, y1, 0.55, 0.03, dx=0.012, dy=-0.03)
    K.door_on_board(b, XL, XR, YA, seed=37, casing=0.13)
    ys, xs = b.sl(XL, XR, -0.01, YA)
    b.alpha[ys, xs] = 0.0
    Yv = b.y1 - (np.arange(b.h) + 0.5) / b.res
    b.ao *= (1 - 0.45 * np.exp(-(HA - Yv) / 0.12))[:, None]


def near_side_painter(b, plane):
    K.plaster_band(b, 2.45, HA, name='plaster_aged-beige', size_m=1.0, mean=0.34, sat=0.35, seed=41, soot=0.3)
    K.paper_band(b, 0.95, 2.45, blackthorn(), 0.50, seed=43, key='blackthorn')
    K.dado_w(b, top=0.95, skirt=0.16, mean=0.24)
    K.hmoulding_w(b, 2.42, 2.47, [.2, .7, 1, .8, .4, .6, .2], mean=0.30)
    K.hmoulding_w(b, HA - 0.12, HA, [.1, .3, .6, .9, 1, .9, .7, .5, .3, .2], mean=0.32, shadow=0.0)
    U = b.x0 + (np.arange(b.w) + 0.5) / b.res
    zz = np.abs(U)
    b.ao *= (1 - 0.45 * np.exp(-np.maximum(0, ZA - zz) / 0.12))[None, :]


def hall_floor_painter(b, plane):
    K.floor_boards(b, 'floor_old-worn-dark', 3.0, mean=0.27, sat=0.6, tint=(1.0, 0.92, 0.88), seed=3)
    X, _, Z = plane.world(b)
    d = np.minimum(X - XL, XR - X)
    b.ao *= 1 - 0.5 * np.exp(-d / 0.10)
    # under the first step and in the stairwell corner
    b.ao *= 1 - 0.5 * np.exp(-np.abs(Z - STZ) / 0.05) * (X < XS)
    b.ao *= 1 - 0.45 * np.exp(-np.maximum(0, ZW - Z) / 0.15)
    # rug at the foot of the stairs (a worn Spanish carpet end)
    r = K.CACHE.get('footrug')
    if r is None:
        r = K.match_albedo(f32(load('rug_spanish-end-border')), mean=0.25, sat=0.6, tint=(1.0, 0.88, 0.9))
        K.CACHE['footrug'] = r
    rx0, rx1, rz0, rz1 = -0.95, 0.30, 2.6, 4.12
    ys, xs = b.sl(rx0, rx1, rz0, rz1)
    if ys.stop > ys.start and xs.stop > xs.start:
        rr = resize_f(np.ascontiguousarray(np.rot90(r)), xs.stop - xs.start, ys.stop - ys.start, LANCZOS)
        m = rect_mask(rr.shape[1], rr.shape[0], 0, 0, rr.shape[1], rr.shape[0], soft=2)
        b.alb[ys, xs] = rr * m[..., None] + b.alb[ys, xs] * (1 - m[..., None])


def ceil_painter(b, plane):
    K.ceiling_plaster(b, 'plaster_ceiling-textured', 2.0, mean=0.28, seed=27)
    X, _, Z = plane.world(b)
    d = np.minimum(X - XL, XR - X)
    b.ao *= 1 - 0.5 * np.exp(-d / 0.15)


def draw_steps(sc):
    """treads, risers and nosings, with the runner draped over them and brass rods; far steps first."""
    res = 520
    # treads: old varnished oak, its grain running across the stair (not the pale painted 'stair-treads' photo,
    # which read as grey concrete under the moon)
    tread_t = K.wood_tile('wood_dark-varnished', 1.6, res, mean=0.25, sat=0.62, tint=(1.0, 0.84, 0.74))
    # risers: the same old oak (from down here it is the risers you see; chipped white paint read as concrete)
    riser_t = K.wood_tile('wood_dark-varnished', 1.6, res, mean=0.22, sat=0.62, tint=(1.0, 0.84, 0.74), rot=False)
    k = ('stairrun',)
    if k not in K.CACHE:
        r = f32(load('rug_star-ushak'))
        r = np.ascontiguousarray(np.rot90(r))
        K.CACHE[k] = K.match_albedo(r, mean=0.20, sat=0.75, tint=(1.0, 0.80, 0.84))
    run = K.CACHE[k]
    brass = K.mat('metal_brass-brushed', mean=0.45, sat=0.55, tint=(1.0, 0.9, 0.72))
    w_m = XS - XL
    rx0, rx1 = RUN_X[0] - XL, RUN_X[1] - XL
    for i in reversed(range(NSTEP)):
        z = STZ + i * GOING
        y0, y1 = i * RISE, (i + 1) * RISE
        # riser (faces -z)
        wpx, hpx = int(w_m * res), max(6, int(RISE * res))
        t = tile(riser_t, wpx, hpx, seed=100 + i, tone_var=0.10)
        rr = resize_f(run[int(run.shape[0] * ((i * 0.43) % 0.6)):][:int(run.shape[0] * 0.08)],
                      int((rx1 - rx0) * res), hpx, LANCZOS)
        t[:, int(rx0 * res):int(rx0 * res) + rr.shape[1]] = rr * 0.85
        t *= (1 - 0.25 * np.exp(-np.arange(hpx)[:, None, None][::-1] / (0.03 * res)))   # grime at the foot
        ao = np.ones((hpx, wpx), np.float32)
        ao *= (1 - 0.55 * np.exp(-np.arange(hpx)[::-1] / (0.03 * res)))[:, None]      # tread above shades the riser
        ao *= (1 - 0.35 * np.exp(-np.arange(wpx) / (0.06 * res)))[None, :]           # wall corner
        sc.draw_quad([(XL, y1, z), (XS, y1, z), (XS, y0, z), (XL, y0, z)], t, ao=ao, name=f'riser{i}')
        # tread (faces up), with a rounded nosing drawn as a thin front band
        dpx = int((GOING + 0.03) * res)
        t = tile(tread_t, wpx, dpx, seed=200 + i, tone_var=0.12)
        L = K.lum(t)[..., None]
        wear = np.exp(-((np.arange(wpx) / res - (rx0 + rx1) / 2) / 0.45) ** 2)[None, :, None]
        t = t * (1 - 0.15 * wear) + L * 0.15 * wear
        rr = resize_f(run[int(run.shape[0] * ((i * 0.43 + 0.08) % 0.6)):][:int(run.shape[0] * 0.13)],
                      int((rx1 - rx0) * res), dpx, LANCZOS)
        edge = np.clip(np.minimum(np.arange(rr.shape[1]), rr.shape[1] - 1 - np.arange(rr.shape[1])) / 2.0, 0, 1)
        reg = t[:, int(rx0 * res):int(rx0 * res) + rr.shape[1]]
        reg[:] = rr * edge[None, :, None] + reg * (1 - edge[None, :, None])
        ao = np.ones((dpx, wpx), np.float32)
        ao *= (1 - 0.5 * np.exp(-np.arange(dpx) / (0.04 * res)))[:, None]             # the riser behind
        ao *= (1 - 0.35 * np.exp(-np.arange(wpx) / (0.06 * res)))[None, :]
        # the nosing: a lighter rounded lip along the front 3 cm
        nose = np.clip((np.arange(dpx) - (dpx - 0.035 * res)) / (0.01 * res), 0, 1)[:, None, None]
        t = t * (1 + 0.25 * nose)
        sc.draw_quad([(XL, y1, z + GOING), (XS, y1, z + GOING), (XS, y1, z - 0.03), (XL, y1, z - 0.03)],
                     np.clip(t, 0, 1), ao=ao, spec=0.3, gloss=30, name=f'tread{i}')
        # brass stair rod in the angle between this tread and the next riser
        if i < NSTEP - 1:
            rw = int((rx1 - rx0 + 0.08) * res)
            rt = tile(brass, rw, 8, seed=i, scale=0.3) * so.profile_shade(8, [.3, .8, 1, .8, .3])[:, None, None] * 0.7
            zr = z + GOING - 0.012
            sc.draw_quad([(RUN_X[0] - 0.03, y1 + 0.016, zr), (RUN_X[1] + 0.03, y1 + 0.016, zr),
                          (RUN_X[1] + 0.03, y1 + 0.004, zr), (RUN_X[0] - 0.03, y1 + 0.004, zr)], np.clip(rt, 0, 1),
                         spec=0.4, gloss=30, name=f'rod{i}', zwrite=False)


def baluster_tex(wp, hp, face):
    t = so.wood('wood_fine-grain-old', wp, hp, 900, 0.6, rot=True, seed=7, mean=0.30)
    L = K.lum(t)[..., None]
    t = np.clip((1 + 0.35 * (L / max(1e-3, float(L.mean())) - 1)) * np.array([0.62, 0.60, 0.55]), 0, 1)  # old white paint
    a = None
    if face in ('front', 'left', 'right'):
        v = np.linspace(0, 1, hp)[:, None]
        u = np.abs(np.linspace(-1, 1, wp))[None, :]
        # turned profile: a vase low down, rings, a slim upper shaft, square blocks top and bottom
        prof = 0.55 + 0.35 * np.exp(-((v - 0.72) / 0.10) ** 2) + 0.25 * np.exp(-((v - 0.55) / 0.015) ** 2)
        prof = np.where((v < 0.06) | (v > 0.90), 1.0, prof)
        a = np.clip((prof - u) * wp * 0.5, 0, 1)
        t = t * (0.65 + 0.45 * np.sqrt(np.clip(1 - (u / np.maximum(prof, 0.1)) ** 2, 0, 1)))[..., None]
    out = {'tex': np.clip(t, 0, 1), 'spec': 0.35, 'gloss': 30}
    if a is not None:
        out['alpha'] = a
    return out


def balusters(sc, register=True):
    """two turned balusters per tread along the open side, plus the newel post and the sloping handrail."""
    bw = 0.042
    out = []
    for i in range(NSTEP):
        for j in range(BAL_PER_TREAD):
            z = STZ + i * GOING + (j + 0.5) * GOING / BAL_PER_TREAD - bw / 2
            y0 = (i + 1) * RISE
            y1 = nosing_y(z + bw / 2) + 0.90
            out.append(((XS - 0.06, y0, z), (XS - 0.06 + bw, y1, z + bw)))
    if register:
        for k, (a, b) in enumerate(out):
            sc.add_occluder(f'bal{k}', a, b)
        nx, nz = NEWEL
        sc.add_occluder('newel', (nx - 0.07, 0.0, nz - 0.07), (nx + 0.07, 1.15, nz + 0.07))
    return out


def draw_banister(sc, bals):
    for k, (a, b) in reversed(list(enumerate(bals))):
        sc.box(a, b, baluster_tex, res=900, occluder=False, name=f'bal{k}')
    # handrail: a sloping moulded rail over the balusters (its left side and top are seen)
    res = 600
    xr0, xr1 = XS - 0.085, XS + 0.02
    z0, z1 = NEWEL[1], ZTOP
    ya, yb = 0.92 + 0.06, nosing_y(z1) + 0.90
    L = math.hypot(z1 - z0, yb - ya)
    wpx = int(L * res)
    side = so.wood('wood_lacquered-cherry', wpx, 40, res, 1.0, seed=3, mean=0.24, contrast=1.3)
    side *= so.profile_shade(40, [1, .9, .7, .9, 1, .8, .5])[:, None, None]
    top = so.wood('wood_lacquered-cherry', wpx, 30, res, 1.0, seed=4, mean=0.30, contrast=1.3)
    sc.draw_quad([(xr0, ya + 0.065, z0), (xr0, yb + 0.065, z1), (xr0, yb, z1), (xr0, ya, z0)], np.clip(side, 0, 1),
                 spec=0.6, gloss=35, name='rail_side')
    sc.draw_quad([(xr0, ya + 0.065, z0), (xr0, yb + 0.065, z1), (xr1, yb + 0.065, z1), (xr1, ya + 0.065, z0)],
                 np.clip(top, 0, 1), spec=0.6, gloss=35, name='rail_top', cull=True)
    sc.draw_quad([(xr0, ya, z0), (xr1, ya, z0), (xr1, yb, z1), (xr0, yb, z1)], np.clip(top * 0.6, 0, 1),
                 name='rail_under', cull=True)
    # newel post with a ball cap
    nx, nz = NEWEL

    def newel_tex(wp, hp, face):
        t = so.wood('wood_lacquered-cherry', wp, hp, 700, 1.0, rot=True, seed=9, mean=0.26, contrast=1.3)
        if face != 'top':
            v = np.linspace(0, 1, hp)[:, None]
            sh = 1 - 0.45 * (np.exp(-((v - 0.12) / 0.01) ** 2) + np.exp(-((v - 0.85) / 0.01) ** 2))
            inner = (v > 0.2) & (v < 0.8)
            u = np.abs(np.linspace(-1, 1, wp))[None, :]
            sh = sh * np.where(inner & (u < 0.62), 0.85, 1.0) * np.where(inner & (np.abs(u - 0.62) < 0.06), 0.6, 1.0)
            t = t * sh[..., None]
        return {'tex': np.clip(t, 0, 1), 'spec': 0.4, 'gloss': 30}
    sc.box((nx - 0.065, 0.0, nz - 0.065), (nx + 0.065, 1.12, nz + 0.065), newel_tex, res=700, occluder=False,
           name='newel')
    sc.box((nx - 0.08, 1.12, nz - 0.08), (nx + 0.08, 1.17, nz + 0.08), newel_tex, res=700, occluder=False,
           name='newel_cap')


def newel_lamp(sc):
    """a small brass lamp with a frosted globe on the newel post: the warm light at the foot of the stairs."""
    nx, nz = NEWEL
    cam = sc.cam
    res = cam.f / nz * cam.ss
    brass = K.mat('metal_brass-brushed', mean=0.38, sat=0.55, tint=(1.0, 0.9, 0.72))
    w, h = max(4, int(0.05 * res)), max(4, int(0.20 * res))
    t = tile(brass, w, h, seed=5, scale=0.3)
    xs = np.linspace(-1, 1, w)
    t *= (0.55 + 0.6 * np.sqrt(np.clip(1 - xs ** 2, 0, 1)))[None, :, None]
    sc.draw_quad([(nx - 0.025, 1.37, nz), (nx + 0.025, 1.37, nz), (nx + 0.025, 1.17, nz), (nx - 0.025, 1.17, nz)],
                 np.clip(t, 0, 1), spec=0.8, gloss=25, name='lamp_stem')
    r = 0.085
    gw = max(6, int(2 * r * res))
    yy, xx = np.mgrid[0:gw, 0:gw].astype(np.float32)
    d = np.sqrt((xx - gw / 2) ** 2 + (yy - gw / 2) ** 2) / (gw / 2)
    a = np.clip((1 - d) * gw * 0.25, 0, 1)
    em = (0.55 + 0.45 * (1 - d ** 2))[..., None] * np.array([1.0, 0.80, 0.55], np.float32)
    cy = 1.37 + r
    sc.draw_quad([(nx - r, cy + r, nz), (nx + r, cy + r, nz), (nx + r, cy - r, nz), (nx - r, cy - r, nz)],
                 np.zeros((gw, gw, 3), np.float32), alpha=a, emissive=np.clip(em, 0, 1), emit=2.4, lit=False,
                 name='globe')
    return np.array([nx, cy, nz], np.float32)


def window_and_sky(sc):
    z0, z1, y0, y1 = WIN
    Xs = XR + 3.0
    zs0, zs1, ys0, ys1 = 3.0, 20.0, -2.0, 12.0
    res = 50
    w, h = int((zs1 - zs0) * res), int((ys1 - ys0) * res)
    sky = K.night_sky(w, h, moon_c=None, pines=False)
    zz = zs0 + (np.arange(w) + 0.5) / res
    yy = ys1 - (np.arange(h) + 0.5) / res
    ZZ, YY = np.meshgrid(zz, yy)
    gl = np.exp(-(((ZZ - 4.0) / 3.5) ** 2 + ((YY - 8.0) / 4.0) ** 2))
    sky = np.clip(sky + gl[..., None] * K.hexcol('#cfc8ff', False) * 0.30, 0, 1)
    # bare branches against the sky (a dark pine silhouette, reused)
    pines = f32(load('fog_ph-misty-pines'))[150:1350, 200:2000]
    pl = K.lum(pines)
    pl = resize_f(pl, w, int(w * pl.shape[0] / pl.shape[1]), LANCZOS)
    sil = np.clip((0.80 - pl) * 2.0, 0, 1)
    top = int(h * 0.55)
    reg = sky[top:top + pl.shape[0]]
    a = sil[:reg.shape[0]][..., None] * 0.9
    reg[:] = reg * (1 - a) + np.array([0.04, 0.04, 0.08]) * a
    sky[top + pl.shape[0]:] = np.array([0.04, 0.04, 0.08])
    sky = sky[:, ::-1].copy()
    sc.draw_quad([(Xs, ys1, zs1), (Xs, ys1, zs0), (Xs, ys0, zs0), (Xs, ys0, zs1)], sky, lit=False, name='sky')


def window_sash(sc):
    z0, z1, y0, y1 = WIN
    Xg = XR + 0.08
    res = 400
    ww, hh = int((z1 - z0) * res), int((y1 - y0) * res)
    zz = z1 - (np.arange(ww) + 0.5) / res
    yy = y1 - (np.arange(hh) + 0.5) / res
    ZZ, YY = np.meshgrid(zz, yy)
    Q = np.stack([np.full_like(ZZ, Xg), YY, ZZ], -1).reshape(-1, 3)
    a = 1 - window_aperture(Q).reshape(hh, ww)
    a = blur(a, 0.8)
    paint = K.mat('wood_painted-green', mean=0.30, sat=0.30, tint=(0.92, 0.94, 1.0))
    sash = tile(paint, ww, hh, seed=8, scale=1.5 * res / paint.shape[1], tone_var=0.15)
    sc.draw_quad([(Xg, y1, z1), (Xg, y1, z0), (Xg, y0, z0), (Xg, y0, z1)], sash, alpha=a, name='sash')
    plaster = K.mat('plaster_aged-beige', mean=0.38, sat=0.35)
    pt = tile(plaster, 60, 300, seed=3, scale=0.4)
    ya = y1 - (z1 - z0) / 2
    sc.draw_quad([(XR + 0.14, ya, z1), (XR, ya, z1), (XR, y0, z1), (XR + 0.14, y0, z1)], pt, name='reveal')
    sc.draw_quad([(XR + 0.14, y0, z1), (XR, y0, z1), (XR, y0, z0), (XR + 0.14, y0, z0)], pt, name='sill')


def landing(sc):
    """the landing floor at the top, its front fascia over the stairwell."""
    fl = Plane('floor', TOPY, XL, XR, ZTOP - 0.01, ZW, name='landing')

    def lp(b, p):
        K.floor_boards(b, 'floor_old-worn-dark', 3.0, mean=0.27, sat=0.6, tint=(1.0, 0.92, 0.88), seed=5)
        X, _, Z = p.world(b)
        b.ao *= 1 - 0.5 * np.exp(-np.maximum(0, ZW - Z) / 0.1)
    draw_plane(sc, fl, lp, None, max_res=300)
    # under the landing (seen from below over the stairwell): its plaster soffit, so the landing reads as a solid
    # floor with depth, not a plank hanging in the air
    YS = TOPY - 0.25

    def soffit(b, p):
        K.ceiling_plaster(b, 'plaster_ceiling-textured', 2.0, mean=0.24, seed=33, cracks=False)
        Z = p.world(b)[2]
        b.ao *= 1 - 0.55 * np.exp(-np.maximum(0, Z - ZTOP) / 0.12)          # the crease behind the fascia
        b.ao *= 1 - 0.45 * np.exp(-np.maximum(0, ZW - Z) / 0.25)            # and where it meets the wall
    draw_plane(sc, Plane('ceil', YS, XS, XR, ZTOP, ZW, name='soffit'), soffit, None, max_res=300)

    # ... and the wall that closes the space under it (the same paper and dado as the stairwell, in its shadow)
    def under(b, p):
        K.plaster_band(b, 0.0, YS, name='plaster_aged-worn', size_m=1.8, mean=0.28, sat=0.4, seed=17, soot=0.0)
        K.paper_band(b, 0.92, YS, blackthorn(), 0.50, seed=19, key='blackthorn')
        K.dado_w(b, top=0.92, skirt=0.16, seed=21)
        Yr = b.y1 - (np.arange(b.h) + 0.5) / b.res
        b.ao *= 0.8 * (1 - 0.6 * np.exp(-np.clip(YS - Yr, 0, None) / 0.18))[:, None]
        X = b.x0 + (np.arange(b.w) + 0.5) / b.res
        b.ao *= (1 - 0.4 * np.exp(-np.minimum(X - XS, XR - X) / 0.12))[None, :]
    draw_plane(sc, Plane('back', ZTOP + 0.004, XS, XR, 0.0, YS, name='under_landing'), under, None, max_res=320)
    # the landing's edge over the stairwell (x > XS): a fascia board facing the camera, a rounded nosing on top
    # (the landing floor's front edge, catching the moon) and a shadow line under it
    t = so.wood('wood_dark-varnished', 300, 60, 300, 2.0, seed=6, mean=0.24)
    t = t * (1 - 0.35 * np.exp(-np.arange(60)[:, None, None] / 6.0))           # shade under the nosing
    sc.draw_quad([(XS, TOPY, ZTOP), (XR, TOPY, ZTOP), (XR, YS, ZTOP), (XS, YS, ZTOP)], t, name='fascia')
    nz = ZTOP - 0.025
    nt = so.wood('wood_dark-varnished', 300, 10, 300, 2.0, seed=8, mean=0.30) * \
        so.profile_shade(10, [.55, .9, 1.0, .95, .8, .6, .45, .35, .3, .3])[:, None, None]
    sc.draw_quad([(XS, TOPY + 0.03, nz), (XR, TOPY + 0.03, nz), (XR, TOPY - 0.005, nz), (XS, TOPY - 0.005, nz)],
                 np.clip(nt, 0, 1), spec=0.3, gloss=25, name='nosing')


def build_scene():
    cam = K.make_camera(F, CX, CY, EYE)
    sc = ZScene(cam, K.ambient_fn)
    moon = K.MOON
    sc.lights.append(K.XApertureLight(MOON_DIR, moon, power=3.4, plane_x=XR + 0.08, aperture=window_aperture,
                                      shadow_px=1.2, name='moon'))
    zc = (WIN[0] + WIN[1]) / 2
    sc.lights.append(PointLight((XR - 0.3, (WIN[2] + WIN[3]) / 2, zc), moon * np.array([0.9, 0.92, 1.0]), power=2.2,
                                soft=0.7, pattern=lambda d: np.clip(-d[:, 0], 0, 1) ** 1.2, wrap=0.3, shadow_px=None,
                                name='window_glow'))
    nx, nz = NEWEL
    lampP = (nx, 1.37 + 0.085, nz)
    sc.lights.append(PointLight(lampP, K.AMBER, power=2.2, soft=0.25, wrap=0.15, shadow_px=None, name='newel_lamp'))
    sc.lights.append(PointLight((0.0, 2.5, -0.5), moon * np.array([0.85, 0.85, 1.0]), power=1.8, soft=1.5, wrap=0.3,
                                shadow_px=None, name='fill'))
    # a cold glimmer from a skylight somewhere above the landing: just enough to find the blank wall
    sc.lights.append(PointLight((-0.3, 5.2, ZW - 0.9), moon * np.array([0.85, 0.88, 1.0]), power=5.0, soft=1.0,
                                pattern=lambda d: np.clip(-d[:, 1], 0, 1) ** 0.7, wrap=0.2, shadow_px=None,
                                name='skylight'))
    for (ax, ay) in ARCH_SCONCES:
        sc.lights.append(K.sconce_light((ax, ay, ZA - 0.16), +1, power=1.6))
        sc.lights[-1].pattern = lambda d: (0.55 + 0.35 * smoothstep(0.2, 0.8, d[:, 1]) +
                                           0.15 * np.clip(-d[:, 2], -1, 1)).astype(np.float32)
    bals = balusters(sc)
    # back to front: the stair hall first, then the near wall with its opening
    window_and_sky(sc)
    draw_plane(sc, Plane('back', ZW, XL, XR, 0.0, H_ALL), top_wall_painter, None, max_res=320)
    draw_plane(sc, Plane('ceil', H_ALL, XL, XR, ZA, ZW), lambda b, p: K.ceiling_plaster(b, mean=0.22, seed=3),
               None, max_res=150)
    landing(sc)
    draw_plane(sc, Plane('floor', 0.0, XS, XR, ZA, ZTOP), hall_floor_painter, zbreaks(ZA, ZTOP, 1.42), max_res=600)
    draw_plane(sc, Plane('floor', 0.0, XL, XS, ZA, STZ + 0.01, name='foot'), hall_floor_painter, None, max_res=600,
               spec=0.2, gloss=25)
    window_sash(sc)
    draw_plane(sc, Plane('rwall', XR, ZA, ZW, 0.0, H_ALL), right_wall_painter, zbreaks(ZA, ZW, 1.42), max_res=600)
    draw_plane(sc, Plane('lwall', XL, ZA, ZW, 0.0, H_ALL), left_wall_painter, zbreaks(ZA, ZW, 1.42), max_res=600)
    draw_steps(sc)
    draw_banister(sc, bals)
    newel_lamp(sc)
    # the opening's reveals (the near wall's thickness)
    plaster = K.mat('plaster_aged-beige', mean=0.34, sat=0.35)
    pt = tile(plaster, 80, 600, seed=4, scale=0.5)
    sc.draw_quad([(XL, YA, ZA), (XL, YA, ZA + 0.16), (XL, 0, ZA + 0.16), (XL, 0, ZA)], pt, name='rev_l')
    sc.draw_quad([(XL, YA, ZA + 0.16), (XR, YA, ZA + 0.16), (XR, YA, ZA), (XL, YA, ZA)], pt, name='rev_top')
    # the near hall: its ceiling, side walls and the near wall with the opening
    draw_plane(sc, Plane('ceil', HA, XA0, XA1, 0.3, ZA), ceil_painter, zbreaks(0.3, ZA, 1.42), max_res=500)
    draw_plane(sc, Plane('lwall', XA0, 0.3, ZA, 0.0, HA, name='near_l'), near_side_painter, zbreaks(0.3, ZA, 1.42),
               max_res=500)
    draw_plane(sc, Plane('rwall', XA1, 0.3, ZA, 0.0, HA, name='near_r'), near_side_painter, zbreaks(0.3, ZA, 1.42),
               max_res=500)
    draw_plane(sc, Plane('back', ZA, XA0, XA1, 0.0, HA, name='arch_wall'), arch_wall_painter, None, max_res=520)
    for (x0, x1, y0, y1, name) in ARCH_PAINTINGS:
        Zp = ZA - 0.03
        K.framed_painting(sc, [(x0, y1, Zp), (x1, y1, Zp), (x1, y0, Zp), (x0, y0, Zp)], name, x1 - x0, y1 - y0,
                          res=520, frame=0.07, seed=int(abs(x0) * 10))
    for (ax, ay) in ARCH_SCONCES:
        K.sconce_front(sc, ax, ay, ZA, seed=int(ax * 10))
    return sc


def height_dark(sc, y0=3.6, y1=6.2, keep=0.06):
    """the stairwell above the landing sinks into darkness (world height from the depth buffer)."""
    cam = sc.cam
    Hs, Ws = sc.zbuf.shape
    ys = (np.arange(Hs, dtype=np.float32) + 0.5) / cam.ss
    Y = cam.eye - (ys[:, None] - cam.cy) * np.minimum(sc.zbuf, 60.0) / cam.f
    k = smoothstep(y0, y1, Y)
    sc.canvas *= (1 - (1 - keep) * k)[..., None]


def render(seed=41):
    sc = build_scene()
    height_dark(sc, 4.6, 6.6)
    for (ax, ay) in ARCH_SCONCES:
        K.halo(sc, (ax, ay + 0.02, ZA - 0.05), 0.45, 0.16, K.AMBER * np.array([1.0, 0.9, 0.75]))
        K.halo(sc, (ax, ay, ZA - 0.05), 0.12, 0.45, K.AMBER)
    nx, nz = NEWEL
    K.halo(sc, (nx, 1.455, nz), 0.55, 0.22, K.AMBER * np.array([1.0, 0.9, 0.75]))
    K.halo(sc, (nx, 1.455, nz), 0.16, 0.45, K.AMBER)
    lin = sc.downsample()
    moonL = [l for l in sc.lights if l.name == 'moon'][0]
    lin = lin + K.volumetric(sc.cam, sc.depth_out(), moonL, 1.0, ZW, n=40, density=0.010)
    y = K.finish_cam(lin, seed)
    return y, lin, sc


def poses():
    cam = K.make_camera(F, CX, CY, EYE)
    zn = STZ + 3 * GOING + GOING * 0.5
    zm = STZ + 9 * GOING + GOING * 0.5
    zf = ZTOP + 0.55
    return [K.pose_for(cam, -0.33, zn, ground=float(step_y(zn))), K.pose_for(cam, -0.33, zm, ground=float(step_y(zm))),
            K.pose_for(cam, -0.30, zf, ground=TOPY)]


def build(out_path):
    y, _, _ = render()
    save_jpeg(pil(y), out_path, quality=84, max_kb=880)
    return out_path


if __name__ == '__main__':
    import time
    t = time.time()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/cam4.png')
    y, lin, sc = render()
    pil(y).save(out)
    K.overlay(y, sc.cam, poses(), vp=(CX, CY)).save(str(out).replace('.png', '_ov.png'))
    print('saved', out, f'{time.time() - t:.1f}s')
