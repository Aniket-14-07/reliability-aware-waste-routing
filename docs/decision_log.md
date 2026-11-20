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
| D14 | RESOLVED by D15. Was: With D13, travel is only 6% of an auto tipper's working time; all travel must be 6x slower before 1 of 60 stops misses 11:00. Travel-time randomness alone therefore cannot produce a ward reliability gap in this design. Team must choose how uncertainty / on-time is defined before Model B. | Resolved 2026-11-20 |
| D15 | Option 1 adopted (team, 2026-11-20): each plan publishes a fixed-width collection slot (60 min) per point; uncertainty = start delay U(0,60) + service time (truck-day CV 0.15, point CV 0.20) + traffic. On time = service starts by slot end (truck waits if early, D4). Only public data; no fieldwork. | Confirmed by team |
| D16 | Ward-wise operation: each ward has its own fleet (norm ceil(HH/1000)) and trucks never cross wards. SOURCED: BBMP ward-wise tenders; auto tippers work within microplan blocks. | Proposed |
| D17 | Models: A = slots centred on deterministic timetable; B = slots centred on TRAIN-median arrival; C = B + one re-announcement at 08:00 (30 min notice) from observed progress. Same distance-first routes for A/B/C; routing tested separately (makespan-balanced routes). | Proposed |
| D18 | Household size 3.71 (Census 2011 HH/population of old BBMP wards 14, 15, 39, 40), replacing assumed 4.0. | Proposed |
| D19 | Finding: ward gap is small (<=2.9 points in every case); unreliability is POSITIONAL (later stops in a route). Equity framing should move from ward-level to street/position-level - guide to confirm. | **Guide to confirm** |

## Change history
- 2026-11-18: M1 toy pipeline built and tested.
- 2026-11-18: M2 built. OR-Tools Model A matches exact optimum on 41/41 tiny instances. Real-area instance (60 points, 12,686 HH, travel-time matrix) built. Depot still PLACEHOLDER. Finding D14 raised.
- 2026-11-20: M3 built (slots, Models A/B/C, sensitivity). Base: A 0.61-0.62, B 0.89, C 0.92-0.93 on-time; ordering holds in all 9 sensitivity cases.
