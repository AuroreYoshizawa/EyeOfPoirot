# Build status

This file distinguishes frozen decisions from implementation status.

| Workstream | Status | Acceptance condition |
|---|---|---|
| Methodology v0.2.1 | frozen (same-day pre-registration revision, before M101) | Markdown and rendered PDF agree |
| Raw archive | complete for frozen cutoff | 64/64/64/100 timelines; 2026 excludes M101–M104 |
| Source cross-check | complete | reused fields traced; four independent match pages checked; two display differences retained as `AUDIT` |
| Normalized tables | complete | schemas and row-count tests pass for four editions |
| Card-reason evidence | complete for M1–M100 cutoff | 908/908 in-play player cards classified; 25 explicit `unknown`; 35 StatsBomb linkage `AUDIT` plus one written-source `AUDIT`; full 2018/2022 Bad Behaviour census reconciled in a four-row public aggregate, with event-level StatsBomb details retained only in private raw |
| Availability / injury evidence | complete for all carded players | 783 players × full team schedules (3,306 rows), including group-stage eliminations; 57 served suspensions lineup-verified; 56 sourced positive intervals; no unexplained absence remains |
| Exposure and sensitivity | complete | primary setting; 72-row rho × mu × denominator grid; `T_end - 1` boundary check; §5.1 depth check |
| Expanded-cohort amendment | complete for 2014/2018/2022; provisional for 2026 M1–M100 | stripped ledger and suspensions rebuilt; full 32/32/32/48 cohort; `E_s^grp`, `E_s^all`, `E_s'`, MD2 grid, timing checks, and disclosed stripped correlations published as additive outputs |
| Cumulative foul order | complete where an event feed exists | 908 public card rows and 584 team-match sides; 2018/2022/2026 computed, 2014 labeled `source_unavailable`; provider-native IDs/order keys remain private |
| Expanded anchor reconciliation | complete with two retained `AUDIT` rows | exposure/rank anchors pass; 2018 stripped conceded-rate tau-b and 2022 stripped knockout timing p-value disagreements are documented without tuning |
| 2026 post-M104 rerun | pending scheduled matches | M101–M104 are not ingested; every current amendment output is labeled `provisional_M100` |
| Results and official figures | complete | twelve v0.2.1 SVGs generated (three per edition); old images archived as drafts |
| CI / fresh-clone check | complete locally | 44 tests, deterministic public rebuild, manifest verification, public/private event-field gate, and raw/secret scan pass without `data/raw/` |
| OSF registration | manual user step | public registration DOI recorded |
| OSF embargoed snapshot | manual user step | embargo DOI recorded; view-only link tested |
| GitHub public release | complete | public repository published; reproducibility workflow enabled |

## Resolved disciplinary-decision cases

Themba Zwane's three-match suspension is represented by M25, M54, and M73
service rows. Jarell Quansah's two-match decision is retained, with M99 as the
only service match inside the M1–M100 cutoff. FIFA's formal deferral of Folarin
Balogun's automatic ban is represented as `deferred`, so his M94 start is not
a conflict and contributes no served term. Fredy Guarín's carry-in suspension
is represented at 2014 M5.
All four decision sources and lineup checks are visible in
`data/derived/stages/s4-suspensions.csv` and `docs/RESULTS.md`.
