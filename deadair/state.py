"""
DEAD AIR — engine.

Pure logic. Returns a list of (style, text) events for the UI to render;
knows nothing about Textual.

Styles: narr | sound | radio | sys | alarm | good | title
"""

import random

from .content import (ROOMS, AMBIENCE, AMBIENCE_AFTER, ECHO_FRAME, ECHO_ACTS,
                      RADIO, RADIO_AT_BASECAMP, RADIO_AT_SINK, PARK_AMBIENCE, PARK_DUSK,
                      PAYOFFS, LISTEN_QUIET, PARK_QUIET, PARK_SILENCE, PAGE)

# --- tuning ----------------------------------------------------------------
LAMP_BURN_HIGH = 0.45      # % per minute, beam wide
LAMP_BURN_LOW = 0.22       # % per minute, beam stopped down
AIR_DRAIN = 5.5            # % per minute in a bad-air pocket
AIR_RECOVER = 4.0          # % per minute in clean air
ROPE_TOTAL = 60            # meters carried
PURSUIT_LIMIT = 115        # minutes you have, once you take the helmet
BYPASS_ROPE = 20           # meters to rig past the collapse
DAYLIGHT_TOTAL = 85        # minutes of usable dusk in Act One
PARK_START = 18 * 60 + 40  # 18:40, when you get out of the truck
DESCENT_START = 2 * 60 + 14   # 02:14, when you put your legs into the cold
TURNAROUND = 6 * 60           # 06:00, when Trammell calls Blakely
DAWN = 5 * 60 + 35            # 05:35, enough gray at the choke to burn with
CLOSE_WORK = 4             # a clue this slow is close work, and
                           # close work needs real light
LISTEN_NOTHING = 0.20      # underground, how often L gives you nothing at all


