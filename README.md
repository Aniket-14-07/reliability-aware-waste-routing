# Reliability-Aware Waste Collection Routing (Bengaluru)

MSc Data Science research project, CHRIST (Deemed to be University), Bengaluru.
Team: Abel Mathews, Aliya Zuha, Aniket Agarwal. Guide: Dr. Vinay K.

**Question:** If waste trucks are routed only to minimise distance, do some wards get late collection more often when traffic is unpredictable? Can a reliability-aware planner close that gap without adding much distance?

> **Data honesty.** Every parameter is labelled OBSERVED / SOURCED / DERIVED / ASSUMED in `data/config/real_area.json`. Road network and ward boundaries are OBSERVED. Window and fleet norm are SOURCED. Point placement and demand are DERIVED. Speeds, household size and service time are ASSUMED until calibrated. Traffic randomness is SYNTHETIC. The depot is a PLACEHOLDER until `data/raw/facilities.json` is filled. No result here describes actual GBA/BBMP collection performance.

## Status

| Milestone | What | Status |
|---|---|---|
| M1 | Toy end-to-end: 6 stops, 2 wards, 2 trucks, exact solver, traffic simulator, reliability metrics | **Done** |
| M2 | OR-Tools Model A, checked against M1 exact answers; real road network for Nagasandra + Dodda Bidarakallu | **Done** (depot = placeholder until facilities.json) |
| M3 | Published slots under uncertainty: Models A, B, C on the real area + sensitivity | **Done** (depot = placeholder) |
| M4 | Model C: dynamic re-plan at 08:00 | — |
| M5 | Experiments, sensitivity, figures | — |

## Quick start

```bash
pip install -r requirements.txt
python -m pytest -q              # 56 tests should pass (~45 s)
python -m experiments.run_toy    # M1 table -> results/tables/toy_m1.csv
python -m experiments.run_m2     # M2 (~4 min): solver check, real instance, map, stress test
python -m experiments.run_m3     # M3 (~12 min): slots, Models A/B/C, sensitivity
```

## M2 results (2026-11-18)

**Solver check.** OR-Tools Model A gives the exact optimum on the toy and on 40 random tiny instances (41/41; 8 infeasible, both agree). Table: `results/tables/m2_ortools_vs_exact.csv`.

**Real area.** 60 collection points on real Nagasandra + Dodda Bidarakallu streets (30 each, split by population), 12,686 households, full one-way-aware travel-time matrix. Median network speed 16.6 km/h (TomTom 2025 city average is also 16.6 km/h). Dodda Bidarakallu has 95 km of collection streets vs 42 km in Nagasandra for a similar population, so its points are more spread out. Files: `data/derived/`, map `results/figures/m2_real_points_and_model_a.png`.

**Model A on the real area (PLACEHOLDER depot, so not a result):** best 57.7 km with 13-14 auto tippers; different search settings differ by up to 10.7% in distance, so Model A must be best-of-several runs (`m2_real_model_a_stability.csv`).

### D14 resolved -> option 1 (see M3)

## M3 results (2026-11-20) - published collection slots

Travel is ~6% of an auto tipper's day, so the question became: **how often does the truck arrive by the end of the slot it promised?** Each ward runs its own fleet (D16). All three models use the same distance-first routes; only the slot rule differs (D17). 2,000 test days, common random numbers, 95% CIs.

| Ward | A timetable | B simulation-based | C + 08:00 update | first stop (B) | last stop (B) |
|---|---|---|---|---|---|
| Dodda Bidarakallu (8 trucks) | 0.625 | 0.893 | 0.929 | 0.985 | 0.833 |
| Nagasandra (7 trucks) | 0.613 | 0.890 | 0.918 | 0.987 | 0.810 |

Paired gains: B-A = +0.27 (CI +/-0.005), C-B = +0.03 (CI +/-0.002) in both wards.

Findings (all PLACEHOLDER depot; depot sensitivity shows <=0.03 change):
1. **Most of the gain comes from how slots are set, not from routing.** Makespan-balanced routes change B by <=0.01.
2. **A's low score is mostly bias:** its timetable ignores the average start delay. With start delay up to 30 min instead of 60, A rises to 0.83 (B 0.92).
3. **No meaningful ward gap** (<=2.9 points in every case). **Unreliability is positional:** later stops in a route are less reliable (B: 0.98 first vs 0.81-0.83 last). C narrows this.
4. Ordering A < B < C holds in all 9 sensitivity cases (`results/tables/m3_sensitivity.csv`).

Figure: `results/figures/m3_reliability_by_position.png`. Questions for the guide: `docs/questions_for_guide.md`.

## How the model works (simple version)

1. **Plan.** Model A picks the shortest routes that are on time with normal traffic. Model B also demands that every ward is on time in at least `rho` of the practice (TRAIN) traffic days.
2. **Simulate.** Each traffic day slows every trip by a random factor: one city-wide factor x one factor for the ward the trip ends in. Factors average 1.
3. **Score.** On 2,000 new (TEST) traffic days, the same for every model:
   - `p_i` = share of days stop *i* is served on time
   - `R_w` = average `p_i` in ward *w*
   - gap = best ward minus worst ward; `min_R` = worst ward
4. **Timing rule.** Truck waits if early; on time means service starts by the window end.

## Files

```
data/raw/        real inputs (see data/raw/README.md for sources)
data/synthetic/  made-up inputs, clearly labelled
src/instance.py          load an instance, build distance & time matrices
src/traffic.py           seeded traffic scenarios (TRAIN seed 1001, TEST seed 2002)
src/evaluate.py          simulate a plan, compute p_i, R_w, gap, min_R, minutes late
src/enumerate_solver.py  exact solver for tiny instances (tries all 2,520 plans)
src/ortools_solver.py    Model A with OR-Tools (any size), float re-check of every plan
src/slots.py             slot model, uncertainty, Models A/B/C scoring
src/real_instance.py     real wards + OSM roads -> collection points + travel-time matrix
data/config/real_area.json  every real-area parameter with its source label
experiments/run_m2.py    M2 experiment
experiments/run_toy.py   M1 experiment
tests/test_toy.py        acceptance tests
docs/decision_log.md     every modelling decision and why
```

## M1 hand check (route depot -> 2 -> 6 -> 5 -> 4, no traffic)

Road km = straight-line km x 1.3. Speed 18 km/h into ward A, 12 km/h into ward B. Service 20 min. Window 30–150 min (07:00–09:00, t=0 is 06:30).

| Leg | km | minutes | arrive | start | leave |
|---|---|---|---|---|---|
| depot -> 2 | 2.76 | 9.19 | 9.19 | **30.00** (waits) | 50.00 |
| 2 -> 6 | 4.16 | 20.81 | 70.81 | 70.81 | 90.81 |
| 6 -> 5 | 1.30 | 6.50 | 97.31 | 97.31 | 117.31 |
| 5 -> 4 | 1.45 | 7.27 | 124.58 | 124.58 | 144.58 |

All starts are before 150, so all four stops are on time. `tests/test_toy.py` checks these exact numbers.
