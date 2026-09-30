# DEAD AIR — design notes

> **Spoilers.** This document describes the mechanics, the escalation, and the
> shape of the endings. If you would rather play it cold, stop here.

## What's implemented

**Act One: the park.** The game opens at the trailhead at 18:40 with 85
minutes of usable dusk and no cave in sight. Five locations, five people to
talk to, twelve things to examine — and nowhere near enough light to do all
of it. Talking costs 3 minutes, examining costs 2-4, walking costs 6-9. Close
work (a clue costing 4 minutes) cannot be done below 25% daylight at all, so
the ground you cover early is ground you actually get.

The helmet lamp starts **off** — it is daylight, and switching it on early
tells you nothing. `F` toggles it, and once the day is gone it buys back a
description layer the dusk took away. Underground `F` is refused: the lamp is
why you are alive down there.

This is deliberate teaching. The park runs exactly the mechanic the cave will
later charge you for — a light budget that buys you description — using a
resource you cannot die from spending. By the time the lamp starts draining
you already know what running out of light feels like.

You are cleared to descend once you have Trammell's brief and have spoken to
Wren's mother. Everything else in Act One is optional and none of it changes
a mechanic; it changes what you understand while a mechanic is happening to
you. See PAYOFFS.

**The bridge.** Taking the descent runs the night ground search past you in
three paragraphs, resets the clock, and puts you on the lip of the sink at
02:14, which is where the game used to start.

**Light as a rendering budget.** Every room is written in three layers —
arm's length, the room, and beyond. As the battery drains you stop being *told*
what is there. Below 25% the far layer is gone; below 8% you get one sentence
about rock. Dimming the beam doubles your endurance and costs you a layer, so
the meter is a real decision rather than a countdown.

The plot never lives only in the far layer. A room whose first visit depends
on something out there — the suit at the end of the footprints, Wren across
the nest, the dive line, the orange tape — carries a `found` line, shown on
that first visit only when the beam could not reach it: the thing you walk
up to, told at arm's length.

**Resources.** Lamp (burns per minute, two spare batteries hidden in the cave,
swapped in by themselves if it dies with one in your pocket),
air (CO₂ pools in the low passage; a fast crossing is survivable, loitering
is not), rope (60 m, spent permanently when you rig a pitch — and you need
20 m in reserve for a route that closes behind you), radio signal (by depth).

**A cave that answers back.** Ambience is keyed to a hidden dread band driven
by depth and by what you have seen. Deep in, `L` stops returning cave noises
and starts returning *your own past actions* — the game logs what you did in
each room and plays it back at you from the wrong direction, hours late.
Nothing it gives you comes twice — each line and each echo plays once per
run — and underground one listen in five gets nothing at all, so the longer
you stay down the quieter it gets.

**Escalation with teeth.** The first half is procedure: rigging, survey tags,
radio checks that work. Things go wrong structurally, not with a jump scare —
the radio degrades, then degrades incorrectly, then is clear at sixty meters
of limestone and saying something impossible. Taking the find starts a
115-minute pursuit clock.

**Ten endings.** Five ways out, five ways not to.

Two of the five you survive — `OUT_WITH` and `OUT_ALONE`, the solo exits back
through the Letterbox — resolve against the clock. Act Two starts at 02:14 and
a run is anywhere from twelve minutes (straight back out of the Letterbox) to
most of the night, so nothing about the exit can be written down in advance:
`SKY` and `ARRIVAL` in `state.py` are indexed by `Game._sky_band()`, which
knows roughly where September twilight falls at this latitude. Coming out
after Trammell's 06:00 turnaround — by any of the five ways out — adds a
line, because you were given a
turnaround time in front of the family and the game should notice you missed
it. A helmet run at best speed is 2h43 and puts you out at 04:57.
`OUT_ALONE` also knows how far you got: turn back before the Long Room and
it ends on a room you never reached (`HAUNT`); find Wren alive and leave
her, and it becomes its own three-page ending (`OUT_ALONE_LEFT_HER`).

