"""Generate repeatable traffic scenarios.

Each scenario r draws one city-wide factor g_r and one factor per ward w_{ward,r}.
A leg i -> j in scenario r takes   base_min[i, j] * g_r * w_{ward(j), r].
All factors are lognormal with mean exactly 1, so "no traffic surprise" = base time.

TRAIN and TEST scenarios use different seeds (decision D7):
the planner only ever sees TRAIN; models are scored only on TEST.
"""
import numpy as np

TRAIN_SEED = 1001
TEST_SEED = 2002


def _lognormal_mean1(rng, sigma, size):
    # if X ~ LogNormal(mu, sigma) then E[X] = exp(mu + sigma^2/2); set mu so E[X] = 1
    return rng.lognormal(mean=-sigma**2 / 2, sigma=sigma, size=size)


def make_scenarios(inst, n_scen, seed, intensity=1.0):
    """Return an array F of shape (n_scen, n+1): F[r, j] = factor for any leg ending at node j.

    intensity scales every sigma (1.0 = default, 1.5 = 50% more variable traffic).
    """
    rng = np.random.default_rng(seed)
    t = inst.traffic
    g = _lognormal_mean1(rng, t["global_sigma"] * intensity, n_scen)
    ward_f = {w: _lognormal_mean1(rng, s * intensity, n_scen) for w, s in sorted(t["ward_sigma"].items())}
    F = np.empty((n_scen, inst.n + 1))
    for j, w in enumerate(inst.ward):
        F[:, j] = g * (ward_f[w] if w in ward_f else 1.0)
    return F
