"""Shared toolkit for the photo-composited scenes of "Until the Alarm".

Everything a scene needs to turn the curated photos and textures in
art-src/sources/ into one coherent, lit picture:

  * image IO (sources in, progressive JPEG out), sRGB <-> linear
  * fast Gaussian blur on float arrays, value noise, smoothstep
  * texture prep: flatten uneven museum lighting, colour-match a texture to
    the scene (mean albedo, saturation, tint), make a photo seamless, tile a
    texture over any size with random offsets and soft tone variation
  * a tiny pinhole camera + "deferred" quad renderer: every wall, floor,
    ceiling, door frame, desk face, painting ... is a textured quad placed in
    3-D metres; it is projected with an exact perspective (PIL PERSPECTIVE,
    supersampled), then lit per pixel by the scene's lights with soft
    inverse-square falloff, cosine terms, ray-cast box shadows (blurred into
    penumbras), ambient occlusion and contact shadows
  * screen-space helpers: glows, light shafts, polygons, text masks

Coordinates: X to the right, Y up (floor = 0), Z away from the eye.
The eye sits at (0, cam.eye, 0) and looks down +Z.
Colours inside the renderer are LINEAR radiance (0..1+, lights can exceed 1);
grade.finish() turns the result into the final sRGB picture.

Only PIL and numpy are used (no scipy / cv2).
"""
from __future__ import annotations

import io
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None

ART_SRC = Path(__file__).resolve().parent.parent          # art-src/
SOURCES = ART_SRC / 'sources'
GAME = ART_SRC.parent / 'nightmare'                       # the game folder
SCENES_OUT = GAME / 'assets' / 'scenes'                   # built-in stand-ins (never assets/rooms/)
FONTS = GAME / 'assets' / 'fonts'

BICUBIC = Image.Resampling.BICUBIC
BILINEAR = Image.Resampling.BILINEAR
LANCZOS = Image.Resampling.LANCZOS
PERSPECTIVE = Image.Transform.PERSPECTIVE


# --------------------------------------------------------------------------
# IO
# --------------------------------------------------------------------------
def src_path(name: str) -> Path:
    """'floor_old-oak-dark' or 'textures/floor_old-oak-dark.jpg' -> full path in sources/."""
    p = Path(name)
    if p.is_absolute() and p.exists():
        return p
    for cand in (SOURCES / name, SOURCES / 'textures' / name, SOURCES / 'photos' / name):
        for c in (cand, cand.with_suffix('.jpg')):
            if c.exists():
                return c
    raise FileNotFoundError(name)


def load(name: str, max_side: int | None = None) -> Image.Image:
    im = Image.open(src_path(name))
    im.load()
    im = im.convert('RGB')
    if max_side and max(im.size) > max_side:
        k = max_side / max(im.size)
        im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), LANCZOS)
    return im


def f32(img) -> np.ndarray:
    """PIL image -> float32 array in 0..1 (H, W[, C])."""
    if isinstance(img, np.ndarray):
        return img.astype(np.float32)
    return np.asarray(img, dtype=np.float32) / 255.0


def pil(a: np.ndarray, mode: str | None = None) -> Image.Image:
    """float array in 0..1 -> PIL image (RGB, RGBA or L)."""
    a = np.clip(np.nan_to_num(a), 0, 1)
    u8 = (a * 255.0 + 0.5).astype(np.uint8)
    if u8.ndim == 3 and u8.shape[2] == 1:
        u8 = u8[..., 0]
    return Image.fromarray(u8, mode) if mode else Image.fromarray(u8)


def srgb2lin(a: np.ndarray) -> np.ndarray:
    a = np.clip(a, 0, None)
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4).astype(np.float32)


def lin2srgb(a: np.ndarray) -> np.ndarray:
    a = np.clip(a, 0, None)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(a, 1 / 2.4) - 0.055).astype(np.float32)


def hexcol(h: str, linear: bool = True) -> np.ndarray:
    h = h.lstrip('#')
    c = np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)
    return srgb2lin(c) if linear else c


