"""meshkit: real furniture (CC0 Poly Haven photoscanned models) in the photo-composited scenes.

The props that were boxes and cut-outs (the parlor armchairs, CAM 7's desk chair, the hall's long-case clock,
the nursery's crib and dresser, the game's alarm clock) are 3-D models made from photographs of real objects
(their textures are photos). This file draws them into a Scene with the scene's own camera, lights, shadows and
ambient, so they share the one look: same light, same falloff, same finish afterwards.

    m = Mesh('ArmChair_01', mean=0.24, sat=0.6, tint=(1, .9, .92))      # sources/models/<id>/<id>.npz + textures
    inst = m.place((x, 0.0, z), yaw=15, height=1.06)                   # feet on the floor at (x, z), in metres
    draw_mesh(sc, inst, name='chair0')                                 # rasterised at the scene's ss, z-buffered
    sc.add_occluder('chair0', *inst.bounds())                          # so it also casts shadows

Geometry: glTF is right-handed with the model's front toward +z; the scenes are x right, y up, z away from the
camera, so a model is turned to face the camera (z -> -z) when it is loaded. Lighting: Lambert + wrap (the
scene's own lights, with their patterns and box shadows; a model never shadows itself through its own box),
the texture's ambient occlusion, and a Blinn-Phong highlight from its roughness map (varnish, brass, leather).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from common import SOURCES, f32, lum, match_albedo, srgb2lin, PointLight  # noqa: F401

MODELS = SOURCES / 'models'


def _bilinear(tex, u, v):
    """sample tex (h, w, c) at UV (repeat), glTF convention (v = 0 at the top of the image)."""
    h, w = tex.shape[:2]
    x = (u % 1.0) * w - 0.5
    y = (v % 1.0) * h - 0.5
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx = (x - x0).astype(np.float32)[:, None]
    fy = (y - y0).astype(np.float32)[:, None]
    x0 %= w
    y0 %= h
    x1 = (x0 + 1) % w
    y1 = (y0 + 1) % h
    return (tex[y0, x0] * (1 - fx) * (1 - fy) + tex[y0, x1] * fx * (1 - fy) + tex[y1, x0] * (1 - fx) * fy +
            tex[y1, x1] * fx * fy)


class Instance:
    """a placed model: world-space triangles per primitive."""

    def __init__(self, mesh, prims):
        self.mesh = mesh
        self.prims = prims                    # [(P (n,3), N (n,3), UV (n,2), idx (m,3), meta)]

    def bounds(self):
        P = np.concatenate([p[0] for p in self.prims])
        return P.min(0), P.max(0)

    def points(self):
        return np.concatenate([p[0] for p in self.prims])


class Mesh:
    """a model from sources/models/<ident>/ (geometry .npz and its diff / arm textures), colour-matched once."""

    def __init__(self, ident, mean=None, sat=None, tint=None, contrast=None, recolor=None, only=None, skip=None):
        d = MODELS / ident
        z = np.load(d / f'{ident}.npz')
        self.meta = json.loads(str(z['meta']))
        self.prims = []
        for k, m in enumerate(self.meta):
            if only and not any(s in m['node'] or s in m['material'] for s in only):
                continue
            if skip and any(s in m['node'] or s in m['material'] for s in skip):
                continue
            if m['alpha'] == 'BLEND':                         # (glass: left out, the room shows through)
                continue
            self.prims.append((z[f'p{k}_pos'].astype(np.float64), z[f'p{k}_nrm'].astype(np.float32),
                               z[f'p{k}_uv'].astype(np.float32), z[f'p{k}_idx'].astype(np.int64), m))
        diff = f32(Image.open(d / f'{ident}_diff.jpg').convert('RGB'))
        if recolor is not None:
            diff = recolor(diff)
        if mean is not None or sat is not None or tint is not None or contrast is not None:
            diff = match_albedo(diff, mean=mean, sat=sat, tint=tint, contrast=contrast)
        self.alb = srgb2lin(np.clip(diff, 0, 1)).astype(np.float32)
        arm = d / f'{ident}_arm.jpg'
        self.arm = f32(Image.open(arm).convert('RGB')) if arm.exists() else None
        self.ident = ident

    def place(self, pos, yaw=0.0, height=None, scale=1.0, mirror_x=False):
        """feet on the floor at pos = (x, y, z) (the middle of its footprint), turned yaw degrees (positive turns its
        front toward +x), scaled to `height` metres tall (or by `scale`)."""
        allP = np.concatenate([p[0] for p in self.prims])
        lo, hi = allP.min(0), allP.max(0)
        s = (height / (hi[1] - lo[1])) if height else scale
        c = (lo + hi) / 2
        a = -math.radians(yaw)                                         # (yaw > 0: its front turns toward +x)
        R = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
        flip = np.array([-1.0 if mirror_x else 1.0, 1.0, -1.0])       # glTF front (+z) -> toward the camera (-z)
        out = []
        xf = lambda P: ((np.asarray(P, np.float64) - np.array([c[0], lo[1], c[2]])) * flip * s) @ R.T + np.asarray(pos, np.float64)
        for P, N, UV, idx, m in self.prims:
            Q = xf(P)
            Nn = (N * flip) @ R.T.astype(np.float32)
            ix = idx[:, ::-1] if mirror_x else idx
            out.append((Q, Nn.astype(np.float32), UV, ix, m))
        inst = Instance(self, out)
        inst.xf = xf                         # (model coordinates -> world, e.g. a clock's dial centre)
        return inst


def rasterise(cam, inst, zlimit=None, keep=None):
    """z-buffered triangles at ss resolution. Returns (ys, xs, prim, tri, b (k,3) perspective barycentrics, depth).
    zlimit: (H, W) depths already drawn in front (pixels behind them are dropped); keep(P) -> bool per vertex
    region test is applied later (e.g. above the water)."""
    H, W = cam.H, cam.W
    zb = np.full((H, W), np.inf, np.float32)
    pid = np.full((H, W), -1, np.int32)
    tid = np.full((H, W), -1, np.int32)
    bar = np.zeros((H, W, 3), np.float32)
    for pi, (P, N, UV, idx, m) in enumerate(inst.prims):
        S = cam.project_ss(P)
        Z = cam.depth(P)
        for ti in range(len(idx)):
            a, b, c = idx[ti]
            za, zb_, zc = Z[a], Z[b], Z[c]
            if min(za, zb_, zc) < 0.05:
                continue
            (xa, ya), (xb, yb), (xc, yc) = S[a], S[b], S[c]
            x0 = max(0, int(math.floor(min(xa, xb, xc) - 0.5)))
            x1 = min(W - 1, int(math.ceil(max(xa, xb, xc) - 0.5)))
            y0 = max(0, int(math.floor(min(ya, yb, yc) - 0.5)))
            y1 = min(H - 1, int(math.ceil(max(ya, yb, yc) - 0.5)))
            if x1 < x0 or y1 < y0:
                continue
            area = (xb - xa) * (yc - ya) - (xc - xa) * (yb - ya)
            if abs(area) < 1e-9:
                continue
            gx = np.arange(x0, x1 + 1, dtype=np.float64) + 0.5
            gy = np.arange(y0, y1 + 1, dtype=np.float64)[:, None] + 0.5
            w0 = ((xb - gx) * (yc - gy) - (xc - gx) * (yb - gy)) / area
            w1 = ((xc - gx) * (ya - gy) - (xa - gx) * (yc - gy)) / area
            w2 = 1.0 - w0 - w1
            inside = (w0 >= -1e-7) & (w1 >= -1e-7) & (w2 >= -1e-7)
            if not inside.any():
                continue
            iz = w0 / za + w1 / zb_ + w2 / zc
            d = (1.0 / iz).astype(np.float32)
            reg = zb[y0:y1 + 1, x0:x1 + 1]
            upd = inside & (d < reg)
            if zlimit is not None:
                upd &= d < zlimit[y0:y1 + 1, x0:x1 + 1] + 0.004
            if not upd.any():
                continue
            reg[upd] = d[upd]
            pid[y0:y1 + 1, x0:x1 + 1][upd] = pi
            tid[y0:y1 + 1, x0:x1 + 1][upd] = ti
            pb = np.stack([w0 / za / iz, w1 / zb_ / iz, w2 / zc / iz], -1).astype(np.float32)
            bar[y0:y1 + 1, x0:x1 + 1][upd] = pb[upd]
    ys, xs = np.nonzero(pid >= 0)
    return ys, xs, pid[ys, xs], tid[ys, xs], bar[ys, xs], zb[ys, xs]


def draw_mesh(sc, inst, *, name='mesh', spec=0.35, ao_strength=0.85, light_ignore=(), mirror_y=None,
              exposure=1.0, write_z=True, test_z=True, extra_light=None, return_px=False):
    """render a placed model into sc.canvas (linear), lit by sc's ambient and lights (its own occluder ignored).
    mirror_y: the water level of a mirror pass (the model is drawn reflected, only its part above the water)."""
    cam = sc.cam
    if mirror_y is not None:
        hw = mirror_y
        prims = [(P * np.array([1, -1, 1]) + np.array([0, 2 * hw, 0]), N * np.array([1, -1, 1], np.float32), UV,
                  idx[:, ::-1], m) for (P, N, UV, idx, m) in inst.prims]
        inst = Instance(inst.mesh, prims)
    zl = getattr(sc, 'zbuf', None) if test_z else None
    ys, xs, pi, ti, b, d = rasterise(cam, inst, zlimit=zl)
    if len(ys) == 0:
        return (ys, xs, np.zeros((0, 3))) if return_px else 0
    n = len(ys)
    P = np.zeros((n, 3), np.float64)
    N = np.zeros((n, 3), np.float32)
    UV = np.zeros((n, 2), np.float32)
    for k, (Pp, Np, UVp, idx, m) in enumerate(inst.prims):
        sel = pi == k
        if not sel.any():
            continue
        tri = idx[ti[sel]]
        bb = b[sel]
        for j in range(3):
            P[sel] += Pp[tri[:, j]] * bb[:, j:j + 1]
            N[sel] += Np[tri[:, j]] * bb[:, j:j + 1]
            UV[sel] += UVp[tri[:, j]] * bb[:, j:j + 1]
    keep = np.ones(n, bool)
    if mirror_y is not None:
        keep = (2 * mirror_y - P[:, 1]) > mirror_y          # only what is above the water is reflected
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-8
    O = np.asarray(cam.viewpoint(), np.float64)
    V = O[None, :] - P
    V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-9
    back = (N * V.astype(np.float32)).sum(1) < 0               # (thin parts seen from behind: light their far side)
    N[back] *= -1
    Pf = P.astype(np.float32)
    alb = _bilinear(inst.mesh.alb, UV[:, 0], UV[:, 1])
    if inst.mesh.arm is not None:
        arm = _bilinear(inst.mesh.arm, UV[:, 0], UV[:, 1])
        ao, rough, metal = arm[:, 0], arm[:, 1], arm[:, 2]
    else:
        ao, rough, metal = np.ones(n, np.float32), np.full(n, 0.6, np.float32), np.zeros(n, np.float32)
    ao = 1 - ao_strength * (1 - ao)
    amb = sc.ambient(Pf, N) if callable(sc.ambient) else np.broadcast_to(np.asarray(sc.ambient, np.float32), Pf.shape)
    ign = tuple(light_ignore) + (name,)
    Ed = np.zeros_like(Pf)
    for L in sc.lights:
        Ed += L.irradiance(Pf, N, sc, None, ign)
    if extra_light is not None:
        Ed += extra_light(Pf, N)
    E = amb * ao[:, None] + Ed * (1 - 0.4 * (1 - ao))[:, None]
    out = alb * E * (1 - 0.6 * metal)[:, None]
    if spec > 0:
        sp = np.zeros_like(Pf)
        gloss = 6 + 90 * (1 - rough) ** 2
        Vf = V.astype(np.float32)
        for L in sc.lights:
            if not isinstance(L, PointLight):
                continue
            Lv = L.pos[None, :] - Pf
            d2 = (Lv * Lv).sum(1)
            Ln = Lv / (np.sqrt(d2)[:, None] + 1e-9)
            Hh = Ln + Vf
            Hh /= np.linalg.norm(Hh, axis=1, keepdims=True) + 1e-9
            nh = np.clip((N * Hh).sum(1), 0, 1)
            pat = L.pattern(-Ln) if L.pattern is not None else 1.0
            sp += (L.power * pat * nh ** gloss / (d2 + L.soft ** 2))[:, None] * L.color[None, :]
        ks = (spec * (1 - rough) ** 2 * ao)[:, None]
        tint = (1 - metal)[:, None] + metal[:, None] * alb / (lum(alb)[:, None] + 1e-3) * 0.6
        out = out + sp * ks * tint
    out = (out * exposure).astype(np.float32)
    ys, xs, out, d = ys[keep], xs[keep], out[keep], d[keep]
    sc.canvas[ys, xs] = out
    if write_z and getattr(sc, 'zbuf', None) is not None:
        sc.zbuf[ys, xs] = d
    if return_px:
        return ys, xs, P[keep]
    return len(ys)


def contact_shadow(sc, inst, strength=0.55, radius=0.10, floor_y=0.0, region_pad=0.25, y_top=0.06):
    """darken the floor round where the model touches it (world-space AO from its lowest points), before it is drawn.
    Uses sc.zbuf to find the floor's world points when there is one, the floor plane otherwise."""
    cam = sc.cam
    P = inst.points()
    feet = P[P[:, 1] < floor_y + y_top]
    if len(feet) == 0:
        return
    if len(feet) > 600:
        feet = feet[np.random.default_rng(0).choice(len(feet), 600, replace=False)]
    lo, hi = P.min(0) - region_pad, P.max(0) + region_pad
    corners = np.array([[x, floor_y, z] for x in (lo[0], hi[0]) for z in (lo[2], hi[2])])
    S = cam.project_ss(corners)
    x0, x1 = max(0, int(S[:, 0].min()) - 4), min(cam.W, int(S[:, 0].max()) + 4)
    y0, y1 = max(0, int(S[:, 1].min()) - 4), min(cam.H, int(S[:, 1].max()) + 4)
    if x1 <= x0 or y1 <= y0:
        return
    D = cam.rays(x0, y0, x1 - x0, y1 - y0)
    Oo = cam.origin
    with np.errstate(divide='ignore', invalid='ignore'):
        t = (floor_y - Oo[1]) / D[..., 1]
    W = Oo[None, None, :] + D * t[..., None]
    onfloor = (t > 0) & np.isfinite(t)
    zb = getattr(sc, 'zbuf', None)
    if zb is not None:
        onfloor &= np.abs(zb[y0:y1, x0:x1] - t) < 0.03 * np.maximum(t, 1)
    acc = np.zeros((y1 - y0, x1 - x0), np.float32)
    Wx, Wz = W[..., 0], W[..., 2]
    for fx, fy, fz in feet:
        acc = np.maximum(acc, np.exp(-((Wx - fx) ** 2 + (Wz - fz) ** 2) / (radius * radius) * (1 + 0 * fy)))
    ao = 1 - strength * acc * onfloor
    sc.canvas[y0:y1, x0:x1] *= ao[..., None]


