"""
ui_prototype.py -- GUI prototype for the proposal review (NOT the finished system).

Tkinter only, so it runs with a plain `python ui_prototype.py`: no Streamlit, no
solver, no LLM. The panels draw canned data. Anything tagged TODO in the window
is a layer that is not wired up yet.

    python ui_prototype.py          open the window
    python ui_prototype.py --smoke  build the widgets and exit (sanity check)
"""

import sys
import tkinter as tk
from tkinter import ttk

BG = "#f4f2ed"
INK = "#23201c"
PENCIL = "#6f6a62"
LINE = "#c9c3b8"
ACCENT = "#b4670b"
OK = "#2f6f4e"
BAD = "#b3402f"

# Same map shape as world.py, kept as a literal so this file stands alone.
#   # rock   . tunnel   ~ flooded   * quiet zone
CAMPUS_MAP = [
    "###############",
    "#B....#.......#",
    "#.###.#.####..#",
    "#.#~~.#.#..#..#",
    "#.#.#.*.#.##..#",
    "#...#...#....P#",
    "#.###.###.###.#",
    "#.....#S#...#.#",
    "###.###.###.#.#",
    "#...........#G#",
    "###############",
]
CELL = 22

FLEET = [
    ("CB-1", "Atlas", 85, 30, "quiet-wheeled"),
    ("CB-2", "Comet", 40, 20, "not quiet-wheeled"),
    ("CB-3", "Pixel", 15, 10, "quiet-wheeled, below min battery"),
]

# Canned traces. The real coordinator writes these from live tool calls.
ROUTINE = [
    ("tool", "get_fleet_status", "3 robots known, CB-3 disabled (15% battery)"),
    ("tool", "get_inventory", "projector 8kg, lab_kit 4kg, water 12kg"),
    ("tool", "plan_route", "CB-1 -> Studio 3, 29 steps"),
    ("sat", "verify_dispatch_smt", "2 projectors + 1 lab kit -> CB-1"),
    ("done", "finish", "dispatched, task written to the log"),
]
OVERLOAD = [
    ("tool", "get_fleet_status", "usable capacity 50kg (CB-1 30 + CB-2 20)"),
    ("tool", "get_inventory", "3 projectors 24kg + whiteboard 30kg = 54kg"),
    ("unsat", "verify_dispatch_smt", "54kg requested > 50kg usable -- UNSAT"),
    ("note", "replan", "oxygen is life-critical, so drop the whiteboard"),
    ("sat", "verify_dispatch_smt", "3 projectors -> CB-1, CB-2"),
    ("done", "finish", "dispatched, whiteboard left at Supply Room"),
]
TAGS = {
    "tool": ("TOOL ", PENCIL),
    "sat": ("Z3 SAT ", OK),
    "unsat": ("Z3 UNSAT ", BAD),
    "note": ("THOUGHT ", ACCENT),
    "done": ("COMMIT ", INK),
}


