"""M2 check: OR-Tools Model A must reproduce the EXACT optimum (M1 enumeration) on tiny instances.

1. The M1 toy instance (known answer: 1-3 | 2-6-5-4, 21.14 km).
2. 40 random tiny instances (6 stops, 2 trucks) with random positions, speeds, demands
   and windows, some tight enough to be infeasible. OR-Tools must give the same optimal
   distance (within 1 m of rounding per leg) and agree on infeasibility.
"""
import numpy as np
import pytest

from src.enumerate_solver import all_plans, feasible_base
from src.enumerate_solver import solve as exact_solve
from src.evaluate import plan_distance
from src.instance import Instance, load_toy
from src.ortools_solver import solve_model_a

TOY = load_toy("data/synthetic/toy_instance.json")


def random_tiny(seed, n=6):
    rng = np.random.default_rng(seed)
    xy = rng.uniform(0, 5, size=(n + 1, 2))
    ward = ["depot"] + list(rng.choice(["A", "B"], size=n))
    dist = np.linalg.norm(xy[:, None] - xy[None], axis=2) * 1.3
    speed = {"depot": 18.0, "A": float(rng.uniform(12, 24)), "B": float(rng.uniform(8, 18))}
    base_min = dist / np.array([speed[w] for w in ward])[None, :] * 60
    ws = np.concatenate([[0], rng.uniform(0, 60, n)])
    we = np.concatenate([[1e6], ws[1:] + rng.uniform(20, 120, n)])
    return Instance(
        n=n, ward=ward,
        demand=np.concatenate([[0], rng.integers(1, 3, n)]),
        service=np.concatenate([[0], rng.uniform(5, 20, n)]),
        win_start=ws, win_end=we,
        capacity=int(rng.integers(4, 8)), n_vehicles=2,
        dist_km=dist, base_min=base_min, traffic={},
    )


def test_toy_matches_exact():
    """Toy distances are symmetric, so a route and its reverse can tie. The exact solver
    lists ALL optimal plans; OR-Tools' plan must be one of them."""
    exact, _, _ = exact_solve(TOY)
    best = plan_distance(TOY, exact)
    optimal = {frozenset(map(tuple, filter(None, p)))
               for p in all_plans(TOY)
               if feasible_base(TOY, p) and abs(plan_distance(TOY, p) - best) < 1e-9}
    plan, info = solve_model_a(TOY, time_limit_s=2)
    assert info["status"] == "ok"
    assert plan_distance(TOY, plan) == pytest.approx(best, abs=1e-6)
    assert frozenset(map(tuple, filter(None, plan))) in optimal
    # 4 tied optimal plans: each of the two routes can be driven forwards or backwards.
    # They have the SAME distance but DIFFERENT ward reliability (see docs/decision_log.md D11).
    assert len(optimal) == 4


@pytest.mark.parametrize("seed", range(40))
def test_random_tiny_matches_exact(seed):
    inst = random_tiny(seed)
    exact, _, n_feas = exact_solve(inst)
    plan, info = solve_model_a(inst, time_limit_s=1)
    if exact is None:
        assert plan is None, "OR-Tools found a plan the exact solver says is impossible"
        return
    assert plan is not None and info["status"] == "ok"
    # allow 1 m per leg of integer rounding
    assert plan_distance(inst, plan) == pytest.approx(plan_distance(inst, exact), abs=0.001 * (inst.n + 2))
