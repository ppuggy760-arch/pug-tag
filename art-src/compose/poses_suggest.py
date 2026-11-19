#!/usr/bin/env python3
"""Write poses_suggest.json: for each camera picture, three suggested stand spots for a ~1.9 m figure, the
vanishing point, the horizon and the floor lines (all from the same cameras the pictures are rendered with).

    python3 art-src/compose/poses_suggest.py      # -> art-src/compose/poses_suggest.json
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import camkit as K  # noqa: E402

CAMS = [('nursery', 'scene_cam1_nursery'), ('hall', 'scene_cam2_hall'), ('parlor', 'scene_cam3_parlor'),
        ('stairs', 'scene_cam4_stairs'), ('west', 'scene_cam5_west'), ('east', 'scene_cam6_east')]


def frac(u, v):
    return [round(float(u) / K.CW, 4), round(float(v) / K.CH, 4)]


def floor_lines(m, cam):
    """picture-fraction polylines where the floor (or the water) meets the walls."""
    out = {}
    g = vars(m)
    y0 = g.get('HW', 0.0) if m.__name__.endswith('parlor') else 0.0
    XL, XR = g.get('XL'), g.get('XR')
    zb = g.get('ZB', g.get('ZBK', None))
    if m.__name__.endswith('hall'):
        XL, XR = -g['HW'], g['HW']
        zb = None
    if m.__name__.endswith('stairs'):
        out['nosing_line'] = [frac(*cam.project((g['XL'], 0.0, g['STZ']))), frac(*cam.project((g['XL'], g['TOPY'], g['ZTOP'])))]
        out['landing_meets_blank_wall'] = [frac(*cam.project((g['XL'], g['TOPY'], g['ZW']))),
                                          frac(*cam.project((g['XS'], g['TOPY'], g['ZW'])))]
        return out
    zfar = zb if zb is not None else 60.0
    for name, X in (('left', XL), ('right', XR)):
        zn = max(0.5, cam.f * (cam.eye - y0) / (K.CH - cam.cy) * 0.98)
        a = cam.project((X, y0, zn))
        b = cam.project((X, y0, zfar))
        out[f'floor_meets_{name}_wall'] = [frac(*a), frac(*b)]
    if zb is not None:
        out['floor_meets_back_wall'] = [frac(*cam.project((XL, y0, zb))), frac(*cam.project((XR, y0, zb)))]
    return out


def main():
    data = {
        '_about': ('Suggested monster stand spots for the built-in camera pictures in nightmare/assets/scenes/ '
                   '(1824 x 1026). x, y, h use the game\'s monsters[].poses convention: fractions of the camera feed '
                   'box, which is exactly the picture (fitPicture keeps 1824 x 1026; camFeedBox draws it at '
                   'W*CAM_ZOOM x H*CAM_ZOOM = 1824 x 1026 screen px). x = middle of the body, y = where the feet are '
                   '(the bottom of the sprite), h = sprite height / picture height for a 1.9 m figure. Only '
                   'y 0.061 .. 0.939 is ever on screen (the box is shifted up 63 px) and the feed pans 224 px '
                   'sideways, so keep x within about 0.07 .. 0.93. The sprite fades out over its bottom 28 % '
                   '(softFrame), so the feet may sit a little lower (y + 0.01..0.03) if the legs look short. '
                   'h_of_y gives the height for feet anywhere on that room\'s main floor: h = k * (y - y_horizon).'),
        'picture': [K.CW, K.CH],
    }
    for cid, modname in CAMS:
        m = importlib.import_module(modname)
        cam = K.make_camera(m.F, m.CX, m.CY, m.EYE)
        ps = m.poses()
        labels = ['near', 'middle', 'far']
        g = vars(m)
        floor_y = 0.0
        entry = {
            'file': 'assets/scenes/' + m.OUT,
            'spots': {lab: p for lab, p in zip(labels, ps)},
            'vanishing_point': {'px': [m.CX, m.CY], 'frac': frac(m.CX, m.CY)},
            'horizon_y': round(m.CY / K.CH, 4),
            'camera': {'f_px': m.F, 'eye_m': m.EYE},
            'h_of_y': {'k': round(1.9 / (m.EYE - floor_y), 4), 'y_horizon': round(m.CY / K.CH, 4),
                       'note': 'feet on the ' + ('drowned floor, under the water' if cid == 'parlor' else
                                                ('hall floor (on a step, use the spots)' if cid == 'stairs'
                                                 else 'floor'))},
            'floor_lines': floor_lines(m, cam),
        }
        if cid == 'parlor':
            entry['note'] = ('the floor is under 0.40 m of water: the spots put the feet on the drowned floor '
                             '(the water hides the shins), so h is for a 1.9 m figure standing on the floor')
        if cid == 'stairs':
            entry['note'] = ('near = on the 4th step, middle = on the 10th step, far = on the landing in front of '
                             'the blank wall; a figure on the stairs stands higher than the hall floor')
        data[cid] = entry
    out = HERE / 'poses_suggest.json'
    out.write_text(json.dumps(data, indent=2))
    print('wrote', out)


if __name__ == '__main__':
    main()
