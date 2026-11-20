"""Milestone M3 - published collection slots under day-to-day uncertainty (decisions D15-D17).

Per ward (Bengaluru operates ward-wise, D16), with the SAME distance-first routes for all three
models so that differences come only from how slots are set:
  A  deterministic timetable: slot centred on the planned time (nothing goes wrong)
  B  simulation-based (static): slot centred on the median arrival over TRAIN days
  C  dynamic: B's slots, re-announced once at 08:00 from each truck's observed progress
Plus a routing ablation (B on makespan-balanced routes) to test whether routing itself helps.

Scored on 2,000 TEST days (common random numbers); slots/forecasts only ever see TRAIN days.
Sensitivity: one-at-a-time changes to start delay, service variability, slot width, traffic,
fleet norm and depot location.

Run from repo root:  python -m experiments.run_m3      (~6-8 min)
"""
import json
import math
import os
import time
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd

from src.instance import ward_subset
from src.ortools_solver import solve_model_a
from src.real_instance import build
from src.slots import (Uncertainty, make_days, score, score_dynamic, simulate_slots,
                       slots_median, slots_nominal)
from src.traffic import TEST_SEED, TRAIN_SEED

warnings.filterwarnings("ignore", category=RuntimeWarning)
OUT_T, OUT_F = "results/tables", "results/figures"
CFG = json.load(open("data/config/real_area.json"))
N_TRAIN, N_TEST = CFG["n_train_days"]["value"], CFG["n_test_days"]["value"]
W0 = CFG["slot_width_min"]["value"]
U0 = Uncertainty(**CFG["uncertainty"]["value"])


def best_routes(sub, time_limit=30, span=0):
    """Distance-first routes: best of three OR-Tools settings (solver varies up to ~10%, M2)."""
    best = None
    for fs, mh in [("PATH_CHEAPEST_ARC", "GUIDED_LOCAL_SEARCH"),
                   ("PARALLEL_CHEAPEST_INSERTION", "GUIDED_LOCAL_SEARCH"),
                   ("PATH_CHEAPEST_ARC", "SIMULATED_ANNEALING")]:
        p, info = solve_model_a(sub, time_limit_s=time_limit, first_solution=fs, metaheuristic=mh,
                                span_m_per_min=span)
        if p is not None and info["status"] == "ok" and (best is None or info["distance_km"] < best[1]["distance_km"]):
            best = (p, info)
    return best


def ward_instance(inst, ward, cap):
    """Fleet = BBMP norm ceil(HH / cap); add trucks only if no feasible plan is found."""
    hh = int(sum(inst.demand[i] for i in inst.stops if inst.ward[i] == ward))
    for extra in range(3):
        sub = ward_subset(inst, ward, n_vehicles=math.ceil(hh / cap) + extra, capacity=cap)
        sol = best_routes(sub, time_limit=20)
        if sol:
            return sub, sol, extra
    raise RuntimeError(f"no plan for {ward}")


def summarise(sub, plan, res, model, extra_cols):
    pos = {j: k for r in plan for k, j in enumerate(r)}
    last = {j: (k == len(r) - 1) for r in plan for k, j in enumerate(r)}
    P, st = res["p"], res["stops"]
    first_p = np.mean([p for j, p in zip(st, P) if pos[j] == 0])
    last_p = np.mean([p for j, p in zip(st, P) if last[j]])
    w = sub.meta["ward"]
    day = res["R_day"][w]
    return {**extra_cols, "ward": w, "model": model,
            "R": round(res["R"][w], 4), "R_ci95": round(1.96 * day.std(ddof=1) / math.sqrt(len(day)), 4),
            "R_hh": round(res["R_hh"][w], 4),
            "min_p": round(float(P.min()), 3), "p10_p": round(float(np.percentile(P, 10)), 3),
            "first_stop_p": round(float(first_p), 3), "last_stop_p": round(float(last_p), 3),
            "position_gap": round(float(first_p - last_p), 3),
            "late_mean_min": round(res["late_mean_all"], 2), "late_p95_worst_point": round(res["late_p95_point"], 1),
            "slot_end_after_11": res["slot_end_after_11"],
            "slot_updates_per_day": round(res.get("n_updated_per_day", 0.0), 1)}


def run_models(sub, plan, unc, W, tag):
    tr = make_days(sub, N_TRAIN, TRAIN_SEED, unc)
    te = make_days(sub, N_TEST, TEST_SEED, unc)
    aA, aB = slots_nominal(sub, plan, W), slots_median(sub, plan, W, tr)
    res = {"A": score(sub, plan, aA, W, te), "B": score(sub, plan, aB, W, te),
           "C": score_dynamic(sub, plan, aB, W, te, tr)}
    w = sub.meta["ward"]
    rows = [summarise(sub, plan, r, m, tag) for m, r in res.items()]
    # paired differences on the same TEST days (common random numbers)
    for a, b in [("A", "B"), ("B", "C")]:
        d = res[b]["R_day"][w] - res[a]["R_day"][w]
        rows.append({**tag, "ward": w, "model": f"{b}-{a} (paired)",
                     "R": round(float(d.mean()), 4), "R_ci95": round(1.96 * d.std(ddof=1) / math.sqrt(len(d)), 4)})
    return rows, res


def with_depot_at(sub, k):
    """Depot moved to the location of point k (row/col k of the matrices). Used for depot sensitivity."""
    import copy
    s = copy.deepcopy(sub)
    for M in (s.dist_km, s.base_min):
        M[0, :] = M[k, :]
        M[:, 0] = M[:, k]
        M[0, 0] = 0
    return s


