"""
test_agent.py - checks that the safety story the demo tells is actually true.
Run:  .venv\\Scripts\\python test_agent.py     (offline, no API key, uses a throwaway database)
"""

import tempfile
from pathlib import Path

import agent
import memory
import world

memory.DB_PATH = Path(tempfile.gettempdir()) / "campus_courier_test.db"  # never touch the demo database


def flags(run):
    return [t["flag"] for t in run["trace"]]


def test_routine_dispatch():
    memory.reset()
    run = agent.run_agent(agent.scripted_delivery(), "Get 2 projectors and a lab kit to Studio 3.")
    assert run["ok"], run["final_answer"]
    assert flags(run)[-2:] == ["sat", "finish"]
    assert all(run["routes"][r]["reachable"] for r in set(run["assignments"].values()))


def test_overload_is_rejected_then_relaxed():
    memory.reset()
    run = agent.run_agent(agent.scripted_delivery(overloaded=True), "Send 3 projectors and the whiteboard.")
    assert run["ok"]
    assert flags(run).index("unsat") < flags(run).index("sat")
    assert not any(p.startswith("whiteboard") for p in run["assignments"])


def test_low_battery_robot_is_refused():
    memory.reset()
    run = agent.run_agent(agent.scripted_low_battery(), "Use Pixel to carry a lab kit to the Library.")
    assert not run["ok"] and "unsat" in flags(run)


def test_invented_numbers_and_unverified_finish_are_blocked():
    memory.reset()
    liar = agent.ScriptedLLM([
        {"thought": "", "action": "verify_dispatch_smt", "action_input": {
            "packages": [{"id": "projector#1", "weight": 12}],
            "agvs": [{"id": "CB-3", "capacity": 10, "battery_pct": 95, "min_battery": 20, "drain_rate": 0.3}]}},
        {"thought": "", "action": "finish", "action_input": {
            "final_answer": "done", "destination": "Studio 3", "assignments": {"projector#1": "CB-3"}}},
        {"thought": "", "action": "finish", "action_input": {"final_answer": "cannot"}},
    ])
    run = agent.run_agent(liar, "test")
    assert flags(run) == ["blocked", "blocked", "finish"] and not run["ok"]
    assert run["trace"][0]["observation"]["status"] == "REJECTED_UNGROUNDED"


def test_repeating_an_unsat_plan_is_blocked():
    memory.reset()
    fleet = [{"id": r["robot_id"], "capacity": r["capacity"], "battery_pct": r["battery_pct"],
              "min_battery": r["min_battery"], "drain_rate": r["drain_rate"]} for r in memory.robots()]
    too_heavy = {"packages": [{"id": f"projector#{i}", "weight": 12} for i in range(1, 6)], "agvs": fleet}
    step = {"thought": "", "action": "verify_dispatch_smt", "action_input": too_heavy}
    run = agent.run_agent(agent.ScriptedLLM([step, step, {"thought": "", "action": "finish",
                                                           "action_input": {"final_answer": "no"}}]), "test")
    assert flags(run)[:2] == ["unsat", "blocked"]
    assert run["trace"][1]["observation"]["status"] == "BLOCKED_REPEAT"


def test_battery_drain_blocks_a_load_that_capacity_allows():
    memory.reset()
    run = agent.run_agent(agent.scripted_delivery(overloaded=True), "Send 3 projectors and the whiteboard.")
    memory.record_dispatch("setup", run["destination"], run["packages"], run["assignments"], run["routes"])
    badger = next(r for r in memory.robots() if r["robot_id"] == "CB-2")   # drained by the first dispatch
    spec = {k: badger[k] for k in ("capacity", "battery_pct", "min_battery", "drain_rate")} | {"id": "CB-2"}
    tank = [{"id": "projector#1", "weight": 12}]
    assert 12 <= badger["capacity"] and badger["battery_pct"] - badger["drain_rate"] * 12 < badger["min_battery"]
    assert agent.verify_dispatch_smt({"packages": tank, "agvs": [spec]})["status"] == "UNSATISFIABLE"


def test_robots_without_silent_wheels_avoid_the_quiet_zone():
    memory.reset()
    badger = agent.plan_route_tool("CB-2", "Corridor B")    # not quiet-wheeled
    mole = agent.plan_route_tool("CB-1", "Corridor B")      # quiet-wheeled
    assert badger["reachable"] and badger["quiet_cells_on_route"] == 0
    assert mole["quiet_cells_on_route"] > 0 and badger["steps"] > mole["steps"]
    for a in world.LOCATIONS.values():
        for b in world.LOCATIONS.values():
            assert world.plan_route(a, b, quiet_wheels=False)["quiet_cells_on_route"] == 0


if __name__ == "__main__":
    tests = [f for name, f in dict(globals()).items() if name.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"\nAll {len(tests)} checks passed.")
