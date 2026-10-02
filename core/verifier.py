

from __future__ import annotations

from typing import Any, Dict, List

import z3
from pydantic import BaseModel, Field


class PackageSpec(BaseModel):
    id: str
    weight: int = Field(gt=0)


class AGVSpec(BaseModel):
    id: str
    capacity: int = Field(gt=0)
    battery_pct: int = Field(ge=0, le=100)
    min_battery: int = Field(default=20)
    # How many percentage points of battery it costs this AGV to carry one
    # kg of assigned load. 0 (the default) means "no drain modeled" -- the
    # AGV only needs to clear `min_battery` once, regardless of load. See
    # README Section 1 ("Extending the model") and Task 4 below.
    drain_rate: float = Field(default=0.0, ge=0)


class VerificationPayload(BaseModel):
    packages: List[PackageSpec]
    agvs: List[AGVSpec]


def battery_drain_constraint(agv: AGVSpec, assigned_weight: "z3.ArithRef") -> "z3.BoolRef":
   
    # Battery left after carrying the load must stay at or above the minimum.
    # Only when a load is assigned: an idle AGV below its threshold is already
    # handled by constraint 2 and must not make the whole problem UNSAT.
    # RealVal(str(...)) keeps 0.3 exact (3/10) instead of a binary float.
    battery_left = agv.battery_pct - z3.RealVal(str(agv.drain_rate)) * assigned_weight
    return z3.Implies(assigned_weight > 0, battery_left >= agv.min_battery)


def verify_dispatch_smt(raw_payload: dict) -> Dict[str, Any]:
    """
    Evaluates payload against First-Order Logic constraints using Z3.
    Returns structured mathematical feedback for the agent context.
    """
    try:
        payload = VerificationPayload.model_validate(raw_payload)
    except Exception as e:
        return {"status": "SYNTACTIC_ERROR", "message": str(e)}

    solver = z3.Solver()
    num_agvs = len(payload.agvs)
    pkg_vars = {p.id: z3.Int(f"assign_{p.id}") for p in payload.packages}

    # 1. Bounds: Every package mapped to a valid AGV index
    for p_id, var in pkg_vars.items():
        solver.add(var >= 0, var < num_agvs)

    # 2. Battery Theory Check: Low battery AGVs cannot receive assignments
    for idx, agv in enumerate(payload.agvs):
        if agv.battery_pct < agv.min_battery:
            for p_id, var in pkg_vars.items():
                solver.add(var != idx)

    # 3. Weight Theory Check: Sum of package weights <= AGV capacity
    for idx, agv in enumerate(payload.agvs):
        assigned_weight = z3.Sum([
            z3.If(pkg_vars[p.id] == idx, p.weight, 0)
            for p in payload.packages
        ])
        solver.add(assigned_weight <= agv.capacity)

    # 4. Battery-Drain Theory Check (Task 4 -- fill in battery_drain_constraint above)
    for idx, agv in enumerate(payload.agvs):
        assigned_weight = z3.Sum([
            z3.If(pkg_vars[p.id] == idx, p.weight, 0)
            for p in payload.packages
        ])
        solver.add(battery_drain_constraint(agv, assigned_weight))

    # Solve
    if solver.check() == z3.sat:
        model = solver.model()
        assignments = {
            p.id: payload.agvs[model[pkg_vars[p.id]].as_long()].id
            for p in payload.packages
        }
        return {
            "status": "SATISFIABLE",
            "assignments": assignments,
            "feedback": "Allocation verified mathematically.",
        }

    # ---- UNSAT: figure out WHICH of three distinct failures applies ----
    active_agvs = [a for a in payload.agvs if a.battery_pct >= a.min_battery]
    disabled_agvs = [a for a in payload.agvs if a.battery_pct < a.min_battery]
    total_weight = sum(p.weight for p in payload.packages)
    total_active_capacity = sum(a.capacity for a in active_agvs)
    max_active_capacity = max((a.capacity for a in active_agvs), default=0)
    oversized_packages = [
        p.id for p in payload.packages if p.weight > max_active_capacity
    ]

    diagnostics = {
        "total_requested_weight": total_weight,
        "available_active_capacity": total_active_capacity,
        "active_agvs": [a.id for a in active_agvs],
        "disabled_agvs_low_battery": [a.id for a in disabled_agvs],
        "oversized_packages": oversized_packages,
    }

    if not active_agvs:
        feedback = (
            "UNSAT: every AGV is below its minimum battery threshold. "
            "No assignment is possible until at least one AGV is charged."
        )
    elif oversized_packages:
        feedback = (
            f"UNSAT: package(s) {oversized_packages} individually exceed the "
            f"capacity of every active AGV (largest active capacity: "
            f"{max_active_capacity}kg). This cannot be fixed by reassigning "
            f"packages alone -- split the package, free up a bigger AGV, or "
            f"drop it."
        )
    elif total_weight > total_active_capacity:
        feedback = (
            f"UNSAT: total requested weight ({total_weight}kg) exceeds "
            f"usable active capacity ({total_active_capacity}kg). Check "
            f"disabled low-battery AGVs or reduce the package set."
        )
    else:
        feedback = (
            f"UNSAT: no valid assignment exists even though total weight "
            f"({total_weight}kg) fits within total active capacity "
            f"({total_active_capacity}kg). This is a packing/arrangement "
            f"conflict, not a raw capacity shortfall -- try a different "
            f"split of which packages travel together."
        )
        if any(a.drain_rate > 0 for a in active_agvs):
            feedback += (
                " Note: one or more active AGVs have a nonzero drain_rate, "
                "meaning the weight they're given also costs them battery "
                "headroom above their own min_battery -- that interaction "
                "may be part of why no split of these packages works, even "
                "though the raw capacity numbers look sufficient."
            )

    return {
        "status": "UNSATISFIABLE",
        "diagnostics": diagnostics,
        "feedback": feedback,
    }


if __name__ == "__main__":
    # Quick manual sanity check -- python verifier.py
    import json

    sat_case = {
        "packages": [{"id": "Item-1", "weight": 10}, {"id": "Item-2", "weight": 15}],
        "agvs": [
            {"id": "AGV-A", "capacity": 30, "battery_pct": 80, "min_battery": 25},
            {"id": "AGV-B", "capacity": 20, "battery_pct": 50, "min_battery": 25},
        ],
    }
    unsat_case = {
        "packages": [
            {"id": "Heavy-Box-1", "weight": 40},
            {"id": "Heavy-Box-2", "weight": 25},
        ],
        "agvs": [
            {"id": "AGV-1", "capacity": 30, "battery_pct": 90, "min_battery": 25},
            {"id": "AGV-2", "capacity": 20, "battery_pct": 10, "min_battery": 25},
        ],
    }

    print("SAT case:")
    print(json.dumps(verify_dispatch_smt(sat_case), indent=2))
    print("\nUNSAT case:")
    print(json.dumps(verify_dispatch_smt(unsat_case), indent=2))
