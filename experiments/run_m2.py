"""Milestone M2.

Part 1 - solver check: OR-Tools Model A vs the exact optimum on the toy + 40 random tiny instances
         (same checks as tests/test_ortools.py, but printed as a table for the paper's appendix).
Part 2 - real area: build the Nagasandra + Dodda Bidarakallu instance, solve Model A with several
         search strategies and time limits, and report how stable the answer is.
Part 3 - outputs: points CSV, matrices, map, solution table.

Run from repo root:   python -m experiments.run_m2
If data/raw/facilities.json exists it is used for the depot; otherwise a PLACEHOLDER depot is used
and every output is stamped PLACEHOLDER (pipeline test only, not a result).
"""
import json
import os
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.enumerate_solver import solve as exact_solve
from src.evaluate import plan_distance, simulate
from src.instance import load_toy
from src.ortools_solver import solve_model_a
from src.real_instance import UTM, build
from tests.test_ortools import random_tiny

OUT_T, OUT_F, OUT_D = "results/tables", "results/figures", "data/derived"


def part1():
    rows = []
    insts = [("toy", load_toy("data/synthetic/toy_instance.json"))] + \
            [(f"random_{s}", random_tiny(s)) for s in range(40)]
    for name, inst in insts:
        ex, _, n_feas = exact_solve(inst)
        t = time.time()
        plan, info = solve_model_a(inst, time_limit_s=1)
        rows.append({
            "instance": name, "exact_feasible_plans": n_feas,
            "exact_km": None if ex is None else round(plan_distance(inst, ex), 4),
            "ortools_km": None if plan is None else round(plan_distance(inst, plan), 4),
            "match": (ex is None and plan is None) or
                     (ex is not None and plan is not None and abs(plan_distance(inst, ex) - plan_distance(inst, plan)) < 0.01),
        })
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT_T}/m2_ortools_vs_exact.csv", index=False)
    print(f"Part 1: OR-Tools matched the exact optimum on {df.match.sum()}/{len(df)} instances "
          f"({(df.exact_km.isna()).sum()} infeasible, both agree).")
    return df


def part2():
    fac = "data/raw/facilities.json" if os.path.exists("data/raw/facilities.json") else None
    inst, pts, seg, wards, G = build(facilities_path=fac)
    tag = inst.meta["depot_label"]
    print(f"\nPart 2: real area, depot = {tag}")
    print(f"  {inst.n} points {inst.meta['points_per_ward']}, {inst.meta['total_households']} households, "
          f"fleet {inst.n_vehicles} x {inst.capacity} HH")

    runs = []
    best = None
    for fs in ["PATH_CHEAPEST_ARC", "PARALLEL_CHEAPEST_INSERTION"]:
        for mh in ["GUIDED_LOCAL_SEARCH", "SIMULATED_ANNEALING"]:
            for tl in [10, 30]:
                t = time.time()
                plan, info = solve_model_a(inst, time_limit_s=tl, first_solution=fs, metaheuristic=mh)
                row = {"first_solution": fs, "metaheuristic": mh, "time_limit_s": tl,
                       "status": info["status"], "wall_s": round(time.time() - t, 1)}
                if plan is not None:
                    row.update(distance_km=round(info["distance_km"], 3), trucks_used=info["trucks_used"])
                    if best is None or info["distance_km"] < best[1]["distance_km"] - 1e-9:
                        best = (plan, info, row)
                runs.append(row)
                print("  ", row)
    # one long run as the reference
    plan, info = solve_model_a(inst, time_limit_s=120)
    row = {"first_solution": "PATH_CHEAPEST_ARC", "metaheuristic": "GUIDED_LOCAL_SEARCH", "time_limit_s": 120,
           "status": info["status"], "distance_km": round(info["distance_km"], 3), "trucks_used": info["trucks_used"]}
    runs.append(row); print("  ", row)
    if info["distance_km"] < best[1]["distance_km"] - 1e-9:
        best = (plan, info, row)
    df = pd.DataFrame(runs)
    df["depot"] = tag
    ok = df[df.status == "ok"]
    print(f"  spread across {len(ok)} runs: best {ok.distance_km.min():.2f} km, worst {ok.distance_km.max():.2f} km "
          f"({100 * (ok.distance_km.max() / ok.distance_km.min() - 1):.1f}% above best)")
    df.to_csv(f"{OUT_T}/m2_real_model_a_stability.csv", index=False)
    return inst, pts, seg, wards, G, best, tag


