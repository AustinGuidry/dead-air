"""
DEAD AIR — cave, prose, and flavor tables.

Pure data. No mechanics live here, so the writing can be edited without
touching the engine.

Room.look is layered by how far the lamp reaches:
    look[0]  arm's length   — always shown
    look[1]  the room       — needs a working lamp
    look[2]  beyond         — needs a strong lamp
As the battery dies you literally stop being told what is there.
"""

from dataclasses import dataclass, field


@dataclass
class Exit:
    label: str                  # what the action button says
    to: str                     # destination room id
    travel: str = ""            # prose while moving
    mins: int = 4               # minutes of lamp burn
    rope: int = 0               # meters permanently rigged on first use
    need: str = ""              # flag required in state.flags
    deny: str = ""              # shown when `need` is missing
    once: str = ""              # extra prose, first traverse only
    once_after: str = ""        # the same, but after `travel` rather than before
    hazard: str = ""            # engine hook: 'collapse', 'dive', 'commit'
    unless: str = ""            # hidden once this flag is set
    when: str = ""              # hidden until this flag is set
    came_from: str = ""         # shown only if you walked in from this room


@dataclass
class Person:
    """Someone you can talk to. `beats` are consumed in order, one per ask."""
    name: str
    role: str
    beats: list                 # [(text, flag_granted_or_empty)]


@dataclass
class Clue:
    """Something you can go and look at properly. Costs you daylight."""
    label: str
    mins: int
    text: str
    flag: str = ""


@dataclass
class Pickup:
    """Something you can carry down, or decide not to.

    Costs no daylight — it is lying right there and the decision is the whole
    of it. Offered only once `needs` is set, so you have to have looked at the
    thing before you are asked to commit to it, and gone for good either way.
    """
    label: str                  # "the lens"
    needs: str                  # flag that has to be set before it is offered
    flag: str                   # flag set if you take it
    take: str
    leave: str


@dataclass
class Room:
    id: str
    name: str
    depth: int                  # meters below the sink lip
    look: tuple                 # (near, room, beyond)
    exits: list = field(default_factory=list)
    first: str = ""             # first visit only
    found: str = ""             # first visit only, when the beam cannot reach
                                # look[2]: the one thing `first` needs you to
                                # have seen, found by walking up to it
    tags: set = field(default_factory=set)   # badair, water, signal, roof,
                                             # quiet (no ambience; in the
                                             # park, L finds only silence),
                                             # gray (lit by the dawn)
    mx: int = 0                 # sidebar map grid
    my: int = 0
    people: list = field(default_factory=list)   # Act One only
    clues: list = field(default_factory=list)    # Act One only
    pickups: list = field(default_factory=list)  # Act One only
    look_if: dict = field(default_factory=dict)  # {flag: look} once it is set


# --------------------------------------------------------------------------
#  THE CAVE
# --------------------------------------------------------------------------

