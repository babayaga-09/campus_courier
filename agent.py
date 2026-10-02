"""
agent.py: the LLM "courier coordinator". A ReAct loop (adapted from the
ReAct lab's run_react_loop) whose tools are the reused lab algorithms.


"""

import json
import os
from collections import Counter
from typing import Dict, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

import memory
import world
from verifier import AGVSpec, PackageSpec, verify_dispatch_smt  # core/ (SMT lab)

load_dotenv()
MAX_ITERATIONS = 12


# ---------------------------------------------------------------------------
# Tool argument schemas (validated before any tool runs, as in the ReAct lab)
# ---------------------------------------------------------------------------

class NoArgs(BaseModel):
    pass


class VerifyArgs(BaseModel):
    packages: List[PackageSpec]
    agvs: List[AGVSpec]


class RouteArgs(BaseModel):
    robot_id: str
    destination: str


class FinishArgs(BaseModel):
    final_answer: str
    destination: Optional[str] = None
    assignments: Dict[str, str] = {}


ARG_MODELS = {
    "get_fleet_status": NoArgs,
    "get_inventory": NoArgs,
    "get_locations": NoArgs,
    "verify_dispatch_smt": VerifyArgs,
    "plan_route": RouteArgs,
    "finish": FinishArgs,
}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def get_locations():
    return {
        "locations": {name: list(xy) for name, xy in world.LOCATIONS.items()},
        "hazards": "~ cells are just mopped (slippery); g cells are a quiet zone outside the exam hall.",
    }


def grounding_problems(payload):
    """Gate 1: every number the LLM put in the payload must come from the database."""
    fleet = {r["robot_id"]: r for r in memory.robots()}
    stock = {s["item"]: s for s in memory.supplies()}
    problems = []
    for agv in payload["agvs"]:
        row = fleet.get(agv["id"])
        if row is None:
            problems.append(f"unknown robot {agv['id']}")
            continue
        for field in ("capacity", "battery_pct", "min_battery", "drain_rate"):
            if agv[field] != row[field]:
                problems.append(f"{agv['id']}.{field} is {agv[field]} but the database says {row[field]}")
    for pkg in payload["packages"]:
        item = pkg["id"].split("#")[0]
        if item not in stock:
            problems.append(f"unknown supply '{item}' (package ids look like 'projector#1')")
        elif pkg["weight"] != stock[item]["weight"]:
            problems.append(f"{pkg['id']} weighs {stock[item]['weight']}kg, not {pkg['weight']}kg")
    for item, count in Counter(p["id"].split("#")[0] for p in payload["packages"]).items():
        if item in stock and count > stock[item]["stock"]:
            problems.append(f"requested {count}x {item} but only {stock[item]['stock']} in stock")
    return problems


def plan_route_tool(robot_id, destination):
    robot = next((r for r in memory.robots() if r["robot_id"] == robot_id), None)
    if robot is None:
        return {"error": f"unknown robot {robot_id}"}
    if destination not in world.LOCATIONS:
        return {"error": f"unknown destination {destination}", "valid": list(world.LOCATIONS)}
    return {"robot_id": robot_id, "destination": destination,
            **world.plan_route((robot["x"], robot["y"]), world.LOCATIONS[destination], bool(robot["quiet_wheels"]))}


# ---------------------------------------------------------------------------
# LLM clients: live OpenAI, or an offline scripted replay for demos without wifi
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the courier coordinator for a university campus floor.
A human commander sends orders in plain language. You dispatch robots carrying
supplies to the rooms that asked for them, using ONLY tool observations. Never invent numbers.

Every turn, reply with exactly one JSON object and nothing else:
{"thought": "<reasoning>", "action": "<action>", "action_input": {...}}

Actions:
- get_fleet_status   {}  -> robots with capacity, battery_pct, min_battery, drain_rate, position
- get_inventory      {}  -> supplies with weight per unit and stock
- get_locations      {}  -> named destinations
- plan_route         {"robot_id": "CB-1", "destination": "Studio 3"}  -> A* route. Robots that
     are not quiet-wheeled are routed around the quiet zone; if such a route is unreachable,
     re-verify without that robot.
- verify_dispatch_smt {"packages": [{"id": "projector#1", "weight": 12}, ...],
                       "agvs": [{"id": "CB-1", "capacity": 30, "battery_pct": 85,
                                 "min_battery": 20, "drain_rate": 0.5}, ...]}
     Z3 decides which robot carries which package. Copy robot fields EXACTLY from
     get_fleet_status. One package entry per unit, ids like "lab_kit#1", "lab_kit#2".
- finish {"final_answer": "<summary for the commander>", "destination": "<location>",
          "assignments": {<copied exactly from the SATISFIABLE result>}}
     Use empty assignments if the order cannot be done.

