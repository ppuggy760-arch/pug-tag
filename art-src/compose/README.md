# art-src/compose: the photo-composited scenes

These scripts build the game's **built-in stand-in pictures** from real photos
and textures (wood, plaster, wallpaper, velvet, carpets, brass, old paintings,
NASA's moon, old-house photos...). They live in `nightmare/assets/scenes/` and
are shown whenever the creator has not drawn their own picture into
`nightmare/assets/rooms/` yet. Never write into `assets/rooms/` from here.

## Rebuild

From the repository root (`pug-tag-build/`):

    python3 art-src/compose/build_all.py            # every scene
    python3 art-src/compose/build_all.py office     # only these scenes
    python3 art-src/compose/build_all.py --list

Needs only Python 3 with Pillow and numpy. The office takes about 45 s on
4 CPUs and about 1.2 GB of memory (it renders at 2x and shrinks at the end).
Output: progressive JPEG, quality 84, every file under 900 KB.

A scene module can also be run by itself to write a PNG preview and its
linear render (`.lin.npy`, handy for trying grade changes without re-rendering):

    python3 art-src/compose/scene_office.py /tmp/office.png

## Files

| file | what it is |
|---|---|
| `common.py` | the toolkit: IO, blur/noise, texture prep (flatten, colour-match, seamless, tile), camera, perspective quads, lights, shadows, AO |
| `grade.py` | **one** `finish(img, kind)` for every picture (the look; see LOOK.md) |
| `build_all.py` | the scene registry and the rebuild command |
| `scene_office.py` | the desk room (2400 x 900), the hero scene that set the look |
| `meshkit.py` | real furniture: draws photoscanned 3-D models (CC0, Poly Haven) into a scene with its own camera, lights, shadows and ambient (a small z-buffered rasteriser), plus contact shadows |
| `scene_clock.py` | `clock.png`, the twin-bell alarm clock the game draws (a scanned model, no hands: the game draws them) |
| `../sources/models/` | the 3-D scans (geometry re-saved as `.npz`, textures re-encoded) + `models.json` (licence, author, page) |
| `LOOK.md` | the look bible as numbers: grade, lights, palette, scale, rules |
| `../sources/` | curated, re-encoded source images + `textures.json` / `photos.json` (licence, author, source page of each) |

**Note:** the source images and 3-D scans themselves are not in this repository (they are about 62 MB, and the game never uses them). `textures.json`, `photos.json` and `models.json` list every one with its licence, source page and `download_url`. To rebuild the scenes, download them into `art-src/sources/textures/`, `photos/` and `models/` under the `file`/`path` names in those lists (a few were cropped or re-encoded first; the `notes` field says how). The finished pictures the game uses are in `nightmare/assets/scenes/`.

## Adding a scene

1. Write `scene_<name>.py` next to the others with
   ```python
   OUT = '<name>.jpg'           # file name inside nightmare/assets/scenes/
   def build(out_path): ...     # render, finish(...), save_jpeg(...)
   ```
2. Add one line to `SCENES` in `build_all.py`.
3. Finish with `grade.finish(linear, kind)` and `common.save_jpeg(...)`. Never
   build your own grade: the shared finish is what makes every picture belong
   to the same dream.

`scene_office.py` is the worked example. The usual recipe:

```python
from common import Camera, Scene, PointLight, ApertureLight, edge_ao, load, f32, match_albedo, tile
from grade import finish

cam = Camera(width, height, f=..., cx=..., cy=horizon_y, eye=1.2, ss=2)  # pinhole, metres
sc = Scene(cam, ambient=(0.25, 0.28, 0.56))                              # violet night fill
sc.lights += [PointLight(pos, colour, power, soft=0.5, pattern=..., shadow_px=2.5)]
sc.add_occluder('desk', bmin, bmax)              # boxes that cast ray-traced soft shadows
sc.draw_quad([TL, TR, BR, BL], albedo, ao=..., spec=..., alpha=...)   # back to front
sc.box(bmin, bmax, face_textures)                # only the faces the eye can see
linear = sc.downsample()
finish(linear, 'room', seed=...).save(...)
```

* **Planes are real planes.** A wall/floor/ceiling is a quad with 3-D corners;
  its texture is mapped with an exact perspective (PIL `PERSPECTIVE`, rendered
  at 2x and box-filtered down, so edges are clean). Make the texture at a
  physical density (pixels per metre) so scale is consistent everywhere:
  floor boards 9-14 cm, doors 2.1 m, wallpaper repeat about 53-56 cm.
* **Frontal walls** are easiest as a `Board` (see `scene_office.py`): a 2-D
  canvas in wall metres where wallpaper, dado, mouldings, door trim, curtains
  and carved letters are painted, then drawn as one lit quad.
* **Colour-match every source** with `match_albedo(mean=, sat=, tint=)` before
  use, and `flatten_light()` museum photos with uneven lighting. Albedos sit in
  sRGB means of roughly 0.22-0.40 (dark woods 0.27-0.30, damask 0.34, plaster
  0.36-0.45, paper 0.6-0.75); the lights and the grade do the rest.
* **No visible repeats**: `tile()` with random offsets and `tone_var`,
  `make_seamless()` for photographed samples (find the repeat with
  `find_period()`), real-size scaling.
* **Light everything with the scene's lights** (no painted-on highlights except
  small baked profile shading on mouldings). Emissive things (sky, moon, screens,
  lamp shades) use `lit=False` or `emissive=`.

