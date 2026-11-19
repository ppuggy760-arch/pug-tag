"""CAM 3 - THE DROWNED PARLOR (1824 x 1026).

A Victorian parlor standing in still, black water. The carved oak overmantel
(cut from a real photo of an abandoned house) rises out of the flood, flanked
by an old portrait and Aivazovsky's moonlit sea; William Morris 'Pomegranate'
paper is stained by the water that has climbed it; two velvet armchairs sit up
to their cushions in the flood; a dark chandelier hangs over it all. Moonlight
comes through the tall window on the left. The water is a mirror: the whole
room is rendered a second time, reflected in the water plane (only what is
above the water), and composited with Fresnel reflectance, slow ripples, two
spreading drip rings and murk for whatever is under the surface.

    camera  f = 800, eye 2.5 m at x = 0, horizon y = 320 (vanishing point 912, 320)
    room    x = -2.3 .. 2.3, z = 0.3 .. 6.0 (back wall), ceiling 3.4 m
    water   surface Y = 0.40 m (the floor is under it)
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
from common import (blur, edge_ao, f32, load, pil, rect_mask, resize_f, save_jpeg, smoothstep, tile, value_noise,
                    LANCZOS, BILINEAR)

OUT = 'cam3_parlor.jpg'
F, CX, CY, EYE = 800.0, 912.0, 320.0, 2.5
XL, XR, ZBK, CEIL = -2.3, 2.3, 6.0, 3.4
HW = 0.40                                          # water level
DADO, SKIRT, RAIL = 0.95, 0.18, 2.70
MANTEL_W, MANTEL_H = 1.78, 2.88
WIN = (2.55, 3.85, 1.05, 3.0)                      # left wall window z0, z1, Y0, Y1
MOON_DIR = (0.55, -0.22, 0.80)          # moonlight crosses the room and lays the panes on the mantel wall
DOOR_R = (3.4, 4.32)                               # right wall door z range
CHAIRS = [(-1.65, -0.85, 3.25, 4.05), (0.80, 1.60, 3.95, 4.75)]   # x0, x1, z0, z1 (facing the camera)
CHANDELIER = (0.0, 3.6)                            # x, z
DRIPS = [(-0.35, 3.3, 1.0), (1.25, 4.9, 0.6)]     # x, z, age (ring radius scale)
PAINTINGS = [(-1.85, -1.20, 1.35, 2.20, 'painting_christus-portrait-young-woman', True),
             (1.12, 2.02, 1.45, 2.12, 'painting_aivazovsky-moonlit-sea', False)]
PAPER = {}


# ==========================================================================
# the mirror pass: the same scene drawn reflected in the water plane, clipped to what is above the water
# ==========================================================================
class MirrorScene(ZScene):
    def __init__(self, cam, ambient, hw):
        super().__init__(cam, ambient)
        self.hw = hw

    def draw_quad(self, corners, tex, *, alpha=None, **kw):
        C = np.asarray(corners, np.float64)
        Y = C[:, 1]
        if Y.max() <= self.hw + 1e-4:
            return
        if Y.min() < self.hw:
            if alpha is not None:
                ah, aw = np.asarray(alpha).shape[:2]
            else:
                if isinstance(tex, Image.Image):
                    aw, ah = tex.size
                else:
                    ah, aw = np.asarray(tex).shape[:2]
                ah, aw = min(ah, 512), min(aw, 512)
            u = (np.arange(aw) + 0.5) / aw
            v = (np.arange(ah) + 0.5) / ah
            top = (1 - u) * Y[0] + u * Y[1]
            bot = (1 - u) * Y[3] + u * Y[2]
            Yg = (1 - v)[:, None] * top[None, :] + v[:, None] * bot[None, :]
            clip = smoothstep(self.hw - 0.004, self.hw + 0.004, Yg).astype(np.float32)
            alpha = clip if alpha is None else np.asarray(alpha, np.float32) * clip
        C2 = C.copy()
        C2[:, 1] = 2 * self.hw - C[:, 1]
        super().draw_quad(C2, tex, alpha=alpha, **kw)

    def box(self, bmin, bmax, textures, **kw):
        # mirror the box itself (so the right faces are chosen), keep only its part above the water
        x0, y0, z0 = bmin
        x1, y1, z1 = bmax
        if y1 <= self.hw:
            return
        y0 = max(y0, self.hw)
        my0, my1 = 2 * self.hw - y1, 2 * self.hw - y0
        kw = dict(kw)
        kw['occluder'] = False
        sup = super(MirrorScene, self)
        quad = self.draw_quad
        self.draw_quad = lambda corners, tex, **k: sup.draw_quad(corners, tex, **k)    # already mirrored
        try:
            Scene_box(self, (x0, my0, z0), (x1, my1, z1), textures, **kw)
        finally:
            self.draw_quad = quad


def Scene_box(sc, bmin, bmax, textures, **kw):
    from common import Scene
    return Scene.box(sc, bmin, bmax, textures, **kw)


def mirror_light(L, hw):
    import copy
    M = copy.copy(L)
    if isinstance(L, (K.XApertureLight,)) or hasattr(L, 'dir'):
        M.dir = L.dir * np.array([1, -1, 1], np.float32)
        ap = L.aperture
        M.aperture = lambda Q, ap=ap: ap(Q * np.array([1, -1, 1], np.float32) + np.array([0, 2 * hw, 0], np.float32))
    else:
        M.pos = L.pos * np.array([1, -1, 1], np.float32) + np.array([0, 2 * hw, 0], np.float32)
        if L.pattern is not None:
            pat = L.pattern
            M.pattern = lambda d, pat=pat: pat(d * np.array([1, -1, 1], np.float32))
    return M


# ==========================================================================
# materials and painters
# ==========================================================================
def pomegranate():
    if 'p' not in PAPER:
        a = K.flatten_light(K.f32(K.load('wallpaper_morris-pomegranate')), 120)
        t = K.make_seamless(a, blend=0.08)
        PAPER['p'] = K.match_albedo(t, sat=0.60, tint=(0.98, 0.98, 1.0), mean=0.36, contrast=1.0)
    return PAPER['p']


def flood_marks(b, plane):
    """the water climbed the walls: wet dark paper up to a crisp old tide line, green-brown damp above it,
    peeling paper and a rising-damp band from the real photo."""
    Yv = b.y1 - (np.arange(b.h) + 0.5) / b.res
    U = b.x0 + (np.arange(b.w) + 0.5) / b.res
    UU, YY = np.meshgrid(U, Yv)
    n = K.wnoise(UU, YY * 0.3, 0.35, 77, 3)
    tide = 1.12 + 0.10 * (n - 0.5)                       # the old high-water line, a little ragged
    wet = smoothstep(tide + 0.02, tide - 0.06, YY)
    line = np.exp(-((YY - tide) / 0.012) ** 2)
    b.alb *= (1 - 0.42 * wet)[..., None] * (1 + wet[..., None] * np.array([-0.05, 0.02, -0.02]))
    b.alb *= (1 - 0.35 * line)[..., None]
    b.alb[:] = b.alb + (line * 0.06)[..., None] * np.array([0.55, 0.50, 0.38])
    # secondary tide marks
    for k, hgt in enumerate((0.78, 0.92)):
        l2 = np.exp(-((YY - hgt - 0.05 * (K.wnoise(UU, YY * 0, 0.5, 91 + k, 2) - 0.5)) / 0.008) ** 2)
        b.alb *= (1 - 0.18 * l2)[..., None]
    # mould blooms above the tide line
    m = K.wnoise(UU, YY, 0.25, 83, 4)
    bloom = smoothstep(0.62, 0.78, m) * smoothstep(tide + 0.9, tide, YY) * (YY > tide)
    b.alb[:] = b.alb * (1 - 0.35 * bloom[..., None]) + bloom[..., None] * np.array([0.10, 0.12, 0.08]) * 0.35


def wall_common(b, seed, plane):
    K.plaster_band(b, RAIL, CEIL, name='plaster_aged-beige', size_m=1.0, mean=0.36, sat=0.32, seed=seed, soot=0.35)
    K.paper_band(b, DADO, RAIL, pomegranate(), 0.53, seed=seed + 1, key='pomegranate', age=1.1)
    K.dado_w(b, top=DADO, skirt=SKIRT, mean=0.23)
    K.hmoulding_w(b, RAIL - 0.025, RAIL + 0.025, [.2, .7, 1, .8, .4, .6, .2], mean=0.30)
    K.hmoulding_w(b, CEIL - 0.16, CEIL, [.1, .3, .6, .9, 1, .9, .7, .5, .3, .2, .1], mean=0.34, shadow=0.0)
    flood_marks(b, plane)
    Yv = b.y1 - (np.arange(b.h) + 0.5) / b.res
    b.ao *= (1 - 0.45 * np.exp(-(CEIL - Yv) / 0.14))[:, None]


def back_painter(b, plane):
    wall_common(b, 11, plane)
    b.shadow(-MANTEL_W / 2, MANTEL_W / 2, 0.0, MANTEL_H, 0.55, 0.06, dx=0.0, dy=-0.02)
    for (x0, x1, y0, y1, _, oval) in PAINTINGS:
        if oval:
            b.shadow(x0 + 0.03, x1 - 0.03, y0, y1 - 0.02, 0.5, 0.03, dy=-0.025)
        else:
            b.shadow(x0, x1, y0, y1, 0.55, 0.03, dx=0.01, dy=-0.03)
    b.ao *= edge_ao(b.x1 - b.x0, b.y1 - b.y0, b.res, {'left': (0.45, 0.14), 'right': (0.45, 0.14)})[:b.h, :b.w]


def left_painter(b, plane):
    wall_common(b, 21, plane)
    z0, z1, y0, y1 = WIN
    cw = 0.10
    for a, c in ((z0 - cw, z0), (z1, z1 + cw)):
        ys, xs = b.sl(a, c, y0 - 0.06, y1 + cw)
        if ys.stop - ys.start > 3 and xs.stop - xs.start > 3:
            b.alb[ys, xs] = so.fluted(xs.stop - xs.start, ys.stop - ys.start, 141, flutes=2)
        b.shadow(a, c, y0 - 0.06, y1 + cw, 0.4, 0.015, dy=-0.004)
    ys, xs = b.sl(z0, z1, y1, y1 + cw)
    if ys.stop - ys.start > 3 and xs.stop - xs.start > 3:
        b.alb[ys, xs] = so.fluted(xs.stop - xs.start, ys.stop - ys.start, 143, vertical=False, flutes=2)
    ys, xs = b.sl(z0, z1, y0, y1)
    b.alpha[ys, xs] = 0.0
    U = b.x0 + (np.arange(b.w) + 0.5) / b.res
    b.ao *= (1 - 0.3 * smoothstep(1.2, 0.0, U))[None, :]


def right_painter(b, plane):
    wall_common(b, 31, plane)
    s0, s1 = -DOOR_R[1], -DOOR_R[0]
    K.door_on_board(b, s0, s1, 2.25, seed=35, mean=0.22)


def ceil_painter(b, plane):
    K.ceiling_plaster(b, 'plaster_ceiling-textured', 2.0, mean=0.30, seed=5)
    X, _, Z = plane.world(b)
    d = np.minimum(X - XL, XR - X)
    b.ao *= 1 - 0.5 * np.exp(-d / 0.18)
    b.ao *= 1 - 0.5 * np.exp(-np.maximum(0, ZBK - Z) / 0.18)
    # water stains spreading from the drips
    for (dx, dz, _) in DRIPS:
        r = np.sqrt((X - dx) ** 2 + (Z - dz) ** 2)
        n = K.wnoise(X, Z, 0.25, int(dx * 10 + 50), 3)
        st = smoothstep(0.55, 0.35, r + 0.25 * (n - 0.5))
        ring = np.exp(-((r + 0.25 * (n - 0.5) - 0.48) / 0.015) ** 2)
        b.alb[:] = b.alb * (1 - 0.12 * st[..., None]) * (1 - 0.2 * ring[..., None])


def floor_painter(b, plane):
    """the drowned floor (only seen through the water): parquet, silt."""
    t = K.mat('floor_herringbone-parquet', mean=0.22, sat=0.5, tint=(0.9, 0.95, 0.9))
    tt = K.at_res(('herringP',), t, 3.4, b.res)
    out = K.wtile(tt, b, slice(0, b.h), slice(0, b.w)).copy()
    n = K.bnoise(b, 0.8, 21, 3)
    out = out * (0.7 + 0.5 * n)[..., None]
    b.alb[:] = np.clip(out, 0, 1)


# ==========================================================================
# props
# ==========================================================================
def mantel(sc):
    """the carved overmantel: a matte cut from the real photo, set against the back wall."""
    k = ('mantel',)
    if k not in K.CACHE:
        im = load('parlor_ph-oldhall-carved-mantel')
        x0, y0 = 850, 220
        crop = im.crop((x0 + 25, y0 + 25, x0 + 500, y0 + 795))
        W_, H_ = crop.size
        S = 4
        m = Image.new('L', (W_ * S, H_ * S), 0)
        d = ImageDraw.Draw(m)
        pts = [(48, 795), (482, 795), (482, 506), (500, 506), (500, 487), (447, 487), (447, 140), (455, 128),
               (455, 100), (380, 100)]
        for kk in range(1, 30):
            a = kk / 30 * math.pi
            pts.append((265 + 115 * math.cos(a), 104 - 80 * math.sin(a)))
        pts += [(150, 100), (65, 100), (65, 128), (75, 140), (75, 487), (25, 487), (25, 506), (48, 506)]
        d.polygon([((px - 25) * S, (py - 25) * S) for px, py in pts], fill=255)
        mask = np.asarray(m.resize((W_, H_), Image.Resampling.LANCZOS), np.float32) / 255
        a = f32(crop)
        a = K.flatten_light(a, 140)
        a = K.match_albedo(a, mean=0.24, sat=0.55, tint=(0.86, 0.90, 0.84), contrast=1.15)
        # the glazed tops of the gothic panels catch daylight in the photo: at night they are dark glass
        L = K.lum(a)
        hot = smoothstep(0.45, 0.65, L)
        a = a * (1 - 0.6 * hot[..., None])
        K.CACHE[k] = (a, blur(mask, 0.6))
    a, mask = K.CACHE[k]
    Zm = ZBK - 0.25
    sc.draw_quad([(-MANTEL_W / 2, MANTEL_H, Zm), (MANTEL_W / 2, MANTEL_H, Zm), (MANTEL_W / 2, 0.0, Zm),
                  (-MANTEL_W / 2, 0.0, Zm)], a, alpha=mask, spec=0.35, gloss=30, name='mantel')
    # its shelf and sides (the depth of the chimney piece), plain wood
    t = so.wood('wood_dark-varnished', 500, 40, 500, 2.0, seed=3, mean=0.24)
    sh_y = MANTEL_H * (1 - (487 - 25) / 770)
    sc.draw_quad([(-MANTEL_W / 2 - 0.03, sh_y, Zm - 0.02), (MANTEL_W / 2 + 0.03, sh_y, Zm - 0.02),
                  (MANTEL_W / 2 + 0.03, sh_y, ZBK), (-MANTEL_W / 2 - 0.03, sh_y, ZBK)], t, name='shelf_top')
    side = so.wood('wood_dark-varnished', 60, 600, 500, 2.0, rot=True, seed=4, mean=0.20)
    for X in (-MANTEL_W / 2 + 0.03, MANTEL_W / 2 - 0.03):
        sc.draw_quad([(X, MANTEL_H * 0.82, Zm), (X, MANTEL_H * 0.82, ZBK), (X, 0, ZBK), (X, 0, Zm)], side,
                     name='mantel_side')


def velvet(seed, mean=0.25):
    vel = K.mat('fabric_velvet-red', mean=mean, sat=0.50, tint=(0.95, 0.84, 0.86))
    return vel


def chair_tex(seed, kind, mean=0.25):
    """velvet faces for the armchair: 'back' (buttoned, arched crest), 'arm' (rolled scroll front), 'seat'."""
    vel = velvet(seed, mean)

    def f(wp, hp, face):
        t = tile(vel, wp, hp, seed=seed, scale=0.25 * 700 / vel.shape[1], tone_var=0.12)
        u = np.linspace(-1, 1, wp)[None, :]
        v = np.linspace(0, 1, hp)[:, None]
        a = None
        if kind == 'back' and face == 'front':
            yy, xx = np.mgrid[0:hp, 0:wp].astype(np.float32)
            sp = max(6.0, wp / 6)
            gx = (xx / sp) % 1.0
            gy = (yy / sp + 0.5 * np.floor(xx / sp)) % 1.0
            d = np.sqrt((gx - 0.5) ** 2 + (gy - 0.5) ** 2)
            puff = 1 - 0.35 * np.exp(-(d / 0.11) ** 2) + 0.12 * np.cos(d * math.pi * 1.7)
            t = t * puff[..., None]
            crest = 0.16 * (1 - u ** 2) ** 0.7                      # rounded crest, high in the middle
            a = (v > 0.17 - crest).astype(np.float32)
            t = t * (0.75 + 0.25 * np.clip((v - (0.17 - crest)) * 12, 0, 1))[..., None] ** 0.5
        elif kind == 'arm' and face == 'front':
            # a rolled scroll: round top, a spiral shadow
            r = np.sqrt(u ** 2 + ((v - 0.22) / 0.22) ** 2)
            a = np.where(v < 0.22, (r < 1.0).astype(np.float32), 1.0).astype(np.float32)
            t = t * (0.65 + 0.45 * np.clip(1 - r, 0, 1) ** 0.5 * (v < 0.44))[..., None]
            t = t * (1 - 0.35 * np.exp(-((r - 0.55) / 0.08) ** 2) * (v < 0.44))[..., None]
        elif kind == 'arm' and face in ('left', 'right', 'top'):
            t = t * (0.75 + 0.35 * np.sqrt(np.clip(1 - u ** 2, 0, 1)))[..., None]
        elif kind == 'seat' and face == 'top':
            t = t * (0.8 + 0.25 * np.sqrt(np.clip(1 - u ** 2, 0, 1)))[..., None]
        if face != 'top':
            t = t * (1 - 0.35 * smoothstep(0.5, 1.0, v))[..., None]           # soaked toward the water
        e = rect_mask(wp, hp, 0, 0, wp, hp, soft=max(1.5, min(wp, hp) * 0.12))
        t = t * (0.72 + 0.28 * e)[..., None]
        out = {'tex': np.clip(t, 0, 1), 'spec': 0.08, 'gloss': 6}
        if a is not None:
            out['alpha'] = blur(a, 0.8)
        return out
    return f


CHAIR_MESH = {}


def chair_instance(i):
    """the i-th armchair: a real carved Victorian armchair (Poly Haven 'Arm Chair 01', a photoscanned model) with
    its pale upholstery turned to the parlor's soaked crimson velvet, the pair turned a little toward each other."""
    if 'm' not in CHAIR_MESH:
        CHAIR_MESH['m'] = M.Mesh('ArmChair_01', recolor=M.recolor((0.42, 0.13, 0.17), lo=0.28, hi=0.5, keep=0.55))
    x0, x1, z0, z1 = CHAIRS[i]
    return CHAIR_MESH['m'].place(((x0 + x1) / 2, 0.0, (z0 + z1) / 2 + 0.05), yaw=(18 if i == 0 else -22), height=1.06)


