# LOOK: the numbers behind "Until the Alarm"

Every built-in picture is a real, photographic place: an old Victorian family
house at night, seen in a dream. Beautiful, eerie, a little wrong (a moon far
too big, halls too long, stairs into nothing), never gory, never a monster.
This file is the look bible turned into numbers. `grade.py` holds the same
numbers in code; change them there and every scene changes together.

## 1. The finish (grade.py, `finish(linear, kind)`)

Applied in this order to the renderer's **linear** radiance:

| step | value (kind `room`) |
|---|---|
| exposure | x 1.0 |
| bloom (linear) | soft-knee threshold 0.42 (knee 0.25); three Gaussian radii 3 / 11 / 34 px, weights 0.22 / 0.16 / 0.12, tint (1.0, 0.97, 1.02) |
| tone curve | Reinhard on luminance with white point 3.2, then sRGB encode |
| saturation | 0.64 of the source, toward a violet grey (0.96, 0.94, 1.06) x luminance |
| warm keep | warm practical light (R well above B, luminance 0.25-0.7) keeps up to 55 % of the removed saturation, so lamplight stays amber |
| night tint | shadows/mids x (0.88, 0.87, 1.08), fading out by luminance 0.75, strength 0.65 |
| contrast | display S-curve y + 0.18 y(1-y)(2y-1) |
| vignette | 1 - 0.36 x smoothstep(0.42, 1.18, r), r = elliptical radius in normalised picture coordinates (same shape on every picture) |
| black lift | lift + (1 - lift) y with lift = #07050c: the darkest pixel is never pure black |
| grain | monochrome Gaussian, sigma 0.018 at mid-grey (x (0.35 + 2.6 L(1-L))), softened 0.55 px, never below the lift |

All pixel sizes are for a 900 px tall picture and scale with height
(`scale = height / 900`), so a 1026 px camera picture gets the same bloom and
grain per pixel scale.

Kinds (same core, small differences):

| kind | differences from `room` |
|---|---|
| `room`, `door`, `bedroom_night` | none |
| `menu` | vignette 0.42 |
| `cam` | saturation 0.52, grey (0.93, 1.0, 1.0), shadow tint (0.80, 0.92, 1.0), S-curve 0.32, colour x (0.90, 1.03, 0.97), exposure 1.05, vignette 0.40. **No** scanlines, REC, timestamps or static: the game adds its own camera overlay |
| `prop` | no vignette, no bloom, no night tint (a cut-out the game lights itself: the alarm clock) |
| `bedroom_day` | exposure 1.25, saturation 0.74, warm grey (1.04, 0.99, 0.94), shadow tint (1.0, 0.94, 0.92) at 0.4, colour x (1.10, 1.0, 0.86), lift #0e0a0c, vignette 0.26, bloom threshold 0.55 |

## 2. Light (what the renderer is fed)

* **Ambient** (violet night fill): linear irradiance (0.25, 0.28, 0.56); x0.64 on surfaces facing down, x0.82 on walls, x1.0 facing up; +-6 % toward the window side.
* **Moonlight** is cool lavender `#cfc8ff` (linear ~ (0.62, 0.58, 1.0)). Through a window it is a
  directional `ApertureLight` (office: direction (0.30, -0.88, -0.36), power 2.4), so its patch on the
  floor carries the shadow of the glazing bars. A soft lobe light just inside the glass (power 2.0) lets
  the window glow into the room. A light shaft is a faint additive screen-space wedge (about 0.16 x moon).
* **Practical lights** are the only warm accents: amber `#ffb466` (office lamp: linear amber x
  (1, 0.93, 0.80), power 9.0, soft radius 0.5 m, a shade pattern: full below 54-64 deg from straight
  down, 45 % through the top opening, 30 % through the fabric).
* Falloff: `power x cos / (d^2 + soft^2)` (inverse-square, softened), Lambert with a little wrap (0.1-0.3).
* Shadows: ray-cast against occluder boxes, blurred 2-4 px into penumbras. Every object that stands on
  something gets AO/contact shadows (`edge_ao` creases 5-15 cm, blobs under feet and bases).
