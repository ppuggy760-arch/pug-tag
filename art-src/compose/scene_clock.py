"""THE ALARM CLOCK: clock.png, the twin-bell wind-up clock the game draws in the desk room, on the bedside table
and (big, ringing) on your quilt in the morning.

A real clock: Poly Haven's 'Alarm Clock 01' (a photoscanned model, CC0), its aqua paint turned the muted
crimson of the game's clock, seen straight on (so the game can draw its hands on a round dial), lit by a soft
neutral key from the upper left. Its hands are left out: the game draws them (the time is live). The game
multiplies it by the light of the room it stands in (CLOCK_LIGHT in game.js) and the grade is the shared finish,
kind 'prop' (no vignette, bloom or night tint: the room's own light is laid on in the game).

The numbers the game needs (CLOCK_PHOTO in game.js): the dial centre (cx, cy as fractions of the picture's width
and height), the radius of the round body and of the dial (fractions of its width). They are printed by a build.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import meshkit as M  # noqa: E402
from common import Camera, Scene, PointLight, lum  # noqa: E402
from grade import finish  # noqa: E402

OUT = 'clock.png'
W, H, SS = 460, 560, 2
CY = 0.604                                  # the dial centre's height (fraction of H)
CLOCK_RED = (0.40, 0.12, 0.14)
GEOMETRY = {}


def render(seed=3):
    m = M.Mesh('alarm_clock_01', skip=['hand'], recolor=M.recolor(CLOCK_RED, where='hue', hue=(0.45, 0.80, 0.74), keep=0.6))
    inst = m.place((0.0, 0.0, 1.0), yaw=0, height=0.17)
    dial = inst.xf(np.array([[0.0, 0.064597487449646, 0.0]]))[0]       # (the hands' pivot: the dial's axis)
    f = 3000.0
    cam = Camera(W, H, f, W / 2, H * CY, float(dial[1]), ss=SS)
    # the camera on the dial's axis: move the clock so its dial axis is at x = 0
    inst = m.place((-dial[0], 0.0, 1.0), yaw=0, height=0.17)
    sc = Scene(cam, (0.22, 0.21, 0.22))
    sc.lights.append(PointLight((-0.55, 0.55, 0.35), np.array([1.0, 0.97, 0.93], np.float32), 0.55, soft=0.25,
                                shadow_px=None, name='key'))
    sc.lights.append(PointLight((0.45, 0.30, 0.55), np.array([0.92, 0.94, 1.0], np.float32), 0.16, soft=0.3,
                                shadow_px=None, name='fill'))
    sc.lights.append(PointLight((0.20, 0.45, 1.35), np.array([1.0, 1.0, 1.0], np.float32), 0.10, soft=0.3,
                                shadow_px=None, name='rim'))
    ys, xs, P = M.draw_mesh(sc, inst, name='clock', spec=0.6, return_px=True)
    cov = np.zeros((cam.H, cam.W), np.float32)
    cov[ys, xs] = 1
    a = cov.reshape(H, SS, W, SS).mean((1, 3))
    lin = (sc.canvas * cov[..., None]).reshape(H, SS, W, SS, 3).mean((1, 3)) / np.maximum(a, 1e-4)[..., None]
    y = finish(lin, 'prop', seed=seed, return_array=True)
    # measure the dial (cream, round) and the round body around it, outward from the dial centre
    cx, cy = W / 2, H * CY
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    L = lum(y)
    face = (L > 0.45) & (a > 0.9)
    rf = np.percentile(r[face & (r < W * 0.4)], 99) if face.any() else 0
    band = (a > 0.5) & (np.abs(yy - cy) < 6)                       # the body's width along the dial's middle row
    rb = max(np.abs(xx[band] - cx).max(), rf) if band.any() else rf
    GEOMETRY.update(cx=round(cx / W, 4), cy=round(cy / H, 4), body=round(float(rb) / W, 4), face=round(float(rf) * 0.97 / W, 4))
    return y, a


def build(out_path):
    y, a = render()
    rgba = np.concatenate([np.clip(y, 0, 1), a[..., None]], -1)
    rgba = np.clip(rgba * 255 + 0.5, 0, 255).astype(np.uint8)
    rgba[rgba[..., 3] == 0, :3] = 0
    # (a 256-colour palette with alpha: 40 KB instead of 220, and the grain hides the steps; it loads before the
    # title screen, so it should be small)
    q = Image.fromarray(rgba, 'RGBA').quantize(colors=256, method=Image.Quantize.FASTOCTREE,
                                               dither=Image.Dither.FLOYDSTEINBERG)
    q.save(out_path, optimize=True)
    print('  clock.png: CLOCK_PHOTO =', GEOMETRY)
    return out_path


if __name__ == '__main__':
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/clock.png'))
