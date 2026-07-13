# Build status

This file distinguishes frozen decisions from implementation status.

| Workstream | Status | Acceptance condition |
|---|---|---|
| Methodology v0.2 | frozen | Markdown and rendered PDF agree |
| Raw archive | complete for frozen cutoff | 64/64/64/100 timelines; 2026 excludes M101–M104 |
| Source cross-check | complete | reused fields traced; four independent match pages checked; two display differences retained as `AUDIT` |
| Normalized tables | complete | schemas and row-count tests pass for four editions |
| Availability / injury evidence | complete | 56 sourced intervals; every positive interval has a URL; no unexplained absence remains |
| Exposure and sensitivity | complete | primary setting; 72-row rho × mu × denominator grid; `T_end - 1` boundary check |
| Results and official figures | complete | eight v0.2 SVGs generated; old images archived as drafts |
| CI / fresh-clone check | complete locally | tests, public rebuild, raw/secret scan pass without `data/raw/` |
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
