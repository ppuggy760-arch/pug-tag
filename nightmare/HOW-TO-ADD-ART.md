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
* **K** tests the jumpscare, **T** speeds up time, **N** skips to 5:59 AM (to see waking up),
  **M** makes the monsters move, **L** drops Lucidity to 5%.
* **V** shows a *dream lie*: a fake of your monster at a door (turn that light
  on) or on a camera. Fakes use your own monster pictures, frozen and tinted
  violet, so there is nothing extra to draw.
* **Y** opens the cameras and shows **CAM 7** (see section 5) right away, on
  any night: click it, look at another camera, then click CAM 7 again.

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

Make each one the same shape as the door box. You don't need to draw a
cracked or damaged door: when a door is held shut too long, the game draws
cracks over your `closedImage` and makes it shudder by itself.

Three more spots you can mark in your desk room (also under `office` in
`config.js`; take away the `//` in front of the line to switch them on):

* `clock: { x, y, r }`: the alarm clock on your desk. `x` and `y` are the
  middle of its face and `r` is how big the face is (a fraction of the picture
  height). **Draw the clock without hands**: the game draws hands that show the
  night's real time, from 12 to 6 (when your Lucidity is very low they jump
  ahead now and then, because clocks can't be trusted in dreams). At 6 AM the
  alarm rings right there, and the sound comes from that side.
* `window: { x, y, w, h }`: the window box, like a door box. When the monster
  reaches a hall next to your doors, its dark shadow walks past the window.
  When your Lucidity runs out, something comes and stands in it.
* `lamp: { x, y }`: the middle of your desk lamp's light. Now and then the
  lamp slowly "breathes" there (a warm glow that swells and sinks).

Click on them in art-helper mode to read the numbers. If your room has no
clock, window or lamp, leave them out: the game then skips those effects
instead of drawing them in the wrong place. (The lamp also flickers and dims
by itself when something is near your doors; that works on any picture.)

## 4. Your bedroom (the real world)

Every night starts in your bedroom: you fall asleep, count, and drop into the
dream. When the alarm rings at 6 AM you wake up in the same room and slap the
alarm off.

| File | What it is |
|---|---|
| `assets/rooms/bedroom.png` | Your room **seen from your bed**, **1600 × 900**. The game makes it dark blue at night and warm in the morning, so draw it in normal daylight colours. |

Optional, in `config.js`:

* `bedroom.morningImage`: a different picture for the morning (leave `""` and
  the game warms up your normal one).
* `morning.evidence`: something follows you out of the dream. Night 2 the
  closet door is open a crack, Night 3 the "he walks at night" drawing lies on
  the bedside table, Night 4 a scrap of pink collar is on the floor. Draw your
  own as a **transparent PNG** and put its path next to the night's number.
  To move it, write `{ image: "…", x: 0.15, y: 0.76, w: 0.08, h: 0.04 }`
  (a box in your bedroom picture, like the door boxes). The picture stands on
  the bottom of that box.

The big alarm clock in the morning is drawn by the game, so you don't need to
draw it.

## 5. Camera rooms

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

**CAM 7, "Your Room".** Once a night (from Night 3) a camera that isn't on the
map shows up: it films *you*, from behind, sitting at your desk. Look at
another camera, look back, and something is standing behind your chair. The
game makes this picture from your desk room by itself, but you can draw it:

| File | What it is |
|---|---|
| `assets/rooms/cam7_you.png` | Your desk room seen **from behind and above**, with an **empty chair**, 1600 × 900. |

The game draws the back of your head on it. In `config.js`, `youCam.seat`
says where: `x` and `y` are the middle of your head in that picture, and
`size` makes it bigger or smaller (1 = normal). On the last night the chair
stays empty.

Each camera can also have a **sound** you hear while you watch that room:
`sound: "water_drip", soundVol: 0.35` (the name of one of the `sounds:`, and
how loud, from 0 to 1). The Nursery plays the music box, the Endless Hall a
ticking clock, the Drowned Parlor dripping water. Leave them out for a quiet
room.

Draw rooms **without** the monster in them. The game places your animated
monster into the room by itself, using the `poses` numbers.

## 6. Monsters

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
   * `presenceSound`: the noise it makes in the walls (Redhorn clicks). You hear
     it louder and clearer the closer it gets to your doors, and right there
     when you watch its room. Use the name of one of the `sounds:`, or `""` for
     a silent monster.
   * `jumpscareFrames` (optional): special close-up frames for its jumpscare
   * `jumpscareFocus`: which part of the picture rushes at the player
     (`y: 0.2` is near the top, where the face usually is)