class Game:
    def __init__(self, seed=None):
        self.seed = seed           # kept so a new run can repeat this one
        self.rng = random.Random(seed)
        self.phase = "park"        # "park" (Act One) | "cave" (Act Two)
        self.park_minutes = 0
        self.said = {}             # person name -> beats already given
        self.focus = None          # a clue's own picture, while you look at it
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
        self.heard = set()         # every sound it has given you: none twice

    # -- derived ------------------------------------------------------------

    @property
    def room(self):
        return ROOMS[self.here]

    @property
    def view(self):
        """What the viewport shows: where you are, or, straight after you
        have gone over to look at something that has a picture of its own
        (the chimney fall, the springhouse), that. Not saved — a resumed
        run is back standing in the room."""
        return self.focus or self.here

    @property
    def depth(self):
        return self.room.depth

    @property
    def reach(self):
        """Effective beam reach, 0-100. Dimming saves battery but costs sight."""
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
        # up in the gray the dawn is doing some of the work, and at the lip
        # of the sink the work lights are: not enough to see the room by,
        # but you are never down to your hand on the rock
        return 1 if self.lit_without_lamp else 0

    @property
    def lit_without_lamp(self):
        """Somewhere a dead lamp does not leave you blind: the gray at the
        choke, or the work lights at the sink."""
        return bool({"gray", "surface"} & self.room.tags)

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
        """September, this latitude: astronomical twilight around 04:50,
        nautical around 05:35, civil around 06:15, sun about 06:40 — so
        'well after sunrise' waits until 07:15."""
        m = DESCENT_START + self.minutes
        if m < 4 * 60 + 50: return 0
        if m < 5 * 60 + 35: return 1
        if m < 6 * 60 + 15: return 2
        if m < 7 * 60 + 15: return 3
        return 4

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
        self.lamp -= rate * mins
        if self.lamp <= 0 and self.cells > 0:
            # Nobody sits down in the dark with a spare in their pocket.
            # Whatever the dead battery still owed comes out of the new one.
            self.cells -= 1
            self.lamp += 100.0
            ev.append(("good",
                "The lamp dies. Not dramatically. It just stops — and your "
                "hands are at your chest pocket before the dark has finished "
                "arriving. You change the battery by feel, with the old one held "
                "in your teeth. The light comes back, and the room is exactly "
                "where you left it."))
        self.lamp = max(0.0, self.lamp)

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
                0: "The LEDs go. Not off — down, to an ember, to a color. "
                   "You are functionally blind"
                   + (f", {-self.depth} meters under the hill."
                      if self.depth <= -10 else ".")
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
        if self.lamp <= 0 and not self.lit_without_lamp:
            # up in the gray the dawn beats a dead lamp, the way the work
            # lights do at the sink when you come out of the Letterbox on
            # the last of it
            self.ending = "DARK"
            if "with_wren" in self.flags:
                return [("alarm",
                    "The lamp dies. Not dramatically. It just stops, and the "
                    "dark that replaces it is complete, and it has weight.\n\n"
                    "You get your back to the rock and her shoulder against "
                    "yours, because that is the protocol: stay put, conserve, "
                    "wait for the team. She is counting again, under her "
                    "breath.\n\nAfter a while, she stops. After a while "
                    "longer, something sits down on your other side.")]
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
        look = r.look
        for flag, alt in r.look_if.items():
            if flag in self.flags:
                look = alt
        n = self.layers
        if n == 0:
            ev.append(("narr", "You put your hand out and find rock. That is "
                               "the whole of what you know about this place."))
            return ev
        for i in range(min(n, 3)):
            text = look[i] if i < len(look) else ""
            if text:
                ev.append(("narr", text))
        if n < 3 and any(look[i] for i in range(n, min(3, len(look)))):
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

        if first and self.room.found and self.layers < 3:
            # the beam did not get there, but on a first visit you did
            ev.append(("narr", self.room.found))
        if first and self.room.first:
            ev.append(("narr", self.room.first))
        if first and self.here in ("roost", "ladder"):
            self.cells += 1
            ev.append(("good", "SPARE BATTERY STOWED."))
        if first:
            # what you learned up top, arriving where it means something
            for flag, line in PAYOFFS.get(self.here, {}).items():
                if flag in self.flags:
                    ev.append(("sys", line))

        ev += self._ambience()
        return ev

    def _ambience(self):
        # Above ground the ridge only makes noise when you stop and listen.
        if self.phase == "park" or "quiet" in self.room.tags:
            return []
        chance = (0.30, 0.45, 0.70)[self.dread]
        if self.rng.random() < chance:
            line = self._pick_sound(AMBIENCE[self.dread])
            return [("sound", line)] if line else []
        return []

    def _pick_sound(self, pool):
        """A line from `pool` you have not heard yet, or None once you have
        heard all of them. Nothing the cave says comes twice, so the longer
        you are down here the quieter it gets."""
        fresh = [x for x in pool if x not in self.heard
                 and AMBIENCE_AFTER.get(x, self.here) in self.visited]
        if not fresh:
            return None
        line = self.rng.choice(fresh)
        self.heard.add(line)
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
                                "not by headlamp" if self.lamp_on
                                else "not in this light", c))
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
        self.focus = None
        if kind == "talk":
            return self._talk(obj)
        if kind == "clue":
            return self._inspect(obj)
        if kind in ("take", "leave"):
            return self._decide(obj, kind == "take")
        return self.move([x for x, _, _ in self.exits()].index(obj))

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
        self.focus = clue.scene or None
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
        came = self.trail[-2] if len(self.trail) > 1 else ""
        for x in self.room.exits:
            if x.unless and x.unless in self.flags:
                continue
            if x.when and x.when not in self.flags:
                continue
            if x.came_from and x.came_from != came:
                continue
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

        # the gray at the choke: you wait for it before you set off, not
        # after the climb has already been told
        if x.hazard == "climb_out":
            ev += self._wait_for_dawn()

        seen = f"once:{x.to}:{self.here}"
        first = (x.once or x.once_after) and seen not in self.flags
        if first:
            self.flags.add(seen)
        if first and x.once:
            ev.append(("narr", x.once))
        if x.travel:
            ev.append(("narr", x.travel))
        if first and x.once_after:
            ev.append(("narr", x.once_after))

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
            # The work lights beat a dead lamp (see lit_without_lamp).
            # Being caught in the crawl does not.
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
                "Four meters in, the line goes slack in your hand.\n\n"
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
                    "thirty tons of rock now, and the way back is the bad "
                    "air, or rope you would rather not spend.")]
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
                 "A dozen people walk the drainage in a line abreast until "
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
                 "and there is one person on this ridge with a ticket to go "
                 "and find out."),
                ("sys",
                 f"Piney Ridge National Park.  "
                 f"{DESCENT_START // 60:02d}:{DESCENT_START % 60:02d}.  "
                 f"Search and rescue callout, one subject, now twenty-seven "
                 f"hours overdue."),
            ]
        if h == "answer":
            self.ending = "STAY"
            return []
        if h == "burn":
            # The lens at the nest: the helmet lamp is not enough light down
            # here to finish it, but it buys the gap to get her moving.
            self.flags.add("with_wren")
            return [("alarm",
                "You get the lens up in front of the helmet lamp, and the "
                "flood of the beam collapses through it to a single white "
                "point, and where the point lands on the shape between you "
                "and her, the dark flinches back.\n\n"
                "Not enough. There is not enough light down here to do more "
                "than that. But it is enough of a gap to get past it to her, "
                "take her weight, and turn her toward where the air is "
                "coming from.")]
        if h == "unarmed":
            self.flags.add("bolted")
            self.flags.add("with_wren")
            return [("alarm",
                "You do not try anything with it. The light swings wild off "
                "the walls and whatever comes after you does not need the "
                "light to see by, and you do not look back to check.")]
        if h == "climb_out":
            # The mine head: the lens has a real source here — the knife of
            # gray the mountain leaks at dawn — but only if you still have it
            # and did not panic your way out of the nest. If so, you get the
            # choke, and the choice of whether to use it, instead of a
            # foregone conclusion. The wait for the gray has already
            # happened, in move().
            if "lens" in self.flags and "bolted" not in self.flags:
                return []
            self.ending = "RESCUE_HARD"
            return []
        if h == "rescue_run":
            # the lens stays in your pocket: out clean, and it keeps the cave
            self.ending = "RESCUE_HARD"
            return []
        if h == "rescue_now":
            self.ending = "RESCUE_INJURED"
            return []
        if h == "rescue_watch":
            self.ending = "RESCUE_CLEAN"
            return []
        return []

    def _wait_for_dawn(self):
        """Every way out of the adit is keyed to the gray, so you wait for it.

        A fast run reaches the choke long before morning. The wait is spent
        with the beam stopped down, and it can drain the battery but never kill
        it — this is the part of the night you have already survived. The
        pursuit clock does not run: whatever is behind you catches up in the
        choke, not here.
        """
        wait = DAWN - (DESCENT_START + self.minutes)
        if wait <= 0:
            return []
        self.minutes += wait
        self.lamp = max(min(self.lamp, 2.0), self.lamp - LAMP_BURN_LOW * wait)
        # the fastest run there is gets here at 04:12, so it is never much
        # more than an hour and a half
        how = ("It does not keep you long." if wait < 20 else
               "It keeps you half an hour or so." if wait < 40 else
               "It keeps you most of an hour." if wait < 55 else
               "It keeps you about an hour." if wait < 70 else
               "It keeps you well over an hour.")
        # if you ran, it came after you, and it is still down there
        below = ("Below you, just past where the beam gives out, something "
                 "is waiting too. It does not come into the light. "
                 if "bolted" in self.flags else "")
        return [("narr",
                 "You wait for it at the foot of the choke with the beam "
                 "stopped down, her shoulder against yours. She counts under "
                 "her breath the whole time, and you do not say anything. "
                 + below + how)]

    def listen(self):
        ev = self._burn(1)
        if self.ending: return ev
        if self.phase == "park":
            if "quiet" in self.room.tags:
                return ev + [("sound", PARK_SILENCE)]
            pool = PARK_AMBIENCE + ([PARK_DUSK] if self.daylight > 0 else [])
            line = self._pick_sound(pool)
            return ev + [("sound", line or PARK_QUIET)]
        # Sometimes it gives you nothing at all. Deep in, what it gives you
        # is yourself — each thing you did, played back once and only once.
        if self.rng.random() < LISTEN_NOTHING:
            return ev + [("sound", LISTEN_QUIET)]
        if self.dread >= 2 and self.trail and self.rng.random() < 0.72:
            fresh = [r for r in (self.trail[:-1] or self.trail)
                     if ECHO_ACTS.get(r, "footsteps") not in self.heard]
            if fresh:
                act = ECHO_ACTS.get(self.rng.choice(fresh), "footsteps")
                self.heard.add(act)
                line = self.rng.choice(ECHO_FRAME).format(act)
                return ev + [("sound", line[0].upper() + line[1:])]
        line = self._pick_sound(AMBIENCE[self.dread])
        return ev + [("sound", line or LISTEN_QUIET)]

    def radio(self):
        if self.phase == "park" and self.here == "basecamp":
            return [("sys", RADIO_AT_BASECAMP)]
        if self.phase == "cave" and self.here == "sink":
            return [("sys", RADIO_AT_SINK)]
        ev = self._burn(2)
        if self.ending: return ev
        if self.phase == "park":
            pool = RADIO["park_back" if "basecamp" in self.visited else "park"]
        else:
            pool = RADIO[self.signal]
        ev.append(("sys", "You key the set and give your callsign and "
                          "position."))
        ev.append(("radio", self.rng.choice(pool)))
        return ev

    def look(self):
        self.focus = None
        ev = self._burn(1)
        if self.ending: return ev
        return ev + self.describe(full=True)

    def toggle_lamp(self):
        """Act One only. Underground the lamp is why you are still alive."""
        if self.phase == "cave":
            return [("sys", "The lamp stays on. That is not a decision you "
                            "get to make down here.")]
        self.lamp_on = not self.lamp_on
        if not self.lamp_on:
            return [("sys", "You switch the lamp off. Your eyes take a "
                            "while to give the evening back to you.")]
        if self.daylight >= 25:
            return [("sys", "You switch the lamp on. In this much daylight "
                            "it puts a pale coin on the ground in front of "
                            "your boots and tells you nothing.")]
        return [("sys", "You switch the lamp on, and the hillside shrinks "
                        "to the few yards of it you can see.")]

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
        if self.ending == "DARK" and "with_wren" in self.flags:
            head, kind, body = DARK_WITH_WREN
        if self.ending == "OUT_ALONE" and "nest" in self.visited:
            # you found her alive, and you came out without her
            head, kind, body = OUT_ALONE_LEFT_HER
        if self.ending in TIMED:
            band = self._sky_band()
            body = body.format(clock=self.surface_clock(),
                               sky=SKY[band], arrival=ARRIVAL[band],
                               haunt=HAUNT["long_room" in self.visited])
        elif self.ending in RESCUES:
            body = body.format(dawn=DAWN_SKY[max(2, self._sky_band())])
        return head, kind, body

    def ending_note(self):
        """You gave the family a turnaround time. This is you missing it."""
        late = self.overdue_by()
        if not late or self.ending not in SURVIVED:
            return None
        mins = f"{late} minute" + ("" if late == 1 else "s")
        return ("Trammell called Blakely at six, the way he said he would. "
                f"You are {mins} past your own turnaround, and there "
                "are two more vehicles on the bench than there were, and a "
                "helicopter working the next drainage over, and every one of "
                "those people came up here for you.")

    def swap_cell(self):
        if self.cells <= 0:
            return [("sys", "You have no spare battery. You check twice.")]
        self.cells -= 1
        self.lamp = 100.0
        ev = self._burn(3)
        return [("good", "You pull the old battery and change it in the dark, "
                         "by feel, with the old one held in your teeth. The "
                         "light comes back and the room is exactly where you "
                         "left it.")] + ev


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
        data["heard"] = sorted(self.heard)
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
            # a save from before sounds stopped repeating has heard nothing
            g.heard = set(data.get("heard", []))
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
    "night anymore either",
    "the ridge is going gray around the work lights",
    "the sun is coming up and the work lights are already beside the point",
    "it has been full morning long enough that the work lights are pointless "
    "and nobody has thought to switch them off",
)

