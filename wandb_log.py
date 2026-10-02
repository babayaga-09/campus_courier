"""
wandb_log.py: optional Weights & Biases logging for CampusCourier runs.

Off by default. To turn it on:
    pip install wandb
    wandb login
    set WANDB_ENABLED=1 in .env

Every dispatch attempt is logged as one run: how many steps the coordinator took,
how many Z3 verdicts it got, how often a gate blocked it, and whether the order
was finally dispatched. Nothing here changes the agent's behaviour. If wandb is
missing, disabled, or offline, log_run() returns silently.
"""

import os


def summarise(order, run):
    """Turn a finished agent run into flat metrics. Pure function, easy to test."""
    trace = run.get("trace", [])
    flags = [step["flag"] for step in trace]
    routes = run.get("routes", {})
    return {
        "order": order,
        "steps_taken": len(trace),
        "tool_calls": flags.count("ok"),
        "z3_sat": flags.count("sat"),
        "z3_unsat": flags.count("unsat"),
        "gate_blocked": flags.count("blocked"),
        "schema_errors": flags.count("syntax"),
        "verifier_attempts": flags.count("sat") + flags.count("unsat"),
        "dispatched": int(bool(run.get("ok"))),
        "items_dispatched": len(run.get("assignments", {})),
        "robots_used": len(set(run.get("assignments", {}).values())),
        "total_route_steps": sum(r.get("steps", 0) for r in routes.values()),
    }


def log_run(order, run, engine="unknown"):
    if os.getenv("WANDB_ENABLED", "0") != "1":
        return None
    try:
        import wandb
    except ImportError:
        print("wandb not installed; skipping logging. pip install wandb")
        return None

    metrics = summarise(order, run)
    try:
        with wandb.init(project=os.getenv("WANDB_PROJECT", "campuscourier"),
                        config={"engine": engine, "order": order},
                        reinit=True) as session:
            session.log(metrics)
            return session.url
    except Exception as exc:  # a dead network must never break a demo
        print(f"wandb logging skipped: {type(exc).__name__}: {exc}")
        return None


if __name__ == "__main__":  # smoke check with a fake run, no network needed
    fake = {"ok": True, "assignments": {"projector#1": "CB-1"}, "routes": {"CB-1": {"steps": 29}},
            "trace": [{"flag": "ok"}, {"flag": "unsat"}, {"flag": "sat"}, {"flag": "finish"}]}
    m = summarise("test order", fake)
    assert m["steps_taken"] == 4 and m["z3_unsat"] == 1 and m["verifier_attempts"] == 2
    assert m["dispatched"] == 1 and m["total_route_steps"] == 29
    print("ok:", m)
