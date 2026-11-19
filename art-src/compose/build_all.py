#!/usr/bin/env python3
"""Rebuild the photo-composited scenes of "Until the Alarm".

    python3 art-src/compose/build_all.py            # every scene
    python3 art-src/compose/build_all.py office     # just these
    python3 art-src/compose/build_all.py --list

Each scene is a module next to this file with
    OUT = 'office.jpg'          # file name inside nightmare/assets/scenes/
    def build(out_path): ...    # writes the picture (and returns its path)
Add a new scene by writing scene_<name>.py and adding one line to SCENES.
"""
from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import SCENES_OUT  # noqa: E402

# name -> module (scene_<name>.py). Keep in the order they should be built.
SCENES = {
    'office': 'scene_office',
    'doors': 'scene_doors',            # door_{left,right}_{dark,lit,closed}.jpg (360 x 630, all six)
    'bedroom': 'scene_bedroom',        # bedroom.jpg + bedroom_morning.jpg (1600 x 900)
    'cam7': 'scene_cam7',              # cam7_you.jpg (1824 x 1026)
    'menu': 'scene_menu',              # menu.jpg (1600 x 900) + menu_light.png + menu_fog.png
    'cam1_nursery': 'scene_cam1_nursery',    # the six camera rooms (1824 x 1026, kind 'cam')
    'cam2_hall': 'scene_cam2_hall',
    'cam3_parlor': 'scene_cam3_parlor',
    'cam4_stairs': 'scene_cam4_stairs',
    'cam5_west': 'scene_cam5_west',
    'cam6_east': 'scene_cam6_east',
    'paper': 'scene_paper',            # paper.jpg (380 x 460): the sheet the game's crayon drawing is drawn on
    'clock': 'scene_clock',            # clock.png (460 x 560, RGBA): the twin-bell alarm clock (the game draws its hands)
}


def build(names):
    SCENES_OUT.mkdir(parents=True, exist_ok=True)
    for name in names:
        mod = importlib.import_module(SCENES[name])
        out = SCENES_OUT / mod.OUT
        t = time.time()
        mod.build(out)
        kb = out.stat().st_size / 1024
        print(f'{name:16s} -> {out.relative_to(SCENES_OUT.parent.parent.parent)}  {kb:6.0f} KB  {time.time() - t:5.1f}s')
        if kb > 900:
            print(f'  WARNING: {out.name} is over 900 KB')


def main(argv):
    if '--list' in argv:
        print('\n'.join(SCENES))
        return 0
    names = [a for a in argv if not a.startswith('-')] or list(SCENES)
    bad = [n for n in names if n not in SCENES]
    if bad:
        print('unknown scene(s):', ', '.join(bad), '\nknown:', ', '.join(SCENES))
        return 2
    build(names)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