ARRIVAL = (
    "in the middle of the night",
    "in the last of the dark",
    "at first gray",
    "at sunrise",
    "well after sunrise",
)

TIMED = ("OUT_WITH", "OUT_ALONE")

# The rescues are keyed to dawn, so they never come out in the dark — only
# into the gray, or, if you took long enough getting there, into morning.
RESCUES = ("RESCUE_HARD", "RESCUE_INJURED", "RESCUE_CLEAN")
DAWN_SKY = {2: "with the sky going gray", 3: "at sunrise",
            4: "into full morning"}

# every ending you walk out of
SURVIVED = TIMED + RESCUES

ENDINGS = {
"OUT_WITH": ("YOU CAME OUT", "good",
    "You come out of the Letterbox into a smell you had forgotten existed: "
    "dirt with things growing in it. Life.\n\n"
    "It is {clock} and {sky}, and there is a crowd of people at the sink. One "
    "of them is holding a thermos, and the second you notice is Wren's "
    "mother.\n\n"
    "You hand over the helmet. The lamp is still burning. It burns for "
    "another six days in an evidence locker in the county seat and then it "
    "stops, all at once, at 03:04, and the deputy who logs it writes "
    "BATTERY DEPLETED because there is no other box to tick.\n\n"
    "Wolf Sink is gated in November. The park calls it a bat conservation "
    "measure.\n\n"
    "There are no bats in Wolf Sink."),

"OUT_ALONE": ("YOU CAME OUT", "sys",
    "You come out {arrival} with nothing.\n\n"
    "You are debriefed for two hours. You give the passages, the depths, "
    "the rigging, the times — all of it clean and professional, and none "
    "of it explains why you turned around. They know that. Nobody "
    "asks.\n\n"
    "The search is called at day nine. Wren Alcott is now the third name "
    "on the board.\n\n"
    "You do not cave again. That is fine. What is not fine is that some "
    "nights, in a house with the lights on, you can hear {haunt}"),

"RESCUE_INJURED": ("YOU BROUGHT HER OUT", "good",
    # the grip itself is the `grip` room's first-visit text in content.py
    "You get her up and out under the hemlocks {dawn}, "
    "your glove filling with something that is not entirely blood, and you "
    "do not look at it properly until you have gotten her around the hill "
    "to the work lights and Trammell is already cutting the glove off.\n\n"
    "Junie gets to her first. Nobody tells her she is not family. "
    "Rosalind stays exactly where she is, at the edge of the work "
    "lights, and looks at her daughter for a long time, the way she "
    "promised she would. Then she says, \"It's her,\" and crosses the "
    "light." + PAGE +
    "Your statement and Wren's go to the district's cave specialist, the "
    "man with the list, and they describe the same thing, and it is the "
    "thing in eleven pages in a drawer in Blakely under PARTY UNWILLING. "
    "He signs the order that week.\n\n"
    "Wolf Sink is gated. The paperwork says something about bat "
    "conservation. The man who welds it does the whole rim, not just the "
    "entrance. He is not told why. He does not ask. The old workings on "
    "the far side of the hill get a loader and forty tons of fill, the "
    "same as in 1911.\n\n"
    "The hand heals wrong. Two fingers do not fully close again, the "
    "surgeon writing nerve damage consistent with a crush injury. He's not "
    "totally wrong." + PAGE +
    "The other thing is not on the chart... there is nothing to put it "
    "on. It settles behind your sternum, small, about the size of the "
    "lens, and it is cold the way the hand is numb — not painful, just "
    "present like a scar. Heat does not touch it — you have tried. Most "
    "days you forget it is there, the way you stop noticing an old limp. "
    "Then, every September, close to the day you went down, it turns over "
    "on its own. You do not sleep right for a week, and you never once "
    "have a sentence ready that does not sound insane said out loud, so "
    "you never speak of it to anyone." + PAGE +
    "Wren Alcott gives a statement that is never released. You give one "
    "as well, holding the mic in your right hand, because the left will "
    "not close around it.\n\n"
    "You eventually go into another cave — years later — a show cave, "
    "handrails, a guide — and you are fine until the guide kills the "
    "lights for effect. Your hand finds the wall before you tell it to. So "
    "does the cold, for about a second — it turns over, the way it does "
    "every September, like it recognizes the dark — and then it settles, "
    "and you are fine again, and nobody on the tour saw anything at "
    "all."),

"RESCUE_CLEAN": ("YOU BROUGHT HER OUT", "good",
    "You do not turn. You keep the point on it and make yourself watch, "
    "which is the harder of the two things you could be doing right "
    "now.\n\n"
    "It runs on more joints than it has any right to, and none of them "
    "bend the way the last one did, as if it is relearning its own shape "
    "every time it moves. Bigger than the nest made it look and smaller "
    "than the dark made it sound, and for one full second, pinned by the "
    "light, it holds still enough for you to be certain of both those "
    "things and nothing else." + PAGE +
    "It stops trying to get past the light and starts, instead, showing you "
    "things — a room you have never stood in, a voice that is almost your "
    "mother's, the specific fear you have never once said out loud to "
    "another living person, pushed at you all at once, fast, the way you'd "
    "empty your pockets onto a table. It is not asking. It is searching "
    "out for what works. Probing your mind." + PAGE +
    "None of it works. You struggle, trying to keep the point on it as it "
    "throws itself around the cave to avoid the light until she is past "
    "you and up and out into the open air, and only then do you follow "
    "her, and behind you the gray goes back to being nothing.\n\n"
    "You walk her around the hill to the work lights {dawn}. "
    "Junie gets to her first. Nobody tells her she is not family. "
    "Rosalind stays exactly where she is, at the edge of the work "
    "lights, and looks at her daughter for a long time, the way she "
    "promised she would. Then she says, \"It's her,\" and crosses the "
    "light." + PAGE +
    "Your statement and Wren's go to the district's cave specialist, the "
    "man with the list, and they describe the same thing, and it is the "
    "thing in eleven pages in a drawer in Blakely under PARTY UNWILLING. "
    "He signs the order that week.\n\n"
    "Wolf Sink is gated. The paperwork says bat conservation. The man who "
    "welds it does the whole rim, not just the entrance, and he is not "
    "told why and does not ask. The old workings on the far side of the "
    "hill get a loader and forty tons of fill, the same as in 1911.\n\n"
    "Wren Alcott gives a statement that is never released. You give one "
    "too. Yours is shorter.\n\n"
    "You go into a cave once more, years later — a show cave, handrails, a "
    "guide — and you are fine until the guide kills the lights for effect. "
    "You are the only person on the tour who knows exactly what the dark "
    "can do with one second of your full attention, and you are still fine. "
    "That is somehow the worst part."),

"RESCUE_HARD": ("YOU BROUGHT HER OUT", "sys",
    "Fifteen meters of broken rock at forty degrees. You go up it. She goes "
    "up it. Something goes up it behind her.\n\n"
    "You do not stop and you do not look. You get a hand on her collar where "
    "the rock pinches and you drag her through it into the open, out under "
    "the hemlocks {dawn}, and you turn around with your "
    "light up and there is nothing in the gap.\n\n"
    "There was never going to be. It does not come out into the open. That is "
    "the one rule of it you can prove. But it is still down there, entire, "
    "having lost nothing tonight except the two of you." + PAGE +
    "You walk her around the hill to the work lights. "
    "Junie gets to her first. Nobody tells her she is not family. "
    "Rosalind stays exactly where she is, at the edge of the work "
    "lights, and looks at her daughter for a long time, the way she "
    "promised she would. Then she says, \"It's her,\" and crosses the "
    "light."
    "\n\n"
    "Wren Alcott lives. She is in the news for a week. She tells it once, "
    "plainly, on a local station. The interviewer's face does the thing "
    "bored news anchors' faces do, and neither Wren nor the anchor ever "
    "tells the story again.\n\n"
    "Wolf Sink is not gated. After the local news, there is no reason on "
    "paper to justify the cost of gating it, only a story. You call the district office in November, again in "
    "March to change their minds, and a third time the following autumn. "
    "After the third time they stop picking up or returning your "
    "calls." + PAGE +
    "Some Saturdays you drive out to the trailhead and thumb back through "
    "the carbon copies in the permit box. Most weeks there is nothing. "
    "Then, one spring, there is a name you do not know. Solo. The Wolf "
    "Sink box ticked.\n\n"
    "No exit time."),

"STAY": ("—", "alarm",
    "You answer, and it is so relieved.\n\n"
    "It has been down here in the dark for a length of time you cannot hold "
    "in your head, and it is so relieved that someone finally answered. You "
    "can sense its relief. It burrows deep inside you and settles in a way "
    "you could never describe.\n\n"
    "It steps forward into your light to show you what it has been "
    "practicing.\n\n"
    "It has been practicing you." + PAGE +
    "A day later, at dawn, an SAR officer comes out of Wolf Sink, cold "
    "and shaken and entirely themselves, and gives a clean debrief. They hand "
    "over a folded oversuit and go home." + PAGE +
    "Ten days later, someone who has known them for twenty-something years "
    "sits across a table from them and knows, immediately and completely, "
    "that they are not who they say they are. They file a report. Won't "
    "retract it. It goes in the same drawer the last one did, because that "
    "is where these things go, and somebody, eventually, has to type it "
    "up. And sooner or later, someone will go down there again."),

"TAKEN": ("—", "alarm",
    "There is no report. There is a callout, a search, a second search, and "
    "after the second unsuccessful search, a gate.\n\n"
    "Four names now populate the board outside the ranger station, and "
    "nobody in Blakely says Wolf Sink out loud anymore, not even to warn "
    "people off it."),

"DARK": ("LAMP FAILURE", "alarm",
    "They find you on the fourth day, sitting up with your back to the wall, "
    "hypothermic and only hours past saving.\n\n"
    "Your lamp is in your lap, switched off, with a fresh battery in it. "
    "You had none left."),

"AIR": ("BAD AIR", "alarm",
    "The recovery team wears breathing apparatus into the Sallow and finds "
    "you eighteen meters in, face-down, pointed the wrong way.\n\n"
    "Everyone agrees it was the CO2. Everyone agrees people get disoriented. "
    "They never debate or wish to talk about any other reasons you might have "
    "been crawling deeper."),

"SUMP": ("SUMP", "alarm",
    "Your body is not recovered. Cave divers go in twice. The second team "
    "surfaces early and never says why.\n\n"
    "The dive line is still there, knotted to a rock thread at the near "
    "end, and taut again. Nobody knows what is holding the far end, and "
    "there is no record of anyone ever having put it in."),
}

