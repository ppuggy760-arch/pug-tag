"""CAM 7 "YOUR ROOM": cam7_you.jpg (1824 x 1026, the size camera pictures are fitted to).

The desk room of the office picture, the very same 3-D set (scene_office's walls, window, curtains, moon,
alcove and paintings, desk, CRT, lamp, books and papers, the scratched WAKE UP, the same lights), filmed by a
camera hanging in the high corner behind and to the right of your chair (common.PoseCamera). The chair is in
the picture and EMPTY: the game draws you (head and shoulders, lit by the monitor) over it, at youCam.seat.
The doorways are dark. The grade is the shared finish, kind 'cam' (no scanlines / REC / static baked in).

    camera  at (1.9, 2.55, -1.0) m looking at (-0.3, 0.95, 2.9), f = 1250 px
    chair   centred at x 0.30, its back 0.60 m wide at z 1.20..1.30 (you sit at z ~1.45, the desk front is 2.2)
    seat    see GEOMETRY['seat'] (fractions of the picture) - the middle of your head and its size
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scene_office as so  # noqa: E402
from common import (PoseCamera, Scene, PointLight, blur, edge_ao, f32, hexcol, load, lum, match_albedo,  # noqa: E402
                    paste_over, pil, rect_mask, resize_f, save_jpeg, smoothstep, tile, value_noise, LANCZOS)
from grade import finish  # noqa: E402
from scenekit import draw_lod, mean_lum255, relief, src, wood_grain  # noqa: E402

OUT = 'cam7_you.jpg'
W, H, SS = 1824, 1026, 2
POS, LOOK, FOCAL = (1.9, 2.55, -1.0), (-0.3, 0.95, 2.9), 1250.0
HEAD = np.array([0.30, 1.22, 1.45])                     # the middle of your head when you sit in the chair
CHAIR_X, CHAIR_Z0, CHAIR_Z1 = 0.30, 1.20, 1.30           # the chair back
CHAIR_W = 0.60
ROOM_X0, ROOM_X1, ROOM_Z0 = -4.02, 4.02, 0.0
GEOMETRY = {}


def camera():
    return PoseCamera(W, H, FOCAL, W / 2, H / 2, POS, LOOK, ss=SS)


def seat_numbers(cam):
    """where the game should draw you: youCam.seat {x, y, size} (head centre, as fractions of the picture)
    and the height of the chair back's top edge so it sits right under the drawn shoulders."""
    u, v = cam.project(HEAD)
    d = cam.depth(HEAD)
    head_rx_px = FOCAL * 0.085 / d                      # a real head is ~17 cm wide
    k = head_rx_px / 62.0                                # the game's head ellipse is 62k x 78k
    size = k / (1026 / 900)                              # k = seat.size * box.h / H, box.h = 1026 at zoom 1.14
    shoulder_v = v + 300 * k                             # the bottom edge of the drawn shoulders
    # find the chair-back height whose top edge (at z = CHAIR_Z0) lands on that line
    lo, hi = 0.5, 1.3
    for _ in range(40):
        mid = (lo + hi) / 2
        vv = cam.project(np.array([CHAIR_X, mid, CHAIR_Z0]))[1]
        if vv > shoulder_v:
            lo = mid
        else:
            hi = mid
    return dict(x=u / W, y=v / H, size=size, k=k, head_px=(u, v), shoulder_v=shoulder_v, chair_top=lo)