* A dim CRT/screen is green-cyan `#6cf0c0` (power 0.35), lighting only what is in front of it.
* Every camera room's mid-tones lean violet (B - R at least +3, aim +7.5): `camkit.finish_cam` corrects a room
  whose own practical lights left it olive (night_balance), keeping amber only round the lights themselves.
* Allowed cheats, if motivated: a broad cool fill from behind the viewer (power 2.2, no shadows) and a
  "wash" that carries a practical's glow onto a wall it could not reach (office alcove, power 0.55).

Targets after the finish (office): mean luminance ~32/255 (old flat stand-in: 21), lit wall 55-75,
moonlit/ambient walls 30-35, darkest doorframes ~20, highlights only at the lamp, moon, screen.
The game draws its own darkness (8 % black + lamp flicker) and vignette on top: do not go darker.

Props are real objects (LOOK rule "real and photographic"): photoscanned 3-D models or cut-out museum photos,
drawn through the scene camera and lit by the scene's own lights (meshkit.py), never boxes or flat cut-outs
standing in a perspective room. A prop the game lays over a room itself (the alarm clock) is finished with kind
'prop' (the core grade without vignette, bloom or night tint) and lit in the game by the room's light.

## 3. Palette

* night shadows: deep blue-violet, never pure black: #07050c (floor) .. #0d0a16
* moonlight: cool lavender-white, #cfc8ff family
* practical light: warm amber, #ffb466 family (lamp, bulbs, light under doors) - the only warm accents
* reds (curtains, runners, the WAKE UP stain): muted crimson, never pure red
* woods: dark brown leaning violet in shadow; tint wood textures (0.84, 0.90, 0.80) at saturation 0.5
  before lighting so they do not turn magenta under the violet ambient
* overall saturation ~55-70 % of the source; the finish does most of it

## 4. Craft rules

* Perspective-correct planes (`Scene.draw_quad`), physically consistent scale: floor boards 9-14 cm,
  doors 2.1 m tall, wallpaper repeat ~53-56 cm (the damask: one 0.53 m roll width), dado ~0.58 m,
  picture rail 2.35 m.
* No visible repeats: random tile offsets, tone variation (`tile(..., tone_var=0.07-0.15)`), large
  textures, seamless crops (`make_seamless`, `find_period`).
* No seams, halos, jaggies, banding or blurry upscales: render at 2x (`ss=2`) and box-filter down;
  premultiplied alpha; sources are never upscaled past ~1.5x of their resolution.
* Edges of composited objects are soft and shaded by the same lights; same black level and grain
  everywhere (the finish guarantees it).
* Old monochrome photos (HABS) must be tinted into the palette and mixed with colour textures.
* Text in the world is never a font pasted on top: carve it, write it, stain it (WAKE UP is built
  from knife strokes over the Eater letterforms, showing pale plaster with a rust-red bleed).

## 5. The spoiler rule

**No monster anywhere in a background**: not in a painting, a photo, a drawing, a shadow or a
reflection. Never Redhorn. Paintings may be eerie old portraits and moonlit landscapes. The office's
"pinned drawing" spot (x 1700-1890, y 190-420) is left as clear wallpaper; the game draws a new,
monster-free drawing there.

## 6. Sources used by the office (all in ../sources, licences in the manifests)

Wallpaper: Cooper Hewitt dark green damask (PD). Plaster: Poly Haven damp-stained, aged-worn, aged-beige,
ceiling-textured. Wood: Poly Haven raised wainscot (+ AO), dark varnished, lacquered cherry, fine-grain old,
painted green; dark oak floor. Rug: Met Lotto carpet (CC0). Fabric: red velvet, leather, red book cloth,
Met green quilt. Metal: NASA/Smithsonian brushed brass. Paper: aged stained paper (PD), off-white grain.
Night: Poly Haven Milky Way, NASA full moon (PD), Poly Haven misty pines. Paintings: Boecklin "Isle of the
Dead" (Met, CC0), Heinrich Paul "Portrait of a Young Girl" 1840 (PD). Fonts: Eater (WAKE UP), VT323 (the
screen) from nightmare/assets/fonts (OFL).
