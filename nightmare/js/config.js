/* =====================================================================
   GAME CONFIG  —  this is the file YOU edit.
   ---------------------------------------------------------------------
   * Every picture path is relative to the nightmare/ folder.
   * If a picture is missing, the game draws a stand-in so it still runs.
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
     one waiting at a door stops waiting, and the rest move at their next chance.
       amount:      how much Lucidity a pinch gives back.
       cooldown:    seconds before you can pinch again.
       lowBonus:    below 30% Lucidity it gives this many times more (2 = double).
       highPenalty: above 60% it gives only this much of it (0.25 = a quarter). */
  pinch: { amount: 4, cooldown: 45, lowBonus: 2, highPenalty: 0.25 },

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
     doors: where the two doorways are in that picture.
       darkImage  (optional) doorway with the light OFF
       litImage   (optional) doorway with the light ON (empty hallway)
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
     Until you draw it, the game paints a stand-in bedroom.
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
     night 3: the "he walks at night" drawing is on your bedside table,
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
     ------------------------------------------------------------------ */
  /* CAM 7, "YOUR ROOM": once a night (from Night 3, see youCam in nights) a
     camera that isn't on the map appears. It films YOU from behind...
       image: (optional) your desk room seen from behind and above, with an
              EMPTY chair (1600 x 900). Until you draw it, the game makes one.
       seat:  where the back of your head goes in that picture (x, y = the
              middle of your head, size: 1 = normal). */
  youCam: { image: "assets/rooms/cam7_you.png", seat: { x: 0.5, y: 0.5, size: 1 } },

  cameras: [
    { id: "nursery", label: "CAM 1", name: "The Nursery",       image: "assets/rooms/cam1_nursery.png", map: { x: 0.50, y: 0.10 }, sound: "music_box",  soundVol: 0.25 },
    { id: "hall",    label: "CAM 2", name: "The Endless Hall",  image: "assets/rooms/cam2_hall.png",    map: { x: 0.50, y: 0.33 }, sound: "clock_tick", soundVol: 0.3 },
    { id: "parlor",  label: "CAM 3", name: "Drowned Parlor",    image: "assets/rooms/cam3_parlor.png",  map: { x: 0.19, y: 0.53 }, sound: "water_drip", soundVol: 0.35 },
    { id: "stairs",  label: "CAM 4", name: "Stairs to Nowhere", image: "assets/rooms/cam4_stairs.png",  map: { x: 0.81, y: 0.53 } },
    { id: "west",    label: "CAM 5", name: "West Hall",         image: "assets/rooms/cam5_west.png",    map: { x: 0.19, y: 0.76 }, sound: "light_buzz", soundVol: 0.18 },
    { id: "east",    label: "CAM 6", name: "East Hall",         image: "assets/rooms/cam6_east.png",    map: { x: 0.81, y: 0.76 }, sound: "light_buzz", soundVol: 0.18 },
  ],

  /* ------------------------------------------------------------------
     MONSTERS. Copy a whole { ... } block to add a new one.
     frames:  your animation pictures in order (transparent PNGs).
     fps:     animation speed (frames per second).
     levels:  how aggressive it is on nights 1-5 (0 = it sleeps all night, 20 = max).
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
      poses: {
        nursery: { x: 0.62, y: 1.02, h: 0.78 },
        hall:    { x: 0.50, y: 0.92, h: 0.52 },
        parlor:  { x: 0.34, y: 1.04, h: 0.80 },
        stairs:  { x: 0.60, y: 0.96, h: 0.66 },
        west:    { x: 0.55, y: 1.05, h: 0.92 },
        east:    { x: 0.45, y: 1.05, h: 0.92, flip: true },
      },
      doorPose: {   // small enough that both horns fit inside the doorway
        left:  { x: 0.55, y: 1.00, h: 0.70 },
        right: { x: 0.45, y: 1.00, h: 0.70, flip: true },
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
     of each night. Use \n\n for a new paragraph.
     ------------------------------------------------------------------ */
  dreamVoice: {
    1: "Hey. Hey — can you hear me? Good. You're asleep. I know, it doesn't feel like it. That's how this place works.\n\nThis is the Desk Room. Same desk, same walls, every night, until the alarm rings at six.\n\nSomething walks the halls of this dream. It's red. It's tall. It doesn't blink.\n\nWatch it on the cameras. If it comes to your door, shut the door. Use the lights to check — it's always darker out there than it should be. Doors are like holding your breath. Don't hold them forever.\n\nEverything you do costs Lucidity: doors, lights, cameras. If your Lucidity runs out, the dream stops listening to you.\n\nIf you're slipping, pinch yourself. It helps more the deeper you've sunk. But it's loud, and it will hear you.\n\nJust make it to six. The alarm always comes. Usually.",
    2: "You came back. Most people don't remember the first night.\n\nIt remembers you, though. It's quicker now — it's learned the way to your room.\n\nWhen your Lucidity drops below the line, the dream starts to lie. The real one always moves. The fake one stands still, and its breathing runs backwards. When in doubt, use the light.",
    3: "The halls were longer tonight. Did you notice? The dream is building the house out of your memories.\n\nIt walks quietly now. Don't wait for footsteps. Listen for the breathing.\n\nIf you hear it bang on the door, that's good. That means the door held.",
    4: "Don't stare at it on the cameras for too long. I think it likes being watched.\n\nThe doors are tired. Don't make them hold their breath for nothing.\n\nI can barely hear you anymore. You're sinking deeper.",
    5: "This is the last night I can reach you.\n\nWhen the alarm rings, don't hesitate. Don't look back. Just wake up.\n\nI'll be the one ringing.",
    endless: "There is no voice here. Only the dream.",
    lie: "Not real. The real one always moves. If its breathing runs backwards, the dream is lying.",  // the first time your light finds a fake
    falseDawn: "Not yet.",  // Night 5: the alarm rings too early... and stops
  },

  /* Credits shown in the Extras screen (see also CREDITS.md) and rolled after Night 5.
     The first line is YOU: change "You!" to your name if you like. */
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
    { what: "Sound: Water drips", who: "qubodup", license: "CC0", url: "https://opengameart.org/content/dripping-water-loop" },
    { what: "Fonts: IM Fell English & SC", who: "Igino Marini", license: "OFL 1.1" },
    { what: "Font: Special Elite", who: "Astigmatic", license: "Apache 2.0" },
    { what: "Font: VT323", who: "Peter Hull", license: "OFL 1.1" },
    { what: "Font: Eater", who: "Typomondo", license: "OFL 1.1" },
  ],
};