# ==========================================================================
def draw_sky(sc):
    """the night beyond the office window (bigger than the office's own sky, for this slanting view)."""
    Z = so.ZN + 0.6
    X0, X1, Y0, Y1 = -3.4, -0.9, 0.7, 2.7
    s = 300
    w, h = int((X1 - X0) * s), int((Y1 - Y0) * s)
    sky = f32(load('sky_ph-milky-way'))[60:60 + 800, 1000:1000 + 1000]
    sky = resize_f(sky, w, h, LANCZOS)
    Ls = lum(sky)
    stars = np.clip((Ls - 0.42) * 3.0, 0, 1) ** 1.2
    yy = np.linspace(0, 1, h)[:, None, None]
    img = hexcol('#070b22', False) * (1 - yy) + hexcol('#1b1640', False) * yy + stars[..., None] * 0.7
    # the same too-big moon (centre seen from the office camera at office (724, 258) on this plane)
    mx, my = so.X_at(724, Z), so.Y_at(258, Z)
    mc = ((mx - X0) * s, (Y1 - my) * s)
    mr = 76 * Z / so.F * s
    yy2, xx2 = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xx2 - mc[0]) ** 2 + (yy2 - mc[1]) ** 2)
    halo = np.exp(-((d - mr).clip(0) / (mr * 0.35))) * 0.45 + np.exp(-((d - mr).clip(0) / (mr * 1.4))) * 0.22
    img = img + halo[..., None] * hexcol('#cfc8ff', False) * 0.55
    moon = f32(load('moon_nasa-full-moon-photo'))
    ml = lum(moon)
    y3, x3 = np.where(ml > 0.08)
    moon = moon[y3.min():y3.max(), x3.min():x3.max()]
    R = int(mr)
    moon = resize_f(match_albedo(moon, sat=0.1, tint=(0.95, 0.93, 1.0)), 2 * R, 2 * R, LANCZOS)
    g = np.mgrid[0:2 * R, 0:2 * R].astype(np.float32)
    rr = np.sqrt((g[1] - R + .5) ** 2 + (g[0] - R + .5) ** 2)
    mm = np.clip((R - 1.0 - rr) / 1.5, 0, 1)
    paste_over(img, (0.22 + 0.85 * moon) * (1 - 0.25 * (rr / R) ** 4)[..., None], mm, int(mc[0] - R), int(mc[1] - R))
    pines = f32(load('fog_ph-misty-pines'))[150:1350, 200:2000]
    pl = resize_f(lum(pines), w, int(w * 1200 / 1800), LANCZOS)
    top = int(h - pl.shape[0] * 0.55)
    reg = img[top:]
    s2 = np.clip((0.80 - pl[:reg.shape[0]]) * 2.0, 0, 1) * np.clip(np.linspace(-0.2, 1.4, reg.shape[0]), 0, 1)[:, None]
    fog = hexcol('#2a2650', False)
    reg[:] = reg * (1 - s2[..., None] * 0.95) + fog * 0.3 * s2[..., None] * 0.95
    sc.draw_quad([(X0, Y1, Z), (X1, Y1, Z), (X1, Y0, Z), (X0, Y0, Z)], np.clip(img, 0, 1), lit=False, emit=1.0,
                 name='sky')


def draw_floor(sc):
    res = 300
    x0, x1, z0, z1 = ROOM_X0, ROOM_X1, ROOM_Z0, so.ZN + 0.02
    w_m, d_m = x1 - x0, z1 - z0
    fl = so.floor_tex(w_m, d_m, res, seed=43)
    from scenekit import rug_field                                       # (the office's rug, the same knots)
    rx0, rx1, rz0, rz1 = -1.95, 1.95, 2.0, 3.72
    rw, rd = int((rx1 - rx0) * res), int((rz1 - rz0) * res)
    rr = rug_field(rw, rd, res, seed=71)
    m = rect_mask(rw, rd, 0, 0, rw, rd, soft=2)
    px0, pz0 = int((rx0 - x0) * res), int((z1 - rz1) * res)
    reg = fl[pz0:pz0 + rd, px0:px0 + rw]
    reg[:] = rr * m[..., None] + reg * (1 - m[..., None])
    tz = lambda z: z1 - z
    rects = [(-0.80 - x0, tz(2.80), 0.85 - x0, tz(2.20), 0.55, 0.10),                 # under the desk
             (CHAIR_X - 0.33 - x0, tz(1.80), CHAIR_X + 0.33 - x0, tz(1.18), 0.45, 0.10)]  # under the chair
    ao = edge_ao(w_m, d_m, 50, {'top': (0.55, 0.10), 'left': (0.5, 0.10)}, rects=rects)
    draw_lod(sc, [(x0, 0, z1), (x1, 0, z1), (x1, 0, z0), (x0, 0, z0)], fl, ao=ao, axis=0, n=6, power=1.0,
             spec=0.35, gloss=28, name='floor')


