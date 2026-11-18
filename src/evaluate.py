"""Simulate a route plan and compute the reliability metrics.

A plan is a list of routes; each route is a list of stop ids (depot not included).
Every truck leaves the depot at t = 0.

Timing rule (decision D4):
    arrival  = previous departure + travel time
    start    = max(arrival, window start)      # truck WAITS if early, never serves early
    on time  = start <= window end
    depart   = start + service time
"""
import numpy as np


def plan_distance(inst, plan):
    d = 0.0
    for route in plan:
        path = [0] + list(route) + [0]
        d += sum(inst.dist_km[a, b] for a, b in zip(path[:-1], path[1:]))
    return d


def is_capacity_ok(inst, plan):
    return all(inst.demand[list(r)].sum() <= inst.capacity for r in plan)


def simulate(inst, plan, F):
    """Return (on_time, start) arrays of shape (n_scen, n+1). Column 0 (depot) is unused.

    F has shape (n_scen, n+1); pass np.ones((1, n+1)) for the no-traffic case.
    """
    n_scen = F.shape[0]
    on_time = np.zeros((n_scen, inst.n + 1), dtype=bool)
    start = np.full((n_scen, inst.n + 1), np.nan)
    for route in plan:
        t = np.zeros(n_scen)
        prev = 0
        for j in route:
            arrival = t + inst.base_min[prev, j] * F[:, j]
            s = np.maximum(arrival, inst.win_start[j])
            start[:, j] = s
            on_time[:, j] = s <= inst.win_end[j]
            t = s + inst.service[j]
            prev = j
    return on_time, start


def metrics(inst, plan, F):
    """Stop-level p_i, ward-level R_w, gap G, min R_w, and mean minutes late."""
    on_time, start = simulate(inst, plan, F)
    stops = np.arange(1, inst.n + 1)
    p = on_time[:, stops].mean(axis=0)                     # p_i for i = 1..n
    late_min = np.maximum(start[:, stops] - inst.win_end[stops], 0).mean(axis=0)
    R = {}
    for w in inst.wards:
        idx = [k for k, i in enumerate(stops) if inst.ward[i] == w]
        R[w] = p[idx].mean()                               # R_w = mean of p_i in ward w
    return {
        "distance_km": plan_distance(inst, plan),
        "p": dict(zip(stops.tolist(), p.round(4).tolist())),
        "R": R,
        "gap": max(R.values()) - min(R.values()),
        "min_R": min(R.values()),
        "mean_late_min": float(late_min.mean()),
    }
