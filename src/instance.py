"""Load a routing instance and build distance / base travel-time matrices.

Node 0 is always the depot. Nodes 1..n are collection points.
Distances are in km, times in minutes.
"""
import json
from dataclasses import dataclass

import numpy as np


@dataclass
class Instance:
    n: int                    # number of collection points (depot excluded)
    ward: list                # ward label per node; index 0 = "depot"
    demand: np.ndarray        # per node, depot = 0
    service: np.ndarray       # service minutes per node, depot = 0
    win_start: np.ndarray     # window start (minutes from time origin)
    win_end: np.ndarray       # window end
    capacity: int
    n_vehicles: int
    dist_km: np.ndarray       # (n+1, n+1)
    base_min: np.ndarray      # (n+1, n+1) travel minutes with NO traffic
    traffic: dict             # traffic parameters

    @property
    def wards(self):
        return sorted(set(self.ward[1:]))


def load_toy(path):
    cfg = json.load(open(path))
    nodes = [cfg["depot"]] + cfg["stops"]
    n = len(cfg["stops"])
    xy = np.array([[p["x_km"], p["y_km"]] for p in nodes])
    ward = ["depot"] + [s["ward"] for s in cfg["stops"]]

    straight = np.linalg.norm(xy[:, None, :] - xy[None, :, :], axis=2)
    dist = straight * cfg["road"]["circuity_factor"]

    speed = cfg["road"]["base_speed_kmph"]
    # speed of leg i->j is the speed of the ward that j is in
    end_speed = np.array([speed[w] for w in ward])
    base_min = dist / end_speed[None, :] * 60.0

    zero = {"demand": 0, "service_min": 0, "window_min": [0, 10**6]}
    get = lambda k: [zero[k] if i == 0 else nodes[i][k] for i in range(n + 1)]
    win = np.array(get("window_min"), dtype=float)

    return Instance(
        n=n, ward=ward,
        demand=np.array(get("demand")), service=np.array(get("service_min"), dtype=float),
        win_start=win[:, 0], win_end=win[:, 1],
        capacity=cfg["vehicles"]["capacity"], n_vehicles=cfg["vehicles"]["count"],
        dist_km=dist, base_min=base_min, traffic=cfg["traffic"],
    )