def draw_left_wall(sc):
    """the room's left-hand wall (x = -4.02), from the near wall back past the camera: the same paper and dado."""
    res = 300
    b = so.Board(ROOM_Z0, so.ZN + 0.02, 0.0, 2.95, res)
    so.paper_wall(b, so.DADO_Y, so.PICT_Y, seed=521)
    so.frieze(b, so.PICT_Y, 2.95, seed=522)
    so.dado(b, seed=523)
    so.hmoulding(b, so.PICT_Y - 0.02, so.PICT_Y + 0.025, [.2, .7, 1, .8, .4, .6, .2], 524, mean=0.30)
    # an old dark interior by candlelight (Hammershoi) in a gilt frame
    X0, X1, Y0, Y1 = 1.55, 2.45, 1.25, 1.90
    w, h = int((X1 - X0) * res), int((Y1 - Y0) * res)
    bp = int(0.07 * res)
    rgb, hole = so.gilt_frame(w, h, bp, 531, res=res)
    canvas = so.painting('painting_hammershoi-artificial-light', w - 2 * bp + 4, h - 2 * bp + 4, 532)
    full = rgb.copy()
    paste_over(full, canvas, np.ones(canvas.shape[:2], np.float32), bp - 2, bp - 2)
    full = np.where(hole[..., None] > 0.5, rgb, full)
    b.shadow(X0, X1, Y0, Y1, 0.5, 0.03, dx=0.01, dy=-0.03)
    b.put(X0, X1, Y0, Y1, full)
    b.ao *= edge_ao(b.x1 - b.x0, b.y1 - b.y0, res, {'right': (0.5, 0.12), 'bottom': (0.4, 0.06)})[:b.h, :b.w]
    X = ROOM_X0
    draw_lod(sc, [(X, b.y1, b.x0), (X, b.y1, b.x1), (X, 0, b.x1), (X, 0, b.x0)], b.alb, ao=b.ao, axis=1, n=4,
             power=1.0, name='left_wall')


def draw_top_band(sc):
    """the strip of wall above the office picture's top edge (2.65 .. 2.95 m) on the near wall."""
    res = 200
    for (a, c, y0) in ((ROOM_X0, so.XAL, 2.65), (so.XAR, ROOM_X1, 2.65), (so.XAL, so.XAR, so.CEIL)):
        b = so.Board(a, c, y0, 2.95, res)
        so.frieze(b, y0, 2.95, seed=541)
        sc.draw_quad([(a, 2.95, so.ZN), (c, 2.95, so.ZN), (c, y0, so.ZN), (a, y0, so.ZN)], b.alb, name='band')