ROOMS = {

"sink": Room(
    id="sink", name="Wolf Sink", depth=0, mx=3, my=0,
    tags={"signal", "surface", "quiet"},
    look=(
        "The sink is a wound in the hillside. Limestone and root, collapsed "
        "in on itself under a stand of hemlock, ten minutes off the Piney "
        "Ridge trail and not on any of the park's public maps.",
        "You stand at its edge looking down. Cold air pours out of it "
        "steadily enough to move the ferns at the lip. September. The cave is "
        "breathing out, which means it is deep, and it means somewhere far "
        "under you there is at least one more way to the surface that nobody "
        "has found.",
        "Behind you the work lights make a hard white room out of forty feet "
        "of the trees followed by nothing at all for the rest of the ridge. "
        "Your shadow goes down into the hole ahead of you and does not come "
        "back out."
    ),
    first=(
        "Wren Alcott has been under this hill for forty-four hours.\n\n"
        "You do the checks the way you were taught, out loud, alone in the "
        "hemlocks. Primary lamp. Fresh battery. Sixty meters of rope. "
        "Radio.\n\n"
        "Then you sit on the lip and put your legs into the cold."
    ),
    exits=[
        Exit(label="Go in feet-first", to="letterbox", mins=3,
             travel="You go in feet-first and the temperature drops ten "
                    "degrees in the length of your own body."),
    ],
),

"letterbox": Room(
    id="letterbox", name="The Letterbox", depth=-4, mx=3, my=1,
    tags={"signal"},
    look=(
        "Forty meters of flat-out crawl, and nowhere in it can you lift your "
        "head. You go on your side with the pack pushed ahead, breathing "
        "against rock that is two inches from your face. A cave cricket "
        "picks its way across it, unhurried, feelers going.",
        "There are fresh drag marks in the silt, one set going in, and a handprint "
        "between them. You put your own hand beside it for scale and it is a "
        "smaller hand than yours.",
        ""
    ),
    first=(
        "Someone named this the Letterbox and then, presumably, went home and "
        "slept fine. They probably thought that was terribly funny and "
        "clever, too."
    ),
    exits=[
        # which way you are facing in a crawl you cannot turn around in
        # depends on which end you came in by
        Exit(label="Push on through the crawl", to="bell", mins=9,
             came_from="sink",
             travel="Nine minutes of shuffling on one hip. Your helmet "
                    "scrapes a groove in the ceiling the whole way, and the "
                    "sound of it runs on ahead of you into the dark, and "
                    "nothing sends it back."),
        Exit(label="Reverse out to the sink", to="sink", mins=9,
             came_from="sink",
             travel="You reverse out. It takes longer going backwards. "
                    "It always does."),
        Exit(label="Crawl out to the sink", to="sink", mins=9,
             came_from="bell",
             travel="Nine minutes of shuffling on one hip, head-first this "
                    "time, pushing the pack ahead of you toward the sink."),
        Exit(label="Reverse back to the Bell", to="bell", mins=9,
             came_from="bell",
             travel="You reverse out. It takes longer going backwards. "
                    "It always does."),
    ],
),

"bell": Room(
    id="bell", name="Bell Chamber", depth=-9, mx=3, my=2,
    tags={"signal"},
    look=(
        "You can stand.",
        "A bell-shaped void, six meters across, floored in cobble, its walls "
        "crowded with cave crickets at head height. Three ways to choose "
        "from. Someone has left a cairn of four stones by the western "
        "passage — recent, the top stone still pale where it was lifted. "
        "Wren marks her way in orange. Whoever built this did not.",
        "The ceiling goes up past the useful reach of your beam into a "
        "chimney that nobody has surveyed. Water comes down out of it, one "
        "drop at a time, and lands somewhere you can hear but not see."
    ),
    first=(
        "After the Letterbox, standing up feels like a gift, and you take a "
        "minute to give your ribs back to yourself.\n\n"
        "You call it in. Basecamp comes back clear and readable: they have "
        "you at the Bell, they have your time, they will hold the frequency."
        "\n\nThis is the last place in the cave where that is true."
    ),
    exits=[
        Exit(label="West — the stream passage", to="stream", mins=6,
             travel="You take the western way, past the cairn, and within "
                    "twenty meters you can hear water working."),
        Exit(label="East — the dry gallery", to="gallery", mins=6,
             travel="East. The floor goes to dust and the air goes dry and the "
                    "sound of your boots changes register."),
        Exit(label="Back into the Letterbox", to="letterbox", mins=2,
             travel="You get back down on your side and feed yourself into "
                    "the crawl."),
    ],
),

"stream": Room(
    id="stream", name="Stream Passage", depth=-14, mx=1, my=2,
    tags={"water"},
    look=(
        "Ankle-deep and moving. The cold comes through your boots in about "
        "ninety seconds and settles in for the duration. A salamander no "
        "longer than your finger holds still in the shallows until your "
        "light moves off it.",
        "A canyon passage, taller than it is wide, cut by this same water "
        "over a timescale nobody can wrap their heads around. Scallops in the "
        "wall all point the way the flow goes. Downstream is southwest. "
        "On the surface, downstream is the answer if you are lost; "
        "underground it only takes you deeper, and as an experienced "
        "caver, Wren knew that.",
        "There is a flood line on the wall at chest height. Old debris packed "
        "into a ledge — twigs, a shred of blue tarp, a bone that you decide "
        "is a deer's."
    ),
    exits=[
        Exit(label="Follow the water down", to="sump", mins=8,
             travel="You follow it down. The ceiling comes to meet the water "
                    "by degrees, politely, until politeness goes out the "
                    "window and you're hunching and crawling again."),
        Exit(label="Back up to the Bell", to="bell", mins=6,
             travel="Back upstream. Your own footprints have already "
                    "silted over."),
    ],
),

"sump": Room(
    id="sump", name="The Sump", depth=-19, mx=0, my=3,
    tags={"water"},
    look=(
        "The passage ends in water. Not a pool — a sump: the roof comes "
        "down and meets the surface and the cave carries on underneath it "
        "for an unknown distance.",
        "Perfectly still. Black, and so clear that your beam goes down it "
        "for four or five meters before it gives up, showing you clean rock "
        "and one boot-shaped disturbance in the silt at the very edge of "
        "what you can see.",
        "There is a dive line here. Blue polypropylene, knotted to a rock "
        "thread, going into the water and down. It is not park equipment, nor "
        "is it new. Nobody at basecamp mentioned a dive line."
    ),
    found=(
        "Your boot finds a line before your light does: blue polypropylene, "
        "knotted to a rock thread at the edge, going into the water and down."
    ),
    first=(
        "You crouch at the edge and put your hand in to the wrist and hold "
        "it there until it hurts, because knowing the temperature matters "
        "and because you want a reason not to look at the line."
    ),
    exits=[
        Exit(label="Follow the dive line under", to="drowned", mins=2,
             hazard="dive",
             travel="You take the line in your left hand."),
        Exit(label="Back upstream", to="stream", mins=8,
             travel="You back away from the water without turning around, "
                    "which you notice yourself doing, but do anyway."),
    ],
),

"gallery": Room(
    id="gallery", name="Dry Gallery", depth=-13, mx=5, my=2,
    look=(
        "Dust. This means no water has come through here in a very long time.",
        "Survey stations, old ones — aluminum tags hammered into the wall, "
        "stamped WS-11, WS-12. Someone surveyed this. None of it made it "
        "into the file.",
        "Orange flagging tape on a projection at the far end, tied in a "
        "bowline. Fresh. Wren's color. It marks the way on, and the way on "
        "is a hole in the floor."
    ),
    found=(
        "Right at the edge of your beam, down at the far end, a scrap of "
        "orange: flagging tape, Wren's color, marking a hole in the floor."
    ),
    exits=[
        Exit(label="On to the flagged hole", to="pitch_head", mins=5,
             travel="You walk the gallery. The dust is already trodden "
                    "into a path — the same small boots, in and out, trip "
                    "after trip — and on top of all of it, fresh, one set of "
                    "prints just beside yours, going the same way. None "
                    "coming back."),
        Exit(label="Back to the Bell", to="bell", mins=6,
             travel="Back west, into the sound of dripping."),
    ],
),

"pitch_head": Room(
    id="pitch_head", name="The Drop", depth=-16, mx=5, my=3,
    look=(
        "A hole in the floor of the gallery, a meter and a half across. "
        "You lie on your stomach and put your head over the edge.",
        "Twelve meters, free-hanging, into a chamber your beam cannot find "
        "the far side of. There are two good naturals for a rig — a waterworn "
        "thread in the rock and a solid flake you can throw a loop over — and "
        "a deviation you would want at about four meters that'll keep the "
        "rope off the wall.",
        "Wren's flagging goes over the lip and stops. There is no rope here, "
        "no anchor, no rub mark on either natural. Nobody downclimbs twelve "
        "meters of free hang. Either she fell down it, or she has been "
        "getting down it some other way."
    ),
    first=(
        "You try the radio. Basecamp is a shape in the static now rather than "
        "a voice. You give your position twice and get nothing back you would "
        "swear to in a report."
    ),
    exits=[
        Exit(label="Rig the rope and descend  (15 m)", to="pitch_bottom",
             mins=14, rope=15, hazard="commit",
             once="You rig it properly: thread, backup, deviation at four "
                  "meters, knot in the end. Then you weight it and step off "
                  "farther down into the unknown.",
             travel="Down the rope. Twelve meters of free hang, turning "
                    "slowly, your light swinging across walls that keep "
                    "not being where you left them."),
        Exit(label="Back into the gallery", to="gallery", mins=5,
             travel="You back off the lip."),
    ],
),

"pitch_bottom": Room(
    id="pitch_bottom", name="Foot of the Drop", depth=-28, mx=5, my=4,
    look=(
        "A floor of shattered plate, and the rope hanging down onto it, "
        "rigged. It's the only way you can get out of here.",
        "Bigger down here. The chamber runs off in two directions and the air "
        "moves through it, which is good — air movement is life — except that "
        "it is moving toward you from both directions at once — which is not "
        "how air works.",
        "Twenty-eight meters. There is more rock over your head now than "
        "most people stand under in a lifetime."
    ),
    first=(
        "You come off the rope, and you touch it once before you leave "
        "it.\n\n"
        "You mark the pitch foot with a reflective tag at knee height, "
        "because at the end of this you will be tired and the way out will "
        "look like every other hole in the wall.\n\n"
        "The crickets are gone. You did not see where they stopped. There "
        "is nothing living on these walls at all."
    ),
    exits=[
        Exit(label="West into the breakdown", to="breakdown", mins=7,
             travel="West, over blocks the size of cars, testing each one "
                    "before you trust it."),
        Exit(label="South — a low sallow passage", to="badair", mins=6,
             travel="South, and the passage lowers, and within a minute your "
                    "lamp flame — you don't have a flame, you have an LED — "
                    "and still something about the light goes yellow."),
        Exit(label="Climb the rope out", to="pitch_head", mins=16,
             travel="You get back on the rope and start the ascent, friction "
                    "hitches at work. Twelve meters takes sixteen minutes and "
                    "every one of them gets slower than the last."),
    ],
),

"breakdown": Room(
    id="breakdown", name="Breakdown", depth=-31, mx=3, my=4,
    look=(
        "A collapse. The ceiling came down here, once, all at once, long ago.",
        "You route through the gaps between blocks. Some of them are keyed in "
        "and some of them are balanced, and telling the difference is why "
        "you're here and not someone else.",
        "Something shifts, far back in the pile, and settles. Caves do this. "
        "The cave has always done this. You wait until your heart agrees."
    ),
    exits=[
        Exit(label="Pick a line through the blocks", to="pack", mins=11,
             hazard="collapse",
             travel="You take it slow, three points of contact, weight "
                    "committed only after the block has been asked twice."),
        Exit(label="A crawl going west", to="roost", mins=5,
             travel="A crawl, west, and the smell changes."),
        Exit(label="Back east to the pitch", to="pitch_bottom", mins=7,
             travel="Back east across the blocks."),
    ],
),

"roost": Room(
    id="roost", name="The Roost", depth=-33, mx=1, my=4,
    look=(
        "A domed side-chamber, and the floor of it is soft and deep and "
        "black. You know what guano is before your light finds the ceiling.",
        "Decades of it. Centuries. A colony lived here in numbers that "
        "would have made this room roar every dusk from April to October.",
        "The ceiling is empty. Not white-nose empty, not sick-and-dying empty "
        "— empty like it was swept. No bats. No bodies. No mites. Nothing has "
        "been in this room for a long time, and that there is no trace of "
        "anything but the guano tells you something else made sure of that."
    ),
    first=(
        "You stand in the middle of it with your light up and you count to "
        "thirty and nothing in the room moves except you.\n\n"
        "There is a spare lamp battery here, on a rock, set down neatly "
        "with its terminals up. It is the same model as yours. You put it "
        "in your chest pocket and you do not think about who set it down "
        "neatly, or when, or why they did not come back for it."
    ),
    exits=[
        Exit(label="Back to the breakdown", to="breakdown", mins=5,
             travel="You leave. You do not hurry, because hurrying would "
                    "mean admitting something."),
    ],
),

"badair": Room(
    id="badair", name="The Sallow", depth=-30, mx=5, my=5,
    tags={"badair"},
    look=(
        "The passage is a meter high and you are on hands and knees and the "
        "air here is wrong. Heavy. It sits in the low places the way water "
        "would.",
        "Carbon dioxide, pooled. Your breathing has gone deep and fast "
        "without asking you, and there is a band tightening behind your "
        "eyes. This is a bad-air pocket and the only cure for it is being "
        "somewhere else.",
        ""
    ),
    exits=[
        Exit(label="Push west, fast", to="pack", mins=5,
             travel="You go, and you go fast and low, and the headache "
                    "comes with you for a while after the air improves."),
        Exit(label="North to the pitch foot", to="pitch_bottom", mins=6,
             travel="You get yourself out of it, and the moment the air thins you sit "
                    "down hard and breathe like something landed."),
    ],
),

"pack": Room(
    id="pack", name="Wren's Cache", depth=-37, mx=3, my=5,
    look=(
        "A junction chamber, and in the middle of it, set down against a "
        "boulder, is a red forty-liter pack.",
        "Wren's. Her name is inked on the lid strap. It is packed and "
        "closed and upright. Nobody drops a pack this neatly in an "
        "emergency; you set a pack down like this when you intend to come "
        "straight back to it.",
        "Inside: dry bag, food for the day untouched, a first-aid kit "
        "unopened, and a handheld radio with the volume wheel turned "
        "all the way up."
    ),
    first=(
        "The radio in the pack is on. The battery should have died hours "
        "ago, but it is on, and it is putting out a flat carrier hiss with "
        "no station behind it.\n\n"
        "You key your own set and say Wren's name into it. The hiss in the "
        "pack changes shape for exactly as long as you are talking, and "
        "then goes back to being hiss."
    ),
    exits=[
        Exit(label="On, to a slot in the far wall", to="squeeze", mins=6,
             travel="There is a slot in the far wall, and there is fresh "
                    "scuffing on the lip of it at hip height."),
        Exit(label="North into the breakdown", to="breakdown", mins=11,
             travel="North, over the blocks."),
        Exit(label="East into the sallow air", to="badair", mins=5,
             travel="You take a breath in good air, and go into the "
                    "bad on purpose, which everything in you objects to."),
    ],
),

"squeeze": Room(
    id="squeeze", name="The Keyhole", depth=-41, mx=3, my=6,
    look=(
        "A vertical slot, hip-wide at the bottom and shoulder-wide at the "
        "top, and the only way through it is on your side with your arms "
        "over your head and nothing on your back.",
        "It is too tight for a pack. What goes through goes in your "
        "pockets, and everything else stays on this side of a hole you may "
        "not be able to reverse quickly.",
        "Air moves through it hard enough to whistle."
    ),
    first=(
        "This is the point in the callout where the honest thing to do is "
        "turn around, log the find, and come back with four people and a "
        "hauling system.\n\n"
        "The pack radio is still hissing behind you.\n\n"
        "It's time to go. You take your helmet off to fit."
    ),
    exits=[
        Exit(label="Strip the pack and go through", to="long_room", mins=12,
             hazard="commit",
             once="You set the pack down against the wall, closed and "
                  "upright, the way you set a pack down when you intend to "
                  "come straight back to it.",
             once_after="Halfway through, wedged, with the rock on your sternum "
                  "and on your spine at the same time, you exhale all the "
                  "way to make yourself smaller, and for four seconds you "
                  "cannot get the breath back.",
             travel="You go through sideways, in stages, with your lamp in "
                    "your teeth and nothing in its light but the next inch "
                    "of rock."),
        Exit(label="Back to the cache", to="pack", mins=6,
             travel="You go back to the cache, and the slot whistles behind "
                    "you."),
    ],
),

"long_room": Room(
    id="long_room", name="The Long Room", depth=-52, mx=3, my=7,
    look=(
        "Space. You can feel it before you "
        "see it — the sound of your own breathing goes away from you and "
        "does not come back for a full second.",
        "Your beam does not reach the far wall. It does not reach the "
        "ceiling. You are standing at the edge of a room the size of a "
        "cathedral, fifty-two meters under a national park, in a cave that "
        "has eleven pages of survey and no mention or inkling of this at all.",
        "The floor is flat. Not fallen-flat. Flat like a lakebed, and "
        "across it, going away from you into the dark, is a single line of "
        "footprints in the silt, and they are not going toward anything "
        "you can see."
    ),
    found=(
        "In the silt at your feet, a single line of footprints goes away from "
        "you into the dark."
    ),
    first=(
        "You shout Wren's name because that is the protocol.\n\n"
        "The echo comes back at four seconds, which is wrong for a room "
        "this size. And it comes back in your voice, saying your own name."
    ),
    exits=[
        Exit(label="Follow the footprints", to="deep", mins=15,
             travel="You follow them. They are Wren's size. Their stride does "
                    "not shorten, does not stumble, does not deviate. Whoever "
                    "walked this walked it calmly, like they knew exactly "
                    "where they were going. There is no widened stance for "
                    "balance, no hand-drag low on the wall where someone "
                    "would have left one."),
        Exit(label="East, along the wall", to="ladder", mins=9,
             travel="You keep your left hand on the wall and work east, "
                    "which is what you do in a room you cannot see the "
                    "shape of."),
        Exit(label="Back to the Keyhole", to="squeeze", mins=12,
             travel="You go back through the slot in the wall. Your pack is "
                    "where you left it."),
    ],
),

"ladder": Room(
    id="ladder", name="The Carbide Ladder", depth=-55, mx=5, my=7,
    look=(
        "A working. Human. Old.",
        "A ladder of iron rungs driven into the wall, going up into a rift, "
        "and on the rock beside it the black feathered smoke-marks that "
        "carbide lamps leave. Someone worked here for weeks to leave marks "
        "like that.",
        "Above the rungs, written in lamp-black in a careful hand: a date. "
        "1911. And below the date, in the same hand, the same black, not "
        "faded differently, not weathered differently: a second date, and "
        "it is this year."
    ),
    first=(
        "There is no shaft, no ore, no reason for a working here. The rungs "
        "go up nine meters into a rift and stop at solid rock.\n\n"
        "You take a photograph, because the report will need it and because "
        "holding the camera up gives your hands something to do.\n\n"
        "There is a spare battery wedged behind the third rung. Modern. It "
        "fits your lamp. You take it and feel like a thief, but you take it anyway."
    ),
    exits=[
        Exit(label="Back into the Long Room", to="long_room", mins=9,
             travel="Back along the wall, right hand trailing, west."),
    ],
),

"deep": Room(
    id="deep", name="—", depth=-61, mx=3, my=8,
    look=(
        "The footprints stop.",
        "They do not turn around. They do not scuff or scatter. They walk "
        "ten paces into an open flat floor and they stop, and after that "
        "there is only clean silt for as far as your light reaches.",
        "And sitting on the silt at the end of them, folded neatly, is "
        "Wren Alcott's oversuit, and her helmet on top of it, and the "
        "helmet lamp is still on."
    ),
    look_if={"took_find": (
        "The footprints stop.",
        "They do not turn around. They do not scuff or scatter. They walk "
        "ten paces into an open flat floor and they stop, and after that "
        "there is only clean silt for as far as your light reaches.",
        "And sitting on the silt at the end of them, folded neatly, is "
        "Wren Alcott's oversuit, with a round dent in the top of it where "
        "her helmet sat until you took it."
    )},
    found=(
        "Out at the end of them, past where your beam reaches, something is "
        "giving off its own light. It is Wren Alcott's helmet lamp, still on, "
        "sitting on top of her oversuit, which is folded neatly on the silt."
    ),
    first=(
        "You are sixty-one meters down.\n\n"
        "You kneel by the suit. It is dry. It has been dry for a long time "
        "in a cave where nothing is dry, and it is warm, the way clothes "
        "are warm when someone has just taken them off.\n\n"
        "The helmet lamp has been burning for forty-five hours on a "
        "battery rated for eight.\n\n"
        "Behind you, from the direction you came, at a distance you could "
        "walk in ninety seconds, someone says your name.\n\n"
        "It is not Wren's voice. It is not a conversational voice. It is "
        "the voice you use when you are alone and reading directions out "
        "loud."
    ),
    exits=[
        Exit(label="Take the helmet and get out. Now.", to="long_room",
             mins=15, hazard="took_find", unless="took_find",
             travel="You take the helmet. You do not turn your back on the "
                    "dark to do it — you back away with your light up, all "
                    "the way, until the wall finds your shoulder."),
        Exit(label="Back along the footprints", to="long_room", mins=15,
             when="took_find",
             travel="You go back along the footprints. Yours are over hers "
                    "now, the whole way."),
        Exit(label="Answer it", to="stay", mins=1, hazard="answer",
             travel="You turn around, and you put your light on it, and "
                    "you say: \"I'm here.\""),
        Exit(label="Go the way the suit was facing", to="nest", mins=12,
             unless="took_find",
             travel="The suit is folded, and the folded suit seems to point "
                    "somewhere. The collar is turned toward a low seam in "
                    "the west wall that you had taken for shadow, and the "
                    "silt in front of it is smooth like a threshold.\n\n"
                    "You go in on your belly with your light held out in "
                    "front of your face, and for the next few minutes, the "
                    "only thing you can think about is that this is how she "
                    "went, and that she went without her suit.",
             once_after="You are not following procedure anymore. You know that. "
                  "You log the time out of habit... the habit is the only "
                  "part of you still behaving like a rescue."),
    ],
),

# ----- the nest -------------------------------------------------------------

"nest": Room(
    id="nest", name="—", depth=-66, mx=2, my=9,
    look=(
        "Bone. Not a pile — a floor. Worked flat and worked smooth and gone "
        "the color of old soap. Clearly not new.",
        "The chamber is warm. Sixty-six meters down in a cave that runs at "
        "fifty-two degrees, and it is warm, and the air moves across your face "
        "from somewhere ahead and to the left, coming down.",
        "And on the far side of it, a dozen meters off, sitting upright against "
        "the wall with her knees drawn up, is Wren Alcott. Her eyes are "
        "open. She has been looking at the seam you came out of since "
        "before your light reached it."
    ),
    found=(
        "Across the chamber, at the very edge of what your beam can do, "
        "somebody is sitting upright against the wall with her knees drawn "
        "up. Wren Alcott. Her eyes are open."
    ),
    first=(
        "She says your name.\n\n"
        "Not the way the dark said it. She has only ever heard it in the "
        "dark's voice, through the rock, and she says it back the way a "
        "person does, carefully, and she gets it slightly wrong, and that "
        "small wrongness is the first thing in twenty-two "
        "hours that has been unambiguously good.\n\n"
        "\"Don't put the light on it,\" she says. \"Not yet. It's been "
        "asleep about an hour and I've been counting.\"\n\n"
        "You do not ask what. There is a shape between you and her that "
        "your beam goes into and does not come out of, and it is not "
        "rock, and your light has been on it for four seconds already."
    ),
    exits=[
        Exit(label="Put the lamp through the lens", to="adit", mins=25,
             need="lens", deny="you have nothing to do it with",
             when="clue:lens", hazard="burn"),
        Exit(label="Take her and run for it", to="adit", mins=25,
             hazard="unarmed",
             travel="You cross the floor and get a hand under her arm and "
                    "she is lighter than a person should be."),
        Exit(label="Back into the seam, alone", to="deep", mins=12,
             travel="She does not call after you. Whatever else happens "
                    "tonight, you will think about that for a long time."),
    ],
),

"adit": Room(
    id="adit", name="The Old Workings", depth=-18, mx=4, my=9,
    look=(
        "Cut timber. Square-set, adzed, propped by somebody who meant it to "
        "hold and who has been dead for a hundred years.",
        "A mine tunnel, driven by hand into the hill and abandoned before it "
        "found anything. There is a rail, and a hand-drill scar every "
        "eighteen inches, and the black feathered smoke of carbide lamps on "
        "the back of every set.",
        "And at the top of it, past the choke, cold air coming in off the "
        "hill. The gray comes from there, when it comes — thin as a "
        "blade, and nothing you could see by."
    ),
    first=(
        "You followed the air up. It had been moving across your face the "
        "whole time you were in the nest, and you did not know until you "
        "were moving that it was telling you where to go — the seam "
        "behind the bone floor narrowing almost at once into a chimney, "
        "tight and wet in patches, climbed with her weight added to yours "
        "and every hold tested before you trusted it, for what felt like "
        "longer than the twenty-five minutes it actually took.\n\n"
        "This is the second way to the surface. It has been here the whole "
        "time, and it is why the cave breathes, and the people who cut it "
        "walked out of it in 1911 and closed it behind them with forty tons "
        "of hillside and did not write down why.\n\n"
        "Wren is on your shoulder and she is talking, low and continuous, and "
        "none of it is for you. She is counting.\n\n"
        "The way out is fifteen meters up through a choke that two people can "
        "just about get through if one of them goes first and does not stop "
        "to think about the other one."
    ),
    exits=[
        Exit(label="Up, into the gray", to="choke", mins=9, hazard="climb_out",
             travel="You go first because you have the light and she goes "
                    "second because she has nothing left, and twice she "
                    "stops and twice she starts again without being asked."),
    ],
),

# ----- the choke -------------------------------------------------------------
# Only reached with the lens and without `bolted` — otherwise `climb_out`
# resolves straight to RESCUE_HARD and this room never gets entered.

"choke": Room(
    id="choke", name="—", depth=-9, mx=5, my=9, tags={"quiet", "gray"},
    look=("", "", ""),
    first=(
        "Fifteen meters of broken rock at forty degrees, and something in "
        "it with you.\n\n"
        "You can hear it in the rock — not a voice or a call, the scrape "
        "of scree taking its weight — and it is closing a distance the two "
        "of you cannot close any faster.\n\n"
        "Where the choke opens there is a hand's width of gray. Not "
        "lamplight. The mountain's own, leaking in for a hundred years, "
        "thin and cold, the color of nothing.\n\n"
        "You take the lens out again. You have been carrying it since a "
        "folding table under the work lights, and not long ago, back where "
        "it was sleeping, it bought you nothing but a few feet of room. "
        "In real light, it does more than that.\n\n"
        "You hold it in the gray. The light goes through it and lands on "
        "the dark behind Wren's shoulder as a point the size of a match "
        "head. It lands on something pale that moves. The point "
        "flares white — almost hot — and for the first time, the thing in "
        "the cave makes a sound that is unmistakably its own.\n\n"
        "It isn't a mouth-sound, and it doesn't land in your ears. It "
        "lands behind your eyes in that instant, at the exact pitch of "
        "the worst thing you have ever thought alone in the dark, and for "
        "one second you know it heard you think it. It knows. It wants "
        "more.\n\n"
        "It comes apart from the light. Not away — apart."
    ),
    exits=[
        Exit(label="Turn for the gray. Now.", to="grip", mins=1),
        Exit(label="Hold the point on it to buy Wren time.", to="resolved",
             mins=2,
             hazard="rescue_watch"),
    ],
),

# ----- the grip --------------------------------------------------------------
# A held breath inside RESCUE_INJURED: the moment it takes your hand, then one
# forced action before the epilogue. Quiet — no ambience rolls here.

"grip": Room(
    id="grip", name="—", depth=-9, mx=5, my=9,
    tags={"quiet", "offmap", "gray"},
    look=("", "", ""),
    first=(
        "You do not wait to see where it goes. You are already turning for "
        "the gray, the lens still full of it and throwing wild white across the "
        "rock, when something closes the last of the distance on your blind "
        "side.\n\n"
        "It has your left hand for perhaps half a second. That is the whole "
        "of it — a grip, and then, deliberately, a release, the way you "
        "would set something down. Except it does not let go clean. "
        "It leaves something behind that never shows up on your glove — "
        "small, and cold, and it does not stay in your hand. You are through the "
        "choke on your good hand and both knees before you understand you "
        "are hurt, and hurt turns out to be the wrong word for one of the "
        "two things that just happened to you. It will be years before you "
        "find a better word for it."
    ),
    exits=[
        Exit(label="GET OUT", to="resolved", mins=0, hazard="rescue_now"),
    ],
),

# ----- terminal rooms -------------------------------------------------------

"drowned": Room(
    id="drowned", name="Under", depth=-24, mx=0, my=3, tags={"offmap"},
    look=("", "", ""),
),

"stay": Room(
    id="stay", name="—", depth=-61, mx=3, my=8, tags={"offmap"},
    look=("", "", ""),
),

"resolved": Room(
    id="resolved", name="—", depth=-9, mx=5, my=9, tags={"offmap"},
    look=("", "", ""),
),
}