**The rescue.** The other three survivable exits are the ones where you
bring Wren back. Following the folded suit's line from `deep` leads to `nest`
— Wren alive, held, the creature asleep on the floor between you and her —
and then to `adit`, the choked head of the old workings, where the mountain
leaks a blade of gray dawn light that is nothing to see by and, through the
burning-glass lens from Act One, is fire. `RESCUE_HARD` (no lens, or you
grabbed her and ran — the `bolted` flag) gets you both out into open air,
which is the one thing it will not follow you into, but the thing is
untouched and nobody seals anything — no choice offered, because you never
had the tool to make one. Having the lens and not being `bolted` instead
routes `climb_out` into `choke`, fifteen meters of broken rock at forty
degrees with it closing on you and a hand's width of gray at the top — and
the lens is still in your pocket. Using it there is the player's call, never
done for them: leave it and climb, and it is `RESCUE_HARD` after all, out
clean with the thing entire. Take it out (`point`) and the lens burns it for
the first time and it answers back — a sound that lands behind your eyes,
not your ears, the first onstage hint of the thought-reading it gets built
around in Act Two. That is the second choice: turn immediately
(`RESCUE_INJURED` — out clean and fast, but it gets a piece of you: two
fingers that never close again, and something cold behind the sternum that
turns over every September) or hold the light and watch it
(`RESCUE_CLEAN` — uninjured, but you stay long enough to see its shape and
feel it reach for more than your position, so you carry the worse memory
instead). Both of those gate the sink and fill in the old workings.
All three of `RESCUE_HARD`/`RESCUE_INJURED`/`RESCUE_CLEAN` are keyed to dawn,
not the clock — they come out into the gray, at sunrise, or into full
morning (`DAWN_SKY`) if you took long enough to get there. `climb_out` makes you wait
at the foot of the choke until `DAWN` (05:35), with the beam stopped down,
before the climb is told. The wait can drain the battery but never kill it, and
the pursuit clock does not run through it. A fast run otherwise reaches the
foot of the choke around 04:10, in full dark, under prose that is all gray
light. The nest's third exit, back into the seam alone, drops you back at
`deep`. Taking the helmet closes the way to the nest — you are running by
then, and the thing in it is awake — and opens a way back along the
footprints instead. Up in the gray (`choke`, `point`, `grip`) a dead lamp
is not a death, and neither is one that runs out on the last crawl out of
the Letterbox — the work lights at the sink beat it (`Game.lit_without_lamp`);
a lamp that dies anywhere after the nest ends in a `DARK` that knows
Wren was with you.

The Letterbox is the one crawl you cannot turn around in, so its exits
depend on which end you came in by (`Exit.came_from`): from the sink you
push on or reverse out; from the Bell you crawl out head-first or reverse
back.

**Graphics that carry the mechanic.** Every room has a viewport above the
prose, and it is not decoration. Scenes are described as signed-distance
fields and raymarched at runtime, then lit by your actual lamp — a headlamp
at the eye with a cone, inverse-square falloff, and a reach that scales with
what is left in the battery. Losing the far prose layer and watching the picture
pull in are the same event. Above ground the light is the sky instead, and it
goes out on the same schedule the dusk does.

## Layout

    deadair/content.py   the park, the cave, the prose, the tables — pure data
    deadair/state.py     resources, hazards, dread, endings — pure logic
    deadair/art.py       scene geometry and the renderer — pure rendering
    deadair/save.py      the one save slot, in this platform's state dir
    deadair/app.py       Textual widgets, meters, viewport, the survey map

Content is fully separated from mechanics, so writing is edited without
touching the engine. A new room is a `Room(...)` in `ROOMS` plus an `Exit`
pointing at it; give it `mx`/`my` grid coordinates and it appears on the
survey map automatically, and a `Scene(...)` in `art.SCENES` under the same
id and it draws itself. A room with no scene falls back to a generic passage
rather than failing.

Act One rooms carry `people` (a `Person` with `beats` consumed one per ask)
and `clues` (a `Clue` costing minutes and granting a flag), and are tagged
`park` so they stay off the survey map and out of the passage count.
`Game.choices()` returns people, then clues, then exits as one numbered list;
in Act Two the first two are empty and it collapses to the exits, which is
what it always was.

## The menu and the save slot

`deadair` opens on a menu, not in a cave: RESUME (when there is a run to
resume), NEW RUN, CONTROLS, QUIT. `ESC` reopens it mid-run. Nothing starts
until the player picks something — `App._started` is what the rest of the
code checks before it believes `App.game` is a real run.

`Game.snapshot()` returns the whole run as JSON-able data and
`Game.restore()` builds one back, returning `None` for anything it cannot
read — a save that names a room the cave no longer has is rejected rather
than half-loaded. The rng state travels with it, so reloading is not a way
to make the cave pick a different one of your own footsteps to play back at
you. `save.VERSION` retires the format outright when the fields change.

