"""Sanity checks for the slot model (src/slots.py) on the toy instance."""
import numpy as np

from src.enumerate_solver import solve
from src.instance import load_toy
from src.slots import (Uncertainty, make_days, nominal_days, score, score_dynamic, simulate_slots,
                       slots_median, slots_nominal)
from src.traffic import TEST_SEED, TRAIN_SEED

TOY = load_toy("data/synthetic/toy_instance.json")
PLAN, _, _ = solve(TOY)
NO_UNC = Uncertainty(start_delay_max=0, cv_truck=0, cv_point=0, traffic_intensity=0)


def test_no_uncertainty_everything_on_time():
    days = make_days(TOY, 50, TEST_SEED, NO_UNC)
    for a in (slots_nominal(TOY, PLAN, 30), slots_median(TOY, PLAN, 30, days)):
        r = score(TOY, PLAN, a, 30, days)
        assert r["min_R"] == 1.0 and r["late_mean_all"] == 0.0


def test_nominal_days_match_deterministic_timetable():
    st = simulate_slots(TOY, PLAN, nominal_days(TOY))[0]
    t, prev = 0.0, 0
    for j in PLAN[1]:
        t += TOY.base_min[prev, j]
        assert abs(st[j] - t) < 1e-9
        t += TOY.service[j]
        prev = j


def test_waiting_rule_never_serves_before_slot_opens():
    unc = Uncertainty()
    days = make_days(TOY, 200, TEST_SEED, unc)
    a = slots_median(TOY, PLAN, 30, make_days(TOY, 200, TRAIN_SEED, unc))
    st = simulate_slots(TOY, PLAN, days, a)
    for j in TOY.stops:
        assert (st[:, j] >= a[j] - 1e-9).all()


def test_mean_one_factors():
    days = make_days(TOY, 200_000, 1, Uncertainty())
    assert abs(days["xi"].mean() - 1) < 0.01 and abs(days["eta"].mean() - 1) < 0.01
    assert abs(days["delay"].mean() - 30) < 0.5


def test_dynamic_without_uncertainty_changes_nothing():
    days = make_days(TOY, 30, TEST_SEED, NO_UNC)
    a = slots_median(TOY, PLAN, 30, days)
    assert score_dynamic(TOY, PLAN, a, 30, days, days)["min_R"] == 1.0
