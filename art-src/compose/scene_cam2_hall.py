"""CAM 2 - THE ENDLESS HALL (1824 x 1026).

A Victorian upstairs hall that does not end: black-and-gold 1880 damask paper
over a raised-panel wainscot, panel doors on both sides every few metres, a
worn red Star Ushak runner down the middle, and a row of small frosted pendant
lamps whose warm pools step away into a violet fog. One door far down on the
right has light under it. Seen from a security camera high on the near wall.

    camera  f = 900, eye 2.3 m, horizon y = 380 (vanishing point 912, 380)
    hall    2.3 m wide (x = -1.15 .. 1.15), 3.1 m high, 70 m long
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import camkit as K
from camkit import Plane, PointLight, ZScene, draw_plane, zbreaks, so  # noqa: F401
from common import blur, edge_ao, f32, hexcol, load, pil, rect_mask, resize_f, save_jpeg, smoothstep

OUT = 'cam2_hall.jpg'
F, CX, CY, EYE = 900.0, 912.0, 350.0, 2.3
HW, CEIL, ZEND = 1.25, 3.1, 70.0
DADO, SKIRT, RAIL = 0.92, 0.16, 2.45
PERIOD = 4.5
LEFT_DOORS = [(3.0 + PERIOD * k, 3.0 + PERIOD * k + 0.92) for k in range(15)]
RIGHT_DOORS = [(5.25 + PERIOD * k, 5.25 + PERIOD * k + 0.92) for k in range(15)]
SCONCES_L = [1.9 + PERIOD * k for k in range(14)]
SCONCES_R = [4.15 + PERIOD * k for k in range(14)]
CLOCK = (HW - 0.34, HW - 0.02, 2.35, 2.82)      # x0, x1, z0, z1 of the tall-case clock against the right wall
SCONCE_Y = 1.95
DOOR_PAINT = [(0.45, 0.41, 0.35), (0.42, 0.38, 0.33), (0.47, 0.42, 0.36)]
FOG0, FOGS = 9.0, 24.0
GLOW_DOOR = 2            # right door index with light under it
AJAR_L, AJAR_R = {1: 0.10, 5: 0.18}, {0: 0.0, 3: 0.12}

PAPER = None


def paper_tile():
    global PAPER
    if PAPER is None:
        t = K.make_seamless(K.f32(K.load('misc_wallpaper-1880-gold-damask')), px=752, py=884, blend=0.08)
        t = K.flatten_light(t, 120)
        PAPER = K.match_albedo(t, sat=0.50, tint=(1.0, 0.96, 0.94), mean=0.30, contrast=1.3)
    return PAPER


REPEAT_W = 0.48 * 752 / 1194        # one pattern repeat is ~30 cm wide


def wall_painter(side):
    doors = LEFT_DOORS if side == 'l' else RIGHT_DOORS
    ajar = AJAR_L if side == 'l' else AJAR_R

    def paint(b, plane):
        K.plaster_band(b, RAIL, CEIL, seed=3, mean=0.27)
        K.paper_band(b, DADO, RAIL, paper_tile(), 0.604, seed=11 if side == 'l' else 13, key='gold',
                     repeat_w=REPEAT_W)
        K.dado_w(b, top=DADO, skirt=SKIRT)
        K.hmoulding_w(b, RAIL - 0.025, RAIL + 0.025, [.2, .7, 1, .8, .4, .6, .2], mean=0.30)
        K.hmoulding_w(b, CEIL - 0.13, CEIL, [.1, .3, .6, .9, 1, .9, .7, .5, .3, .2], mean=0.32, shadow=0.0)
        for i, (z0, z1) in enumerate(doors):
            s0, s1 = (z0, z1) if side == 'l' else (-z1, -z0)
            if s1 + 0.2 < b.x0 or s0 - 0.2 > b.x1:
                continue
            glow = (K.AMBER * 0.0 + np.array([1.0, 0.72, 0.42])) * 0.9 if (side == 'r' and i == GLOW_DOOR) else None
            K.door_on_board(b, s0, s1, 2.15, seed=40 + i * 3 + (0 if side == 'l' else 1), ajar=ajar.get(i, 0.0),
                            mean=0.22 + 0.03 * ((i * 7) % 3), gap_glow=glow, painted=DOOR_PAINT[(i * 5) % 3])
        # corner occlusion with the ceiling and the floor
        Yv = b.y1 - (np.arange(b.h) + 0.5) / b.res
        b.ao *= (1 - 0.45 * np.exp(-(CEIL - Yv) / 0.12) - 0.35 * np.exp(-Yv / 0.06))[:, None]
    return paint


def floor_painter(b, plane):
    K.floor_boards(b, 'floor_dark-varnished', 2.0, mean=0.26, sat=0.6, tint=(1.0, 0.92, 0.88), seed=3)
    K.runner(b, -0.48, 0.48, 'rug_star-ushak', mean=0.28, sat=0.62, tint=(1.0, 0.84, 0.88), repeat_m=2.2, seed=5)
    X, _, Z = plane.world(b)
    d = np.minimum(X + HW, HW - X)
    b.ao *= 1 - 0.55 * np.exp(-d / 0.10)
    # door thresholds: a darker worn patch in front of each door
    for (z0, z1) in LEFT_DOORS:
        b.ao *= 1 - 0.18 * np.exp(-(((Z - (z0 + z1) / 2) / 0.4) ** 2 + ((X + HW) / 0.25) ** 2))
    for (z0, z1) in RIGHT_DOORS:
        b.ao *= 1 - 0.18 * np.exp(-(((Z - (z0 + z1) / 2) / 0.4) ** 2 + ((HW - X) / 0.25) ** 2))


def ceil_painter(b, plane):
    K.ceiling_plaster(b, 'plaster_ceiling-smooth', 3.2, mean=0.28, seed=7)
    X, _, Z = plane.world(b)
    d = np.minimum(X + HW, HW - X)
    b.ao *= 1 - 0.5 * np.exp(-d / 0.15)


def clock_face(w, h, seed=3):
    """the front of a tall-case clock (w x h px for 0.47 x 2.05 m): case, hood with a painted dial,
    trunk door with a glass window and the brass pendulum bob, plinth."""
    import math
    from PIL import Image, ImageDraw
    from common import font
    w_m, h_m = CLOCK[3] - CLOCK[2], 2.05
    rx = w / w_m
    t = so.wood('wood_lacquered-cherry', w, h, rx, 1.0, rot=True, seed=seed, mean=0.25, sat=0.5, contrast=1.3)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    X, Y = (xx + 0.5) / rx, h_m - (yy + 0.5) / (h / h_m)
    # mouldings: hood (top 0.55 m) and plinth (bottom 0.28 m) stand out; trunk recessed
    sh = np.ones((h, w), np.float32)
    for yb in (h_m - 0.58, 0.30):
        sh *= 1 - 0.45 * np.exp(-((Y - yb) / 0.012) ** 2)
        sh *= 1 + 0.25 * np.exp(-((Y - yb - 0.02) / 0.012) ** 2)
    sh *= np.where((Y < h_m - 0.58) & (Y > 0.30) & ((X < 0.05) | (X > w_m - 0.05)), 1.12, 1.0)
    t *= sh[..., None]
    # trunk door with a glass window: dark glass, the pendulum bob glinting
    gx0, gx1, gy0, gy1 = 0.13, w_m - 0.13, 0.75, 1.30
    g = ((X > gx0) & (X < gx1) & (Y > gy0) & (Y < gy1)).astype(np.float32)
    g = blur(g, 1.0)
    glass = np.zeros_like(t) + np.array([0.04, 0.04, 0.05])
    bob = np.exp(-(((X - w_m / 2) / 0.055) ** 2 + ((Y - 0.92) / 0.055) ** 2))
    rod = np.exp(-((X - w_m / 2) / 0.006) ** 2) * (Y > 0.92) * (Y < gy1)
    glass += (bob[..., None] * 0.9 + rod[..., None] * 0.5) * np.array([0.55, 0.42, 0.22])
    t = t * (1 - g[..., None]) + glass * g[..., None]
    # the dial: a cream painted face with roman numerals in a brass bezel
    cx, cy, R = w_m / 2, h_m - 0.30, 0.165
    d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
    pap = K.mat('paper_old-paper-stained', mean=0.62, sat=0.35)
    face = resize_f(pap[200:700, 200:700], w, h) * (1 - 0.35 * (d / R) ** 3)[..., None]
    im = Image.new('L', (w, h), 0)
    dr = ImageDraw.Draw(im)
    fnt = font('IMFellEnglishSC-Regular.ttf', max(6, int(0.045 * rx)))
    num = ['XII', 'I', 'II', 'III', 'IIII', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI']
    for i, n in enumerate(num):
        a = i / 12 * 2 * math.pi
        px, py = cx + math.sin(a) * R * 0.78, cy + math.cos(a) * R * 0.78
        u, v = px * rx, (h_m - py) * (h / h_m)
        dr.text((u, v), n, font=fnt, fill=255, anchor='mm')
    # hands at ten to three... no: at a quarter past three (it never moves)
    for ang, L_, wd in ((3.25 / 12 * 2 * math.pi, R * 0.5, 3), (15 / 60 * 2 * math.pi + 0.4, R * 0.72, 2)):
        u0, v0 = cx * rx, (h_m - cy) * (h / h_m)
        dr.line([(u0, v0), (u0 + math.sin(ang) * L_ * rx, v0 - math.cos(ang) * L_ * rx)], fill=255,
                width=max(1, int(wd * rx / 400)))
    ink = f32(im)
    face = face * (1 - 0.85 * ink[..., None])
    inside = np.clip((R - d) * rx + 0.5, 0, 1)
    ring = np.clip(1 - np.abs(d - R - 0.012) / 0.012, 0, 1)
    t = t * (1 - inside[..., None]) + face * inside[..., None]
    t = t * (1 - ring[..., None]) + np.array([0.50, 0.38, 0.20]) * (0.7 + 0.5 * value_noise_ok(w, h))[..., None] * ring[..., None]
    return np.clip(t, 0, 1)


def hood_face(wp, hp):
    full_h = int(round(hp * 2.05 / 0.58))
    t = clock_face(wp, full_h)
    return t[:hp]


def value_noise_ok(w, h):
    from common import value_noise
    return value_noise(w, h, 12, 5, 2)


def plain_faces(h_m, seed, mean=0.23):
    def f(wp, hp, face):
        t = so.wood('wood_lacquered-cherry', wp, hp, 600, 1.0, rot=(face != 'top'), seed=seed, mean=mean, sat=0.5,
                    contrast=1.3)
        if face != 'top':
            e = rect_mask(wp, hp, 0, 0, wp, hp, soft=max(1.5, min(wp, hp) * 0.04))
            t = t * (0.78 + 0.22 * e)[..., None]
            if h_m > 0.5:                                 # a recessed panel on the trunk
                inner = rect_mask(wp, hp, wp * 0.15, hp * 0.08, wp * 0.85, hp * 0.92, soft=2)
                edge = blur(inner, max(1.0, wp * 0.02))
                g = np.gradient(edge, axis=0) * wp * 0.06
                t = t * np.clip(1 + g[..., None] * 3 - 0.06 * inner[..., None], 0.6, 1.3)
        return {'tex': np.clip(t, 0, 1), 'spec': 0.3, 'gloss': 30}
    return f


def draw_clock(sc):
    """the long-case clock against the right wall: a real one (Poly Haven 'Vintage Grandfather Clock 01', a
    photoscanned model: carved case, brass dial, moon-phase arch), its face turned to the hall, its hands at 3:40."""
    import meshkit as M
    x0, x1, z0, z1 = CLOCK
    m = M.Mesh('vintage_grandfather_clock_01', mean=0.24, sat=0.55, tint=(1.0, 0.92, 0.88))
    P = np.concatenate([p[0] for p in m.prims])
    depth = (P.max(0) - P.min(0))[2] * 2.12 / (P.max(0) - P.min(0))[1]
    inst = m.place((HW - depth / 2 - 0.01, 0.0, (z0 + z1) / 2), yaw=-90, height=2.12)
    M.contact_shadow(sc, inst, strength=0.6, radius=0.10)
    M.draw_mesh(sc, inst, name='clock', spec=0.4)


def draw_clock_boxes(sc):
    """(the old box clock, kept for reference)"""
    x0, x1, z0, z1 = CLOCK

    def faces(wp, hp, face):
        if face == 'left':
            return {'tex': hood_face(wp, hp), 'spec': 0.35, 'gloss': 30}
        t = so.wood('wood_lacquered-cherry', wp, hp, 600, 1.0, rot=(face != 'top'), seed=7, mean=0.22, sat=0.5,
                    contrast=1.3)
        if face == 'front':                       # the side of the case, seen almost square-on
            Y = 2.05 - (np.arange(hp) + 0.5) / hp * 2.05
            sh = np.ones(hp, np.float32)
            for yb in (2.05 - 0.58, 0.30):
                sh *= 1 - 0.45 * np.exp(-((Y - yb) / 0.012) ** 2)
            t = t * sh[:, None, None]
        return {'tex': t, 'spec': 0.3, 'gloss': 30}
    # contact shadow on the floor first, then the case
    sh = edge_ao(1.0, 1.0, 100, rects=[(0.3, 0.3, 0.7, 0.7, 0.8, 0.08)])
    sc.draw_quad([(x0 - 0.15, 0.002, z1 + 0.15), (x1 + 0.0, 0.002, z1 + 0.15), (x1 + 0.0, 0.002, z0 - 0.15),
                  (x0 - 0.15, 0.002, z0 - 0.15)], np.zeros((100, 100, 3), np.float32), alpha=(1 - sh) * 0.9,
                 name='clock_shadow', zwrite=False)
    # three stacked boxes give the case its silhouette: plinth, trunk (narrower), hood (wider), cap
    sc.box((x0 - 0.02, 0.0, z0 - 0.02), (x1, 0.30, z1 + 0.02), plain_faces(0.30, 11), res=700, occluder=False,
           name='plinth')
    sc.box((x0 + 0.015, 0.30, z0 + 0.03), (x1, 1.47, z1 - 0.03), plain_faces(1.17, 12), res=700, occluder=False,
           name='trunk')
    sc.box((x0, 1.47, z0), (x1, 2.05, z1), faces, res=700, occluder=False, name='hood')
    sc.box((x0 - 0.03, 2.05, z0 - 0.03), (x1, 2.12, z1 + 0.03), plain_faces(0.07, 13, mean=0.20), res=700,
           occluder=False, name='cap')


def build_scene():
    cam = K.make_camera(F, CX, CY, EYE)
    sc = ZScene(cam, K.ambient_fn)
    amber = K.AMBER
    for z in SCONCES_L:
        sc.lights.append(K.sconce_light((-HW + 0.16, SCONCE_Y, z), +1, power=2.2))
        sc.lights.append(PointLight((-0.3, 1.5, z), amber, power=0.8, soft=1.0, wrap=0.4, shadow_px=None, name='bounce'))
    for z in SCONCES_R:
        sc.lights.append(K.sconce_light((HW - 0.16, SCONCE_Y, z), -1, power=2.2))
        sc.lights.append(PointLight((0.3, 1.5, z), amber, power=0.8, soft=1.0, wrap=0.4, shadow_px=None, name='bounce'))
    z0, z1 = RIGHT_DOORS[GLOW_DOOR]
    sc.lights.append(PointLight((HW - 0.05, 0.03, (z0 + z1) / 2), amber, power=0.35, soft=0.12,
                                pattern=lambda d: np.clip(-d[:, 0], 0, 1) ** 2, wrap=0.2, shadow_px=None, name='under'))
    # a cool fill from the camera's side (a moonlit window behind us, out of frame)
    sc.lights.append(PointLight((0.0, 2.5, -0.6), K.MOON * np.array([0.85, 0.85, 1.0]), power=1.6, soft=1.5, wrap=0.3,
                                shadow_px=None, name='fill'))
    brk = zbreaks(0.5, ZEND, 1.42)
    draw_plane(sc, Plane('ceil', CEIL, -HW, HW, 1.2, ZEND), ceil_painter, zbreaks(1.2, ZEND, 1.42), max_res=500)
    draw_plane(sc, Plane('floor', 0.0, -HW, HW, 2.0, ZEND), floor_painter, zbreaks(2.0, ZEND, 1.42), max_res=700,
               spec=0.25, gloss=28)
    draw_plane(sc, Plane('lwall', -HW, 0.5, ZEND, 0.0, CEIL), wall_painter('l'), brk, max_res=650)
    draw_plane(sc, Plane('rwall', HW, 0.5, ZEND, 0.0, CEIL), wall_painter('r'), brk, max_res=650)
    # the far end: a dark wall lost in the fog
    end = np.zeros((40, 40, 3), np.float32) + 0.15
    sc.draw_quad([(-HW, CEIL, ZEND), (HW, CEIL, ZEND), (HW, 0, ZEND), (-HW, 0, ZEND)], end, name='end')
    # paintings between the doors (near ones only are worth the pixels)
    for z0, name, side in ((4.55, 'painting_christus-portrait-young-woman', 'l'),
                           (6.75, 'painting_hammershoi-white-doors', 'r'),
                           (9.05, 'painting_friedrich-walk-at-dusk', 'l')):
        wm, hm = 0.62, 0.80
        X = -HW + 0.03 if side == 'l' else HW - 0.03
        Y0 = 1.25
        if side == 'l':
            C = [(X, Y0 + hm, z0), (X, Y0 + hm, z0 + wm), (X, Y0, z0 + wm), (X, Y0, z0)]
        else:
            C = [(X, Y0 + hm, z0 + wm), (X, Y0 + hm, z0), (X, Y0, z0), (X, Y0, z0 + wm)]
        K.framed_painting(sc, C, name, wm, hm, res=420, frame=0.07, seed=int(z0 * 10))
    draw_clock(sc)
    for z in SCONCES_L:
        if z < 55:
            K.sconce(sc, -HW, +1, SCONCE_Y, z, seed=int(z))
    for z in SCONCES_R:
        if z < 55:
            K.sconce(sc, HW, -1, SCONCE_Y, z, seed=int(z))
    return sc


def render(seed=21):
    sc = build_scene()
    fogc = np.array([0.006, 0.0048, 0.014], np.float32)
    K.apply_fog(sc, FOG0, FOGS, fogc)
    # halos round the sconces, fading with the fog
    for zs, x in ((SCONCES_L, -HW + 0.16), (SCONCES_R, HW - 0.16)):
        for z in zs:
            if z < 55:
                T = np.exp(-max(0.0, z - FOG0) / FOGS)
                K.halo(sc, (x, SCONCE_Y + 0.02, z), 0.45, 0.16 * T, K.AMBER * np.array([1.0, 0.9, 0.75]))
                K.halo(sc, (x, SCONCE_Y, z), 0.12, 0.45 * T, K.AMBER)
    lin = sc.downsample()
    y = K.finish_cam(lin, seed)
    return y, lin, sc


def poses():
    cam = K.make_camera(F, CX, CY, EYE)
    return [K.pose_for(cam, 0.05, 4.1), K.pose_for(cam, -0.15, 7.6), K.pose_for(cam, 0.1, 13.5)]


GEOMETRY = dict(vanishing_point=(CX, CY), eye=EYE, f=F,
                floor_line='floor meets the walls along lines to the VP; the runner (x -0.46..0.46 m) runs to the VP')


def build(out_path):
    y, _, _ = render()
    save_jpeg(pil(y), out_path, quality=84, max_kb=880)
    return out_path


if __name__ == '__main__':
    import time
    t = time.time()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/cam2.png')
    y, lin, sc = render()
    pil(y).save(out)
    K.overlay(y, sc.cam, poses(), vp=(CX, CY)).save(str(out).replace('.png', '_ov.png'))
    print('saved', out, f'{time.time() - t:.1f}s')