def main():
    os.makedirs(OUT_T, exist_ok=True); os.makedirs(OUT_F, exist_ok=True)
    inst, pts, seg, wards, G = build()
    depot_tag = inst.meta["depot_label"]
    print(f"Real area: {inst.meta['total_households']} households, depot = {depot_tag}")
    cap0 = CFG["vehicle_capacity_households"]["value"]

    base, routes, all_rows = {}, {}, []
    fleet_rows = []
    for w in inst.wards:
        sub, (plan, info), extra = ward_instance(inst, w, cap0)
        routes[w] = (sub, plan)
        fleet_rows.append({"ward": w, "households": sub.meta["households"], "norm_fleet": sub.n_vehicles - extra,
                           "fleet_used_for_feasibility": sub.n_vehicles, "trucks_in_plan": info["trucks_used"],
                           "distance_km": round(info["distance_km"], 2), "depot": depot_tag})
        rows, res = run_models(sub, plan, U0, W0, {"scenario": "base"})
        base[w] = res
        all_rows += rows
        # routing ablation: makespan-balanced routes, slots by rule B
        bal = best_routes(sub, time_limit=20, span=300)
        if bal:
            tr = make_days(sub, N_TRAIN, TRAIN_SEED, U0); te = make_days(sub, N_TEST, TEST_SEED, U0)
            rb = score(sub, bal[0], slots_median(sub, bal[0], W0, tr), W0, te)
            all_rows.append({**summarise(sub, bal[0], rb, "B on balanced routes", {"scenario": "base"}),
                             "distance_km": round(bal[1]["distance_km"], 2)})
        print(f"  {w}: fleet {sub.n_vehicles} (norm +{extra}), {info['distance_km']:.1f} km")
    pd.DataFrame(fleet_rows).to_csv(f"{OUT_T}/m3_fleet.csv", index=False)
    df = pd.DataFrame(all_rows)
    df["depot"] = depot_tag
    df.to_csv(f"{OUT_T}/m3_base_results.csv", index=False)
    show = ["ward", "model", "R", "R_ci95", "min_p", "first_stop_p", "last_stop_p", "position_gap", "late_mean_min"]
    print(df[show].to_string(index=False))

    # ---- sensitivity: one change at a time --------------------------------------------------
    sens = []
    cases = [("start delay U=30", dict(unc=Uncertainty(30, U0.cv_truck, U0.cv_point))),
             ("start delay U=90", dict(unc=Uncertainty(90, U0.cv_truck, U0.cv_point))),
             ("service CV x0.5", dict(unc=Uncertainty(U0.start_delay_max, U0.cv_truck * .5, U0.cv_point * .5))),
             ("service CV x1.5", dict(unc=Uncertainty(U0.start_delay_max, U0.cv_truck * 1.5, U0.cv_point * 1.5))),
             ("traffic x2", dict(unc=Uncertainty(U0.start_delay_max, U0.cv_truck, U0.cv_point, 2.0))),
             ("slot width 30", dict(W=30)), ("slot width 90", dict(W=90)),
             ("fleet norm 750 HH", dict(cap=750)), ("depot at farthest point", dict(depot="far"))]
    for name, c in cases:
        for w in inst.wards:
            sub, plan = routes[w]
            if "cap" in c:
                sub, (plan, _), _ = ward_instance(inst, w, c["cap"])
            if c.get("depot") == "far":
                k = int(np.argmax(sub.base_min[0, 1:])) + 1
                sub = with_depot_at(sub, k)
                sol = best_routes(sub, time_limit=30)
                if sol is None:                       # same rule as base: add a truck only if needed
                    sub.n_vehicles += 1
                    sol = best_routes(sub, time_limit=30)
                plan = sol[0]
            rows, _ = run_models(sub, plan, c.get("unc", U0), c.get("W", W0), {"scenario": name})
            sens += rows
        print(f"  sensitivity done: {name}")
    sd = pd.DataFrame(sens)
    sd["depot"] = depot_tag
    sd.to_csv(f"{OUT_T}/m3_sensitivity.csv", index=False)
    piv = sd[sd.model.isin(["A", "B", "C"])].pivot_table(index=["scenario", "ward"], columns="model", values="R")
    print(piv.round(3).to_string())

    # ---- figure: reliability by position in route -------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    colors = {"A": "#c0392b", "B": "#2a6fdb", "C": "#1e8449"}
    names = {"A": "A  deterministic timetable", "B": "B  simulation-based slots", "C": "C  B + update at 08:00"}
    for ax, w in zip(axes, inst.wards):
        sub, plan = routes[w]
        pos = {j: k for r in plan for k, j in enumerate(r)}
        for m in ["A", "B", "C"]:
            r = base[w][m]
            byk = {}
            for j, p in zip(r["stops"], r["p"]):
                byk.setdefault(pos[j] + 1, []).append(p)
            ks = sorted(byk)
            ax.plot(ks, [np.mean(byk[k]) for k in ks], "-o", color=colors[m], label=names[m])
        ax.set_title(f"{w}  (fleet {sub.n_vehicles})", fontsize=10)
        ax.set_xlabel("position of the collection point in its route")
        ax.grid(alpha=.3)
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    axes[0].set_ylabel("P(served by end of published slot)")
    axes[0].legend(fontsize=8, loc="lower left")
    fig.suptitle(f"On-time reliability by route position, 2,000 test days, slot width {W0} min "
                 f"[depot: {depot_tag[:20]}]", fontsize=10)
    plt.tight_layout()
    fig.savefig(f"{OUT_F}/m3_reliability_by_position.png", dpi=160)
    print(f"wrote {OUT_F}/m3_reliability_by_position.png")


if __name__ == "__main__":
    t = time.time()
    main()
    print(f"done in {time.time() - t:.0f} s")