def mesh_armchair(sc, i, mirror=False):
    inst = chair_instance(i)
    if mirror:
        M.draw_mesh(sc, inst, name=f'chair{i}', mirror_y=HW, spec=0.25)
    else:
        M.draw_mesh(sc, inst, name=f'chair{i}', spec=0.25)


def armchair(sc, x0, x1, z0, z1, seed):
    """(the old box armchair, kept for reference: the scene now uses mesh_armchair)
    a buttoned velvet armchair facing the camera, standing in the water to its cushion."""
    sc.box((x0 + 0.06, 0.20, z1 - 0.20), (x1 - 0.06, 1.12, z1), chair_tex(seed, 'back'), res=700, name='back')
    sc.box((x0 + 0.12, 0.20, z0 + 0.06), (x1 - 0.12, 0.53, z1 - 0.18), chair_tex(seed + 1, 'seat', 0.23), res=700,
           name='seat')
    for (a, b_) in ((x0, x0 + 0.14), (x1 - 0.14, x1)):
        sc.box((a, 0.20, z0), (b_, 0.74, z1 - 0.10), chair_tex(seed + 2, 'arm', 0.20), res=700, name='arm')


def chandelier(sc):
    """a dark brass gasolier: stem, a bowl, six curling arms with candle cups (a cut-out facing the camera)."""
    cx, cz = CHANDELIER
    top, bot = CEIL, 2.35
    wm, hm = 1.10, top - bot
    res = 700
    w, h = int(wm * res), int(hm * res)
    S = 3
    im = Image.new('L', (w * S, h * S), 0)
    d = ImageDraw.Draw(im)

    def P(x, y):                                      # metres (x from centre, y down from the ceiling)
        return ((x + wm / 2) * res * S, y * res * S)
    lw = max(1, int(0.026 * res * S))
    d.line([P(0, 0), P(0, 0.62)], fill=255, width=lw)                                 # stem
    d.ellipse([P(-0.05, 0.0), P(0.05, 0.05)], fill=255)                               # ceiling cup
    for yb, rb in ((0.30, 0.045), (0.46, 0.035)):
        d.ellipse([P(-rb, yb - rb * 0.7), P(rb, yb + rb * 0.7)], fill=255)          # knops
    d.polygon([P(-0.13, 0.66), P(0.13, 0.66), P(0.07, 0.80), P(-0.07, 0.80)], fill=255)  # bowl
    d.ellipse([P(-0.03, 0.80), P(0.03, 0.88)], fill=255)                              # finial
    for k, xs in enumerate((-1, 1)):
        for (reach, drop) in ((0.48, 0.70), (0.30, 0.74), (0.14, 0.78)):
            pts = []
            for i in range(21):
                t = i / 20
                x = xs * reach * t
                y = 0.68 + 0.10 * math.sin(t * math.pi) * -1 + (drop - 0.68) * t * t
                pts.append(P(x, y))
            d.line(pts, fill=255, width=max(1, int(0.018 * res * S)))
            ex, ey = xs * reach, drop
            d.polygon([P(ex - 0.035, ey - 0.03), P(ex + 0.035, ey - 0.03), P(ex + 0.025, ey + 0.01),
                       P(ex - 0.025, ey + 0.01)], fill=255)                          # candle cup
            d.rectangle([P(ex - 0.012, ey - 0.13), P(ex + 0.012, ey - 0.03)], fill=200)     # candle stub
    a = np.asarray(im.resize((w, h), Image.Resampling.LANCZOS), np.float32) / 255
    brass = K.mat('metal_brass-brushed', mean=0.38, sat=0.55, tint=(1.0, 0.88, 0.70))
    t = tile(brass, w, h, seed=3, scale=0.3) * (0.6 + 0.6 * value_noise(w, h, 20, 4, 2))[..., None]
    sc.draw_quad([(cx - wm / 2, top, cz), (cx + wm / 2, top, cz), (cx + wm / 2, bot, cz), (cx - wm / 2, bot, cz)],
                 np.clip(t, 0, 1), alpha=a, spec=0.8, gloss=25, spec_tint=(1.0, 0.85, 0.6), name='chandelier')


