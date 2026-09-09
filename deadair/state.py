"""
DEAD AIR — engine.

Pure logic. Returns a list of (style, text) events for the UI to render;
knows nothing about Textual.

Styles: narr | sound | radio | sys | alarm | good | title
"""

import random

from .content import (ROOMS, AMBIENCE, ECHO_FRAME, ECHO_ACTS, RADIO,
                      PARK_AMBIENCE, PAYOFFS)

# --- tuning ----------------------------------------------------------------
LAMP_BURN_HIGH = 0.45      # % per minute, beam wide
LAMP_BURN_LOW = 0.22       # % per minute, beam stopped down
AIR_DRAIN = 5.5            # % per minute in a bad-air pocket
AIR_RECOVER = 4.0          # % per minute in clean air
ROPE_TOTAL = 60            # metres carried
PURSUIT_LIMIT = 115        # minutes you have, once you take the helmet
BYPASS_ROPE = 20           # metres to rig past the collapse
DAYLIGHT_TOTAL = 85        # minutes of usable dusk in Act One
PARK_START = 18 * 60 + 40  # 18:40, when you get out of the truck
DESCENT_START = 2 * 60 + 14   # 02:14, when you put your legs into the cold
TURNAROUND = 6 * 60           # 06:00, when Trammell calls Blakely
CLOSE_WORK = 4             # a clue this slow is close work, and
                           # close work needs real light