`save.state_root()` picks the directory: `%LOCALAPPDATA%` on Windows,
`~/Library/Application Support` on macOS, `~/.local/state` otherwise, and
whatever `XDG_STATE_HOME` says wherever it is set, on any of them.

`App.autosave()` runs after every action, because nothing that kills you
down there announces itself first, and the file is written to a temporary
name and renamed over the old one so a crash mid-write cannot eat the run.
An ending clears the slot: a finished run is a story, not a save.


## The renderer

`art.py` draws every room from a `Scene`: a kind of place and the numbers
that shape it — passage radii, bedding relief, chamber extents, tree and
canopy counts, fog, lamp reach, palette, camera tilt — plus, for the rooms
the prose furnishes, what is in them. The kinds: `forest` above ground;
`crawl` and `drop` for the Letterbox and the Drop; `dome`, `hall`, `rift`,
`mine`, `jumble` and `under` for the furnished cave rooms; `void` for the
dark. The plain `tube`, `chamber` and `hole` are no longer used by any room;
a room with no Scene of its own falls back to a `tube`.

Notes for anyone changing it:

- The SDF is displaced by noise, which breaks the Lipschitz bound, so the
  march steps at 0.62 of the reported distance underground. Above ground the
  dominant surface is an exact plane and it strides at 0.92 in fewer steps —
  worth about a second a frame.
- The march runs on a one-octave SDF and the normals are taken with two. All
  the visible texture comes from the normals; the march only needs to know
  roughly where the rock is.
- Chambers are smooth-minimum boxes. A hard corner reads instantly as
  architecture rather than cave.
- A forest is a planted stand, not a handful of props. `_Stand` puts a few
  hundred trees on a jittered lattice across the wedge you can see — trunks,
  a cone crown each (hemlock tall and narrow, oak squat, saplings low), and
  rhododendron brush walling the path — and bins them into 2 m ground cells.
  A point measures only what its cell lists, grouped by how full the cell
  is, so the cost barely depends on how many trees there are. `trees` on a
  forest Scene is the stem count; `understory`, `canopy` and `broadleaf` set
  the brush, the height of the lowest branches, and the oak share.
- Every forest ray is grounded. One that skims the hillside and runs out of
  steps is put down on the slope analytically (`_ground_t`); a contact
  shadow seats each trunk in the ground; and each hit is shaded by what it
  is — pale path dirt under a slot of sky, bark, dark needles and leaf —
  with the brightness carried by the haze in the distance.
- Wolf Sink is the one surface place that is built as well as grown. Basecamp
  and the sink are forest scenes over one shared layout — the hole, the
  camp's clearing, two vehicles, the generator, the table, the people, a
  string of bulbs and floods on stands — seen from the flagging at dusk and
  from the lip at two in the morning. The camp's gear is binned into the
  same ground cells as the trees. Its lamps light with shadows cast by
  anything standing (people, vehicles, trunks, you) and scatter into the
  air around them; a lamp reaches into the sink only through its mouth.
