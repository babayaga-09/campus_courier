"""
world.py: the campus floor map, and thin adapters that feed it to the
reused lab algorithms in core/. No algorithm logic lives here.

"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "core"))

from environment import SurgicalLabEnvironment  # Lab 1 (A*)
from planner import ForkliftPlanner  # Lab 1 (A*)

CAMPUS_MAP = """
######################
#B....#.......#......#
#.##..#.#####.#.####.#
#.#...~~~.....#..P.#.#
#.#.###.##.##.###..#.#
#...#...#...#....#...#
###.#.###.#.####.###.#
#.....#...#....#.....#
#.###.#.#######S####.#
#...#.....gggg.......#
#.#.####.#gggg######.#
#.#......#..........X#
######################
"""

ROWS = CAMPUS_MAP.strip().splitlines()
HEIGHT, WIDTH = len(ROWS), len(ROWS[0])

LOCATION_CODES = {"B": "Supply Room", "X": "Studio 3", "P": "Library", "S": "Corridor B"}


def cells(char):
    return {(x, y) for y, row in enumerate(ROWS) for x, c in enumerate(row) if c == char}


LOCATIONS = {name: next(iter(cells(code))) for code, name in LOCATION_CODES.items()}
WET = cells("~")
GAS = cells("g")


def make_nav_env(avoid_quiet=False):
    """Lab 1's environment with the campus geometry swapped in. Robots that aren't
    quiet-wheeled see the quiet zone as solid rock, so A* routes around it."""
    env = SurgicalLabEnvironment(map_type="trivial")  # blank preset; geometry replaced below
    env.width, env.height = WIDTH, HEIGHT
    env.grid = [[1 if c == "#" or (avoid_quiet and c == "g") else 0 for c in row] for row in ROWS]
    return env


def plan_route(start, goal, quiet_wheels=True):
    env = make_nav_env(avoid_quiet=not quiet_wheels)
    path, expanded, seconds = ForkliftPlanner(env).a_star(tuple(start), tuple(goal), "manhattan")
    return {
        "reachable": bool(path),
        "path": [list(p) for p in path],
        "steps": max(len(path) - 1, 0),
        "nodes_expanded": expanded,
        "wet_cells_on_route": sum(p in WET for p in path),
        "quiet_cells_on_route": sum(p in GAS for p in path),
        "quiet_zone": "allowed (quiet-wheeled)" if quiet_wheels else "avoided (not quiet-wheeled)",
    }


if __name__ == "__main__":
    for start_name, start in LOCATIONS.items():
        for name, goal in LOCATIONS.items():
            r = plan_route(start, goal)
            safe = plan_route(start, goal, quiet_wheels=False)
            assert r["reachable"] and safe["reachable"], f"{start_name} -> {name} unreachable"
            assert safe["quiet_cells_on_route"] == 0, f"{start_name} -> {name} enters quiet zone"
            if start_name == "Supply Room":
                print(f"Supply Room -> {name}: {r['steps']} steps (gas={r['quiet_cells_on_route']}), "
                      f"not quiet-wheeled: {safe['steps']} steps (gas={safe['quiet_cells_on_route']})")
