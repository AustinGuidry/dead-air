# DEAD AIR

A first-person cave-horror game for the terminal. You are a search-and-rescue
officer entering an unsurveyed sink in Piney Ridge National Park, nineteen
hours behind a solo caver who did not come out.

Built with [Textual](https://textual.textualize.io/). Runs in kitty.

## Play

    ./play

Or: `.venv/bin/python -m deadair`

## Controls

| key   | action |
|-------|--------|
| `1`–`5` | take the numbered way on |
| `L`   | listen |
| `R`   | radio basecamp |
| `X`   | look again |
| `D`   | stop the beam down — half the burn rate, half the sight |
| `C`   | swap in a spare cell |
| `N`   | new run |
| `Q`   | quit |

## What's implemented

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

## Layout

    deadair/content.py   the cave, the prose, the flavour tables — pure data
    deadair/state.py     resources, hazards, dread, endings — pure logic
    deadair/app.py       Textual widgets, meters, the survey map

Content is fully separated from mechanics, so writing is edited without
touching the engine. A new room is a `Room(...)` in `ROOMS` plus an `Exit`
pointing at it; give it `mx`/`my` grid coordinates and it appears on the
survey map automatically.

## Tuning

Constants at the top of `state.py`: `LAMP_BURN_HIGH`, `LAMP_BURN_LOW`,
`AIR_DRAIN`, `ROPE_TOTAL`, `PURSUIT_LIMIT`, `BYPASS_ROPE`.

A clean run to the bottom and back is about 3 hours of game time and lands
you at the surface around 10–20% lamp. `Game(seed=N)` makes ambience
deterministic for testing.

## Setup

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