def draw_desk_extras(sc):
    """the faces of the desk and the CRT that only this camera sees (their right sides and the CRT's top)."""
    res = 600
    side = so.wood('wood_lacquered-cherry', int(0.56 * res), int(0.73 * res), res, 1.0, seed=31, mean=0.26, contrast=1.3)
    sc.draw_quad([(0.79, so.DESK_Y - 0.03, 2.22), (0.79, so.DESK_Y - 0.03, 2.78), (0.79, 0.0, 2.78), (0.79, 0.0, 2.22)],
                 side, ao=edge_ao(0.56, 0.73, 80, {'top': (0.5, 0.05), 'bottom': (0.4, 0.08)}), name='ped_r_side')
    edge = so.wood('wood_lacquered-cherry', int(0.6 * res), int(0.03 * res), res, 1.0, seed=32, mean=0.26)
    sc.draw_quad([(0.85, so.DESK_Y, so.DESK_ZF), (0.85, so.DESK_Y, so.DESK_ZB), (0.85, so.DESK_Y - 0.03, so.DESK_ZB),
                  (0.85, so.DESK_Y - 0.03, so.DESK_ZF)], edge, name='desk_edge_r')
    cab = so.wood('wood_fine-grain-old', int(0.79 * res), int(0.33 * res), res, 0.6, seed=4, mean=0.32, sat=0.7,
                  tint=(1.0, 0.92, 0.84))
    cab *= (1 - 0.3 * (1 - rect_mask(cab.shape[1], cab.shape[0], 0, 0, cab.shape[1], cab.shape[0], soft=8)))[..., None]
    sc.draw_quad([(-0.36, 1.235, 2.78), (0.43, 1.235, 2.78), (0.43, 1.235, 2.45), (-0.36, 1.235, 2.45)], cab,
                 spec=0.3, gloss=25, name='crt_top')
    sc.draw_quad([(0.43, 1.235, 2.45), (0.43, 1.235, 2.78), (0.43, so.DESK_Y, 2.78), (0.43, so.DESK_Y, 2.45)],
                 cab[:, :int(0.33 * res)].transpose(1, 0, 2).copy()[:int(0.475 * res)], name='crt_side')


def alarm_clock_tex(n=256, h_turns=3.0 / 12, m_turns=0.0):
    """the twin-bell alarm clock of the game, painted small (no hands moving here: three o'clock)."""
    im = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = n * 0.30
    cx, cy = n / 2, n * 0.56
    for s in (-1, 1):                                                       # bells and legs
        bx, by = cx + s * r * 0.62, cy - r * 0.80
        d.pieslice([bx - r * 0.42, by - r * 0.42, bx + r * 0.42, by + r * 0.42], 180, 360, fill=(217, 194, 126, 255))
        d.line([cx + s * r * 0.5, cy + r * 0.72, cx + s * r * 0.72, cy + r * 1.05], fill=(42, 12, 16, 255),
               width=int(r * 0.13))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(163, 32, 44, 255), outline=(90, 14, 22, 255), width=int(r * 0.08))
    d.ellipse([cx - r * 0.78, cy - r * 0.78, cx + r * 0.78, cy + r * 0.78], fill=(243, 234, 214, 255))
    for turns, ln, wd in ((h_turns, 0.42, 0.10), (m_turns, 0.62, 0.065)):
        a = turns * 2 * math.pi
        d.line([cx, cy, cx + math.sin(a) * r * ln, cy - math.cos(a) * r * ln], fill=(29, 18, 16, 255), width=int(r * wd))
    a = f32(im)
    return a[..., :3], a[..., 3]


CLOCK_RED = (0.40, 0.12, 0.14)          # the alarm clock's paint: a muted crimson (LOOK.md), not the model's aqua
DESK_CLOCK_POS = None


def clock_mesh():
    """the twin-bell alarm clock: Poly Haven 'Alarm Clock 01' (photoscanned), repainted a muted crimson."""
    import meshkit as M
    return M.Mesh('alarm_clock_01', recolor=M.recolor(CLOCK_RED, where='hue', hue=(0.45, 0.80, 0.74), keep=0.6))


def draw_clock(sc):
    """the alarm clock on the desk (the same spot as in the office picture), a real model, its hands at three."""
    import meshkit as M
    cz = so.F * (so.EYE - so.DESK_Y) / (623 - so.CY)
    cx = so.X_at(1452, cz)
    inst = clock_mesh().place((cx, so.DESK_Y, cz - 0.04), yaw=28, height=0.17)       # (its face to your chair and this camera)
    M.contact_shadow(sc, inst, strength=0.5, radius=0.05, floor_y=so.DESK_Y, y_top=0.02)
    M.draw_mesh(sc, inst, name='alarm_clock', spec=0.5)


