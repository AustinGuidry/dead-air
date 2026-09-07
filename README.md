# DEAD AIR

A first-person cave-horror game for the terminal. You are a search-and-rescue
officer entering an unsurveyed sink in Piney Ridge National Park, nineteen
hours behind a solo caver who did not come out.

Built with [Textual](https://textual.textualize.io/). Runs in kitty.

## Setup

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

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

Take your time in the first few rooms. The cave teaches you what it wants
before it asks you for anything.

## Design notes

Mechanics, escalation, module layout, and tuning constants are documented in
[DESIGN.md](DESIGN.md) — **that file spoils the game**, so read it only if you
are here to work on the code rather than to play.

## License

MIT — see [LICENSE](LICENSE).
