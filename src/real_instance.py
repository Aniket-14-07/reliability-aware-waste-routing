"""Build the REAL-AREA instance: Nagasandra + Dodda Bidarakallu on the OSM road network.

Pipeline (each step is deterministic given the config + seed):
  1. Ward polygons from the GBA 369-ward KML (OBSERVED), repaired with make_valid().
  2. OSM drive graph (OBSERVED), restricted to its largest strongly connected component
     so every point can reach every other point and get back (one-way streets respected).
  3. Edge speeds from the road-type table in data/config/real_area.json (ASSUMED until calibrated);
     travel_time = length / speed.
  4. Street segments (decision D5) = undirected road pieces of collection road types whose
     midpoint lies inside a study ward.
  5. Collection points: in each ward, length-weighted k-means on segment midpoints; the number of
     clusters per ward is proportional to ward population. Each cluster becomes one point, placed
     at the segment END NODE nearest the cluster centre (so it is a real road junction inside the
     cluster, inside the ward).
  6. Demand: ward population is shared out by street length (more frontage -> more homes), then
     households = persons / household size; service time = households x minutes per household.
  7. Travel-time matrix: fastest path (Dijkstra on travel_time) between every pair of nodes;
     distance = length of that same path.
"""
import json
import math

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from shapely.geometry import LineString, Point
from sklearn.cluster import KMeans

from src.instance import Instance

UTM = "EPSG:32643"     # metres, Bengaluru is in UTM zone 43N
KML = "data/raw/gba-369-wards-december-2025.kml"
GRAPH = "data/raw/nagasandra_dbk_drive.graphml"


def _v(cfg, key):
    return cfg[key]["value"]


def _road_type(h):
    """OSM 'highway' can be a list (merged edges). Use the first listed type."""
    if isinstance(h, list):
        return h[0]
    if isinstance(h, str) and h.startswith("["):
        return h.strip("[]").split(",")[0].strip(" '\"")
    return h


def load_wards(cfg):
    g = gpd.read_file(KML)
    rows = []
    for w in _v(cfg, "wards"):
        r = g[(g.Corporation == w["corporation"]) & (g.ward_id.astype(str) == w["ward_id"])]
        assert len(r) == 1, f"ward {w} not found exactly once"
        rows.append(r)
    wards = pd.concat(rows).copy()
    wards["geometry"] = wards.geometry.make_valid()
    wards = wards.set_crs(4326, allow_override=True)
    wards["population"] = wards[_v(cfg, "population_field")].astype(float)
    return wards[["ward_name", "ward_id", "Corporation", "population", "geometry"]].reset_index(drop=True)


def load_graph(cfg):
    G = ox.load_graphml(GRAPH)
    big = max(nx.strongly_connected_components(G), key=len)
    G = G.subgraph(big).copy()
    speed = _v(cfg, "speed_kmph_by_road_type")
    unknown = set()
    for u, v, k, d in G.edges(keys=True, data=True):
        rt = _road_type(d.get("highway"))
        if rt not in speed:
            unknown.add(rt)
        kmph = speed.get(rt, speed["residential"])
        d["road_type"] = rt
        d["speed_kmph"] = kmph
        d["travel_time_min"] = d["length"] / 1000.0 / kmph * 60.0
    return G, sorted(map(str, unknown))


def street_segments(G, wards, cfg):
    """One row per undirected road piece of a collection road type, with the ward it lies in."""
    keep = set(_v(cfg, "collection_road_types"))
    seen, rows = set(), []
    for u, v, k, d in G.edges(keys=True, data=True):
        if d["road_type"] not in keep:
            continue
        key = (min(u, v), max(u, v))
        if key in seen:
            continue
        seen.add(key)
        geom = d.get("geometry") or LineString([(G.nodes[u]["x"], G.nodes[u]["y"]),
                                               (G.nodes[v]["x"], G.nodes[v]["y"])])
        rows.append({"u": u, "v": v, "length_m": float(d["length"]),
                     "road_type": d["road_type"], "geometry": geom})
    seg = gpd.GeoDataFrame(rows, crs=4326).to_crs(UTM)
    mid = seg.geometry.interpolate(0.5, normalized=True)
    w = wards.to_crs(UTM)
    seg["ward"] = None
    for _, r in w.iterrows():
        seg.loc[mid.within(r.geometry).values, "ward"] = r.ward_name
    seg["mx"], seg["my"] = mid.x.values, mid.y.values
    return seg[seg.ward.notna()].reset_index(drop=True)