def save_jpeg(img: Image.Image, path, quality: int = 84, max_kb: int = 900) -> int:
    """Progressive JPEG; lowers the quality a little if the file would be over max_kb. Returns bytes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img = img.convert('RGB')
    q = quality
    while True:
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=q, progressive=True, optimize=True, subsampling='4:2:0')
        if buf.tell() <= max_kb * 1024 or q <= 60:
            break
        q -= 2
    path.write_bytes(buf.getvalue())
    return buf.tell()


# --------------------------------------------------------------------------
# small maths / filters
# --------------------------------------------------------------------------
def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, np.float32) - e0) / (e1 - e0 + 1e-9), 0, 1)
    return t * t * (3 - 2 * t)


def lum(a: np.ndarray) -> np.ndarray:
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def _box1d(a: np.ndarray, r: int, axis: int) -> np.ndarray:
    if r <= 0:
        return a
    n = a.shape[axis]
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    p = np.pad(a, pad, mode='edge')
    c = np.cumsum(p, axis=axis, dtype=np.float64)
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def blur(a: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur (3 box passes per axis) for float arrays (H, W) or (H, W, C)."""
    a = np.asarray(a, np.float32)
    if sigma <= 0.3:
        return a.copy()
    # box radius for 3 passes approximating sigma
    w = math.sqrt(12 * sigma * sigma / 3 + 1)
    r = max(1, int(round((w - 1) / 2)))
    out = a
    for axis in (0, 1):
        for _ in range(3):
            out = _box1d(out, r, axis)
    return out


def value_noise(w: int, h: int, cell: float, seed: int, octaves: int = 1, persistence: float = 0.5) -> np.ndarray:
    """Smooth noise in 0..1 (bicubic-upsampled random grid), fractal with octaves."""
    rng = np.random.default_rng(seed)
    total = np.zeros((h, w), np.float32)
    amp, norm, c = 1.0, 0.0, float(cell)
    for _ in range(octaves):
        gw, gh = max(2, int(w / c) + 3), max(2, int(h / c) + 3)
        g = rng.random((gh, gw)).astype(np.float32)
        im = Image.fromarray(g, 'F').resize((int(gw * c), int(gh * c)), BICUBIC)
        ox, oy = int(rng.integers(0, max(1, int(c)))), int(rng.integers(0, max(1, int(c))))
        arr = np.asarray(im, np.float32)[oy:oy + h, ox:ox + w]
        total += amp * arr
        norm += amp
        amp *= persistence
        c = max(1.5, c / 2)
    total /= norm
    lo, hi = np.percentile(total, 1), np.percentile(total, 99)
    return np.clip((total - lo) / (hi - lo + 1e-6), 0, 1)


def resize_f(a: np.ndarray, w: int, h: int, resample=BILINEAR) -> np.ndarray:
    """Resize a float array (H, W) or (H, W, C) with PIL (per channel, 'F' mode)."""
    a = np.asarray(a, np.float32)
    if a.ndim == 2:
        return np.asarray(Image.fromarray(a, 'F').resize((w, h), resample), np.float32)
    return np.stack([resize_f(a[..., i], w, h, resample) for i in range(a.shape[2])], -1)


# --------------------------------------------------------------------------
# texture prep
# --------------------------------------------------------------------------
def flatten_light(a: np.ndarray, sigma: float) -> np.ndarray:
    """Remove slow lighting gradients from a photographed sample (keeps the mean)."""
    L = lum(a)[..., None] + 1e-3
    low = blur(L, sigma)
    return np.clip(a * (L.mean() / low), 0, 1)


def match_albedo(a: np.ndarray, mean: float | None = None, sat: float | None = None,
                 tint=None, contrast: float | None = None) -> np.ndarray:
    """Colour-match a texture (sRGB 0..1) to the scene: mean luminance, saturation,
    tint (multiplied, sRGB triple) and contrast around the mean."""
    a = np.asarray(a, np.float32)
    L = lum(a)[..., None]
    if sat is not None:
        a = L + (a - L) * sat
    if contrast is not None:
        m = L.mean()
        a = m + (a - m) * contrast
    if tint is not None:
        a = a * np.asarray(tint, np.float32)
    if mean is not None:
        a = a * (mean / max(1e-4, float(lum(a).mean())))
    return np.clip(a, 0, 1)


def find_period(a: np.ndarray, axis: int, lo: int, hi: int) -> int:
    """Pattern repeat (pixels) along an axis, from the autocorrelation of luminance."""
    L = lum(a) if a.ndim == 3 else a
    L = L - L.mean()
    best, best_s = lo, -1e9
    n = L.shape[axis]
    for p in range(lo, min(hi, n - 8)):
        if axis == 0:
            x, y = L[:-p], L[p:]
        else:
            x, y = L[:, :-p], L[:, p:]
        s = float((x * y).mean() / (x.std() * y.std() + 1e-6))
        if s > best_s:
            best_s, best = s, p
    return best


