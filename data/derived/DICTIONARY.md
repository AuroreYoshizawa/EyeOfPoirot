# Derived-data dictionary — methodology v0.2

All CSV files are UTF-8 with a header row. Empty cells mean not applicable or
not observed; they are not implicit zeros. IDs are strings even when they
contain digits. Minutes may be fractional where a source exposes sub-minute
period timing.

## `source/`

- `matches.csv` — one row per included match (292 rows). `nominal_minutes` is
  90 or 120; `t_end_min` includes stoppage and extra time but excludes the
  shoot-out. `t_end_source` declares the clock source.
- `cards.csv` — full player and team-official card census (937 rows).
  `recipient_type` selects player versus official. `event_scope` is
  `in_play`, `interval`, `post_play`, or `penalty_shootout`.
- `fouls_team_match.csv` — two team perspectives per match (584 rows).
  `team_match_number` is chronological within the team's tournament.
- `player_match.csv` — every tournament match for every carded player
  (3,306 rows). `played_minutes` uses the nominal clock.
- `availability_evidence.csv` — 56 documented positive injury/illness intervals.
  Every row has an evidence tier, paraphrased note, and public `source_url`.
- `sanction_decisions.csv` — four sourced decisions that carry in, extend,
  or defer an automatic suspension. Service matches are explicit.
- `source_audit.csv` — input cardinalities and independent source-layer
  comparisons. `AUDIT` records a disclosed difference, not a failed build.

## `stages/`

- `s1-card-ledger.csv` — player cards only. `base_horizon` is the reset-only
  fixture horizon; `effective_horizon` applies the second-caution stop rule.
  `accumulation_role` and `paired_card_id` expose every pairing decision.
  The three `exp_match_min_rho_*` columns are the card-level match exposure.
- `s2-team-match-fouls.csv` and `s3-player-match-minutes.csv` — validated
  denominator and participation layers copied into the deterministic chain.
- `s4-suspensions.csv` — one row per service match or pending trigger.
  `service_status` is `served`, `pending`, `deferred`, or `conflict`.
  Decision provenance and lineup verification remain on the same row. Only
  `served` rows contribute the 90 × mu term and an `S` interval.
- `s5-availability.csv` — player × team-match coding. `S` and `I` intervals
  are unioned in `union_unavailable_minutes`; overlaps are never double
  subtracted.
- `s5-player-opportunity.csv` — player × edition components of
  `omega = played_minutes / opportunity_denominator_minutes`.

## `results/`

- `match-exposure.csv` — primary rho=2 result for both team perspectives of
  every match. Canonical fields are `exp_match_min`, `exp_match_per_foul`,
  `d_exp_match`, and `d_exp_match_per_foul`.
- `match-exposure-sensitivity.csv` — the same rows for rho 1, 1.5, and 2.
- `match-end-clock-sensitivity.csv` — source-end and `T_end - 1` primary-rho
  rows for both team perspectives.
- `player-suspension-exposure.csv` — primary rho=2, mu=1.25 player result.
  `unweighted_exp_susp_min` is $X_s$; `exp_susp_min` is `omega * X_s`.
- `team-suspension-exposure.csv` — primary team totals with all-tournament and
  knockout-only foul denominators. `primary_cohort=yes` identifies teams that
  entered the knockout stage.
- `suspension-sensitivity.csv` — 72 edition × rho × mu × denominator rows.
  `pooled_exp_susp_per_foul` is a ratio of sums, not a mean of team ratios.
- `suspension-end-clock-sensitivity.csv` — primary pooled values under the
  source end clock and `T_end - 1`, with both foul denominators.
- `results_2014.csv`, `results_2018.csv`, `results_2022.csv`, and
  `results_2026.csv` — filterable primary knockout-team rankings.
- `edition-summary.csv` — compact primary-setting inventory used in the
  results document.
- `build-audit.csv` — frozen invariants. `PASS` is required; `AUDIT` preserves
  reviewed source differences without turning them into inferred facts.

## Legacy pre-freeze files

The root-level `cards_*.csv`, `cards_all.csv`, `match_exposure_*.csv`, and
`build_report.md` preserve the July 2026 extraction audit. They use retired
`W1/D1/W2` terminology and are not methodology-v0.2 result tables. Use the
`source/`, `stages/`, and `results/` directories for current outputs.