# --------------------------------------------------------------------------
#  AMBIENCE — one may fire on any move. Keyed by dread band.
# --------------------------------------------------------------------------

AMBIENCE = {
    0: [
        "Water, somewhere, on a two-second interval.",
        "Your own breathing, coming back off a wall you can't see.",
        "The rock ticks as it takes your heat.",
        "Far off, the hollow knock of a drop into standing water.",
    ],
    1: [
        "A stone turns over, back the way you came. Nothing follows it.",
        "The airflow reverses for a moment, then settles.",
        "A sound like fabric drawn over rock. It stops when you stop.",
        "Your light finds a wall much closer than it was a second ago.",
        "Somewhere above, a sound like a boot set down carefully.",
    ],
    2: [
        "Breathing. Not yours. It is matching yours, one beat late.",
        "A radio, very faint, playing nothing.",
        "Something says half a word and thinks better of it.",
        "The drips stop. All of them. For nine seconds.",
        "Your name, at conversational volume, from the direction of the exit.",
        "A dim light passes across the far wall. You have not moved your head.",
    ],
}

# Lines that would give a beat away before it lands: {line: the room you have
# to have stood in first}. Deep is where it first says your name.
AMBIENCE_AFTER = {
    "Your name, at conversational volume, from the direction of the exit.":
        "deep",
}

