"""
DEAD AIR — cave, prose, and flavour tables.

Pure data. No mechanics live here, so the writing can be edited without
touching the engine.

Room.look is layered by how far the lamp reaches:
    look[0]  arm's length   — always shown
    look[1]  the room       — needs a working lamp
    look[2]  beyond         — needs a strong lamp
As the cell dies you literally stop being told what is there.
"""

from dataclasses import dataclass, field


@dataclass
class Exit:
    label: str                  # what the action button says
    to: str                     # destination room id
    travel: str = ""            # prose while moving
    mins: int = 4               # minutes of lamp burn
    rope: int = 0               # metres permanently rigged on first use
    need: str = ""              # flag required in state.flags
    deny: str = ""              # shown when `need` is missing
    once: str = ""              # extra prose, first traverse only
    hazard: str = ""            # engine hook: 'collapse', 'dive', 'commit'


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
class Room:
    id: str
    name: str
    depth: int                  # metres below the sink lip
    look: tuple                 # (near, room, beyond)
    exits: list = field(default_factory=list)
    first: str = ""             # first visit only
    tags: set = field(default_factory=set)   # badair, water, signal, roof
    mx: int = 0                 # sidebar map grid
    my: int = 0
    people: list = field(default_factory=list)   # Act One only
    clues: list = field(default_factory=list)    # Act One only


# --------------------------------------------------------------------------
#  THE CAVE
# --------------------------------------------------------------------------

