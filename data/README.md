# Data provenance, rights, and rebuild paths

The repository publishes normalized observations and analytical outputs under
`data/derived/`. Rights-sensitive source snapshots stay under the gitignored
`data/raw/` archive and are not distributed or relicensed.

## Frozen coverage

| Edition | Included matches | Primary source snapshot |
|---|---:|---|
| 2014 | 64/64 | FIFA calendar/cards/reports; FotMob period clocks and match details |
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

## Published table families

| Family | Grain | Representative fields |
|---|---|---|
| cards | card event | edition, match, team, player, card type, card minute, `T_end` |
| fouls_team_match | team × match | edition, match, team, stage, fouls |
| player_minutes | player × match | status, nominal minutes, played minutes, source URL |
| suspensions | suspension interval | trigger, served match, nominal loss, source URL |
| availability | player × unavailable interval | reason, interval, evidence tier, source URL |
| omega | player × edition | played minutes, denominator intervals, `omega` |
| exposure_match | card event | `exp_match_min` and parameter setting |
| exposure_susp | player/card contribution | `exp_susp_min`, horizon, `omega` |
| results | team or match perspective | exposure totals, foul-normalized rates, differences |

`data/derived/DICTIONARY.md` is the machine-output schema reference. The
dated manifest records SHA-256 hashes for the local raw snapshot and the
published derived files.

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
- Every positive injury/illness interval must have a public evidence URL.
  Substitution alone is not evidence of injury.
