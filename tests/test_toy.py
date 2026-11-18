"""M1 acceptance tests. Run from repo root:  python -m pytest -q"""
import numpy as np
import pytest

from src.enumerate_solver import all_plans, solve
from src.evaluate import simulate
from src.instance import load_toy
from src.traffic import TEST_SEED, TRAIN_SEED, make_scenarios

INST = load_toy("data/synthetic/toy_instance.json")


def test_hand_checked_timing():
    """Route depot -> 2 -> 6 -> 5 -> 4 with no traffic. Hand calculation (see README):
    stop 2: arrive 9.19, WAIT to 30.00 | stop 6: 70.81 | stop 5: 97.31 | stop 4: 124.58 (all <= 150)."""
    on_time, start = simulate(INST, [[2, 6, 5, 4], []], np.ones((1, INST.n + 1)))
    assert start[0, [2, 6, 5, 4]] == pytest.approx([30.00, 70.81, 97.31, 124.58], abs=0.01)
    assert on_time[0, [2, 6, 5, 4]].all()


def test_plan_count():
    # 6! orders x 7 split points / 2 (the two trucks are identical) = 2520
    assert sum(1 for _ in all_plans(INST)) == 2520


def test_same_seed_same_numbers():
    a = make_scenarios(INST, 100, TRAIN_SEED)
    b = make_scenarios(INST, 100, TRAIN_SEED)
    assert np.array_equal(a, b)


def test_train_and_test_differ():
    assert not np.array_equal(make_scenarios(INST, 100, TRAIN_SEED), make_scenarios(INST, 100, TEST_SEED))


def test_traffic_factors_mean_one():
    F = make_scenarios(INST, 200_000, 7)
    assert F[:, 1:].mean() == pytest.approx(1.0, abs=0.01)


def test_impossible_target_reports_infeasible():
    F = make_scenarios(INST, 500, TRAIN_SEED, intensity=3.0)
    plan, _, n_feasible = solve(INST, F, rho=1.0)
    assert plan is None and n_feasible == 0
