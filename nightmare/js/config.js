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

  /* Lucidity (your "power"). Higher drain = harder. One number per night. */
  lucidityDrain: [0.09, 0.10, 0.11, 0.12, 0.13],
  /* Extra drain in the Endless Dream (custom night). */
  endlessDrain: 0.13,

  /* PINCH YOURSELF: gives back lucidity but makes noise
     (every monster's next move is a guaranteed step closer). */
  pinch: { amount: 6, cooldown: 30 },

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
  },

  /* ------------------------------------------------------------------
     CAMERAS. One entry per room you can watch.
     image: the room picture (16:9 works best, e.g. 1600 x 900).
     map:   where its button sits on the little camera map (0..1).
     ------------------------------------------------------------------ */
  cameras: [
    { id: "nursery", label: "CAM 1", name: "The Nursery",       image: "assets/rooms/cam1_nursery.png", map: { x: 0.50, y: 0.10 } },
    { id: "hall",    label: "CAM 2", name: "The Endless Hall",  image: "assets/rooms/cam2_hall.png",    map: { x: 0.50, y: 0.33 } },
    { id: "parlor",  label: "CAM 3", name: "Drowned Parlor",    image: "assets/rooms/cam3_parlor.png",  map: { x: 0.19, y: 0.53 } },
    { id: "stairs",  label: "CAM 4", name: "Stairs to Nowhere", image: "assets/rooms/cam4_stairs.png",  map: { x: 0.81, y: 0.53 } },
    { id: "west",    label: "CAM 5", name: "West Hall",         image: "assets/rooms/cam5_west.png",    map: { x: 0.19, y: 0.76 } },
    { id: "east",    label: "CAM 6", name: "East Hall",         image: "assets/rooms/cam6_east.png",    map: { x: 0.81, y: 0.76 } },
  ],

  /* ------------------------------------------------------------------
     MONSTERS. Copy a whole { ... } block to add a new one.
     frames:  your animation pictures in order (transparent PNGs).
     fps:     animation speed (frames per second).
     levels:  how aggressive it is on nights 1-5 (0 = never moves, 20 = max).
     path:    where it can walk next from each room. "door:left" /
              "door:right" means it reaches your door.
     retreat: rooms it runs back to when it finds the door shut.
     poses:   where it stands in each camera picture:
              x = middle of its body, y = where its feet are
              (above 1 = feet below the picture), h = height of the
              monster compared to the picture height. flip: true mirrors it.
     doorPose: same idea, but inside the doorway box of your desk room.
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
      doorPose: {
        left:  { x: 0.55, y: 1.10, h: 1.05 },
        right: { x: 0.45, y: 1.10, h: 1.05, flip: true },
      },
    },
  ],

  /* ------------------------------------------------------------------
     SOUNDS (real recordings downloaded from the internet — see CREDITS.md).
     Swap any file by changing its path.
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
    alarm:      "assets/audio/alarm.mp3",
    morning:    "assets/audio/morning.mp3",
    cam_open:   "assets/audio/cam_open.mp3",
    cam_close:  "assets/audio/cam_close.mp3",
    cam_switch: "assets/audio/cam_switch.mp3",
    static:     "assets/audio/static.mp3",
    ui_click:   "assets/audio/ui_click.mp3",
    hour_chime: "assets/audio/hour_chime.mp3",
  },

  /* ------------------------------------------------------------------
     THE DREAM VOICE — what the voice in your head says at the start
     of each night. Use \n\n for a new paragraph.
     ------------------------------------------------------------------ */
  dreamVoice: {
    1: "Hey. Hey — can you hear me? Good. You're asleep. I know, it doesn't feel like it. That's how this place works.\n\nThis is the Desk Room. Same desk, same walls, every night, until the alarm rings at six.\n\nSomething walks the halls of this dream. It's red. It's tall. It doesn't blink.\n\nWatch it on the cameras. If it comes to your door, shut the door. Use the lights to check — it's always darker out there than it should be.\n\nEverything you do costs Lucidity: doors, lights, cameras. If your Lucidity runs out, the dream stops listening to you.\n\nIf you're slipping, pinch yourself. It helps. But it's loud, and it will hear you.\n\nJust make it to six. The alarm always comes. Usually.",
    2: "You came back. Most people don't remember the first night.\n\nIt remembers you, though. It's quicker now — it's learned the way to your room.\n\nDon't waste the light. Listen for its breathing at the door.",
    3: "The halls were longer tonight. Did you notice? The dream is building the house out of your memories.\n\nIf you hear it bang on the door, that's good. That means the door held.",
    4: "Don't stare at it on the cameras for too long. I think it likes being watched.\n\nI can barely hear you anymore. You're sinking deeper.",
    5: "This is the last night I can reach you.\n\nWhen the alarm rings, don't hesitate. Don't look back. Just wake up.\n\nI'll be the one ringing.",
    endless: "There is no voice here. Only the dream.",
  },

  /* Credits shown in the Extras screen (see also CREDITS.md). */
  credits: [
    { what: "Monster art & animation", who: "You!", license: "" },
  ],
};