- Sander's Hollow's homestead gets pictures of its own. A `Clue` may name a
  `scene`; examining it switches the view to that (`Game.view`), and the
  next thing you do switches it back. The app draws them ahead while you
  stand in the room. The chimney fall is seen from inside the house that
  was: the firebox, a dressed lintel with 1889 cut in it and 1911 scratched
  under, the stack heaped beside it, the foundation under the leaves. The
  springhouse is its tumbled walls, the run out of it as a dark wet line,
  and the mortared course where it goes back into the ground. The cemetery
  is the thirteenth stone in front of you, HERE and 1911 on its face, and
  the twelve twenty feet up the rise with their backs to you. They are
  forest scenes carrying `props` (the cave rooms' primitives), in a
  `clearing` the woods keep off and open the canopy over. The stone is
  lichen-gray (`_M_FIELD`) and its laid joints are paint (`stones`, dark
  where dry-laid, pale where mortared). `exposure` is eyes that have opened
  up to the dark; the hollow itself stays as dim as it always was.
- Two cave rooms are drawn as the prose frames them rather than as generic
  passages. The Letterbox (`crawl`) is a bedding-plane crawl: two beds of
  limestone a head's height apart, pinching shut to the sides, the pack
  pushed ahead, a cave cricket on the silt, and the drag marks and the small
  handprint running off into the dark. The Drop (`drop`) is the view with
  your head over the edge: the throat through the gallery floor, the
  flake and the thread on the lip, the free hang to a floor of broken plate
  twelve metres down. Both shade by material, and in both the helmet beam
  is centred where your head points.
- No two cave rooms are the same picture. Each is one of the shapes above —
  a dome (Bell, Roost, Wren's Cache, the Nest), a hall (Dry Gallery, Foot of
  the Drop, the Keyhole, the Sallow, the Long Room, the Deep), a rift
  (Stream, Carbide Ladder), a mine drift (the Old Workings), a jumble of fallen
  blocks (Breakdown, Sump, Choke, Grip), or flooded (Under) — dressed with
  what its prose puts in it. `props` are clusters of rotated boxes,
  capsules and broken rock (a cairn, a pack against its fallen block, the
  rope, rungs, timber sets, her suit and helmet, Wren herself); `marks` are paint on the rock (soot,
  lamp-black lettering, footprints, crickets, a flood line); `ground` is the
  floor (cobble, broken plate, rubble, guano, silt, dust, bone). A few rooms carry
  more: `glow` for a light of their own (her helmet lamp, the gray at the
  top of the workings), `murk` for bad air pooled on the floor, `clear` for
  water the beam goes down into, `absorb` for the thing the beam goes into
  and does not come out of. The builders for all of it sit just above
  `SCENES` and are data, not code: change a number, not a function.
- The Breakdown is a real collapse, not a room of boxes. Limestone breaks
  along its beds and joints, so each rock (`_Rock`) is a convex solid cut
  by planes: two near-parallel bedding faces, five to eight joint faces
  never square to one another or quite upright, and corners knocked off.
  The broken face is a creased fracture with a slight bend across it,
  added only when the normals are taken. `_pile` drops them in order —
  car-sized slabs tilted and half sunk in `rubble`, blocks landing on
  whatever is under them, spall heaped round the feet and down the line
  you walk — and keeps a way through the first few metres. The roof they
  came out of (`scar`) is flat broken bedding, faceted and stepped, not
  the lumps the other rooms' rock has.
- The Choke and the Grip are the same fill seen twice: the forty tons the
  miners brought down behind them in 1911, fifteen metres of it at forty
  degrees. It is a `_pile` on a `slope` — floor and roof climb with it,
  and every rock lies tilted with the hill — scaled down to the passage
  (`size`), kept clear of both viewpoints and of the lens (`eyes`), with
  a way up the middle the whole length. In a passage that narrow a rock
  dropped anywhere across it nearly always blocks the way, so `sides`
  drops each slab and block to one side of the way or the other, its far
  side going into the wall: the choke's walls are its own blocks. The
  floor is `scree` — the heap under loose angular chips of every size
  (`_chips`), not a tiling. The Choke looks up it from the foot at the
  hand's width of gray at the top; the Grip is six metres up, turning.
- A pile costs something to work out (the Choke's tries ~400 rocks to
  keep ~100), so it is built the first time its room is drawn (`_Later`),
  on the worker thread that draws the rooms ahead, not at import — where
  the two piles were a second's pause before the title.
- The Bell is drawn to be read in one look: you have climbed down out of
  the Letterbox and turned round, so all three ways the prose offers are in
  frame. A way's shape follows what made it: `ways` entries are (bearing,
  width, height, sill, shape, skew), and one much wider than tall is a
  bedding-plane slot (flat, thinning to the sides), one much taller than
  wide a canyon (near-parallel walls, wider at the stream), anything else
  the old round tube unless `shape` names one (see the Cache). `sill` lifts a way up the wall (the Letterbox is knee-high) or,
  negative, sinks it into the floor, which cuts it off — an arch or a
  canyon standing on the floor instead of an oval hole in the wall. `bell`
  draws a dome's walls in above head height. The cobble floor is loose
  rounded stones of mixed sizes lying in sand (`_cobbles`), and the
  crickets (`specks`) crowd in patches rather than rows.
- The Foot of the Drop is the first room bigger than the lamp. Off the
  rope, you look out at the chamber forking round a buttress of jointed
  rock (`_buttress`, a tall `_Rock`) and running off both ways into the
  dark — two big `ways` sunk into the floor. The rope hangs in front of the
  buttress onto shattered plate (`plate`: slabs a pace or two across, each
  at its own tilt, the cracks open), its tail coiled where it landed, and
  the block beside it carries your tag at knee height (`_marked_block`
  puts the tag on whichever face you can see). The rope is lit evenly: a
  strand two pixels wide shaded as a solid was all dark edge.
