"""Model A with Google OR-Tools: min-distance CVRPTW under BASE travel times.

Same model as the exact solver (src/enumerate_solver.py), but scales to real instances:
    minimise   total road distance (depot -> stops -> end node)
    subject to truck capacity, and every stop's service START inside its window
               (truck waits if early, decision D4), using base (no-surprise) travel times.

OR-Tools works in integers, so we scale:
    distance  : metres (km x 1000, rounded)       -> objective error <= 0.5 m per leg
    time      : 1/1000 minute, travel rounded UP   -> never accepts a plan that is late in float time
Every returned plan is re-checked with the float simulator in src/evaluate.py.

OR-Tools is a heuristic (local search). On tiny instances we check it matches the exact
optimum (tests/test_ortools.py). On real instances no exact optimum is available, so we
report stability across time limits / search strategies instead (experiments/run_m2_verify.py).
"""
import math

import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from src.evaluate import is_capacity_ok, plan_distance, simulate

DIST_SCALE = 1000      # km -> m
TIME_SCALE = 1000      # min -> 1/1000 min


def _int_matrix(m, scale, up=False):
    f = np.ceil if up else np.rint
    return f(np.asarray(m) * scale).astype(np.int64)


def solve_model_a(inst, time_limit_s=10, first_solution="PATH_CHEAPEST_ARC",
                  metaheuristic="GUIDED_LOCAL_SEARCH", time_window_end=None):
    """Return (plan, info). plan = list of routes (stop ids), or None if no feasible plan found.

    time_window_end: optional array overriding inst.win_end (used later by Model B's buffered windows).
    """
    n_nodes = inst.n + 1
    end_node = getattr(inst, "end_node", 0)
    win_end = inst.win_end if time_window_end is None else np.asarray(time_window_end, dtype=float)

    D = _int_matrix(inst.dist_km, DIST_SCALE)
    T = _int_matrix(inst.base_min, TIME_SCALE, up=True)
    S = _int_matrix(inst.service, TIME_SCALE, up=True)

    # OR-Tools needs separate start and end indices; if the end is the depot, start == end.
    starts = [0] * inst.n_vehicles
    ends = [end_node] * inst.n_vehicles
    manager = pywrapcp.RoutingIndexManager(n_nodes, inst.n_vehicles, starts, ends)
    routing = pywrapcp.RoutingModel(manager)

    def dist_cb(i, j):
        return int(D[manager.IndexToNode(i), manager.IndexToNode(j)])

    def time_cb(i, j):
        a, b = manager.IndexToNode(i), manager.IndexToNode(j)
        return int(S[a] + T[a, b])          # service at a, then drive a -> b

    def demand_cb(i):
        return int(inst.demand[manager.IndexToNode(i)])

    d_idx = routing.RegisterTransitCallback(dist_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(d_idx)

    dem_idx = routing.RegisterUnaryTransitCallback(demand_cb)
    routing.AddDimensionWithVehicleCapacity(dem_idx, 0, [int(inst.capacity)] * inst.n_vehicles,
                                            True, "Load")

    horizon = int(math.ceil(max(win_end[inst.stops].max(), 1) * TIME_SCALE + S.max() + T.max())) * 4
    t_idx = routing.RegisterTransitCallback(time_cb)
    # slack = waiting allowed (up to the horizon); cumul at a stop = service START time
    routing.AddDimension(t_idx, horizon, horizon, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")
    for node in range(1, n_nodes):
        if node == end_node:
            continue
        idx = manager.NodeToIndex(node)
        lo = int(math.ceil(inst.win_start[node] * TIME_SCALE))
        hi = int(math.floor(win_end[node] * TIME_SCALE))
        if hi < lo:
            return None, {"status": "INFEASIBLE (empty window)"}
        time_dim.CumulVar(idx).SetRange(lo, hi)
    for v in range(inst.n_vehicles):
        time_dim.CumulVar(routing.Start(v)).SetRange(0, 0)     # every truck leaves at t = 0

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = getattr(routing_enums_pb2.FirstSolutionStrategy, first_solution)
    params.local_search_metaheuristic = getattr(routing_enums_pb2.LocalSearchMetaheuristic, metaheuristic)
    params.time_limit.FromSeconds(int(time_limit_s))

    sol = routing.SolveWithParameters(params)
    if sol is None:
        return None, {"status": "NO SOLUTION FOUND"}

    plan = []
    for v in range(inst.n_vehicles):
        idx, route = routing.Start(v), []
        idx = sol.Value(routing.NextVar(idx))
        while not routing.IsEnd(idx):
            route.append(manager.IndexToNode(idx))
            idx = sol.Value(routing.NextVar(idx))
        plan.append(route)

    # independent float re-check (guards against any scaling/rounding mistake)
    on_time, _ = simulate(inst, plan, np.ones((1, n_nodes)))
    stops = [j for r in plan for j in r]
    ok = is_capacity_ok(inst, plan) and bool(on_time[0, stops].all()) and sorted(stops) == [
        j for j in range(1, n_nodes) if j != end_node]
    return plan, {
        "status": "ok" if ok else "FAILED FLOAT RE-CHECK",
        "objective_m": sol.ObjectiveValue(),
        "distance_km": plan_distance(inst, plan),
        "trucks_used": sum(1 for r in plan if r),
    }
