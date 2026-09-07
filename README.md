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
half-blocks elsewhere.

## Setup

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

## Play

    ./play

Or: `.venv/bin/python -m deadair`

Pass `--seed N` to fix the run's coin-flips — the same seed always gives you
the same cave noises. `--help` lists the options.

## Controls

| key   | action |
|-------|--------|
| `1`–`9` | take the numbered action — someone to talk to, something to look at, or a way on |
| `L`   | listen |
| `R`   | radio basecamp |
| `X`   | look again |
| `D`   | stop the beam down — half the burn rate, half the sight |
| `C`   | swap in a spare cell |
| `N`   | new run |
| `Q`   | quit |

`D` and `C` are underground only.

Take your time in the first few rooms. The cave teaches you what it wants
before it asks you for anything.

You cannot see everything in the park before the light goes, and that is the
point of the park.

## Design notes

Mechanics, escalation, module layout, and tuning constants are documented in
[DESIGN.md](DESIGN.md) — **that file spoils the game**, so read it only if you
are here to work on the code rather than to play.

## License

MIT — see [LICENSE](LICENSE).