class Prototype(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CampusCourier -- Campus Delivery Desk  [UI prototype v0.1]")
        self.configure(bg=BG)
        self.geometry("980x660")
        self.minsize(860, 600)

        self._header()
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self._fleet(body)
        self._map(body)
        self._log(body)
        self._order()
        self._statusbar()

    # -- header ------------------------------------------------------------
    def _header(self):
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=14, pady=(12, 8))
        tk.Label(bar, text="MINE RESCUE COMMAND", bg=BG, fg=INK,
                 font=("Segoe UI", 18, "bold")).pack(side="left")
        tk.Label(bar, text="  UI PROTOTYPE v0.1 -- panels marked TODO are not wired up yet",
                 bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(side="left", pady=(6, 0))
        self.verdict = tk.Label(bar, text="last Z3 verdict: none yet", bg=BG, fg=PENCIL,
                                font=("Consolas", 10))
        self.verdict.pack(side="right", pady=(6, 0))

    # -- left: fleet -------------------------------------------------------
    def _fleet(self, parent):
        box = self._panel(parent, "FLEET", side="left", width=250)
        for rid, name, batt, cap, note in FLEET:
            row = tk.Frame(box, bg="white")
            row.pack(fill="x", padx=10, pady=(8, 0))
            tk.Label(row, text=f"{rid}  {name}", bg="white", fg=INK,
                     font=("Segoe UI", 10, "bold")).pack(anchor="w")
            bar = tk.Canvas(row, height=8, bg="white", highlightthickness=0)
            bar.pack(fill="x", pady=2)
            bar.create_rectangle(0, 0, 220, 8, fill="#e7e3da", outline=LINE)
            bar.create_rectangle(0, 0, 2.2 * batt, 8,
                                 fill=BAD if batt < 20 else PENCIL, outline="")
            tk.Label(row, text=f"battery {batt}%   capacity {cap}kg", bg="white",
                     fg=PENCIL, font=("Segoe UI", 8)).pack(anchor="w")
            tk.Label(row, text=note, bg="white", fg=PENCIL,
                     font=("Segoe UI", 8, "italic")).pack(anchor="w")
        tk.Label(box, text="live positions: TODO (comes from the HMM filter)",
                 bg="white", fg=ACCENT, font=("Segoe UI", 8)).pack(anchor="w", padx=10, pady=10)

    # -- middle: map -------------------------------------------------------
    def _map(self, parent):
        box = self._panel(parent, "MINE MAP + A* ROUTE", side="left", width=360)
        w, h = len(CAMPUS_MAP[0]) * CELL, len(CAMPUS_MAP) * CELL
        cv = tk.Canvas(box, width=w, height=h, bg="white", highlightthickness=0)
        cv.pack(padx=10, pady=8)
        fills = {"#": "#d9d4c9", "~": "#bcd3e0", "*": "#dcdba8"}
        for r, line in enumerate(CAMPUS_MAP):
            for c, ch in enumerate(line):
                x, y = c * CELL, r * CELL
                cv.create_rectangle(x, y, x + CELL, y + CELL,
                                    fill=fills.get(ch, "white"), outline="#eceae4")
                if ch in "BPG":
                    cv.create_oval(x + 6, y + 6, x + CELL - 6, y + CELL - 6,
                                   fill=ACCENT if ch == "B" else "white", outline=INK)
                    cv.create_text(x + CELL / 2, y - 2, text=ch, fill=PENCIL,
                                   font=("Segoe UI", 7, "bold"))
        # placeholder route: straight dashed line, the planner will replace it
        cv.create_line(1.5 * CELL, 1.5 * CELL, 1.5 * CELL, 9.5 * CELL,
                       7.5 * CELL, 9.5 * CELL, 7.5 * CELL, 7.5 * CELL,
                       fill=ACCENT, width=2, dash=(4, 3))
        self.mapnote = tk.Label(box, text="route shown is a placeholder -- A* not called from here",
                                bg="white", fg=ACCENT, font=("Segoe UI", 8))
        self.mapnote.pack(anchor="w", padx=10)
        tk.Label(box, text="B base camp   P pump room   G gallery 3   S shaft B\n"
                           "blue = just mopped (wheels slip)   olive = quiet zone (silent wheels)",
                 bg="white", fg=PENCIL, font=("Segoe UI", 8), justify="left"
                 ).pack(anchor="w", padx=10, pady=(4, 0))
        tk.Label(box, text="belief heatmap: TODO", bg="white", fg=ACCENT,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(6, 10))

    # -- right: reasoning log ---------------------------------------------
    def _log(self, parent):
        box = self._panel(parent, "COORDINATOR REASONING", side="left", width=320)
        self.text = tk.Text(box, wrap="word", bg="white", fg=INK, relief="flat",
                            font=("Consolas", 9), height=18, padx=10, pady=8)
        self.text.pack(fill="both", expand=True, padx=4, pady=4)
        for kind, (_, colour) in TAGS.items():
            self.text.tag_configure(kind, foreground=colour, font=("Consolas", 9, "bold"))
        self.text.tag_configure("body", foreground=PENCIL)
        self._say("note", "no order yet",
                  "type an order below, or press a demo button. "
                  "this prototype replays a canned trace -- the real loop calls Z3.")

    # -- bottom: order entry ----------------------------------------------
    def _order(self):
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=14, pady=(0, 6))
        self.entry = ttk.Entry(bar, font=("Segoe UI", 10))
        self.entry.insert(0, "get 2 projectors and a lab kit to Studio 3")
        self.entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.entry.bind("<Return>", lambda _e: self.run(ROUTINE))
        ttk.Button(bar, text="Send", command=lambda: self.run(ROUTINE)).pack(side="left", padx=6)
        ttk.Button(bar, text="Demo: routine", command=lambda: self.run(ROUTINE)).pack(side="left")
        ttk.Button(bar, text="Demo: overload (UNSAT)",
                   command=lambda: self.run(OVERLOAD)).pack(side="left", padx=6)

    def _statusbar(self):
        bar = tk.Frame(self, bg="#e9e5dd")
        bar.pack(fill="x", side="bottom")
        built = "built: LLM loop + Z3 verifier + A* routing + SQLite memory"
        todo = "TODO: HMM belief heatmap  |  adaptive pilot (MDP/RL)  |  Corridor B conflict"
        tk.Label(bar, text=built, bg="#e9e5dd", fg=OK, font=("Segoe UI", 8)).pack(side="left", padx=10)
        tk.Label(bar, text=todo, bg="#e9e5dd", fg=ACCENT, font=("Segoe UI", 8)).pack(side="right", padx=10)

    # -- helpers -----------------------------------------------------------
    def _panel(self, parent, title, side, width):
        outer = tk.Frame(parent, bg=LINE, padx=1, pady=1)
        outer.pack(side=side, fill="both", expand=True, padx=4)
        inner = tk.Frame(outer, bg="white", width=width)
        inner.pack(fill="both", expand=True)
        tk.Label(inner, text=title, bg="white", fg=PENCIL,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
        return inner

    def _say(self, kind, head, body):
        label, _ = TAGS[kind]
        self.text.insert("end", f"{label}{head}\n", kind)
        self.text.insert("end", f"    {body}\n\n", "body")
        self.text.see("end")

    def run(self, trace):
        """Replay a canned trace, one step every 600ms so it reads like a live run."""
        self.text.delete("1.0", "end")
        order = self.entry.get().strip() or "(no order text)"
        self._say("note", "order received", order)
        self.verdict.config(text="last Z3 verdict: running...", fg=PENCIL)
        for i, (kind, tool, detail) in enumerate(trace):
            self.after(600 * (i + 1), self._step, kind, tool, detail)

    def _step(self, kind, tool, detail):
        self._say(kind, tool, detail)
        if kind == "sat":
            self.verdict.config(text="last Z3 verdict: SAT", fg=OK)
        elif kind == "unsat":
            self.verdict.config(text="last Z3 verdict: UNSAT -> replanning", fg=BAD)


if __name__ == "__main__":
    app = Prototype()
    if "--smoke" in sys.argv:  # build the widgets, prove nothing raised, exit
        app.update()
        print("ok: prototype window built")
        app.destroy()
    else:
        app.mainloop()
