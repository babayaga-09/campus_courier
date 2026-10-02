"""
perception.py: runs the Lab 2 HMM filter over the campus floor.

No algorithm lives here. The transition and emission models come from the lab's
WarehouseHMMEnvironment, and the forward filter is my Lab 2 hmm_filter.py, both
unchanged in core/. This file only translates between the campus map and the
shapes those two expect, and simulates a noisy walk so the dashboard has a
belief to draw.

Conventions, because the two sides disagree:
    world.py uses (x, y) = (column, row)
    the lab environment uses (r, c) = (row, column), state index = r * width + c
    lab actions are 0 North, 1 South, 2 East, 3 West
"""

import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "core"))

from hmm_environment import WarehouseHMMEnvironment  # Lab 2, instructor scaffold
from hmm_filter import HMMStateEstimator  # Lab 2, my completed filter

import world

SENSOR_ACCURACY = 0.8  # the lab's default: the wall count is right 80% of the time

_env = None


def env():
    """One shared environment, built from the campus map the planner already uses."""
    global _env
    if _env is None:
        _env = WarehouseHMMEnvironment(world.CAMPUS_MAP, sensor_accuracy=SENSOR_ACCURACY)
    return _env


def action_between(a, b):
    """Lab action index for a single step from cell a to cell b, both (x, y)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dy < 0:
        return 0  # North
    if dy > 0:
        return 1  # South
    if dx > 0:
        return 2  # East
    return 3  # West


def state_of(cell):
    """(x, y) from world.py to the lab's flat state index."""
    x, y = cell
    return env().coord_to_state(y, x)


def sample_observation(cell, rng):
    """Draw a noisy wall count for the true cell, using the lab's own emission matrix."""
    column = env().E[:, state_of(cell)]
    total = column.sum()
    if total == 0:  # a wall cell emits nothing; treat it as a dead reading
        return 0
    return int(rng.choices(range(len(column)), weights=column / total)[0])


def walk(path, seed=0):
    """
    Walk a planned route one step at a time, feeding the filter a noisy wall count
    at each step, and record what it believed.

    Returns a list of snapshots, one per step:
        true: the real (x, y)
        observation: the noisy wall count the robot got
        belief: (height, width) array of probabilities
        guess: the filter's most likely (x, y)
        correct: whether the guess matched the truth
    """
    if len(path) < 2:
        return []

    rng = random.Random(seed)
    e = env()
    estimator = HMMStateEstimator(e.num_states, e.T, e.E)

    # The filter starts uniform over the whole floor, which is the right prior when a
    # robot wakes up lost. Here it does not: it undocks from a known room, so the belief
    # starts on that cell. Everything after this point is the lab filter doing the work,
    # spreading the belief on each move and sharpening it on each wall count.
    start = np.zeros(e.num_states)
    start[state_of(tuple(path[0]))] = 1.0
    estimator.belief_state = start

    snapshots = []

    for previous, current in zip(path, path[1:]):
        action = action_between(previous, current)
        observation = sample_observation(current, rng)
        belief = estimator.bayesian_filter_step(action, observation)

        guess_r, guess_c = e.state_to_coord(int(np.argmax(belief)))
        snapshots.append({
            "true": tuple(current),
            "observation": observation,
            "belief": belief.reshape(e.height, e.width).copy(),
            "guess": (guess_c, guess_r),
            "correct": (guess_c, guess_r) == tuple(current),
        })
    return snapshots


def summary(snapshots):
    """Two numbers for the dashboard caption: how often it was right, and how sure it got."""
    if not snapshots:
        return {"steps": 0, "hit_rate": 0.0, "final_confidence": 0.0, "final_guess": None}
    hits = sum(s["correct"] for s in snapshots)
    near = sum(abs(s["guess"][0] - s["true"][0]) + abs(s["guess"][1] - s["true"][1]) <= 1
               for s in snapshots)
    return {
        "steps": len(snapshots),
        "hit_rate": hits / len(snapshots),
        "near_rate": near / len(snapshots),  # within one cell
        "final_confidence": float(snapshots[-1]["belief"].max()),
        "final_guess": snapshots[-1]["guess"],
    }


if __name__ == "__main__":
    route = world.plan_route(world.LOCATIONS["Supply Room"], world.LOCATIONS["Studio 3"])
    steps = walk([tuple(p) for p in route["path"]], seed=1)
    stats = summary(steps)
    print(f"route: {route['steps']} steps")
    print(f"exact cell guessed on {stats['hit_rate']:.0%} of steps")
    print(f"within one cell on {stats['near_rate']:.0%} of steps")
    print(f"final confidence in one cell: {stats['final_confidence']:.2f}")
    print(f"final guess {stats['final_guess']} vs true {steps[-1]['true']}")

    assert stats["steps"] == route["steps"], "one snapshot per move"
    for s in steps:
        assert abs(s["belief"].sum() - 1.0) < 1e-9, "belief must stay a distribution"
        assert s["belief"].min() >= 0, "no negative probabilities"
    assert stats["near_rate"] > 0.75, "the belief should stay near the robot"
    assert stats["final_confidence"] > 1.0 / env().num_states, "better than knowing nothing"
    print("ok")
