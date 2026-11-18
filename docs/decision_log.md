# Decision log

| # | Decision | Status |
|---|---|---|
| D1 | Problem class: capacitated VRP with time windows (CVRPTW) under stochastic travel times. DARP used only as motivation (user-centred service quality), not as the formulation. | Agreed by team |
| D2 | Scope: stochastic core (Model A, Model B) + one dynamic model (Model C): re-plan remaining stops once at 08:00 using only traffic observed up to 08:00. | Agreed by team |
| D3 | Title: reliability-aware routing under stochastic travel times, ward-level service equity. | Wording to confirm with guide |
| D4 | Truck waits if early, never serves before the window opens. On time = service start <= window end. Minutes late also recorded. | Agreed |
| D5 | Spatial unit: a street segment aggregated into one collection point. | Agreed |
| D6 | Model A = CVRPTW meeting windows under base travel times (fair baseline, not a strawman). | Agreed |
| D7 | Planning uses TRAIN scenarios (seed 1001); all scoring uses held-out TEST scenarios (seed 2002); both models see identical TEST scenarios. | Agreed |
| D8 | Geography: final GBA 369-ward map (Dec 2025). Study area: Nagasandra + Dodda Bidarakallu (adjacent, West Corporation). | Agreed |
| D9 | Model B method for real instances: buffered time windows + outer loop. Toy instance uses exact enumeration as ground truth. | Proposed |
| D10 | Traffic model: leg factor = city factor x ward factor of the leg's end; lognormal, mean 1. Parameters are SYNTHETIC until calibrated. | Proposed |
| D11 | Model A tie-breaking: distance-optimal plans can tie (toy: 4 tied plans) yet give OPPOSITE ward rankings (toy, traffic x2: A 1.000/B 0.945 vs A 0.945/B 0.972). A baseline "inequity" can therefore be an artefact of which tied/near-tied plan the solver returns. Safeguard: report Model A as best-of-several OR-Tools runs AND show the reliability spread over its near-optimal plans. | Proposed |
| D12 | Real-area points (D5 implemented): collection streets (residential, tertiary, etc.; NOT motorway/trunk) inside each ward; length-weighted k-means; 60 points split by ward population (30/30); each point = a real junction inside its own ward. Demand = ward population shared by street length / 4.0 persons per household. | Proposed |
| D13 | Window = contractual household period 06:30-11:00 (SOURCED, BBMP/BSWML scope). Capacity = 1000 households per auto tipper (SOURCED norm). Fleet available = norm + 1 (14); best plan uses 13. | Proposed |
| D14 | **OPEN - blocks M3.** With D13, travel is only 6% of an auto tipper's working time; all travel must be 6x slower before 1 of 60 stops misses 11:00. Travel-time randomness alone therefore cannot produce a ward reliability gap in this design. Team must choose how uncertainty / on-time is defined before Model B (see README "Decision needed"). | **Team to decide** |

## Change history
- 2026-11-18: M1 toy pipeline built and tested.
- 2026-11-18: M2 built. OR-Tools Model A matches exact optimum on 41/41 tiny instances. Real-area instance (60 points, 12,686 HH, travel-time matrix) built. Depot still PLACEHOLDER. Finding D14 raised.
