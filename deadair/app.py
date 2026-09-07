"""DEAD AIR — Textual front end."""

import argparse

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static

from . import art
from .content import ROOMS
from .state import Game, ROPE_TOTAL, DAYLIGHT_TOTAL, PARK_START

STYLE = {
    "title": "bold #f0b46b",
    "narr":  "#cdc6bb",
    "sound": "italic #7fa9bd",
    "radio": "#8fc98f",
    "sys":   "#8d867c",
    "alarm": "bold #dd6a58",
    "good":  "bold #a9c987",
}

BAR_FULL, BAR_EMPTY = "█", "─"

# the cave proper — the park does not count toward a survey
CAVE_ROOMS = [r for r in ROOMS.values()
              if "park" not in r.tags and r.id not in ("drowned", "stay")]
CAVE_IDS = {r.id for r in CAVE_ROOMS}

PIXEL_BUDGET = 112_000   # about a second of raymarching per frame


def bar(pct, width=14, colour="#f0b46b"):
    pct = max(0.0, min(100.0, pct))
    n = int(round(pct / 100 * width))
    return (f"[{colour}]{BAR_FULL * n}[/]"
            f"[#3a3630]{BAR_EMPTY * (width - n)}[/]")


class DeadAir(App):
    TITLE = "DEAD AIR"

    CSS = """
    Screen { background: #0d0c0b; color: #cdc6bb; }
    #topbar {
        height: 1; background: #17150f; color: #f0b46b;
        padding: 0 2; text-style: bold;
    }
    #topbar.hunted { background: #3d1512; color: #ff8f7c; }
    #viewport {
        /* content-box so the separator rule does not eat into the third */
        box-sizing: content-box;
        height: 34%; min-height: 8; background: #080807;
        border-bottom: solid #2a2723;
    }
    #viewport.gone { display: none; }
    #view { width: 100%; height: 100%; }
    #body { height: 1fr; }
    #narrative {
        width: 1fr; padding: 1 3 1 2; background: #0d0c0b;
        scrollbar-size-vertical: 0;
    }
    #narrative Static { margin: 0 0 1 0; }
    #side {
        width: 34; background: #100f0d; padding: 1 2;
        border-left: solid #2a2723; overflow-y: auto;
        scrollbar-size-vertical: 0;
    }
    #meters { height: auto; }
    #kit { height: auto; margin: 1 0 0 0; }
    #map { height: auto; margin: 1 0 0 0; color: #6d675e; }
    #actions {
        height: auto; max-height: 14; padding: 1 2;
        background: #131110; border-top: solid #2a2723;
    }
    """

    BINDINGS = [
        *[Binding(str(n), f"choose({n - 1})", str(n), show=False)
          for n in range(1, 10)],
        Binding("l", "listen", "listen"),
        Binding("r", "radio", "radio"),
        Binding("x", "look", "look"),
        Binding("d", "dim", "dim beam"),
        Binding("c", "cell", "swap cell"),
        Binding("f", "lamp", "lamp"),
        Binding("n", "restart", "new run"),
        Binding("q", "quit", "quit"),
    ]

    def __init__(self, seed=None):
        super().__init__()
        self.seed = seed
        self.game = Game(seed)
        self._view_key = None
        self._can_draw = False

    # -- layout -------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static(id="topbar")
        with Vertical(id="viewport"):
            yield self._make_view()
        with Horizontal(id="body"):
            yield VerticalScroll(id="narrative")
            with Vertical(id="side"):
                yield Static(id="meters")
                yield Static(id="kit")
                yield Static(id="map")
        yield Static(id="actions")

    def _make_view(self):
        """The image widget, or a plain Static if this terminal cannot."""
        try:
            from textual_image.widget import AutoImage
            self._can_draw = True
            return AutoImage(id="view")
        except Exception:
            self._can_draw = False
            return Static(id="view")

    def on_mount(self):
        if not self._can_draw:
            self.query_one("#viewport").add_class("gone")
        self.emit([("title", "DEAD AIR"),
                   ("sys", "Piney Ridge National Park.  18:40.  "
                           "Search and rescue callout, one subject, "
                           "nineteen hours overdue.")])
        self.emit(self.game.enter())
        self.refresh_panels()
        # the viewport has no size until the first layout has happened
        self.call_after_refresh(self.refresh_view)

    def on_resize(self, event=None):
        self._view_key = None
        self.refresh_view()

    # -- the viewport -------------------------------------------------------

    def refresh_view(self):
        """Redraw the lamp's-eye view, if what it would show has changed."""
        if not self._can_draw:
            return
        g = self.game
        view = self.query_one("#view")
        cols, rows = view.size.width, view.size.height
        if cols < 8 or rows < 3:
            return
        w, h = self._pixels(cols, rows)
        if g.phase == "park":
            # the lamp is off until you switch it on, and the picture has to
            # agree with that or you get a beam in full daylight
            band = art.light_band(100.0 if g.lamp_on else 0.0)
            sky = art.sky_band(g.daylight)
        else:
            band, sky = art.light_band(g.reach), 4
        key = (g.here, band, sky, w, h)
        if key == self._view_key:
            return
        self._view_key = key
        self._draw(*key)

    @staticmethod
    def _pixels(cols, rows):
        """Pixel size to render for a viewport of `cols` x `rows` cells.

        A cell is roughly twice as tall as it is wide, so the aspect that
        fills the viewport undistorted is cols : rows*2. Sizes are rounded
        off so the render cache actually gets hits, and held under a pixel
        budget — a wide short viewport would otherwise ask for a frame that
        takes several seconds to raymarch.
        """
        def fit(width):
            width = max(256, min(960, (width // 32) * 32))
            return width, max(96, min(320,
                              int(round(width * rows * 2 / cols / 8)) * 8))

        w, h = fit(cols * 6)
        if w * h > PIXEL_BUDGET:
            w, h = fit(int(w * (PIXEL_BUDGET / (w * h)) ** 0.5))
        return w, h

    @work(thread=True, exclusive=True, group="view")
    def _draw(self, room, band, sky, w, h):
        try:
            img = art.frame(room, band, sky, w, h)
        except Exception:
            return
        self.call_from_thread(self._show, img)

    def _show(self, img):
        try:
            self.query_one("#view").image = img
        except Exception:
            return
        # draw the rooms you could walk into next while nothing else is
        # happening, so that moving does not sit on a stale frame
        self._prefetch(self._upcoming())

    def _upcoming(self):
        """Frames worth having ready before they are asked for."""
        if not self._view_key:
            return []
        here, band, sky, w, h = self._view_key
        keys = [(x.to, band, sky, w, h) for x in self.game.room.exits
                if x.to in art.SCENES]
        if self.game.phase == "park":
            # F re-lights this same room, and the light keeps failing, so
            # both are one keystroke or a few minutes away
            other = art.light_band(0.0 if self.game.lamp_on else 100.0)
            keys.insert(0, (here, other, sky, w, h))
            if sky > 0:
                keys.insert(1, (here, band, sky - 1, w, h))
        return keys

    @work(thread=True, exclusive=True, group="prefetch")
    def _prefetch(self, keys):
        for key in keys:
            try:
                art.frame(*key)
            except Exception:
                return

    # -- output -------------------------------------------------------------

    def emit(self, events):
        log = self.query_one("#narrative", VerticalScroll)
        faint = self.game.layers <= 1 and not self.game.ending
        for kind, text in events:
            style = STYLE.get(kind, "#cdc6bb")
            if faint and kind in ("narr", "title"):
                style = "#6d675e"
            if kind == "title":
                text = f"── {text} " + "─" * max(0, 46 - len(text))
            log.mount(Static(f"[{style}]{text}[/]"))
        children = log.children
        if len(children) > 240:
            for w in list(children)[:60]:
                w.remove()
        self.call_after_refresh(log.scroll_end, animate=False)

    # -- side panels --------------------------------------------------------

    def refresh_panels(self):
        g = self.game
        if g.phase == "park":
            self.refresh_park()
        else:
            self.refresh_cave()
        self.refresh_actions()
        self.refresh_view()

    def refresh_park(self):
        g = self.game
        top = self.query_one("#topbar", Static)
        top.set_class(False, "hunted")
        top.update(f"DEAD AIR   ·   {g.room.name}   ·   {g.wall_clock()}"
                   f"   ·   Act One")

        light_col = ("#f0b46b" if g.daylight > 55 else
                     "#d3c07a" if g.daylight > 25 else "#dd6a58")
        gone = (PARK_START + DAYLIGHT_TOTAL) % (24 * 60)
        lines = [
            f"[#8d867c]LIGHT [/] {bar(g.daylight, 14, light_col)}"
            f" {g.daylight:5.1f}%",
            f"[#8d867c]      [/] [#5a554e]last light {gone // 60:02d}:"
            f"{gone % 60:02d}[/]",
            f"[#8d867c]SIGNAL[/] {bar(100, 14, '#8fc98f')} {'strong':>5}",
        ]
        lamp = ("[#f0b46b]on[/]" if g.lamp_on else "[#5a554e]off[/]")
        warn = ("  [#dd6a58]you need it[/]"
                if not g.lamp_on and g.daylight < 25 else "")
        lines.append(f"[#8d867c]LAMP  [/] [#5a554e]helmet lamp[/] {lamp}{warn}")
        self.query_one("#meters", Static).update("\n".join(lines))

        asked = sum(min(self.game.said.get(p.name, 0), len(p.beats))
                    for r in ROOMS.values() for p in r.people)
        beats = sum(len(p.beats) for r in ROOMS.values() for p in r.people)
        clues = [c for r in ROOMS.values() for c in r.clues]
        seen = sum(1 for c in clues if f"seen:{c.label}" in g.flags)
        kit = ["[#8d867c]NOTEBOOK[/]",
               f"  heard         [#cdc6bb]{asked}[/][#5a554e]/{beats}[/]",
               f"  examined      [#cdc6bb]{seen}[/][#5a554e]/{len(clues)}[/]"]
        kit.append("  cleared to go [#a9c987]yes[/]" if "ready" in g.flags
                   else "  cleared to go [#5a554e]not yet[/]")
        self.query_one("#kit", Static).update("\n".join(kit))
        self.query_one("#map", Static).update(
            "[#8d867c]APPROACH[/]\n" + self.render_approach())

    def render_approach(self):
        """A line of the walk in, rather than a survey you have not made."""
        order = ["trailhead", "ridge_trail", "blowdown", "hollow", "basecamp"]
        names = {"trailhead": "trailhead", "ridge_trail": "ridge trail",
                 "blowdown": "the blowdown", "hollow": "the hollow",
                 "basecamp": "wolf sink"}
        out = []
        for rid in order:
            if rid == self.game.here:
                out.append(f"  [bold #f0b46b]@[/] {names[rid]}")
            elif rid in self.game.visited:
                out.append(f"  [#a89478]O[/] [#6d675e]{names[rid]}[/]")
            else:
                out.append(f"  [#4a453f].[/] [#4a453f]{names[rid]}[/]")
        return "\n".join(out)

    def refresh_cave(self):
        g = self.game
        bar_text = (f"DEAD AIR   ·   {g.room.name}   ·   {g.depth} m   "
                    f"·   {g.clock()} elapsed")
        hunted = g.pursuit is not None and not g.ending
        if hunted:
            from .state import PURSUIT_LIMIT
            left = max(0, PURSUIT_LIMIT - g.pursuit)
            bar_text += f"      ⟨ GET OUT · {left} min ⟩"
        top = self.query_one("#topbar", Static)
        top.set_class(hunted, "hunted")
        top.update(bar_text)

        sig = {"clear": ("strong", 100, "#8fc98f"),
               "weak": ("weak", 40, "#d3c07a"),
               "gone": ("none", 0, "#dd6a58")}[g.signal]
        lamp_col = "#f0b46b" if g.lamp > 40 else (
                   "#d3c07a" if g.lamp > 15 else "#dd6a58")
        air_col = "#8fc98f" if g.air > 50 else (
                  "#d3c07a" if g.air > 25 else "#dd6a58")

        beam = "[#8d867c]stopped down[/]" if g.dim else "wide"
        lines = [
            f"[#8d867c]LAMP  [/] {bar(g.lamp, 14, lamp_col)} {g.lamp:5.1f}%",
            f"[#8d867c]      [/] [#5a554e]beam {beam}[/]",
            f"[#8d867c]AIR   [/] {bar(g.air, 14, air_col)} {g.air:5.1f}%",
            f"[#8d867c]ROPE  [/] {bar(g.rope / ROPE_TOTAL * 100, 14, '#8ba9c9')}"
            f" {g.rope:3d} m",
            f"[#8d867c]SIGNAL[/] {bar(sig[1], 14, sig[2])} {sig[0]:>5}",
        ]
        self.query_one("#meters", Static).update("\n".join(lines))
        self.query_one("#map", Static).update(self.render_map())

        kit = [f"[#8d867c]KIT[/]"]
        kit.append(f"  spare cells   [#cdc6bb]{g.cells}[/]")
        kit.append("  helmet        [#a9c987]recovered[/]"
                   if "took_find" in g.flags else
                   "  helmet        [#5a554e]—[/]")
        kit.append(f"  passages      [#cdc6bb]{self.surveyed()}[/#cdc6bb]"
                   f"[#5a554e]/{len(CAVE_ROOMS)}[/]")
        self.query_one("#kit", Static).update("\n".join(kit))

    def surveyed(self):
        return len(self.game.visited & CAVE_IDS)

    def render_map(self):
        g = self.game
        placed = {r.id: (r.mx * 4, r.my * 2) for r in CAVE_ROOMS}
        w = max(x for x, _ in placed.values()) + 1
        h = max(y for _, y in placed.values()) + 1
        grid = [[" "] * w for _ in range(h)]

        known = set(g.visited) & CAVE_IDS
        for rid in list(known):
            for x in ROOMS[rid].exits:
                if x.to in placed:
                    known.add(x.to)

        for rid in g.visited & CAVE_IDS:
            ax, ay = placed[rid]
            for x in ROOMS[rid].exits:
                if x.to not in placed:
                    continue
                bx, by = placed[x.to]
                if ay == by:
                    for cx in range(min(ax, bx) + 1, max(ax, bx)):
                        grid[ay][cx] = "─"
                elif ax == bx:
                    for cy in range(min(ay, by) + 1, max(ay, by)):
                        grid[cy][ax] = "│"
                else:
                    grid[(ay + by) // 2][(ax + bx) // 2] = "╱"

        for rid, (px, py) in placed.items():
            if rid == g.here:
                grid[py][px] = "@"
            elif rid in g.visited:
                grid[py][px] = "O"
            elif rid in known:
                grid[py][px] = "."

        while grid and not "".join(grid[-1]).strip():
            grid.pop()
        out = ["[#8d867c]SURVEY[/]"]
        for row in grid:
            line = "".join(row).rstrip()
            line = (line.replace("@", "[bold #f0b46b]@[/]")
                        .replace("O", "[#a89478]O[/]")
                        .replace(".", "[#4a453f].[/]"))
            out.append("  " + line)
        return "\n".join(out)

    def refresh_actions(self):
        g = self.game
        if g.ending:
            self.query_one("#actions", Static).update(
                "[#8d867c]  N  new run       Q  quit[/]")
            return
        rows = []
        for i, (kind, label, ok, why, _) in enumerate(g.choices()):
            key = f"[bold #f0b46b]{i + 1}[/]" if ok else "[#4a453f]-[/]"
            mark = {"talk": "[#7fa9bd]›[/] ", "clue": "[#8d867c]·[/] "}.get(
                kind, "  ")
            if ok:
                note = f"  [#5a554e]{why}[/]" if why else ""
                rows.append(f" {key} {mark}{label}{note}")
            else:
                rows.append(f" {key} {mark}[#4a453f]{label}  ({why})[/]")
        rows.append("")
        if g.phase == "park":
            rows.append("[#8d867c] L[/] listen   [#8d867c]R[/] radio   "
                        "[#8d867c]X[/] look again   [#8d867c]F[/] lamp")
        else:
            rows.append("[#8d867c] L[/] listen   [#8d867c]R[/] radio   "
                        "[#8d867c]X[/] look again   [#8d867c]D[/] dim beam   "
                        "[#8d867c]C[/] swap cell")
        self.query_one("#actions", Static).update("\n".join(rows))

    # -- actions ------------------------------------------------------------

    def after(self, events):
        self.emit(events)
        if self.game.ending:
            self.show_ending()
        self.refresh_panels()

    def show_ending(self):
        g = self.game
        head, kind, body = g.ending_body()
        deepest = min((ROOMS[r].depth for r in g.visited & CAVE_IDS),
                      default=0)
        ev = [("title", head), (kind, body)]
        note = g.ending_note()
        if note:
            ev.append(("alarm", note))
        ev.append(("sys", f"Out at {g.surface_clock()}.  Elapsed {g.clock()}. "
                          f" Deepest point {deepest} m.  "
                          f"{self.surveyed()} passages surveyed."))
        ev.append(("sys", "N for a new run.  Q to quit."))
        self.emit(ev)

    def action_choose(self, idx: int):
        if self.game.ending:
            return
        self.after(self.game.act(idx))

    def action_listen(self):
        if not self.game.ending:
            self.after(self.game.listen())

    def action_radio(self):
        if not self.game.ending:
            self.after(self.game.radio())

    def action_look(self):
        if not self.game.ending:
            self.after(self.game.look())

    def action_dim(self):
        if not self.game.ending and self.game.phase == "cave":
            self.after(self.game.toggle_dim())

    def action_lamp(self):
        if not self.game.ending:
            self.after(self.game.toggle_lamp())

    def action_cell(self):
        if not self.game.ending and self.game.phase == "cave":
            self.after(self.game.swap_cell())

    def action_restart(self):
        self.game = Game(self.seed)
        self._view_key = None
        log = self.query_one("#narrative", VerticalScroll)
        for w in list(log.children):
            w.remove()
        self.emit([("title", "DEAD AIR")])
        self.emit(self.game.enter())
        self.refresh_panels()


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="deadair",
        description="DEAD AIR — a first-person cave-horror game for the "
                    "terminal.")
    p.add_argument("--seed", type=int, metavar="N", default=None,
                   help="fix the run's coin-flips — which ambience fires, "
                        "which line basecamp comes back with, which of your "
                        "own past actions the cave plays back at you. The "
                        "cave itself does not change. Survives a new run.")
    return p.parse_args(argv)


def main(argv=None):
    DeadAir(seed=parse_args(argv).seed).run()