def window_parts(sc):
    z0, z1, y0, y1 = WIN
    Xg = XL - 0.08
    # the night sky outside the window (a plane well beyond the wall), the moon in it
    Xs = XL - 3.0
    zs0, zs1, ys0, ys1 = 1.0, 14.0, -2.0, 8.0
    res = 60
    w, h = int((zs1 - zs0) * res), int((ys1 - ys0) * res)
    t = Xs / XL
    sky = K.night_sky(w, h, moon_c=None, pines=False)
    # the moon is behind the camera's line of sight (its light crosses the room toward the back wall):
    # the sky glows toward it, at the near edge of the window
    zz = zs0 + (np.arange(w) + 0.5) / res
    yy = ys1 - (np.arange(h) + 0.5) / res
    ZZ, YY = np.meshgrid(zz, yy)
    gl = np.exp(-(((ZZ - (zs0 - 1.5)) / 3.5) ** 2 + ((YY - 4.5) / 4.0) ** 2))
    sky = np.clip(sky + gl[..., None] * K.hexcol('#cfc8ff', False) * 0.45, 0, 1)
    pines = f32(load('fog_ph-misty-pines'))[150:1350, 200:2000]
    pl = K.lum(pines)
    pl = resize_f(pl, w, int(w * pl.shape[0] / pl.shape[1] * 0.6), LANCZOS)
    sil = np.clip((0.80 - pl) * 2.0, 0, 1)
    hz = int((ys1 - (EYE + (1.0 - EYE) * t)) * res)
    top = max(0, hz - int(pl.shape[0] * 0.6))
    reg = sky[top:top + pl.shape[0]]
    al = sil[:reg.shape[0]][..., None] * 0.9
    reg[:] = reg * (1 - al) + np.array([0.05, 0.05, 0.10]) * al
    sky[top + pl.shape[0]:] = np.array([0.05, 0.05, 0.10])
    sc.draw_quad([(Xs, ys1, zs0), (Xs, ys1, zs1), (Xs, ys0, zs1), (Xs, ys0, zs0)], sky, lit=False, name='sky')
    res = 500
    ww, hh = int((z1 - z0) * res), int((y1 - y0) * res)
    zz = z0 + (np.arange(ww) + 0.5) / res
    yy = y1 - (np.arange(hh) + 0.5) / res
    ZZ, YY = np.meshgrid(zz, yy)
    Q = np.stack([np.full_like(ZZ, Xg), YY, ZZ], -1).reshape(-1, 3)
    a = blur(1 - window_aperture(Q).reshape(hh, ww), 0.8)
    paint = K.mat('wood_painted-green', mean=0.30, sat=0.30, tint=(0.92, 0.94, 1.0))
    sash = tile(paint, ww, hh, seed=8, scale=1.5 * res / paint.shape[1], tone_var=0.15)
    sc.draw_quad([(Xg, y1, z0), (Xg, y1, z1), (Xg, y0, z1), (Xg, y0, z0)], sash, alpha=a, name='sash')
    plaster = K.mat('plaster_aged-beige', mean=0.36, sat=0.35)
    pt = tile(plaster, 80, 400, seed=3, scale=0.4)
    sc.draw_quad([(XL - 0.15, y1, z1), (XL, y1, z1), (XL, y0, z1), (XL - 0.15, y0, z1)], pt, name='reveal')
    sc.draw_quad([(XL - 0.15, y0, z0), (XL - 0.15, y0, z1), (XL, y0, z1), (XL, y0, z0)],
                 so.wood('wood_painted-green', 120, 400, 400, 1.5, seed=12, mean=0.28, sat=0.3), name='sill')


