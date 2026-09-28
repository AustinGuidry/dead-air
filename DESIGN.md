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
degrees, where the lens burns it for the first time and it answers back — a
sound that lands behind your eyes, not your ears, the first onstage hint of
the thought-reading it gets built around in Act Two. That room is the actual
choice: turn immediately (`RESCUE_INJURED` — out clean and fast, but it gets
a piece of you: two fingers that never close again, and something cold
behind the sternum that turns over every September) or hold the light and
watch it (`RESCUE_CLEAN` — uninjured, but you stay long enough to see its
shape and feel it reach for more than your position, so you carry the worse
memory instead). Both of those gate the sink and fill in the old workings.
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
footprints instead. Up in the gray (`choke`, `grip`) a dead lamp is not a
death, and neither is one that runs out on the last crawl out of the
Letterbox — the work lights at the sink beat it (`Game.lit_without_lamp`);
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

`art.py` has five scene kinds — `tube`, `chamber`, `hole`, `forest`, `void` —
and one shading pipeline. A `Scene` is about twenty numbers: passage radii,
bedding relief, chamber extents, tree and canopy counts, fog, lamp reach,
palette, camera tilt.

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
- Frames are cached on `(room, light band, sky band, w, h)` — quantized, or
  the cache would never hit — rendered on a worker thread, and the rooms
  reachable from where you are standing are drawn before you walk into them.
  A forest frame costs about two seconds, a cave frame well under one.

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