ROOMS = {

"sink": Room(
    id="sink", name="Wolf Sink", depth=0, mx=3, my=0,
    tags={"signal", "surface"},
    look=(
        "The sink is a wound in the hillside. Limestone and root, collapsed "
        "in on itself under a stand of hemlock, forty minutes off the Piney "
        "Ridge trail and not on any of the park's public maps.",
        "Cold air pours out of it steadily enough to move the ferns at the "
        "lip. September. The cave is breathing in, which means it is deep, "
        "and it means somewhere far under you there is a second way to the "
        "surface that nobody has found.",
        "Behind you the work lights make a hard white room out of forty "
        "feet of hemlock and nothing at all out of the rest of the ridge. "
        "Your shadow goes down into the hole ahead of you and does not come "
        "back out."
    ),
    first=(
        "Wren Alcott. Twenty-six. Solo, which is the whole problem. Their "
        "car has been at the trailhead nineteen hours and their permit says "
        "Wolf Sink, and Wolf Sink is a name that made three people at "
        "basecamp go quiet when you read it aloud.\n\n"
        "You do the checks the way you were taught, out loud, alone in the "
        "hemlocks. Primary lamp. Spare cell. Sixty metres of rope. Radio.\n\n"
        "Then you sit on the lip and put your legs into the cold."
    ),
    exits=[
        Exit(label="Go in feet-first", to="letterbox", mins=3,
             travel="You go in feet-first and the temperature drops eleven "
                    "degrees in the length of your own body."),
    ],
),

"letterbox": Room(
    id="letterbox", name="The Letterbox", depth=-4, mx=3, my=1,
    tags={"signal"},
    look=(
        "Forty metres of flat-out crawl, and nowhere in it can you lift your "
        "head. You go on your side with the pack pushed ahead, breathing "
        "against rock that is two inches from your face.",
        "There are drag marks in the silt. One set going in. You put your "
        "own hand beside one of them for scale and it is a smaller hand "
        "than yours.",
        ""
    ),
    first=(
        "Someone named this the Letterbox and then, presumably, went home "
        "and slept fine."
    ),
    exits=[
        Exit(label="Push on through the crawl", to="bell", mins=9,
             travel="Nine minutes of shuffling on one hip. Your helmet "
                    "scrapes a groove in the ceiling the whole way, and the "
                    "sound of it goes ahead of you into the dark and does "
                    "not come back."),
        Exit(label="Reverse out to the sink", to="sink", mins=9,
             travel="You reverse out. It takes longer going backwards. "
                    "It always does."),
    ],
),

"bell": Room(
    id="bell", name="Bell Chamber", depth=-9, mx=3, my=2,
    tags={"signal"},
    look=(
        "You can stand. After the Letterbox that feels like a gift, and you "
        "take a minute to give your ribs back to yourself.",
        "A bell-shaped void, six metres across, floored in cobble. Three "
        "ways on. Someone has left a cairn of four stones by the western "
        "passage — recent, the top stone still pale where it was lifted.",
        "The ceiling goes up past the useful reach of your beam into a "
        "chimney that nobody has surveyed. Water comes down out of it, "
        "one drop at a time, and lands somewhere you cannot see."
    ),
    first=(
        "You call it in. Basecamp comes back thin but readable: they have "
        "you at the Bell, they have your time, they will hold the frequency."
        "\n\nThis is the last place in the cave where that is true."
    ),
    exits=[
        Exit(label="West — the stream passage", to="stream", mins=6,
             travel="You take the western way, past the cairn, and within "
                    "twenty metres you can hear water working."),
        Exit(label="East — the dry gallery", to="gallery", mins=6,
             travel="East. The floor comes up and the air goes dry and the "
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
        "ninety seconds and settles in for the duration.",
        "A canyon passage, taller than it is wide, cut by this same water "
        "over a length of time that does not fit in your head. Scallops in "
        "the wall all point the way the flow goes. Downstream is north-west. "
        "Downstream is always the answer if you are lost, and Wren knew that.",
        "There is a flood line on the wall at chest height. Old debris "
        "packed into a ledge — twigs, a shred of blue tarp, one bone that "
        "you decide is a deer's."
    ),
    exits=[
        Exit(label="Follow the water down", to="sump", mins=8,
             travel="You follow it down. The ceiling comes to meet the "
                    "water by degrees, politely, until it doesn't."),
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
        "for four or five metres before it gives up, showing you clean rock "
        "and one boot-shaped disturbance in the silt at the very edge of "
        "what you can see.",
        "There is a dive line here. Blue polypropylene, knotted to a rock "
        "thread, going into the water and down. It is not park equipment. "
        "It is not new. Nobody at basecamp mentioned a dive line."
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
                    "which you notice yourself doing, and do anyway."),
    ],
),

"gallery": Room(
    id="gallery", name="Dry Gallery", depth=-13, mx=5, my=2,
    tags={"signal"},
    look=(
        "Dust. Actual dust, which in a cave means no water has come through "
        "here in a very long time.",
        "Survey stations, old ones — aluminium tags hammered into the wall, "
        "stamped WS-11, WS-12. Someone mapped this in nineteen-seventy-"
        "something and then the file went into a drawer.",
        "Orange flagging tape on a projection at the far end, tied in a "
        "bowline. Fresh. Wren's colour. It marks the way on, and the way on "
        "is a hole in the floor."
    ),
    exits=[
        Exit(label="On to the flagged hole", to="pitch_head", mins=5,
             travel="You walk the gallery. Your boots print in dust that "
                    "already holds one other set of prints, going the "
                    "same way."),
        Exit(label="Back to the Bell", to="bell", mins=6,
             travel="Back west, into the sound of dripping."),
    ],
),

"pitch_head": Room(
    id="pitch_head", name="The Drop", depth=-16, mx=5, my=3,
    look=(
        "A hole in the floor of the gallery, a metre and a half across. "
        "You lie on your stomach and put your head over the edge.",
        "Twelve metres, free-hanging, into a chamber your beam cannot find "
        "the far side of. There are two good naturals for a rig — a thread "
        "and a solid flake — and a deviation you would want at about four "
        "metres.",
        "Wren's flagging goes over the lip and stops. They downclimbed this "
        "or they fell down it, and there is no way to know which from up here."
    ),
    first=(
        "You try the radio. Basecamp is a shape in the static now, not a "
        "voice. You give your position twice and get nothing back you would "
        "swear to in a report."
    ),
    exits=[
        Exit(label="Rig the rope and descend  (15 m)", to="pitch_bottom",
             mins=14, rope=15, hazard="commit",
             once="You rig it properly because that is what you are: thread, "
                  "backup, deviation at four metres, knot in the end. Then "
                  "you weight it and step off the floor of the world.",
             travel="Down the rope. Twelve metres of free hang, turning "
                    "slowly, your light swinging across walls that keep "
                    "not being where you left them."),
        Exit(label="Back into the gallery", to="gallery", mins=5,
             travel="You back off the lip."),
    ],
),

"pitch_bottom": Room(
    id="pitch_bottom", name="Foot of the Drop", depth=-28, mx=5, my=4,
    look=(
        "You come off the rope onto a floor of shattered plate. The rope "
        "hangs behind you, rigged, which is the only reason you can get out "
        "of here, and you touch it once before you leave it.",
        "Bigger down here. The chamber runs off in two directions and the "
        "air moves through it — which is good, air movement is life — "
        "except that it is moving toward you from both directions at once, "
        "which is not how air works.",
        "Twenty-eight metres. There is more rock over your head now than "
        "most people stand under in a lifetime."
    ),
    first=(
        "You mark the pitch foot with a reflective tag at knee height, "
        "because at the end of this you will be tired and the way out will "
        "look like every other hole in the wall."
    ),
    exits=[
        Exit(label="West into the breakdown", to="breakdown", mins=7,
             travel="West, over blocks the size of cars, testing each one "
                    "before you trust it."),
        Exit(label="South — a low sallow passage", to="badair", mins=6,
             travel="South, and the passage lowers, and within a minute "
                    "your lamp flame — you don't have a flame, you have an "
                    "LED, and still something about the light goes yellow."),
        Exit(label="Climb the rope out", to="pitch_head", mins=16,
             travel="You get back on the rope and start prusiking. Twelve "
                    "metres takes sixteen minutes and every one of them is "
                    "yours."),
    ],
),

"breakdown": Room(
    id="breakdown", name="Breakdown", depth=-31, mx=3, my=4,
    look=(
        "A collapse. The ceiling came down here, once, all at once, and "
        "nobody was under it because nobody had been born yet.",
        "You route through the gaps between blocks. Some of them are keyed "
        "in and some of them are balanced, and telling the difference is "
        "the entire job.",
        "Something shifts, far back in the pile, and settles. The cave does "
        "this. The cave has always done this. You wait until your heart "
        "agrees."
    ),
    exits=[
        Exit(label="Pick a line through the blocks", to="pack", mins=11,
             hazard="collapse",
             travel="You take it slow, three points of contact, weight "
                    "committed only after the block has been asked twice."),
        Exit(label="A crawl going north", to="roost", mins=5,
             travel="A crawl, north, and the smell changes."),
        Exit(label="Back east to the pitch", to="pitch_bottom", mins=7,
             travel="Back east across the blocks."),
    ],
),

"roost": Room(
    id="roost", name="The Roost", depth=-33, mx=1, my=4,
    look=(
        "A domed side-chamber, and the floor of it is soft and deep and "
        "black, and you know what guano is before your light finds the "
        "ceiling.",
        "Decades of it. Centuries. A colony lived here in numbers that "
        "would have made this room roar every dusk from October to April.",
        "The ceiling is empty. Not white-nose empty, not sick-and-dying "
        "empty — empty like it was swept. No bats. No bodies. No mites. "
        "Nothing has been in this room for a long time and something made "
        "very sure of that."
    ),
    first=(
        "You stand in the middle of it with your light up and you count to "
        "thirty and nothing in the room moves except you.\n\n"
        "There is a spare lamp cell here, on a rock, set down neatly with "
        "its terminals up. It is the same model as yours. You put it in "
        "your chest pocket and you do not think about who set it down "
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
        "The passage is a metre high and you are on hands and knees and the "
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
        Exit(label="Reverse out to the pitch foot", to="pitch_bottom", mins=6,
             travel="You reverse out, and the moment the air thins you sit "
                    "down hard and breathe like something landed."),
    ],
),

"pack": Room(
    id="pack", name="Wren's Cache", depth=-37, mx=3, my=5,
    look=(
        "A junction chamber, and in the middle of it, set down against a "
        "boulder, is a red forty-litre pack.",
        "Wren's. Their name is inked on the lid strap. It is packed and "
        "closed and upright. Nobody drops a pack this neatly in an "
        "emergency; you set a pack down like this when you intend to come "
        "straight back to it.",
        "Inside: dry bag, food for two days untouched, a first-aid kit "
        "unopened, and a handheld radio with the volume wheel turned "
        "all the way up."
    ),
    first=(
        "The radio in the pack is on. The battery should have died eleven "
        "hours ago and it is on, and it is putting out a flat carrier hiss "
        "with no station behind it.\n\n"
        "You key your own set and say Wren's name into it. The hiss in the "
        "pack changes shape for exactly as long as you are talking, and "
        "then goes back to being hiss."
    ),
    exits=[
        Exit(label="On, to a slot in the far wall", to="squeeze", mins=6,
             travel="There is a slot in the far wall, and there is fresh "
                    "scuffing on the lip of it at hip height."),
        Exit(label="Back east into the breakdown", to="breakdown", mins=11,
             travel="Back east over the blocks."),
        Exit(label="Back north into the sallow air", to="badair", mins=5,
             travel="You take a breath in good air, and go back into the "
                    "bad on purpose, which everything in you objects to."),
    ],
),

"squeeze": Room(
    id="squeeze", name="The Keyhole", depth=-41, mx=3, my=6,
    look=(
        "A vertical slot, hip-wide at the bottom and shoulder-wide at the "
        "top, and the only way through it is on your side with your arms "
        "over your head and nothing on your back.",
        "You will have to take off your pack and push it through ahead of "
        "you. Everything you own will be on the far side of a hole you may "
        "not be able to reverse quickly.",
        "Air moves through it hard enough to whistle."
    ),
    first=(
        "This is the point in the callout where the honest thing to do is "
        "turn around, log the find, and come back with four people and a "
        "hauling system.\n\n"
        "The pack radio is still hissing behind you.\n\n"
        "You take your helmet off to fit."
    ),
    exits=[
        Exit(label="Strip the pack and go through", to="long_room", mins=12,
             hazard="commit",
             once="Halfway through, wedged, with the rock on your sternum "
                  "and on your spine at the same time, you exhale all the "
                  "way to make yourself smaller, and for four seconds you "
                  "cannot get the breath back.",
             travel="You go through sideways, in stages, in the dark, with "
                    "your lamp in your teeth."),
        Exit(label="Back to the cache", to="pack", mins=6,
             travel="You reverse the Keyhole. It is worse in this direction."),
    ],
),

"long_room": Room(
    id="long_room", name="The Long Room", depth=-52, mx=3, my=7,
    look=(
        "You come out of the Keyhole into space. You can feel it before you "
        "see it — the sound of your own breathing goes away from you and "
        "does not come back for a full second.",
        "Your beam does not reach the far wall. It does not reach the "
        "ceiling. You are standing at the edge of a room the size of a "
        "cathedral, fifty-two metres under a national park, in a cave that "
        "has eleven pages of survey and no mention of this at all.",
        "The floor is flat. Not fallen-flat. Flat like a lakebed, and "
        "across it, going away from you into the dark, is a single line of "
        "footprints in the silt, and they are not going toward anything "
        "you can see."
    ),
    first=(
        "You shout Wren's name because that is the protocol.\n\n"
        "The echo comes back at four seconds, which is wrong for a room "
        "this size. And it comes back in your voice, saying your own name."
    ),
    exits=[
        Exit(label="Follow the footprints", to="deep", mins=15,
             travel="You follow them. They are Wren's size. Their stride "
                    "does not shorten, does not stumble, does not deviate. "
                    "Whoever walked this walked it calmly, in the dark, "
                    "with no light at all — there is no lamp-splash on the "
                    "silt, and there would be."),
        Exit(label="East, along the wall", to="ladder", mins=9,
             travel="You keep your left hand on the wall and work east, "
                    "which is what you do in a room you cannot see the "
                    "shape of."),
        Exit(label="Back to the Keyhole", to="squeeze", mins=12,
             travel="You go back to the slot in the wall."),
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
        "go up eleven metres into a rift and stop at solid rock.\n\n"
        "You take a photograph, because the report will need it and because "
        "holding the camera up gives your hands something to do.\n\n"
        "There is a spare cell wedged behind the third rung. Modern. Yours "
        "fits it. You take it and you feel like a thief and you take it "
        "anyway."
    ),
    exits=[
        Exit(label="Back into the Long Room", to="long_room", mins=9,
             travel="Back along the wall, left hand trailing, west."),
    ],
),

"deep": Room(
    id="deep", name="—", depth=-61, mx=3, my=8,
    look=(
        "The footprints stop.",
        "They do not turn around. They do not scuff or scatter. They walk "
        "eleven paces into an open flat floor and they stop, and after that "
        "there is only clean silt for as far as your light reaches.",
        "And sitting on the silt at the end of them, folded neatly, is "
        "Wren Alcott's oversuit, and their helmet on top of it, and the "
        "helmet lamp is still on."
    ),
    first=(
        "You are sixty-one metres down.\n\n"
        "You kneel by the suit. It is dry. It has been dry for a long time "
        "in a cave where nothing is dry, and it is warm, the way cloth is "
        "warm when someone has just got out of it.\n\n"
        "The helmet lamp has been burning for nineteen hours on a cell "
        "rated for eight.\n\n"
        "Behind you, from the direction you came, at a distance you could "
        "walk in ninety seconds, someone says your name.\n\n"
        "It is not Wren's voice. It is not anyone's voice. It is the voice "
        "you use when you are alone and reading a map out loud."
    ),
    exits=[
        Exit(label="Take the helmet and get out. Now.", to="long_room",
             mins=15, hazard="took_find",
             travel="You take the helmet. You do not turn your back on the "
                    "dark to do it — you back away with your light up, all "
                    "the way, until the wall finds your shoulder."),
        Exit(label="Answer it", to="stay", mins=1, hazard="answer",
             travel="You turn around, and you put your light on it, and "
                    "you say: I'm here."),
    ],
),

# ----- terminal rooms -------------------------------------------------------

"drowned": Room(
    id="drowned", name="Under", depth=-24, mx=0, my=3,
    look=("", "", ""),
),

"stay": Room(
    id="stay", name="—", depth=-61, mx=3, my=8,
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
        "A light passes across the far wall. You have not moved your head.",
    ],
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
    "letterbox": "a helmet dragging a groove along a low ceiling",
    "bell": "boots on cobble, then a pause, then boots on cobble",
    "stream": "someone walking in ankle-deep water, unhurried",
    "sump": "a hand put into still water and held there",
    "gallery": "footsteps in dust, and the small sound of tape being touched",
    "pitch_head": "a rope being pulled through a descender",
    "pitch_bottom": "someone landing on shattered plate and standing still",
    "breakdown": "a block tested, twice, and then trusted",
    "roost": "a person counting to thirty under their breath",
    "badair": "fast shallow breathing that will not slow down",
    "pack": "a radio being keyed, and a name said into it",
    "squeeze": "a long exhale, and then nothing at all for four seconds",
    "long_room": "a shout, and then a four-second wait",
    "ladder": "a camera shutter",
    "deep": "someone kneeling down in silt",
}


