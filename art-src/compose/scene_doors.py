"""THE DOORWAYS of the desk room: six 360 x 630 pictures the game paints into the two door boxes.

    door_left_dark.jpg   door_left_lit.jpg   door_left_closed.jpg     (WEST HALL, CAM 5 side)
    door_right_dark.jpg  door_right_lit.jpg  door_right_closed.jpg    (EAST HALL, CAM 6 side)

* closed: a heavy pair of old panelled doors filling the opening, built from real wood photos with
  their mouldings shaded from a height field, lit by the office's own lights (scene_office.make_lights)
  through the office camera, so they sit in the office's carved door frames like the wall around them.
* lit / dark: the hall beyond each doorway. Each hall is seen through its doorway from straight in front
  (a camera with the office's focal length and eye height, its centre shifted to the door), so the hall
  runs away from you and its floor meets the bottom edge at the threshold (office y = 790): a monster
  drawn at doorPose {y: 1.0} stands on the threshold board.
    WEST: dark green Morris 'Blackthorn' paper over the office's raised wainscot, worn dark boards with two
          Star Ushak rugs, a console table, a portrait, side doors; through an archway at the end the hall
          goes on in a real old-house photo (HABS, Blandair) to a moonlit window - cold moonlight on the floor.
    EAST: black-and-gold 1880 paper over dark beadboard, a checkerboard marble floor running on into a real
          photo of a checkerboard corridor (HABS), a tall case clock at the end and a thin warm line of
          lamplight under a side door.
  lit:  a warm amber bulb above your door (on your side) shines through the opening: a pool of light on the
        threshold and floor, the hall falling off into darkness. dark: the same hall with the bulb off -
        only the faint moon / lamplight at the far end and a little of the office's own light on the threshold.
Every picture is graded with grade.finish('door') as a patch of the 2400 x 900 office picture (same edge
darkening, vignette and grain), see scenekit.office_finish.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scene_office as so  # noqa: E402
from common import (Camera, Scene, PointLight, ApertureLight, blur, edge_ao, f32, hexcol, load, lum,  # noqa: E402
                    match_albedo, paste_over, pil, rect_mask, resize_f, save_jpeg, smoothstep, srgb2lin, tile,
                    value_noise, LANCZOS)
from scenekit import (aperture_pattern, draw_lod, ellipse_mask, mean_lum255, night_photo, office_finish,  # noqa: E402
                      panel_door, paper, src, wood_grain)

OUT = 'door_left_dark.jpg'
OUTS = ['door_left_dark.jpg', 'door_left_lit.jpg', 'door_left_closed.jpg',
        'door_right_dark.jpg', 'door_right_lit.jpg', 'door_right_closed.jpg']

F, EYE, SS = so.F, so.EYE, 2
BOX = {'left': so.GEOMETRY['door_left'], 'right': so.GEOMETRY['door_right']}   # (x, y, w, h) office px
DW, DH = 360, 630
ZD = so.ZN                         # the doorway plane (the office's near wall), 4 m
WALL_T = 0.16                      # wall thickness (the jamb reveal)
YC = 2.95                          # hall ceiling
ZX = 10.8                          # the cross wall at the end of the 3-D hall (an archway into the photo)
BULB_POWER, HALL_POWER, SPILL_POWER, BOUNCE_POWER = 80.0, 76.0, 0.60, 10.0
HALL_AMB = np.array(so.AMBIENT, np.float32) * 0.20
# the hall's bulbs are practical lights: warm amber like the desk lamp (LOOK.md), a little paler than the lamp's shade
WARM_BULB = (hexcol('#ffb466') * np.array([1.0, 0.95, 0.86], np.float32) * 0.62 + 0.38).astype(np.float32)

SIDE = {
    'left': dict(vp=0.42, seed=500, name='west'),
    'right': dict(vp=0.58, seed=700, name='east'),
}

GEOMETRY = dict(size=(DW, DH), threshold_y=630, floor_line_y=630, vp=None)


def hall_frame(side):
    """the camera and the doorway / hall extents (local metres: eye at x 0, door plane z 4)."""
    cx = SIDE[side]['vp'] * DW
    cy = so.CY - BOX[side][1]
    cam = Camera(DW, DH, F, cx, cy, EYE, ss=SS)
    xa, xb = -cx / 300.0, (DW - cx) / 300.0           # the door opening (1.2 m)
    hx0, hx1 = xa - 0.20, xb + 0.20                   # the hall (1.6 m wide)
    return cam, xa, xb, hx0, hx1


# ==========================================================================
# wall dressing (boards in the plane of a side wall: board x = depth z, board y = height)
# ==========================================================================
def paper_band(b: so.Board, name, roll, Y0, Y1, seed, mean, sat=0.55, tint=(1, 1, 1), contrast=1.1, py=None,
               px=None, age=1.0):
    t = paper(name, roll, b.res, py=py, px=px, sat=sat, tint=tint, mean=mean, contrast=contrast)
    ys, xs = b.sl(b.x0, b.x1, Y0, Y1)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    rng = np.random.default_rng(seed)
    p = tile(t, ww, hh, seed=seed, offset=(int(rng.integers(0, t.shape[1])), int(rng.integers(0, t.shape[0]))),
             tone_var=0.08, tone_cell=b.res * 0.9)
    X = (np.arange(ww) + 0.5) / b.res
    seam = np.abs((X / roll) % 1.0)
    seam = np.minimum(seam, 1 - seam) * roll * b.res
    p *= (1 - 0.10 * np.exp(-(seam / 1.2) ** 2))[None, :, None]
    if age > 0:
        st = f32(load('plaster_damp-stained'))
        sL = lum(st)
        sL = sL / sL.mean()
        sm = tile(sL[..., None].repeat(3, -1), ww, hh, seed=seed + 5, scale=4.0 * b.res / st.shape[1])[..., 0]
        p *= np.clip(1 - age * 0.45 + age * 0.45 * sm, 0.5, 1.15)[..., None]
        n = value_noise(ww, hh, b.res * 0.7, seed + 9, octaves=3)
        p *= (1 - age * (smoothstep(0.66, 0.72, n) * 0.16 + smoothstep(0.72, 0.9, n) * 0.10))[..., None]
        Yv = Y1 - (np.arange(hh) + 0.5) / b.res
        p *= (1 - 0.2 * smoothstep(Y1 - 0.6, Y1, Yv) - 0.1 * smoothstep(Y0 + 0.35, Y0, Yv))[:, None, None]
        # a peeling seam here and there (the paper lifts and shows paler backing)
        peel = smoothstep(0.86, 0.93, value_noise(ww, hh, b.res * 0.25, seed + 13, octaves=3))
        peel *= np.exp(-(seam / (0.03 * b.res)) ** 2)[None, :] * age
        p = p * (1 - peel[..., None]) + np.array([0.42, 0.40, 0.36]) * peel[..., None]
    b.alb[ys, xs] = np.clip(p, 0, 1)


def dress_wall(b: so.Board, cfg, seed):
    """the wall finish of each hall, matched to its camera room (CAM 5 West Hall / CAM 6 East Hall)."""
    if cfg['name'] == 'west':
        # Morris 'Willow Bough' over the office's raised wainscot, plaster frieze, picture rail
        paper_band(b, 'misc_wallpaper-morris-willow', 0.50, so.DADO_Y, 2.40, seed, mean=0.30, sat=0.62,
                   tint=(0.96, 1.0, 0.92), contrast=1.15)
        so.dado(b, seed=seed + 2)
        so.frieze(b, 2.40, YC, seed=seed + 1)
        so.hmoulding(b, 2.38, 2.425, [.2, .7, 1, .8, .4, .6, .2], seed + 3, mean=0.30)
    else:
        # tall dark raised panelling to shoulder height, peeling damp plaster above
        damp_plaster(b, 1.48, YC, seed)
        tall_wainscot(b, 1.48, seed + 2)
    so.hmoulding(b, YC - 0.11, YC, [.1, .3, .6, .9, 1, .9, .7, .5, .3], seed + 4, mean=0.32, shadow=0.0)


def damp_plaster(b: so.Board, Y0, Y1, seed):
    ys, xs = b.sl(b.x0, b.x1, Y0, Y1)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    base = src('plaster_aged-worn', mean=0.36, sat=0.35, tint=(0.94, 0.96, 1.0))
    t = tile(base, ww, hh, seed=seed, tone_var=0.12, scale=1.8 * b.res / base.shape[1])
    peel = src('plaster_peeling-patches', mean=0.36, sat=0.30, tint=(0.95, 0.96, 1.0))
    pt = tile(peel, ww, hh, seed=seed + 1, scale=1.5 * b.res / peel.shape[1])
    n = value_noise(ww, hh, b.res * 0.9, seed + 2, octaves=3)
    m = smoothstep(0.45, 0.65, n)[..., None]
    t = t * (1 - m) + pt * m
    st = f32(load('plaster_damp-stained'))
    sL = lum(st) / lum(st).mean()
    sm = tile(sL[..., None].repeat(3, -1), ww, hh, seed=seed + 5, scale=4.0 * b.res / st.shape[1])[..., 0]
    t *= np.clip(0.5 + 0.5 * sm, 0.45, 1.15)[..., None]
    Yv = Y1 - (np.arange(hh) + 0.5) / b.res
    t *= (1 - 0.25 * smoothstep(Y1 - 0.5, Y1, Yv))[:, None, None]
    b.alb[ys, xs] = np.clip(t, 0, 1)


def tall_wainscot(b: so.Board, top, seed):
    """three rows of the real raised-panel wainscot (the office's), skirting and a heavy cap rail."""
    res = b.res
    pan = src('panel_wainscot-raised', mean=0.24, sat=0.50, tint=(0.84, 0.90, 0.80))
    ao = f32(load('panel_wainscot-raised_ao'))[..., 0]
    ao = resize_f(ao, pan.shape[1], pan.shape[0])
    rows = pan.shape[0] / 5
    r0, r1 = int(rows * 1 - rows * 0.08), int(rows * 4 + rows * 0.02)
    blk = pan[r0:r1] * (0.55 + 0.45 * ao[r0:r1])[..., None]
    ys, xs = b.sl(b.x0, b.x1, 0.15, top - 0.05)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    s = hh / blk.shape[0]
    rr = resize_f(blk, max(2, int(blk.shape[1] * s)), hh, LANCZOS)
    b.alb[ys, xs] = tile(rr, ww, hh, seed=seed, offset=(int(seed * 37) % rr.shape[1], 0), tone_var=0.08)
    so.hmoulding(b, top - 0.06, top, [0, .6, 1, .9, .5, .7, .3, 0], seed + 1, mean=0.26, shadow=0.5)
    so.hmoulding(b, 0.0, 0.15, [.9, 1, .7, .62, .6, .6, .6, .6, .6, .6, .58, .55], seed + 2, mean=0.20, shadow=0.0)
    b.ao *= 1 - 0.35 * np.exp(-np.clip(b.py(0) - np.arange(b.h), 0, None) / (0.05 * res))[:, None]


def beadboard_dado(b: so.Board, top, seed, tint=(0.62, 0.46, 0.42), mean=0.20):
    t = src('panel_beadboard-painted', mean=mean, sat=0.6, tint=tint, contrast=1.3)
    ys, xs = b.sl(b.x0, b.x1, 0.0, top)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    b.alb[ys, xs] = tile(t, ww, hh, seed=seed, tone_var=0.10, scale=1.8 * b.res / t.shape[1])
    so.hmoulding(b, top - 0.035, top, [0, .6, 1, .9, .5, .7, .3, 0], seed + 1, mean=0.26, shadow=0.45)
    so.hmoulding(b, 0.0, 0.16, [.9, 1, .7, .62, .6, .6, .6, .6, .6, .6, .58, .55], seed + 2, mean=0.20, shadow=0.0)
    b.ao *= 1 - 0.35 * np.exp(-np.clip(b.py(0) - np.arange(b.h), 0, None) / (0.05 * b.res))[:, None]


def hang_painting(b: so.Board, name, X0, X1, Y0, Y1, seed, border=0.07):
    """a gilt-framed old painting hung on the board (with its shadow and a wire to the picture rail)."""
    res = b.res
    w, h = int((X1 - X0) * res), int((Y1 - Y0) * res)
    bp = max(3, int(border * res))
    rgb, hole = so.gilt_frame(w, h, bp, seed, res=res)
    canvas = so.painting(name, w - 2 * bp + 4, h - 2 * bp + 4, seed + 1)
    full = rgb.copy()
    paste_over(full, canvas, np.ones(canvas.shape[:2], np.float32), bp - 2, bp - 2)
    lip = 1 - 0.45 * blur(1 - rect_mask(w, h, bp, bp, w - bp, h - bp), max(1, bp * 0.25))
    full = np.where(hole[..., None] > 0.5, rgb, full * lip[..., None])
    b.shadow(X0, X1, Y0, Y1, 0.55, 0.03, dx=0.01, dy=-0.03)
    so.draw_wire(b, (X0 + (X1 - X0) * 0.2, Y1 - 0.02), ((X0 + X1) / 2, 2.38))
    so.draw_wire(b, (X1 - (X1 - X0) * 0.2, Y1 - 0.02), ((X0 + X1) / 2, 2.38))
    b.put(X0, X1, Y0, Y1, full)


def side_door(b: so.Board, X0, X1, seed, light=(0.3, 0.6, 0.7), wood='wood_dark-varnished', paint=None):
    """a closed panelled door with the office's fluted casing on a side wall board."""
    so.door_trim(b, X0, X1, 2.1, seed=seed)
    w_m = X1 - X0
    alb, ao, _ = panel_door(w_m, 2.1, b.res, leaves=1, seed=seed, wood=wood, light=light, knob='right',
                            rows=[(0.24, 0.80), (0.98, 1.95)], paint=paint)
    ys, xs = b.sl(X0, X1, 0.0, 2.1)
    hh, ww = ys.stop - ys.start, xs.stop - xs.start
    b.alb[ys, xs] = resize_f(alb, ww, hh)
    b.ao[ys, xs] *= resize_f(ao, ww, hh)
    b.alpha[ys, xs] = 1


def wall_board(side, which, hx, seed, cfg):
    """one side wall of a hall as a Board (x = z depth from the doorway to the cross wall)."""
    res = 360
    b = so.Board(ZD + WALL_T - 0.02, ZX + 0.02, 0.0, YC, res)
    dress_wall(b, cfg, seed)
    # dressing
    lt_left = (0.55, 0.45, 0.70)
    if cfg['name'] == 'west':
        if which == 'left':
            hang_painting(b, 'painting_christus-portrait-young-woman', 7.05, 7.60, 1.30, 2.02, seed + 20)
            side_door(b, 8.70, 9.55, seed + 30, light=lt_left)
        else:
            side_door(b, 6.15, 7.05, seed + 40, light=lt_left)
            hang_painting(b, 'painting_whistler-nocturne-chelsea', 8.10, 8.55, 1.35, 1.95, seed + 50)
    else:
        if which == 'left':
            side_door(b, 6.30, 7.20, seed + 60, light=lt_left)
            hang_painting(b, 'painting_friedrich-walk-at-dusk', 8.25, 8.95, 1.35, 1.88, seed + 70)
        else:
            hang_painting(b, 'painting_grimshaw-under-the-moonbeams', 5.75, 6.30, 1.30, 2.02, seed + 80)
            side_door(b, 7.90, 8.80, seed + 90, light=lt_left)
    # creases: floor, ceiling, the far corner
    b.ao *= edge_ao(b.x1 - b.x0, b.y1 - b.y0, res, {'bottom': (0.45, 0.06), 'top': (0.35, 0.10),
                                                   'right': (0.35, 0.10)})[:b.h, :b.w]
    return b


def draw_side_wall(sc, b, X, which):
    if which == 'left':   # faces +x: near end on the left of the texture
        corners = [(X, b.y1, b.x0), (X, b.y1, b.x1), (X, 0.0, b.x1), (X, 0.0, b.x0)]
        alb, ao, al = b.alb, b.ao, b.alpha
    else:                 # faces -x: seen from inside the far end is on the left
        corners = [(X, b.y1, b.x1), (X, b.y1, b.x0), (X, 0.0, b.x0), (X, 0.0, b.x1)]
        alb, ao, al = b.alb[:, ::-1], b.ao[:, ::-1], b.alpha[:, ::-1]
    draw_lod(sc, corners, np.ascontiguousarray(alb), ao=np.ascontiguousarray(ao), axis=1, n=7,
             power=1.7 if which == 'left' else 0.6, name=f'wall_{which}')


# ==========================================================================
# floor, ceiling, rugs, furniture
# ==========================================================================
def floor_texture(cfg, x0, x1, seed):
    res = 420
    z0, z1 = ZD - 0.05, ZX + 0.05
    w, h = int((x1 - x0) * res), int((z1 - z0) * res)
    if cfg['name'] == 'west':
        t = src('floor_old-worn-dark', mean=0.24, sat=0.6, tint=(1.0, 0.93, 0.90))
        t = np.ascontiguousarray(np.rot90(t))                        # boards run away from us
        fl = tile(t, w, h, seed=seed, tone_var=0.12, scale=3.0 * res / t.shape[1])
        # two worn Spanish carpets end to end down the middle (the West Hall's runner), long axis along the hall
        rug = src('rug_spanish-medallions', mean=0.24, sat=0.62, tint=(1.0, 0.90, 0.95))
        rug = np.ascontiguousarray(np.rot90(rug))
        xc = (x0 + x1) / 2
        for (za, zb), sd in (((4.50, 6.70), 1), ((7.05, 9.25), 2)):
            rw, rd = int(0.9 * res), int((zb - za) * res)
            rr = tile(rug, rw, rd, seed=sd, scale=1.4 * res / rug.shape[1])         # at its real size (1.4 m across)
            rr *= (0.8 + 0.3 * value_noise(rw, rd, 150, seed + sd, 3))[..., None]       # wear
            m = rect_mask(rw, rd, 0, 0, rw, rd, soft=2)
            px0, pz0 = int((xc - 0.45 - x0) * res), int((z1 - zb) * res)
            reg = fl[pz0:pz0 + rd, px0:px0 + rw]
            reg[:] = rr[:reg.shape[0], :reg.shape[1]] * m[:reg.shape[0], :reg.shape[1], None] + \
                reg * (1 - m[:reg.shape[0], :reg.shape[1], None])
            # fringes at both ends
            fr = int(0.045 * res)
            xs = np.arange(rw)
            fringe = (np.sin(xs * 1.1) * 0.5 + 0.5)[None, :] * np.ones((fr, 1))
            for fz in (pz0 - fr, pz0 + rd):
                if 0 <= fz < fl.shape[0] - fr:
                    fl[fz:fz + fr, px0:px0 + rw] = fl[fz:fz + fr, px0:px0 + rw] * (1 - 0.7 * fringe[..., None]) + \
                        np.array([0.40, 0.37, 0.33]) * 0.7 * fringe[..., None]
    else:
        # worn herringbone parquet (the East Hall's floor), darkened and dulled
        t = src('floor_herringbone-parquet', mean=0.22, sat=0.55, tint=(1.0, 0.92, 0.88), contrast=1.6)
        fl = tile(t, w, h, seed=seed, tone_var=0.10, scale=3.4 * res / t.shape[1])
        n = value_noise(w, h, 0.6 * res, seed + 3, octaves=3)
        fl *= (0.85 + 0.25 * n)[..., None]                                       # grime and old wax
    return fl, (x0, x1, z0, z1, res)


def draw_floor(sc, cfg, hx0, hx1, xa, xb, seed):
    fl, (x0, x1, z0, z1, res) = floor_texture(cfg, hx0, hx1, seed)
    w_m, d_m = x1 - x0, z1 - z0
    rects = []
    if cfg['name'] == 'west':      # under the console table
        rects.append((0.0, z1 - 6.62, 0.42, z1 - 5.68, 0.55, 0.10))
    else:                          # in front of the clock at the end
        rects.append((w_m - 0.60, 0.0, w_m - 0.08, 0.40, 0.55, 0.10))
    ao = edge_ao(w_m, d_m, 60, {'left': (0.5, 0.07), 'right': (0.5, 0.07), 'top': (0.45, 0.08)}, rects=rects)
    corners = [(x0, 0.0, z1), (x1, 0.0, z1), (x1, 0.0, z0), (x0, 0.0, z0)]
    draw_lod(sc, corners, fl, ao=ao, axis=0, n=7, power=0.55, spec=0.30 if cfg['name'] == 'west' else 0.45,
             gloss=26, name='floor')
    # the threshold: a worn oak saddle across the doorway, a hair proud of the floor
    sad = wood_grain('floor_stair-treads', int((xb - xa) * 700), int(WALL_T * 700), 700, 1.2, along='x', seed=seed + 7,
                     mean=0.30, sat=0.5)
    sad *= (0.8 + 0.25 * np.sin(np.linspace(0, math.pi, sad.shape[0])))[:, None, None]
    sc.draw_quad([(xa, 0.012, ZD + WALL_T), (xb, 0.012, ZD + WALL_T), (xb, 0.012, ZD - 0.03), (xa, 0.012, ZD - 0.03)],
                 sad, spec=0.35, gloss=30, name='saddle',
                 ao=edge_ao(xb - xa, WALL_T + 0.03, 200, {'left': (0.5, 0.03), 'right': (0.5, 0.03)}))
    sc.draw_quad([(xa, 0.012, ZD - 0.03), (xb, 0.012, ZD - 0.03), (xb, 0.0, ZD - 0.03), (xa, 0.0, ZD - 0.03)],
                 sad[:12] * 0.6, name='saddle_front')


def draw_ceiling(sc, hx0, hx1, seed):
    res = 300
    z0, z1 = ZD + WALL_T - 0.02, ZX + 0.02
    c = src('plaster_ceiling-smooth', mean=0.30, sat=0.3, tint=(0.96, 0.95, 1.0))
    w, h = int((hx1 - hx0) * res), int((z1 - z0) * res)
    t = tile(c, w, h, seed=seed, tone_var=0.15, scale=3.2 * res / c.shape[1])
    st = src('plaster_damp-stained', mean=0.3, sat=0.2)
    t *= (0.75 + 0.5 * lum(tile(st, w, h, seed=seed + 1, scale=4 * res / st.shape[1])) / 0.3 * 0.5)[..., None]
    # rows: 0 = far end
    ao = edge_ao(hx1 - hx0, z1 - z0, 60, {'left': (0.55, 0.10), 'right': (0.55, 0.10), 'top': (0.4, 0.1)})
    corners = [(hx0, YC, z1), (hx1, YC, z1), (hx1, YC, z0), (hx0, YC, z0)]
    draw_lod(sc, corners, t, ao=ao, axis=0, n=5, power=0.55, name='ceiling')


def draw_cross_wall(sc, cfg, hx0, hx1, seed, opening):
    """the end wall of the 3-D hall with an open doorway (the hall goes on in the photo beyond)."""
    ox0, ox1 = opening
    res = 260
    b = so.Board(hx0 - 0.02, hx1 + 0.02, 0.0, YC, res)
    dress_wall(b, cfg, seed)
    so.door_trim(b, ox0, ox1, 2.15, seed=seed + 5)
    ys, xs = b.sl(ox0, ox1, -0.01, 2.15)
    b.alpha[ys, xs] = 0
    b.ao *= edge_ao(b.x1 - b.x0, b.y1 - b.y0, res, {'left': (0.5, 0.10), 'right': (0.5, 0.10),
                                                   'top': (0.4, 0.1), 'bottom': (0.45, 0.06)})[:b.h, :b.w]
    sc.draw_quad([(b.x0, b.y1, ZX), (b.x1, b.y1, ZX), (b.x1, 0, ZX), (b.x0, 0, ZX)], b.alb, alpha=b.alpha, ao=b.ao,
                 name='cross_wall')
    # the reveal of that doorway (wall thickness) and its floor
    rv = wood_grain('wood_dark-varnished', 60, 300, 300, 2.0, along='y', seed=seed + 9, mean=0.22)
    for X in (ox0, ox1):
        sc.draw_quad([(X, 2.15, ZX), (X, 2.15, ZX + 0.16), (X, 0, ZX + 0.16), (X, 0, ZX)], rv, name='xrev')
    sc.draw_quad([(ox0, 2.15, ZX + 0.16), (ox1, 2.15, ZX + 0.16), (ox1, 2.15, ZX), (ox0, 2.15, ZX)], rv[:, :40] * 0.7,
                 name='xsoffit')


def draw_backplate(sc, cfg, opening, lit):
    """the hall going on beyond the archway: a real old-house photo turned to night, set in the opening."""
    ox0, ox1 = opening
    Zp = ZX + 0.17
    cam = sc.cam
    if cfg['name'] == 'west':
        # Blandair upstairs hall (HABS): the far end and its window. Crop around its vanishing point.
        crop = (180, 330, 1020, 1560)
        plate = night_photo('hall_habs-blandair-empty-hall', crop=crop, size=(420, 615), base=0.035,
                            hot=0.80, hot_gain=3.2, tint=(0.66, 0.62, 1.0))
        vp_src = ((596 - crop[0]) / (crop[2] - crop[0]), (900 - crop[1]) / (crop[3] - crop[1]))
        # the photo is a narrow hall: about 1.0 m of its width shows across the opening
        width_m = 1.5
    else:
        # Lyndhurst (HABS): gothic doorways nested one behind another, far into the house
        crop = (440, 520, 1000, 1700)
        plate = night_photo('hall_habs-lyndhurst-gothic-enfilade', crop=crop, size=(420, 885), base=0.030,
                            hot=0.82, hot_gain=0.7, tint=(0.70, 0.66, 1.0))
        vp_src = ((757 - crop[0]) / (crop[2] - crop[0]), (990 - crop[1]) / (crop[3] - crop[1]))
        width_m = 1.25
    ph, pw = plate.shape[:2]
    height_m = width_m * ph / pw
    # put the photo's vanishing point on ours (the eye's horizon straight ahead, x = 0)
    Xl = 0.0 - vp_src[0] * width_m
    Yt = EYE + vp_src[1] * height_m
    corners = [(Xl, Yt, Zp), (Xl + width_m, Yt, Zp), (Xl + width_m, Yt - height_m, Zp), (Xl, Yt - height_m, Zp)]
    k = 1.0 if lit else 0.75
    E = 3.0
    sc.draw_quad(corners, np.zeros_like(plate), emissive=lin_to_srgb_safe(plate * k / E), emit=E,
                 lit=False, name='backplate')


def lin_to_srgb_safe(a):
    from common import lin2srgb
    return lin2srgb(np.clip(a, 0, 1))


def furniture(sc, cfg, hx0, hx1, seed):
    if cfg['name'] == 'west':
        # a narrow console table against the left wall
        top_y, x0, x1, z0, z1 = 0.80, hx0, hx0 + 0.38, 5.70, 6.60
        dark = lambda wp, hp, face: wood_grain('wood_lacquered-cherry', wp, hp, 700, 1.0, along='x', seed=seed + 3,
                                               mean=0.24, contrast=1.3)
        sc.box((x0, top_y - 0.035, z0), (x1, top_y, z1), dark, res=700, name='console_top', spec=0.45, gloss=35)
        sc.box((x0, top_y - 0.12, z0 + 0.02), (x1 - 0.02, top_y - 0.035, z1 - 0.02), dark, res=700, name='console_apron')
        for (lx, lz) in ((x1 - 0.06, z0 + 0.03), (x1 - 0.06, z1 - 0.07)):
            sc.box((lx, 0.0, lz), (lx + 0.04, top_y - 0.12, lz + 0.04), dark, res=700, name='console_leg')
        # an old oil lamp (unlit) on it: a glass chimney and a brass font, as a small upright billboard
        lamp_quad(sc, (x0 + 0.20, top_y, 6.15), seed)
    else:
        # a tall case clock at the end, against the cross wall, right of the archway
        x0, x1, z1 = hx1 - 0.58, hx1 - 0.10, ZX
        z0 = z1 - 0.30
        case = lambda wp, hp, face: wood_grain('wood_dark-varnished', wp, hp, 500, 2.0, along='y', seed=seed + 5,
                                               mean=0.24)
        sc.box((x0 + 0.04, 0.0, z0 + 0.02), (x1 - 0.04, 1.62, z1), case, res=500, name='clock_body')
        hood = lambda wp, hp, face: clock_hood(wp, hp, face, seed)
        sc.box((x0, 1.62, z0), (x1, 2.22, z1), hood, res=600, name='clock_hood')
        sc.box((x0 - 0.02, 0.0, z0 - 0.01), (x1 + 0.02, 0.22, z1), case, res=500, name='clock_plinth')


def clock_hood(wp, hp, face, seed):
    t = wood_grain('wood_dark-varnished', wp, hp, 600, 2.0, along='y', seed=seed + 9, mean=0.24)
    if face != 'front':
        return t
    # the dial: a pale painted face with roman-ish ticks and two hands, under a little glass door
    yy, xx = np.mgrid[0:hp, 0:wp].astype(np.float32)
    cx, cy, r = wp / 2, hp * 0.45, wp * 0.36
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    dial = np.clip((r - d) / 1.2, 0, 1)
    paperc = src('paper_offwhite-grain', mean=0.30, sat=0.25, tint=(1.0, 0.95, 0.84))
    pt = tile(paperc, wp, hp, seed=seed, scale=0.4)
    ang = np.arctan2(xx - cx, -(yy - cy))
    ticks = (np.abs(((ang / (2 * math.pi) * 12) + 0.5) % 1 - 0.5) < 0.05) & (d > r * 0.78) & (d < r * 0.93)
    face_t = pt * (1 - 0.8 * ticks[..., None])
    for turns, ln, wd in ((3.0 / 12 + 0.0, 0.5, 0.06), (0.0, 0.78, 0.04)):      # hands at three o'clock
        a = turns * 2 * math.pi
        ux, uy = math.sin(a), -math.cos(a)
        t_ = (xx - cx) * ux + (yy - cy) * uy
        s_ = np.abs((xx - cx) * uy - (yy - cy) * ux)
        hand = (t_ > -r * 0.08) & (t_ < r * ln) & (s_ < r * wd)
        face_t[hand] *= 0.15
    ring = np.clip(1 - np.abs(d - r) / 2.0, 0, 1)
    out = t * (1 - dial[..., None]) + face_t * dial[..., None]
    out = out * (1 - ring[..., None] * 0.5) + np.array([0.5, 0.42, 0.25]) * ring[..., None] * 0.5
    return out


def lamp_quad(sc, base, seed):
    """a small unlit oil lamp standing on the console (brass font, glass chimney), billboard facing us."""
    x, y, z = base
    w, h = 0.13, 0.36
    res = 900
    W, H = int(w * res), int(h * res)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    u = (xx + 0.5) / W - 0.5
    v = 1 - (yy + 0.5) / H                       # 0 at the bottom
    # silhouette: foot, font (a squat bulb), collar, chimney (bulb and neck)
    prof = np.where(v < 0.06, 0.32, np.where(v < 0.12, 0.12, np.where(v < 0.36, 0.40 * np.sqrt(np.clip(1 - ((v - 0.24) / 0.13) ** 2, 0, 1)) + 0.08,
                    np.where(v < 0.42, 0.20, np.where(v < 0.70, 0.26 * np.sqrt(np.clip(1 - ((v - 0.56) / 0.15) ** 2, 0, 1)) + 0.12, 0.12)))))
    a = np.clip((prof - np.abs(u)) * W / 1.5, 0, 1)
    brass = src('metal_brass-brushed', mean=0.42, sat=0.5, tint=(1.0, 0.9, 0.72))
    bt = tile(brass, W, H, seed=seed, scale=0.3)
    glass = np.zeros((H, W, 3), np.float32) + np.array([0.16, 0.17, 0.19])
    isglass = (v >= 0.42)[..., None]
    shade = (0.6 + 0.6 * np.sqrt(np.clip(1 - (u / np.maximum(prof, 1e-3)) ** 2, 0, 1)) - 0.3 * u)[..., None]
    col = np.where(isglass, glass, bt) * shade
    alpha = a * np.where(v >= 0.42, 0.55, 1.0)
    sc.draw_quad([(x - w / 2, y + h, z), (x + w / 2, y + h, z), (x + w / 2, y, z), (x - w / 2, y, z)], np.clip(col, 0, 1),
                 alpha=alpha, spec=0.8, gloss=40, name='oil_lamp')


def jambs(sc, xa, xb, seed):
    """the inside of our own doorway (the wall's thickness): thin strips at the edges of the picture."""
    lin = wood_grain('wood_dark-varnished', 80, 800, 380, 2.0, along='y', seed=seed, mean=0.26)
    for X in (xa, xb):
        sc.draw_quad([(X, 2.1, ZD), (X, 2.1, ZD + WALL_T), (X, 0.0, ZD + WALL_T), (X, 0.0, ZD)], lin,
                     ao=edge_ao(WALL_T, 2.1, 300, {'left': (0.4, 0.02), 'right': (0.5, 0.03)}), name='jamb')
    head = wood_grain('wood_dark-varnished', 500, 80, 380, 2.0, along='x', seed=seed + 1, mean=0.22)
    sc.draw_quad([(xa, 2.1, ZD + WALL_T), (xb, 2.1, ZD + WALL_T), (xb, 2.1, ZD), (xa, 2.1, ZD)], head, name='soffit')


# ==========================================================================
# the hall render
# ==========================================================================
def render_hall(side, lit):
    cfg = SIDE[side]
    seed = cfg['seed']
    cam, xa, xb, hx0, hx1 = hall_frame(side)
    rng_state = so.RNG.bit_generator.state           # the office's shared RNG (dado / paper offsets):
    so.RNG.bit_generator.state = np.random.default_rng((5100 + seed)).bit_generator.state   # same start in any build order
    sc = Scene(cam, lambda P, N: np.broadcast_to(HALL_AMB * (0.82 + 0.18 * np.clip(N[:, 1:2], -1, 1)), P.shape)
               .astype(np.float32))
    # ---- lights
    # the door light: a bare bulb high on our side of the wall, shining through the opening
    bulb = np.array([(xa + xb) / 2 + 0.05, 2.62, ZD - 0.75], np.float32)
    through = aperture_pattern(bulb, xa, xb, 0.0, 2.1, ZD, soft=0.03,
                               cone=lambda d: 0.55 + 0.45 * np.clip(-d[:, 1] * 1.3, 0, 1))
    if lit:
        sc.lights.append(PointLight(bulb, WARM_BULB, BULB_POWER, soft=0.30, pattern=through, wrap=0.15,
                                    shadow_px=2.0, name='bulb'))
        # ... and its twin, the hall's own ceiling bulb just past the doorway (out of sight above the head)
        hb = np.array([(hx0 + hx1) / 2, 2.70, ZD + 0.75], np.float32)
        sc.lights.append(PointLight(hb, WARM_BULB, HALL_POWER, soft=0.22, wrap=0.15, shadow_px=2.0, name='hallbulb',
                                    pattern=lambda d: 0.35 + 0.65 * np.clip(-d[:, 1] + 0.25, 0, 1)))
        # the lit floor throws a little of it back up onto the walls and ceiling
        sc.lights.append(PointLight(((xa + xb) / 2, 0.35, 5.6), WARM_BULB * np.array([1.0, 0.97, 0.95]),
                                    BOUNCE_POWER, soft=1.2, pattern=lambda d: np.clip(d[:, 1] + 0.6, 0, 1),
                                    wrap=0.4, shadow_px=None, name='bounce'))
    spill_pos = np.array([(xa + xb) / 2 + 0.3, 1.5, 2.6], np.float32)
    spill = aperture_pattern(spill_pos, xa, xb, 0.0, 2.1, ZD, soft=0.04)
    sc.lights.append(PointLight(spill_pos, np.array(so.AMBIENT, np.float32) * np.array([1.2, 1.1, 0.9]),
                                SPILL_POWER, soft=0.6, pattern=spill, wrap=0.2, shadow_px=None, name='spill'))
    hc = (hx0 + hx1) / 2
    if cfg['name'] == 'west':
        opening = (hc - 0.50, hc + 0.50)
        moon = hexcol('#cfc8ff')

        def ap(Q):
            x, y = Q[:, 0], Q[:, 1]
            e = np.minimum(np.minimum(x - opening[0], opening[1] - x), np.minimum(y - 0.0, 2.15 - y))
            return np.clip(e / 0.03 + 0.5, 0, 1)
        # the moon from the far window, through the archway, down the hall floor
        sc.lights.append(ApertureLight((0.05, -0.30, -1.0), moon, power=0.9 if lit else 1.0, plane_z=ZX + 0.08,
                                       aperture=ap, shadow_px=3.0, name='moon'))
        sc.lights.append(PointLight((hc, 1.4, ZX + 1.2), moon * 0.8, 0.9, soft=0.8,
                                    pattern=aperture_pattern((hc, 1.4, ZX + 1.2), opening[0], opening[1], 0, 2.15, ZX,
                                                             soft=0.05), wrap=0.3, shadow_px=None, name='moonglow'))
    else:
        opening = (hx0 + 0.12, hx1 - 0.66)
        amber = hexcol('#ffb466') * np.array([1.0, 0.93, 0.80], np.float32)
        # lamplight under the side door on the right wall (z 7.9 .. 8.8): low, warm, a fan on the floor
        # (three small lights along the slit at floor level; wrap lets them graze the floor like real light does)
        for zl in (7.98, 8.35, 8.72):
            sc.lights.append(PointLight((hx1 - 0.01, 0.006, zl), amber, 0.12, soft=0.14, wrap=1.0, shadow_px=None,
                                        pattern=lambda d: np.clip(-d[:, 0] * 1.5, 0, 1) * np.clip(1 - d[:, 1] * 3, 0, 1),
                                        name='under_door'))
        # and a faint cool glow from the photo corridor beyond
        sc.lights.append(PointLight((opening[0] + 0.45, 1.3, ZX + 1.0), hexcol('#cfc8ff') * 0.7, 0.5, soft=0.8,
                                    pattern=aperture_pattern((opening[0] + 0.45, 1.3, ZX + 1.0), opening[0], opening[1],
                                                             0, 2.15, ZX, soft=0.05),
                                    wrap=0.3, shadow_px=None, name='beyond'))
    # occluders
    if cfg['name'] == 'west':
        sc.add_occluder('console', (hx0, 0.68, 5.70), (hx0 + 0.38, 0.80, 6.60))
    # ---- geometry, back to front
    draw_backplate(sc, cfg, opening, lit)
    draw_cross_wall(sc, cfg, hx0, hx1, seed + 1, opening)
    draw_ceiling(sc, hx0, hx1, seed + 2)
    for which, X in (('left', hx0), ('right', hx1)):
        b = wall_board(side, which, X, seed + (11 if which == 'left' else 31), cfg)
        draw_side_wall(sc, b, X, which)
    draw_floor(sc, cfg, hx0, hx1, xa, xb, seed + 3)
    if cfg['name'] == 'east':
        # the lamplight's line itself, under the door, and its fan on the marble
        warm_floor_fan(sc, hx1, 7.92, 8.78)
    furniture(sc, cfg, hx0, hx1, seed + 4)
    jambs(sc, xa, xb, seed + 5)
    so.RNG.bit_generator.state = rng_state
    lin = sc.downsample()
    return lin


def warm_floor_fan(sc, X, z0, z1):
    """the bright slit under a door at the foot of the wall x = X (emissive)."""
    w, h = 200, 6
    em = np.zeros((h, w, 3), np.float32) + np.array([1.0, 0.72, 0.40])
    em *= np.sin(np.linspace(0, math.pi, w))[None, :, None] ** 0.3
    sc.draw_quad([(X - 0.001, 0.016, z1), (X - 0.001, 0.016, z0), (X - 0.001, 0.0, z0), (X - 0.001, 0.0, z1)],
                 np.zeros_like(em), emissive=em, emit=1.6, lit=False, name='door_slit')


# ==========================================================================
# the closed doors
# ==========================================================================
def render_closed(side):
    x, y, w, h = BOX[side]
    cam = Camera(DW, DH, F, so.CX - x, so.CY - y, EYE, ss=SS)       # the office camera, cropped to the box
    sc = Scene(cam, so.ambient_fn)
    so.make_lights(sc)
    X0, X1 = so.X_at(x, ZD), so.X_at(x + w, ZD)
    Ytop = so.Y_at(y, ZD)
    light = (0.62, 0.18, 0.70) if side == 'left' else (-0.62, 0.18, 0.70)
    res = 600
    alb, ao, spec = panel_door(X1 - X0, Ytop, res, leaves=2, seed=900 if side == 'left' else 950, light=light,
                               mean=0.27)
    # a heavy door: a deep shadow line at the head (the frame's stop) and darker toward the floor
    Yv = np.linspace(Ytop, 0, alb.shape[0])[:, None]
    ao = ao * (1 - 0.35 * np.exp(-(Ytop - Yv) / 0.03)) * (1 - 0.18 * smoothstep(0.5, 0.0, Yv))
    sc.draw_quad([(X0, Ytop, ZD + 0.005), (X1, Ytop, ZD + 0.005), (X1, 0.0, ZD + 0.005), (X0, 0.0, ZD + 0.005)], alb,
                 ao=ao, spec=0.35, gloss=30, spec_tint=(1.0, 0.92, 0.85), name='closed_door', direct_ao=0.6)
    lin = sc.downsample()
    lin = lin * (1 - 0.0)
    return lin


# ==========================================================================
def render_all(outdir=None, only=None):
    res = {}
    for side in ('left', 'right'):
        x, y, w, h = BOX[side]
        seed = 31 if side == 'left' else 37
        if only is None or 'closed' in only:
            res[f'door_{side}_closed.jpg'] = office_finish(render_closed(side), x, y, 'door', seed=seed)
        for lit in (False, True):
            if only is None or ('lit' if lit else 'dark') in only:
                lin = render_hall(side, lit)
                res[f'door_{side}_{"lit" if lit else "dark"}.jpg'] = office_finish(lin, x, y, 'door', seed=seed + lit)
    return res


def build(out_path):
    out_dir = Path(out_path).parent
    for name, img in render_all().items():
        save_jpeg(pil(img), out_dir / name, quality=90, max_kb=400)
    return out_path


if __name__ == '__main__':
    import time
    t = time.time()
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/doors')
    only = sys.argv[2].split(',') if len(sys.argv) > 2 else None
    outdir.mkdir(parents=True, exist_ok=True)
    for name, img in render_all(only=only).items():
        pil(img).save(outdir / name.replace('.jpg', '.png'))
        print(name, f'mean {mean_lum255(img):.1f}')
    print(f'{time.time() - t:.1f}s')