Rules:
1. After UNSATISFIABLE, read the feedback and diagnostics, then submit a genuinely
   different payload (e.g. fewer or lighter items), never the same one again.
   Tell the commander what you dropped and why. Priority when cutting load:
   projector > lab_kit > water_case > marker_box > whiteboard.
2. Never finish with assignments unless the latest verify_dispatch_smt was SATISFIABLE.
3. Before finishing, plan_route every robot that appears in the assignments.
"""


class OpenAILLM:
    label = "OpenAI (live)"

    def __init__(self, model=None):
        from openai import OpenAI
        self.client = OpenAI(timeout=60, max_retries=1)  # fail fast on bad wifi instead of hanging the demo
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5-mini")

    def step(self, messages):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content


class ScriptedLLM:
    """Offline replay (same idea as the ReAct lab's scripted_llm.py). A step may be a
    callable taking the last observation, so it can copy Z3's assignment."""
    label = "Offline scripted replay (no LLM)"

    def __init__(self, steps):
        self.steps, self.i = steps, 0

    def step(self, messages):
        step = self.steps[self.i]
        self.i += 1
        if callable(step):
            step = step(json.loads(messages[-1]["content"].removeprefix("Observation: ")))
        return json.dumps(step)


def scripted_delivery(overloaded=False):
    fleet = [r for r in memory.robots() if r["battery_pct"] >= r["min_battery"]]
    specs = [{k: r[k] for k in ("capacity", "battery_pct", "min_battery", "drain_rate")} | {"id": r["robot_id"]}
             for r in fleet]
    stock = {s["item"]: s["weight"] for s in memory.supplies()}

    def pkgs(**counts):
        return [{"id": f"{item}#{n}", "weight": stock[item]} for item, c in counts.items() for n in range(1, c + 1)]

    steps = [
        {"thought": "Check which robots are usable.", "action": "get_fleet_status", "action_input": {}},
        {"thought": "Check supply weights and stock.", "action": "get_inventory", "action_input": {}},
    ]
    steps += [{"thought": f"Route {s['id']} to Studio 3.", "action": "plan_route",
               "action_input": {"robot_id": s["id"], "destination": "Studio 3"}} for s in specs]
    if overloaded:
        steps.append({"thought": "Try the full request: 3 projectors and the whiteboard.",
                      "action": "verify_dispatch_smt",
                      "action_input": {"packages": pkgs(projector=3, whiteboard=1), "agvs": specs}})
        request, note = pkgs(projector=3), " The whiteboard was dropped: total load exceeded usable capacity."
        thought = "UNSAT on capacity. The class needs the projectors, so drop the whiteboard and retry."
    else:
        request, note, thought = pkgs(projector=2, lab_kit=1), "", "Verify 2 projectors + 1 lab kit."
    steps.append({"thought": thought, "action": "verify_dispatch_smt",
                  "action_input": {"packages": request, "agvs": specs}})
    steps.append(lambda obs: {
        "thought": "Z3 verified the plan; commit it." if obs.get("status") == "SATISFIABLE" else "Still infeasible.",
        "action": "finish",
        "action_input": {"final_answer": f"Dispatched {len(request)} items to Studio 3.{note}"
                         if obs.get("status") == "SATISFIABLE" else "Order cannot be fulfilled safely.",
                         "destination": "Studio 3", "assignments": obs.get("assignments", {})},
    })
    return ScriptedLLM(steps)


def scripted_low_battery():
    """Offline replay of 'Use Pixel to carry a lab kit to the Library': Z3 refuses a robot below its minimum."""
    ferret = next(r for r in memory.robots() if r["robot_id"] == "CB-3")
    spec = {k: ferret[k] for k in ("capacity", "battery_pct", "min_battery", "drain_rate")} | {"id": "CB-3"}
    lab_kit = next(s for s in memory.supplies() if s["item"] == "lab_kit")
    return ScriptedLLM([
        {"thought": "The commander named Pixel; check its battery.", "action": "get_fleet_status", "action_input": {}},
        {"thought": "Verify the plan exactly as ordered: one lab kit on Pixel only.", "action": "verify_dispatch_smt",
         "action_input": {"packages": [{"id": "lab_kit#1", "weight": lab_kit["weight"]}], "agvs": [spec]}},
        lambda obs: {
            "thought": "Z3 refused: Pixel is below its minimum battery. Report back instead of overriding the order.",
            "action": "finish",
            "action_input": {"final_answer": f"Not dispatched. Pixel is at {ferret['battery_pct']}% battery, below its "
                             f"{ferret['min_battery']}% minimum, so Z3 rejected the plan. Atlas or Comet can take the "
                             "lab_kit if you approve."} if obs.get("status") != "SATISFIABLE" else
            {"final_answer": "Pixel is charged enough; dispatching.", "destination": "Library",
             "assignments": obs.get("assignments", {})},
        },
    ])


# ---------------------------------------------------------------------------
# The ReAct loop
# ---------------------------------------------------------------------------

def run_agent(llm, order, max_iterations=MAX_ITERATIONS, on_step=None):
    """Returns a dict with ok, final_answer, destination, assignments, packages, routes, trace.
    on_step(entry) is called after every step so a UI can stream the trace."""
    messages = [{"role": "user", "content": order}]
    trace, routes, unsat_payloads = [], {}, set()
    last_verdict, last_payload = None, None

    def observe(entry, observation, flag="ok"):
        entry.update(observation=observation, flag=flag)
        trace.append(entry)
        if on_step:
            on_step(entry)
        messages.append({"role": "user", "content": f"Observation: {json.dumps(observation)}"})

    for _ in range(max_iterations):
        raw = llm.step(messages)
        messages.append({"role": "assistant", "content": raw})
        entry = {"thought": "", "action": "?", "input": {}}

        try:
            step = json.loads(raw)
            if not isinstance(step, dict):
                raise json.JSONDecodeError("not an object", raw, 0)
            entry.update(thought=step.get("thought", ""), action=step.get("action", "?"),
                         input=step.get("action_input", {}))
        except json.JSONDecodeError:
            observe(entry, {"error": "Reply must be one JSON object with thought, action, action_input."}, "syntax")
            continue

        if entry["action"] not in ARG_MODELS:
            observe(entry, {"error": f"Unknown action. Valid actions: {list(ARG_MODELS)}"}, "syntax")
            continue
        try:
            args = ARG_MODELS[entry["action"]](**entry["input"])
        except (ValidationError, TypeError) as e:
            observe(entry, {"error": str(e)}, "syntax")
            continue

        action = entry["action"]
        if action == "finish":
            refusal = None
            if args.assignments:
                if not last_verdict or last_verdict.get("status") != "SATISFIABLE":
                    refusal = "BLOCKED: no SATISFIABLE verification backs these assignments."
                elif args.assignments != last_verdict["assignments"]:
                    refusal = "BLOCKED: assignments differ from the Z3-verified model."
                elif args.destination not in world.LOCATIONS:
                    refusal = f"BLOCKED: unknown destination {args.destination}."
                else:
                    missing = [r for r in set(args.assignments.values())
                               if routes.get(r, {}).get("destination") != args.destination]
                    if missing:
                        refusal = f"BLOCKED: plan_route to {args.destination} first for {missing}."
            if refusal:
                observe(entry, {"error": refusal}, "blocked")
                continue
            observe(entry, {"status": "COMMITTED" if args.assignments else "NO DISPATCH"}, "finish")
            return {"ok": bool(args.assignments), "final_answer": args.final_answer,
                    "destination": args.destination, "assignments": args.assignments,
                    "packages": last_payload["packages"] if args.assignments else [],
                    "routes": routes, "trace": trace, "messages": messages}

        if action == "verify_dispatch_smt":
            payload = args.model_dump()
            key = json.dumps(payload, sort_keys=True)
            problems = grounding_problems(payload)
            if problems:
                observe(entry, {"status": "REJECTED_UNGROUNDED", "problems": problems}, "blocked")
            elif key in unsat_payloads:
                observe(entry, {"status": "BLOCKED_REPEAT",
                                "feedback": "This exact payload was already UNSATISFIABLE. Change it."}, "blocked")
            else:
                last_verdict, last_payload = verify_dispatch_smt(payload), payload
                if last_verdict["status"] != "SATISFIABLE":
                    unsat_payloads.add(key)
                observe(entry, last_verdict, "sat" if last_verdict["status"] == "SATISFIABLE" else "unsat")
        elif action == "plan_route":
            result = plan_route_tool(args.robot_id, args.destination)
            if result.get("reachable"):
                routes[args.robot_id] = result
            # the full cell list goes to the dashboard, not back into the LLM context
            observe(entry, {k: v for k, v in result.items() if k != "path"})
        else:
            observe(entry, {"get_fleet_status": memory.robots, "get_inventory": memory.supplies,
                            "get_locations": get_locations}[action]())

    return {"ok": False, "final_answer": f"Stopped: no decision within {max_iterations} steps.",
            "destination": None, "assignments": {}, "packages": [], "routes": routes,
            "trace": trace, "messages": messages}


if __name__ == "__main__":
    import sys
    memory.reset()
    live = "--live" in sys.argv
    llm = OpenAILLM() if live else scripted_delivery(overloaded="--overload" in sys.argv)
    result = run_agent(llm, "Get 2 projectors and a lab kit to Studio 3 before the 2pm class.")
    for t in result["trace"]:
        print(f"[{t['flag']:>7}] {t['action']}: {t['thought']}")
        print("          ->", json.dumps(t["observation"])[:220])
    print("\nOK:", result["ok"], "|", result["final_answer"], "|", result["assignments"])
