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
| M3 | Model B on the real area (buffered windows + outer loop) | Blocked on decision D14 |
| M4 | Model C: dynamic re-plan at 08:00 | — |
| M5 | Experiments, sensitivity, figures | — |

## Quick start

```bash
pip install -r requirements.txt
python -m pytest -q              # 51 tests should pass (~45 s)
python -m experiments.run_toy    # M1 table -> results/tables/toy_m1.csv
python -m experiments.run_m2     # M2 (~4 min): solver check, real instance, map, stress test
```

## M2 results (2026-11-18)

**Solver check.** OR-Tools Model A gives the exact optimum on the toy and on 40 random tiny instances (41/41; 8 infeasible, both agree). Table: `results/tables/m2_ortools_vs_exact.csv`.

**Real area.** 60 collection points on real Nagasandra + Dodda Bidarakallu streets (30 each, split by population), 12,686 households, full one-way-aware travel-time matrix. Median network speed 16.6 km/h (TomTom 2025 city average is also 16.6 km/h). Dodda Bidarakallu has 95 km of collection streets vs 42 km in Nagasandra for a similar population, so its points are more spread out. Files: `data/derived/`, map `results/figures/m2_real_points_and_model_a.png`.

**Model A on the real area (PLACEHOLDER depot, so not a result):** best 57.7 km with 13-14 auto tippers; different search settings differ by up to 10.7% in distance, so Model A must be best-of-several runs (`m2_real_model_a_stability.csv`).

### Decision needed (D14) before Model B

Travel is only **6%** of an auto tipper's working day; 94% is door-to-door service. Every road leg must be **6x slower** before one stop misses 11:00 (`m2_travel_stress_test.csv`). So random traffic alone cannot create a ward reliability gap here, and the A-vs-B comparison would show nothing. Options:

1. **Recommended:** keep CVRPTW, but (a) make the uncertain parts the ones that really vary: start delay, service time per household, travel; and (b) score "on time" against a **published collection slot** per point (e.g. 60 min), which is what residents feel ("arrival times are inconsistent"). Needs field data: daily auto-tipper arrival times at a few homes for ~2 weeks.
2. Keep the 06:30-11:00 window and only travel randomness: honest but almost certainly a null result.
3. Switch to the compactor layer (transfer point -> processing plant), where travel dominates. Needs transfer-point locations; fewer stops per ward.

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