def window_aperture(Q):
    z, y = Q[:, 2], Q[:, 1]
    z0, z1, y0, y1 = WIN
    inside = (z > z0 + 0.05) & (z < z1 - 0.05) & (y > y0 + 0.06) & (y < y1 - 0.06)
    zm, ym = (z0 + z1) / 2, (y0 + y1) / 2
    bars = (np.abs(z - zm) < 0.016) | (np.abs(y - ym) < 0.03)
    bars |= (np.abs(y - (y0 + ym) / 2) < 0.012) | (np.abs(y - (ym + y1) / 2) < 0.012)
    return (inside & ~bars).astype(np.float32)


def curtains(sc):
    """heavy velvet drapes hanging into the water, sodden at the hem."""
    z0, z1, y0, y1 = WIN
    res = 360
    Xc = XL + 0.10
    for k, (za, zb_) in enumerate(((z0 - 0.22, z0 + 0.06), (z1 - 0.06, z1 + 0.42))):
        ya, yb = 0.0, y1 + 0.32
        ww, hh = int((zb_ - za) * res), int((yb - ya) * res)
        t, a = so.velvet_curtain(ww, hh, res, 90 + k, inner_right=(k == 0))
        Y = yb - (np.arange(hh) + 0.5) / res
        wet = smoothstep(1.15, 0.8, Y)[:, None, None]
        t = t * (1 - 0.45 * wet)
        sc.draw_quad([(Xc, yb, za), (Xc, yb, zb_), (Xc, ya, zb_), (Xc, ya, za)], t, alpha=a, name=f'curtain{k}')