def draw_clock_painted(sc):
    rgb, a = alarm_clock_tex()
    cz = so.F * (so.EYE - so.DESK_Y) / (623 - so.CY)
    cx = so.X_at(1452, cz)
    s = 0.20
    sc.draw_quad([(cx - s / 2, so.DESK_Y + s * 0.94, cz - 0.02), (cx + s / 2, so.DESK_Y + s * 0.94, cz - 0.02),
                  (cx + s / 2, so.DESK_Y - s * 0.06, cz - 0.02), (cx - s / 2, so.DESK_Y - s * 0.06, cz - 0.02)],
                 rgb, alpha=a, spec=0.4, gloss=40, name='alarm_clock')


def leather_tufted(w_m, h_m, res, seed, buttons=True):
    """dark buttoned leather (a height field of tufts between buttons, real leather photo on top)."""
    w, h = int(w_m * res), int(h_m * res)
    lea = src('fabric_leather-brown', mean=0.20, sat=0.55, tint=(0.85, 0.82, 0.86))
    t = tile(lea, w, h, seed=seed, tone_var=0.15, scale=0.4 * res / lea.shape[1])
    Hm = np.zeros((h, w), np.float32)
    if buttons:
        X = (np.arange(w, dtype=np.float32) + 0.5) / res
        Y = (np.arange(h, dtype=np.float32) + 0.5) / res
        Xg, Yg = np.meshgrid(X, Y)
        step = 0.13
        # a diamond lattice of buttons
        u = (Xg / step + Yg / step) % 1.0
        v = (Xg / step - Yg / step) % 1.0
        du, dv = np.minimum(u, 1 - u), np.minimum(v, 1 - v)
        Hm = 0.012 * np.sqrt(np.clip(du * dv * 4, 0, 1))
        pits = np.exp(-((du ** 2 + dv ** 2) / 0.003))
        Hm -= 0.006 * pits
        shade, ao = relief(Hm, res, light=(0.4, 0.7, 0.6), strength=1.4, cavity=0.5)
        t = t * shade[..., None] * ao[..., None]
        t *= (1 - 0.5 * pits)[..., None]
    return np.clip(t, 0, 1)


CHAIR_LAYER = (670, 700, 990, 1026)    # the crop saved as cam7_chair.png (x0, y0, x1, y1): the game's CAM7_CHAIR
CHAIR_RGBA = {}
CHAIR_AT = (CHAIR_X, 0.0, 1.55)         # the chair's footprint centre (you sit at z ~1.45, the desk front is 2.2)


def draw_mesh_chair(sc):
    """your chair: a real carved Victorian armchair (Poly Haven 'Arm Chair 01', photoscanned) with dark oxblood
    leather, its back to the camera. Returns the ss mask of the parts nearer the camera than you (its back and
    the ends of its arms), which the game draws over you."""
    import meshkit as M
    m = M.Mesh('ArmChair_01', recolor=M.recolor((0.20, 0.085, 0.07), lo=0.28, hi=0.5, keep=0.6))
    inst = m.place(CHAIR_AT, yaw=180 - 6, height=1.06)
    M.contact_shadow(sc, inst, strength=0.55, radius=0.09)
    lo, hi = inst.bounds()
    sc.add_occluder('chair', lo, hi)
    ys, xs, P = M.draw_mesh(sc, inst, name='chair', spec=0.45, return_px=True)
    occ = np.zeros((sc.cam.H, sc.cam.W), np.float32)
    near = P[:, 2] < HEAD[2] - 0.06
    occ[ys[near], xs[near]] = 1.0
    return occ


