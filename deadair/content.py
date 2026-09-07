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
        "Behind you the last of the light lies along the ridge in long "
        "orange bars. Your shadow goes down into the hole ahead of you and "
        "does not come back out."
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