# --------------------------------------------------------------------------
#  RADIO — basecamp, by depth. Degrades. Then it doesn't degrade correctly.
# --------------------------------------------------------------------------

RADIO = {
    "clear": [
        "BASECAMP: Copy your position. We have you logged. Wind's picking "
        "up out here but the sky's clean. Nothing to worry you.",
        "BASECAMP: Copy. Sheriff's put a second team on standby at the "
        "trailhead. You call, they come. Take your time and take it safe.",
        "BASECAMP: Copy, copy. Subject's family is here. I'm not putting "
        "them on the radio. Go do your job.",
    ],
    "weak": [
        "BASECAMP: ...copy your... say again your dep—  ...ave you at...",
        "BASECAMP: ...old the frequency. We're not going... —where. Say "
        "again when you c...",
        "BASECAMP: ...ing you every fifteen. If we lose you for an hour "
        "we're com... ...you hear that? Acknow—",
    ],
    "gone": [
        "Carrier hiss. Under it, at the edge of hearing, a rhythm that is "
        "almost a voice, and it has the cadence of your own callsign, and "
        "it is not saying your callsign.",
        "Nothing. You hold the key down for ten seconds and say your "
        "position into an open channel and hear, faintly, a second key "
        "click open somewhere, and close again.",
        "BASECAMP, clear as a bell, no static at all, at sixty metres of "
        "solid limestone: 'We've got Wren. Wren's here, they walked out an "
        "hour ago. Who's down there?'",
        "Your own voice, from four hours ago, giving your position at the "
        "Bell Chamber. Word for word. Including the part where you cleared "
        "your throat.",
    ],
}


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
        "Gravel pull-off, room for six vehicles, four of them here. Yours is "
        "the one with the light bar. The air smells like hot brake dust and "
        "somebody's coffee going cold on a tailgate.",
        "A silver hatchback sits nose-in at the far end under a hemlock, and "
        "it has been sitting there since yesterday morning. There is a park "
        "notice tucked under its wiper, which is the smallest and most "
        "official way of saying that somebody noticed and did nothing.",
        "The ridge goes up behind the lot and keeps going. Nineteen hundred "
        "feet of it, hemlock over hardwood, and the light on it is the "
        "colour of a struck match and running out fast."
    ),
    first=(
        "Wren Alcott. Twenty-six. Solo, which is the whole problem.\n\n"
        "Nineteen hours overdue on a permit that says Wolf Sink, and Wolf "
        "Sink is a name that made three people at the ranger station go "
        "quiet when you read it aloud.\n\n"
        "You have until dark to walk the approach and talk to whoever saw "
        "them last. After that this stops being a search and starts being "
        "a callout, and you go down the hole."
    ),
    people=[
        Person("Ranger Dolan Pace", "park law enforcement", [
            ("\"Dolan Pace. I took the call.\" He shakes your hand like it "
             "is a thing he has decided to do rather than a thing he does. "
             "\"Vehicle's been here since oh-seven yesterday. Permit's in "
             "the box. Everything by the book, right up until it wasn't.\"",
             ""),
            ("\"Wolf Sink isn't on the public map and it isn't on the "
             "survey either — not properly. There's eleven pages from "
             "seventy-three in a drawer in Blakely and that's the whole "
             "file.\" He looks up the ridge. \"I've worked this park nine "
             "years. I've never been down it and I've never wanted to.\"",
             ""),
            ("\"You want the honest version? We've had three in that hole. "
             "Nineteen-eleven, sixty-eight, and now.\" He says it flat, the "
             "way you say a thing you have already decided not to have an "
             "opinion about. \"The board outside the station has two names "
             "on it. I've been asked twice to take it down.\"",
             "clue:board"),
        ]),
    ],
    clues=[
        Clue("The silver hatchback", 3,
             "Unlocked. Nobody locks a car at a trailhead they mean to come "
             "back to in four hours.\n\n"
             "Inside: a change of clothes folded on the passenger seat, a "
             "receipt from a gas station in Blakely timestamped 05:41 "
             "yesterday, and, in the door pocket, a second permit — same "
             "hand, same box ticked, dated three weeks ago.\n\n"
             "Wren has been here before. More than once.",
             "clue:car"),
        Clue("The permit register", 3,
             "A steel box on a post with a slot in the top and a pad of "
             "carbon forms. You thumb back through the copies.\n\n"
             "Wren's is on top, yesterday, 06:10, WOLF SINK printed in "
             "small square capitals.\n\n"
             "Six weeks back, in the same hand, the same box. And eleven "
             "weeks. And in March, and in March again. Nine entries for "
             "Wolf Sink in seven months and every one of them solo, and "
             "not one of them logged an exit time.",
             "clue:register"),
    ],
    exits=[
        Exit(label="Take the trail up the ridge", to="ridge_trail", mins=6,
             travel="You go up. The grade is honest for the first ten "
                    "minutes and then it stops being honest."),
    ],
),