def build_room(sc, mirror=False):
    """everything above (and, in the main pass, below) the water."""
    window_parts(sc)
    draw_plane(sc, Plane('back', ZBK, XL, XR, 0.0, CEIL), back_painter, None, max_res=420)
    if not mirror:
        draw_plane(sc, Plane('floor', 0.0, XL, XR, 2.0, ZBK), floor_painter, zbreaks(2.0, ZBK, 1.42), max_res=400)
    draw_plane(sc, Plane('ceil', CEIL, XL, XR, 0.6, ZBK), ceil_painter, zbreaks(0.6, ZBK, 1.42), max_res=500)
    draw_plane(sc, Plane('lwall', XL, 0.3, ZBK, 0.0, CEIL), left_painter, zbreaks(0.3, ZBK, 1.42), max_res=600)
    draw_plane(sc, Plane('rwall', XR, 0.3, ZBK, 0.0, CEIL), right_painter, zbreaks(0.3, ZBK, 1.42), max_res=600)
    mantel(sc)
    for (x0, x1, y0, y1, name, oval) in PAINTINGS:
        Zp = ZBK - 0.03
        K.framed_painting(sc, [(x0, y1, Zp), (x1, y1, Zp), (x1, y0, Zp), (x0, y0, Zp)], name, x1 - x0, y1 - y0,
                          res=480, frame=0.07, seed=int(abs(x0) * 10), oval=oval)
    curtains(sc)
    candles(sc)
    for i in reversed(range(len(CHAIRS))):                  # (the far one first)
        mesh_armchair(sc, i, mirror)
    chandelier(sc)