def make_seamless(a: np.ndarray, px: int | None = None, py: int | None = None, blend: float = 0.12) -> np.ndarray:
    """Crop one repeat (px x py, defaults = whole image) and crossfade its borders so it tiles."""
    a = np.asarray(a, np.float32)
    h, w = a.shape[:2]
    px = px or w
    py = py or h
    bx, by = max(2, int(px * blend)), max(2, int(py * blend))
    if px + bx > w:
        bx = max(2, (w - px) if w > px else int(px * blend))
    if py + by > h:
        by = max(2, (h - py) if h > py else int(py * blend))
    out = a[:py + by, :px + bx].copy() if (px + bx <= w and py + by <= h) else None
    if out is None:  # whole-image mode: mirror-free offset blend
        tile = a[:py, :px].copy()
        sh = np.roll(np.roll(tile, py // 2, 0), px // 2, 1)
        m = np.ones((py, px), np.float32)
        yy = np.minimum(np.arange(py), py - 1 - np.arange(py))[:, None]
        xx = np.minimum(np.arange(px), px - 1 - np.arange(px))[None, :]
        m = np.clip(np.minimum(yy / by, xx / bx), 0, 1)
        m = m * m * (3 - 2 * m)
        if a.ndim == 3:
            m = m[..., None]
        return tile * m + sh * (1 - m)
    # proper period crop: fade the extra margin back over the start
    t = out[:, :px].copy()
    ramp = np.linspace(0, 1, bx, dtype=np.float32)
    ramp = ramp * ramp * (3 - 2 * ramp)
    r = ramp[None, :, None] if a.ndim == 3 else ramp[None, :]
    t[:, :bx] = out[:, px:px + bx] * (1 - r) + out[:, :bx] * r
    t2 = t[:py].copy()
    ramp = np.linspace(0, 1, by, dtype=np.float32)
    ramp = ramp * ramp * (3 - 2 * ramp)
    r = ramp[:, None, None] if a.ndim == 3 else ramp[:, None]
    t2[:by] = t[py:py + by] * (1 - r) + t[:by] * r
    return t2


def tile(tex: np.ndarray, w: int, h: int, seed: int = 0, offset=None, tone_var: float = 0.0,
         tone_cell: float | None = None, scale: float = 1.0) -> np.ndarray:
    """Cover w x h by wrap-tiling `tex` (float, already seamless), with a random offset and a
    soft multiplicative tone variation (+-tone_var) so the repeat never reads."""
    tex = np.asarray(tex, np.float32)
    if scale != 1.0:
        th, tw = tex.shape[:2]
        tex = resize_f(tex, max(2, round(tw * scale)), max(2, round(th * scale)), BICUBIC)
    th, tw = tex.shape[:2]
    rng = np.random.default_rng(seed)
    ox, oy = offset if offset is not None else (int(rng.integers(0, tw)), int(rng.integers(0, th)))
    ys = (np.arange(h) + oy) % th
    xs = (np.arange(w) + ox) % tw
    out = tex[ys][:, xs]
    if tone_var > 0:
        cell = tone_cell or max(tw, th) * 0.7
        n = value_noise(w, h, cell, seed + 101, octaves=2) * 2 - 1
        f = 1 + tone_var * n
        out = out * (f[..., None] if out.ndim == 3 else f)
    return np.clip(out, 0, 1)


def flip_tile(tex: np.ndarray) -> np.ndarray:
    """2x2 mirrored tile (seamless for any photo; use only where the mirror does not read)."""
    top = np.concatenate([tex, tex[:, ::-1]], 1)
    return np.concatenate([top, top[::-1]], 0)


# --------------------------------------------------------------------------
# camera + perspective
# --------------------------------------------------------------------------
def persp_coeffs(dst, src):
    """8 PIL PERSPECTIVE coefficients mapping output points dst[i] -> input points src[i]."""
    A, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    return np.linalg.solve(np.array(A, np.float64), np.array(b, np.float64)).tolist()


class Camera:
    """Pinhole camera. Image coordinates are in OUTPUT pixels (e.g. 2400 x 900);
    the renderer works at `ss` times that (supersampling)."""

    def __init__(self, width: int, height: int, f: float, cx: float, cy: float, eye: float, ss: int = 2):
        self.width, self.height, self.ss = width, height, ss
        self.f, self.cx, self.cy, self.eye = f, cx, cy, eye
        self.W, self.H = width * ss, height * ss

    # output-pixel projection (what the game sees)
    def project(self, P):
        P = np.asarray(P, np.float64)
        X, Y, Z = P[..., 0], P[..., 1], P[..., 2]
        return np.stack([self.cx + self.f * X / Z, self.cy - self.f * (Y - self.eye) / Z], -1)

    def project_ss(self, P):
        return self.project(P) * self.ss

    def unproject(self, u, v, Z):
        """output pixel (u, v) at depth Z -> world point."""
        return np.array([(u - self.cx) * Z / self.f, self.eye - (v - self.cy) * Z / self.f, Z], np.float64)

    def on_plane_y(self, u, v, Y):
        """world point on the horizontal plane Y seen at output pixel (u, v)."""
        Z = self.f * (self.eye - Y) / (v - self.cy)
        return self.unproject(u, v, Z)

    def rays(self, x0, y0, w, h):
        """unit-less ray directions (dz = 1) for the SS pixel centres of a bbox."""
        xs = (np.arange(x0, x0 + w, dtype=np.float32) + 0.5) / self.ss
        ys = (np.arange(y0, y0 + h, dtype=np.float32) + 0.5) / self.ss
        dx = (xs - self.cx) / self.f
        dy = -(ys - self.cy) / self.f
        D = np.empty((h, w, 3), np.float32)
        D[..., 0] = dx[None, :]
        D[..., 1] = dy[:, None]
        D[..., 2] = 1.0
        return D

    @property
    def origin(self):
        return np.array([0.0, self.eye, 0.0], np.float32)

    def viewpoint(self):
        """the eye as a float64 world point (which side of a surface the camera is on)."""
        return np.array([0.0, self.eye, 0.0])

    def depth(self, P):
        """distance in front of the camera along its view axis."""
        return np.asarray(P, np.float64)[..., 2]


class PoseCamera(Camera):
    """A pinhole camera anywhere, looking anywhere (CAM 7 looks down at the desk room from a high corner).
    pos: the eye (world metres); look_at: the point it looks at; roll stays level with the floor.
    Image coordinates and `ss` work exactly like Camera."""

    def __init__(self, width, height, f, cx, cy, pos, look_at, ss=2):
        super().__init__(width, height, f, cx, cy, float(pos[1]), ss=ss)
        self.pos = np.asarray(pos, np.float64)
        fwd = np.asarray(look_at, np.float64) - self.pos
        fwd /= np.linalg.norm(fwd)
        right = np.cross(np.array([0.0, 1.0, 0.0]), fwd)
        right /= np.linalg.norm(right)
        up = np.cross(fwd, right)
        self.R = np.stack([right, up, fwd])            # rows: camera x (right), y (up), z (forward)

    def to_cam(self, P):
        return (np.asarray(P, np.float64) - self.pos) @ self.R.T

    def project(self, P):
        Q = self.to_cam(P)
        return np.stack([self.cx + self.f * Q[..., 0] / Q[..., 2], self.cy - self.f * Q[..., 1] / Q[..., 2]], -1)

    def rays(self, x0, y0, w, h):
        D = super().rays(x0, y0, w, h)                 # camera-space directions (dz = 1)
        return (D.reshape(-1, 3) @ self.R.astype(np.float32)).reshape(h, w, 3)

    @property
    def origin(self):
        return self.pos.astype(np.float32)

    def viewpoint(self):
        return self.pos.copy()

    def depth(self, P):
        return self.to_cam(P)[..., 2]


# --------------------------------------------------------------------------
# lights
# --------------------------------------------------------------------------
def _ray_box_block(P, Ldir, Ldist, bmin, bmax, eps=2e-3):
    """bool (n,): does the segment P -> P + Ldir*Ldist pass through the box?"""
    inv = 1.0 / np.where(np.abs(Ldir) < 1e-9, 1e-9, Ldir)
    t1 = (bmin[None, :] - P) * inv
    t2 = (bmax[None, :] - P) * inv
    tmin = np.max(np.minimum(t1, t2), axis=1)
    tmax = np.min(np.maximum(t1, t2), axis=1)
    return (tmax >= np.maximum(tmin, eps)) & (tmin < Ldist - eps)


class PointLight:
    """Point light with soft inverse-square falloff.
    pattern(dir_from_light (n,3)) -> (n,) shapes the emission (lamp shades, screens).
    wrap: 0 = Lambert, >0 lets light wrap softly past the terminator.
    shadow_px: penumbra blur (output px) of ray-cast box shadows; None = no shadows."""

    def __init__(self, pos, color, power, soft=0.15, pattern=None, wrap=0.15, shadow_px=3.0,
                 ignore=(), name=''):
        self.pos = np.asarray(pos, np.float32)
        self.color = np.asarray(color, np.float32)
        self.power, self.soft, self.pattern, self.wrap = power, soft, pattern, wrap
        self.shadow_px, self.ignore, self.name = shadow_px, set(ignore), name

    def irradiance(self, P, N, scene, grid_shape, mask_ignore=()):
        L = self.pos[None, :] - P
        d2 = (L * L).sum(1)
        d = np.sqrt(d2) + 1e-6
        Ln = L / d[:, None]
        cos = (N * Ln).sum(1)
        w = self.wrap
        cos = np.clip((cos + w) / (1 + w), 0, None)
        e = self.power * cos / (d2 + self.soft ** 2)
        if self.pattern is not None:
            e = e * self.pattern(-Ln)
        if self.shadow_px is not None and scene.occluders:
            vis = np.ones(P.shape[0], np.float32)
            active = e > 1e-5
            if active.any():
                Pa, La, da = P[active], Ln[active], d[active]
                blk = np.zeros(Pa.shape[0], bool)
                for name, bmin, bmax in scene.occluders:
                    if name in self.ignore or name in mask_ignore:
                        continue
                    blk |= _ray_box_block(Pa, La, da, bmin, bmax)
                vis[active] = (~blk).astype(np.float32)
            if self.shadow_px > 0 and grid_shape is not None:
                vis = blur(vis.reshape(grid_shape), self.shadow_px * scene.cam.ss).reshape(-1)
            e = e * vis
        return e[:, None] * self.color[None, :]


class ApertureLight:
    """Directional light (the moon) that only enters through an aperture (a window):
    aperture(points_on_window_plane (n,3)) -> (n,) transmission in 0..1."""

    def __init__(self, direction, color, power, plane_z, aperture, shadow_px=2.0, ignore=(), name=''):
        d = np.asarray(direction, np.float32)
        self.dir = d / np.linalg.norm(d)          # direction the light travels
        self.color = np.asarray(color, np.float32)
        self.power, self.plane_z, self.aperture = power, plane_z, aperture
        self.shadow_px, self.ignore, self.name = shadow_px, set(ignore), name

    def irradiance(self, P, N, scene, grid_shape, mask_ignore=()):
        Ln = -self.dir[None, :].repeat(P.shape[0], 0)
        cos = np.clip((N * Ln).sum(1), 0, None)
        t = (self.plane_z - P[:, 2]) / Ln[:, 2]
        Q = P + Ln * t[:, None]
        tr = np.where(t > 0, self.aperture(Q), 0.0).astype(np.float32)
        e = self.power * cos * tr
        act = e > 1e-5
        if scene.occluders and act.any():
            blk = np.zeros(int(act.sum()), bool)
            for name, bmin, bmax in scene.occluders:
                if name in self.ignore or name in mask_ignore:
                    continue
                blk |= _ray_box_block(P[act], Ln[act], t[act], bmin, bmax)
            v = np.ones(P.shape[0], np.float32)
            v[act] = (~blk).astype(np.float32)
            e = e * v
        if self.shadow_px and grid_shape is not None:
            e = blur(e.reshape(grid_shape), self.shadow_px * scene.cam.ss).reshape(-1)
        return e[:, None] * self.color[None, :]


# --------------------------------------------------------------------------
# AO helpers (texture space of a quad, in metres)
# --------------------------------------------------------------------------
def edge_ao(w_m, h_m, res, edges=None, blobs=(), rects=()):
    """Ambient-occlusion multiplier map (h, w) for a quad w_m x h_m metres at `res` px/m.
    edges: {'top'|'bottom'|'left'|'right': (strength, radius_m)} - darkening along a crease.
    blobs: [(x_m, y_m, rx_m, ry_m, strength)] soft elliptical contact shadows.
    rects: [(x0, y0, x1, y1, strength, soft_m)] soft rectangles (under furniture)."""
    W, H = max(2, int(round(w_m * res))), max(2, int(round(h_m * res)))
    x = (np.arange(W, dtype=np.float32) + 0.5) / res
    y = (np.arange(H, dtype=np.float32) + 0.5) / res
    X, Y = np.meshgrid(x, y)
    ao = np.ones((H, W), np.float32)
    for k, (s, r) in (edges or {}).items():
        dist = {'top': Y, 'bottom': h_m - Y, 'left': X, 'right': w_m - X}[k]
        ao *= 1 - s * np.exp(-dist / max(1e-4, r))
    for (bx, by, rx, ry, s) in blobs:
        d2 = ((X - bx) / rx) ** 2 + ((Y - by) / ry) ** 2
        ao *= 1 - s * np.exp(-d2 * 1.6)
    for (x0, y0, x1, y1, s, soft) in rects:
        dx = np.maximum(np.maximum(x0 - X, X - x1), 0)
        dy = np.maximum(np.maximum(y0 - Y, Y - y1), 0)
        d = np.sqrt(dx * dx + dy * dy)
        ao *= 1 - s * np.exp(-(d / max(soft, 1e-3)) ** 2)
    return np.clip(ao, 0, 1)


# --------------------------------------------------------------------------
# the scene renderer
# --------------------------------------------------------------------------
class Scene:
    """Back-to-front quad renderer with per-pixel lighting.

    canvas: linear radiance (H, W, 3) at ss resolution.
    ambient: callable(P, N) -> (n, 3) irradiance, or an RGB triple.
    occluders: [(name, min_xyz, max_xyz)] boxes that cast shadows from every light.
    """

    def __init__(self, cam: Camera, ambient, background=(0, 0, 0)):
        self.cam = cam
        self.canvas = np.zeros((cam.H, cam.W, 3), np.float32)
        self.canvas[:] = np.asarray(background, np.float32)
        self.depth_hint = None
        self.ambient = ambient
        self.lights = []
        self.occluders = []
        self.log = []

    def add_occluder(self, name, bmin, bmax):
        self.occluders.append((name, np.asarray(bmin, np.float32), np.asarray(bmax, np.float32)))

    # ---- quads ---------------------------------------------------------
    def draw_quad(self, corners, tex, *, alpha=None, ao=None, emissive=None, emit=1.0,
                  lit=True, spec=0.0, gloss=30.0, spec_tint=None, cull=False, light_ignore=(),
                  direct_ao=0.35, normal=None, opacity=1.0, extra_light=None, name=''):
        """Render one textured quad.

        corners: TL, TR, BR, BL world points (texture (0,0) is TL, (w,h) is BR).
        tex:     albedo, float sRGB array (h, w, 3) or PIL RGB image.
        alpha:   optional coverage (h', w') float 0..1 in texture space (any resolution).
        ao:      optional AO multiplier (texture space, any resolution); full on ambient,
                 `direct_ao` of it on direct light.
        emissive: optional float sRGB (h, w, 3) texture; radiance = srgb2lin(emissive) * emit.
        lit=False -> the albedo is shown as linear radiance srgb2lin(tex)*emit (sky, screens).
        spec: Blinn-Phong highlight strength (varnish, glass, brass).
        extra_light: callable(P, N) -> (n,3) irradiance added for this quad only.
        """
        cam = self.cam
        C = np.asarray(corners, np.float64)
        if (cam.depth(C) <= 0.02).any():
            raise ValueError(f'quad {name} crosses the camera plane')
        n = np.cross(C[1] - C[0], C[3] - C[0])
        n = n / (np.linalg.norm(n) + 1e-12)
        centre = C.mean(0)
        view = centre - cam.viewpoint()
        if np.dot(n, view) > 0:
            if cull:
                return
            n = -n
        if normal is not None:
            n = np.asarray(normal, np.float64)
            n = n / np.linalg.norm(n)
        S = cam.project_ss(C)                       # (4, 2) ss pixels
        x0 = int(max(0, math.floor(S[:, 0].min()) - 1))
        x1 = int(min(cam.W, math.ceil(S[:, 0].max()) + 1))
        y0 = int(max(0, math.floor(S[:, 1].min()) - 1))
        y1 = int(min(cam.H, math.ceil(S[:, 1].max()) + 1))
        if x1 <= x0 or y1 <= y0:
            return
        bw, bh = x1 - x0, y1 - y0

        timg = tex if isinstance(tex, Image.Image) else pil(np.asarray(tex)[..., :3])
        tw, th = timg.size
        dst = [(float(S[i, 0] - x0), float(S[i, 1] - y0)) for i in range(4)]
        srcp = [(0.0, 0.0), (float(tw), 0.0), (float(tw), float(th)), (0.0, float(th))]
        co = persp_coeffs(dst, srcp)

        def warp(arr_or_img, w_, h_):
            k = [co[0] * w_ / tw, co[1] * w_ / tw, co[2] * w_ / tw,
                 co[3] * h_ / th, co[4] * h_ / th, co[5] * h_ / th, co[6], co[7]]
            if isinstance(arr_or_img, Image.Image):
                return arr_or_img.transform((bw, bh), PERSPECTIVE, k, resample=BICUBIC)
            a = np.asarray(arr_or_img, np.float32)
            return np.asarray(Image.fromarray(a, 'F').transform((bw, bh), PERSPECTIVE, k, resample=BILINEAR),
                              np.float32)

        # coverage: the quad itself, times the optional alpha
        cov_src = np.ones((th, tw), np.float32)
        cov = warp(cov_src, tw, th)
        if alpha is not None:
            a = np.asarray(alpha, np.float32)
            cov = cov * np.clip(warp(a, a.shape[1], a.shape[0]), 0, 1)
        cov = np.clip(cov * opacity, 0, 1)
        if cov.max() <= 0.002:
            return
        rgb = f32(timg.convert('RGB').transform((bw, bh), PERSPECTIVE, co, resample=BICUBIC))
        alb = srgb2lin(rgb)
        m = cov > 0.002

        if not lit:
            out = alb * emit
        else:
            # world position of every bbox pixel on the quad's plane
            D = cam.rays(x0, y0, bw, bh)
            O = cam.origin
            dn = (D * n.astype(np.float32)).sum(-1)
            t = float(np.dot(n, C[0] - O)) / np.where(np.abs(dn) < 1e-9, 1e-9, dn)
            P = (O[None, None, :] + D * t[..., None]).reshape(-1, 3)
            N = np.broadcast_to(n.astype(np.float32), P.shape)
            aom = np.ones(bw * bh, np.float32)
            if ao is not None:
                aa = np.asarray(ao, np.float32)
                aom = np.clip(warp(aa, aa.shape[1], aa.shape[0]), 0, 1).reshape(-1)
                aom = np.where(m.reshape(-1), aom, 1)
            amb = self.ambient(P, N) if callable(self.ambient) else np.broadcast_to(
                np.asarray(self.ambient, np.float32), P.shape)
            E = amb * aom[:, None]
            dao = 1 - direct_ao * (1 - aom)
            Ed = np.zeros_like(P)
            for Lgt in self.lights:
                Ed += Lgt.irradiance(P, N, self, (bh, bw), light_ignore)
            if extra_light is not None:
                Ed += extra_light(P, N)
            E = E + Ed * dao[:, None]
            out = alb.reshape(-1, 3) * E
            if spec > 0:
                V = -(P - O[None, :])
                V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-9
                sp = np.zeros_like(P)
                for Lgt in self.lights:
                    if not isinstance(Lgt, PointLight):
                        continue
                    L = Lgt.pos[None, :] - P
                    d2 = (L * L).sum(1)
                    Ln = L / (np.sqrt(d2)[:, None] + 1e-9)
                    Hh = Ln + V
                    Hh /= np.linalg.norm(Hh, axis=1, keepdims=True) + 1e-9
                    nh = np.clip((N * Hh).sum(1), 0, 1)
                    pat = Lgt.pattern(-Ln) if Lgt.pattern is not None else 1.0
                    sp += (Lgt.power * pat * nh ** gloss / (d2 + Lgt.soft ** 2))[:, None] * Lgt.color[None, :]
                st = np.asarray(spec_tint if spec_tint is not None else (1, 1, 1), np.float32)
                out = out + sp * spec * st[None, :] * aom[:, None]
            out = out.reshape(bh, bw, 3)
        if emissive is not None:
            eimg = emissive if isinstance(emissive, Image.Image) else pil(np.asarray(emissive)[..., :3])
            ew, eh = eimg.size
            k = [co[0] * ew / tw, co[1] * ew / tw, co[2] * ew / tw,
                 co[3] * eh / th, co[4] * eh / th, co[5] * eh / th, co[6], co[7]]
            e = f32(eimg.transform((bw, bh), PERSPECTIVE, k, resample=BICUBIC))
            out = out + srgb2lin(e) * emit
        reg = self.canvas[y0:y1, x0:x1]
        c3 = cov[..., None]
        reg[:] = out * c3 + reg * (1 - c3)
        self.log.append((name, x0, y0, bw, bh))

    def box(self, bmin, bmax, textures, *, res=600, occluder=True, name='', **kw):
        """Axis-aligned box: only the faces turned to the eye are drawn.
        textures: dict face -> callable(w_px, h_px, face) -> albedo array, or one callable for all.
        faces: 'front' (z=min), 'top' (y=max), 'bottom', 'left' (x=min), 'right' (x=max)."""
        x0, y0, z0 = bmin
        x1, y1, z1 = bmax
        vx, E, vz = self.cam.viewpoint()
        faces = []
        if z0 > vz:
            faces.append(('front', [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)], x1 - x0, y1 - y0))
        if y1 < E:
            faces.append(('top', [(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)], x1 - x0, z1 - z0))
        if y0 > E:
            faces.append(('bottom', [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], x1 - x0, z1 - z0))
        if x0 > vx:
            faces.append(('left', [(x0, y1, z1), (x0, y1, z0), (x0, y0, z0), (x0, y0, z1)], z1 - z0, y1 - y0))
        if x1 < vx:
            faces.append(('right', [(x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (x1, y0, z0)], z1 - z0, y1 - y0))
        for face, corners, wm, hm in faces:
            fn = textures.get(face) if isinstance(textures, dict) else textures
            if fn is None:
                continue
            wpx, hpx = max(2, int(round(wm * res))), max(2, int(round(hm * res)))
            spec = fn(wpx, hpx, face)
            if isinstance(spec, dict):
                tex = spec.pop('tex')
                opts = dict(kw)
                opts.update(spec)
            else:
                tex, opts = spec, dict(kw)
            self.draw_quad(corners, tex, name=f'{name}.{face}', **opts)
        if occluder:
            self.add_occluder(name, bmin, bmax)

    # ---- screen-space helpers -------------------------------------------
    def add_screen(self, rgb_lin, alpha=None, at=(0, 0), mode='over'):
        """Composite a screen-space layer (ss pixels) at `at`: 'over' or 'add'."""
        h, w = rgb_lin.shape[:2]
        x, y = at
        xa, ya = max(0, x), max(0, y)
        xb, yb = min(self.cam.W, x + w), min(self.cam.H, y + h)
        if xb <= xa or yb <= ya:
            return
        src = rgb_lin[ya - y:yb - y, xa - x:xb - x]
        reg = self.canvas[ya:yb, xa:xb]
        if mode == 'add':
            a = 1.0 if alpha is None else alpha[ya - y:yb - y, xa - x:xb - x][..., None]
            reg += src * a
        elif mode == 'multiply':
            a = 1.0 if alpha is None else alpha[ya - y:yb - y, xa - x:xb - x][..., None]
            reg[:] = reg * (1 - a) + reg * src * a
        else:
            a = alpha[ya - y:yb - y, xa - x:xb - x][..., None]
            reg[:] = src * a + reg * (1 - a)

    def glow(self, cx, cy, radius, color_lin, strength, falloff=2.0):
        """Additive radial glow centred at OUTPUT pixel (cx, cy), radius in output px."""
        ss = self.cam.ss
        r = radius * ss
        x0, x1 = int(max(0, cx * ss - r)), int(min(self.cam.W, cx * ss + r))
        y0, y1 = int(max(0, cy * ss - r)), int(min(self.cam.H, cy * ss + r))
        if x1 <= x0 or y1 <= y0:
            return
        X, Y = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        d = np.sqrt((X - cx * ss) ** 2 + (Y - cy * ss) ** 2) / r
        g = np.clip(1 - d, 0, 1) ** falloff
        self.canvas[y0:y1, x0:x1] += (g * strength)[..., None] * np.asarray(color_lin, np.float32)

    def poly_mask(self, pts_out, blur_px=0.0):
        """Full-canvas float mask of a polygon given in OUTPUT pixels."""
        ss = self.cam.ss
        im = Image.new('L', (self.cam.W, self.cam.H), 0)
        ImageDraw.Draw(im).polygon([(x * ss, y * ss) for x, y in pts_out], fill=255)
        m = f32(im)
        return blur(m, blur_px * ss) if blur_px > 0 else m

    def downsample(self) -> np.ndarray:
        """ss canvas -> output resolution (box filter; the supersampled edges become clean AA)."""
        s = self.cam.ss
        H, W = self.cam.height, self.cam.width
        return self.canvas[:H * s, :W * s].reshape(H, s, W, s, 3).mean((1, 3)).astype(np.float32)


# --------------------------------------------------------------------------
# text + misc drawing
# --------------------------------------------------------------------------
def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def text_mask(text: str, fnt, pad: int = 8, spacing: int = 0) -> np.ndarray:
    """Float mask (h, w) of `text` set in `fnt` (tight, with padding)."""
    l, t, r, b = fnt.getbbox(text)
    im = Image.new('L', (r - l + 2 * pad, b - t + 2 * pad), 0)
    ImageDraw.Draw(im).text((pad - l, pad - t), text, font=fnt, fill=255)
    return f32(im)


def rect_mask(w, h, x0, y0, x1, y1, soft=0.0):
    """Float mask (h, w) of an axis-aligned rectangle with an optional feather (px)."""
    X = np.arange(w, dtype=np.float32)[None, :] + 0.5
    Y = np.arange(h, dtype=np.float32)[:, None] + 0.5
    if soft <= 0:
        return ((X >= x0) & (X < x1) & (Y >= y0) & (Y < y1)).astype(np.float32)
    dx = np.minimum(X - x0, x1 - X)
    dy = np.minimum(Y - y0, y1 - Y)
    return np.clip(np.minimum(dx, dy) / soft + 0.5, 0, 1)


def paste_over(base: np.ndarray, layer: np.ndarray, alpha: np.ndarray, x: int, y: int) -> None:
    """In-place alpha paste of a float layer onto a float base (clipped to the base)."""
    h, w = layer.shape[:2]
    H, W = base.shape[:2]
    xa, ya, xb, yb = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if xb <= xa or yb <= ya:
        return
    a = alpha[ya - y:yb - y, xa - x:xb - x]
    if base.ndim == 3:
        a = a[..., None]
    base[ya:yb, xa:xb] = layer[ya - y:yb - y, xa - x:xb - x] * a + base[ya:yb, xa:xb] * (1 - a)
