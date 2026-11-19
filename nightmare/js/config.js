/* =====================================================================
   GAME CONFIG  —  this is the file YOU edit.
   ---------------------------------------------------------------------
   * Every picture path is relative to the nightmare/ folder.
   * If a picture is missing, the game shows its own stand-in so it still
     runs: a photo room made from free pictures (in assets/scenes/).
     The moment you drop your real picture at that path, it is used.
   * Positions (x, y, w, h) are fractions: 0 = left/top edge,
     1 = right/bottom edge, 0.5 = middle.
   * Open the game with  index.html?dev  for ART HELPER mode
     (shows door boxes, lets you click to place monsters on cameras
     and copies the numbers for you).  See HOW-TO-ADD-ART.md.
   ===================================================================== */
window.GAME_CONFIG = {

  title: "UNTIL THE ALARM",
  subtitle: "a nightmare in five dreams",

  /* How many real seconds one in-game hour lasts (12 AM -> 6 AM = 6 hours). */
  hourSeconds: 75,

  /* ------------------------------------------------------------------
     THE FIVE NIGHTS. One { ... } block per night, Night 1 first.
     Leave a setting out and the game uses its own value for it.
       drain:       how fast Lucidity (your "power") drains. Bigger = harder.
       stepChance:  how often you hear its footsteps (1 = always, 0.5 = half the time).
       lies:        true = when Lucidity is low, the dream can show fake monsters.
       pinchRadius: how many rooms away a pinch can be heard.
       youCam:      true = the spooky "CAM 7" can appear once tonight.
       stare:       seconds you can watch it on a camera before it steps closer (0 = never).
       gasp:        seconds a shut door can stay shut before it gasps for air and opens
                    by itself (0 = never). It never opens with a monster behind it.
       doorFree:    seconds a door can stay shut before it costs extra Lucidity
                    (see doorStrain below).
       falseDawn:   the hour a fake 6 AM happens (5.33 = 5:20 AM). Leave out for none.
     (Old config files with lucidityDrain: [ ... ] still work.)
     ------------------------------------------------------------------ */
  nights: [
    { drain: 0.09, stepChance: 1,    lies: false, pinchRadius: 1, youCam: false, stare: 0, gasp: 0,  doorFree: 14 },
    { drain: 0.10, stepChance: 1,    lies: true,  pinchRadius: 1, youCam: false, stare: 0, gasp: 0,  doorFree: 12 },
    { drain: 0.11, stepChance: 0.8,  lies: true,  pinchRadius: 2, youCam: true,  stare: 0, gasp: 0,  doorFree: 11 },
    { drain: 0.12, stepChance: 0.65, lies: true,  pinchRadius: 2, youCam: true,  stare: 5, gasp: 32, doorFree: 10 },
    { drain: 0.125, stepChance: 0.5, lies: true,  pinchRadius: 2, youCam: true,  stare: 4, gasp: 28, doorFree: 10, falseDawn: 5.33 },
  ],
  /* The same settings for the Endless Dream (custom night). */
  endlessRules: { stepChance: 0.6, lies: true, pinchRadius: 2, youCam: true, stare: 4.5, gasp: 28, doorFree: 10 },
  /* Lucidity drain in the Endless Dream. */
  endlessDrain: 0.13,

  /* PINCH YOURSELF: gives back Lucidity, but it is LOUD. A monster close to
     your doors (see pinchRadius above) steps one room closer straight away,
     one waiting at a door stops waiting (if it was breathing at an OPEN door,
     it comes straight in!), and the rest move at their next chance.
       amount:      how much Lucidity a pinch gives back.
       cooldown:    seconds before you can pinch again.
       lowBonus:    below 30% Lucidity it gives this many times more (2 = double).
       highPenalty: above 60% it gives only this much of it (0.25 = a quarter). */
  pinch: { amount: 3, cooldown: 60, lowBonus: 2, highPenalty: 0.25 },

  /* HELD-BREATH DOORS: a shut door is like holding your breath. It is cheap
     for a while (doorFree seconds, see nights above), then it costs more and
     more Lucidity, and it groans and cracks. Open it to let it breathe out.
       rampSeconds: seconds it takes to go from normal cost to the most it can cost.
       maxCost:     the most one shut door can cost (1 = never extra, 3 = three times).
       giveUpAfter: seconds a monster waits at a shut door before it bangs and leaves. */
  doorStrain: { rampSeconds: 10, maxCost: 3, giveUpAfter: 8 },

  /* IT ALWAYS BREATHES FIRST: a monster at your door must breathe (you can
     hear it) and wait at least this many seconds before it can come in.
     That keeps the game fair even if you make a monster very fast. */
  minWarning: 2.5,

  /* THE DREAM LIES: when your Lucidity drops below the line on the bar, the
     dream sometimes shows you a FAKE monster (from Night 2, see "lies" in
     nights above). A fake never moves, glows see-through violet, and its
     breathing runs backwards. Shine the light on it and it fades away, or
     pinch yourself and every lie is gone. A fake can't hurt you.
       below: the line on the Lucidity bar (60 = the lies start below 60%).
       every: how many seconds between two lies: [shortest, longest]. */
  lies: { below: 60, every: [35, 60] },

  /* THE DREAM DIRECTOR: small "wrong" things that happen in the dream
     (the lamp breathes, a lit doorway shows another room, whispering in the
     ceiling, the room stretches wider). Each one comes after a moment of
     silence, and never while a monster is close to your doors.
       enabled:      false = none of them (CAM 7 still comes).
       quietMinutes: in-game minutes of quiet at the start of the night (50 = 12:50 AM).
       minGap, maxGap: seconds between two of them (fewer when the night is calm). */
  director: { enabled: true, quietMinutes: 50, minGap: 40, maxGap: 90 },

  /* ------------------------------------------------------------------
     THE DESK ROOM (the office you sit in).
     image: a WIDE picture works best (about 2400 x 900, or 8:3).
            The player looks left/right across it.
     image: if your picture isn't wide enough (a square or 4:3 canvas), the
            game zooms in so you can still look around, and cuts off a bit
            of the top and bottom. ?dev mode tells you.
     doors: where the two doorways are in that picture (in ?dev mode you
            can drag the green boxes into place and copy the numbers).
       darkImage  (optional) doorway with the light OFF. Leave it "" and
                  the doorway YOU painted in office.png shows, a bit darker.
       litImage   (optional) doorway with the light ON (empty hallway).
                  Leave it "" for the built-in lit hallway.
       closedImage(optional) the door when it is shut
     Leave an image "" to use the built-in look.
     ------------------------------------------------------------------ */
  office: {
    image: "assets/rooms/office.png",
    doors: {
      left:  { x: 0.030, y: 0.178, w: 0.150, h: 0.700, darkImage: "", litImage: "", closedImage: "" },
      right: { x: 0.820, y: 0.178, w: 0.150, h: 0.700, darkImage: "", litImage: "", closedImage: "" },
    },
    /* When you draw your own desk room, you can tell the game where three
       things are in it (use ?dev and click on them to read the numbers).
       Take away the // at the start of the line to switch it on.
         clock:  the alarm clock on the desk. x, y = the middle of its face,
                 r = how big the face is (a fraction of the picture height).
                 Draw the clock WITHOUT hands: the game draws hands that show
                 the night's real time. At 6 AM it rings there.
         window: the window box (x, y, w, h, like the doors). Shadows walk
                 past it, and when your Lucidity runs out, something comes
                 and stands in it.
         lamp:   the middle of your desk lamp's light. Sometimes it breathes.
       Leave them out if your room has no clock, window or lamp. */
    // clock:  { x: 0.604, y: 0.651, r: 0.029 },
    // window: { x: 0.233, y: 0.178, w: 0.104, h: 0.300 },
    // lamp:   { x: 0.396, y: 0.567 },
  },

  /* ------------------------------------------------------------------
     YOUR BEDROOM: every night starts and ends here, in the real world.
     image:        ONE picture of your room, seen from your bed (1600 x 900).
                   The game makes it dark blue at night and warm in the morning.
     morningImage: (optional) a different picture for the morning. "" = the
                   game warms up "image" by itself.
     Until you draw it, the game shows its own photo of a bedroom.
     ------------------------------------------------------------------ */
  bedroom: { image: "assets/rooms/bedroom.png", morningImage: "" },

  /* What you count in your head while you fall asleep (one line per night). */
  fallAsleep: {
    1: "one… two… three…",
    2: "one… two… two… two…",
    3: "one… three… nine… the house is counting with you",
    4: "don't count. it counts backwards.",
    5: "don't count. just listen for the alarm.",
    endless: "there is no counting here.",
  },

  /* THE MORNING. Something follows you out of the dream:
     night 2: the closet door is open a crack,
     night 3: the crayon drawing from the desk-room wall ("he walks at
              night") is on your bedside table,
     night 4: a scrap of pink collar lies on the floor.
     Draw your own (a transparent PNG) and put its path here.
     "" = the game draws it for you.
     To move it, write  { image: "…", x: 0.15, y: 0.76, w: 0.08, h: 0.04 }
     instead (where it goes in your bedroom picture, like the door boxes). */
  morning: { evidence: { 2: "", 3: "", 4: "" } },

  /* THE LAST MORNING (after Night 5): what the dream voice says, then the
     credits roll. The credits start with the FIRST line of "credits" at the
     bottom of this file: that's you! "thanks" is the very last line. */
  finale: { line: "See? I told you I'd be the one ringing.", thanks: "Thank you for waking up." },

  /* ------------------------------------------------------------------
     CAMERAS. One entry per room you can watch.
     image:    the room picture (16:9 works best, e.g. 1600 x 900).
     map:      where its button sits on the little camera map (0..1).
     sound:    (optional) what you hear while you watch this room: the name
               of one of the sounds at the bottom of this file.
     soundVol: how loud that is (0 = silent, 1 = loudest).
     dreamName:(optional) when your Lucidity is very low, the camera's name
               sometimes slips into this for a blink. Leave it out and the
               words of its name get mixed up instead ("HALL ENDLESS THE").
     ------------------------------------------------------------------ */
  /* CAM 7, "YOUR ROOM": once a night (from Night 3, see youCam in nights) a
     camera that isn't on the map appears. It films YOU from behind...
       image: (optional) your desk room seen from behind and above, with an
              EMPTY chair (1600 x 900). Until you draw it, the game shows its
              own photo of it.
       seat:  where the back of your head goes in YOUR picture (x, y = the
              middle of your head, size: 1 = normal). */
  youCam: { image: "assets/rooms/cam7_you.png", seat: { x: 0.5, y: 0.5, size: 1 } },

  cameras: [
    { id: "nursery", label: "CAM 1", name: "The Nursery",       image: "assets/rooms/cam1_nursery.png", map: { x: 0.50, y: 0.10 }, sound: "music_box",  soundVol: 0.25, dreamName: "Nobody's Nursery" },
    { id: "hall",    label: "CAM 2", name: "The Endless Hall",  image: "assets/rooms/cam2_hall.png",    map: { x: 0.50, y: 0.33 }, sound: "clock_tick", soundVol: 0.3 },
    { id: "parlor",  label: "CAM 3", name: "Drowned Parlor",    image: "assets/rooms/cam3_parlor.png",  map: { x: 0.19, y: 0.53 }, sound: "water_drip", soundVol: 0.35 },
    { id: "stairs",  label: "CAM 4", name: "Stairs to Nowhere", image: "assets/rooms/cam4_stairs.png",  map: { x: 0.81, y: 0.53 } },
    { id: "west",    label: "CAM 5", name: "West Hall",         image: "assets/rooms/cam5_west.png",    map: { x: 0.19, y: 0.76 }, sound: "light_buzz", soundVol: 0.18 },
    { id: "east",    label: "CAM 6", name: "East Hall",         image: "assets/rooms/cam6_east.png",    map: { x: 0.81, y: 0.76 }, sound: "light_buzz", soundVol: 0.18 },
  ],

  /* ------------------------------------------------------------------
     MONSTERS. Copy a whole { ... } block to add a new one
     (HOW-TO-ADD-ART.md, "Monsters → Adding a monster, step by step",
     shows you how).
     behavior: its BRAIN, one word (leave it out for "walker"):
              "walker"    walks its path to your door (like Redhorn)
              "shy"       can't move while you watch it on a camera, but
                          gets braver the longer you don't look
              "sleeper"   sleeps until a noise wakes it (a pinch, a bang)
              "trickster" its footsteps come from the WRONG side
                          (its breathing never lies)
     color:   (optional) the colour of its glowing eyes while it has no
              pictures yet, like "#5ad1ff" (it is a shadow until then).
     frames:  your animation pictures in order (transparent PNGs).
     sleepFrames: (optional, sleepers only) pictures of it asleep.
     fps:     animation speed (frames per second).
     levels:  how aggressive it is on nights 1-5 (0 = it sleeps all night, 20 = max).
     hourBoost: extra aggression from that hour on ({ 2: 1 } = +1 at 2 AM).
              A monster at level 0 that night never moves, boost or not.
     moveEvery: seconds between its chances to move.
     waitAtDoor: [shortest, longest] seconds it waits at your door before
              it comes in (it always breathes first, see minWarning).
     jumpscareSound: the sound its jumpscare makes (a name from sounds:).
     sounds:  (optional) its own sounds instead of the usual ones, e.g.
              sounds: { steps: "moan", breath: "whisper", bang: "door_bang" }
              (names from sounds: at the bottom of this file).
     path:    where it can walk next from each room. "door:left" /
              "door:right" means it reaches your door.
     retreat: rooms it runs back to when it finds the door shut.
     poses:   where it stands in each camera picture:
              x = middle of its body, y = where its feet are
              (above 1 = feet below the picture), h = height of the
              monster compared to the picture height. flip: true mirrors it.
     doorPose: same idea, but inside the doorway box of your desk room.
     Room names must match a camera id exactly (the game fixes capital
     letters for you, and ?dev mode lists any typos it finds).
     ------------------------------------------------------------------ */
  monsters: [
    {
      id: "redhorn",
      name: "Redhorn",
      behavior: "walker",        // its brain (see the list above)
      description: "It wears its skin like a borrowed coat. It never blinks, because the dream never asks it to.",
      frames: [
        "assets/monsters/redhorn/frame1.png",
        "assets/monsters/redhorn/frame2.png",
        "assets/monsters/redhorn/frame3.png",
        "assets/monsters/redhorn/frame4.png",
        "assets/monsters/redhorn/frame5.png",
        "assets/monsters/redhorn/frame6.png",
      ],
      fps: 4,
      jumpscareFrames: null,     // null = use the same frames, played fast
      jumpscareFps: 14,
      jumpscareFocus: { x: 0.5, y: 0.2 },  // which part of the picture lunges at you (0.2 = near the top/face)
      jumpscareSound: "jumpscare",
      presenceSound: "redhorn_click",    // the noise it makes in the walls: louder the closer it gets ("" = none)
      levels: [3, 6, 9, 12, 16],
      hourBoost: { 2: 1, 3: 1, 4: 2 },   // extra aggression at 2 AM, 3 AM, 4 AM
      moveEvery: 4.8,                    // seconds between move chances
      waitAtDoor: [3.5, 7],              // seconds it lingers at your door first
      start: "nursery",
      path: {
        nursery: ["hall"],
        hall:    ["parlor", "stairs"],
        parlor:  ["west", "west", "hall"],
        stairs:  ["east", "east", "hall"],
        west:    ["door:left"],
        east:    ["door:right"],
      },
      retreat: ["hall", "parlor", "stairs"],
      // These fit the game's built-in photo rooms (its feet on the floor, never under the camera map).
      // When you draw your own room, place Redhorn in it again with ?dev (see HOW-TO-ADD-ART.md).
      poses: {
        nursery: { x: 0.45, y: 0.80, h: 0.42 },               // on the carpet, by the crib
        hall:    { x: 0.49, y: 0.70, h: 0.30 },               // a little way down the endless hall
        parlor:  { x: 0.46, y: 0.83, h: 0.39 },               // standing in the water
        stairs:  { x: 0.46, y: 0.78, h: 0.36 },               // halfway up the stairs
        west:    { x: 0.45, y: 0.78, h: 0.41 },               // on the carpet runner
        east:    { x: 0.48, y: 0.78, h: 0.41, flip: true },
      },
      doorPose: {   // one step back in the hall, just behind your doorway
        left:  { x: 0.55, y: 0.87, h: 0.70 },
        right: { x: 0.45, y: 0.87, h: 0.70, flip: true },
      },
    },
  ],

  /* ------------------------------------------------------------------
     SOUNDS (real recordings downloaded from the internet — see CREDITS.md).
     Swap any file by changing its path.
     The ones marked "optional" can be missing: the game then uses a
     stand-in sound (a slowed-down or muffled copy of another one).
     ------------------------------------------------------------------ */
  sounds: {
    ambience:   "assets/audio/ambience.mp3",
    menu_music: "assets/audio/menu_music.mp3",
    music_box:  "assets/audio/music_box.mp3",
    whisper:    "assets/audio/whisper.mp3",
    heartbeat:  "assets/audio/heartbeat.mp3",
    jumpscare:  "assets/audio/jumpscare.mp3",
    footsteps:  "assets/audio/footsteps.mp3",
    breathing:  "assets/audio/breathing.mp3",
    door_bang:  "assets/audio/door_bang.mp3",
    moan:       "assets/audio/moan.mp3",
    door_close: "assets/audio/door_close.mp3",
    door_open:  "assets/audio/door_open.mp3",
    light_buzz: "assets/audio/light_buzz.mp3",
    power_down: "assets/audio/power_down.mp3",
    alarm:      "assets/audio/alarm.mp3",      // the 6 AM alarm clock (it rings inside the dream, then in your room)
    morning:    "assets/audio/morning.mp3",
    cam_open:   "assets/audio/cam_open.mp3",
    cam_close:  "assets/audio/cam_close.mp3",
    cam_switch: "assets/audio/cam_switch.mp3",
    static:     "assets/audio/static.mp3",
    ui_click:   "assets/audio/ui_click.mp3",
    hour_chime: "assets/audio/hour_chime.mp3",
    // optional:
    clock_tick:    "assets/audio/clock_tick.mp3",     // a wind-up clock ticking (falling asleep, and slowing down when Lucidity runs out)
    type_key:      "assets/audio/type_key.mp3",       // one typewriter key, while the dream voice types
    reality_snap:  "assets/audio/reality_snap.mp3",   // a sharp snap when you pinch yourself
    redhorn_click: "assets/audio/redhorn_click.mp3",  // Redhorn's clicking in the walls
    door_strain:   "assets/audio/door_strain.mp3",    // a door groaning when it's been shut too long
    hypnic_jolt:   "assets/audio/hypnic_jolt.mp3",    // the falling-into-the-dream thump
    water_drip:    "assets/audio/water_drip.mp3",     // drips for the Drowned Parlor camera
  },

  /* SOUND CAPTIONS (Settings -> Sound captions): the words shown for each
     sound, on the side of the screen it came from. They help on phones
     (one speaker can't tell left from right) and players who can't hear.
     {0} is filled in by the game (the time, for the clock). If you add a new
     scary sound for a monster, give it a caption line here too. */
  captions: {
    steps:         "footsteps",
    stepsNear:     "footsteps, close",
    breath:        "breathing",
    breathMuffled: "breathing, muffled",
    breathClose:   "breathing, very close",
    bang:          "BANG",
    far:           "a low moan, far off",
    whisper:       "whispering",
    chime:         "the clock chimes: {0}",
    powerDown:     "everything goes quiet",
    clockSlow:     "the clock is slowing down",
    strain:        "the door groans",
    whisperAbove:  "whispering, right above you",
    ticking:       "the clock ticks louder",
    nearRing:      "a muffled ring… almost",
    alarm:         "the alarm rings!",
  },

  /* ------------------------------------------------------------------
     THE DREAM VOICE — what the voice in your head says at the start
     of each night. Each night's words go between two ` marks.
     It speaks in BEATS: an empty line starts the next beat.
     Keep each beat short: one or two sentences.
     Two tricks you can use anywhere in the words:
       {wrong|right}  the voice types "wrong" in a red, dripping hand,
                      stops, rubs it out and writes "right" instead.
                      Example: It's {behind you|tall}.
       {A}            shows a key to press, like the keys on the buttons
                      (it is left out on phones and tablets).
     ------------------------------------------------------------------ */
  dreamVoice: {
    1: `Hey. Can you hear me? You're asleep. It never feels like it.

        Something walks this dream. It's red. It's {behind you|tall}. It doesn't blink.

        It always breathes at your door first. Light the doorway. If it's there, shut the door.

        Doors are like holding your breath. Don't hold them forever.

        Slipping? Pinch yourself. But it's loud, and it will hear you.

        Make it to six. The alarm always comes. Usually.`,

    2: `You came back. Most people don't remember the first night.

        It remembers you. It's quicker now.

        See the line on your Lucidity? Below it, the dream starts to lie.

        The real one always moves. A fake stands still, glows violet, and breathes backwards.

        When in doubt, use the light. Or pinch yourself: lies hate that.`,

    3: `The halls were longer tonight. {I counted the doors.|Did you notice?}

        It walks quietly now. Don't wait for footsteps. Listen for the breathing.

        If it bangs on the door, good. The door held. Now let it breathe.

        There are six cameras. If you ever find a seventh, don't look twice.`,

    4: `Don't stare at it on the cameras. It likes being watched.

        The doors are tired. Don't make them hold their breath for nothing.

        I can barely hear you anymore. {Someone else can.|You're sinking deeper.}`,

    5: `This is the last night I can reach you.

        The dream knows it's losing you. It will try anything. Even the alarm.

        When the real one rings, don't look back. Just wake up.

        I'll be the one ringing.`,

    endless: "There is no voice here. Only the dream.",
    lie: `Not real.

          The real one always moves. If its breathing runs backwards, the dream is lying.`,  // the first time your light finds a fake
    falseDawn: "Not yet.",  // Night 5: the alarm rings too early... and stops
    /* after: the voice comes back ONE more time, about 20 seconds after it
       went quiet (one line per night; leave a night out for nothing). */
    after: { 5: "Wake up." },
  },

  /* ------------------------------------------------------------------
     THE FIRST-NIGHT LESSON: on Night 1 (the very first time, and from
     Extras -> "Replay the first-night lesson") the voice teaches one
     step at a time and WAITS until the player has done it. The clock
     waits too, and the monster sleeps. A dashed ring shows what to press.
       say:   what the voice says ({A} = a key, like in dreamVoice)
       wait:  what the player has to do before the next step:
              "lookLeft" / "lookRight"   look all the way to that side
              "light"                    turn on a light
              "cams"                     open the cameras
              "cam:west"                 look at that camera (use its id)
              "door" / "doorOpen"        shut a door / open it again
              "pinch"                    pinch yourself
              "time:4"                   just wait 4 seconds
       point: (optional) what the ring goes around: "leftLight",
              "rightLight", "leftDoor", "rightDoor", "cameras", "pinch",
              "lucidity", "clock", "left", "right" or "none".
     After 25 seconds a step moves on by itself, so nobody gets stuck.
     ------------------------------------------------------------------ */
  tutorial: [
    { say: "Look to your left.", wait: "lookLeft" },
    { say: "That doorway. Turn on the light. {A}", wait: "light" },
    { say: "Now the other side.", wait: "lookRight" },
    { say: "Open the cameras. {SPACE}", wait: "cams" },
    { say: "Find the West Hall. It is right outside your left door.", wait: "cam:west" },
    { say: "Close the cameras. Shut a door and watch your Lucidity. {Q}", wait: "door" },
    { say: "Doors are like holding your breath. Open it again.", wait: "doorOpen" },
    { say: "If you're slipping, pinch yourself. But it hears you. {F}", wait: "time:4", point: "pinch" },
    { say: "Make it to six. Listen for breathing at the doors.", wait: "time:4", point: "clock" },
  ],

  /* Credits shown in the Extras screen (see also CREDITS.md) and rolled after Night 5.
     The first line is YOU: change "You!" to your name if you like.
     Lines starting with "Sound:", "Font:" or "Picture:" are rolled together as one list of names. */
  credits: [
    { what: "Monster art & animation (Redhorn)", who: "You!", license: "" },
    { what: "Sound: Night ambience", who: "congusbongus", license: "CC0", url: "https://opengameart.org/content/lost-in-a-bad-place-horror-ambience-loop" },
    { what: "Sound: Title-screen music", who: "Tsorthan Grove (tsorthan-grove)", license: "CC0", url: "https://opengameart.org/content/moonlit-lullaby-for-the-lost" },
    { what: "Sound: Music box", who: "Aureolus_Omicron (aureolusomicron)", license: "CC0", url: "https://opengameart.org/content/4-music-box-tracks" },
    { what: "Sound: Whispers", who: "eugeneloza", license: "CC0", url: "https://opengameart.org/content/voices-of-madness" },
    { what: "Sound: Heartbeat", who: "bart (Bart Kelsey)", license: "CC0", url: "https://opengameart.org/content/heartbeat-sounds" },
    { what: "Sound: Jumpscare scream", who: "Vinrax", license: "CC0", url: "https://opengameart.org/content/horror-scream1" },
    { what: "Sound: Footsteps", who: "mikeask", license: "CC0", url: "https://opengameart.org/content/steps-in-wood-floor" },
    { what: "Sound: Breathing at the door", who: "iletzy", license: "CC0", url: "https://opengameart.org/content/ghostmonster-sounds" },
    { what: "Sound: Banging on the door", who: "Spring Spring", license: "CC0", url: "https://opengameart.org/content/various-sound-effects-0" },
    { what: "Sound: Distant moan", who: "qubodup", license: "CC0", url: "https://opengameart.org/content/ghost-monster-voice-moaning-growling" },
    { what: "Sound: Door closing", who: "sinny", license: "CC0", url: "https://opengameart.org/content/old-elevator-door" },
    { what: "Sound: Door opening", who: "yd", license: "CC0", url: "https://opengameart.org/content/platformer-sounds-terminal-interaction-door-shots-bang-and-footsteps" },
    { what: "Sound: Hallway light buzz", who: "themightyglider", license: "CC0", url: "https://opengameart.org/content/electric-buzz" },
    { what: "Sound: Power down", who: "Cough-E", license: "CC0", url: "https://opengameart.org/content/machine-shutting-down" },
    { what: "Sound: 6 AM alarm clock", who: "rubberduck", license: "CC0", url: "https://opengameart.org/content/30-cc0-sfx-loops" },
    { what: "Sound: Morning birds", who: "isaiah658", license: "CC0", url: "https://opengameart.org/content/ambient-bird-sounds" },
    { what: "Sound: Cameras up", who: "Little Robot Sound Factory", license: "CC-BY 3.0", url: "https://opengameart.org/content/electric-sound-effects-library" },
    { what: "Sound: Cameras down", who: "Little Robot Sound Factory", license: "CC-BY 3.0", url: "https://opengameart.org/content/electric-sound-effects-library" },
    { what: "Sound: Camera switch", who: "Little Robot Sound Factory", license: "CC-BY 3.0", url: "https://opengameart.org/content/electric-sound-effects-library" },
    { what: "Sound: Camera static", who: "bretbernhoft", license: "CC0", url: "https://opengameart.org/content/frequency-static-sound-effects" },
    { what: "Sound: Menu click", who: "Kenney (Kenney Vleugels, www.kenney.nl)", license: "CC0", url: "https://opengameart.org/content/51-ui-sound-effects-buttons-switches-and-clicks" },
    { what: "Sound: Hour bell", who: "Fun Gi Development", license: "CC-BY 3.0", url: "https://opengameart.org/content/tolling-bell-sfx" },
    { what: "Sound: Clock ticking", who: "AntumDeluge", license: "CC0", url: "https://opengameart.org/content/ticking-clock-0" },
    { what: "Sound: Typewriter key", who: "Cassie-OrbitGames", license: "CC0", url: "https://opengameart.org/content/typewriter-sounds" },
    { what: "Sound: Finger snap", who: "Vinrax", license: "CC0", url: "https://opengameart.org/content/snap-of-the-fingers-sounds" },
    { what: "Sound: Redhorn's clicking", who: "spookymodem", license: "CC-BY 3.0", url: "https://opengameart.org/content/spider-chattering" },
    { what: "Sound: Door groaning", who: "bart (Bart Kelsey)", license: "CC-BY 3.0", url: "https://opengameart.org/content/25-spooky-sound-effects" },
    { what: "Sound: Falling into the dream (whoosh)", who: "bosslevelaudio", license: "CC0", url: "https://opengameart.org/content/wierd-whooshes" },
    { what: "Sound: Falling into the dream (thud)", who: "NenadSimic", license: "CC0", url: "https://opengameart.org/content/muffled-distant-explosion" },
    { what: "Sound: Water drips", who: "Independent.nu (submitted by qubodup)", license: "CC0", url: "https://opengameart.org/content/dripping-water-loop" },
    { what: "Fonts: IM Fell English & SC", who: "Igino Marini", license: "OFL 1.1" },
    { what: "Font: Special Elite", who: "Astigmatic", license: "Apache 2.0" },
    { what: "Font: VT323", who: "Peter Hull", license: "OFL 1.1" },
    { what: "Font: Eater", who: "Typomondo", license: "OFL 1.1" },
    /* The free pictures the game's built-in photo rooms are made from (assets/scenes/, see art-src/).
       All are CC0 or public domain: free for anyone to use. When you draw all your own rooms,
       you can delete these lines. */
    { what: "Picture: \"A Moonlit Night at Sea\" (painting, 1885)", who: "Ivan Aivazovsky", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Ivan_Konstantinovich_Aivazovsky_-_A_Moonlit_Night_at_Sea,_1885.jpg" },
    { what: "Picture: \"Island of the Dead\" (painting)", who: "Arnold Böcklin", license: "CC0", url: "https://commons.wikimedia.org/wiki/File:Island_of_the_Dead_MET_DP-14201-003.jpg" },
    { what: "Picture: \"Portrait of a Young Woman\" (painting)", who: "Petrus Christus", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Petrus_Christus_-_Portrait_of_a_Young_Woman_-_Google_Art_Project.jpg" },
    { what: "Picture: \"Moonrise over the Sea\" (painting)", who: "Caspar David Friedrich", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Caspar_David_Friedrich_-_Mondaufgang_%C3%BCber_dem_Meer.jpg" },
    { what: "Picture: \"A Walk at Dusk\" (painting)", who: "Caspar David Friedrich", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Caspar_David_Friedrich_-_A_Walk_at_Dusk.jpg" },
    { what: "Picture: \"Street Scene in Moonlight\" (painting)", who: "John Atkinson Grimshaw", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:John_Atkinson_Grimshaw_-_Street_Scene_in_Moonlight.jpg" },
    { what: "Picture: \"Under the Moonbeams\" (painting)", who: "John Atkinson Grimshaw", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:John_Atkinson_Grimshaw_-_Under_the_Moonbeams.jpg" },
    { what: "Picture: \"Interior. Artificial Light\" (painting)", who: "Vilhelm Hammershøi", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Vilhelm_Hammersh%C3%B8i_-_Interior._Artificial_Light_-_KMS8677_-_Statens_Museum_for_Kunst.jpg" },
    { what: "Picture: \"The Four Rooms\" (painting, 1914)", who: "Vilhelm Hammershøi", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Vilhelm_Hammersh%C3%B8i-_Die_vier_Zimmer,_1914.jpg" },
    { what: "Picture: \"White Doors\" (painting, 1913)", who: "Vilhelm Hammershøi", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Vilhelm_Hammersh%C3%B8i_-_Hvide_d%C3%B8re._Interi%C3%B8r_fra_Strandgade_25_-_1913.png" },
    { what: "Picture: \"Night on the Dnieper\" (painting)", who: "Arkhip Kuindzhi", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Arkhip_Kuindzhi_-_%D0%9D%D0%BE%D1%87%D1%8C_%D0%BD%D0%B0_%D0%94%D0%BD%D0%B5%D0%BF%D1%80%D0%B5_-_Google_Art_Project.jpg" },
    { what: "Picture: \"Portrait of a Young Girl\" (painting, 1840)", who: "H[einrich?] Paul (German, 19th century)", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Heinrich_Paul_Portrait_of_a_young_girl_1840.jpg" },
    { what: "Picture: \"Nocturne, Grey and Silver (Chelsea Embankment, Winter)\" (painting)", who: "James McNeill Whistler", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:James_McNeill_Whistler_-_Nocturne_Grey_and_Silver--Chelsea_Embankment,_Winter_(c._1879).jpg" },
    { what: "Picture: Victorian armchair (3-D scan: the parlor's armchairs and your chair on CAM 7)", who: "Kirill Sannikov", license: "CC0", url: "https://polyhaven.com/a/ArmChair_01" },
    { what: "Picture: Twin-bell alarm clock (3-D scan: the alarm clock)", who: "Yann Kervran, James Ray Cock", license: "CC0", url: "https://polyhaven.com/a/alarm_clock_01" },
    { what: "Picture: Old iron bed frame (3-D scan: the cot in the nursery)", who: "Luca B", license: "CC0", url: "https://polyhaven.com/a/old_bed_frame" },
    { what: "Picture: Painted wooden nightstand (3-D scan: the nursery)", who: "Kirill Sannikov", license: "CC0", url: "https://polyhaven.com/a/painted_wooden_nightstand" },
    { what: "Picture: Grandfather clock (3-D scan: the Endless Hall)", who: "Yann Kervran, James Ray Cock", license: "CC0", url: "https://polyhaven.com/a/vintage_grandfather_clock_01" },
    { what: "Picture: Misty pine forest (outside the windows)", who: "Greg Zaal", license: "CC0", url: "https://polyhaven.com/a/misty_pines" },
    { what: "Picture: Old photo: second-floor center hall, Blandair (beyond the west doorway)", who: "Historic American Buildings Survey (Library of Congress)", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:View_of_second_floor_Center_Hall_(Room_201),_looking_north,_with_scale_stick_-_Blandair,_6651_Highway_175,_Columbia,_Howard_County,_MD_HABS_MD-1149-28.tif" },
    { what: "Picture: Old photo: first-floor hall, Lyndhurst (beyond the east doorway)", who: "Historic American Buildings Survey (Library of Congress)", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:VIEW_FIRST_FLOOR_HALL_FROM_SOUTH_-_Lyndhurst,_Main_House,_635_South_Broadway,_Tarrytown,_Westchester_County,_NY_HABS_NY,60-TARY,1A-37.tif" },
    { what: "Picture: The full moon", who: "NASA/GSFC/Arizona State University", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Full_Moon_(15984763045).jpg" },
    { what: "Picture: The moon picture in your bedroom", who: "NASA/GSFC/Arizona State University", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Moon_nearside_LRO_5000.jpg" },
    { what: "Picture: Old paper (the crayon drawing, letters)", who: "unknown author (The Digital Yard Sale)", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Old_paper6.jpg" },
    { what: "Picture: The carved mantel in the Drowned Parlor (Old Hall)", who: "Sergej Majboroda", license: "CC0", url: "https://polyhaven.com/a/old_hall" },
    { what: "Picture: Night sky (Rogland Clear Night)", who: "Greg Zaal", license: "CC0", url: "https://polyhaven.com/a/rogland_clear_night" },
    { what: "Picture: Rocking horse with yellow halter (ca. 1900, the nursery)", who: "Unknown maker (Smithsonian American Art Museum, gift of Herbert Waide Hemphill, Jr.)", license: "CC0", url: "https://commons.wikimedia.org/wiki/File:Rocking_Horse_with_Yellow_Halter-saam-1986.65.89_1.jpg" },
    { what: "Picture: Wallpaper, sidewall, France 1875-1900 (the desk room)", who: "J. Zuber et Cie (Cooper Hewitt)", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Sidewall_(France),_1875%E2%80%931900_(CH_18798335).jpg" },
    { what: "Picture: \"Daisy\" wallpaper", who: "William Morris / Morris & Co.", license: "CC0", url: "https://commons.wikimedia.org/wiki/File:Daisy_MET_DP306732.jpg" },
    { what: "Picture: \"Fruit or Pomegranate\" wallpaper", who: "William Morris / Morris & Co.", license: "CC0", url: "https://commons.wikimedia.org/wiki/File:Fruit_or_Pomegranate_MET_DP109416.jpg" },
    { what: "Picture: \"St. James\" acanthus wallpaper (the carving on the desk room's picture frame)", who: "William Morris", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Morris_St_James_1880.jpg" },
    { what: "Picture: \"Nursery Rhymes (1876)\" wallpaper", who: "unknown artist (Cooper Hewitt)", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Sidewall,_Nursery_Rhymes,_1876_(CH_18606165).jpg" },
    { what: "Picture: Wallpaper with umbel flowers, butterflies and dragonflies", who: "Rijksmuseum", license: "CC0", url: "https://commons.wikimedia.org/wiki/File:Blad_behangselpapier_met_schermbloemen,_vlinders_en_libellen,_RP-P-1970-1.jpg" },
    { what: "Picture: Book Pattern (col2) (texture)", who: "Rob Tuytel", license: "CC0", url: "https://polyhaven.com/a/book_pattern" },
    { what: "Picture: Brown Leather (texture)", who: "Rob Tuytel", license: "CC0", url: "https://polyhaven.com/a/brown_leather" },
    { what: "Picture: Fabric Pattern 05 (col_02) (texture)", who: "Rob Tuytel", license: "CC0", url: "https://polyhaven.com/a/fabric_pattern_05" },
    { what: "Picture: Wholecloth quilt", who: "The Metropolitan Museum of Art", license: "CC0", url: "https://commons.wikimedia.org/wiki/File:Wholecloth_quilt_MET_DP123109.jpg" },
    { what: "Picture: Wholecloth calamanco quilt", who: "The Metropolitan Museum of Art", license: "CC0", url: "https://commons.wikimedia.org/wiki/File:Wholecloth_calamanco_quilt_MET_DP332843.jpg" },
    { what: "Picture: Velour Velvet (texture)", who: "colormass, Rico Cilliers", license: "CC0", url: "https://polyhaven.com/a/velour_velvet" },
    { what: "Picture: Dark Wooden Planks (texture)", who: "Amal Kumar", license: "CC0", url: "https://polyhaven.com/a/dark_wooden_planks" },
    { what: "Picture: Plank Flooring 04 (texture)", who: "Dimitrios Savva", license: "CC0", url: "https://polyhaven.com/a/plank_flooring_04" },
    { what: "Picture: Herringbone Parquet (texture)", who: "Jenelle van Heerden, Sergej Majboroda", license: "CC0", url: "https://polyhaven.com/a/herringbone_parquet" },
    { what: "Picture: Old Wooden Floor 02 (texture)", who: "Charlotte Baglioni, Jenelle van Heerden", license: "CC0", url: "https://polyhaven.com/a/old_wooden_floor_02" },
    { what: "Picture: Old Wood Floor (texture)", who: "Guillaume Monsergent", license: "CC0", url: "https://polyhaven.com/a/old_wood_floor" },
    { what: "Picture: Distressed Painted Planks (texture)", who: "Rob Tuytel", license: "CC0", url: "https://polyhaven.com/a/distressed_painted_planks" },
    { what: "Picture: Stair Planks (texture)", who: "Rob Tuytel", license: "CC0", url: "https://polyhaven.com/a/stair_planks" },
    { what: "Picture: Brushed brass (Apollo 11 interior paint)", who: "NASA / Smithsonian Institution", license: "CC0", url: "https://commons.wikimedia.org/wiki/File:Brushed_brass_paint_(Apollo_11)_interior.png" },
    { what: "Picture: Rusty Metal 02 (texture)", who: "Rob Tuytel", license: "CC0", url: "https://polyhaven.com/a/rusty_metal_02" },
    { what: "Picture: Wallpaper, sidewall, ca. 1880 (CH 85010069)", who: "unknown designer, ca. 1880 (Cooper Hewitt)", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Sidewall,_ca._1880_(CH_85010069).jpg" },
    { what: "Picture: Wallpaper, sidewall, ca. 1880 (CH 85010039)", who: "unknown designer, ca. 1880 (Cooper Hewitt)", license: "Public domain", url: "https://commons.wikimedia.org/wiki/File:Sidewall,_ca._1880_(CH_85010039).jpg" },
    { what: "Picture: Decrepit Wallpaper (texture)", who: "Rob Tuytel", license: "CC0", url: "https://polyhaven.com/a/decrepit_wallpaper" },
    { what: "Picture: \"Blackthorn\" wallpaper", who: "William Morris / Morris & Co. (The Met)", license: "CC0", url: "https://commons.wikimedia.org/wiki/File:Blackthorn_MET_DP306737.jpg" },
    { what: "Picture: \"Trellis\" wallpaper", who: "William Morris, Philip Webb / Morris & Co. (The Met)", license: "CC0", url: "https://commons.wikimedia.org/wiki/File:Trellis_MET_DP306738.jpg" },
    { what: "Picture: \"Willow Bough\" wallpaper", who: "William Morris / Morris & Co. (The Met)", license: "CC0", url: "https://commons.wikimedia.org/wiki/File:Willow_Bough_MET_DP306734.jpg" },
    { what: "Picture: White Planks Clean (texture)", who: "Rob Tuytel", license: "CC0", url: "https://polyhaven.com/a/white_planks_clean" },
    { what: "Picture: Wooden Panels (texture)", who: "Dimitrios Savva", license: "CC0", url: "https://polyhaven.com/a/wooden_panels" },
    { what: "Picture: Papier7 (Paper-Textures seamless pack) (texture)", who: "Leschge", license: "CC0", url: "https://opengameart.org/content/paper-textures-seamless" },
    { what: "Picture: Grey Plaster 03 (texture)", who: "Rob Tuytel", license: "CC0", url: "https://polyhaven.com/a/grey_plaster_03" },
    { what: "Picture: Worn Plaster Wall (texture)", who: "Dimitrios Savva", license: "CC0", url: "https://polyhaven.com/a/worn_plaster_wall" },
    { what: "Picture: Plastered Wall 04 (texture)", who: "Rob Tuytel", license: "CC0", url: "https://polyhaven.com/a/plastered_wall_04" },
    { what: "Picture: Ceiling Interior (texture)", who: "Dimitrios Savva", license: "CC0", url: "https://polyhaven.com/a/ceiling_interior" },
    { what: "Picture: Worn Mossy Plasterwall (texture)", who: "Amal Kumar", license: "CC0", url: "https://polyhaven.com/a/worn_mossy_plasterwall" },
    { what: "Picture: Plastered Wall 03 (texture)", who: "Rob Tuytel", license: "CC0", url: "https://polyhaven.com/a/plastered_wall_03" },
    { what: "Picture: Rough Plaster Broken (texture)", who: "Rob Tuytel", license: "CC0", url: "https://polyhaven.com/a/rough_plaster_broken" },
    { what: "Picture: 'Lotto' carpet", who: "The Metropolitan Museum of Art", license: "CC0", url: "https://commons.wikimedia.org/wiki/File:%27Lotto%27_Carpet_MET_DP329233.jpg" },
    { what: "Picture: Carpet MET DP169907", who: "The Metropolitan Museum of Art", license: "CC0", url: "https://commons.wikimedia.org/wiki/File:Carpet_MET_DP169907.jpg" },
    { what: "Picture: Carpet MET DP169905", who: "The Metropolitan Museum of Art", license: "CC0", url: "https://commons.wikimedia.org/wiki/File:Carpet_MET_DP169905.jpg" },
    { what: "Picture: 'Star Ushak' carpet", who: "The Metropolitan Museum of Art", license: "CC0", url: "https://commons.wikimedia.org/wiki/File:%27Star_Ushak%27_Carpet_MET_DP169931.jpg" },
    { what: "Picture: Dark Wood (texture)", who: "Dario Barresi, Dimitrios Savva, Rico Cilliers", license: "CC0", url: "https://polyhaven.com/a/dark_wood" },
    { what: "Picture: Fine Grained Wood (texture)", who: "Rob Tuytel", license: "CC0", url: "https://polyhaven.com/a/fine_grained_wood" },
    { what: "Picture: Lacquered Cherry Wood (texture)", who: "Jenelle van Heerden, Rico Cilliers", license: "CC0", url: "https://polyhaven.com/a/lacquered_cherry_wood" },
    { what: "Picture: Green Rough Planks (texture)", who: "Rob Tuytel", license: "CC0", url: "https://polyhaven.com/a/green_rough_planks" },
    { what: "Picture: Wood Table Worn (texture)", who: "Dimitrios Savva, Rico Cilliers", license: "CC0", url: "https://polyhaven.com/a/wood_table_worn" },
  ],
};