# When you LISTEN deep in, the cave gives you back your own past.
ECHO_FRAME = [
    "Behind you, at a distance, {} — and you have not moved in minutes.",
    "From the way out, clearly: {}.",
    "You hear, arriving late and from the wrong direction, {}.",
    "{} — again. Same rhythm. Same stumble in the middle of it.",
]

ECHO_ACTS = {
    "sink": "the sound of someone sitting down on wet leaves",
    "letterbox": "a helmet dragging on a groove along a low ceiling",
    "bell": "boots on cobble, then a pause, then they lazily resume",
    "stream": "someone walking in ankle-deep water, unhurried",
    "sump": "a hand put into still water and held there",
    "gallery": "footsteps in dust, and the small sound of tape being touched",
    "pitch_head": "a rope being pulled through a descender",
    "pitch_bottom": "someone landing on a broken slab, then standing still",
    "breakdown": "a block tested, twice, and then trusted",
    "roost": "a person counting to thirty under their breath",
    "badair": "breathing, deep and fast, that will not slow down",
    "pack": "a radio being keyed, and a name said into it",
    "squeeze": "a long exhale, and then nothing at all for four seconds",
    "long_room": "a shout, and then a four-second wait",
    "ladder": "a camera shutter",
    "deep": "someone kneeling down in silt",
}

