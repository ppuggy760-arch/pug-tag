# How to add your art to *Until the Alarm*

The game already runs. Every picture you haven't drawn yet is a **stand-in**
that the game paints by itself. When you save a picture with the right name in
the right folder, the game uses yours instead. You never have to change the
game's code.

Everything you can change lives in one file: **`js/config.js`**. It has the
title, the rooms, the monsters, the sounds and all the words. Its notes (the
`/* … */` and `// …` parts) explain each setting.

**What's in this guide**

1. [Play it](#1-play-it)
2. [The art helper](#2-the-art-helper-dev)
3. [Every picture you can draw](#3-every-picture-you-can-draw)
4. [The desk room](#4-the-desk-room)
5. [Your bedroom and the morning](#5-your-bedroom-and-the-morning)
6. [Camera rooms](#6-camera-rooms)
7. [Monsters](#7-monsters) (adding one, step by step, and **picking a brain**)
8. [Sounds](#8-sounds)
9. [Words](#9-words) (the dream voice, its `{wrong|right}` trick, the lesson)
10. [Night rules](#10-night-rules)
11. [When something goes wrong](#11-when-something-goes-wrong)

---

## 1. Play it

* **Easiest:** double-click `index.html` to open it in Chrome, Edge or Firefox.
* **Best:** run a tiny web server in the `nightmare` folder, then open the
  address it gives you. For example, in a terminal:
  `python3 -m http.server` and then open http://localhost:8000.
  GitHub Pages works too.

Both work. From a web server the sounds are better (left and right, muffled
through doors), and when something is wrong the game can show you the exact
line in `config.js`.

> **Tip:** after you change `config.js` or a picture, save it and **reload**
> the page. In the art helper you can press **U** to reload just the pictures.

---

## 2. The art helper (`?dev`)

Add **`?dev`** to the end of the address:
`index.html?dev` or `http://localhost:8000/?dev`.

A green **ART HELPER** box appears. Players never see it.

**The art checklist.** Click *Art checklist* in the box. It lists every picture
and sound `config.js` asks for:

* ✓ found, with its size
* – not found, so the game uses a stand-in: either it isn't drawn yet, or its
  name or folder isn't exactly the same as in `config.js` (capital letters count)
* **!** something to look at, in plain words, for example:
  * "office.png is 1600×900. Make it wider (about 2400×900) so there is room to look around."
  * "cam3_parlor.png is 1000×1000: its edges will be cropped (use 16:9, like 1600×900)."
  * "Shade's frames are not all the same size: it will jump around."
  * "frame2.png has no see-through background. Cut the background out."

  (The see-through check only works from a web server.)

**Config warnings** are listed in red: typos in room names, a number written as
a word, a brain the game doesn't know… Each one says what to do, often with a
"Did you mean …?".

**Keys and buttons.** The main keys also have buttons in the box, so the helper
works on a tablet too.

| Key | What it does |
|---|---|
| **H** | Hide or show the helper box. |
| **Tab** | Pick which monster the helper works on (its name is at the top of the box). |
| **G** | A **see-through monster** to place (see below). |
| **+ / −** or the mouse wheel | Make the monster you are placing bigger or smaller. |
| **R** | Flip it (mirror it). |
| **J** | **Jumpscare aim**: shows its jumpscare picture. Click its face. **J** or **Esc** to go back. |
| **K** | Test the jumpscare. |
| **Z / X** | Put the monster at the left / right door (then turn that light on). |
| **U** | Reload your pictures (after you saved a new one), without restarting the night. |
| **T** | Time goes faster: ×1, ×10, ×40. |
| **N** | Skip to 5:59 AM, to see waking up. |
| **M** | Every monster moves right now. |
| **L** | Lucidity drops to 5% (to see the dream lie and the HUD slip). |
| **V** | Show a *dream lie* (a fake of your monster). |
| **Y** | Show CAM 7 right now. |

**Placing things.** Whatever you place is written in the box, ready to paste
into `config.js`. Press **copy**, then paste it over the old line.

* **Door boxes:** the green dashed boxes are where the game thinks your
  doorways are. With the light **off**, drag a box's **edges or corners** to
  fit your doorway, or drag its **middle** to move it. Copy the `left:` or
  `right:` line it gives you and paste it over the old one in `office: doors:`.
* **A spot in the desk room:** click anywhere else in the room. You get a
  ready `clock:` line and a ready `lamp:` line for that spot: paste the one you
  want under `office:` (see part 4). **For the window, drag a box** around it
  with the mouse instead, and paste the `window:` line it gives you.
* **A monster on a camera:** press **G**, open the cameras and pick a room.
  Click where the monster's **feet** go. Make it bigger or smaller with the
  wheel or **+ / −**, and flip it with **R**. In the monster's `poses:`,
  **replace** the old line for that room with the new one (or add it, if that
  room has no line yet). If the same room is written twice, the game only uses
  the **last** one, and the art helper warns you.
* **A monster in a doorway:** press **G**, then turn a light **on** (A or D).
  Click where its feet go in the doorway. In `doorPose:`, **replace** the old
  `left:` or `right:` line with the new one.
  Keep it small enough that its whole body (horns too!) fits in the doorway.
* **Jumpscare aim:** press **J** and click the part of the picture that should
  rush at the player (usually the face). Add the `jumpscareFocus` line to the
  monster's `{ … }` block (or replace its old one).

**Onion skin.** In ?dev mode, *Extras* shows every frame of your monster at
once, faint, each with a coloured box around it. If the boxes jump around, so
will your monster. The checklist also says how far its body moves sideways.

---

## 3. Every picture you can draw

Put room pictures in a folder called **`assets/rooms`** (make it if it isn't
there yet), and monster frames in **`assets/monsters/<name>/`**. Use PNG.

> **Careful:** on a website, file names must match **exactly**, capital letters
> too. `Office.PNG` is not `office.png`.

| Picture | Size | See-through? | In `config.js` | If it's missing |
|---|---|---|---|---|
| `assets/rooms/office.png` (your desk room) | **2400 × 900** (wide!) | no | `office.image` | a dreamy stand-in room |
| a doorway with the light off | the door box's shape | no | `office.doors.left.darkImage` (and `right`) | the doorway you painted in office.png |
| a doorway with the light on | the door box's shape | no | `office.doors.left.litImage` | a lit hallway |
| a shut door | the door box's shape | no | `office.doors.left.closedImage` | a shutter with a glowing sign |
| `assets/rooms/bedroom.png` | 1600 × 900 | no | `bedroom.image` | a stand-in bedroom |
| your bedroom in the morning | 1600 × 900 | no | `bedroom.morningImage` | the game warms up `bedroom.png` |
| things that follow you out (Nights 2, 3, 4) | small | **yes** | `morning.evidence` | the game draws them |
| `assets/rooms/cam1_nursery.png` … `cam6_east.png` | 1600 × 900 | no | `cameras[].image` | a stand-in room each |
| `assets/rooms/cam7_you.png` | 1600 × 900 | no | `youCam.image` | made from your desk room |
| `assets/monsters/redhorn/frame1.png` … | the same size for every frame | **yes** | `frames` | a shadow with glowing eyes |
| close-up jumpscare frames | any | **yes** | `jumpscareFrames` | its normal frames |
| a sleeper asleep | like its frames | **yes** | `sleepFrames` | its normal frame, darker, with z's |

---

## 4. The desk room

This is where the player sits all night: two doorways, a desk, maybe a window,
a lamp and an alarm clock.

**Make it wide: about 2400 × 900.** The player looks left and right across it,
and only a part of it fits on the screen at once. In Procreate, pick
*Custom size* and type **2400 × 900 px**.

If your picture is square or 4:3 (like an iPad canvas, 2048 × 2048 or
2732 × 2048), the game still works: it zooms in so you can look around, and
cuts off some of the top and bottom. Only about the **middle half** of a square
picture's height fits on the screen, so paint your doorways **shorter** there
(they should fit in that middle half), or they get cut off too. The art
checklist tells you when a doorway doesn't fit, and its green box shows yellow
arrows on the edge that is cut off.

**The doorways.** Paint your two doorways where you like, then tell the game
where they are, under `office: doors:` in `config.js`:

```js
left:  { x: 0.030, y: 0.178, w: 0.150, h: 0.700, darkImage: "", litImage: "", closedImage: "" },
```

`x` and `y` are the door's top-left corner, `w` and `h` its width and height.
They are **fractions** of your picture: 0 = the left (or top) edge, 1 = the
right (or bottom) edge, 0.5 = the middle. Easiest: drag the green boxes in the
art helper and copy the line it gives you.

What the player sees in a doorway:

* **Light off:** what **you painted** in the doorway, a little darker. (Or your
  `darkImage`, if you give one.)
* **Light on:** a lit hallway, and the monster if it's there. Draw your own
  empty, lit hallway as `litImage` if you like.
* **Door shut:** a shutter, or your `closedImage`. You don't need to draw it
  cracked: when a door is held shut too long, the game cracks and shakes it.

Make `darkImage`, `litImage` and `closedImage` the same shape as their door box.

**Three more spots** you can mark in your desk room (under `office` in
`config.js`; take away the `//` at the start of the line to switch it on):

* `clock: { x, y, r }` — the alarm clock on your desk. `x` and `y` are the
  middle of its face, `r` how big the face is (a fraction of the picture's
  height). **Draw the clock without hands**: the game draws hands that show the
  night's real time. When Lucidity is very low they sometimes jump ahead. At
  6 AM the alarm rings right there.
* `window: { x, y, w, h }` — the window box, like a door box. A shadow walks past
  it when a monster is close, and when Lucidity runs out something stands in it.
* `lamp: { x, y }` — the middle of your desk lamp's light. Sometimes it breathes.

Click on the clock or the lamp in the art helper and it writes the whole
`clock:` / `lamp:` line for you; drag a box around the window for the
`window:` line. If your room has no
clock, window or lamp, leave them out: the game then skips those effects.

---

## 5. Your bedroom and the morning

Every night starts in your bedroom: you fall asleep, count, and drop into the
dream. At 6 AM the alarm rings and you wake up in the same room.

* `assets/rooms/bedroom.png` — your room **seen from your bed**, 1600 × 900.
  Draw it in normal daylight colours: the game makes it dark blue at night and
  warm in the morning. (Or draw a separate morning picture as
  `bedroom.morningImage`.)
* `morning.evidence` — something follows you out of the dream. Night 2: the
  closet door is open a crack. Night 3: the "he walks at night" drawing is on
  the bedside table. Night 4: a scrap of pink collar lies on the floor. Draw
  your own as **see-through PNGs** and put the path next to the night's number:

  ```js
  morning: { evidence: { 2: "", 3: "assets/rooms/drawing.png", 4: "" } },
  ```

  To move one, write `{ image: "…", x: 0.15, y: 0.76, w: 0.08, h: 0.04 }`
  instead: a box in your bedroom picture, like a door box. The picture stands
  on the bottom of the box.

The big alarm clock in the morning is drawn by the game.

---

## 6. Camera rooms

One picture per camera, **1600 × 900** (16:9):

| File | Camera |
|---|---|
| `assets/rooms/cam1_nursery.png` | CAM 1, The Nursery (Redhorn starts here) |
| `assets/rooms/cam2_hall.png` | CAM 2, The Endless Hall |
| `assets/rooms/cam3_parlor.png` | CAM 3, Drowned Parlor |
| `assets/rooms/cam4_stairs.png` | CAM 4, Stairs to Nowhere |
| `assets/rooms/cam5_west.png` | CAM 5, West Hall (right outside your left door) |
| `assets/rooms/cam6_east.png` | CAM 6, East Hall (right outside your right door) |

* **Draw the rooms empty.** The game puts your animated monster in by itself,
  using its `poses`.
* **Keep important things away from the edges.** The camera picture is zoomed
  in a little and slowly drifts left and right, so about 6% of the top and
  bottom never shows, and the sides come and go. A picture that isn't 16:9 gets
  its top and bottom (or sides) cut off.
* Each camera line in `config.js` can have:
  * `name` and `label` — what the camera is called ("CAM 3 — DROWNED PARLOR").
  * `map: { x, y }` — where its button sits on the little camera map (0 to 1).
  * `sound` and `soundVol` — what you hear while you watch it, like
    `sound: "water_drip", soundVol: 0.35` (a name from `sounds:`; 0 = silent,
    1 = loudest).
  * `dreamName` — when Lucidity is very low, the camera's name sometimes slips
    into this for a blink. Without it, the words of its name get mixed up.
* Add a camera by copying a line in `cameras:` and giving it a new `id`.
  Keys 1–9 pick cameras.

**CAM 7, "Your Room".** Once a night (from Night 3) a camera that isn't on the
map appears: it films *you* from behind. Look away, look back, and something
stands behind your chair. The game builds this picture from your desk room,
but you can draw it as `assets/rooms/cam7_you.png`: your desk room seen **from
behind and above**, with an **empty chair**. The game draws the back of your
head on it; `youCam.seat` says where (`x`, `y` = the middle of your head;
`size`: 1 = normal).

---

## 7. Monsters

### Drawing the frames

* Each monster is a list of **frames**: see-through PNGs, played in order like
  a flip-book. Redhorn has 6.
* Use the **same canvas size** for every frame, and keep the monster in the
  same spot on each one (the onion skin in *Extras* shows you).
* Crop close to its body: then the sizes in `poses` and `doorPose` behave the
  way you expect.
* White background? Ask Claude to cut it out. Redhorn's frames were cut out of
  your video that way.

### Adding a monster, step by step

1. Make a folder `assets/monsters/shade/` and save its frames there as
   `frame1.png`, `frame2.png` …
2. Open `js/config.js` and find `monsters: [`. Right after Redhorn's whole
   `{ … }` block (after its last `},`), paste this:

   ```js
       {
         id: "shade",
         name: "The Shade",
         behavior: "shy",
         color: "#5ad1ff",
         description: "It only moves when nobody is looking.",
         frames: [
           "assets/monsters/shade/frame1.png",
           "assets/monsters/shade/frame2.png",
         ],
         fps: 4,
         jumpscareSound: "jumpscare",
         presenceSound: "",
         levels: [0, 0, 4, 7, 10],
         hourBoost: { 3: 1 },
         moveEvery: 5,
         waitAtDoor: [3, 6],
         start: "parlor",
         path: {
           parlor: ["west"],
           west:   ["door:left"],
         },
         retreat: ["parlor"],
         poses: {
           parlor: { x: 0.40, y: 1.02, h: 0.80 },
           west:   { x: 0.55, y: 1.05, h: 0.90 },
         },
         doorPose: {
           left: { x: 0.55, y: 1.00, h: 0.70 },
         },
       },
   ```

   Mind the commas: every `{ … }` block in the list ends with `},`.
3. Change its `id` (one word, no spaces), `name`, `frames`, its brain
   (`behavior`, see below) and its route (`start`, `path`, `retreat`). Give it a
   different route from Redhorn's, like the west side only.
4. Reload the game with `?dev`, press **Tab** until the box says its name, and
   place it with **G** on each camera it walks through, and in its doorway.
   Aim its jumpscare with **J**. Paste the lines into its block.

Until you draw its frames, a new monster is a **hunched shadow with glowing
eyes** (in its `color`), so you can try it out first.

### Pick a brain

The `behavior` word decides how a monster plays. Each brain asks the player to
do something different. **Bring in at most one new brain per night**, so
players can learn it.

| Word | What it does | What the player must do | Extra settings |
|---|---|---|---|
| `"walker"` ⭐ start here | Walks its path room by room to your door, waits, breathes, then comes in (door open) or bangs and leaves (door shut). Redhorn is a walker. | Listen for breathing, check the light, shut the door, open it after the bang. | — |
| `"shy"` ⭐ start here | **Can't move while you watch it** on a camera (it freezes, even its animation). Every 15 seconds you don't look at it, it gets braver (+2 levels). Staring doesn't bother it. | Keep glancing at it on the cameras. | — |
| `"sleeper"` ⭐ start here | **Sleeps** where it stands. A noise wakes it: a pinch, or a bang on a door. Then it takes one step at once and stays awake for 6 seconds. Once at your door it acts like a walker. | Play quietly: pinch less, and don't let the others bang on your doors. | `sleepFrames` (optional): pictures of it asleep. Without them it is shown darker, with z's. |
| `"trickster"` | A walker whose **footsteps near your doors come from the wrong side**. Its breathing never lies. | Don't trust its footsteps. Listen for the breathing, check with the light. | — |

Every brain keeps the game's promise: a monster at your door **always breathes
first**, and waits at least `minWarning` seconds before it can come in.

### Every monster setting

| Setting | What it does |
|---|---|
| `id` | Its short name for the game (one word, no spaces). Every monster needs its own. |
| `name` | Its name for players ("REDHORN FOUND YOU"). |
| `behavior` | Its brain, see above. Leave it out for `"walker"`. |
| `description` | A line about it in *Extras*. |
| `color` | Eye colour while it is still a shadow, like `"#5ad1ff"`. |
| `frames` | Its animation pictures, in order. |
| `fps` | Animation speed in frames per second (Redhorn: 4). |
| `sleepFrames` | Sleepers only: pictures of it asleep. |
| `jumpscareFrames` | Special close-up frames for its jumpscare (`null` = its normal frames). |
| `jumpscareFps` | How fast those play (14). |
| `jumpscareFocus` | Which part of the picture rushes at you: `{ x: 0.5, y: 0.2 }` is near the top middle, where a face usually is. Aim it with **J**. |
| `jumpscareSound` | The scream: a name from `sounds:`. |
| `presenceSound` | The noise it makes in the walls, louder and clearer the closer it gets (Redhorn clicks). A name from `sounds:`, or `""` for a silent monster. |
| `sounds` | Its own sounds instead of the usual ones: `sounds: { steps: "moan", breath: "whisper", bang: "door_bang" }`. You can also change `far` (its sound far away). |
| `levels` | How hungry it is on Nights 1–5, from **0** (asleep all night: it never moves) to **20** (relentless). Use 0 to bring a monster in on a later night. |
| `hourBoost` | Extra hunger from that hour on: `{ 2: 1, 4: 2 }` = +1 at 2 AM, +2 more at 4 AM. A monster at level 0 that night stays asleep anyway. |
| `moveEvery` | Seconds between its chances to move (Redhorn: 4.8). Smaller = faster. |
| `waitAtDoor` | `[shortest, longest]` seconds it waits at your door before it comes in or bangs. |
| `start` | The camera room it starts in (a camera `id`). |
| `path` | Where it can go next from each room. `"door:left"` and `"door:right"` are your doors. Write a room twice to make it more likely. |
| `retreat` | Rooms it runs back to after it bangs on a shut door. |
| `poses` | Where it stands in each camera picture: `x` = the middle of its body, `y` = its feet (above 1 = feet below the picture), `h` = its height (1 = as tall as the picture), `flip: true` mirrors it. Place them with **G**. |
| `doorPose` | The same, inside the `left` / `right` doorway. |

---

## 8. Sounds

All the sounds are real recordings from OpenGameArt.org, under free licenses
(see `CREDITS.md`). To swap one, put a new file in `assets/audio/` and change
its path in `sounds:` in `config.js`. Keep short sounds short (a few seconds);
the long music tracks (`ambience`, `menu_music`, `morning`, `music_box`) play
straight from their files, so they can be big.

| Name | When you hear it |
|---|---|
| `ambience` | the night's background |
| `menu_music` | the title screen |
| `music_box` | while you watch the Nursery |
| `whisper`, `moan` | whispers in the dark, a moan far away |
| `heartbeat` | when danger is close |
| `footsteps`, `breathing`, `door_bang` | a monster walking, breathing at your door, banging on it |
| `jumpscare` | the scream |
| `door_close`, `door_open` | your doors |
| `light_buzz` | a door light |
| `power_down` | your Lucidity runs out |
| `alarm` | the 6 AM alarm clock (the hero sound) |
| `morning` | birds in the morning |
| `cam_open`, `cam_close`, `cam_switch`, `static` | the cameras |
| `ui_click`, `hour_chime` | buttons, each new hour |
| `clock_tick` | *optional:* falling asleep, the last half hour, Lucidity running out |
| `type_key` | *optional:* the dream voice typing |
| `reality_snap` | *optional:* pinching yourself |
| `redhorn_click` | *optional:* Redhorn in the walls |
| `door_strain` | *optional:* a door held shut too long |
| `hypnic_jolt` | *optional:* falling into the dream |
| `water_drip` | *optional:* the Drowned Parlor |

If an **optional** sound is missing, the game uses a stand-in (another sound,
slowed down or muffled). If another one is missing, that moment is silent. The
art checklist lists both.

**A new sound for a monster:** add a line to `sounds:`, like
`growl: "assets/audio/growl.mp3",`, then use its name in the monster
(`jumpscareSound: "growl"` or `sounds: { breath: "growl" }`).

**Sound captions.** In *Settings → Sound captions* every sound is also shown as
words, on the side of the screen it came from ("‹ breathing"). It helps on
phones and for players who can't hear. The words are in `captions:` in
`config.js`; change them as you like. The names:

| Caption | When |
|---|---|
| `steps`, `stepsNear` | footsteps far away, and close to a door |
| `breath`, `breathMuffled`, `breathClose` | breathing at an open door, behind a shut one, right next to you |
| `bang` | a bang on a door |
| `far`, `whisper`, `whisperAbove` | a moan far off, whispering, whispering in the ceiling |
| `chime` | each new hour (`{0}` becomes the time) |
| `powerDown`, `clockSlow` | Lucidity runs out |
| `strain` | a door held shut too long |
| `ticking`, `nearRing`, `alarm` | the last half hour, the alarm almost ringing, the alarm |

**Scares** (also in Settings): *Gentle* makes the jumpscare quieter and softer
for younger players. It uses your monster's own pictures, so a new monster
needs nothing extra.

---

## 9. Words

* `title` and `subtitle` — the name on the menu.
* `fallAsleep` — what you count in your head while you fall asleep (one line per night).
* `finale` — after Night 5 the voice says `line`, then the credits roll. They
  start with the **first line of `credits`**, which is you: change `"You!"` to
  your name if you like. `thanks` is the very last line.

### The dream voice (`dreamVoice`)

The voice talks to the player at the start of each night. It speaks in
**beats**: one or two short sentences at a time. Write each night's words
between two `` ` `` marks, and leave an **empty line** to start the next beat:

```js
2: `You came back. Most people don't remember the first night.

    It remembers you. It's quicker now.`,
```

Each beat types itself out with a typewriter clack, stays long enough to read,
then the next one comes. Players can click it to hurry it on.

Two tricks you can use anywhere in the words:

* **`{wrong|right}`** — the voice types the **wrong** words in a red, dripping
  hand, stops, rubs them out and writes the **right** ones.
  `It's {behind you|tall}.` types "behind you", deletes it, and writes "tall".
  It is creepiest when it is rare: once or twice a night.
* **`{A}`** — shows a key to press, drawn like the keys on the buttons. On phones
  and tablets it is left out.

More voice lines: `endless` (the Endless Dream), `lie` (the first time the
light finds a fake), `falseDawn` (when Night 5's early alarm stops), and
`after: { 5: "Wake up." }` (it speaks once more, about 20 seconds after it went
quiet; leave a night out for nothing).

### The first-night lesson (`tutorial`)

The very first Night 1 is a lesson: the voice says one step at a time and
**waits until the player has done it**. The clock waits too. Each step is
`{ say: "…", wait: "…" }`:

| `wait:` | the player has to… |
|---|---|
| `"lookLeft"` / `"lookRight"` | look all the way to that side |
| `"light"` | turn on a light |
| `"cams"` | open the cameras |
| `"cam:west"` | look at that camera (use its `id`) |
| `"door"` / `"doorOpen"` | shut a door / open it again |
| `"pinch"` | pinch themselves |
| `"time:4"` | nothing: wait 4 seconds |

An optional `point:` says what the dashed ring goes around: `"leftLight"`,
`"rightLight"`, `"leftDoor"`, `"rightDoor"`, `"cameras"`, `"pinch"`,
`"lucidity"`, `"clock"`, `"left"` or `"right"` (arrows at that edge), or
`"none"`. After 25 seconds a step moves on by itself, so nobody gets stuck.
If you rename the West Hall camera, change the `cam:` step too. Players can
replay the lesson from *Extras*.

---

## 10. Night rules

`nights:` has one `{ … }` block per night, Night 1 first. Leave a setting out
and the game uses its own value.

| Setting | What it does |
|---|---|
| `drain` | How fast Lucidity (your "power") drains. Bigger = harder. |
| `stepChance` | How often you hear footsteps (1 = always, 0.5 = half the time). Breathing is never skipped. |
| `lies` | `true` = below the line on the Lucidity bar, the dream shows fake monsters. |
| `pinchRadius` | How many rooms away a pinch is heard. |
| `youCam` | `true` = CAM 7 can appear tonight. |
| `stare` | Seconds you can watch a monster on a camera before it steps closer (0 = never). |
| `gasp` | Seconds a door can stay shut before it gasps open by itself (0 = never; never with a monster behind it). |
| `doorFree` | Seconds a shut door is cheap, before it costs more and more. |
| `falseDawn` | The hour of a fake 6 AM (5.33 = 5:20 AM). Leave it out for none. |

More settings, each explained in `config.js`:

* `hourSeconds` — how many real seconds one hour lasts (75).
* `endlessRules`, `endlessDrain` — the same rules for the Endless Dream.
* `pinch` — how much a pinch gives back (`amount`), how often (`cooldown`),
  more when you are low (`lowBonus`), less when you are high (`highPenalty`).
* `doorStrain` — how fast a held door gets dearer (`rampSeconds`, `maxCost`),
  and how long a monster waits at a shut door before it bangs (`giveUpAfter`).
* `minWarning` — the fairness promise: seconds a monster must breathe at your
  door before it can come in (2.5).
* `lies` — where the line on the Lucidity bar is (`below`: 60%) and how often a
  lie comes (`every`).
* `director` — small "wrong" things in the dream (the lamp breathes, a doorway
  shows another room …): `enabled`, `quietMinutes`, `minGap`, `maxGap`.

When Lucidity drops below 30%, the HUD dreams too: the eye droops, and its
words slip for a blink ("13 AM", "LUCKILY"). The percentage itself never lies.

---

## 11. When something goes wrong

* **"Oops! The dream got stuck."** Something in `config.js` stops the game
  from starting. From a web server it shows the line, and the lines before it,
  with an arrow. The mistake is usually **at the end of the line before the
  arrow**: a missing comma `,`. Also check that every `{` has a `}`, every `[`
  a `]`, and every `"` another `"`. Opened straight from the file, the browser
  won't say which line: undo your last change, or play from a web server.
* **"something needs a look: add ?dev to the address"** on the first screen:
  the game started, but a sound or a monster frame is missing, or `config.js`
  has a typo the game fixed by itself for now. Open `?dev`: the helper box
  lists everything.
* **A monster never moves:** is its level 0 tonight (asleep all night)? Can its
  `path` reach `"door:left"` or `"door:right"`? (The helper box warns when it
  can't.)
* **My picture doesn't show up:** check the file name, capital letters too, and
  that it's in the right folder. Press **U** in the art helper to reload.
* **Capital letters in room names don't matter** (`"Hall"` = `"hall"`), and a
  small typo is fixed for you (with a warning), but it's better to fix it.
