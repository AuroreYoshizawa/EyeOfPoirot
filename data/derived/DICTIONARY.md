# Derived-data dictionary — methodology v0.2.1

All CSV files are UTF-8 with a header row. Empty cells mean not applicable or
not observed; they are not implicit zeros. IDs are strings even when they
contain digits. Minutes may be fractional where a source exposes sub-minute
period timing.

## `source/`

- `matches.csv` — one row per included match (292 rows). `nominal_minutes` is
  90 or 120; `t_end_min` includes stoppage and extra time but excludes the
  shoot-out. `t_end_source` declares the clock source. `winner_team_id` and
  `winner_team` retain FIFA's recorded winner, including shoot-out winners.
- `cards.csv` — full player and team-official card census (937 rows).
  `recipient_type` selects player versus official. `event_scope` is
  `in_play`, `interval`, `post_play`, or `penalty_shootout`.
- `card_reasons.csv` — one evidence-audited reason for every in-play player
  card (908 rows). `reason_class` is `foul_play`, `dissent`, `time_wasting`,
  `other_nonfoul`, or `unknown`. `sb_foul_linked` records the independent
  StatsBomb open-data linkage for 2018/2022 (`yes`, `no`, or `unmatched`) and
  is `not_available` for 2014/2026. Linkage conflicts remain labeled `AUDIT`
  in `note`; they never silently replace the written-source classification.
- `card_reason_sb_reconciliation.csv` — four aggregate edition × event-type
  rows reconciling StatsBomb `Foul Committed` and `Bad Behaviour` card counts
  with the in-play FIFA player-card census. It publishes in-census,
  outside-census, and all-card counts plus an aggregate scope summary. The 12
  underlying outside- or unalignable-census event records remain only in the
  gitignored private raw archive; no StatsBomb event identifier is
  redistributed.
- `fouls_team_match.csv` — two team perspectives per match (584 rows).
  `team_match_number` is chronological within the team's tournament.
- `player_match.csv` — every tournament match for every carded player
  (3,306 rows). `played_minutes` uses the nominal clock.
- `availability_evidence.csv` — 56 documented positive injury/illness intervals.
  Every row has an evidence tier, paraphrased note, and public `source_url`.
- `sanction_decisions.csv` — four sourced decisions that carry in, extend,
  or defer an automatic suspension. Service matches are explicit.
- `foul_event_segments.csv` — eight public team-match segment aggregates for
  every complete event feed (2018/2022 StatsBomb, 2026 FIFA M1–M100). It has
  no provider-native match/event ID or order key. `feed_status` discloses the
  known 2026 timeline under-count.
- `card_event_order.csv` — one safe order-reconciliation row per in-play
  player card. Counts are blank for `unmatched` and `source_unavailable`
  rows. Reviewed FIFA/StatsBomb player-name equivalences are explicit; there
  is no minute-only cross-source fallback. StatsBomb `source_url` is the
  dataset-level open-data link only.
- `team_match_card_order.csv` — exactly one row per team side in the 292-match
  census, including zero-card sides. `fouls_before_first_card` is blank, not
  zero, for no-card, unmatched-first-card, and source-unavailable rows.
  Same-clock first-card ties use provider sequence order internally without
  publishing that order key.
- `team_outcomes.csv` — FIFA score observations for both team perspectives;
  shoot-out goals are excluded. This is the input for the disclosed
  per-edition conceded-rate robustness recomputation.
- `source_audit.csv` — input cardinalities and independent source-layer
  comparisons. `AUDIT` records a disclosed difference, not a failed build.

## `stages/`

- `s1-card-ledger.csv` — player cards only. `base_horizon` is the reset-only
  fixture horizon; `effective_horizon` applies the fixture-level stop rule and
  is retained for audit. The minute-granular v0.2.1 stop rule is exposed in
  `stop_scope` (`same_match` or `cross_match`), `stop_card_id`,
  `stop_match_number`, `stop_t_min`, and `stop_gap_fixtures` (fixtures
  strictly between the caution and its stopper).
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
- `s9-stripped-card-ledger.csv` — a full chronological ledger rebuild after
  removing only `dissent` and `time_wasting`. Pairing and stop fields are
  recomputed; this is not a row deletion from `s1-card-ledger.csv`.
  `edition_status` labels 2026 rows `provisional_M100`.