# When you LISTEN and get nothing. Nothing the cave says comes twice, and
# sometimes it says nothing at all.
LISTEN_QUIET = ("You hold your breath and listen, and the cave gives you "
                "nothing back.")


# --------------------------------------------------------------------------
#  RADIO — basecamp, by depth. Degrades. Then it doesn't degrade correctly.
# --------------------------------------------------------------------------

RADIO = {
    "clear": [
        "BASECAMP: Copy your position. We have you logged. Wind's picking "
        "up out here but the sky's clean. Nothing to worry about.",
        "BASECAMP: Copy. Sheriff's put a surface team on standby at the "
        "trailhead. They can't come down to you, but they're there. Take "
        "your time and take it safe.",
        "BASECAMP: Copy, copy. Family is still here. I'm not putting "
        "them on the radio. Go do your job.",
    ],
    "weak": [
        "BASECAMP: ...copy your... say again your dep—  ...ave you at...",
        "BASECAMP: ...old the frequency. We're not going... —where. Say "
        "again when you c...",
        "BASECAMP: ...ing you every fifteen. If we lose you for an hour "
        "we're call... ...you hear that? Acknow—",
    ],
    "gone": [
        "Carrier hiss. Under it, at the edge of hearing, a rhythm that is "
        "almost a voice, and it has the cadence of your own callsign, and "
        "it is not saying your callsign.",
        "Nothing. You hold the key down for ten seconds and say your "
        "position into an open channel and hear, faintly, a second key "
        "click open somewhere, and close again.",
        "BASECAMP, clear as a bell, no static at all, through solid "
        "limestone: \"Giving it one more try — you there? We've got Wren. "
        "She's here — walked out an hour ago. Heard someone else on the "
        "radio. Who's down there with you?\"",
        "Your own voice, from earlier tonight, giving your position at the "
        "Bell Chamber. Word for word. Including the part where you cleared "
        "your throat.",
    ],
    # Act One: you are on the ridge and basecamp is up at the sink
    "park": [
        "BASECAMP: Copy your position. We're set up at the sink, generator's "
        "running. We'll see you when we see you.",
        "BASECAMP: Copy. We have you. Talk to whoever you need to talk to on "
        "the way — we're not going anywhere.",
        "BASECAMP: Copy, copy. Family's up here with us. Just so you know "
        "that before you walk in.",
    ],
    # Act One, once you have been up to basecamp and walked back out of it
    "park_back": [
        "BASECAMP: Copy your position. Generator's still running. We'll see "
        "you when we see you.",
        "BASECAMP: Copy. We have you. Get what you need out there — the "
        "hole's not going anywhere.",
        "BASECAMP: Copy, copy. Family's still up here. The mother hasn't "
        "moved.",
    ],
}

# Act One, keying the set while you are standing at basecamp
RADIO_AT_BASECAMP = ("Basecamp is the folding table in front of you. You put "
                     "the set away.")

# Act Two, keying the set before you have left the lip of the sink
RADIO_AT_SINK = ("Basecamp is a dozen yards behind you, under the work "
                 "lights. Somebody at the table lifts a hand. You put the "
                 "set away.")


# --------------------------------------------------------------------------
#  ACT ONE — THE PARK
#
#  Dusk, six hours before you go underground. No lamp yet; the budget you
#  are spending is daylight, which teaches the mechanic the cave will later
#  charge you for. Nothing here can kill you. That is the point of it.
# --------------------------------------------------------------------------

