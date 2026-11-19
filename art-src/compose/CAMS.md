# The six camera rooms

Built-in stand-ins for the security-camera pictures (`nightmare/assets/scenes/cam1_nursery.jpg` ...
`cam6_east.jpg`, 1824 x 1026 = W x CAM_ZOOM by H x CAM_ZOOM). They are shown while the creator's own
`assets/rooms/camN_*.png` is missing. Rebuild:

    python3 art-src/compose/build_all.py cam1_nursery cam2_hall cam3_parlor cam4_stairs cam5_west cam6_east
    python3 art-src/compose/poses_suggest.py        # -> poses_suggest.json (stand spots for the monster)

Every room is a small 3-D set in metres, built with the same toolkit and finished with the same
`grade.finish(..., 'cam')` as the office, so all of them belong to the same house and the same camera
system (no scanlines, REC text or static are baked in: the game draws its own camera overlay).

## camkit.py (shared by the six)

* `ZScene`: `Scene` + a depth buffer (fog, the parlor's water, debug overlays). Planes seen exactly
  edge-on are skipped.
* `Plane` + `draw_plane`: floors, ceilings, side walls and back walls are painted by functions of
  WORLD coordinates and drawn in depth segments (ratio 1.42). Each segment is painted at the
  resolution its near end needs and then LANCZOS-resampled to what each texture axis needs, so a 70 m
  hall has neither moire at grazing angles nor blurry close-ups, and the content is continuous across
  segments (world-anchored tiling and world noise).
* `Board`: the office's wall board with slices clamped on both ends.
* painters: world-anchored wallpaper with roll seams, damp-stain photo, tide marks, grime and streaks
  (`paper_band`), plaster, raised wainscot from the real panel texture (`wainscot_row`, `dado_w`),
  mouldings, floor boards (`PLANKS` knows which way each floor photo's planks run), carpet runners,
  plaster ceilings, four-panel doors (`victorian_door`) with fluted casings and bullseye blocks.
* lights: `PortalLight` (a lamp in the room behind a door: lights the near side only through the gap),
  `XApertureLight` (moonlight through a window in a side wall, with glazing-bar shadows and occluders),
  sconces (`sconce`, `sconce_front`, `sconce_light`), a bare bulb, `volumetric()` (dust lit by a light,
  integrated along every camera ray up to the depth buffer), `halo()`.
* `night_sky()`: Poly Haven Milky Way, the NASA moon, misty pines (same recipe as the office window).
* `finish_cam()`: a gentle edge darkening (the feed pans) + `finish(lin, 'cam')`.
* `pose_for(cam, X, Z, height=1.9, ground=0)`: the game's `{x, y, h}` for a figure standing at (X, Z).

## The rooms

| camera | look | key light | warm accent |
|---|---|---|---|
| CAM 1 Nursery | Morris Daisy over painted beadboard, Walter Crane 1876 Nursery Rhymes frieze, crib, mobile of paper moons and brass stars, dappled rocking horse, letter blocks, Lotto carpet | the moon in the window (panes on the floor) | oil lamp on the chest |
| CAM 2 Endless Hall | 70 m hall, 1880 black-and-gold paper over raised wainscot, pale four-panel doors every 4.5 m, Star Ushak runner, tall-case clock, paintings | 26 sconces receding into violet fog | the sconces, light under one door |
| CAM 3 Drowned Parlor | carved overmantel cut from a real photo, Morris Pomegranate stained by the flood, velvet armchairs to their cushions in black water, chandelier, portraits | moonlight across the room onto the mantel wall | one candle still burning on the mantel (and its streak in the water) |
| CAM 4 Stairs to Nowhere | seen through a cased opening: white risers, crimson runner on brass rods, balusters, Morris Blackthorn, raking dado; 16 steps to a landing and a blank wall with the ghost of a door | moon through the arched stair window, a cold skylight | sconces either side of the opening, the newel lamp |
| CAM 5 West Hall | Morris Willow Bough over dark wainscot, Aivazovsky / Hammershoi / an oval portrait, Spanish carpet runner, side doors | a bare bulb on its flex | your desk-room door at the end stands open a hand's width: the lamp's light spills through it as a wedge across the floor |
| CAM 6 East Hall | tall raised panelling, decrepit paper, herringbone parquet, six-over-six sash window with velvet curtains, oak bench, Kuindzhi and an oval portrait | moonlight through the window, panes across the floor | a sconce by the far door; the desk-room door at the end is ajar onto the warm lamp light |

The far doors of the West and East halls are YOUR doors: the warm light behind them is the desk lamp.

## Water (CAM 3)

The parlor is rendered twice: once normally, once mirrored in the water plane (`MirrorScene`: every
quad's Y is reflected about Y = 0.40 and clipped to what is above the water; lights are mirrored too).
`composite_water()` then puts water wherever the plane is nearer than the depth buffer: Fresnel mix of
the reflection (displaced by the slope of a slow swell and two spreading drip rings) and the murky
underwater view, glints toward the window, and a faint meniscus where things stand in the water.
