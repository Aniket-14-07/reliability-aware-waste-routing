"""Option 1 (decision D15): published collection slots under day-to-day uncertainty.

Why: in the real area, travel is only ~6% of an auto tipper's working time (M2 stress test), so
traffic alone cannot make households late against the 06:30-11:00 window. What residents feel is
WHEN the tipper comes ("arrival times are inconsistent", Deccan Herald). So each plan publishes a
collection SLOT of fixed width W per collection point, and we ask how often the truck keeps it.

Day-to-day uncertainty (one scenario = one working day), all mean-1 or mean-preserving:
  start delay   d_v  ~ Uniform(0, U)            per truck   (contract start 06:30 vs reported 07:30)
  service       s_i * xi_v * eta_i              xi_v = truck-day factor (crew size, absenteeism)
                                                eta_i = point factor (households not ready, etc.)
                                                both lognormal, mean 1, CV c_truck / c_point
  travel        base_ij * F_j                   city x ward lognormal factors (src/traffic.py)

Rules (decision D4 kept): if the truck reaches a point before its slot opens it WAITS;
the point is ON TIME if service starts no later than the slot end. Minutes late = max(0, start - slot end).

Common random numbers: every plan is scored on the SAME scenarios; truck v of every plan gets the
same (d_v, xi_v). TRAIN scenarios are used to set slots / choose parameters, TEST to score (D7).
"""
from dataclasses import dataclass

import numpy as np

from src.traffic import make_scenarios


def _lognormal_cv(rng, cv, size):
    """Lognormal with mean 1 and coefficient of variation cv."""
    if cv <= 0:
        return np.ones(size)
    s = np.sqrt(np.log(1 + cv ** 2))
    return rng.lognormal(mean=-s ** 2 / 2, sigma=s, size=size)


@dataclass
class Uncertainty:
    start_delay_max: float = 60.0     # U, minutes
    cv_truck: float = 0.15            # truck-day service factor
    cv_point: float = 0.20            # point-level service factor
    traffic_intensity: float = 1.0    # scales traffic sigmas (src/traffic.py)

    def label(self):
        return (f"U={self.start_delay_max:g} cvT={self.cv_truck:g} cvP={self.cv_point:g} "
                f"traffic x{self.traffic_intensity:g}")


def make_days(inst, n_days, seed, unc: Uncertainty):
    rng = np.random.default_rng(seed + 7)          # separate stream from traffic
    V = inst.n_vehicles
    return {
        "F": make_scenarios(inst, n_days, seed, unc.traffic_intensity),
        "delay": rng.uniform(0, unc.start_delay_max, size=(n_days, V)),
        "xi": _lognormal_cv(rng, unc.cv_truck, (n_days, V)),
        "eta": _lognormal_cv(rng, unc.cv_point, (n_days, inst.n + 1)),
    }


def nominal_days(inst):
    """A single 'everything as planned' day: no delay, all factors 1."""
    V = inst.n_vehicles
    return {"F": np.ones((1, inst.n + 1)), "delay": np.zeros((1, V)),
            "xi": np.ones((1, V)), "eta": np.ones((1, inst.n + 1))}


def simulate_slots(inst, plan, days, slot_start=None):
    """Service start times, shape (n_days, n+1). slot_start=None -> no waiting (free-running truck)."""
    S = days["F"].shape[0]
    start = np.full((S, inst.n + 1), np.nan)
    for v, route in enumerate(plan):
        t = days["delay"][:, v].copy()
        prev = 0
        for j in route:
            t = t + inst.base_min[prev, j] * days["F"][:, j]
            if slot_start is not None:
                t = np.maximum(t, slot_start[j])
            start[:, j] = t
            t = t + inst.service[j] * days["xi"][:, v] * days["eta"][:, j]
            prev = j
    return start


# ---------- slot-setting rules ----------------------------------------------------------------

def slots_nominal(inst, plan, W):
    """Model A rule: centre each slot on the planned (nothing-goes-wrong) time. This is what a
    planner publishes from a deterministic timetable."""
    t = simulate_slots(inst, plan, nominal_days(inst))[0]
    return _centre(inst, t, W)


def slots_median(inst, plan, W, train_days):
    """'Honest' rule: centre each slot on the MEDIAN arrival over TRAIN days (no peeking at TEST)."""
    t = np.nanmedian(simulate_slots(inst, plan, train_days), axis=0)
    return _centre(inst, t, W)


def _centre(inst, t, W):
    a = np.full(inst.n + 1, -np.inf)
    for j in inst.stops:
        a[j] = max(t[j] - W / 2, 0.0)              # a slot cannot open before 06:30
    return a


# ---------- scoring ---------------------------------------------------------------------------

def score(inst, plan, slot_start, W, days, weight="points"):
    """Per-day on-time shares by ward, plus point-level reliability and lateness."""
    st = simulate_slots(inst, plan, days, slot_start)
    stops = np.array(inst.stops)
    end = slot_start[stops] + W
    on = st[:, stops] <= end + 1e-9                               # (S, n_stops)
    late = np.maximum(st[:, stops] - end, 0)
    hh = inst.demand[stops].astype(float)
    out = {"p": on.mean(axis=0), "late_mean": late.mean(axis=0), "stops": stops,
           "slot_end_after_11": int((end > inst.win_end[stops]).sum()),
           "R_day": {}, "R": {}, "R_hh": {}}
    for w in inst.wards:
        m = np.array([inst.ward[i] == w for i in stops])
        out["R_day"][w] = on[:, m].mean(axis=1)                   # share of ward's points on time, per day
        out["R"][w] = float(out["R_day"][w].mean())
        out["R_hh"][w] = float((on[:, m] * hh[m]).sum(axis=1).mean() / hh[m].sum())
    R = out["R"]
    out["gap"] = max(R.values()) - min(R.values())
    out["min_R"] = min(R.values())
    out["late_mean_all"] = float(late.mean())
    out["late_p95_point"] = float(np.percentile(late, 95, axis=0).max())
    return out