PARK = {

"trailhead": Room(
    id="trailhead", name="Piney Ridge Trailhead", depth=0, mx=0, my=0,
    tags={"surface", "park", "signal"},
    look=(
        "The pull-off has room for six vehicles, four "
        "already here. The day's nearly at an end, and the air smells like "
        "hot brake dust and somebody's coffee going cold on a tailgate.",
        "A silver Subaru hatchback sits at the far end under the mix of pine, "
        "oak, and hemlock, and it has apparently been sitting there since "
        "yesterday morning. You see a park notice tucked under the wiper... "
        "and you also know that it's basically the smallest and most official "
        "way of saying \"We noticed but didn't do anything.\"",
        "The ridge goes up behind the lot and keeps going. Nearly 2,000 feet "
        "of it, hemlock over hardwood — mostly oak. The light on it is the "
        "color of a struck match, and it's running out fast."
    ),
    first=(
        "Wren Alcott. Twenty-six. Solo... which is the whole problem.\n\n"
        "Nineteen hours overdue on a permit that says Wolf Sink, and Wolf "
        "Sink is a name that made three old-timers at the ranger station go "
        "quiet when you read it aloud.\n\n"
        "You have until dark to walk the approach by daylight and talk to "
        "whoever saw her last. You know that "
        "you essentially only have a few hours until this stops being a "
        "rescue and starts being a recovery. Time to go."
    ),
    people=[
        Person("Ranger Dolan Pace", "park law enforcement", [
            ("\"Dolan Pace — took the call.\" He shakes your hand like it is "
             "a thing he has decided to do rather than something he does out "
             "of habit. \"Vehicle's been here since yesterday 0600. Permit's "
             "in the self-issue box by the lot. Everything by the "
             "book... well... until it wasn't, I guess.\"",
             ""),
            ("\"Weird thing is how she even knew about it. Wolf Sink is a "
             "pretty deep cut, so to speak. It isn't on the public map... "
             "you'd only find it if you were looking at the actual physical "
             "survey of this place — or some local walked you down the old path. "
             "There's eleven pages on it from the '73 survey sitting in a drawer in "
             "Blakely and that's the only file on it. Only reason I can even "
             "stamp a permit for it at all is there's a standing clearance "
             "from the district's cave specialist — some list of names of "
             "experienced cavers he keeps that never crosses my desk. I just "
             "take the slip and drop it in the box like it's any other "
             "trail.\" He looks up the ridge. \"Been here nine years and "
             "never been down it. Just walk by it on occasion. The idea of "
             "spelunking half-mapped caves gives me the heebie-jeebies. "
             "Half-mapped caves with a body count? Forget it.\"",
             ""),
            ("\"Real talk? We've had three gone in that hole. 1911, '68, and "
             "now — at least on the books,\" he says flatly, how you say a "
             "thing you have already decided not to have an opinion about. "
             "\"The Missing Persons board outside the station already has two "
             "names on it, and they asked me to take it down so people don't "
             "potentially see us adding a third. I haven't. You'll want to take the "
             "witness's statement — what do you think — car, witness, or "
             "straight up to the sink?\"",
             "clue:board"),
        ]),
    ],
    clues=[
        Clue("The silver hatchback", 3,
             "Unlocked. Junie — Wren's partner — has had a key to this car "
             "for seven years, and according to the call you got before you "
             "showed up, she was standing here at 04:00, hours before she "
             "called anyone and anybody thought to call you.\n\n"
             "Inside: a change of clothes folded on the passenger seat, a "
             "receipt from a gas station in Blakely timestamped 05:41 "
             "yesterday, and, in the door pocket, a second permit — same "
             "hand, same box ticked, dated three weeks ago. In the back, a "
             "half-used reel of orange flagging tape.\n\n"
             "Wren has been here before. More than once.\n\n"
             "A note from Trammell on the seat — \"Girlfriend found "
             "something in the door pocket. Took it up to the sink with "
             "me.\" Strange. Whatever it was, it did not fit a normal "
             "missing-person case, or it would still be in the door "
             "pocket.",
             "clue:car"),
        Clue("The permit register", 3,
             "A steel box on a post with a slot in the top and a pad of "
             "carbon forms. You thumb back through the copies.\n\n"
             "Wren's is on top, yesterday, 06:10, WOLF SINK printed in small "
             "square capital letters.\n\n"
             "Three weeks back, in the same hand, the same box. Then six "
             "weeks back, and ten, and fourteen. May. April. And March... "
             "and March again. Nine entries for "
             "Wolf Sink in seven months and every one of them solo. None with "
             "a logged exit time.",
             "clue:register"),
    ],
    exits=[
        Exit(label="Take the trail up the ridge", to="ridge_trail", mins=6,
             travel="You go up. The grade is honest for the first few minutes "
                    "and then it stops being honest, making your legs burn "
                    "more than you feel they should."),
    ],
),

"ridge_trail": Room(
    id="ridge_trail", name="The Ridge Trail", depth=0, mx=1, my=0,
    tags={"surface", "park", "signal"},
    look=(
        "Packed dirt and root, two feet wide, switchbacking up through "
        "rhododendron, laurel, and ferns, closed over by the pine and "
        "hemlock to the point of almost being a tunnel before they lose their "
        "grip farther up the ridge.",
        "A junction. The maintained trail goes left along the contour "
        "toward the overlook. A second path goes right and downhill and is "
        "not a trail at all — it is a use path, worn in by people who all "
        "wanted to go to the same unmarked place.",
        "From the turn you can see most of the drainage. Hemlock, and then "
        "a wide scar of standing dead timber about a half mile north where "
        "something came through, and past that nothing but ridge."
    ),
    people=[
        Person("Ivy Crenshaw", "trail runner, waiting to give a statement", [
            ("She is sitting on a rock with a foil blanket she does not need "
             "around her shoulders. Somebody handed it to her and she did not "
             "know how to refuse it.\n\n"
             "\"I already told the ranger. I ran past her — I run this ridge "
             "three or four times a week, two to four loops depending where I "
             "am in my workout regime. Anyway, sorry — yesterday, early, "
             "before it was properly light. Not that I couldn't see her — "
             "just — anyway — sorry. What was I saying...\"",
             ""),
            ("You reassure her and ask her to continue.\n\n"
             "\"She was going down the use path with a pack on. I said "
             "morning and she said morning back.\" She stops. \"That's the "
             "part I keep going over, because she said it like — like she was "
             "being polite to somebody she'd already said it to. Like she'd "
             "already said good morning to me a couple of times — really "
             "weird. You know that sort of awkwardness you might have at "
             "school or the office when you see someone again you weren't "
             "expecting to see again? You don't want to say good morning "
             "again, but you kind of do again shyly, like 'Well, this is "
             "awkward,' and you kind of look around so you don't have too "
             "much eye contact.\" You do. You know that feeling and that "
             "look.",
             "clue:ivy"),
            ("\"There wasn't anyone else on the path. I'd have passed them on "
             "my first loop. It's a mile of switchbacks and there's nowhere "
             "to step off it.\"\n\n"
             "She pulls the blanket tighter, but not because she is cold.\n\n"
             "\"I ran the rest of it faster than I meant to. I couldn't tell "
             "you why. There weren't any birds. It was dead quiet... like "
             "someone held down the button on the remote to get it quiet real "
             "fast. Not instant, but it wasn't natural.\"",
             ""),
        ]),
    ],
    clues=[
        Clue("The use path", 2,
             "Twenty years of boots, minimum. This is not a route somebody "
             "found last spring — it is a route the ground has agreed to "
             "after decades of being trodden on.\n\n"
             "You're not a fantastic tracker or anything like that, but you "
             "can read this much. Running shoes all over the junction — "
             "Ivy's, you guess — and none of them turn down. On the use path "
             "itself, the fresh tread on top of all of it is one set. "
             "Vibram, size seven or eight, you guess. Going down. Nothing "
             "coming back up.",
             "clue:path"),
        Clue("The junction sign", 2,
             "Brown fiberglass, routed lettering, park standard. OVERLOOK "
             "1.4 with an arrow to the left.\n\n"
             "There is no arrow to the right. There is a rectangle of "
             "slightly darker fiberglass where a second panel used to be "
             "bolted on, and two empty holes, and the holes have been "
             "filled with silicone by somebody who did not want a third "
             "panel going up.",
             ""),
    ],
    exits=[
        Exit(label="Right — down the use path", to="blowdown", mins=7,
             travel="You take the use path down. Within a hundred yards the "
                    "rhododendron closes and the trail noise stops, almost "
                    "all at once, the way sound stops when a door is being "
                    "quickly but quietly shut."),
        Exit(label="Left — follow the flagging to the sink", to="basecamp",
             mins=8,
             travel="You go left along the contour and follow the flagging tape "
                    "somebody has already run in for you."),
        Exit(label="Back down to the trailhead", to="trailhead", mins=6,
             travel="Back down. It goes faster than it came."),
    ],
),

"blowdown": Room(
    id="blowdown", name="The Blowdown", depth=0, mx=2, my=1,
    tags={"surface", "park", "quiet"},
    look=(
        "Standing dead timber, forty acres of it. Hemlock, gray, "
        "still upright — which is wrong. Blowdown falls. This did not fall.",
        "It died standing and it died all together. No fire scar, no beetle "
        "galleries under the bark you peeled back when you were here last to "
        "investigate, no wind-throw, no root plates up in the air. Forty "
        "acres of trees simply stopped, on some particular day years ago "
        "before you ever got here, and they have all been standing here "
        "since... holding the shape of what they used to be.",
        "The ground under it is bare. Not thin — bare. Nothing has colonized "
        "forty acres of full sun in however many years, and the seedlings "
        "stop at the edge of it in a line you could follow with your finger."
    ),
    first=(
        "You stop in the middle of it and do the thing you were taught to do "
        "in ground you don't trust, which is stand still for one full minute and "
        "let the place tell you what is in it. Even though you've been here "
        "on occasion over the years, you hope that it speaks to you and tells "
        "you a different story this time.\n\n"
        "It takes about fifteen seconds to work out what is wrong.\n\n"
        "There is no sound. Not quiet or muffled. Silent. No birds, no "
        "squirrel scold, no insect, no wind in forty acres of dead standing "
        "timber that ought to be clacking like a xylophone. It's always been "
        "relatively quiet here, but now... now you can hear the blood in your "
        "own ear. The ticking of your quartz field watch. Every single rustle "
        "of your clothing."
    ),
    clues=[
        Clue("The silence", 3,
             "You get the recorder out of your chest pocket and hold it up "
             "and let it run for thirty seconds, because a thing you cannot "
             "explain is a thing you document. After thirty seconds of "
             "standing in the absolute nothing, the loud click of the button "
             "to stop recording goes off like a gunshot before you put it "
             "away and move on.\n\n"
             "Later — if there is a later — you will play it back in a "
             "motel room in Blakely and hear nothing, and then, at "
             "twenty-six seconds, very far away yet very clear, a sound like the thud of "
             "a large door being pulled to.",
             "clue:silence"),
        Clue("A whitetail doe, dead", 3,
             "Three weeks gone, maybe four. It is lying on its side in the "
             "open with its legs out straight.\n\n"
             "Nothing has been at it. No coyote, no vulture, no beetle, no "
             "fly. In four weeks in September, in these mountains, a deer on "
             "the ground should be down to hide and bone within just a few "
             "days. This one hasn't been touched at all.\n\n"
             "The head is pointed downhill. So are the other two you find "
             "without looking very hard. All three are pointed downhill, at "
             "the same thing, and you already know what is downhill of here.",
             "clue:deer"),
        Clue("Blazes on the dead trees", 4,
             "Old ones. Cut with a hatchet, not painted — a hand's width of "
             "bark taken off and the wood beneath gone silver.\n\n"
             "They are chest height on a person shorter than you and they are "
             "spaced for somebody walking a line in the dark. The silver "
             "blazes are on dead trees, but the bark has rolled in over the "
             "edges of every cut, the way it only does on a living tree, which "
             "means they were cut before the trees died... older than forty acres of impossible standing "
             "timber.\n\n"
             "They go downhill in a straight line. Down to Wolf Sink and then "
             "somebody else, later, spent the effort in taking the sign off a "
             "junction. Before, you figured — small town, underfunded parks "
             "department, little-visited area — nobody really cares to "
             "document things, preferring to just inherit a system rather "
             "than map it or learn why something is the way it is. Now that "
             "you're here in stranger times, something is definitely off. "
             "Sweat trickles, but not because it's hot in September.",
             "clue:blaze"),
    ],
    exits=[
        Exit(label="Follow the blazes down", to="hollow", mins=8,
             travel="You follow them down. It is easy walking, which is "
                    "its own kind of wrong — forty acres of dead timber and "
                    "not one stem across your path."),
        Exit(label="Back up to the trail", to="ridge_trail", mins=7,
             travel="Back up out of it. The birds start again about ten "
                    "yards past the seedling line. You notice exactly where."),
    ],
),

"hollow": Room(
    id="hollow", name="Sander's Hollow", depth=0, mx=3, my=2,
    tags={"surface", "park"},
    look=(
        "A bowl in the hillside, an acre of it, wet at the bottom. The last "
        "of the light does not come down in here at all — it goes over the "
        "top, and you are standing in the dark part of the evening about "
        "forty minutes before anybody else is.",
        "Somebody lived here. There is a chimney fall, a rectangle of "
        "foundation stone under the leaf litter, and the collapsed square "
        "of a springhouse over a run of water that still works.",
        "And apple — two apple trees, gone wild and barely holding on in the "
        "shade, which nobody plants by accident. This was a place with a "
        "family in it, half a mile from the sink, not on the park "
        "map, either."
    ),
    first=(
        "You make a note of the homestead, and regret not asking more "
        "questions at the station."
    ),
    clues=[
        Clue("The chimney fall", 3,
             "Dry-laid fieldstone, and a single dressed lintel, cut properly "
             "with a chisel, with the date 1889.\n\n"
             "Under it, in a different hand and a shallower cut, somebody "
             "scratched a second date the way you would scratch it with a "
             "nail, in a hurry, not meaning it to last: 1911.",
             "clue:1911"),
        Clue("The springhouse", 3,
             "The water still comes out from the earth cold enough to hurt. "
             "You put two fingers in it out of habit.\n\n"
             "The resurgence goes about eight feet and then goes back into "
             "the ground, back to whatever river it came from, and the hole "
             "it goes into has been closed with a course of the same "
             "fieldstone, mortared, by somebody who came back here with a "
             "bucket of mortar a long time after the house fell in.\n\n"
             "You do not close a spring. A spring is the reason you build "
             "where you build. You close the hole it drains into when you have stopped "
             "caring where the water goes and started caring what comes up "
             "out of it. Futile. Water will always find its way back down.",
             "clue:spring"),
        Clue("The cemetery", 4,
             "Thirteen stones on the rise above the house, field-cut, most of "
             "them illegible. The ones you can read are from the 1890s.\n\n"
             "Four of them are small. The sad truth of lives lived out up "
             "here.\n\n"
             "The last one is not from the 1890s. It is newer, and it is set apart "
             "from the others by a good twenty feet, and it faces the "
             "opposite way — every stone on this rise faces the house except "
             "this one, which faces downhill, toward the sink. There is no "
             "name on it. There is a date, 1911, and above the date somebody "
             "has cut, very carefully, the word HERE.",
             "clue:here"),
    ],
    exits=[
        Exit(label="Down the last of it to the sink", to="basecamp", mins=9,
             travel="You come out of the hollow onto a bench of level ground, "
                    "and there are lights on it, and voices, and the ordinary "
                    "and also completely out-of-place sound of people at "
                    "work."),
        Exit(label="Up through the dead timber", to="blowdown", mins=8,
             travel="Up. You go faster than the ground requires."),
    ],
),

"basecamp": Room(
    id="basecamp", name="Wolf Sink — Basecamp", depth=0, mx=4, my=3,
    tags={"surface", "park", "signal"},
    look=(
        "At the sink there are two vehicles that should not have "
        "been able to get up here, a generator running a string of work "
        "lights, and a folding table with a map on it held down at the "
        "corners by rocks.",
        "Too many people. Two of them are in oversuits, silent, and are not "
        "going anywhere until somebody tells them to. The rest are standing "
        "or sitting around the table being as useful as they can be while "
        "examining a map that does not show the one thing they need it to.",
        "And there — a dozen yards off — at the edge of the light, the ground "
        "opens up under a stand of hemlock. Cold air comes out of it "
        "steadily, now and then strong enough to quietly stir the "
        "leaves of the ferns at the lip."
    ),
    first=(
        "The generator makes it possible to pretend this is an operation with "
        "a floor under it.\n\n"
        "Nobody is going down that hole tonight except you. The reason a "
        "state SAR office came in rather than someone 'in-house.' There is "
        "one person on this ridge with a current cave rescue ticket who also has a "
        "vertical qualification, and you have been that person since this "
        "morning when somebody in Blakely made the call."
    ),
    people=[
        Person("Beau Trammell", "SAR team lead", [
            ("\"Evening. Trammell — don't know if you remember me. I've got "
             "the surface.\" He does not waste your time. \"There's a survey "
             "you can check out — eleven pages from 1973 — surveyor's note "
             "says it's incomplete. Rigging's on you. You've got sixty "
             "meters, a fresh battery, and the set. If you find flagging down "
             "there, orange is hers — off a reel in the hatchback. Only color "
             "we can tie to her for certain.\"",
             "brief"),
            ("\"Comms is going to be garbage. We'll hold the frequency and "
             "we'll take whatever we get.\" He taps the map twice, on "
             "nothing. \"Turnaround is 0600. If I haven't heard you by then I "
             "call Blakely and Blakely calls the state. From then it's a "
             "recovery and nobody's going down after you for at least a few "
             "days. Nutty Putty was mapped end to end, and they still couldn't "
             "get that man out. This one's half-mapped and unknown. You're "
             "the outside specialist — if you get lost, you're on your own "
             "for a while. Our one technical "
             "team is four hours away on another rescue job.\"",
             ""),
            ("\"One more thing — then I'll leave you alone.\"\n\n"
             "He waits until the two in oversuits have gone back to the "
             "table.\n\n"
             "\"1968, the one before this. They brought him out alive on day "
             "four and he was fine — dehydrated and hypothermic, but "
             "otherwise fine. Gave a clean statement.\" Trammell looks at the "
             "hole. \"Then he went home to Ohio and ten days later his wife "
             "of twenty-something years told the county he wasn't her "
             "husband. Filed a formal report. Wouldn't retract it. It's in "
             "the file because somebody had to type it up. His name went up "
             "on the board after that, and nobody's ever taken it down. I'm "
             "not superstitious or anything, but thought you should know.\"",
             "clue:sixtyeight"),
        ]),
        Person("Rosalind Alcott", "Wren's mother", [
            ("Wren's mother Rosalind, a small, wiry woman somewhere around "
             "sixty, is standing exactly at the edge of the work "
             "lights, where she has been for the last six hours.\n\n"
             "\"You're the one going down.\"\n\n"
             "It is not a question, so you do not answer it like one. You "
             "give her your name, certification ticket, and a potential "
             "turnaround time, because people hold onto facts when they "
             "cannot hold anything else.",
             "mother"),
            ("\"She started coming here in the spring.\" She has her hands in "
             "her coat pockets and she does not take them out. \"She wouldn't "
             "say where — just Piney Ridge. I thought there was somebody. You "
             "think that, don't you, when she goes quiet and starts going to "
             "another place every few weekends.\"",
             ""),
            ("\"Six weeks ago she came for Sunday and she was fine, and she "
             "was funny, and she did the dishes. We've had this stupid "
             "joke since she was a teenager — if I ever start walking funny, "
             "shoot me — that sort of thing — from every bad horror film we "
             "ever watched. So when she said it at the door I laughed, "
             "because that's the joke.\"\n\n"
             "She stops and starts again, and gets it out straight — she's "
             "been wanting to say this for a long time.\n\n"
             "\"Except she said it twice. And the second time she wasn't "
             "laughing. 'If I ever come back and I'm not right, you'll know, "
             "won't you.' I said 'Yes, sure' — "
             "because it was the door and it was raining, that seemed to be "
             "what she wanted to hear before she left. I just can't figure it "
             "out... was that just a random thing that happened...? Was "
             "this...? I just can't get past it...\" Her voice trails off and "
             "her eyes look out, seeing things nobody else can see. Lost in "
             "memories and questions.",
             "clue:promise"),
        ]),
        Person("Junie Vance", "Wren's partner", [
            ("She is sitting in the open door of the second vehicle with a "
             "cup of something she has not drunk any of.\n\n"
             "\"I'm not family. They keep saying I can go home.\" She looks "
             "up. \"Been together seven years, and I'm 'Not Family.'\"",
             ""),
            ("\"Keys — her car, my car, same ring, since before either of us "
             "had anything worth locking.\" She turns the cup around and does "
             "not drink out of it. \"I came up at four this morning. I opened "
             "it myself... couldn't stand next to it and not open it.\"\n\n"
             "\"Didn't see anything, right? Me neither. Not a single f---ing "
             "clue. I just don't understand. What do you know? What did she "
             "say?\" She looks over at Rosalind. \"Did she tell you anything? "
             "She doesn't talk to me. Never liked me. Wanted Wren to be with "
             "'a nice boy from church,' and I was the furthest thing.\" You "
             "reassure her that she hasn't missed anything of note, despite "
             "the growing feeling of sad suspicion that that isn't true. You "
             "ask her whether she found anything in the car. \"What, that glass in the "
             "bag? I dunno — looked like a camera lens or something? I "
             "mean... it's a lens off something, but who cares? Just some "
             "junk from some other explorer messing around in there like her, "
             "and now we're just wasting time talking and talking. I gave it "
             "to that guy.\" She points at Trammell.\n\n"
             "She pauses. \"No — I — sorry — I just — I don't know what I'm "
             "saying anymore. I guess I gave it to him because I just had "
             "this feeling somebody should keep hold of it. Somebody who "
             "could get it to whoever was going down there. I couldn't tell "
             "you why.\"",
             "clue:keys"),
            ("\"Wren caves. Caved. Caves. Ten years, since school, and she "
             "is the most careful person I have ever met about it — till now, "
             "I guess — buddy system, callouts, the whole song and dance.\" "
             "Junie's hands are steady on the cup. \"Caving isn't my thing, "
             "but we always talked about it and I never stopped her. Just "
             "wanted her to be happy. And then in March she started going "
             "alone and she wouldn't discuss it. Wren doesn't refuse to "
             "discuss things. Wren discusses things until you'd rather die. I "
             "kept wondering if there was someone else or if it was cover for "
             "something else? Really great girlfriend, right? Jumping "
             "straight to conclusions. But this not knowing is infinitely "
             "worse than pretending to know.\"",
             "clue:junie"),
            ("\"She came back different every time. Not bad. Quieter. "
             "Sometimes happier, actually, and that was worse.\"\n\n"
             "She finally looks at the hole.\n\n"
             "\"Last month I asked what was down there. She went quiet — "
             "really thought about it, which isn't like her — she argues in "
             "paragraphs — and then she said, 'Something that's been on its "
             "own a very long time.' I asked what that meant. She said never "
             "mind and that it was a joke and that it was just fun and "
             "deflection, deflection, deflection. She got up and did the "
             "dishes rather than look at me. Not a good night. And now we're "
             "here.\"\n\n"
             "She dissolves into a slow spiral of self-doubt, what-ifs, and "
             "genuine fear. You say and do what you can, but you have to move "
             "on.",
             "clue:somebody"),
        ]),
    ],
    clues=[
        Clue("The map on the table", 2,
             "Eleven pages photocopied and taped together, dated 1973, and "
             "somebody has drawn the modern trail on it with a fine-point "
             "black Sharpie.\n\n"
             "The survey stops at a chamber marked BELL. Past that the "
             "draftsman has written, in the neat block hand of a man doing "
             "his job properly, SURVEY DISCONTINUED — and then, in the same "
             "hand and much smaller, as though it were a technical note: "
             "PARTY UNWILLING.",
             "clue:map"),
        Clue("The thing out of her car", 2,
             "It is on the corner of the map in a freezer bag, "
             "which is what you do with a thing you cannot figure out what it "
             "is for, you suppose. Fair enough.\n\n"
             "You take it out. Definitely a lens. Glass, "
             "thick, a little bigger than a silver dollar, convex on both "
             "faces, gone cloudy around the rim. It sits in a felt sleeve "
             "worn through at one corner. No maker's mark, no frame, no "
             "thread, nothing to say what it was ever fitted to.\n\n"
             "\"Door pocket,\" Trammell says. \"Girlfriend handed it over "
             "this morning. It's not from anyone's glasses, and it's not "
             "off a camera, and whatever it is, it's older than anybody "
             "standing on this ridge. Glass doesn't cloud like that in a few "
             "months or a year or two.\"\n\n"
             "He takes it from you, turns it over once, puts it down on the "
             "map, and does not pick it back up.\n\n"
             "\"Means nothing to me. You want it, take it. It's the only "
             "thing she had with her that I can't account for or explain away "
             "besides 'she found it in or around the cave.'\"",
             "clue:lens"),
    ],
    pickups=[
        Pickup("the lens", needs="clue:lens", flag="lens",
               take="You put it in your chest pocket with the zip, the one "
                    "spare batteries go in; that is the pocket you "
                    "can reach even with a pack on.\n\n"
                    "It weighs almost nothing. You do not think about it "
                    "again for a long time.",
               leave="You leave it on the corner of the map where Trammell "
                     "put it.\n\n"
                     "It is a piece of glass out of a car door. Let's be "
                     "honest: you have sixty meters of rope to rig and a "
                     "hole to be at the bottom of, and there is a limit to "
                     "what you can carry down there on a feeling."),
    ],
    exits=[
        Exit(label="Rig in. Go down.", to="sink", mins=0, hazard="descend",
             need="ready",
             deny="not until you have your brief and have spoken to the "
                  "family"),
        Exit(label="Up toward the hollow", to="hollow", mins=9,
             travel="You walk up out of the lights, "
                    "because you want to hear what the ridge sounds like "
                    "without a generator on it."),
        Exit(label="Follow the flagging up to the ridge trail",
             to="ridge_trail", mins=8,
             travel="You follow the flagging tape up to the contour and "
                    "along it to the junction."),
    ],
),
}

