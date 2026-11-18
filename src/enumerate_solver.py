"""Exact solver for TINY instances: try every possible plan.

Only usable for ~6-8 stops (6 stops, 2 trucks -> 6! x 7 = 5,040 plans).
Purpose: give the TRUE optimum, so later heuristics (OR-Tools, buffer loop) can be checked against it.

Model A: min distance  s.t. capacity + all windows met under BASE travel times (CVRPTW).
Model B: Model A's constraints  +  R_w >= rho for every ward, estimated on TRAIN scenarios.
"""
from itertools import permutations

import numpy as np

from src.evaluate import is_capacity_ok, metrics, plan_distance, simulate


def all_plans(inst):
    """Yield every 2-truck plan (route1, route2). Swapped duplicates are skipped."""
    assert inst.n_vehicles == 2, "enumeration written for 2 trucks"
    seen = set()
    for perm in permutations(range(1, inst.n + 1)):
        for k in range(inst.n + 1):
            r1, r2 = perm[:k], perm[k:]
            key = frozenset([r1, r2])
            if key in seen:
                continue
            seen.add(key)
            yield [list(r1), list(r2)]


def feasible_base(inst, plan):
    """Capacity ok and every stop on time when there is no traffic surprise."""
    if not is_capacity_ok(inst, plan):
        return False
    on_time, _ = simulate(inst, plan, np.ones((1, inst.n + 1)))
    return bool(on_time[0, 1:].all())


def solve(inst, F_train=None, rho=None):
    """rho=None -> Model A. rho given -> Model B. Returns (best_plan, n_checked, n_feasible)."""
    best, best_d, n_all, n_feas = None, np.inf, 0, 0
    for plan in all_plans(inst):
        n_all += 1
        if not feasible_base(inst, plan):
            continue
        if rho is not None:
            if min(metrics(inst, plan, F_train)["R"].values()) < rho:
                continue
        n_feas += 1
        d = plan_distance(inst, plan)
        if d < best_d - 1e-9:
            best, best_d = plan, d
    return best, n_all, n_feas