SHELF_Y = MANTEL_H * (1 - (487 - 25) / 770)
CANDLES = [(-0.62, SHELF_Y, ZBK - 0.36), (0.58, SHELF_Y, ZBK - 0.36)]


def candles(sc):
    """two brass candlesticks on the mantel shelf, one candle still burning, one long dead."""
    cam = sc.cam
    brass = K.mat('metal_brass-brushed', mean=0.40, sat=0.6, tint=(1.0, 0.9, 0.7))
    for i, (x, y, z) in enumerate(CANDLES):
        res = cam.f / z * cam.ss
        w, h = max(6, int(0.10 * res)), max(8, int(0.26 * res))
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        v = yy / h
        half = (0.12 + 0.30 * np.exp(-((v - 0.95) / 0.08) ** 2) + 0.14 * np.exp(-((v - 0.12) / 0.05) ** 2) +
                0.10 * np.exp(-((v - 0.55) / 0.04) ** 2)) * w
        a = np.clip((half - np.abs(xx - w / 2)) / 1.0, 0, 1)
        t = tile(brass, w, h, seed=i, scale=0.3) * (0.55 + 0.7 * np.clip(1 - np.abs(xx - w * 0.42) / (w * 0.5), 0,
                                                                          1))[..., None]
        sc.draw_quad([(x - 0.05, y + 0.26, z), (x + 0.05, y + 0.26, z), (x + 0.05, y, z), (x - 0.05, y, z)],
                     np.clip(t, 0, 1), alpha=a, spec=0.9, gloss=30, spec_tint=(1.0, 0.85, 0.6), name='stick')
        ch = 0.16 if i == 0 else 0.22
        wax = K.mat('paper_offwhite-grain', mean=0.70, sat=0.2, tint=(1.0, 0.96, 0.88))
        w2, h2 = max(4, int(0.026 * res)), max(4, int(ch * res))
        sc.draw_quad([(x - 0.013, y + 0.26 + ch, z), (x + 0.013, y + 0.26 + ch, z), (x + 0.013, y + 0.26, z),
                      (x - 0.013, y + 0.26, z)], tile(wax, w2, h2, seed=i, scale=0.2), name='candle',
                     emissive=(np.zeros((h2, w2, 3)) + np.array([0.5, 0.3, 0.12]) *
                               np.linspace(1, 0, h2)[:, None, None] ** 3) if i == 0 else None, emit=0.4)
        if i == 0:                                              # the flame
            fw, fh = max(4, int(0.03 * res)), max(6, int(0.07 * res))
            yy, xx = np.mgrid[0:fh, 0:fw].astype(np.float32)
            d = np.sqrt(((xx - fw / 2) / (fw / 2)) ** 2 + ((yy - fh * 0.6) / (fh * 0.45)) ** 2)
            fa = np.clip((1 - d) * 3, 0, 1)
            em = np.clip(1.2 - d, 0, 1)[..., None] * np.array([1.0, 0.75, 0.40])
            yt = y + 0.26 + ch
            sc.draw_quad([(x - 0.015, yt + 0.075, z), (x + 0.015, yt + 0.075, z), (x + 0.015, yt - 0.005, z),
                          (x - 0.015, yt - 0.005, z)], np.zeros((fh, fw, 3), np.float32), alpha=fa,
                         emissive=np.clip(em, 0, 1), emit=3.0, lit=False, name='flame')


