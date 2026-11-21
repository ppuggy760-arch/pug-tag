# Pug Tag VR

A pixel-art tag game where you play as a legless pug with long arms. It runs in the browser on VR headsets (WebXR, e.g. Quest), desktop and phones. It is a single `index.html` with no build step. Host it anywhere (GitHub Pages works) and open it.

## How you move

- **VR:** you don't need any buttons to move. Slap your paws on the ground and push the world away to run. Your paws stick to every surface, so you can climb walls, trees, fridges and rockets hand over hand. Push down hard and let go to launch: the speed of your last push carries into the jump, and a strong push sends you several metres up. You can hang from walls and monkey bars, and IT pugs get stronger pushes.
- **Desktop:** `WASD` to run, `Space` to jump and wall-jump, mouse to look. Hold `LMB` near any surface to grab and climb, then release to fling yourself. Click a pug to tag it. `E` presses in-world buttons and picks up balls, `Q` throws, `Tab` shows scores, `Esc` opens the menu (it pauses the round), `M` toggles music, and the arrow keys also turn. Touchscreen laptops keep full mouse controls; the on-screen controls appear when you touch the screen.
- **Phone / tablet:** the left stick runs and dragging on the right side looks around. Use the **JUMP**, **GRAB** (hold to climb) and **USE** buttons. You can also tap world buttons directly.

## Features

- **Pixel textures everywhere.** Every texture is generated in code: grass, bark, planks, bricks, tiles, candy, moon rock and more. They use nearest-neighbour filtering and baked per-face shading.
- **5 original maps:**
  - **Bark Park:** the hub, with the lodge, pet shop, playground, monkey bars, slide, trampoline and treetop bridge.
  - **Giant Kitchen:** you're tiny; climb chairs, the table, counters and the fridge.
  - **Junkyard:** car stacks, shipping containers, a crane and a bouncy mattress.
  - **Candy Cliffs:** cake cliffs, bouncy gumdrops, lollipops, a donut and cotton-candy clouds.
  - **Moon Base:** low gravity, domes, a rocket and a gantry.
- **NPC pugs.** Each has a name, fur colour, random cosmetics and long furry arms with big padded paws. They hop like real arm-runners, climb walls, plan routes over a navigation graph (including hops up onto tables and counters, and a way back down from every high spot), climb after you when you hide, chase and flee, lunge at you, wave, chat, bark, and get distracted by tennis balls.
- **Game modes:** Infection, Classic Tag (no tag-backs) and Casual. There are 0 to 11 bots, three skill levels, a round timer, a scoreboard and bone rewards.
- **In-world buttons.** A PUG-OS terminal in every spawn kennel sets the map, mode, bots, skill, VR arm length, turning, stick move, music, sound and name. The lodge also has a fur-colour board, a scoreboard and a mirror.
- **Cosmetics.** There are 38 items across hat, face, neck and back slots, plus 12 fur colours. Buy them with bones at the pet shop and admire yourself in the mirror.
- **Items:**
  - **Bones:** collect them, earn them by tagging and surviving, and look for gold bones.
  - **Zoomies:** faster movement.
  - **Bubble:** blocks one tag.
  - **Moon Paws:** low gravity.
  - **Tennis balls:** grab and throw them.
- **Layered sound design.** Every sound effect is a "recipe" that combines short CC0 sound samples (pitched, sliced, filtered) with synthesized layers (tones, filtered noise, sweeps). Examples are jumps, surface-specific paw taps, landings, tags, pickups, the shop, pug barks/yips/growls and a looping ambience per map. The game bakes each sound effect into a few varied buffers while the title screen shows, and bakes each map's ambience loop the first time that map loads. It plays them with distance fading, stereo panning and voice limits. If baking isn't possible, most sounds fall back to a simple live-synth version. There is also a chiptune track for each map.
- **VR comforts:** a wrist watch HUD (lava wait countdown, power-up timers), floating banners (including shop and bone messages), haptics, and snap or smooth turning. Stick move works with your paws resting on the floor. Grip and trigger both hold a ball; it's thrown when you let go of both. If you leave VR (Meta menu, headset asleep, or you pressed PLAY), an **ENTER VR** button on the HUD and in the pause menu takes you back in.
- **No sound?** Browsers keep audio off until you press something. In VR, pull a trigger; on desktop or a phone, click, press a key or tap. The game wakes the audio by itself if the headset or browser pauses it later. The watch (or the HUD on desktop) shows **NO SOUND** while the audio is paused and **SFX OFF** when sound effects are switched off on the terminal's SOUND key or in the settings. On an iPhone, the game plays even with the silent switch on (iOS 17 and newer).

Bones, cosmetics and settings save in your browser (`localStorage`).

## Sound credits

All sampled sound material is dedicated to the public domain (CC0 1.0), embedded as small mono MP3 clips inside `index.html`:

- [Kenney](https://kenney.nl): sound effects from the Starter Kit 3D Platformer, FPS, City Builder and Racing. Each kit's README states: "Assets included in this package (2D sprites, 3D models and sound effects) are CC0 licensed". The Racing kit's skid sound is by [Landeplage](https://github.com/Landeplage), also CC0.
- [uisfx](https://uisfx.com) (npm package `uisfx`, © Yuki Capital): the UI sound packs. Its audio files are dedicated to the public domain under CC0 1.0 (the package code is MIT; none of it is used here).

These clips are mixed with synthesized layers by the game's sound engine. Attribution isn't required, but thank you, Kenney, Landeplage and uisfx!