> **Tip:** if your art has a white background, ask Claude to cut it out.
> Redhorn's frames were cut out of your video that way.
>
> **Tip:** crop each frame close to the monster's body (not much empty space
> around it). Then the sizes in `poses` and `doorPose` behave the way you expect.

## 7. Sounds

All sounds are real recordings downloaded from OpenGameArt.org under free
licenses. See `CREDITS.md`. To swap one, put a new file in `assets/audio/` and
change its path in `sounds:` in `config.js`.

`alarm` is the hero sound: it rings inside the dream at 6 AM (muffled at
first, as if through a pillow) and then in your room until you turn it off.
`clock_tick` ticks while you fall asleep, and slows down and stops when your
Lucidity runs out.

The sounds marked `// optional:` in `config.js` (`clock_tick`, `type_key`,
`reality_snap`, `redhorn_click`, `door_strain`, `hypnic_jolt`, `water_drip`)
can be missing: the game then plays a stand-in, like a slowed-down or muffled
copy of another sound.

The long music tracks (`ambience`, `menu_music`, `morning`, `music_box`) play
straight from their files while the game runs, so they can be big. Every other
sound is loaded before the game starts, so keep those short (a few seconds).

**Sound captions.** In Settings, *Sound captions* shows every scary sound as
words on the side of the screen it came from ("‹ breathing", "footsteps,
close ›"), with a red glow at that edge. It is on by default on phones and
tablets. The words live in `captions:` in `config.js`. If you give a monster
its own scary sound, add a caption line for it too, so players who can't hear
it still know what happened.

**Scares.** Also in Settings: *Scares: Normal / Gentle*. Gentle makes the
jumpscare quieter and softer (it fades in instead of lunging, after a whole
second of darkness) for younger players. The nights stay just as hard. Every
jumpscare uses your monster's own pictures (`jumpscareFrames`, or its normal
frames) and its `jumpscareFocus`, so a new monster needs nothing extra.

## 8. Text and game settings

* `title` and `subtitle`: the name on the menu
* `fallAsleep`: what you count in your head while you fall asleep (one line per night)
* `dreamVoice`: what the voice says at the start of each night
* `finale`: after Night 5, the voice says `line`, then the credits roll. They
  start with the **first line of `credits`**, which is you: change `"You!"` to
  your name if you like. `thanks` is the very last line.
* `hourSeconds`: how long an in-game hour lasts (default 75 seconds)
* `nights`: one `{ … }` block per night. `drain` is how fast Lucidity drains
  (bigger = harder); the other settings in each block are explained in the
  comments right above it in `config.js`. Leave a setting out and the game uses
  its own value. (An older `lucidityDrain: [ … ]` list still works too.)
* `endlessRules` and `endlessDrain`: the same settings for the Endless Dream
* `pinch`: how much Lucidity a pinch gives back and how often you can do it.
  It gives more when you are low (`lowBonus`) and less when you are high
  (`highPenalty`). A pinch is loud: monsters near your doors come closer.
* `doorStrain`: doors are like holding your breath. A shut door is cheap for
  `doorFree` seconds (set per night in `nights`), then costs more and more,
  up to `maxCost` times as much. `giveUpAfter` is how long a monster waits at
  a shut door before it bangs and leaves.
* `minWarning`: the fairness promise. A monster at your door always breathes
  first and waits at least this many seconds (2.5) before it can come in, even
  if you give it a tiny `waitAtDoor`.
* `director`: the *dream director* gives each night a shape. After a quiet
  start (`quietMinutes`, 50 = 12:50 AM) small "wrong" things happen every
  `minGap`–`maxGap` seconds: the lamp breathes, a lit doorway shows a
  different room of the house, someone whispers in the ceiling, the room
  stretches wider. Each comes after a moment of silence, and never while a
  monster is close to your doors. `enabled: false` switches them off. From
  5:30 AM the clock shows the minutes and ticks louder, and on Night 5 the
  alarm rings once too early (`falseDawn` in `nights`; the voice then says
  `dreamVoice.falseDawn`). It is a trick: it never hurts you.
* `lies`: below the violet line on the Lucidity bar (`below`, 60%), the dream
  sometimes shows a **fake** monster, about every `every` seconds. A fake never
  moves, glows see-through violet, and its breathing runs backwards. The light
  makes it fade, a pinch clears every fake, and it can never hurt you. Turn the
  lies on or off per night with `lies: true / false` in `nights`. The first
  time your light finds a fake, the voice says `dreamVoice.lie`.

The little glyphs under the Lucidity bar show what is draining you right now:
a dot (just being asleep), the left door, the right door, a star (a light) and
a screen (the cameras). A door glyph fills up while you hold that door and
turns red once it costs extra.
