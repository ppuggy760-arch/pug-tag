# How to add your art to *Until the Alarm*

The game runs right now with **stand-in pictures** for everything you haven't
drawn yet. When you save a picture at the path the game expects, it switches to
your picture automatically. You don't need to change any code.

Everything you might change lives in **`js/config.js`**: the title, rooms,
monsters, sounds and the "dream voice" text.

---

## 1. Play it

* **Easiest:** open `index.html` in Chrome, Edge or Firefox.
* **Best (full sound effects):** run a tiny web server in the `nightmare` folder,
  e.g. `python3 -m http.server`, then open http://localhost:8000.
  GitHub Pages works too.

Opened straight from a file, sounds still play, but some effects (left/right
panning and muffled sounds) are simpler.

## 2. Art-helper mode

Open the game with **`?dev`** at the end of the address, like
`index.html?dev` or `http://localhost:8000/?dev`.

* Green boxes show where the game thinks the **doors** are in your desk room.
  Click anywhere in the room to see that spot's `x` / `y` numbers.
* While a room still uses stand-in art, a line at the top of the screen tells
  you the exact file name to save your picture as.
* If `config.js` has a typo (like a room name that doesn't exist), the helper
  box lists it with a "did you mean …?" hint. Capital letters don't matter:
  `"Hall"` and `"hall"` are the same room.
* **Tab** picks which monster the helper works on (its name is shown at the
  top of the box). G, Z, X and K then use that monster.
* Press **G**, then open the cameras. A see-through copy of the monster appears.
  **Click where its feet should go.** Use the **mouse wheel** or **+ / −** to
  resize it and **R** to flip it. The box in the corner shows the exact line to
  paste into `config.js` under `poses:`.
* **Z** / **X** put the monster at the left / right door, so you can check how
  it looks in the doorway (turn the light on).
* **K** tests the jumpscare, **T** speeds up time, **N** skips to 5:59 AM,
  **M** makes the monsters move, **L** drops Lucidity to 5%.

## 3. The desk room (office)

| File | What it is |
|---|---|
| `assets/rooms/office.png` | Your desk room. Make it **wide**, about **2400 × 900** (8:3), because the player looks left and right across it. |

Then line up the doors in `config.js`, under `office.doors`:

```js
left:  { x: 0.030, y: 0.178, w: 0.150, h: 0.700, ... },
```

`x` and `y` are the door's top-left corner, and `w` and `h` its width and
height, all as fractions of the picture. Use art-helper mode to read them off
your picture.

Optional extra pictures for each door (leave `""` to use the built-in look):

* `darkImage`: the doorway with the light off
* `litImage`: the doorway with the light on (an empty hallway)
* `closedImage`: the shut door

Make each one the same shape as the door box.

## 4. Camera rooms

Make one picture per camera, ideally **1600 × 900** (16:9):

| File | Camera |
|---|---|
| `assets/rooms/cam1_nursery.png` | CAM 1, The Nursery (the monster starts here) |
| `assets/rooms/cam2_hall.png` | CAM 2, The Endless Hall |
| `assets/rooms/cam3_parlor.png` | CAM 3, Drowned Parlor |
| `assets/rooms/cam4_stairs.png` | CAM 4, Stairs to Nowhere |
| `assets/rooms/cam5_west.png` | CAM 5, West Hall (next to your left door) |
| `assets/rooms/cam6_east.png` | CAM 6, East Hall (next to your right door) |

You can rename rooms, change `name:` or `label:`, or add more cameras by
copying a line in `cameras:`. Number keys 1–9 pick cameras.

Draw rooms **without** the monster in them. The game places your animated
monster into the room by itself, using the `poses` numbers.

## 5. Monsters

Each monster is a list of frames, transparent PNGs played in order:

```
assets/monsters/redhorn/frame1.png … frame6.png   (your first monster, from your video)
```

To add a new monster:

1. Put its frames in `assets/monsters/<name>/frame1.png`, `frame2.png`, and so on.
   Transparent background, same canvas size for every frame.
2. In `config.js`, copy the whole `{ id: "redhorn", ... }` block inside
   `monsters: [ ... ]`, paste it after the first one (add a comma between), and change:
   * `id` and `name`
   * `frames`: the list of your pictures
   * `fps`: animation speed (Redhorn uses 4)
   * `levels`: aggression for nights 1–5 (0 = it sleeps all night and never
     moves, 20 = relentless). Use 0 to make a monster appear only on later nights.
   * `start`, `path` and `retreat`: which rooms it walks through. Give it a
     different route from Redhorn's, e.g. only the west side.
   * `poses`: where it stands in each camera picture (use art-helper mode)
   * `doorPose`: where it stands in the doorway. Keep `h` small enough that its
     whole body (horns too!) fits inside the door box. Redhorn uses `h: 0.70`.
   * `jumpscareFrames` (optional): special close-up frames for its jumpscare
   * `jumpscareFocus`: which part of the picture rushes at the player
     (`y: 0.2` is near the top, where the face usually is)

> **Tip:** if your art has a white background, ask Claude to cut it out.
> Redhorn's frames were cut out of your video that way.
>
> **Tip:** crop each frame close to the monster's body (not much empty space
> around it). Then the sizes in `poses` and `doorPose` behave the way you expect.

## 6. Sounds

All sounds are real recordings downloaded from OpenGameArt.org under free
licenses. See `CREDITS.md`. To swap one, put a new file in `assets/audio/` and
change its path in `sounds:` in `config.js`.

The sounds marked `// optional:` in `config.js` (`clock_tick`, `type_key`,
`reality_snap`, `redhorn_click`, `door_strain`, `hypnic_jolt`, `water_drip`)
can be missing: the game then plays a stand-in, like a slowed-down or muffled
copy of another sound.

## 7. Text

* `title` and `subtitle`: the name on the menu
* `dreamVoice`: what the voice says at the start of each night
* `hourSeconds`: how long an in-game hour lasts (default 75 seconds)
* `nights`: one `{ … }` block per night. `drain` is how fast Lucidity drains
  (bigger = harder); the other settings in each block are explained in the
  comments right above it in `config.js`. Leave a setting out and the game uses
  its own value. (An older `lucidityDrain: [ … ]` list still works too.)
* `endlessRules` and `endlessDrain`: the same settings for the Endless Dream
