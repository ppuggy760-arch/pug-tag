#!/usr/bin/env python3
"""The sheet of old paper the game's crayon drawing is drawn on (paper.jpg, 380 x 460).

The drawing itself (a house at night under a huge moon, one lit window, the front door
left open, "he walks at night") is drawn on top of this sheet by the game, in crayon
strokes (paintKidDrawing in js/game.js). It hangs on the desk-room wall and turns up on
your bedside table after Night 3. There is NO monster in it, on purpose: the monster is
only ever seen in the real game.

Source: sources/photos/paper_old-paper-stained.jpg ("Old paper6.jpg", public domain),
cropped, a little less yellow, and lightly darkened at the edges like a sheet that has
been handled a lot.

    python3 art-src/compose/build_all.py paper
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import f32, load, save_jpeg, LANCZOS, smoothstep, value_noise  # noqa: E402

OUT = 'paper.jpg'
SIZE = (380, 460)          # 2x the size it is shown at on the desk-room wall (190 x 230)


def render() -> Image.Image:
    src = load('paper_old-paper-stained')                  # 1098 x 1600, portrait
    w, h = src.size
    aspect = SIZE[0] / SIZE[1]
    x0, x1 = 40, w - 120                                    # (inside the scan's own ragged left and ribbed right edge)
    cw = x1 - x0
    ch = round(cw / aspect)
    top = round((h - ch) * 0.45)
    a = f32(src.crop((x0, top, x1, top + ch)).resize(SIZE, LANCZOS))
    # a little less yellow (the stain stays), a touch lighter
    L = (a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722)[..., None]
    a = L + (a - L) * 0.72
    a = a * np.array([1.0, 0.985, 0.95], np.float32) * 1.03
    # handled edges: darker toward the rim (soft, uneven)
    yy, xx = np.mgrid[0:SIZE[1], 0:SIZE[0]].astype(np.float32)
    d = np.minimum.reduce([xx, yy, SIZE[0] - 1 - xx, SIZE[1] - 1 - yy]) / 26.0
    wob = value_noise(SIZE[0], SIZE[1], 40, seed=31, octaves=2)
    edge = 1 - 0.16 * (1 - smoothstep(0.0, 1.0, d * (0.45 + 1.1 * wob)))
    a = a * edge[..., None]
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB')


def build(out_path):
    save_jpeg(render(), out_path, quality=86, max_kb=60)
    return out_path


if __name__ == '__main__':
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/paper.png')
    render().save(out)
    print(out)
