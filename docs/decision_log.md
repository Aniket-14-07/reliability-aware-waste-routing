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

## Change history
- 2026-11-18: M1 toy pipeline built and tested.
