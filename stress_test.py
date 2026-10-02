"""
stress_test.py: awkward inputs thrown at the agent and the verifier, offline only.

test_agent.py checks that the three demo stories behave. This file checks the
edges: impossible packages, an empty fleet, a model that invents numbers,
malformed replies, and a loop that never finishes.

    python stress_test.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "core"))

import memory

memory.DB_PATH = Path(tempfile.gettempdir()) / "campuscourier_stress.db"  # never touch the demo database

import agent
import world
from verifier import verify_dispatch_smt

passed, failed = [], []


def check(name, ok, detail=""):
    (passed if ok else failed).append(name)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail if not ok else ''}")


def fresh():
    memory.DB_PATH.unlink(missing_ok=True)
    memory.reset()


fresh()

# 1. the three scripted stories still run end to end
for label, llm, order in [
    ("routine", agent.scripted_delivery(), "Get 2 projectors and a lab kit to Studio 3."),
    ("overload", agent.scripted_delivery(overloaded=True), "Send 3 projectors and the whiteboard to Studio 3."),
    ("low battery", agent.scripted_low_battery(), "Use Pixel to carry a lab kit to the Library."),
]:
    fresh()
    run = agent.run_agent(llm, order)
    check(f"story runs: {label}", bool(run["trace"]), "empty trace")

# 2. every room reachable from every room, for both kinds of robot
fresh()
bad = []
for a_name, a in world.LOCATIONS.items():
    for b_name, b in world.LOCATIONS.items():
        for quiet in (True, False):
            route = world.plan_route(a, b, quiet_wheels=quiet)
            if not route["reachable"]:
                bad.append((a_name, b_name, quiet))
            if not quiet and route["quiet_cells_on_route"]:
                bad.append(("quiet zone entered", a_name, b_name))
check("all rooms reachable, quiet zone respected", not bad, str(bad[:3]))

# 3. verifier edge cases
fleet = [{"id": r["robot_id"], "capacity": r["capacity"], "battery_pct": r["battery_pct"],
          "min_battery": r["min_battery"], "drain_rate": r["drain_rate"]} for r in memory.robots()]

empty = verify_dispatch_smt({"packages": [], "agvs": fleet})
check("empty package list does not crash", empty["status"] in ("SATISFIABLE", "UNSATISFIABLE"), str(empty)[:80])

single_huge = verify_dispatch_smt({"packages": [{"id": "crate#1", "weight": 999}], "agvs": fleet})
check("one impossible package is UNSAT", single_huge["status"] == "UNSATISFIABLE")
check("  and names it as oversized",
      "crate#1" in single_huge.get("diagnostics", {}).get("oversized_packages", []))

many = verify_dispatch_smt({"packages": [{"id": f"p#{i}", "weight": 1} for i in range(40)], "agvs": fleet})
check("40 tiny packages still solvable", many["status"] == "SATISFIABLE")

no_fleet = verify_dispatch_smt({"packages": [{"id": "p#1", "weight": 1}], "agvs": []})
check("no robots at all is UNSAT", no_fleet["status"] == "UNSATISFIABLE")

flat = [dict(f, battery_pct=5) for f in fleet]
check("whole fleet flat is UNSAT",
      verify_dispatch_smt({"packages": [{"id": "p#1", "weight": 1}], "agvs": flat})["status"] == "UNSATISFIABLE")

# capacity alone would allow this load, the drain rule must stop it
tight = [{"id": "X", "capacity": 100, "battery_pct": 50, "min_battery": 20, "drain_rate": 1.0}]
check("capacity ok but drain too high is UNSAT",
      verify_dispatch_smt({"packages": [{"id": "p#1", "weight": 40}], "agvs": tight})["status"] == "UNSATISFIABLE")
check("same load within drain budget is SAT",
      verify_dispatch_smt({"packages": [{"id": "p#1", "weight": 25}], "agvs": tight})["status"] == "SATISFIABLE")

# 4. the gates, against a model that behaves badly on purpose
fresh()
idle = [{"thought": "idle", "action": "get_fleet_status", "action_input": {}}] * 12

liar = agent.ScriptedLLM([
    {"thought": "inflate the battery", "action": "verify_dispatch_smt",
     "action_input": {"packages": [{"id": "projector#1", "weight": 12}],
                      "agvs": [{"id": "CB-3", "capacity": 10, "battery_pct": 99,
                                "min_battery": 20, "drain_rate": 0.3}]}},
    {"thought": "commit anyway", "action": "finish",
     "action_input": {"final_answer": "done", "destination": "Studio 3",
                      "assignments": {"projector#1": "CB-3"}}},
] + idle)
run = agent.run_agent(liar, "sneak it through")
check("invented battery is blocked", "blocked" in [s["flag"] for s in run["trace"]])
check("  and nothing is dispatched", run["ok"] is False)

bad_json = agent.ScriptedLLM(["not json at all",
                              {"thought": "", "action": "nope", "action_input": {}}] + idle)
run = agent.run_agent(bad_json, "garbage in")
check("malformed replies are caught", [s["flag"] for s in run["trace"]].count("syntax") == 2)

loop = agent.ScriptedLLM([{"thought": "stall", "action": "get_fleet_status", "action_input": {}}] * 30)
run = agent.run_agent(loop, "never finish")
check("runaway loop stops at the iteration cap",
      len(run["trace"]) == agent.MAX_ITERATIONS and not run["ok"])

unknown_room = agent.ScriptedLLM([{"thought": "route somewhere fake", "action": "plan_route",
                                   "action_input": {"robot_id": "CB-1", "destination": "Mars"}}] * 14)
run = agent.run_agent(unknown_room, "go to Mars")
check("unknown destination does not crash", len(run["trace"]) > 0)

memory.DB_PATH.unlink(missing_ok=True)
print(f"\n{len(passed)} passed, {len(failed)} failed")
if failed:
    print("FAILED:", failed)
    sys.exit(1)
