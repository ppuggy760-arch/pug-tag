"""ONE finish for every scene of "Until the Alarm" (see LOOK.md).

    from grade import finish
    img = finish(linear_rgb, 'room', seed=7)        # -> PIL RGB, ready to save

`linear_rgb` is the renderer's linear radiance (H, W, 3) float array; a PIL
image (or a float array marked srgb=True) is accepted too and is linearised
first, so a scene painted in plain sRGB still gets the identical finish.

Kinds share the same core (exposure -> bloom -> tone curve -> desaturate
toward violet -> night tint -> contrast -> vignette -> black lift -> grain):
  room          the default night look (office, halls, every doorway picture)
  door          = room (doorway / closed-door pictures)
  menu          = room, a touch more vignette
  bedroom_night = room
  cam           room + colder, slightly greener, a bit more contrast
                 (NO scanlines, REC text or static: the game adds its own)
  bedroom_day   the warm morning variant (amber light, softer lift)

All sizes are given for a 900 px tall picture and scale with the height,
so a 1026 px camera picture gets the same bloom and grain per pixel scale.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from common import blur, f32, lum, pil, srgb2lin, lin2srgb, smoothstep

# --------------------------------------------------------------------------
# the numbers (LOOK.md documents each one)
# --------------------------------------------------------------------------
CORE = dict(
    exposure=1.0,
    # bloom (linear light): what is brighter than `thresh` glows, at three radii
    bloom_thresh=0.42, bloom_knee=0.25,
    bloom_sigmas=(3.0, 11.0, 34.0),          # px at 900 px picture height
    bloom_weights=(0.22, 0.16, 0.12),
    bloom_tint=(1.0, 0.97, 1.02),
    # tone curve: Reinhard with a white point, then a gentle display S-curve
    white=3.2, s_curve=0.18,
    # colour: saturation kept, and the grey it desaturates toward (violet-grey)
    saturation=0.64, desat_tint=(0.96, 0.94, 1.06),
    # night tint: shadows cooled toward blue-violet, highlights left alone
    shadow_tint=(0.88, 0.87, 1.08), shadow_tint_amount=0.65,
    # warm practical lights keep their amber (they are the only warm accents)
    warm_keep=0.55,
    # vignette (same shape everywhere: an ellipse in normalised picture coordinates)
    vignette=0.36, vig_inner=0.42, vig_outer=1.18, vig_aspect=1.0,
    # black lift: the darkest pixel lands on #07050c, never pure black
    lift=(7 / 255, 5 / 255, 12 / 255),
    # fine monochrome film grain (sRGB 0..1 sigma at mid-grey), 1 px cells @ 900 px
    grain=0.018, grain_soft=0.55,
)

KINDS = {
    'room': {},
    'door': {},
    'bedroom_night': {},
    'menu': dict(vignette=0.42),
    'cam': dict(saturation=0.52, desat_tint=(0.93, 1.0, 1.0), shadow_tint=(0.80, 0.92, 1.0),
                s_curve=0.32, cam_grade=(0.90, 1.03, 0.97), exposure=1.05, vignette=0.40),
    # a cut-out prop the game lays over a room and lights itself (the photo alarm clock): the same tone curve,
    # colour, black lift and grain, but no vignette, no bloom and no night tint (the room's light is added in game)
    'prop': dict(vignette=0.0, bloom_weights=(0.0, 0.0, 0.0), shadow_tint_amount=0.0),
    'bedroom_day': dict(exposure=1.25, saturation=0.74, desat_tint=(1.04, 0.99, 0.94),
                        shadow_tint=(1.0, 0.94, 0.92), shadow_tint_amount=0.4,
                        day_grade=(1.10, 1.00, 0.86), lift=(14 / 255, 10 / 255, 12 / 255),
                        vignette=0.26, bloom_thresh=0.55),
}


def params(kind: str) -> dict:
    if kind not in KINDS:
        raise ValueError(f'unknown kind {kind!r}: {sorted(KINDS)}')
    p = dict(CORE)
    p.update(KINDS[kind])
    return p


def _bloom(x: np.ndarray, p: dict, scale: float) -> np.ndarray:
    L = lum(x)
    t, k = p['bloom_thresh'], p['bloom_knee']
    # soft knee: the glow starts gently instead of at a hard threshold
    soft = np.clip(L - t + k, 0, 2 * k) ** 2 / (4 * k + 1e-6)
    w = np.maximum(soft, L - t)
    bright = x * (w / np.maximum(L, 1e-4))[..., None]
    out = np.zeros_like(x)
    for s, wt in zip(p['bloom_sigmas'], p['bloom_weights']):
        out += blur(bright, s * scale) * wt
    return out * np.asarray(p['bloom_tint'], np.float32)


def finish(img, kind: str = 'room', seed: int = 1, srgb: bool = False, return_array: bool = False):
    """The shared finish. img: linear float (H, W, 3) [or PIL / srgb=True]. Returns PIL RGB."""
    p = params(kind)
    if isinstance(img, Image.Image):
        x = srgb2lin(f32(img.convert('RGB')))
    else:
        x = np.asarray(img, np.float32)
        if srgb:
            x = srgb2lin(x)
    H, W = x.shape[:2]
    scale = H / 900.0
    x = x * p['exposure']

    # 1. bloom on the light sources (linear light)
    x = x + _bloom(x, p, scale)

    # 2. tone curve (Reinhard with a white point keeps the lamp from clipping flat)
    wht = p['white']
    L = lum(x)[..., None]
    Lt = L * (1 + L / (wht * wht)) / (1 + L)
    x = x * (Lt / np.maximum(L, 1e-5))
    y = lin2srgb(np.clip(x, 0, None))

    # 3. colour: desaturate toward a violet grey, but let warm practicals keep some amber
    Ly = lum(y)[..., None]
    grey = Ly * np.asarray(p['desat_tint'], np.float32)
    warm = np.clip((y[..., 0:1] - y[..., 2:3]) * 2.2, 0, 1) * smoothstep(0.25, 0.7, Ly)
    sat = p['saturation'] + (1 - p['saturation']) * p['warm_keep'] * warm
    y = grey + (y - grey) * sat

    # 4. night tint: shadows and mids lean blue-violet
    st = np.asarray(p['shadow_tint'], np.float32)
    k = (1 - smoothstep(0.0, 0.75, Ly)) * p['shadow_tint_amount']
    y = y * (1 + (st - 1) * k)
    if 'cam_grade' in p:
        y = y * np.asarray(p['cam_grade'], np.float32)
    if 'day_grade' in p:
        y = y * np.asarray(p['day_grade'], np.float32)

    # 5. display S-curve (contrast around mid-grey)
    c = p['s_curve']
    y = np.clip(y, 0, 1)
    y = y + c * y * (1 - y) * (2 * y - 1)

    # 6. vignette (same ellipse on every picture, in normalised coordinates)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    nx = (xx + 0.5) / W * 2 - 1
    ny = ((yy + 0.5) / H * 2 - 1) * p['vig_aspect']
    r = np.sqrt(nx * nx + ny * ny)
    v = 1 - p['vignette'] * smoothstep(p['vig_inner'], p['vig_outer'], r)
    y = y * v[..., None]

    # 7. black lift (never pure black: #07050c)
    lift = np.asarray(p['lift'], np.float32)
    y = lift + (1 - lift) * y

    # 8. grain: fine, monochrome, strongest in the mid-tones
    rng = np.random.default_rng(seed)
    g = rng.standard_normal((H, W)).astype(np.float32)
    if p['grain_soft'] > 0:
        g = blur(g, p['grain_soft'] * scale)
        g /= g.std() + 1e-6
    Lg = lum(y)
    amp = p['grain'] * (0.35 + 2.6 * Lg * (1 - Lg))
    y = y + (g * amp)[..., None]
    y = np.clip(np.maximum(y, lift * 0.8), 0, 1)       # grain never digs below the lifted black
    if return_array:
        return y
    return pil(y)
