# DEAD AIR — design notes

> **Spoilers.** This document describes the mechanics, the escalation, and the
> shape of the endings. If you would rather play it cold, stop here.

## What's implemented

**Act One: the park.** The game opens at the trailhead at 18:40 with 85
minutes of usable dusk and no cave in sight. Five locations, five people to
talk to, eleven things to examine — and nowhere near enough light to do all
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
arm's length, the room, and beyond. As the cell drains you stop being *told*
what is there. Below 25% the far layer is gone; below 8% you get one sentence
about rock. Dimming the beam doubles your endurance and costs you a layer, so
the meter is a real decision rather than a countdown.

**Resources.** Lamp (burns per minute, two spare cells hidden in the cave),
air (CO₂ pools in the low passage; a fast crossing is survivable, loitering
is not), rope (60 m, spent permanently when you rig a pitch — and you need
20 m in reserve for a route that closes behind you), radio signal (by depth).

**A cave that answers back.** Ambience is keyed to a hidden dread band driven
by depth and by what you have seen. Deep in, `L` stops returning cave noises
and starts returning *your own past actions* — the game logs what you did in
each room and plays it back at you from the wrong direction, hours late.

**Escalation with teeth.** The first half is procedure: rigging, survey tags,
radio checks that work. Things go wrong structurally, not with a jump scare —
the radio degrades, then degrades incorrectly, then is clear at sixty metres
of limestone and saying something impossible. Taking the find starts a
115-minute pursuit clock, and the way you came in is no longer open.

**Seven endings.** Two ways out, five ways not to.

The two you survive resolve against the clock. Act Two starts at 02:14 and a
run is anywhere from twelve minutes (straight back out of the Letterbox) to
most of the night, so nothing about the exit can be written down in advance:
`SKY` and `ARRIVAL` in `state.py` are indexed by `Game._sky_band()`, which
knows roughly where September twilight falls at this latitude. Coming out
after Trammell's 06:00 turnaround adds a line, because you were given a
turnaround time in front of the family and the game should notice you missed
it. A helmet run at best speed is 2h43 and puts you out at 04:57.

**Graphics that carry the mechanic.** Every room has a viewport above the
prose, and it is not decoration. Scenes are described as signed-distance
fields and raymarched at runtime, then lit by your actual lamp — a headlamp
at the eye with a cone, inverse-square falloff, and a reach that scales with
what is left in the cell. Losing the far prose layer and watching the picture
pull in are the same event. Above ground the light is the sky instead, and it
goes out on the same schedule the dusk does.

## Layout

    deadair/content.py   the park, the cave, the prose, the tables — pure data
    deadair/state.py     resources, hazards, dread, endings — pure logic
    deadair/art.py       scene geometry and the renderer — pure rendering
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
- Frames are cached on `(room, light band, sky band, w, h)` — quantised, or
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

A clean run to the bottom and back is about 3 hours of game time and lands
you at the surface around 10–20% lamp.

`Game(seed=N)` makes the ambience deterministic for testing, and `--seed N`
threads one in from the shell — `deadair --seed 7`, or `./play --seed 7`. The
seed is held on the app, so `N` for a new run reseeds identically rather than
drifting. It fixes only the RNG draws; the cave, the prose and the endings
are not procedural.
