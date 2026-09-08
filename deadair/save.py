"""
DEAD AIR — the save slot.

One run, one file. The game writes it after every action, because the things
that kill you down there are not the kind you see coming, and a player who
has to remember to save is a player who loses an hour of careful rope work to
a closed laptop.

The file lives under XDG_STATE_HOME. A half-finished run is neither config
nor a cache, and that is the drawer for things that are neither.
"""

import json
import os
from pathlib import Path

from .state import Game

VERSION = 1


def path():
    root = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(root) / "deadair" / "save.json"


def write(game, seed=None):
    """Put the run on disk. Failing to save is not worth ending a run over."""
    data = game.snapshot()
    data["version"] = VERSION
    data["seed"] = seed
    p = path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".new")
        tmp.write_text(json.dumps(data))
        tmp.replace(p)      # so a crash mid-write cannot eat the run
    except OSError:
        pass


def read():
    """The saved run as data, or None if there is not one we can use."""
    try:
        data = json.loads(path().read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != VERSION:
        return None
    if data.get("ending"):
        return None         # a finished run is a story, not a save
    return data


def load():
    """The saved run as a Game, or None."""
    data = read()
    return Game.restore(data) if data else None


def clear():
    try:
        path().unlink()
    except OSError:
        pass


def describe(game):
    """One line for the menu: where you left yourself standing."""
    if game.phase == "park":
        return (f"Act One · {game.room.name.lower()} · "
                f"{game.wall_clock()} · {game.daylight:.0f}% light")
    bits = ["Act Two"]
    if game.room.name != "—":   # two rooms down there do not have a name,
        bits.append(game.room.name.lower())   # and are not given one here
    bits += [f"{abs(game.depth)} m down", f"{game.clock()} elapsed",
             f"{game.lamp:.0f}% cell"]
    return " · ".join(bits)
