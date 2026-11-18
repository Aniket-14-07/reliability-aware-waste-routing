"""M2 checks on the real-area instance (no solver run, ~6 s)."""
import numpy as np
import geopandas as gpd
import pytest

from src.real_instance import UTM, build


@pytest.fixture(scope="module")
def built():
    return build()


def test_sixty_points_split_by_population(built):
    inst, pts, seg, wards, G = built
    assert inst.n == 60
    assert inst.meta["points_per_ward"] == {"Nagasandra": 30, "Dodda Bidarakallu": 30}
    assert pts.osm_node.is_unique


def test_every_point_inside_its_ward(built):
    inst, pts, seg, wards, G = built
    w = wards.to_crs(UTM).set_index("ward_name")
    p = gpd.GeoDataFrame(pts, geometry=gpd.points_from_xy(pts.lon, pts.lat), crs=4326).to_crs(UTM)
    for _, r in p.iterrows():   # snapped to a junction: allow 30 m on the boundary
        assert w.loc[r.ward].geometry.buffer(30).contains(r.geometry), r.point_id


def test_population_conserved(built):
    inst, pts, seg, wards, G = built
    for _, r in wards.iterrows():
        assert pts[pts.ward == r.ward_name].persons.sum() == pytest.approx(r.population, rel=1e-3)


def test_matrix_complete_and_sane(built):
    inst, *_ = built
    T, D = inst.base_min, inst.dist_km
    assert np.isfinite(T).all() and np.isfinite(D).all()
    assert np.allclose(np.diag(T), 0)
    off = ~np.eye(len(T), dtype=bool)
    speed = D[off] / T[off] * 60
    assert 9.9 <= speed.min() and speed.max() <= 40.1      # inside the speed table's range