def part3(inst, pts, seg, wards, G, best, tag):
    os.makedirs(OUT_D, exist_ok=True)
    pts.to_csv(f"{OUT_D}/real_points.csv", index=False)
    np.save(f"{OUT_D}/real_dist_km.npy", inst.dist_km)
    np.save(f"{OUT_D}/real_base_min.npy", inst.base_min)
    json.dump({k: v for k, v in inst.meta.items()}, open(f"{OUT_D}/real_meta.json", "w"), indent=1)

    plan, info, row = best
    on_time, start = simulate(inst, plan, np.ones((1, inst.n + 1)))
    route_rows = []
    for v, r in enumerate(plan):
        for pos, j in enumerate(r):
            route_rows.append({"truck": v + 1, "pos": pos + 1, "point_id": j, "ward": inst.ward[j],
                               "households": int(inst.demand[j]),
                               "start_min": round(float(start[0, j]), 1),
                               "slack_to_11am_min": round(float(inst.win_end[j] - start[0, j]), 1)})
    rr = pd.DataFrame(route_rows)
    rr["depot"] = tag
    rr.to_csv(f"{OUT_T}/m2_real_model_a_plan.csv", index=False)
    print("\nBest Model A plan:", row)
    print("  slack to 11:00 by ward (min): ",
          rr.groupby("ward").slack_to_11am_min.describe()[["min", "25%", "50%"]].round(1).to_dict("index"))

    # map
    w = wards.to_crs(UTM)
    s = seg.to_crs(UTM) if seg.crs else seg
    import geopandas as gpd
    from shapely.geometry import LineString, Point
    p = gpd.GeoDataFrame(pts, geometry=gpd.points_from_xy(pts.lon, pts.lat), crs=4326).to_crs(UTM)
    dep = gpd.GeoSeries([Point(G.nodes[inst.meta["depot_osm"]]["x"], G.nodes[inst.meta["depot_osm"]]["y"])],
                        crs=4326).to_crs(UTM)
    fig, ax = plt.subplots(1, 2, figsize=(15, 8))
    colors = {"Nagasandra": "#2a6fdb", "Dodda Bidarakallu": "#e07b39"}
    for a in ax:
        w.boundary.plot(ax=a, color="black", linewidth=1)
        for name, g in s.groupby("ward"):
            g.plot(ax=a, color=colors[name], linewidth=0.5, alpha=0.35)
        dep.plot(ax=a, marker="*", color="red", markersize=300, zorder=5)
        a.set_axis_off()
    for name, g in p.groupby("ward"):
        g.plot(ax=ax[0], color=colors[name], markersize=g.households / 3, edgecolor="black", zorder=4, label=name)
    for _, r in p.iterrows():
        ax[0].annotate(str(r.point_id), (r.geometry.x, r.geometry.y), fontsize=6, ha="center", va="center")
    ax[0].legend(loc="lower left")
    ax[0].set_title("60 collection points (size = households) on collection streets\n"
                    f"red star = depot [{tag[:40]}]", fontsize=10)
    xy = {i + 1: (r.geometry.x, r.geometry.y) for i, r in p.reset_index(drop=True).iterrows()}
    xy[0] = (dep.iloc[0].x, dep.iloc[0].y)
    cmap = plt.get_cmap("tab20")
    for v, r in enumerate(plan):
        if not r:
            continue
        path = [0] + r + [0]
        ax[1].plot([xy[i][0] for i in path], [xy[i][1] for i in path], "-o", color=cmap(v % 20),
                   markersize=3, linewidth=1.2, label=f"truck {v + 1}")
    ax[1].set_title(f"Model A (OR-Tools), base times: {info['distance_km']:.1f} km, "
                    f"{info['trucks_used']} trucks\n(straight lines = order only; trucks follow real roads)",
                    fontsize=10)
    fig.suptitle(f"Nagasandra + Dodda Bidarakallu  |  depot: {tag[:60]}", fontsize=11)
    plt.tight_layout()
    fig.savefig(f"{OUT_F}/m2_real_points_and_model_a.png", dpi=160)
    print(f"  wrote {OUT_F}/m2_real_points_and_model_a.png")


def main():
    for d in (OUT_T, OUT_F):
        os.makedirs(d, exist_ok=True)
    part1()
    args = part2()
    part3(*args)
    stress_test(args[0], args[5][0])


def stress_test(inst, plan, out=f"{OUT_T}/m2_travel_stress_test.csv"):
    """How much slower would ALL road travel have to be before any stop misses 11:00?
    Answers whether travel-time randomness alone can create lateness in this design."""
    _, st = simulate(inst, plan, np.ones((1, inst.n + 1)))
    trav = sum(inst.base_min[a, b] for r in plan if r for a, b in zip([0] + r[:-1], r))
    serv = sum(inst.service[r].sum() for r in plan if r)
    rows = []
    for k in [1, 1.5, 2, 3, 4, 6, 8]:
        on, _ = simulate(inst, plan, np.full((1, inst.n + 1), float(k)))
        late = [j for j in inst.stops if not on[0, j]]
        rows.append({"travel_multiplier": k, "late_stops": len(late),
                     **{f"late_{w}": sum(inst.ward[j] == w for j in late) for w in inst.wards}})
    df = pd.DataFrame(rows)
    df["travel_share_of_work_pct"] = round(100 * trav / (trav + serv), 1)
    df.to_csv(out, index=False)
    print(f"\nStress test: travel = {100 * trav / (trav + serv):.1f}% of working time")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
