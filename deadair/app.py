"""DEAD AIR — Textual front end."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static

from .content import ROOMS
from .state import Game, ENDINGS, ROPE_TOTAL

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
        Binding("1", "choose(0)", "1", show=False),
        Binding("2", "choose(1)", "2", show=False),
        Binding("3", "choose(2)", "3", show=False),
        Binding("4", "choose(3)", "4", show=False),
        Binding("5", "choose(4)", "5", show=False),
        Binding("l", "listen", "listen"),
        Binding("r", "radio", "radio"),
        Binding("x", "look", "look"),
        Binding("d", "dim", "dim beam"),
        Binding("c", "cell", "swap cell"),
        Binding("n", "restart", "new run"),
        Binding("q", "quit", "quit"),
    ]

    def __init__(self, seed=None):
        super().__init__()
        self.seed = seed
        self.game = Game(seed)

    # -- layout -------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static(id="topbar")
        with Horizontal(id="body"):
            yield VerticalScroll(id="narrative")
            with Vertical(id="side"):
                yield Static(id="meters")
                yield Static(id="kit")
                yield Static(id="map")
        yield Static(id="actions")

    def on_mount(self):
        self.emit([("title", "DEAD AIR"),
                   ("sys", "Piney Ridge National Park.  02:14.  "
                           "Search and rescue callout, one subject, "
                           "nineteen hours overdue.")])
        self.emit(self.game.enter())
        self.refresh_panels()

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
        kit.append(f"  passages      [#cdc6bb]{len(g.visited)}[/#cdc6bb]"
                   f"[#5a554e]/16[/]")
        self.query_one("#kit", Static).update("\n".join(kit))

        self.refresh_actions()

    def render_map(self):
        g = self.game
        placed = {r.id: (r.mx * 4, r.my * 2) for r in ROOMS.values()
                  if r.id not in ("drowned", "stay")}
        w = max(x for x, _ in placed.values()) + 1
        h = max(y for _, y in placed.values()) + 1
        grid = [[" "] * w for _ in range(h)]

        known = set(g.visited)
        for rid in list(g.visited):
            for x in ROOMS[rid].exits:
                if x.to in placed:
                    known.add(x.to)

        for rid in g.visited:
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
        for i, (x, ok, why) in enumerate(g.exits()):
            key = f"[bold #f0b46b]{i + 1}[/]" if ok else "[#4a453f]-[/]"
            if ok:
                note = f"  [#5a554e]{why}[/]" if why else ""
                rows.append(f" {key}  {x.label}{note}")
            else:
                rows.append(f" {key}  [#4a453f]{x.label}  ({why})[/]")
        rows.append("")
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
        head, kind, body = ENDINGS[self.game.ending]
        g = self.game
        self.emit([
            ("title", head),
            (kind, body),
            ("sys", f"Elapsed {g.clock()}.  Deepest point "
                    f"{min(ROOMS[r].depth for r in g.visited)} m.  "
                    f"{len(g.visited)} passages surveyed."),
            ("sys", "N for a new run.  Q to quit."),
        ])

    def action_choose(self, idx: int):
        if self.game.ending:
            return
        self.after(self.game.move(idx))

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
        if not self.game.ending:
            self.after(self.game.toggle_dim())

    def action_cell(self):
        if not self.game.ending:
            self.after(self.game.swap_cell())

    def action_restart(self):
        self.game = Game(self.seed)
        log = self.query_one("#narrative", VerticalScroll)
        for w in list(log.children):
            w.remove()
        self.emit([("title", "DEAD AIR")])
        self.emit(self.game.enter())
        self.refresh_panels()


def main():
    DeadAir().run()
