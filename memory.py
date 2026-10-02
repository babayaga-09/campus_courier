"""
memory.py: SQLite record of the delivery operation (robots, supplies, task log).
Same approach as the ReAct lab's fake_db.py: a real on-disk SQLite file,
rebuilt from seed data by reset().
"""

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from world import LOCATIONS

DB_PATH = Path(__file__).parent / "campus_courier.db"

SCHEMA = """
CREATE TABLE robots (
    robot_id    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    capacity    INTEGER NOT NULL,   -- kg
    battery_pct INTEGER NOT NULL,
    min_battery INTEGER NOT NULL,
    drain_rate  REAL NOT NULL,      -- battery % used per kg carried
    quiet_wheels  INTEGER NOT NULL,   -- 1 = allowed through the quiet zone
    x INTEGER NOT NULL, y INTEGER NOT NULL
);
CREATE TABLE supplies (
    item   TEXT PRIMARY KEY,
    weight INTEGER NOT NULL,        -- kg per unit
    stock  INTEGER NOT NULL
);
CREATE TABLE tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    order_text  TEXT NOT NULL,
    robot_id    TEXT NOT NULL,
    items       TEXT NOT NULL,
    destination TEXT NOT NULL,
    route_steps INTEGER NOT NULL,
    status      TEXT NOT NULL
);
"""

bx, by = LOCATIONS["Supply Room"]
ROBOTS = [
    ("CB-1", "Atlas",   30, 85, 20, 0.5, 1, bx, by),
    ("CB-2", "Comet", 20, 40, 20, 1.0, 0, bx + 1, by),
    ("CB-3", "Pixel", 10, 15, 20, 0.3, 1, bx, by + 1),
]
SUPPLIES = [
    ("projector", 12, 6),
    ("lab_kit", 5, 4),
    ("water_case", 8, 5),
    ("whiteboard", 18, 1),
    ("marker_box", 2, 10),
]


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def reset():
    DB_PATH.unlink(missing_ok=True)
    with closing(_connect()) as conn, conn:  # closes the file handle and commits
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO robots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", ROBOTS)
        conn.executemany("INSERT INTO supplies VALUES (?, ?, ?)", SUPPLIES)


def _rows(sql):
    if not DB_PATH.exists():
        reset()
    with closing(_connect()) as conn, conn:  # closes the file handle and commits
        return [dict(r) for r in conn.execute(sql)]


def robots():
    return _rows("SELECT * FROM robots ORDER BY robot_id")


def supplies():
    return _rows("SELECT * FROM supplies ORDER BY item")


def tasks():
    return _rows("SELECT * FROM tasks ORDER BY id DESC")


def record_dispatch(order_text, destination, packages, assignments, routes):
    """Commit a verified plan: log tasks, draw down stock, drain battery, move robots."""
    weights = {p["id"]: p["weight"] for p in packages}
    fleet = {r["robot_id"]: r for r in robots()}
    goal = LOCATIONS[destination]
    with closing(_connect()) as conn, conn:  # closes the file handle and commits
        for robot_id in sorted(set(assignments.values())):
            items = [pid for pid, rid in assignments.items() if rid == robot_id]
            load = sum(weights[i] for i in items)
            new_battery = int(fleet[robot_id]["battery_pct"] - fleet[robot_id]["drain_rate"] * load)
            conn.execute(
                "INSERT INTO tasks (order_text, robot_id, items, destination, route_steps, status) "
                "VALUES (?, ?, ?, ?, ?, 'dispatched')",
                (order_text, robot_id, json.dumps(items), destination, routes[robot_id]["steps"]),
            )
            conn.execute("UPDATE robots SET battery_pct = ?, x = ?, y = ? WHERE robot_id = ?",
                         (new_battery, goal[0], goal[1], robot_id))
        for pid in assignments:
            conn.execute("UPDATE supplies SET stock = stock - 1 WHERE item = ?", (pid.split("#")[0],))
