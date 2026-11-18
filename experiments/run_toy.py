"""Milestone M1: toy end-to-end run (SYNTHETIC data only).

For each traffic intensity:
  1. Model A  = exact min-distance CVRPTW (windows checked under base times).
  2. Model B  = exact min-distance plan with every ward's reliability >= rho on TRAIN scenarios.
  3. Both scored on the SAME held-out TEST scenarios (common random numbers).

Run from the repo root:   python -m experiments.run_toy
Output:                   results/tables/toy_m1.csv  (+ printed table)
"""
import os

import pandas as pd

from src.enumerate_solver import solve
from src.evaluate import metrics
from src.instance import load_toy
from src.traffic import TEST_SEED, TRAIN_SEED, make_scenarios

N_TRAIN, N_TEST = 500, 2000
INTENSITIES = [1.0, 1.5, 2.0]
RHOS = [0.90, 0.95, 0.99]


def main():
    inst = load_toy("data/synthetic/toy_instance.json")
    rows = []
    for k in INTENSITIES:
        F_train = make_scenarios(inst, N_TRAIN, TRAIN_SEED, intensity=k)
        F_test = make_scenarios(inst, N_TEST, TEST_SEED, intensity=k)

        plan_a, _, _ = solve(inst)
        runs = [("A (distance-first)", None, plan_a)]
        for rho in RHOS:
            runs.append((f"B (rho={rho})", rho, solve(inst, F_train, rho)[0]))

        d_a = metrics(inst, plan_a, F_test)["distance_km"]
        for name, rho, plan in runs:
            row = {"traffic_intensity": k, "model": name}
            if plan is None:
                row["status"] = "INFEASIBLE: no plan reaches rho on train scenarios"
                rows.append(row)
                continue
            m = metrics(inst, plan, F_test)
            row.update({
                "status": "ok",
                "plan": " | ".join("-".join(map(str, r)) for r in plan),
                "distance_km": round(m["distance_km"], 2),
                "extra_distance_pct": round(100 * (m["distance_km"] / d_a - 1), 1),
                **{f"R_{w}": round(v, 3) for w, v in m["R"].items()},
                "gap_pp": round(100 * m["gap"], 1),
                "min_R": round(m["min_R"], 3),
                "mean_late_min": round(m["mean_late_min"], 2),
            })
            rows.append(row)

    df = pd.DataFrame(rows)
    os.makedirs("results/tables", exist_ok=True)
    df.to_csv("results/tables/toy_m1.csv", index=False)
    print("SYNTHETIC TOY INSTANCE - pipeline check, NOT Bengaluru findings\n")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
