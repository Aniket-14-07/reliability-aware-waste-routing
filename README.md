# Reliability-Aware Waste Collection Routing (Bengaluru)

MSc Data Science research project, CHRIST (Deemed to be University), Bengaluru.
Team: Abel Mathews, Aliya Zuha, Aniket Agarwal. Guide: Dr. Vinay K.

**Question:** If waste trucks are routed only to minimise distance, do some wards get late collection more often when traffic is unpredictable? Can a reliability-aware planner close that gap without adding much distance?

> **Data honesty.** Everything is a simulation. Road network and ward boundaries are real (OBSERVED). Stops, waste amounts, time windows, fleet and traffic randomness are SYNTHETIC. No result here describes actual GBA/BBMP collection performance.

## Status

| Milestone | What | Status |
|---|---|---|
| M1 | Toy end-to-end: 6 stops, 2 wards, 2 trucks, exact solver, traffic simulator, reliability metrics | **Done** |
| M2 | OR-Tools Model A, checked against M1 exact answers; real road network for Nagasandra + Dodda Bidarakallu | Next |
| M3 | Model B on the real area (buffered windows + outer loop) | — |
| M4 | Model C: dynamic re-plan at 08:00 | — |
| M5 | Experiments, sensitivity, figures | — |

## Quick start

```bash
pip install -r requirements.txt
python -m pytest -q              # 6 tests should pass
python -m experiments.run_toy    # prints the M1 table, writes results/tables/toy_m1.csv
```

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