"ridge_trail": Room(
    id="ridge_trail", name="The Ridge Trail", depth=0, mx=1, my=0,
    tags={"surface", "park", "signal"},
    look=(
        "Packed dirt and root, two feet wide, switchbacking up through "
        "rhododendron that closes over the trail like a tunnel and then "
        "lets go of it again.",
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
            ("She is sitting on a rock with a foil blanket she does not "
             "need around her shoulders, because somebody handed it to her "
             "and she did not know how to refuse it.\n\n"
             "\"I already told the ranger. I ran past them. Yesterday, "
             "early, before it was properly light.\"",
             ""),
            ("\"They were going down the use path with a pack on. I said "
             "morning and they said morning back.\" She stops. \"That's the "
             "part I keep going over, because they said it like — like they "
             "were being polite to somebody they'd already said it to. "
             "Like I was the second person.\"",
             "clue:ivy"),
            ("\"There wasn't anyone else on the path. I'd have passed them. "
             "It's a mile of switchback and you can see the whole thing.\"\n\n"
             "She pulls the blanket tighter, and she is not cold.\n\n"
             "\"I ran the rest of it faster than I meant to. I couldn't "
             "tell you why. There weren't any birds.\"",
             ""),
        ]),
    ],
    clues=[
        Clue("The use path", 2,
             "Twenty years of boots, minimum. This is not a route somebody "
             "found last spring — it is a route the ground has agreed to.\n\n"
             "Fresh tread on top of all of it, one set, going down. Vibram, "
             "size seven or eight. Nothing coming back up.",
             "clue:path"),
        Clue("The junction sign", 2,
             "Brown fibreglass, routed lettering, park standard. OVERLOOK "
             "1.4 with an arrow to the left.\n\n"
             "There is no arrow to the right. There is a rectangle of "
             "slightly darker fibreglass where a second panel used to be "
             "bolted on, and two empty holes, and the holes have been "
             "filled with silicone by somebody who did not want a third "
             "panel going up.",
             ""),
    ],
    exits=[
        Exit(label="Right — down the use path", to="blowdown", mins=7,
             travel="You take the use path down. Within a hundred yards the "
                    "rhododendron closes and the trail noise stops, all of "
                    "it at once, the way sound stops when a door shuts."),
        Exit(label="Straight on toward the sink", to="basecamp", mins=8,
             travel="You stay on the contour and follow the flagging tape "
                    "somebody has already run in for you."),
        Exit(label="Back down to the trailhead", to="trailhead", mins=6,
             travel="Back down. It goes faster than it came."),
    ],
),