# ---------- Model C: one slot update at 08:00 using only what is known by then (decision D2) ---

def score_dynamic(inst, plan, slot_start0, W, days, train_days, tau=90.0, notice=30.0, weight="points"):
    """Model C. Start from the static slots slot_start0. At time tau (08:00 = 90 min after 06:30)
    each truck reports which points it has started and when. For every point not yet started,
    the plan re-forecasts its arrival (median over TRAIN draws, rolled forward from the truck's
    estimated state) and RE-ANNOUNCES the slot, centred on that forecast - but only if the new
    slot opens at least `notice` minutes after tau (residents need warning); otherwise the old
    slot stays. Information used: start times observed up to tau only (no peeking).
    Returns the same dict as score() plus 'n_updated'."""
    S = days["F"].shape[0]
    M = train_days["F"].shape[0]
    stops = np.array(inst.stops)
    slot = np.tile(slot_start0, (S, 1))                         # per-day slot starts
    # 1) simulate up to tau with the static slots to get the observed state
    st0 = simulate_slots(inst, plan, days, slot_start0)
    n_upd = 0
    for v, route in enumerate(plan):
        if not route:
            continue
        route = list(route)
        obs = st0[:, route] <= tau                              # started by 08:00?
        k_last = obs.sum(axis=1) - 1                            # index of last started point (-1 = none)
        # nominal timetable for this route, used to estimate the truck's slowdown so far
        nom = np.cumsum([inst.base_min[a, b] + (inst.service[a] if a else 0.0)
                         for a, b in zip([0] + route[:-1], route)])
        rows = np.arange(S)
        s_first = st0[:, route[0]]
        s_last = st0[rows, np.array(route)[np.maximum(k_last, 0)]]
        span_obs = s_last - s_first
        span_nom = nom[np.maximum(k_last, 0)] - nom[0]
        r = np.where((k_last >= 1) & (span_nom > 0), span_obs / np.where(span_nom > 0, span_nom, 1), 1.0)
        r = np.clip(r, 0.5, 3.0)
        # estimated time the truck is free to leave its last started point (or the depot)
        svc_last = inst.service[np.array(route)[np.maximum(k_last, 0)]]
        # not started anything yet -> it left the depot at its (now known) start delay
        ready = np.where(k_last >= 0, np.maximum(tau, s_last + svc_last * r), days["delay"][:, v])
        # 2) roll forward with TRAIN draws (M samples per day), vectorised as (S, M)
        t = np.repeat(ready[:, None], M, axis=1)
        prev = np.where(k_last >= 0, np.array(route)[np.maximum(k_last, 0)], 0)
        for pos, j in enumerate(route):
            todo = k_last < pos                                 # day rows where j not yet started
            if not todo.any():
                continue
            # travel from previous point (prev differs per row only for the first remaining point)
            leg = inst.base_min[prev, j][:, None] * train_days["F"][None, :, j]
            t_new = t + leg
            # rows where j is not the first remaining point keep rolling; first-remaining rows start from ready
            fc = np.median(t_new, axis=1)
            new_a = np.maximum(fc - W / 2, 0.0)
            allow = todo & (new_a >= tau + notice)
            slot[allow, j] = new_a[allow]
            n_upd += int(allow.sum())
            svc = inst.service[j] * r[:, None] * train_days["eta"][None, :, j]
            t = np.where(todo[:, None], np.maximum(t_new, slot[:, j][:, None]) + svc, t)
            prev = np.where(todo, j, prev)
    # 3) re-simulate the whole day with per-day slots
    start = np.full((S, inst.n + 1), np.nan)
    for v, route in enumerate(plan):
        t = days["delay"][:, v].copy()
        prev = 0
        for j in route:
            t = t + inst.base_min[prev, j] * days["F"][:, j]
            t = np.maximum(t, slot[:, j])
            start[:, j] = t
            t = t + inst.service[j] * days["xi"][:, v] * days["eta"][:, j]
            prev = j
    end = slot[:, stops] + W
    on = start[:, stops] <= end + 1e-9
    late = np.maximum(start[:, stops] - end, 0)
    hh = inst.demand[stops].astype(float)
    out = {"p": on.mean(axis=0), "late_mean": late.mean(axis=0), "stops": stops,
           "slot_end_after_11": int((end.mean(axis=0) > inst.win_end[stops]).sum()),
           "R_day": {}, "R": {}, "R_hh": {}, "n_updated_per_day": n_upd / S}
    for w in inst.wards:
        m = np.array([inst.ward[i] == w for i in stops])
        out["R_day"][w] = on[:, m].mean(axis=1)
        out["R"][w] = float(out["R_day"][w].mean())
        out["R_hh"][w] = float((on[:, m] * hh[m]).sum(axis=1).mean() / hh[m].sum())
    R = out["R"]
    out["gap"] = max(R.values()) - min(R.values())
    out["min_R"] = min(R.values())
    out["late_mean_all"] = float(late.mean())
    out["late_p95_point"] = float(np.percentile(late, 95, axis=0).max())
    return out
