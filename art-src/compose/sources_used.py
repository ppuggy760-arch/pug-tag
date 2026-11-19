#!/usr/bin/env python3
"""Which source pictures end up in the game's built-in scenes, and the credit lines for them.

    python3 art-src/compose/sources_used.py trace [scene ...]   # rebuild into a temp folder, note every source each scene opens
                                                               #   -> art-src/compose/sources_used.json (the shipped files are untouched)
    python3 art-src/compose/sources_used.py credits             # print the config.js credits lines and the CREDITS.md table

The rebuild is the normal one (same seeds), so it also tells you whether the shipped files are still
bit-identical to a fresh build. Licences, authors and links come from sources/photos.json and textures.json.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT_JSON = HERE / 'sources_used.json'

# short, readable names for the credits (the source titles can be very long). Missing ones use the title.
NICE = {
    'fog_ph-misty-pines': 'Misty pine forest (outside the windows)',
    'hall_habs-blandair-empty-hall': 'Old photo: second-floor center hall, Blandair (beyond the west doorway)',
    'hall_habs-lyndhurst-gothic-enfilade': 'Old photo: first-floor hall, Lyndhurst (beyond the east doorway)',
    'moon_nasa-full-moon-photo': 'The full moon',
    'moon_nasa-lro-nearside': 'The moon picture in your bedroom',
    'painting_aivazovsky-moonlit-sea': '"A Moonlit Night at Sea" (painting, 1885)',
    'painting_bocklin-isle-of-the-dead': '"Island of the Dead" (painting)',
    'painting_christus-portrait-young-woman': '"Portrait of a Young Woman" (painting)',
    'painting_friedrich-moonrise-sea': '"Moonrise over the Sea" (painting)',
    'painting_friedrich-walk-at-dusk': '"A Walk at Dusk" (painting)',
    'painting_grimshaw-street-moonlight': '"Street Scene in Moonlight" (painting)',
    'painting_grimshaw-under-the-moonbeams': '"Under the Moonbeams" (painting)',
    'painting_hammershoi-artificial-light': '"Interior. Artificial Light" (painting)',
    'painting_hammershoi-four-rooms': '"The Four Rooms" (painting, 1914)',
    'painting_hammershoi-white-doors': '"White Doors" (painting, 1913)',
    'painting_kuindzhi-night-on-the-dnieper': '"Night on the Dnieper" (painting)',
    'painting_paul-portrait-young-girl-1840': '"Portrait of a Young Girl" (painting, 1840)',
    'painting_whistler-nocturne-chelsea': '"Nocturne, Grey and Silver (Chelsea Embankment, Winter)" (painting)',
    'paper_old-paper-stained': 'Old paper (the crayon drawing, letters)',
    'parlor_ph-oldhall-carved-mantel': 'The carved mantel in the Drowned Parlor (Old Hall)',
    'sky_ph-milky-way': 'Night sky (Rogland Clear Night)',
    'wallpaper_dark-green-damask': 'Wallpaper, sidewall, France 1875-1900 (the desk room)',
    'wallpaper_morris-daisy': '"Daisy" wallpaper',
    'wallpaper_morris-pomegranate': '"Fruit or Pomegranate" wallpaper',
    'wallpaper_nursery-rhymes-1876': '"Nursery Rhymes (1876)" wallpaper',
    'wallpaper_rijks-dark-umbel-design': 'Wallpaper with umbel flowers, butterflies and dragonflies',
    'fabric_quilt-green-wholecloth': 'Wholecloth quilt',
    'fabric_quilt-red-wool': 'Wholecloth calamanco quilt',
    'metal_brass-brushed': 'Brushed brass (Apollo 11 interior paint)',
    'misc_wallpaper-1880-gold-damask': 'Wallpaper, sidewall, ca. 1880 (CH 85010069)',
    'misc_wallpaper-1880-olive-floral': 'Wallpaper, sidewall, ca. 1880 (CH 85010039)',
    'misc_wallpaper-morris-blackthorn': '"Blackthorn" wallpaper',
    'misc_wallpaper-morris-trellis': '"Trellis" wallpaper',
    'misc_wallpaper-morris-willow': '"Willow Bough" wallpaper',
    'rug_lotto-lattice': "'Lotto' carpet",
    'rug_spanish-end-border': 'Carpet MET DP169907',
    'rug_spanish-medallions': 'Carpet MET DP169905',
    'rug_star-ushak': "'Star Ushak' carpet",
    'toy_saam-rocking-horse': 'Rocking horse with yellow halter (ca. 1900, the nursery)',
    'wallpaper_morris-st-james-acanthus': '"St. James" acanthus wallpaper (the carving on the desk room\'s picture frame)',
    'ArmChair_01': 'Victorian armchair (3-D scan: the parlor\'s armchairs and your chair on CAM 7)',
    'alarm_clock_01': 'Twin-bell alarm clock (3-D scan: the alarm clock)',
    'old_bed_frame': 'Old iron bed frame (3-D scan: the cot in the nursery)',
    'painted_wooden_nightstand': 'Painted wooden nightstand (3-D scan: the nursery)',
    'vintage_grandfather_clock_01': 'Grandfather clock (3-D scan: the Endless Hall)',
}
WHO = {  # shorter author lines
    'Historic American Buildings Survey (U.S. National Park Service); via Library of Congress': 'Historic American Buildings Survey (Library of Congress)',
    'Unknown author (released as public domain via The Digital Yard Sale)': 'unknown author (The Digital Yard Sale)',
    'Unknown artistUnknown artist': 'unknown artist (Cooper Hewitt)',
    'Unknown designer, ca. 1880 (Cooper Hewitt, Smithsonian Design Museum)': 'unknown designer, ca. 1880 (Cooper Hewitt)',
    '„H[einrich?] Paul“ (German, 19th Century)': 'H[einrich?] Paul (German, 19th century)',
    'William Morris / Morris & Co. (photo: The Metropolitan Museum of Art)': 'William Morris / Morris & Co. (The Met)',
    'William Morris / Morris & Co. / Philip Webb (photo: The Metropolitan Museum of Art)': 'William Morris, Philip Webb / Morris & Co. (The Met)',
    'NASA Smithsonian Institution': 'NASA / Smithsonian Institution',
    'Made by J. Zuber et Cie': 'J. Zuber et Cie (Cooper Hewitt)',
    'NASA Goddard Space Flight Center from Greenbelt, MD, USA': 'NASA/GSFC/Arizona State University',
}


def manifest():
    m = {}
    for kind in ('photos', 'textures'):
        for e in json.load(open(HERE.parent / 'sources' / f'{kind}.json')):
            m[f'{kind}/{e["file"]}'] = e
    for e in json.load(open(HERE.parent / 'sources' / 'models.json')):      # 3-D scans: one entry per model
        m[f'models/{e["file"]}'] = dict(e, file=e['file'] + '.npz')
    return m


def source_key(f):
    """a traced file -> its manifest key ('models/<id>/<id>_diff.jpg' -> 'models/<id>', '_ao' copies merged)."""
    if f.startswith('models/'):
        return '/'.join(f.split('/')[:2])
    return f.replace('_ao.jpg', '.jpg')


def trace(names):
    from PIL import Image
    import build_all
    import common
    src = str(common.SOURCES)
    used = set()
    _open = Image.open

    def op(fp, *a, **k):
        if str(fp).startswith(src):
            used.add(str(fp)[len(src) + 1:])
        return _open(fp, *a, **k)
    Image.open = op
    res = json.load(open(OUT_JSON)) if OUT_JSON.exists() else {}
    same = {}
    with tempfile.TemporaryDirectory() as tmp:
        for n in names or list(build_all.SCENES):
            used.clear()
            mod = importlib.import_module(build_all.SCENES[n])
            t = time.time()
            mod.build(Path(tmp) / mod.OUT)
            res[n] = sorted(used)
            print(f'{n:14s} {len(used):3d} sources  {time.time() - t:5.1f}s', flush=True)
        for f in sorted(Path(tmp).iterdir()):
            g = common.SCENES_OUT / f.name
            same[f.name] = g.exists() and hashlib.md5(f.read_bytes()).hexdigest() == hashlib.md5(g.read_bytes()).hexdigest()
    json.dump(res, open(OUT_JSON, 'w'), indent=1, sort_keys=True)
    print('same as the shipped file:', ', '.join(f'{k} {"yes" if v else "NO"}' for k, v in same.items()))


def credits():
    used = {}
    for scene, files in json.load(open(OUT_JSON)).items():
        for f in files:
            used.setdefault(source_key(f), set()).add(scene)
    man = manifest()
    rows = []
    for f in sorted(used, key=lambda f: (f.split('/')[1].split('_')[0] != 'painting', f)):
        e = man[f]
        slug = e['file'].rsplit('.', 1)[0]
        lic = e['license']
        short = 'CC0' if lic.startswith('CC0') else 'Public domain' if lic.lower().startswith('public domain') else lic
        if not (short in ('CC0', 'Public domain')):
            raise SystemExit(f'{f}: licence {lic!r} needs its exact attribution line')
        nice = NICE.get(slug) or (e['title'] + ' (texture)')
        rows.append(dict(what=nice, who=WHO.get(e['author'], e['author']), license=short, url=e['source_page'],
                         title=e['title'], full_license=lic, scenes=sorted(used[f])))
    print('// ---- config.js credits (paste after the fonts) ----')
    for r in rows:
        print('    { what: %s, who: %s, license: "%s", url: "%s" },' % (json.dumps('Picture: ' + r['what'], ensure_ascii=False), json.dumps(r['who'], ensure_ascii=False), r['license'], r['url']))
    print('\n<!-- ---- CREDITS.md table ---- -->')
    print('| Source | Author | License | Used in |\n|---|---|---|---|')
    for r in rows:
        title = r['title'].replace('|', '/').replace('_', ' ')
        print(f'| [{title}]({r["url"]}) | {r["who"]} | {r["full_license"]} | {", ".join(r["scenes"])} |')


if __name__ == '__main__':
    if sys.argv[1:2] == ['trace']:
        trace(sys.argv[2:])
    elif sys.argv[1:2] == ['credits']:
        credits()
    else:
        print(__doc__)