"blowdown": Room(
    id="blowdown", name="The Blowdown", depth=0, mx=2, my=1,
    tags={"surface", "park"},
    look=(
        "Standing dead timber, forty acres of it. Hemlock, grey, barkless, "
        "still upright — which is wrong. Blowdown falls. This did not fall.",
        "It died standing and it died all together. No fire scar, no beetle "
        "galleries under the bark you peel back, no wind-throw, no root "
        "plates in the air. Forty acres of tree simply stopped, on some "
        "particular day, and have been standing here since holding the "
        "shape of the thing they used to be.",
        "The ground under it is bare. Not thin — bare. Nothing has "
        "colonised forty acres of full sun in however many years this has "
        "been open, and the seedlings stop at the edge of it in a line you "
        "could follow with your finger."
    ),
    first=(
        "You stop in the middle of it and do the thing you were taught to "
        "do in unfamiliar ground, which is stand still for one full minute "
        "and let the place tell you what is in it.\n\n"
        "It takes about fifteen seconds to work out what is wrong.\n\n"
        "There is no sound. No birds, no squirrel scold, no insect, no "
        "wind in forty acres of dead standing timber that ought to be "
        "clacking like a xylophone. You can hear the blood in your own ear."
    ),
    clues=[
        Clue("The silence", 3,
             "You get the recorder out of your chest pocket and hold it up "
             "and let it run for thirty seconds, because a thing you cannot "
             "explain is a thing you document.\n\n"
             "Later, in a motel room in Blakely, you will play it back and "
             "hear thirty seconds of nothing, and then, at twenty-six "
             "seconds, very far away and very clear, a sound like a large "
             "door being pulled to.",
             "clue:silence"),
        Clue("A whitetail doe, dead", 3,
             "Three weeks gone, maybe four. It is lying on its side in the "
             "open with its legs out straight.\n\n"
             "Nothing has been at it. No coyote, no vulture, no beetle, no "
             "fly. In four weeks in September, in these mountains, a deer "
             "goes back into the ground in eleven days and there is nothing "
             "left of this one that has been touched.\n\n"
             "It is pointed downhill. So are the other two you find without "
             "looking very hard. All three are pointed downhill, at the "
             "same thing, and you already know what is downhill of here.",
             "clue:deer"),
        Clue("Blazes on the dead trees", 4,
             "Old ones. Cut with a hatchet, not painted — a hand's width of "
             "bark taken off and the wood beneath gone silver.\n\n"
             "They are chest height on a person shorter than you and they "
             "are spaced for somebody walking a line in the dark. And they "
             "are on dead trees, which means they were cut before the trees "
             "died, which means they are older than forty acres of "
             "impossible standing timber.\n\n"
             "They go downhill in a straight line. Somebody blazed a route "
             "to Wolf Sink and then somebody else, later, spent a lot of "
             "effort taking the sign off a junction.",
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
        "And apple. Two trees of it, gone wild and barely holding on in the "
        "shade, which nobody plants by accident. This was a place with a "
        "family in it, and it is nine hundred yards from the sink, and it "
        "is not on the park map either."
    ),
    clues=[
        Clue("The chimney fall", 3,
             "Dry-laid fieldstone, and one dressed lintel that somebody cut "
             "properly with a chisel.\n\n"
             "There is a date on the lintel. 1889. Under it, in a different "
             "hand and a shallower cut, somebody has scratched a second "
             "date the way you would scratch it with a nail, in a hurry, "
             "not meaning it to last: 1911.",
             "clue:1911"),
        Clue("The springhouse", 3,
             "The water still comes out cold enough to hurt. You put two "
             "fingers in it out of habit.\n\n"
             "It goes about eight feet and then it goes into the ground, "
             "and the hole it goes into has been closed with a course of "
             "the same fieldstone, mortared, by somebody who came back here "
             "with a bucket of mortar a long time after the house fell in.\n\n"
             "You do not close a spring. A spring is the reason you build "
             "where you build. You close a spring when you have stopped "
             "caring where the water goes and started caring what comes up "
             "it.",
             "clue:spring"),
        Clue("The burying ground", 4,
             "Eleven stones on the rise above the house, field-cut, most "
             "of them illegible.\n\n"
             "Four of them are small. That is ordinary for 1889 and you "
             "make yourself remember that it is ordinary.\n\n"
             "The last one is not from 1889. It is newer, and it is set "
             "apart from the others by a good twenty feet, and it faces the "
             "wrong way — every stone on this rise faces the house except "
             "this one, which faces downhill, toward the sink. There is no "
             "name on it. There is a date, 1911, and above the date "
             "somebody has cut, very carefully, the word HERE.",
             "clue:here"),
    ],
    exits=[
        Exit(label="Down the last of it to the sink", to="basecamp", mins=9,
             travel="You come out of the hollow onto a bench of level "
                    "ground, and there are lights on it, and voices, and "
                    "the ordinary sound of people doing a job."),
        Exit(label="Back up through the dead timber", to="blowdown", mins=8,
             travel="Back up. You go faster than the ground requires."),
    ],
),

"basecamp": Room(
    id="basecamp", name="Wolf Sink — Basecamp", depth=0, mx=4, my=3,
    tags={"surface", "park", "signal"},
    look=(
        "Two vehicles they should not have been able to get up here, a "
        "generator running a string of work lights, and a folding table "
        "with a map on it held down at the corners by rocks.",
        "Eleven people. Two of them are in oversuits and are not going "
        "anywhere until somebody tells them to. The rest are standing "
        "around the table being useful at a map that does not show the "
        "thing they need it to show.",
        "And thirty yards off, past the last of the light, the ground opens "
        "up under a stand of hemlock and cold air comes out of it steadily "
        "enough to move the ferns at the lip."
    ),
    first=(
        "The generator makes it possible to pretend this is an operation "
        "with a floor under it.\n\n"
        "Nobody is going down that hole tonight except you. There is one "
        "person on this ridge with a current cave rescue ticket and a "
        "vertical qualification, and you have been that person since "
        "05:20 this morning when somebody in Blakely read a permit."
    ),
    people=[
        Person("Beau Trammell", "SAR team lead", [
            ("\"Trammell. I've got the surface.\" He does not waste your "
             "time. \"Eleven pages of survey from seventy-three, and the "
             "surveyor's note says it's incomplete. Rigging's on you. "
             "You've got sixty metres, two spares, and the set.\"",
             "brief"),
            ("\"Comms is going to be garbage. We'll hold the frequency and "
             "we'll take whatever we get.\" He taps the map twice, on "
             "nothing. \"Turnaround is oh-six-hundred. If I haven't heard "
             "you by then I call Blakely and Blakely calls the state, and "
             "then it's a recovery and nobody's going down after you for "
             "nine days.\"",
             ""),
            ("\"One more thing and then I'll leave you alone.\"\n\n"
             "He waits until the two in oversuits have gone back to the "
             "table.\n\n"
             "\"Sixty-eight. The one before this. They brought him out "
             "alive on day four and he was fine — dehydrated, hypothermic, "
             "fine. He gave a clean statement.\" Trammell looks at the "
             "hole. \"Then he went home to Ohio and eleven days later his "
             "wife of thirty years told the county he wasn't her husband. "
             "Filed it formally. Wouldn't retract it. It's in the file "
             "because somebody had to type it up.\"",
             "clue:sixtyeight"),
        ]),
        Person("Rosalind Alcott", "Wren's mother", [
            ("She is sixty-one and she is standing exactly at the edge of "
             "the work lights, which is where they have put her, and she "
             "has been standing there for six hours.\n\n"
             "\"You're the one going down.\"\n\n"
             "It is not a question, so you do not answer it like one. You "
             "give her your name and your ticket and the turnaround time, "
             "because people can hold facts when they cannot hold anything "
             "else.",
             "mother"),
            ("\"They started coming here in the spring.\" She has her hands "
             "in her coat pockets and she does not take them out. \"They "
             "wouldn't say where. I thought there was somebody. You think "
             "that, don't you, when they go quiet and they go every "
             "weekend. You think there's somebody and you're pleased.\"",
             ""),
            ("\"Six weeks ago they came for Sunday and they were fine, and "
             "they were funny, and they did the washing-up, and at the door "
             "they said —\"\n\n"
             "She stops and starts again, and gets it out level.\n\n"
             "\"They said: if I ever come back and I'm not right, you'll "
             "know, won't you. And I said don't be stupid. And they said "
             "no, I mean it, you'll know. And I said yes. I said yes, "
             "because it was the door and it was raining.\"",
             "clue:promise"),
        ]),
        Person("Junie Vance", "Wren's partner", [
            ("They are sitting in the open door of the second vehicle with "
             "a cup of something they have not drunk any of.\n\n"
             "\"I'm not family. They keep saying I can go home.\" They look "
             "up. \"Eleven years. I'm not family.\"",
             ""),
            ("\"Wren caves. Caved. Twenty years, since school, and they are "
             "the most careful person I have ever met about it — buddy "
             "system, call-outs, the whole liturgy.\" Their hands are "
             "steady on the cup. \"And then in March they started going "
             "alone and they wouldn't discuss it. Wren doesn't refuse to "
             "discuss things. Wren discusses things until you'd rather die.\"",
             "clue:junie"),
            ("\"They came back different every time. Not bad. Quieter. "
             "Happier, actually, and that was worse.\"\n\n"
             "They finally look at the hole.\n\n"
             "\"Last month I asked what was down there. And they thought "
             "about it properly, for a long time, like it was a real "
             "question and they wanted to get it right. And then they said: "
             "somebody who's been on their own for a very long time.\"",
             "clue:somebody"),
        ]),
    ],
    clues=[
        Clue("The map on the table", 2,
             "Eleven pages photocopied and taped together, dated 1973, and "
             "somebody has drawn the modern trail on it in biro.\n\n"
             "The survey stops at a chamber marked BELL. Past that the "
             "draughtsman has written, in the neat block hand of a man "
             "doing his job properly, SURVEY DISCONTINUED — and then, in "
             "the same hand and much smaller, as though it were a technical "
             "note: PARTY UNWILLING.",
             "clue:map"),
    ],
    exits=[
        Exit(label="Rig in. Go down.", to="sink", mins=0, hazard="descend",
             need="ready",
             deny="not until you have your brief and have spoken to the "
                  "family"),
        Exit(label="Back up toward the hollow", to="hollow", mins=9,
             travel="You walk back up out of the lights for a minute, "
                    "because you want to hear what the ridge sounds like "
                    "without a generator on it."),
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

"bell": {
    "clue:map": "This is where the 1973 survey stops. You stand in the last "
                "room eleven pages of paper are willing to admit to, and "
                "you think about a draughtsman with a good hand writing "
                "PARTY UNWILLING and then going home to his tea.",
},

"stream": {
    "clue:spring": "Downstream is north-west. Downstream, over your head "
                   "and nine hundred yards of it, is a springhouse in a "
                   "hollow with a course of mortared fieldstone in the "
                   "mouth of it. This water and that water are the same "
                   "water. Somebody worked that out before you did, and "
                   "then went and got mortar.",
},

"roost": {
    "clue:deer": "Three deer lying in the open pointed downhill at this. "
                 "Untouched, in September, for a month. Whatever cleared "
                 "the ceiling of this room did not stop at the ceiling of "
                 "this room.",
},

"pack": {
    "clue:register": "Nine entries in seven months and no exit times. This "
                     "pack is packed for a day trip by somebody who had "
                     "made this exact trip eight times before and had "
                     "stopped believing the eighth one counted.",
},

"squeeze": {
    "clue:promise": "If I ever come back and I'm not right, you'll know, "
                    "won't you.\n\nWren said that at a door, in the rain, "
                    "six weeks ago, and their mother said yes because it "
                    "was the door and it was raining. You take your helmet "
                    "off and you go through the hole anyway.",
},

"long_room": {
    "clue:ivy": "They said morning back like they were being polite to "
                "somebody they had already said it to. Like Ivy Crenshaw "
                "was the second person to say it to them that morning, on "
                "a mile of switchback with nobody else on it.",
},

"ladder": {
    "clue:1911": "1911 is cut into a lintel in Sander's Hollow in a hand "
                 "in a hurry, and it is on a stone twenty feet from eleven "
                 "others facing the wrong way with HERE cut above it, and "
                 "it is written in lamp-black on this wall beside a date "
                 "from this year in the same hand and the same black.",
    "clue:blaze": "Hatchet blazes, chest height on somebody shorter than "
                  "you, cut before forty acres of hemlock died standing, "
                  "running downhill in a straight line to a hole with no "
                  "sign on the junction. Somebody wanted this findable. "
                  "Somebody else, later, did not.",
},

"deep": {
    "clue:somebody": "You asked what was down here, Junie said, and Wren "
                     "thought about it for a long time because they wanted "
                     "to get it right.\n\nSomebody who's been on their own "
                     "for a very long time.",
    "clue:sixtyeight": "Day four, in sixty-eight, they brought a man out "
                       "of this alive and dehydrated and fine, and he gave "
                       "a clean statement, and eleven days later his wife "
                       "of thirty years told the county he was not her "
                       "husband and would not retract it.",
},
}


# --------------------------------------------------------------------------
#  PARK AMBIENCE — Act One. The ridge, while it still has light on it.
# --------------------------------------------------------------------------

PARK_AMBIENCE = [
    "Somewhere below, a vehicle door, and then nothing.",
    "The hemlocks move all together and then stop all together.",
    "A wood thrush, a long way off, giving the evening call.",
    "The light drops another notch. You can watch it happen.",
    "Something goes through the laurel about forty yards out, unhurried.",
    "Your radio hisses once, on no channel you have selected.",
]