def place_points(G, seg, wards, cfg):
    K = _v(cfg, "n_points_total")
    pop = dict(zip(wards.ward_name, wards.population))
    total = sum(pop.values())
    # largest-remainder split of K by population
    raw = {w: K * p / total for w, p in pop.items()}
    k = {w: int(math.floor(x)) for w, x in raw.items()}
    for w in sorted(raw, key=lambda w: raw[w] - k[w], reverse=True)[: K - sum(k.values())]:
        k[w] += 1

    node_xy = gpd.GeoSeries([Point(G.nodes[n]["x"], G.nodes[n]["y"]) for n in G.nodes],
                            index=list(G.nodes), crs=4326).to_crs(UTM)
    hh_size = _v(cfg, "household_size")
    s_per_hh = _v(cfg, "service_min_per_household")
    seed = _v(cfg, "random_seed")

    ward_geom = {r.ward_name: r.geometry.buffer(30) for _, r in wards.to_crs(UTM).iterrows()}
    pts, used = [], set()
    seg = seg.copy()
    seg["cluster"] = -1
    for w in sorted(k):
        s = seg[seg.ward == w]
        km = KMeans(n_clusters=k[w], n_init=10, random_state=seed)
        lab = km.fit_predict(s[["mx", "my"]].values, sample_weight=s.length_m.values)
        seg.loc[s.index, "cluster"] = lab
        ward_len = s.length_m.sum()
        for c in range(k[w]):
            sc = s[lab == c]
            cand = sorted((set(sc.u) | set(sc.v)) - used)
            # junction must lie in this ward (30 m tolerance for boundary roads)
            inside = [n for n in cand if ward_geom[w].contains(node_xy[n])]
            cand = inside or cand
            cx, cy = km.cluster_centers_[c]
            dd = [(node_xy[n].x - cx) ** 2 + (node_xy[n].y - cy) ** 2 for n in cand]
            node = cand[int(np.argmin(dd))]
            used.add(node)
            persons = pop[w] * sc.length_m.sum() / ward_len
            hh = persons / hh_size
            pts.append({
                "point_id": len(pts) + 1, "ward": w, "osm_node": int(node),
                "lat": G.nodes[node]["y"], "lon": G.nodes[node]["x"],
                "street_length_m": round(float(sc.length_m.sum()), 1),
                "n_segments": int(len(sc)),
                "persons": round(persons, 1), "households": int(round(hh)),
                "service_min": round(hh * s_per_hh, 2),
            })
    return pd.DataFrame(pts), seg, k


def placeholder_depot(G, pts):
    """PLACEHOLDER ONLY: node nearest the household-weighted centre of all points.
    Used to test the pipeline until the real mustering point is known."""
    lat = np.average(pts.lat, weights=pts.households)
    lon = np.average(pts.lon, weights=pts.households)
    return int(ox.distance.nearest_nodes(G, lon, lat))


def _fastest_edge(G, a, b):
    """Between a and b there can be parallel edges; Dijkstra used the fastest one."""
    return min(G[a][b].values(), key=lambda e: e["travel_time_min"])


def travel_matrices(G, nodes):
    n = len(nodes)
    T = np.full((n, n), np.inf)
    D = np.full((n, n), np.inf)
    index = {nd: i for i, nd in enumerate(nodes)}
    for i, src in enumerate(nodes):
        dist, paths = nx.single_source_dijkstra(G, src, weight="travel_time_min")
        for nd, j in index.items():
            T[i, j] = dist[nd]
            p = paths[nd]
            D[i, j] = sum(_fastest_edge(G, a, b)["length"] for a, b in zip(p[:-1], p[1:])) / 1000.0
    assert np.isfinite(T).all(), "some pair unreachable - graph not strongly connected?"
    return D, T


def build(cfg_path="data/config/real_area.json", facilities_path=None, traffic=None):
    cfg = json.load(open(cfg_path))
    wards = load_wards(cfg)
    G, unknown = load_graph(cfg)
    seg = street_segments(G, wards, cfg)
    pts, seg, k = place_points(G, seg, wards, cfg)

    depot_label, end_node_osm = "PLACEHOLDER", None
    if facilities_path:
        fac = json.load(open(facilities_path))
        d = fac["depot"]
        depot = int(ox.distance.nearest_nodes(G, d["lon"], d["lat"]))
        depot_label = "OBSERVED: " + str(d.get("evidence"))
        tp = fac.get("transfer_point") or {}
        if tp.get("lat") is not None:
            end_node_osm = int(ox.distance.nearest_nodes(G, tp["lon"], tp["lat"]))
    else:
        depot = placeholder_depot(G, pts)

    nodes = [depot] + pts.osm_node.tolist() + ([end_node_osm] if end_node_osm else [])
    D, T = travel_matrices(G, nodes)

    n = len(pts)
    extra = 1 if end_node_osm else 0
    win = _v(cfg, "household_window_min")
    hh = np.concatenate([[0], pts.households.values, [0] * extra])
    total_hh = int(pts.households.sum())
    cap = _v(cfg, "vehicle_capacity_households")
    inst = Instance(
        n=n + extra,
        ward=["depot"] + pts.ward.tolist() + (["end"] if extra else []),
        demand=hh.astype(int),
        service=np.concatenate([[0], pts.service_min.values, [0] * extra]).astype(float),
        win_start=np.array([0] + [win[0]] * n + [0] * extra, dtype=float),
        win_end=np.array([1e6] + [win[1]] * n + [1e6] * extra, dtype=float),
        capacity=int(cap),
        n_vehicles=int(math.ceil(total_hh / cap)) + int(_v(cfg, "fleet_extra")),
        dist_km=D, base_min=T, traffic=traffic or {},
        end_node=(n + 1) if extra else 0,
        meta={"depot_osm": depot, "depot_label": depot_label, "nodes": nodes,
              "points_per_ward": k, "unknown_road_types": unknown,
              "n_segments": int(len(seg)), "total_households": total_hh},
    )
    return inst, pts, seg, wards, G