def recolor(target, where='light', lo=0.30, hi=0.55, keep=0.35, sat_max=0.30, hue=None):
    """a texture recolouring for Mesh(recolor=...): the parts picked by `where` take the colour `target` (sRGB),
    keeping `keep` of their own brightness pattern (weave, wear, folds).
    where 'light': light, unsaturated parts (pale upholstery), smoothstep on luminance lo..hi;
    where 'hue': parts whose hue is near `hue` (an sRGB colour, e.g. the aqua paint of a clock)."""
    T = np.asarray(target, np.float32)

    def f(diff):
        L = lum(diff)[..., None]
        mx, mn = diff.max(-1, keepdims=True), diff.min(-1, keepdims=True)
        sat = (mx - mn) / (mx + 1e-4)
        if where == 'hue':
            h = np.asarray(hue, np.float32)
            hn = h / (np.linalg.norm(h) + 1e-6)
            dn = diff / (np.linalg.norm(diff, axis=-1, keepdims=True) + 1e-6)
            sim = (dn * hn).sum(-1, keepdims=True)
            m = np.clip((sim - 0.94) / 0.04, 0, 1) * np.clip((sat - 0.12) / 0.1, 0, 1)
        else:
            m = np.clip((L - lo) / (hi - lo), 0, 1) * np.clip((sat_max - sat) / 0.1, 0, 1)
        rel = L / (np.mean(L[m[..., 0] > 0.5]) + 1e-4) if (m > 0.5).any() else np.ones_like(L)
        col = T * (keep * rel + (1 - keep))
        return np.clip(diff * (1 - m) + col * m, 0, 1)
    return f