- The Stream Passage stands you in the water looking downstream, tilted
  down so the stream is in frame even fullscreen. `ledges` draws the beds
  the water cut down through: each parting a dark groove running the
  length of the wall, some faint, some deep, wavering a little — the lines
  that make a canyon read as going away from you. `flow` makes the water
  run: ripples on it (`_ripple`), so the walls come back broken and the
  lamp is gathered into a wavering net of bright lines on the cobble bed
  under a hand's depth of `clear` water. The flood line is a tide mark
  with a wandering top and a dark rim of dried scum. Only the water is
  shaded as water now (by material, not by height), so something sitting
  on it — the salamander, the rock at the waterline, the Sump's dive line
  going in — keeps its own shading. The salamander is really there, side
  on in the shallows, but at the game's render size it is a few pixels.
- The Keyhole is the far wall of the cache and the slot in it, seen from a
  step to one side. The slot is a `ways` entry with the shape `"keyhole"`:
  an out-of-round tube shoulder-wide at the top over a hip-wide slot that
  wanders a little, snaking once it is half a metre into the rock so the
  light never finds the far end. From the side you see one inner wall of
  it going back, which is what makes it a passage and not a black shape.
  The face carries faint bed partings (`ledges`, weaker ledges paint
  fainter), a `joint` mark — the crack the slot opened along, running on
  up the rock above it — and `scuff` marks, rubbed pale on both lips at
  hip height.
- Wren's Cache is seen down on one knee by her pack, so a 40-litre pack
  is whole and in the middle of the frame even at 6:1, with the tighter
  room lens (`lens`). The pack is built as one (`_cache`): body,
  stuffed lid over the front, front and side pockets, lid and compression
  straps, the shoulder straps against the rock, the hip belt undone with
  its webbing lying on the floor — leaning at the angle of the face it is
  set against, found on a fallen `_Rock` block, not a box. `_strew`
  scatters spall across the floor, bigger toward the walls, and the silt
  banks up the walls (`fill`) instead of meeting them in a crease. The
  ways out are not holes drilled in a wall: the Sallow's is `"bedding"` —
  the floor running on in under the flat underside of a bed, dipping,
  stepped where a slab came away, pinching out at the sides — and it
  turns back across your line of sight past the mouth, so the beam finds
  a far wall instead of a black oval. The slot is the Keyhole's
  own shape, `skew`ed so it runs into the rock at an angle, and `gloom`
  darkens rock by degrees going into any way, which is what makes an
  oblique opening read as an opening rather than an outline.
- The palettes are luminance ramps, and a very few materials keep their own
  colour through them (`_TINT` in `art.py`) — the ones the story names by
  it: Wren's orange flagging, her red pack, the blue dive line, the gray at
  the top of the workings. The Sallow and Under have palettes of their own.
- Frames are cached on `(room, light band, sky band, w, h)` — quantized, or
  the cache would never hit — rendered on a worker thread, and the rooms
  reachable from where you are standing are drawn before you walk into them.
  Forests and furnished rooms render at a reduced pixel budget and upscale;
  a frame costs between a third of a second and about four (the Choke).
- The picture only reaches the terminal as graphics if textual-image is
  asked what the terminal can do before Textual starts (`probe_graphics()`
  in `app.py`); asked afterwards, Textual's input thread eats the answer
  and every terminal gets half-blocks.

## Tuning

Constants at the top of `state.py`: `LAMP_BURN_HIGH`, `LAMP_BURN_LOW`,
`AIR_DRAIN`, `ROPE_TOTAL`, `PURSUIT_LIMIT`, `BYPASS_ROPE`, and for Act One
`DAYLIGHT_TOTAL`, `PARK_START`, `CLOSE_WORK`.

Act One is tuned so that a thorough player sees roughly two thirds of it.
Raising `DAYLIGHT_TOTAL` past about 110 lets you exhaust the park, which
costs the act its only source of pressure.

A best-speed run to the bottom and back is 2h43 of game time and comes out
at about 27% lamp on the first battery with the beam wide the whole way; every
look, listen, and radio call comes out of that.

`Game(seed=N)` makes the ambience deterministic for testing, and `--seed N`
threads one in from the shell — `deadair --seed 7`, or `./play --seed 7`. The
seed is held on the app, so `N` for a new run reseeds identically rather than
drifting. It fixes only the RNG draws; the cave, the prose and the endings
are not procedural.