def draw_chair(sc, chair_top):
    """a high-backed, buttoned leather desk chair, empty, its back toward the camera."""
    x0, x1 = CHAIR_X - CHAIR_W / 2, CHAIR_X + CHAIR_W / 2
    res = 500
    yb = 0.50
    back_h = chair_top - yb
    lea = leather_tufted(CHAIR_W, back_h, res, 3)
    # the outside back of a chair is plain leather with a line of brass nails round its edge
    plain = leather_tufted(CHAIR_W, back_h, res, 4, buttons=False)
    hh, ww = plain.shape[:2]
    yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
    d_edge = np.minimum(np.minimum(xx, ww - 1 - xx), np.minimum(yy, hh - 1 - yy))
    nails = (np.abs(d_edge - 0.022 * res) < 0.006 * res) & ((((xx + yy) / (0.03 * res)) % 1.0) < 0.45)
    brass = src('metal_brass-brushed', mean=0.45, sat=0.5, tint=(1.0, 0.9, 0.72))
    plain = np.where(nails[..., None], tile(brass, ww, hh, seed=2, scale=0.3), plain)
    plain *= (0.70 + 0.30 * smoothstep(0, 0.05 * res, d_edge))[..., None]               # rounded edges
    plain *= (0.85 + 0.15 * (1 - yy / hh))[..., None]
    def faces(wp, hp, face):
        if face == 'front':
            return {'tex': resize_f(plain, wp, hp), 'spec': 0.35, 'gloss': 22}
        if face == 'top':
            t = leather_tufted(CHAIR_W, 0.10, 400, 5, buttons=False)
            return {'tex': resize_f(t * 1.1, wp, hp), 'spec': 0.4, 'gloss': 22}
        t = leather_tufted(0.1, back_h, 400, 6, buttons=False)
        return {'tex': resize_f(t, wp, hp), 'spec': 0.3, 'gloss': 22}
    # back to front (from this camera): far legs, seat, arms, near legs, and the back last
    wood = lambda wp, hp, face: so.wood('wood_lacquered-cherry', wp, hp, 600, 1.0, seed=9, mean=0.24)
    castor = lambda wp, hp, face: tile(brass, wp, hp, seed=3, scale=0.3)
    legs = [(lx, lz) for lz in (CHAIR_Z1 + 0.44, CHAIR_Z0 + 0.02) for lx in (x0 + 0.02, x1 - 0.06)]
    for lx, lz in legs[:2]:
        sc.box((lx, 0.03, lz), (lx + 0.04, 0.40, lz + 0.04), wood, res=600, name='chair_leg')
        sc.box((lx - 0.005, 0.0, lz - 0.005), (lx + 0.045, 0.03, lz + 0.045), castor, res=600, name='castor')
    seat = lambda wp, hp, face: resize_f(leather_tufted(0.6, 0.6, 300, 7, buttons=False), wp, hp)
    sc.box((x0 - 0.02, 0.40, CHAIR_Z1), (x1 + 0.02, 0.50, CHAIR_Z1 + 0.52), seat, res=300, name='chair_seat')
    for ax in (x0 - 0.05, x1 + 0.0):
        sc.box((ax, 0.50, CHAIR_Z1), (ax + 0.05, 0.68, CHAIR_Z1 + 0.45), wood, res=600, name='chair_arm')
    for lx, lz in legs[2:]:
        sc.box((lx, 0.03, lz), (lx + 0.04, 0.40, lz + 0.04), wood, res=600, name='chair_leg')
        sc.box((lx - 0.005, 0.0, lz - 0.005), (lx + 0.045, 0.03, lz + 0.045), castor, res=600, name='castor')
    sc.box((x0, yb, CHAIR_Z0), (x1, chair_top, CHAIR_Z1), faces, res=400, name='chair_back')


