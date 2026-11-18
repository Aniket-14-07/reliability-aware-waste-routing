# Raw data (OBSERVED)

| File | Source | Downloaded | Licence | Notes |
|---|---|---|---|---|
| `gba-369-wards-december-2025.kml` | OpenCity, "GBA Wards Delimitation 2025" — https://data.opencity.in/dataset/gba-wards-delimitation-2025 | Nov 2026 | Public Domain (per OpenCity) | Final 369 GBA wards with population fields (appear to be 2011-census based). 8 geometries are invalid — fix with `make_valid()`. |
| `nagasandra_dbk_drive.graphml` | OpenStreetMap via OSMnx 2.x, `graph_from_bbox((77.47502, 13.00929, 77.51505, 13.05608), network_type="drive")` | 18 Nov 2026 | ODbL (© OpenStreetMap contributors) | Nagasandra + Dodda Bidarakallu wards + 500 m buffer. 5,901 nodes, 14,837 directed edges, 895 km of edge length; largest strongly connected component = 5,868 nodes. Only 84 edges carry `maxspeed`, so speeds will be imputed (DERIVED). |

Not used: the 225-ward KML (old BBMP delimitation, superseded), the draft-delimitation population CSV (draft numbers differ from final), and the processing-plant CSV (no coordinates or date).