ROOMS.update(PARK)


# --------------------------------------------------------------------------
#  PAYOFFS — what Act One bought you.
#
#  {room_id: {flag: line}}. Shown once, on first arrival, if you did the
#  work up top. None of it is required and none of it changes a mechanic —
#  it changes what you understand while a mechanic is happening to you.
# --------------------------------------------------------------------------

PAYOFFS = {

"gallery": {
    "clue:map": "The 1973 survey stops at the Bell. These tags are past the "
                "Bell. The party got this far and kept numbering stations, "
                "and then decided none of it was going on the paper.",
},

"bell": {
    "clue:map": "This is where the 1973 survey stops. You stand in the last "
                "room eleven pages of paper are willing to admit to, and you "
                "think about a draftsman with a good hand writing PARTY "
                "UNWILLING and then going home for coffee and cake or "
                "whatever draftsmen partake in.",
},

"stream": {
    "clue:spring": "Downstream is southwest. Upstream, half a mile off and "
                   "a long way over your head, is a springhouse in a hollow "
                   "with a course of mortared fieldstone in the mouth of it. "
                   "This water and that water are the same water. Somebody "
                   "worked that out before you did, and then went and got "
                   "mortar. Nobody knows why.",
},

"roost": {
    "clue:deer": "Three deer lying in the open pointed downhill at this. "
                 "Untouched, in September, for a month. Whatever cleared "
                 "the ceiling of this room did not stop at the ceiling of "
                 "this room.",
},

"pack": {
    "clue:register": "Nine entries in seven months and no exit times. You "
                     "look over it again. This pack is packed for a day trip "
                     "by somebody who had made this exact trip eight times "
                     "before and had stopped believing in major "
                     "contingencies.",
},

"squeeze": {
    "clue:promise": "If I ever come back and I'm not right, you'll know, "
                    "won't you.\n\n"
                    "Wren said that at a door, in the rain, six weeks ago, "
                    "and her mother said yes because it was the door and it "
                    "was raining. Your helmet's off.",
},

"long_room": {
    "clue:ivy": "She said morning back like she was being polite to "
                "somebody she had already said it to. Like she had already "
                "said good morning to Ivy Crenshaw that morning, more than "
                "once, on a mile of switchback with nobody else on it.",
},

"ladder": {
    "clue:1911": "1911 is scratched into a lintel in Sander's Hollow by a "
                 "hand in a hurry, and it is written in lamp-black on this wall above a date "
                 "from this year in the same hand and the same black.",
    "clue:blaze": "Hatchet blazes, chest height on somebody shorter than "
                  "you, cut before forty acres of hemlock died standing, "
                  "running downhill in a straight line to a hole with no "
                  "sign on the junction. Somebody wanted this findable. "
                  "Somebody else, later, did not.",
    "clue:here": "The last stone on the rise above Sander's Hollow faces "
                 "the wrong way — away from the house, downhill, toward "
                 "the sink. No name. A date, 1911, and the word HERE cut "
                 "above it, very carefully, by someone thinking hard about "
                 "who would read it.\n\nYou are standing on the ground it "
                 "points at.",
},

"deep": {
    "clue:somebody": "I asked what was down here, Junie said, and Wren "
                     "thought about it for a long time because she wanted "
                     "to get it right.\n\nSomething that's been on its own "
                     "a very long time.",
    "clue:sixtyeight": "Day four, in '68, they brought a man out of this "
                       "alive — dehydrated but fine. He gave a clean "
                       "statement, and ten days later his wife of "
                       "twenty-something years told the county he was not "
                       "her husband and would not retract it.",
    "clue:board": "Two names on a board outside a ranger station, and a "
                  "third already measured out before you ever parked at the "
                  "trailhead. You do the math kneeling here, in "
                  "the dark, with somebody's helmet lamp still burning in "
                  "front of you, and you do not like how easily the board "
                  "could hold more than three.",
},

"adit": {
    "clue:silence": "On the recorder in your chest pocket, at twenty-six "
                    "seconds, there is a sound like a large door being "
                    "pulled to. You have not heard it yet. You are standing "
                    "on the inside of it now.",
},
}


# --------------------------------------------------------------------------
#  PARK AMBIENCE — Act One. The ridge, while it still has light on it.
# --------------------------------------------------------------------------

PARK_AMBIENCE = [
    "Somewhere below, a vehicle door, then nothing.",
    "The hemlocks move all together and then stop all together.",
    "A wood thrush, a long way off, giving its evening call.",
    "Something goes through the laurel about forty yards out, unhurried.",
    "Your radio hisses once, on no channel you have selected.",
]

# ...one that only makes sense while there is still some day left to lose
PARK_DUSK = "The light drops another notch. You can see it happen."

# ...and when the ridge has given you everything it had
PARK_QUIET = "You stand still and listen. The ridge has nothing more to give you."

# The Blowdown gives you nothing at all, ever: no birds, no wind, no laurel.
PARK_SILENCE = ("You stand still and listen. Forty acres of timber and not one "
                "sound in any of it — only your own breathing, and your watch.")