def make_lights(sc, mirror=False):
    moon = K.MOON
    cx, cy_, cz = CANDLES[0]
    Ls = [PointLight((cx, cy_ + 0.47, cz - 0.03), K.AMBER, power=1.6, soft=0.22, wrap=0.15, shadow_px=None,
                     name='candle'),
          PointLight((cx * 0.5, 1.2, cz - 0.6), K.AMBER, power=0.5, soft=1.2, wrap=0.4, shadow_px=None,
                     name='candle_bounce'),K.XApertureLight(MOON_DIR, moon, power=3.4, plane_x=XL - 0.08, aperture=window_aperture, shadow_px=1.5,
                           name='moon'),
          PointLight((XL + 0.3, (WIN[2] + WIN[3]) / 2, (WIN[0] + WIN[1]) / 2), moon * np.array([0.9, 0.92, 1.0]),
                     power=2.6, soft=0.7, pattern=lambda d: np.clip(d[:, 0], 0, 1) ** 1.2, wrap=0.3, shadow_px=None,
                     name='window_glow'),
          # moonlight thrown back up by the water onto the walls and the ceiling (a soft cold bounce)
          PointLight((0.0, HW + 0.05, 3.6), moon * np.array([0.75, 0.85, 1.0]), power=1.6, soft=1.6,
                     pattern=lambda d: np.clip(d[:, 1], 0, 1), wrap=0.3, shadow_px=None, name='water_bounce'),
          PointLight((0.0, 2.6, -0.6), moon * np.array([0.85, 0.85, 1.0]), power=2.4, soft=1.5, wrap=0.3,
                     shadow_px=None, name='fill')]
    if mirror:
        Ls = [mirror_light(L, HW) for L in Ls]
    sc.lights += Ls


def ripple_field(X, Z, t_seed=1):
    """height of the water surface (metres) at world X, Z: a slow swell and two spreading drip rings."""
    h = (K.wnoise(X, Z * 1.6, 0.9, 31, 3) - 0.5) * 0.010
    h += (K.wnoise(X * 1.3, Z, 0.25, 37, 2) - 0.5) * 0.0025
    for (dx, dz, age) in DRIPS:
        r = np.sqrt((X - dx) ** 2 + (Z - dz) ** 2)
        R0 = 0.32 * age
        env = np.exp(-((r - R0) / (0.07 * age + 0.03)) ** 2) + 0.4 * np.exp(-((r - R0 * 0.5) / 0.05) ** 2)
        h += 0.0011 * np.sin(r / 0.06 * 2 * math.pi) * env / (1 + 3 * r)
    return h


def composite_water(main: ZScene, refl: ZScene):
    """water over the main canvas: Fresnel mix of the (ripple-displaced) reflection and the murky underwater view."""
    cam = main.cam
    Hs, Ws = main.zbuf.shape
    out = main.canvas
    xs = (np.arange(Ws, dtype=np.float32) + 0.5) / cam.ss
    for y0 in range(0, Hs, 256):
        y1 = min(Hs, y0 + 256)
        ys = (np.arange(y0, y1, dtype=np.float32) + 0.5) / cam.ss
        dy = -(ys - cam.cy) / cam.f
        dx = (xs - cam.cx) / cam.f
        DY = np.repeat(dy[:, None], Ws, 1)
        DX = np.repeat(dx[None, :], y1 - y0, 0)
        with np.errstate(divide='ignore', invalid='ignore'):
            tw = (HW - cam.eye) / DY
        valid = (DY < -1e-4) & (tw > 0) & (tw < main.zbuf[y0:y1])
        if not valid.any():
            continue
        tw = np.where(valid, tw, 1.0)
        Xw, Zw = DX * tw, tw
        # surface slope -> screen displacement of the reflection (stronger nearer the camera)
        h = ripple_field(Xw, Zw)
        e = 0.01
        hx = (ripple_field(Xw + e, Zw) - h) / e
        hz = (ripple_field(Xw, Zw + e) - h) / e
        k = cam.f * cam.ss / np.maximum(tw, 0.5) * 2.2
        offx = -hx * k
        offy = hz * k * 1.6
        sx = np.clip(np.arange(Ws)[None, :] + offx, 0, Ws - 1.001)
        sy = np.clip(np.arange(y0, y1)[:, None] + offy, 0, Hs - 1.001)
        ix, iy = sx.astype(np.int32), sy.astype(np.int32)
        fx, fy = (sx - ix)[..., None], (sy - iy)[..., None]
        R = refl.canvas
        rc = (R[iy, ix] * (1 - fx) * (1 - fy) + R[iy, ix + 1] * fx * (1 - fy) + R[iy + 1, ix] * (1 - fx) * fy +
              R[iy + 1, ix + 1] * fx * fy)
        # Fresnel (exaggerated: black still water reads as a dark mirror)
        Vlen = np.sqrt(DX ** 2 + DY ** 2 + 1)
        cos = np.clip(-DY / Vlen, 0, 1)
        Fr = (0.32 + 0.45 * (1 - cos) ** 2)[..., None]
        under = out[y0:y1] * np.array([0.06, 0.09, 0.09], np.float32)
        murk = np.array([0.002, 0.003, 0.004], np.float32)
        water = rc * Fr * np.array([0.80, 0.90, 1.0], np.float32) + (under + murk) * (1 - Fr)
        # glints where the ripples tilt toward the moonlit window
        slope = np.sqrt(hx ** 2 + hz ** 2)
        glint = smoothstep(0.035, 0.09, slope) * smoothstep(-0.3, 0.6, -Xw / 2.3) * 0.06
        water = water + glint[..., None] * K.MOON
        m = valid[..., None].astype(np.float32)
        out[y0:y1] = water * m + out[y0:y1] * (1 - m)
        main.zbuf[y0:y1] = np.where(valid, tw, main.zbuf[y0:y1])
    # the meniscus: a faint bright line where something stands in the water (water just below a non-water pixel)
    zb = main.zbuf
    with np.errstate(divide='ignore', invalid='ignore'):
        ys = (np.arange(Hs, dtype=np.float32) + 0.5) / cam.ss
        dyv = -(ys - cam.cy) / cam.f
        twv = np.where(dyv < -1e-4, (HW - cam.eye) / dyv, np.inf)
    is_w = np.abs(zb - twv[:, None]) < 1e-3
    above = np.zeros_like(is_w)
    above[3:] = ~is_w[:-3] & (zb[:-3] < zb[3:] + 0.6)
    line = (is_w & above).astype(np.float32)
    line = blur(line, 1.5) * 0.9
    out += line[..., None] * K.MOON[None, None, :] * 0.035