class Game:
    def __init__(self, seed=None):
        self.seed = seed           # kept so a new run can repeat this one
        self.rng = random.Random(seed)
        self.phase = "park"        # "park" (Act One) | "cave" (Act Two)
        self.park_minutes = 0
        self.said = {}             # person name -> beats already given
        self.here = "trailhead"
        self.lamp = 100.0
        self.lamp_on = False       # Act One starts in daylight; you switch it
        self.dim = False            # on yourself, or the dark does it for you
        self.air = 100.0
        self.rope = ROPE_TOTAL
        self.cells = 0
        self.minutes = 0
        self.visited = set()
        self.flags = set()
        self.ending = None
        self.pursuit = None        # minutes elapsed since taking the helmet
        self.trail = []            # rooms you have actually stood in
        self._last_sound = None    # so the cave does not repeat itself

    # -- derived ------------------------------------------------------------

    @property
    def room(self):
        return ROOMS[self.here]

    @property
    def depth(self):
        return self.room.depth

    @property
    def reach(self):
        """Effective beam reach, 0-100. Dimming saves cell but costs sight."""
        return self.lamp * (0.5 if self.dim else 1.0)

    @property
    def daylight(self):
        """Act One's version of the lamp: 100 down to 0, and then dusk."""
        left = DAYLIGHT_TOTAL - self.park_minutes
        return max(0.0, min(100.0, left / DAYLIGHT_TOTAL * 100.0))

    @property
    def layers(self):
        if self.phase == "park":
            d = self.daylight
            if d >= 55: return 3
            if d >= 25: return 2
            # past that the hillside is only as big as your lamp makes it
            return 2 if self.lamp_on else 1
        r = self.reach
        if r >= 55: return 3
        if r >= 25: return 2
        if r >= 8:  return 1
        return 0

    @property
    def dread(self):
        d = 0
        if self.depth <= -25 or "roost" in self.visited: d = 1
        if self.depth <= -45 or "deep" in self.visited: d = 2
        if self.pursuit is not None: d = 2
        return d

    @property
    def signal(self):
        if "surface" in self.room.tags: return "clear"
        if "signal" in self.room.tags and self.depth > -18: return "clear"
        if self.depth > -30: return "weak"
        return "gone"

    def clock(self):
        return f"{self.minutes // 60:02d}:{self.minutes % 60:02d}"

    def surface_clock(self):
        """The time of day at the surface. Act Two starts at 02:14 and the
        run can be anything from twelve minutes to most of the night, so
        nothing about the exit can be written down in advance."""
        m = (DESCENT_START + self.minutes) % (24 * 60)
        return f"{m // 60:02d}:{m % 60:02d}"

    def _sky_band(self):
        """September, this latitude: astronomical twilight around 05:00,
        nautical around 05:35, civil around 06:10, sun a little after."""
        m = DESCENT_START + self.minutes
        if m < 4 * 60 + 50: return 0
        if m < 5 * 60 + 35: return 1
        if m < 6 * 60 + 15: return 2
        return 3

    def overdue_by(self):
        """Minutes past the turnaround you gave the family a promise about."""
        return max(0, DESCENT_START + self.minutes - TURNAROUND)

    def wall_clock(self):
        """Act One runs on the actual time of day, because the sun does."""
        m = (PARK_START + self.park_minutes) % (24 * 60)
        return f"{m // 60:02d}:{m % 60:02d}"

    # -- time & attrition ---------------------------------------------------

    def _burn(self, mins, air_bad=None):
        """Advance the clock. Returns events for anything that went wrong.

        air_bad=None means 'judge by the room I am standing in'. A move passes
        it explicitly, because you breathe the passage for the whole crossing,
        not just wherever you happen to come out.
        """
        ev = []
        if self.phase == "park":
            # Above ground nothing is draining except the sun, which is not
            # negotiable and does not care what you still had to do.
            before = self.layers
            self.park_minutes += mins
            if self.layers < before:
                ev.append(("alarm", {
                    2: "The light goes flat and shadowless, all at once, "
                       "the way it does. You have maybe half an hour of "
                       "usable evening and then you have a headlamp.",
                    1: "That is the day gone. You are standing on a dark "
                       "hillside with an unlit lamp on your helmet and "
                       "nothing to read the ground by.  [F]"
                }[self.layers]))
            return ev

        if air_bad is None:
            air_bad = "badair" in self.room.tags
        rate = LAMP_BURN_LOW if self.dim else LAMP_BURN_HIGH

        before_layers = self.layers
        self.minutes += mins
        self.lamp = max(0.0, self.lamp - rate * mins)

        if air_bad:
            self.air = max(0.0, self.air - AIR_DRAIN * mins)
        else:
            self.air = min(100.0, self.air + AIR_RECOVER * mins)

        if self.pursuit is not None:
            self.pursuit += mins

        if self.layers < before_layers:
            ev.append(("alarm", {
                2: "The beam pulls in. You are seeing less of the room than "
                   "you were, and the room has not changed.",
                1: "The lamp drops to a working glow. You can see your "
                   "hands, the rock in front of them, and nothing else.",
                0: "The filament goes. Not off — down, to an ember, to a "
                   "colour. You are functionally blind at sixty metres."
            }[self.layers]))

        ev += self._check_death()
        ev += self._check_pursuit()
        return ev

    def _check_death(self):
        if self.ending: return []
        if self.air <= 0:
            self.ending = "AIR"
            return [("alarm",
                "Your legs stop taking instructions first. You get one hand "
                "onto a rock and the rock is the last thing you are sure "
                "about. Carbon dioxide is a kind way to go and that is the "
                "only kind thing about it.")]
        if self.lamp <= 0:
            self.ending = "DARK"
            return [("alarm",
                "The lamp dies. Not dramatically. It just stops, and the "
                "dark that replaces it is not the dark you have been in all "
                "night — it is complete, and it has weight, and it presses "
                "on the front of your eyes.\n\nYou sit down with your back "
                "to rock, because that is the protocol: stay put, conserve, "
                "wait for the team.\n\nAfter a while, something sits down "
                "beside you.")]
        return []

    def _check_pursuit(self):
        if self.ending or self.pursuit is None: return []
        if self.pursuit >= PURSUIT_LIMIT:
            self.ending = "TAKEN"
            return [("alarm",
                "It stops being behind you.\n\nThere is no impact, no "
                "sound, no moment you could point to in a report. Simply: "
                "the passage ahead of you is the passage behind you, and "
                "you are walking, calmly, in the dark, with your lamp "
                "switched off, and you do not remember switching it off, "
                "and you are not going toward the surface.")]
        left = PURSUIT_LIMIT - self.pursuit
        if left <= 20 and "warn3" not in self.flags:
            self.flags.add("warn3")
            return [("alarm", "It is close enough now that you can hear it "
                              "choosing where to put its feet.")]
        if left <= 50 and "warn2" not in self.flags:
            self.flags.add("warn2")
            return [("alarm", "Whatever is following you has stopped "
                              "bothering to sound like a person walking.")]
        return []

    # -- description --------------------------------------------------------

    def describe(self, full=False):
        r = self.room
        ev = []
        if full:
            # depth is meaningless while you are still standing on the grass
            head = r.name if self.phase == "park" else f"{r.name}   ·   {r.depth} m"
            ev.append(("title", head))
        n = self.layers
        if n == 0:
            ev.append(("narr", "You put your hand out and find rock. That is "
                               "the whole of what you know about this place."))
            return ev
        for i in range(min(n, 3)):
            text = r.look[i] if i < len(r.look) else ""
            if text:
                ev.append(("narr", text))
        if n < 3 and any(r.look[i] for i in range(n, min(3, len(r.look)))):
            ev.append(("sys", "Past that, the light has gone."
                              if self.phase == "park"
                              else "Past that, the beam gives out."))
        return ev

    # -- actions ------------------------------------------------------------

    def enter(self):
        """Arrive in the current room. Handles first-visit text and finds."""
        ev = []
        first = self.here not in self.visited
        self.visited.add(self.here)
        if self.phase == "cave" and (not self.trail
                                     or self.trail[-1] != self.here):
            self.trail.append(self.here)

        ev += self.describe(full=True)

        if first and self.room.first:
            ev.append(("narr", self.room.first))
        if first and self.here in ("roost", "ladder"):
            self.cells += 1
            ev.append(("good", "SPARE CELL STOWED."))
        if first and self.here == "deep":
            self.flags.add("found")

        if first:
            # what you learned up top, arriving where it means something
            for flag, line in PAYOFFS.get(self.here, {}).items():
                if flag in self.flags:
                    ev.append(("sys", line))

        ev += self._ambience()
        return ev

    def _ambience(self):
        if self.phase == "park":
            if self.rng.random() < 0.42:
                return [("sound", self._pick_sound(PARK_AMBIENCE))]
            return []
        chance = (0.30, 0.45, 0.70)[self.dread]
        if self.rng.random() < chance:
            return [("sound", self._pick_sound(AMBIENCE[self.dread]))]
        return []

    def _pick_sound(self, pool):
        line = self.rng.choice(pool)
        if line == self._last_sound and len(pool) > 1:
            line = self.rng.choice([x for x in pool if x != self._last_sound])
        self._last_sound = line
        return line

    def choices(self):
        """The numbered actions, in order: people, then clues, then ways on.

        Act Two rooms have neither people nor clues, so this collapses back
        to the list of exits and behaves exactly as it always did.
        """
        out = []
        if self.phase == "park":
            for p in self.room.people:
                n = self.said.get(p.name, 0)
                if n >= len(p.beats):
                    out.append(("talk", p.name, False, "nothing more", p))
                else:
                    verb = "Talk to" if n == 0 else "Press"
                    out.append(("talk", f"{verb} {p.name}", True, p.role, p))
            for c in self.room.clues:
                if f"seen:{c.label}" in self.flags:
                    out.append(("clue", c.label, False, "done", c))
                elif c.mins >= CLOSE_WORK and self.daylight < 25:
                    out.append(("clue", c.label, False,
                                "not in this light", c))
                else:
                    out.append(("clue", c.label, True, f"{c.mins} min", c))
            for it in self.room.pickups:
                # offered once you have looked at it, and only until you say
                if it.needs not in self.flags or f"chose:{it.flag}" in self.flags:
                    continue
                out.append(("take", f"Take {it.label}", True, "", it))
                out.append(("leave", f"Leave {it.label}", True, "", it))
        for x, ok, why in self.exits():
            out.append(("go", x.label, ok, why, x))
        return out

    def act(self, idx):
        """Take the idx-th numbered action."""
        opts = self.choices()
        if idx >= len(opts):
            return []
        kind, label, ok, why, obj = opts[idx]
        if not ok:
            return [("sys", f"No. {why.capitalize()}.")]
        if kind == "talk":
            return self._talk(obj)
        if kind == "clue":
            return self._inspect(obj)
        if kind in ("take", "leave"):
            return self._decide(obj, kind == "take")
        return self.move(self.room.exits.index(obj))

    def _talk(self, person):
        n = self.said.get(person.name, 0)
        text, flag = person.beats[n]
        self.said[person.name] = n + 1
        if flag:
            self.flags.add(flag)
        ev = [("title", f"{person.name}   ·   {person.role}")]
        ev.append(("narr", text))
        ev += self._burn(3)
        self._check_ready()
        return ev

    def _inspect(self, clue):
        self.flags.add(f"seen:{clue.label}")
        if clue.flag:
            self.flags.add(clue.flag)
        ev = [("title", clue.label)]
        ev.append(("narr", clue.text))
        ev += self._burn(clue.mins)
        self._check_ready()
        return ev

    def _decide(self, it, taking):
        """Take it or leave it. Costs no daylight and does not come back."""
        self.flags.add(f"chose:{it.flag}")
        if taking:
            self.flags.add(it.flag)
        return [("title", it.label.capitalize()),
                ("narr", it.take if taking else it.leave)]

    def _check_ready(self):
        """You go down once you have your brief and have faced the family."""
        if {"brief", "mother"} <= self.flags:
            self.flags.add("ready")

    def exits(self):
        """[(exit, enabled, reason)] for the current room."""
        out = []
        for x in self.room.exits:
            enabled, reason = True, ""
            if x.rope and f"rigged:{x.to}" not in self.flags:
                if self.rope < x.rope:
                    enabled, reason = False, f"needs {x.rope} m of rope"
            if self._sealed(self.here, x.to):
                if self.rope < BYPASS_ROPE:
                    enabled, reason = False, "buried by the collapse"
                else:
                    reason = f"rig a bypass, {BYPASS_ROPE} m"
            if x.need and x.need not in self.flags:
                enabled, reason = False, x.deny or "not yet"
            out.append((x, enabled, reason))
        return out

    def _sealed(self, a, b):
        """Is the breakdown-cache link shut by the collapse?"""
        return ({a, b} == {"pack", "breakdown"}
                and "collapsed" in self.flags
                and "bypassed" not in self.flags)

    def move(self, idx):
        opts = self.exits()
        if idx >= len(opts):
            return []
        x, enabled, reason = opts[idx]
        if not enabled:
            return [("sys", f"No. {reason.capitalize()}.")]

        ev = []

        # rope committed to a pitch, permanently
        if x.rope and f"rigged:{x.to}" not in self.flags:
            self.rope -= x.rope
            self.flags.add(f"rigged:{x.to}")
            ev.append(("sys", f"{x.rope} m rigged and left in place. "
                              f"{self.rope} m remaining."))

        # the collapse bypass
        if self._sealed(self.here, x.to):
            self.rope -= BYPASS_ROPE
            self.flags.add("bypassed")
            ev.append(("sys", f"You rig {BYPASS_ROPE} m over the new block "
                              f"and haul yourself across it. {self.rope} m "
                              f"remaining."))

        if x.once and f"once:{x.to}:{self.here}" not in self.flags:
            self.flags.add(f"once:{x.to}:{self.here}")
            ev.append(("narr", x.once))
        if x.travel:
            ev.append(("narr", x.travel))

        ev += self._hazard(x)
        if self.ending:
            return ev

        src, dst = self.here, x.to
        air_bad = ("badair" in ROOMS[src].tags) or ("badair" in ROOMS[dst].tags)
        self.here = dst
        ev += self._burn(x.mins, air_bad=air_bad)
        if self.ending:
            return ev

        if self.here in ("drowned", "stay"):
            return ev
        if self.here == "sink" and src == "letterbox":
            # Daylight beats a dead lamp. Being caught in the crawl does not.
            if self.ending in (None, "DARK"):
                self.ending = ("OUT_WITH" if "took_find" in self.flags
                               else "OUT_ALONE")
            return ev

        ev += self.enter()
        return ev

    def _hazard(self, x):
        h = x.hazard
        if h == "dive":
            self.ending = "SUMP"
            return [("alarm",
                "Four metres in, the line goes slack in your hand.\n\n"
                "Not cut. Not snagged. Slack, the way a line goes slack when "
                "the person holding the other end lets go of it, and you are "
                "in black water under a roof of rock with no surface above "
                "you and no direction that means up.\n\n"
                "The last thing you are certain of is that something gave "
                "the line back to you.")]
        if h == "collapse":
            if "collapsed" not in self.flags and x.to == "pack":
                self.flags.add("collapsed")
                return [("alarm",
                    "Halfway across, the pile lets go behind you.\n\n"
                    "You are flat on your face with grit in your teeth and "
                    "the roar of it going on and on in a space that should "
                    "not hold that much sound, and when you get your light "
                    "up the way you came is a wall.\n\n"
                    "You are not hurt. You are simply on the wrong side of "
                    "thirty tonnes of rock now, and there is one other way "
                    "out of here and it is the bad air.")]
            return []
        if h == "took_find":
            if self.pursuit is None:
                self.pursuit = 0
                self.flags.add("took_find")
                return [("alarm",
                    "The moment the helmet is off the silt, everything in "
                    "the room changes its mind about you.\n\n"
                    "GET OUT.")]
            return []
        if h == "descend":
            self.phase = "cave"
            self.lamp_on = True
            self.minutes = 0
            return [
                ("title", "THE GROUND SEARCH"),
                ("sys",
                 "They give you the surface first, because that is the "
                 "order you do it in.\n\n"
                 "Eleven people walk the drainage in a line abreast until "
                 "full dark and then walk it again with lights. Two dog "
                 "teams come up from Blakely at ten and work until one and "
                 "get nothing — not a lost scent, not a confused scent. "
                 "Nothing to be confused about. The handler says her dog "
                 "would not go past the seedling line at the edge of the "
                 "dead timber and she says it in the voice people use when "
                 "they would like you to ask a follow-up question, and you "
                 "do not ask it."),
                ("sys",
                 "At 01:50 Trammell calls it. The surface is clear. "
                 "Whatever happened to Wren Alcott happened underground, "
                 "and it happened nineteen hours ago, and there is one "
                 "person on this ridge with a ticket to go and find out."),
                ("sys",
                 f"Piney Ridge National Park.  "
                 f"{DESCENT_START // 60:02d}:{DESCENT_START % 60:02d}.  "
                 f"Search and rescue callout, one subject, now thirty-two "
                 f"hours overdue."),
            ]
        if h == "answer":
            self.ending = "STAY"
            return []
        return []

    def listen(self):
        ev = self._burn(1)
        if self.ending: return ev
        if self.phase == "park":
            return ev + [("sound", self._pick_sound(PARK_AMBIENCE))]
        if self.dread >= 2 and self.trail and self.rng.random() < 0.72:
            past = self.rng.choice(self.trail[:-1] or self.trail)
            act = ECHO_ACTS.get(past, "footsteps")
            ev.append(("sound", self.rng.choice(ECHO_FRAME).format(act)))
        else:
            ev.append(("sound", self._pick_sound(AMBIENCE[self.dread])))
        return ev

    def radio(self):
        ev = self._burn(2)
        if self.ending: return ev
        sig = self.signal
        ev.append(("sys", "You key the set and give your callsign and "
                          "position."))
        ev.append(("radio", self.rng.choice(RADIO[sig])))
        return ev

    def look(self):
        ev = self._burn(1)
        if self.ending: return ev
        return ev + self.describe(full=True)

    def toggle_lamp(self):
        """Act One only. Underground the lamp is why you are still alive."""
        if self.phase == "cave":
            return [("sys", "The lamp stays on. That is not a decision you "
                            "get to make at sixty metres.")]
        self.lamp_on = not self.lamp_on
        if not self.lamp_on:
            return [("sys", "You switch the lamp off. Your eyes take a "
                            "while to give the evening back to you.")]
        if self.daylight >= 25:
            return [("sys", "You switch the lamp on. In this much daylight "
                            "it puts a pale coin on the ground in front of "
                            "your boots and tells you nothing.")]
        return [("sys", "You switch the lamp on, and the hillside shrinks "
                        "to the eleven feet of it you can see.")]

    def toggle_dim(self):
        self.dim = not self.dim
        if self.dim:
            return [("sys", "You stop the beam down to a coin of light at "
                            "your boots. It will last twice as long. You "
                            "will see half as much.")]
        return [("sys", "You open the beam back up. The room comes back, "
                        "and so does the cost.")]

    def ending_body(self):
        """The ending text, with the clock filled in where it matters."""
        head, kind, body = ENDINGS[self.ending]
        if self.ending in TIMED:
            band = self._sky_band()
            body = body.format(clock=self.surface_clock(),
                               sky=SKY[band], arrival=ARRIVAL[band])
        return head, kind, body

    def ending_note(self):
        """You gave the family a turnaround time. This is you missing it."""
        late = self.overdue_by()
        if not late or self.ending not in TIMED:
            return None
        return ("Trammell called Blakely at six, the way he said he would. "
                f"You are {late} minutes past your own turnaround, and there "
                "are two more vehicles on the bench than there were, and a "
                "helicopter working the next drainage over, and every one of "
                "those people came up here for you.")

    def swap_cell(self):
        if self.cells <= 0:
            return [("sys", "You have no spare cell. You check twice.")]
        self.cells -= 1
        self.lamp = 100.0
        ev = self._burn(3)
        return [("good", "You change the cell in the dark, by feel, with "
                         "the old one held in your teeth. The light comes "
                         "back and the room is exactly where you left it.")] + ev


    # -- saving -------------------------------------------------------------

    SAVED = ("phase", "park_minutes", "here", "lamp", "lamp_on", "dim",
             "air", "rope", "cells", "minutes", "ending", "pursuit",
             "_last_sound")

    def snapshot(self):
        """The whole run, as data a JSON file will hold.

        The rng state goes in with it, so a resumed run flips the coins it
        was always going to flip. Reloading is not a way to make the cave
        pick a different one of your own footsteps to play back at you.
        """
        data = {k: getattr(self, k) for k in self.SAVED}
        data["said"] = dict(self.said)
        data["visited"] = sorted(self.visited)
        data["flags"] = sorted(self.flags)
        data["trail"] = list(self.trail)
        ver, keys, gauss = self.rng.getstate()
        data["rng"] = [ver, list(keys), gauss]
        return data

    @classmethod
    def restore(cls, data):
        """A Game from snapshot() data, or None if the data is not one.

        Anything unreadable comes back as None rather than as a half-built
        run: a save from an older cave would put you in a room that no
        longer has the exit you were counting on.
        """
        try:
            g = cls(data.get("seed"))
            for k in cls.SAVED:
                setattr(g, k, data[k])
            g.said = {str(n): int(v) for n, v in data["said"].items()}
            g.visited = set(data["visited"])
            g.flags = set(data["flags"])
            g.trail = [r for r in data["trail"]]
            ver, keys, gauss = data["rng"]
            g.rng.setstate((int(ver), tuple(int(k) for k in keys), gauss))
        except (AttributeError, KeyError, TypeError, ValueError):
            return None
        if g.phase not in ("park", "cave") or g.here not in ROOMS:
            return None
        if not all(r in ROOMS for r in g.visited | set(g.trail)):
            return None
        return g


