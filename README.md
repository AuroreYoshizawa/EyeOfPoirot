# Eye of Poirot

**Sanction-exposure metrics for FIFA World Cup disciplinary records,
2014–2026.**

[![reproducibility](https://github.com/AuroreYoshizawa/EyeOfPoirot/actions/workflows/ci.yml/badge.svg)](https://github.com/AuroreYoshizawa/EyeOfPoirot/actions/workflows/ci.yml)

[中文说明 → README.zh-CN.md](README.zh-CN.md)

> **Frozen scope (2026-07-13).** The analysis covers the complete 2014, 2018,
> and 2022 World Cups and completed 2026 matches M1–M100. Unplayed 2026
> matches M101–M104 are not included. Methodology v0.2 was frozen before M101
> and revised the same day to v0.2.1 — still before M101 and before any
> registration — to restore four commissioned rules and add one; the five
> changes and their directions are enumerated in the methodology §6 and in
> `docs/AMENDMENTS.md`.

> **Draft warning.** The nine images under `figures/draft-2026-07/` were made with
> superseded `W1/D1/W2/W2*` conventions. They are retained for provenance and
> must not be cited as frozen results. The official four-edition figures under
> `figures/official/` use the frozen `E_m`, `E_s`, `e_m`, and `e_s` definitions.

## What the project measures

Cards differ in timing, duration, and consequences. Eye of Poirot converts
each player card into transparent **sanction-exposure minutes** and publishes
two related families:

- **Match exposure `E_m`**: actual in-play minutes remaining after a card,
  with a prespecified dismissal multiplier. Knockout outputs include own-minus-
  opponent `ΔE_m` and foul-normalized `Δe_m`.
- **Suspension exposure `E_s`**: the knockout impact of the disciplinary
  record — caution risk intervals to the applicable reset, observed knockout
  suspension loss, and the recipient's opportunity weight `ω`. Group cards
  enter only as 2014–2022 carried-in cautions; the primary team rate `e_s`
  divides by the team's tournament fouls excluding the third-place match.

These are descriptive statistics. They do not identify intent or causation.
The frozen specification and non-claim boundary are in
[`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Frozen decisions

| Item | v0.2.1 decision |
|---|---|
| Editions | 2014, 2018, 2022 complete; 2026 through M100 |
| Match clock | `T_end − card minute`; stoppage and extra time included, shoot-outs excluded |
| Suspension scope | knockout impact only: group cards create no direct term; group-earned bans count only when served in a knockout match |
| Carried-in cautions | a 2014–2022 pending group caution prices as if shown at minute 0 of the first knockout match (180 at a round of 16) |
| 2026 cautions | reset after the group stage and after the quarter-finals; nothing carries into the knockout stage |
| Stop rule | a suspension-causing card stops the earlier caution's interval at minute granularity |
| Exact-clock cautions | stoppage/extra-time receipt and all semi-final/final cautions price `T_end − t` |
| Third-place match | excluded at the event level (no exposure terms, no denominator fouls); suspension service and availability there still count |
| Elimination | does not truncate the potential accumulation horizon |
| Primary parameters | dismissal `ρ = 2`; served suspension `μ = 1.25` |
| Opportunity weight | player minutes ÷ (team nominal minutes − documented unavailable intervals) |
| Primary denominator | all team fouls across group and knockout matches, excluding the third-place match |
| Depth check | prespecified per-edition Kendall `τ_b` of matches played vs `e_s`; never pooled across editions |
| Personnel | player cards only in metrics; team-official cards audited separately |

### Frozen expanded-cohort amendment

The amendment approved on 2026-07-14 adds full-field `E_s^grp`/`E_s^all`,
the labeled `lambda=0.5` secondary, reason-stripped robustness variants, the
MD2-plus-knockout secondary, and descriptive cumulative-foul tables. These
are additive outputs and do not replace the registered v0.2.1 primary tables.
All current 2026 amendment rows are labeled `provisional_M100`; M101–M104 are
not ingested, and the confirmatory rerun remains scheduled after M104. See
[`docs/AMENDMENTS.md`](docs/AMENDMENTS.md) and
[`docs/RESULTS.md`](docs/RESULTS.md).

## Data and reproducibility

The repository separates redistributable derived facts from rights-sensitive
raw snapshots.

```text
data/raw/       private and gitignored source snapshots
data/derived/   public normalized and derived CSV tables
pipeline/       fetch, build, validation, figure, and one-command orchestration
tests/          hand-checked fixtures and property tests
figures/        official outputs plus a clearly marked draft archive
```

The reproducible workflow has two paths:

```bash
# Public path: rebuild results and figures from committed derived tables
python3 -m pipeline.build_all --from-derived

# Raw-archive owner path: rebuild every derived table, result, and figure
python3 -m pipeline.build_all --from-raw
```

Both paths are implemented with the Python standard library. The public path
makes no network request and has been checked without `data/raw/`. Results are
reported in [`docs/RESULTS.md`](docs/RESULTS.md); build status and documented
disciplinary-decision cases are tracked in
[`docs/BUILD_STATUS.md`](docs/BUILD_STATUS.md).

Source hierarchy, redistribution boundaries, table inventory, and the
snapshot manifest are documented in [`data/README.md`](data/README.md).

### StatsBomb attribution and rights boundary

[![StatsBomb logo](https://raw.githubusercontent.com/statsbomb/open-data/master/img/SB%20-%20Icon%20Lockup%20-%20Colour%20positive.png)](https://statsbomb.com)

**Data source: StatsBomb.** The `sb_foul_linked` field, the four-row
reconciliation table, the 2018/2022 event-segment and public cumulative-foul
counts, and the related report sections are analyses derived from StatsBomb
Open Data. They remain subject to the
[StatsBomb Public Data User Agreement](https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf),
including its non-commercial restriction, and are excluded from this
repository's CC BY 4.0 grant. Event-level StatsBomb records are retained only
in the gitignored private raw archive and are not redistributed. The
StatsBomb logo and trademarks are also excluded from the repository licenses.
Before a public release, the archive owner must manually confirm that the
StatsBomb user has submitted the name-and-email registration requested at the
[StatsBomb Resource Centre](https://statsbomb.com/resource-centre/); the build
cannot verify that external registration.

## Source hierarchy

1. FIFA calendar, timeline/event, team-statistics, match-centre, and official
   match-report material;
2. federation or club statements for player availability or disciplinary context;
3. established match reporting for injury/illness and card-reason evidence;
4. FotMob, Transfermarkt, and Wikipedia only as documented fallbacks or
   cross-checks.

The public card-reason ledger classifies all 908 in-play player cards at the
M1–M100 cutoff. Its evidence report also retains the full 2018/2022 StatsBomb
`Bad Behaviour` reconciliation as aggregate counts. The public four-row
reconciliation table reports edition × event-type totals; the event-level
StatsBomb records outside the in-play FIFA census remain in the private raw
archive.
Public cumulative-foul CSVs contain only project identifiers and derived
counts; StatsBomb match/event identifiers, sequence indices, order keys, and
linked-event references remain in the gitignored private sidecar. Public
StatsBomb links point only to the dataset landing page.

The 2014 end clock is a declared exception: archived FIFA event feeds lack
usable final-period markers, so archived FotMob period timestamps reconstruct
`T_end`; penalty shoot-outs are excluded. Complete 2014 team-foul totals come
from the archived HuffPost World Cup statistics pages, which credit Opta;
the 19 available FotMob matches are retained as an independent cross-check.

## Registration and release status

- Methodology v0.2.1, normalized tables, tests, figures, and the dated SHA-256
  manifest: prepared and checked locally.
- Public OSF Open-Ended Registration (methodology v0.2.1, frozen and
  registered 2026-07-13 before 2026 M101):
  [https://doi.org/10.17605/OSF.IO/3GESM](https://doi.org/10.17605/OSF.IO/3GESM).
- Reproducibility-snapshot registration (component of the same registration
  tree, public; public-tree zip at commit 88fd47c):
  [https://doi.org/10.17605/OSF.IO/TW48K](https://doi.org/10.17605/OSF.IO/TW48K).
  The originally planned four-year embargo was not applied: the snapshot
  contains only the already-public repository tree, so there was nothing left
  to embargo once the repository went public.
- Public GitHub repository and reproducibility workflow:
  [AuroreYoshizawa/EyeOfPoirot](https://github.com/AuroreYoshizawa/EyeOfPoirot).

The exact project name, upload split, and manual steps are recorded in
[`docs/REGISTRATION.md`](docs/REGISTRATION.md). Registration actions that
require account confirmation are intentionally not automated.

## Prior drafts and amendments

The analyst saw exploratory Argentina-focused outputs before freezing v0.2.
That prior knowledge and the two known draft rule errors are disclosed in the
methodology, as is the same-day v0.2.1 pre-registration revision. Any
post-freeze change is append-only in
[`docs/AMENDMENTS.md`](docs/AMENDMENTS.md).

## Collaboration and issue reporting

Independent re-collection, football-domain review, and adversarial checking
are welcome. Please open a GitHub issue with the edition, match number, source
URL, and the affected derived row. Do not upload copyrighted raw reports or
private correspondence to an issue.

## License and citation

Code will be released under MIT (`LICENSE-CODE`). Original documentation,
project-authored derived tables, and original figures are CC BY 4.0
(`LICENSE`). StatsBomb-derived fields, aggregates, and report sections remain
subject to the StatsBomb Public Data User Agreement and are excluded from the
CC BY grant. Raw FIFA/FotMob pages, event-level StatsBomb records, reports,
third-party logos, and trademarks are not distributed or relicensed by this
repository.
Citation metadata: [`CITATION.cff`](CITATION.cff).