def floating(sc):
    """a few things floating on the surface: letters, a book, petals from a dead bouquet."""
    paper = K.mat('paper_old-paper-stained', mean=0.55, sat=0.35)
    rng = np.random.default_rng(5)
    items = [(0.35, 2.75, 0.20, 0.27, 0.4), (-0.95, 3.0, 0.18, 0.24, -0.6), (1.6, 3.2, 0.21, 0.28, 1.1),
             (0.15, 4.6, 0.18, 0.25, 0.2)]
    for i, (x, z, w, d, rot) in enumerate(items):
        c, s = math.cos(rot), math.sin(rot)
        pts = []
        for (ax, az) in ((-w / 2, d / 2), (w / 2, d / 2), (w / 2, -d / 2), (-w / 2, -d / 2)):
            pts.append((x + ax * c - az * s, HW + 0.002, z + ax * s + az * c))
        wp, hp = 200, 260
        t = tile(paper, wp, hp, seed=i, scale=0.5)
        wet = value_noise(wp, hp, 30, 9 + i, 3)
        t = t * (0.55 + 0.4 * wet)[..., None]
        im = Image.fromarray((np.clip(t, 0, 1) * 255).astype(np.uint8))
        dr = ImageDraw.Draw(im)
        for ln in range(9):
            yl = int(hp * (0.12 + ln * 0.085))
            xl = int(wp * 0.1)
            while xl < wp * 0.85:
                wl = int(rng.uniform(0.06, 0.18) * wp)
                dr.line([(xl, yl), (xl + wl, yl + int(rng.normal(0, 1)))], fill=(60, 55, 70), width=1)
                xl += wl + int(0.03 * wp)
        t = f32(im)
        a = rect_mask(wp, hp, 0, 0, wp, hp, soft=3) * (0.75 + 0.25 * wet)
        sc.draw_quad(pts, t, alpha=a, name=f'letter{i}', spec=0.3, gloss=20)


def render(seed=31):
    cam = K.make_camera(F, CX, CY, EYE)
    main = ZScene(cam, K.ambient_fn)
    make_lights(main)
    for i in range(len(CHAIRS)):
        lo, hi = chair_instance(i).bounds()
        main.add_occluder(f'chair{i}', lo, hi)
    build_room(main)
    refl = MirrorScene(cam, K.ambient_fn, HW)
    make_lights(refl, mirror=True)
    build_room(refl, mirror=True)
    composite_water(main, refl)
    floating(main)
    # the candle's glow and its long rippled streak in the water
    cx, cy_, cz = CANDLES[0]
    K.halo(main, (cx, cy_ + 0.46, cz), 0.35, 0.22, K.AMBER * np.array([1.0, 0.9, 0.75]))
    K.halo(main, (cx, cy_ + 0.46, cz), 0.08, 0.6, K.AMBER)
    u, v = cam.project((cx, 2 * HW - (cy_ + 0.46), cz))
    _, vw = cam.project((cx, HW, cz))
    Hs, Ws = main.zbuf.shape
    yy = (np.arange(Hs) + 0.5) / cam.ss
    xx = (np.arange(Ws) + 0.5) / cam.ss
    wob = np.sin(yy * 0.35) * 3 + np.sin(yy * 0.11 + 1) * 4
    streak = np.exp(-((xx[None, :] - u - wob[:, None]) / 7.0) ** 2) * smoothstep(vw, vw + 25, yy)[:, None] * \
        np.exp(-np.maximum(0, yy - v)[:, None] / 60.0) * (0.6 + 0.4 * np.sin(yy * 0.9)[:, None] ** 2)
    main.canvas += (streak * 0.10)[..., None] * K.AMBER[None, None, :]
    lin = main.downsample()
    moonL = [l for l in main.lights if l.name == 'moon'][0]
    lin = lin + K.volumetric(cam, main.depth_out(), moonL, 0.8, ZBK, n=40, density=0.006)
    y = K.finish_cam(lin, seed)
    return y, lin, main


def poses():
    cam = K.make_camera(F, CX, CY, EYE)
    # feet on the drowned floor (the water hides the shins); y is the floor contact under the water
    return [K.pose_for(cam, 0.10, 2.75), K.pose_for(cam, -0.30, 3.85), K.pose_for(cam, 0.20, 5.20)]


def build(out_path):
    y, _, _ = render()
    save_jpeg(pil(y), out_path, quality=84, max_kb=880)
    return out_path


if __name__ == '__main__':
    import time
    t = time.time()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/cam3.png')
    y, lin, sc = render()
    pil(y).save(out)
    K.overlay(y, sc.cam, poses(), vp=(CX, CY)).save(str(out).replace('.png', '_ov.png'))
    print('saved', out, f'{time.time() - t:.1f}s')
