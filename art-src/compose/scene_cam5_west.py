"""CAM 5 - WEST HALL (1824 x 1026): the corridor outside your LEFT door.

A papered Victorian passage: William Morris 'Willow Bough' over a dark raised
wainscot, old paintings in gilt frames along the left wall (Grimshaw's moonlit
lane, Hammershoi's empty rooms, a Whistler nocturne, an oval portrait), a worn
Spanish carpet runner on dark boards, one bare bulb buzzing on its flex. At the
far end a door stands a hand's width open and warm lamplight from the room
beyond spills through the gap as a wedge across the floor.
The camera hangs high near the right-hand wall, so the left wall is seen well.

    camera  f = 860, eye 2.1 m at x = 0, horizon y = 330 (vanishing point 912, 330)
    hall    x = -1.55 .. 0.75 (2.3 m), ceiling 3.0 m, far wall z = 7.0 m
    door    far wall x = -0.32 .. 0.60, 2.15 m, hinged left, open 40 degrees
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

OUT = 'cam5_west.jpg'
F, CX, CY, EYE = 860.0, 912.0, 330.0, 2.1
XL, XR, CEIL, ZB = -1.55, 0.75, 3.0, 7.0
DADO, SKIRT, RAIL = 0.92, 0.16, 2.35
DX0, DX1, DTOP, DANG = -0.32, 0.60, 2.15, 40.0
WALL_T = 0.12
BULB = (-0.40, 2.40, 3.55)
BEYOND_LIGHT = (1.2, 1.0, 8.6)
LEFT_DOOR = (3.25, 4.17)
RIGHT_DOOR = (1.55, 2.47)
PAINTINGS = [  # z0, z1, Y0, Y1, source, oval
    (2.05, 3.05, 1.32, 1.95, 'painting_aivazovsky-moonlit-sea', False),
    (4.62, 5.12, 1.42, 2.06, 'painting_christus-portrait-young-woman', True),
    (5.45, 6.35, 1.30, 1.95, 'painting_hammershoi-four-rooms', False),
]
PAPER = {}


def willow():
    if 'w' not in PAPER:
        a = K.f32(K.load('misc_wallpaper-morris-willow'))
        a = K.flatten_light(a, 120)
        t = K.make_seamless(a, blend=0.10)
        PAPER['w'] = K.match_albedo(t, sat=0.62, tint=(0.96, 1.0, 0.92), mean=0.34, contrast=1.15)
    return PAPER['w']


def free_edge():
    th = math.radians(DANG)
    w = DX1 - DX0
    return DX0 + w * math.cos(th), ZB + w * math.sin(th)


def aperture(Q):
    """the gap between the open leaf and the latch jamb, as seen from the lamp beyond."""
    lx, ly, lz = BEYOND_LIGHT
    fx, fz = free_edge()
    x_cut = lx + (fx - lx) * (lz - ZB) / (lz - fz)
    x, y = Q[:, 0], Q[:, 1]
    inside = np.clip((x - x_cut) / 0.02, 0, 1) * np.clip((DX1 - x) / 0.02, 0, 1) * np.clip((DTOP - y) / 0.02, 0, 1)
    return inside * (y > -0.05)


def wall_common(b, seed, doors=(), side='l'):
    K.plaster_band(b, RAIL, CEIL, name='plaster_aged-beige', size_m=1.0, mean=0.36, sat=0.35, seed=seed, soot=0.30)
    K.paper_band(b, DADO, RAIL, willow(), 0.50, seed=seed, key='willow', age=1.0)
    K.dado_w(b, top=DADO, skirt=SKIRT, mean=0.25)
    K.hmoulding_w(b, RAIL - 0.025, RAIL + 0.025, [.2, .7, 1, .8, .4, .6, .2], mean=0.30)
    K.hmoulding_w(b, CEIL - 0.12, CEIL, [.1, .3, .6, .9, 1, .9, .7, .5, .3, .2], mean=0.34, shadow=0.0)
    for i, (z0, z1) in enumerate(doors):
        s0, s1 = (z0, z1) if side == 'l' else (-z1, -z0)
        K.door_on_board(b, s0, s1, 2.15, seed=seed + 5 + i, mean=0.24, painted=None)
    Yv = b.y1 - (np.arange(b.h) + 0.5) / b.res
    b.ao *= (1 - 0.45 * np.exp(-(CEIL - Yv) / 0.12) - 0.35 * np.exp(-Yv / 0.06))[:, None]


def left_painter(b, plane):
    wall_common(b, 31, [LEFT_DOOR], 'l')
    for (z0, z1, y0, y1, _, oval) in PAINTINGS:
        if oval:
            b.shadow(z0 + 0.03, z1 - 0.03, y0, y1 - 0.02, 0.5, 0.03, dx=0.0, dy=-0.025)
        else:
            b.shadow(z0, z1, y0, y1, 0.55, 0.03, dx=0.0, dy=-0.03)
    # the near end (behind the camera) is darker: the wall turns the corner there
    U = b.x0 + (np.arange(b.w) + 0.5) / b.res
    b.ao *= (1 - 0.25 * smoothstep(1.2, 0.0, U))[None, :]


def right_painter(b, plane):
    wall_common(b, 41, [RIGHT_DOOR], 'r')


def far_painter(b, plane):
    wall_common(b, 51, (), 'b')
    door_hole = (DX0, DX1)
    # casing round the open doorway (painted over the board, the opening itself is a hole)
    K.door_on_board(b, DX0, DX1, DTOP, seed=57, mean=0.24)
    ys, xs = b.sl(DX0, DX1, -0.01, DTOP)
    b.alpha[ys, xs] = 0.0
    b.ao *= edge_ao(b.x1 - b.x0, b.y1 - b.y0, b.res, {'left': (0.45, 0.12), 'right': (0.45, 0.12)})[:b.h, :b.w]


def floor_painter(b, plane):
    K.floor_boards(b, 'floor_old-worn-dark', 3.0, mean=0.27, sat=0.6, tint=(1.0, 0.92, 0.88), seed=3)
    K.runner(b, -0.88, 0.08, 'rug_spanish-medallions', mean=0.25, sat=0.6, tint=(1.0, 0.88, 0.90), repeat_m=1.6,
             seed=9, wear=0.3)
    X, _, Z = plane.world(b)
    d = np.minimum(X - XL, XR - X)
    b.ao *= 1 - 0.55 * np.exp(-d / 0.10)
    b.ao *= 1 - 0.5 * np.exp(-np.maximum(0, ZB - Z) / 0.08)


def ceil_painter(b, plane):
    K.ceiling_plaster(b, 'plaster_ceiling-textured', 2.0, mean=0.30, seed=7)
    X, _, Z = plane.world(b)
    d = np.minimum(X - XL, XR - X)
    b.ao *= 1 - 0.5 * np.exp(-d / 0.15)
    b.ao *= 1 - 0.5 * np.exp(-np.maximum(0, ZB - Z) / 0.15)


def beyond_room(sc):
    """the lamplit room behind the far door: only a sliver of it shows through the gap."""
    z0, z1 = ZB + WALL_T, ZB + 3.2
    fl = Plane('floor', 0.0, -2.0, 2.2, z0, z1, name='beyond_floor')
    draw_plane(sc, fl, lambda b, p: K.floor_boards(b, 'floor_dark-varnished', 2.0, mean=0.30, sat=0.6, seed=4), None,
               max_res=300)
    back = Plane('back', z1, -2.0, 2.2, 0.0, CEIL)

    def bp(b, p):
        K.plaster_band(b, 0.0, CEIL, name='plaster_aged-beige', size_m=1.0, mean=0.45, sat=0.4, seed=8, soot=0.2)
        K.paper_band(b, 0.9, 2.4, willow(), 0.50, seed=60, key='willow')
    draw_plane(sc, back, bp, None, max_res=250)
    rw = Plane('rwall', 2.2, z0, z1, 0.0, CEIL, name='beyond_r')
    draw_plane(sc, rw, lambda b, p: K.plaster_band(b, 0.0, CEIL, name='plaster_aged-beige', size_m=1.0, mean=0.42,
                                                   sat=0.4, seed=9, soot=0.2), None, max_res=250)
    # the reveals of the doorway (the wall's thickness)
    plaster = K.mat('plaster_aged-beige', mean=0.38, sat=0.35, tint=(0.95, 0.95, 1.0))
    t = tile(plaster, 60, 300, seed=2, scale=0.3)
    for X in (DX0, DX1):
        sc.draw_quad([(X, DTOP, ZB), (X, DTOP, ZB + WALL_T), (X, 0, ZB + WALL_T), (X, 0, ZB)],
                     so.wood('wood_dark-varnished', 60, 300, 500, 2.0, rot=True, seed=3, mean=0.26), name='reveal')
    sc.draw_quad([(DX0, DTOP, ZB), (DX1, DTOP, ZB), (DX1, DTOP, ZB + WALL_T), (DX0, DTOP, ZB + WALL_T)],
                 so.wood('wood_dark-varnished', 300, 60, 500, 2.0, seed=4, mean=0.26), name='reveal_top')
    # the leaf, swung into the room
    fx, fz = free_edge()
    zt = ZB + WALL_T * 0.5
    w = DX1 - DX0
    leaf = K.victorian_door(int(w * 420), int(DTOP * 420), paint=None, seed=17, w_m=w, h_m=DTOP, mean=0.24)
    hx = DX0 + 0.01
    sc.draw_quad([(hx, DTOP - 0.005, zt), (fx, DTOP - 0.005, fz + WALL_T * 0.5), (fx, 0.005, fz + WALL_T * 0.5),
                  (hx, 0.005, zt)], leaf, spec=0.25, gloss=25, name='leaf')


def build_scene():
    cam = K.make_camera(F, CX, CY, EYE)
    sc = ZScene(cam, K.ambient_fn)
    amber = K.AMBER
    sc.lights.append(PointLight(BULB, amber * np.array([1.0, 1.0, 0.95]), power=3.6, soft=0.30,
                                pattern=lambda d: (0.6 + 0.6 * np.clip(-d[:, 1], 0, 1)).astype(np.float32), wrap=0.15,
                                shadow_px=None, name='bulb'))
    sc.lights.append(PointLight((BULB[0], 1.2, BULB[2]), amber, power=0.8, soft=1.0, wrap=0.4, shadow_px=None,
                                name='bounce'))
    sc.lights.append(K.PortalLight(BEYOND_LIGHT, amber * np.array([1.0, 0.9, 0.75]), power=55.0, plane_z=ZB,
                                   aperture=aperture, soft=0.3, wrap=0.0, soft_px=2.5, name='beyond'))
    sc.lights.append(PointLight((0.0, 2.4, -0.6), K.MOON * np.array([0.85, 0.85, 1.0]), power=1.3, soft=1.5, wrap=0.3,
                                shadow_px=None, name='fill'))
    beyond_room(sc)
    draw_plane(sc, Plane('back', ZB, XL, XR, 0.0, CEIL), far_painter, None, max_res=450)
    draw_plane(sc, Plane('ceil', CEIL, XL, XR, 0.6, ZB), ceil_painter, zbreaks(0.6, ZB, 1.42), max_res=520)
    draw_plane(sc, Plane('floor', 0.0, XL, XR, 1.8, ZB), floor_painter, zbreaks(1.8, ZB, 1.42), max_res=700,
               spec=0.25, gloss=28)
    draw_plane(sc, Plane('lwall', XL, 0.3, ZB, 0.0, CEIL), left_painter, zbreaks(0.3, ZB, 1.42), max_res=650)
    draw_plane(sc, Plane('rwall', XR, 0.3, ZB, 0.0, CEIL), right_painter, zbreaks(0.3, ZB, 1.42), max_res=650)
    for (z0, z1, y0, y1, name, oval) in PAINTINGS:
        X = XL + 0.03
        C = [(X, y1, z0), (X, y1, z1), (X, y0, z1), (X, y0, z0)]
        K.framed_painting(sc, C, name, z1 - z0, y1 - y0, res=520, frame=0.075, seed=int(z0 * 10), oval=oval)
    K.bare_bulb(sc, BULB[0], BULB[1], BULB[2], CEIL)
    return sc


def render(seed=51):
    sc = build_scene()
    K.halo(sc, BULB, 0.75, 0.20, K.AMBER * np.array([1.0, 0.9, 0.75]))
    K.halo(sc, BULB, 0.20, 0.70, K.AMBER)
    lin = sc.downsample()
    beyond = [l for l in sc.lights if l.name == 'beyond'][0]
    lin = lin + K.volumetric(sc.cam, sc.depth_out(), beyond, 1.0, ZB, n=40, density=0.009)
    y = K.finish_cam(lin, seed)
    return y, lin, sc


def poses():
    cam = K.make_camera(F, CX, CY, EYE)
    return [K.pose_for(cam, -0.35, 3.05), K.pose_for(cam, -0.55, 4.6), K.pose_for(cam, 0.12, 6.35)]


def build(out_path):
    y, _, _ = render()
    save_jpeg(pil(y), out_path, quality=84, max_kb=880)
    return out_path


if __name__ == '__main__':
    import time
    t = time.time()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/cam5.png')
    y, lin, sc = render()
    pil(y).save(out)
    K.overlay(y, sc.cam, poses(), vp=(CX, CY)).save(str(out).replace('.png', '_ov.png'))
    print('saved', out, f'{time.time() - t:.1f}s')