def render(seed=17):
    cam = camera()
    seat = seat_numbers(cam)
    GEOMETRY.update(seat=dict(x=round(seat['x'], 3), y=round(seat['y'], 3), size=round(seat['size'], 3)),
                    head_px=tuple(round(v, 1) for v in seat['head_px']), chair_top_y=round(seat['shoulder_v'], 1))
    rng_state = so.RNG.bit_generator.state           # the office's shared RNG (dado / paper offsets):
    so.RNG.bit_generator.state = np.random.default_rng(5300).bit_generator.state   # same start in any build order
    sc = Scene(cam, so.ambient_fn)
    L = so.make_lights(sc)
    sc.add_occluder('desk_top', (-0.80, so.DESK_Y - 0.03, so.DESK_ZF - 0.02), (0.85, so.DESK_Y, so.DESK_ZB + 0.01))
    sc.add_occluder('crt', (-0.36, so.DESK_Y, 2.45), (0.43, 1.235, 2.78))
    sc.add_occluder('books', (-0.77, so.DESK_Y, 2.26), (-0.60, 0.87, 2.50))
    sc.add_occluder('ped_l', (-0.74, 0.0, 2.22), (-0.30, so.DESK_Y - 0.03, 2.75))
    sc.add_occluder('ped_r', (0.39, 0.0, 2.22), (0.79, so.DESK_Y - 0.03, 2.75))
    sc.add_occluder('lamp', (-0.65, so.DESK_Y, 2.54), (-0.43, 1.17, 2.76))
    draw_sky(sc)
    so.draw_window_box(sc)
    so.draw_alcove(sc)
    draw_floor(sc)
    draw_left_wall(sc)
    so.draw_near_walls(sc)
    draw_top_band(sc)
    so.draw_desk(sc)
    draw_desk_extras(sc)
    so.draw_crt(sc)
    so.draw_lamp(sc, L)
    so.draw_desk_things(sc)
    draw_clock(sc)
    occ = draw_mesh_chair(sc)
    # the lamp's warm haze around its shade, the moon shaft from the window (screen space, from this camera)
    lu, lv = cam.project(np.array([-0.541, 1.12, 2.62]))
    sc.glow(lu, lv, 90, L['amber'] * np.array([1.0, 0.85, 0.65]), 0.10, 1.6)
    sc.glow(lu, lv + 20, 40, L['amber'], 0.22, 2.0)
    so.RNG.bit_generator.state = rng_state
    lin = sc.downsample()
    u = (np.arange(W) + 0.5) / W
    k = 0.18 * (1 - smoothstep(0.0, 0.12, u)) + 0.18 * smoothstep(0.88, 1.0, u)
    lin = lin * ((1 - k) ** 2.0)[None, :, None]
    y = finish(lin, 'cam', seed=seed, return_array=True)
    # the chair's back as a layer of its own (the game draws you, then this over you: you sit IN the chair)
    s_ = cam.ss
    a = occ.reshape(H, s_, W, s_).mean((1, 3))
    x0, y0, x1, y1 = CHAIR_LAYER
    CHAIR_RGBA['img'] = np.concatenate([y[y0:y1, x0:x1], a[y0:y1, x0:x1, None]], -1)
    nz = np.argwhere(a > 0.01)
    GEOMETRY['chair_layer_bbox'] = (int(nz[:, 1].min()), int(nz[:, 0].min()), int(nz[:, 1].max()) + 1, int(nz[:, 0].max()) + 1)
    return y, lin, seat


def build(out_path):
    y, _, _ = render()
    save_jpeg(pil(y), out_path, quality=84, max_kb=880)
    # cam7_chair.png: the chair back over you (RGBA, the same grade and grain as the picture), at CHAIR_LAYER
    rgba = np.clip(CHAIR_RGBA['img'] * 255 + 0.5, 0, 255).astype(np.uint8)
    rgba[rgba[..., 3] == 0, :3] = 0                     # (nothing behind the clear parts: a small file)
    Image.fromarray(rgba, 'RGBA').save(Path(out_path).parent / 'cam7_chair.png', optimize=True)
    bb = GEOMETRY['chair_layer_bbox']
    if bb[0] < CHAIR_LAYER[0] or bb[1] < CHAIR_LAYER[1] or bb[2] > CHAIR_LAYER[2] or bb[3] > CHAIR_LAYER[3]:
        print('WARNING: the chair layer is cut off: its box is', bb, 'but CHAIR_LAYER is', CHAIR_LAYER)
    return out_path


if __name__ == '__main__':
    import time
    t = time.time()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/cam7.png')
    y, lin, seat = render()
    pil(y).save(out)
    print('seat', GEOMETRY, f'mean {mean_lum255(y):.1f}', f'{time.time() - t:.1f}s')