- `s10-stripped-suspensions.csv` — automatic/sourced service terms rebuilt
  from the stripped sequence. In-edition decisions whose trigger card was
  removed are absent; pre-tournament carry-ins remain. Its 2026 rows carry
  the same provisional label.
- `s11-expanded-player-suspension-exposure.csv` — player-level full/stripped
  decomposition of `E_s^grp`, frozen `E_s`, and `E_s^all`. `omega` is always
  copied from the observed full ledger. `exact_clock_q_min` and the
  `lambda=0.5` prime fields exist only for `ledger=full`.

## `results/`

- `match-exposure.csv` — primary rho=2 result for both team perspectives of
  every match. Canonical fields are `exp_match_min`, `exp_match_per_foul`,
  `d_exp_match`, and `d_exp_match_per_foul`. The new winner-perspective figure
  labels `d_exp_match_per_foul` as `ΔE_m′`; it is the same quantity as
  methodology `Δe_m`, not a second division by fouls.
- `match-exposure-sensitivity.csv` — the same rows for rho 1, 1.5, and 2.
- `match-end-clock-sensitivity.csv` — source-end and `T_end - 1` primary-rho
  rows for both team perspectives.
- `player-suspension-exposure.csv` — primary rho=2, mu=1.25 player result.
  `ordinary_caution_min` covers in-scope knockout cautions;
  `carried_in_caution_min` is the 2014–2022 carried-in pseudo-caution term;
  `unweighted_exp_susp_min` is $X_s$; `exp_susp_min` is `omega * X_s`. A
  player whose discipline was entirely group-stage or third-place scoped has
  an all-zero row.
- `team-suspension-exposure.csv` — primary team totals with all-tournament and
  knockout-only foul denominators, both excluding the third-place match.
  `primary_cohort=yes` identifies teams that entered the knockout stage.
  `exposed_players` and `mean_omega` cover players with positive sanction
  minutes at the row's parameters; `mean_omega` is blank when no player has a
  positive term.
- `depth-check.csv` — the §5.1 prespecified per-edition depth check: Kendall
  `tau_b` between matches played (excluding the third-place match) and the
  primary `e_s`, with a seeded within-edition permutation `p`. Editions are
  never pooled; 2026 is `provisional_M100` until M104 is ingested.
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
- `expanded-suspension-exposure.csv` — additive 32/32/32/48 team table for
  `E_s^grp`, frozen `E_s`, `E_s^all`, and the labeled `E_s'` secondary, plus
  the authorized stripped variants. Ranks are within edition and ledger.
  Every 2026 row is `provisional_M100`.
- `md2-suspension-exposure.csv` — second-knockout-round cohort under
  `lambda_md2` 1, 1.5, and 2. Scope is the second scheduled group match plus
  knockout matches excluding the third-place match; the foul denominator is
  the published match-stat total over that same scope.
- `card-timing-displacement.csv` — full/stripped base-null timing results for
  knockout and expanded scopes. It reports signed mean-segment displacement,
  ordered W1, seeded Monte Carlo p-values, and separately scoped BH q-values.
  `<3` cards are labeled non-evidentiary; zero-card teams are excluded from
  `bh_m`; 2014 is `source_unavailable` and creates no family.
- `stripped-disclosed-correlations.csv` — per-edition, never-pooled stripped
  robustness for depth, total `e_s` versus conceded rate, and the
  accumulation-window component versus conceded rate (`B=10,000`, seed
  20260713).
- `cumulative-fouls-before-card.csv` and
  `cumulative-fouls-before-first-card.csv` — public descriptive order counts.
  They contain project identifiers and derived conclusions only; provider
  event/match identifiers, sequence indices, event-order keys, and linked
  references stay in the gitignored private sidecar.
- `expanded-audit.csv` — amendment invariants and independent cross-check
  reconciliation. Anchor disagreements are `AUDIT`, never force-fit values;
  edition-specific audit rows also carry `edition_status`.

## Legacy pre-freeze files

The root-level `cards_*.csv`, `cards_all.csv`, `match_exposure_*.csv`, and
`build_report.md` preserve the July 2026 extraction audit. They use retired
`W1/D1/W2` terminology and are not methodology-v0.2 result tables. Use the
`source/`, `stages/`, and `results/` directories for current outputs.
