# DEAD AIR

A first-person cave-horror game for the terminal. You are a search-and-rescue
officer entering an unsurveyed sink in Piney Ridge National Park, nineteen
hours behind a solo caver who did not come out.

It opens above ground. You have one evening of light to walk the approach,
read the ground, and talk to the people who saw Wren Alcott last — and then
you go down the hole.

Every room draws itself. The scenes are raymarched at runtime and lit by your
actual lamp, so the picture loses reach and detail as the cell dies, for the
same reason the prose does.

Built with [Textual](https://textual.textualize.io/). Runs in kitty — the
graphics use the kitty protocol, and fall back to sixel and then to Unicode
half-blocks elsewhere, so it plays in any terminal and looks best in one that
can draw. Ghostty, WezTerm and Konsole speak the protocol too.

## Install

Needs Python 3.12 or newer. [pipx](https://pipx.pypa.io) is the tidiest way —
it keeps the game and its dependencies in their own environment and puts
`deadair` on your PATH:

    pipx install git+https://github.com/AustinGuidry/dead-air

Or with plain pip, ideally into a virtualenv:

    pip install git+https://github.com/AustinGuidry/dead-air

Then, from anywhere:

    deadair

Pass `--seed N` to fix the run's coin-flips — the same seed always gives you
the same cave noises. `--help` lists the options.

## Running from a clone

If you would rather have the source to hand:

    git clone https://github.com/AustinGuidry/dead-air
    cd dead-air
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    ./play

## Controls

| key   | action |
|-------|--------|
| `1`–`9` | take the numbered action — someone to talk to, something to look at, or a way on |
| `L`   | listen |
| `R`   | radio basecamp |
| `X`   | look again |
| `F`   | switch the helmet lamp on or off |
| `D`   | stop the beam down — half the burn rate, half the sight |
| `C`   | swap in a spare cell |
| `N`   | new run |
| `ESC` | back to the menu |
| `Q`   | quit |

`F` is for above ground — you start in daylight with the lamp off, and the
evening does not wait for you. `D` and `C` are underground only, where the
lamp is not something you get to switch off.

## Saving

The game opens on a menu — resume, new run, controls, quit — and saves itself
after every action, so quitting and closing the terminal are the same thing as
putting it down. There is one slot and it is the run you are in. Finishing a
run, however it finishes, clears it.

The file goes wherever your machine keeps application state: on Linux
`~/.local/state/deadair/save.json`, on macOS `~/Library/Application
Support/deadair/save.json`, on Windows `%LOCALAPPDATA%\deadair\save.json`.
Setting `XDG_STATE_HOME` overrides all three. Deleting the file is a supported
way to start over.

Take your time in the first few rooms. The cave teaches you what it wants
before it asks you for anything.

You cannot see everything in the park before the light goes, and that is the
point of the park.

## Design notes

Mechanics, escalation, module layout, and tuning constants are documented in
[DESIGN.md](DESIGN.md) — **that file spoils the game**, so read it only if you
are here to work on the code rather than to play.

[RELEASING.md](RELEASING.md) covers cutting a version. It does not spoil
anything.

## License

MIT — see [LICENSE](LICENSE).
