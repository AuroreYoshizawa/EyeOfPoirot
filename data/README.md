# Data provenance, rights, and rebuild paths

The repository publishes normalized observations and analytical outputs under
`data/derived/`. Rights-sensitive source snapshots stay under the gitignored
`data/raw/` archive and are not distributed or relicensed.

## Frozen coverage

| Edition | Included matches | Primary source snapshot |
|---|---:|---|
| 2014 | 64/64 | FIFA calendar/cards/live data; HuffPost/Opta team fouls; FotMob period clocks and foul cross-check |
| 2018 | 64/64 | FIFA calendar, timeline, statistics, and reports |
| 2022 | 64/64 | FIFA calendar, timeline, statistics, and reports |
| 2026 | M1–M100 | FIFA calendar, timeline, statistics, and reports |

M101–M104 were unplayed at the 2026-07-13 freeze and are excluded.

## Source hierarchy

1. FIFA calendar, timeline/event, team-statistics, match-centre, and official
   match-report material;
2. federation or club statements for availability evidence;
3. established match reporting for injury or illness evidence;
4. FotMob, Transfermarkt, and Wikipedia only as declared fallbacks or
   cross-checks.

The 2014 clock is the documented exception: the archived FIFA event feed does
not expose reliable final-period timestamps, so archived FotMob
`header.status.halfs` fields reconstruct actual end of play. Penalty shoot-out
events are excluded. See `docs/METHODOLOGY.md` for the rule and audit boundary.

Complete 2014 team-foul totals come from 64 archived HuffPost World Cup match
statistics pages that identify Opta as the data provider. FotMob exposes foul
totals for 19 of those matches: 13 match-level pairs agree exactly, and six
differ by one foul for one team. Both layers remain in the private audit
archive; the complete HuffPost/Opta layer is the published denominator.

## Published table families

| Family | Grain | Representative fields |
|---|---|---|
| source/cards | card event | edition, match, team, player, card type, event scope, card minute, `T_end` |
| source/fouls_team_match | team × match | edition, match, team, stage, fouls |
| source/player_match | player × match | lineup status, nominal minutes, played minutes, source URL |
| source/sanction_decisions | disciplinary decision | carry-in, extension, deferral, service matches, source URL |
| stages/s1-card-ledger | player card | reset window, base/effective horizon, parameterized `exp_match_min` |
| stages/s4-suspensions | sanction service match | trigger, service match, served/pending/deferred/conflict status, decision source |
| stages/s5-availability | player × match | status, unioned `S`/`I` minutes, opportunity denominator |
| stages/s5-player-opportunity | player × edition | played minutes, denominator intervals, `omega` |
| results/match-exposure | team × match | `exp_match_min`, `d_exp_match`, foul-normalized differences |
| results/player-suspension-exposure | player × edition | `exp_susp_min`, served terms, `omega` |
| results/team-suspension-exposure | team × edition | exposure totals and both foul denominators |
| results/suspension-sensitivity | edition × parameters | complete rho × mu × denominator pooled grid |
| results/end-clock-sensitivity | edition or team × match | source-end versus `T_end - 1` boundary variants |
| results/results_YYYY | ranked team × edition | filterable primary knockout-team rankings |

`data/derived/DICTIONARY.md` is the machine-output schema reference. The
dated manifest records SHA-256 hashes for the local raw snapshot and the
published derived files.

Root-level `cards_*.csv`, `cards_all.csv`, `match_exposure_*.csv`, and
`build_report.md` are retained pre-freeze audit artefacts. They use retired
`W1/D1/W2` fields and are not v0.2 outputs; authoritative tables are under
`source/`, `stages/`, and `results/`.

## Rebuild paths

```bash
# Public path: no private raw archive required.
python3 -m pipeline.build_all --from-derived

# Archive-owner path: re-extract source observations, then rebuild outputs.
python3 -m pipeline.build_all --from-raw
```

The public path starts from committed, normalized source observations. The raw
path starts from locally archived source responses and PDFs; it fails with a
clear message when required private snapshots are absent. Neither path makes
network requests. Fetch scripts are separate and must be invoked explicitly.

## Rights boundary

- Project-authored documentation, original figures, and project-authored
  derived tables are offered under CC BY 4.0 (`LICENSE`).
- Pipeline and test code are offered under MIT (`LICENSE-CODE`).
- FIFA, FotMob, media, federation, and club source pages, API responses,
  reports, logos, and other third-party materials retain their original
  rights. Their inclusion in a local audit archive does not place them under
  either repository license.
- Source URLs and compact provenance fields are published so another analyst
  can recollect or audit observations without redistributing source files.

If a derived row cannot be traced to a source URL or archived source key, the
build treats it as a validation failure rather than silently imputing it.

## Known cross-validation decisions

- The pre-freeze 2018, 2022, and 2026 workbooks are used only as extraction
  aids for raw fields and source links. Their `W1/D1/W2/W2*` formulas are not
  v0.2 results.
- 2018 and 2022 draft suspension-exposure formulas incorrectly carried the
  caution horizon into the semi-finals. v0.2 resets after the quarter-finals.
- FIFA timeline foul-event counts and published team-stat totals are retained
  as separate audit layers; they are not assumed to be interchangeable.
- FIFA live match-centre payloads independently reconstruct participation for
  every carded player. The 2018/2022/2026 overlap with the pre-freeze workbook
  minutes is exact after stoppage labels are converted to the nominal clock.
- Seven 2022 cards and one 2026 card occur during an interval, after play, or
  during a penalty shoot-out. They remain in the card census but do not enter
  match exposure.
- Every positive injury/illness interval must have a public evidence URL.
  Substitution alone is not evidence of injury.
- Five incorrect 2018 medical-ledger fixture numbers are corrected by an
  explicit audited map. The build rejects evidence joined to a match in which
  the player's team did not participate.
- Four matches—one per edition—are independently checked against ESPN or Opta
  in `data/sources/independent-match-checks.csv`. Differences in display
  convention remain labeled `AUDIT`.