## Office: what the integrator must know

* `office.jpg` is exactly 2400 x 900 and keeps the old stand-in's geometry:
  door boxes at the config fractions (x .03 / .82, y .178, w .15, h .7) are
  filled with pure darkness (#050309) for the game to draw into; window
  560,160 250x270; desk top edge y 620 (x ~860-1560); lamp shade 905-1005 x
  445-500 (light spot 950,510); CRT screen 1060,438 280x190; clock spot
  (1449.6, 585.9, r 26) with only a contact shadow at (1452, 623): **the clock
  itself is not in the picture** (draw the full alarm clock live, as the
  stand-in does); wall x 1700-1890, y 190-420 is clear wallpaper for the new
  pinned drawing; WAKE UP is scratched in at (1610, 600).
* Use the stand-in's spots (`OFFICE_SPOTS` in game.js: clock, window, lamp)
  for this picture, i.e. treat it like the code-painted stand-in, not like a
  user picture (a user picture gets only the clock hands, no window pass and no
  lamp breathing unless config sets the spots).
* The doors and the window sit on a **near wall** 4 m away; the desk stands in
  front of an **alcove** whose back wall has the old floor line (712) and
  ceiling line (58). Door thresholds are at y = 790 (the box bottom).
* `GEOMETRY` in `scene_office.py` lists every number above.

## Doorways, bedroom, CAM 7 and menu (scene_doors / scene_bedroom / scene_cam7 / scene_menu)

`scenekit.py` holds what these four share: `paper()` (a seamless wallpaper repeat at a real roll width),
`wood_grain()`, `panel_door()` (panelled doors from real wood photos, mouldings shaded from a height field,
brass knobs and keyhole plates, grime), `draw_lod()` (long walls and floors drawn in slices whose texture is
shrunk to the screen size it covers: no aliasing far down a hall), `aperture_pattern()` (a light that only
shines through an opening), `office_finish()` (grades a doorway as a patch of the 2400 x 900 office: same edge
darkening, vignette and grain), `night_photo()` (a daylight HABS photo turned into a dim night plate) and
`DepthScene` (depth buffer for fog). `common.PoseCamera` is a camera that can stand anywhere and look anywhere
(CAM 7); `Camera.viewpoint()` / `Camera.depth()` let `Scene` work with it (the office renders bit-identically).

| picture | size | for the game |
|---|---|---|
| `door_left_dark.jpg`, `door_left_lit.jpg`, `door_left_closed.jpg` | 360 x 630 | `office.doors.left` dark / lit / closed (West Hall side) |
| `door_right_dark.jpg`, `door_right_lit.jpg`, `door_right_closed.jpg` | 360 x 630 | `office.doors.right` (East Hall side) |
| `bedroom.jpg` | 1600 x 900 | `bedroom.image` (already night-graded: do not multiply it dark blue again) |
| `bedroom_morning.jpg` | 1600 x 900 | `bedroom.morningImage` |
| `cam7_you.jpg` | 1824 x 1026 | `youCam.image`, with `youCam.seat` = { x: 0.459, y: 0.603, size: 0.47 } |
| `menu.jpg` + `menu_light.png` + `menu_fog.png` | 1600 x 900 (fog 1600 x 420) | the main menu background (no monster) |
| `cam1_nursery.jpg` ... `cam6_east.jpg` | 1824 x 1026 | the six `cameras[].image` stand-ins (kind `cam`); built with `camkit.py`, see CAMS.md; monster stand spots in `poses_suggest.json` |
| `paper.jpg` | 380 x 460 | the sheet the game draws its crayon drawing on (`scene_paper.py`; the drawing itself is drawn by the game, `paintKidDrawing`) |
| `cam7_chair.png` | 320 x 326 RGBA | the back of your chair on CAM 7, drawn over you at (670, 700) |
| `clock.png` | 460 x 560 RGBA | the alarm clock (`scene_clock.py`), hands drawn by the game |
| `bedroom_ev2.jpg`, `bedroom_ev4.jpg` | pieces of the morning | Nights 2 and 4's evidence, laid over bedroom_morning.jpg at `EV_PATCH` |

* Doorways: the hall floor meets the bottom edge (the threshold, office y = 790), so the default
  doorPose stands on it (the game now uses {x .55, y .87, h .70}: one step back in the hall, in scale with the room). Lit = a warm amber bulb above your door and the hall's own bulb
  just past it; dark = only the far moonlit window (west) or lamplight under a side door (east) and a little of
  the office's light on the threshold. Closed = a pair of heavy panelled doors lit by the office's own lights.
* Bedroom: the stand-in's geometry exactly (EVIDENCE_SPOTS, WINDOW_PX, TABLE_TOP = 600, MORNING_CLOCK). No clock
  is baked on the table: draw the small night clock at (1500, 566, r 30) and the morning clock as now.
* CAM 7: the office's own 3-D set from a high corner behind your chair; the chair is in the picture and empty,
  its back's top edge sits exactly under the drawn shoulders (y = 779).
* Menu: the warm lamplight from the door ajar is baked at 80 %; `menu_light.png` is that light alone (draw it
  with globalCompositeOperation 'lighter', globalAlpha 0 .. 0.25 to breathe from 80 % to ~105 %).
  `menu_fog.png` is seamless left-right: scroll it slowly along the floor (e.g. at y = 430 .. 850).

## How the game uses them (integration)

Wired in by `loadArt()` in `nightmare/js/game.js` (the `SCENES` table there names every file):

* A picture in `assets/scenes/` is shown **only while the creator's own picture for that slot is missing**
  (`assets/rooms/...`, or the optional door / bedroom / CAM 7 slots in `config.js`). Missing too: the old
  code painter. The art helper (`?dev`) says "using the built-in photo stand-in; your picture goes at ...".
* `office.jpg` is treated like the painted stand-in (`Art.officeMissing` stays true, `Art.officePhoto` is set):
  the full alarm clock is drawn live (shaded into the room's light), the window pass and the lamp breathing use
  `OFFICE_SPOTS`, WAKE UP is not drawn again, and the crayon drawing is pinned at (1700, 190), multiplied by the
  wall's dim violet light, once at load.
* Doorways: used as they are when the door box has their shape (the default boxes); otherwise cut to fit
  (never stretched), floor kept at the bottom. A creator's own `office.png` without a `darkImage` still shows the
  doorway they painted.
* Bedroom: `bedroom.jpg` is drawn without the dark-blue multiply; the small night clock is drawn into it at
  load. The morning clock is drawn live with a soft shadow and the room's light.
* CAM 7: `cam7_you.jpg` uses its own seat (0.459, 0.603, 0.47) and no code chair.
* Menu: `menu_light.png` is cropped to its lit part (x 712-1356, y 20-900) at load; the light breathes
  (`lighter`, alpha 0.03-0.2) and now and then dips slowly (a dark copy, at least 1.5 s apart, none with Dream
  effects Off); the fog drifts at 9 px/s (half with effects Low, still with Off); the whole picture leans up to
  13 px with the mouse or a phone's tilt (half with Low, none with Off).
* Redhorn's `poses` and `doorPose` in `config.js` were re-tuned for these pictures from `poses_suggest.json`
  (feet on the floor, never under the camera map or the bottom bar).

* Loading: the title screen waits only for the creator's pictures, the monster frames, the menu photo, the
  paper, the clock and the night bedroom (`Art.bootP`); the desk room, doorways, cameras, CAM 7 and the morning
  load behind the menu (`Art.restP`), and a night waits for them with your eyes shut (on a slow connection).
* With Dream effects Full (not on phones) the game draws at the screen's real resolution (up to 2400 x 1350),
  so these photos stay sharp on 1080p and Retina screens; it falls back to 1600 x 900 if the frame rate drops.
* The window pass is clipped to the office window's four panes (`OFFICE_PANES`), so the bars stay in front.
* On the cameras a monster gets a soft contact shadow, and in the Drowned Parlor its reflection in the water.

## The fix pass (what changed after the art review)

* **Real furniture, not boxes.** The parlor's two armchairs, your chair on CAM 7, the Endless Hall's long-case
  clock, the nursery's cot and chest and the alarm clock everywhere are photoscanned 3-D models (Poly Haven, CC0;
  their textures are photographs of the real objects), drawn by `meshkit.draw_mesh` through the scene's camera and
  lit by the scene's lights (with their shadows), the texture's own ambient occlusion and a varnish/brass highlight
  from its roughness. `Mesh(..., recolor=meshkit.recolor(...))` repaints a part (pale upholstery to crimson velvet
  or oxblood leather) keeping its weave. `Mesh.place(pos, yaw, height)`: feet on the floor at pos, yaw > 0 turns
  its front toward +x. `contact_shadow` darkens the floor where it stands. The nursery's rocking horse is a museum
  photograph (Smithsonian American Art Museum, CC0) cut out of its black backdrop.
* **CAM 7's chair layer.** `scene_cam7.py` also writes `cam7_chair.png` (the parts of the chair nearer the camera
  than you, at `CHAIR_LAYER` = 670, 700 in cam7_you.jpg): the game draws you, then this over you, so you sit in it.
