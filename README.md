# Pug Tag VR

A pixel-art tag game where you play as a legless pug with long arms. It runs in the browser on VR headsets (WebXR, e.g. Quest), desktop and phones. It is a single `index.html` with no build step. Host it anywhere (GitHub Pages works) and open it.

## How you move

- **VR:** you don't need any buttons to move. Slap your paws on the ground and push the world away to run. Your paws stick to every surface, so you can climb walls, trees, fridges and rockets hand over hand. Push down hard and let go to launch: the speed of your last push carries into the jump. You can hang from walls, and IT pugs get stronger pushes.
- **Desktop:** `WASD` to run, `Space` to jump and wall-jump, mouse to look. Hold `LMB` near any surface to grab and climb, then release to fling yourself. Click a pug to tag it. `E` presses in-world buttons and picks up balls, `Q` throws, `Tab` shows scores, `Esc` opens the menu, `M` toggles music.
- **Phone / tablet:** the left stick runs and dragging on the right side looks around. Use the **JUMP**, **GRAB** (hold to climb) and **USE** buttons. You can also tap world buttons directly.

## Features

- **Pixel textures everywhere.** Every texture is generated in code: grass, bark, planks, bricks, tiles, candy, moon rock and more. They use nearest-neighbour filtering and baked per-face shading.
- **5 original maps:**
  - **Bark Park:** the hub, with the lodge, pet shop, playground, monkey bars, slide, trampoline and treetop bridge.
  - **Giant Kitchen:** you're tiny; climb chairs, the table, counters and the fridge.
  - **Junkyard:** car stacks, shipping containers, a crane and a bouncy mattress.
  - **Candy Cliffs:** cake cliffs, bouncy gumdrops, lollipops, a donut and cotton-candy clouds.
  - **Moon Base:** low gravity, domes, a rocket and a gantry.
- **NPC pugs.** Each has a name, fur colour and random cosmetics. They hop like real arm-runners, climb walls, plan routes over a navigation graph, chase and flee, lunge at you, wave, chat, bark, and get distracted by tennis balls.
- **Game modes:** Infection, Classic Tag (no tag-backs) and Casual. There are 0 to 11 bots, three skill levels, a round timer, a scoreboard and bone rewards.
- **In-world buttons.** A PUG-OS terminal in every spawn kennel sets the map, mode, bots, skill, VR arm length, turning, stick move, music, sound and name. The lodge also has a fur-colour board, a scoreboard and a mirror.
- **Cosmetics.** There are 38 items across hat, face, neck and back slots, plus 12 fur colours. Buy them with bones at the pet shop and admire yourself in the mirror.
- **Items:**
  - **Bones:** collect them, earn them by tagging and surviving, and look for gold bones.
  - **Zoomies:** faster movement.
  - **Bubble:** blocks one tag.
  - **Moon Paws:** low gravity.
  - **Tennis balls:** grab and throw them.
- **Synthesised audio.** Paw taps differ by surface, plus barks, stings, a boing for bouncy surfaces and a chiptune track for each map.
- **VR comforts:** a wrist watch HUD, floating banners, haptics, and snap or smooth turning.

Bones, cosmetics and settings save in your browser (`localStorage`).