# How OUT_ALONE ends depends on how far you got before you turned around.
HAUNT = (
    # you never got as far as the Long Room
    "a room you never reached. A big one, a long way past where you turned "
    "around. You have no way of knowing what it sounds like, and you know "
    "anyway. You know exactly how far away it is, and it is far closer than "
    "you ever wanted it to be.",
    # you stood in it
    "the specific sound of a room the size of a cathedral, and you know "
    "exactly how far away it is, and it is far closer than you ever wanted "
    "it to be.",
)

# OUT_ALONE, when you found Wren alive in the nest and came out without her.
OUT_ALONE_LEFT_HER = ("YOU CAME OUT", "sys",
    "You come out {arrival} with nothing.\n\n"
    "You are debriefed for two hours. You give the passages, the depths, "
    "the rigging, the times — all of it clean and professional. You do not "
    "give them the bone floor, or the woman on the far side of it with her "
    "eyes open, counting. You leave that out, and you go on leaving it "
    "out." + PAGE +
    "Her mother finds you at the edge of the work lights before you leave "
    "and asks you, once, whether you saw anything. You tell her no. She "
    "looks at you for a long time, the way you would look at someone who "
    "came back not right.\n\n"
    "The search is called at day nine. Wren Alcott is now the third name on "
    "the board, and you are the only person alive who knows she was alive "
    "when they wrote it." + PAGE +
    "You do not cave again. That is fine. What is not fine is that some "
    "nights, in a house with the lights on, you can hear someone counting, "
    "low and continuous, and none of it is for you. You know exactly how far "
    "away she is.")

# DARK, when the lamp dies after the nest with Wren beside you. Same ending,
# same lamp in your lap — and a space where she was.
DARK_WITH_WREN = ("LAMP FAILURE", "alarm",
    "They find you on the fourth day, sitting up with your back to the rock, "
    "hypothermic and only hours past saving.\n\n"
    "Your lamp is in your lap, switched off, with a fresh battery in it. "
    "You had none left. There is room beside you for one more person, and the silt there is pressed flat, "
    "and nobody is in it.")