# --------------------------------------------------------------------------
#  ENDINGS
#
#  The two you can walk away from resolve against the clock. A run is
#  anywhere from twelve minutes to most of the night, so what the sky is
#  doing when you come out is not something the prose can know in advance.
# --------------------------------------------------------------------------

SKY = (
    "the ridge is exactly as black as it was when you went in and the work "
    "lights are the only thing on it",
    "there is a thinning over the ridge that is not light yet and is not "
    "night any more either",
    "the ridge is going grey around the work lights",
    "it has been full morning long enough that the work lights are pointless "
    "and nobody has thought to switch them off",
)

ARRIVAL = (
    "in the middle of the night",
    "in the last of the dark",
    "at first grey",
    "well after sunrise",
)

TIMED = ("OUT_WITH", "OUT_ALONE")

ENDINGS = {
"OUT_WITH": ("YOU CAME OUT", "good",
    "You come out of the Letterbox into a smell you had forgotten existed, "
    "which is dirt with things growing in it.\n\n"
    "It is {clock} and {sky}, and there are eleven people at the sink, and "
    "one of them is holding a thermos, and one of them is Wren Alcott's "
    "mother.\n\n"
    "You hand over the helmet. The lamp is still burning. It burns for "
    "another six days in an evidence locker in the county seat and then it "
    "stops, all at once, at 03:11 in the morning, and the deputy who logs "
    "it writes CELL EXHAUSTED because there is no other box to tick.\n\n"
    "Wolf Sink is gated in November. The park calls it a bat conservation "
    "measure.\n\n"
    "There are no bats in Wolf Sink."),

"OUT_ALONE": ("YOU CAME OUT", "sys",
    "You come out {arrival} with nothing.\n\n"
    "You are debriefed for two hours. You give the passages, the depths, "
    "the rigging, the times — all of it clean, all of it professional, and "
    "none of it explains why you turned around.\n\n"
    "The search is called at day nine. Wren Alcott is a name on a board.\n\n"
    "You do not cave again. That is fine. What is not fine is that some "
    "nights, in a house with the lights on, you can hear the specific sound "
    "of a room the size of a cathedral, and you know exactly how far away "
    "it is, and it is not far."),

"STAY": ("—", "alarm",
    "And it is so relieved.\n\n"
    "That is the part you were not ready for — that it has been down here "
    "in the dark for a length of time you cannot hold in your head, and it "
    "is so relieved that someone finally answered.\n\n"
    "It steps forward into your light to show you what it has been "
    "practising.\n\n"
    "It has been practising you.\n\n"
    "Nineteen hours later a SAR officer comes out of Wolf Sink at dawn, "
    "cold and shaken and entirely themselves, and gives a clean debrief, "
    "and hands over a folded oversuit, and goes home.\n\n"
    "Somebody has to. There is a whole park up there, and it is full of "
    "people who go into caves alone."),

"TAKEN": ("—", "alarm",
    "There is no report. There is a callout, and a search, and a second "
    "search, and then a gate.\n\n"
    "Wolf Sink has three names on the board outside the ranger station now. "
    "The oldest is from 1911."),

"DARK": ("LAMP FAILURE", "alarm",
    "They find you on the fourth day, at the foot of the pitch, sitting up "
    "with your back to the wall, hypothermic and eleven hours past saving.\n\n"
    "Your lamp is in your lap, switched off, with a fresh cell in it."),

"AIR": ("BAD AIR", "alarm",
    "The recovery team wears breathing apparatus into the Sallow and finds "
    "you eighteen metres in, face-down, pointed the wrong way.\n\n"
    "Everyone agrees it was the CO2. Everyone agrees people get "
    "disoriented. Nobody wants to talk about why you were crawling deeper."),

"SUMP": ("SUMP", "alarm",
    "Your body is not recovered. Cave divers go in twice and the second "
    "team surfaces early and will not say why.\n\n"
    "The dive line is still there. It is knotted to a rock thread at the "
    "near end. Nobody knows what it is knotted to at the far end, and "
    "there is no record of anyone ever having put it in."),
}
