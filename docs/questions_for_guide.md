# Questions for Dr. Vinay K — reliability-aware waste collection (Nagasandra + Dodda Bidarakallu)

Prepared 2026-11-20 after milestone M3. Numbers come from `results/tables/m3_*.csv` (2,000 simulated test days).

## What we built (one paragraph to read out)

We placed 60 collection points on the real streets of Nagasandra and Dodda Bidarakallu: 30 per ward, 13,676 households, using Census 2011 population and the OSM road network. Each ward runs its own auto-tipper fleet under the BBMP norm (1 per 1,000 households). Routes are distance-minimising (OR-Tools), checked against an exact solver on 41 small cases. Each plan publishes a 60-minute collection slot per point. Every simulated day has a random start delay, random collection time and random traffic. We compare three ways of setting slots:
- **A:** from the deterministic timetable.
- **B:** from simulated median arrival times.
- **C:** B, plus one update of the slots at 08:00 based on each truck's progress.

## Results in one table

| | A | B | C |
|---|---|---|---|
| Dodda Bidarakallu on-time share | 0.62 | 0.89 | 0.93 |
| Nagasandra on-time share | 0.61 | 0.89 | 0.92 |
| Last stop in a route (B) | | 0.81–0.83 | 0.87–0.89 |

The A < B < C ordering holds in all 9 sensitivity cases. These vary start delay, collection-time variability, traffic, slot width, fleet norm and depot location.

## Decisions we need you to confirm

1. **Equity framing (biggest change).** The two wards differ by at most 2.9 percentage points in every case, so a ward-level fairness claim is not supported. The unfairness we do find is by **position in the route**: with B, the first stop is on time 98% of days and the last stop only 81–83%. *Can the paper's equity angle be street/route-position level instead of ward level, with the title adjusted?*

2. **Routing contributes little.** Balanced routes change on-time share by at most 1 point. The gains come from how slots are set (+27 points) and from the 08:00 update (+3 points). *Is it acceptable that the paper's contribution is scheduling and information under uncertainty, with routing as the base layer?*

3. **Model A's weakness is mostly a bias.** It publishes times as if trucks start exactly at 06:30. If start delays are at most 30 min (instead of 60), A rises from 0.62 to 0.83. *Is A a fair baseline, or should we also show A shifted by the average delay? (B already does essentially that.)*

4. **No public data on day-to-day variability.** BSWML says none of Bengaluru's 5,150 auto tippers have GPS, so no arrival-time data exists. Start delay, collection-time variability and traffic variability are assumed, bounded by sources (contract start 06:30; reported start ~07:30), and tested over a grid. *Is "scenario-based with sensitivity analysis" acceptable for publication?*

5. **Model C as the dynamic model.** Our decision D2 said "re-plan once at 08:00". We implemented this as re-announcing the remaining slots from observed progress (like BBMP's track-your-tipper idea), not re-routing. *Is that acceptable?*

6. **Waiting rule.** We assume a truck that arrives before a slot opens waits. In reality auto tippers may not wait, and an early arrival can mean a missed household. *Keep, or treat early arrival as a failure too?*

## Known limitations (to state in the paper)

- **Population is Census 2011.** The old Dodda Bidarakallu ward grew 276% in 2001–2011, so today's loads are higher. Fleet and demand use the same numbers, so ratios stay consistent, but absolute loads are understated.
- **Household size 3.71** comes from Census 2011 household and population counts of the four old BBMP wards covering the area.
- **Depot location is unknown** (it's the ward mustering point). Results change by ≤0.03 when we move it to the farthest point.
- **Multi-trip operation not modelled.** An auto tipper holds 500 kg (BBMP Time & Motion Study 2015), so in reality it empties mid-shift at a transfer point.
- **Fleet:** Dodda Bidarakallu needs 1 truck above the 1,000-household norm (8 vs 7) to fit everyone; Nagasandra fits the norm.
- **Collection points are aggregates** (~230 households each), placed by street length, not by real house locations.
- **Study area is two wards.** The pipeline can run more wards if you want broader evidence.

## Is the study area right?

We recommend keeping these two wards:
- BBMP's 2017 microplans exist for old ward 40 (Dodda Bidarakallu) and the neighbouring wards 14, 15 and 39, so we can check our setup against BBMP's own auto-tipper blocks.
- The main findings (slot setting dominates; position-based unfairness) come from how door-to-door collection works, not from these particular wards, so changing wards would not change them.