* **The alarm clock** is `clock.png` (460 x 560 RGBA, kind 'prop' in grade.py: no vignette, bloom or night tint;
  the game multiplies it by the room's light). Its dial centre and radii are printed by the build and live in
  `CLOCK_PHOTO` in game.js.
* **Evidence mornings.** `scene_bedroom.py` renders the morning again with the closet door ajar (Night 2) and with
  a torn pink leather collar on the floor (Night 4) and saves only the piece that differs, `bedroom_ev2.jpg` /
  `bedroom_ev4.jpg`, at `EV_PATCH` (the game lays it over bedroom_morning.jpg).
* **Lit doorways** have warm amber hall bulbs (LOOK.md: practical lights are the warm ones) and are about 1.6x
  brighter. **Camera night tint:** `camkit.finish_cam` leans a too-warm room's non-practical light back to the
  night violet (`night_balance`, aim B - R = +7.5 in the mid-tones), so every camera looks like one house.
* **Rugs** are `scenekit.rug_field`: the carpet photo repeated at a real knot size (about 4 mm), with a border,
  a guard stripe, a pile blur and wear. **Stairs:** oak treads and risers, and the landing has a soffit and a wall
  under it. **Bedroom night-light** lights its own wall plate. **Office frame:** a carved gilt moulding.

## Credits for the sources

`python3 art-src/compose/sources_used.py trace` rebuilds every scene into a temporary folder, records every
source picture each one opens (`sources_used.json`) and says whether the shipped files are still identical to
a fresh build. `python3 art-src/compose/sources_used.py credits` then prints the `config.js` credit lines and the
`CREDITS.md` table (it stops if a source's licence would need an attribution line).
