# Proposed amendment — expanded-cohort sanction exposure

**Status: PROPOSED, NOT FROZEN.** This file is a decision-ready draft for
analyst and Claude review. It authorizes no computation. Once approved, the
wording must be appended to `docs/AMENDMENTS.md` before any quantity below is
produced. The 2026 variants remain blocked until M101–M104 are ingested after
M104.

## Reason and claim boundary

The existing knockout-only suspension cohort selects on tournament survival.
The expanded specification describes group-stage burden for the full field and
then combines it with the frozen v0.2.1 knockout-impact quantity. It does not
replace the registered primary quantities and does not identify referee intent
or causal effects. Editions are always computed separately.

Expected directions relative to the frozen knockout-only output are stated
below. Team rankings have no prespecified direction. No new correlation is
authorized by this amendment.

## 1. Group-stage suspension exposure

For team `i`, the group horizon ends at the final whistle of that team's last
scheduled group match. It is not extended into the knockout stage. For an
in-play group-stage caution `c`, `L_grp(c)` uses the v0.2.1 rules in §3.3:

- the default in-match remainder is nominal; a caution received in stoppage
  time uses `max(0, T_end,m(c) - t_c)`. Because group matches have no extra
  time, the v0.2.1 §3.3 nominal value here is `max(0, 90 - t_c)`;
- the risk interval stops at the earlier of the next suspension-causing card
  (the same player's cumulative second caution or any dismissal) or the group
  horizon, with the same minute-granular same-match and cross-match stop
  rules;
- future fixture blocks count only scheduled group matches strictly after the
  card. A pending 2014/2018/2022 caution is capped at group end; the existing
  knockout carried-in proxy remains exclusively in frozen `E_s`. The 2026
  group reset remains unchanged.

Let `r_grp(c)` be the applicable nominal or exact-clock receipt-match
remainder above. For every later-match stop, including a caution whose
receipt-match remainder is exact-clock,

```text
L_grp(c) = r_grp(c) + 90 * G + min(t_2, 90)
```

where `G` counts scheduled group fixtures strictly between the receipt and
stopping matches and `t_2` is the stopping card's minute. The group horizon
still caps this value.

Let `C_p^{Y,grp}` be ordinary group cautions, `C_p^{D,grp}` be group
dismissals (`Y2` or `R`), and `B_p^{grp}` count all suspension matches
actually served in group matches. `B_p^{grp}` includes automatic and sourced
decisions, including a carry-in suspension triggered before the tournament.
Then

```text
X_s^grp(p; rho, mu)
  = sum_{c in C_p^{Y,grp}} L_grp(c)
  + sum_{c in C_p^{D,grp}} rho * max(0, T_end,m(c) - t_c)
  + 90 * mu * B_p^grp

E_s^grp(i; rho, mu) = sum_{p in i} omega_p * X_s^grp(p; rho, mu)
e_s^grp(i; rho, mu) = E_s^grp(i; rho, mu) / F_i
```

`omega_p`, `rho`, `mu`, the observed-service requirement, sourced decision
overrides, and `F_i` are exactly those of v0.2.1. A ban earned in a group match
but served in a knockout match contributes to frozen `E_s`, not `E_s^grp`.
A ban served in a group match contributes only to `E_s^grp`. This partitions
served matches by where the loss occurred and prevents double counting.

The widened quantity is

```text
X_s^all(p; rho, mu) = X_s^grp(p; rho, mu) + X_s(p; rho, mu)
E_s^all(i; rho, mu) = E_s^grp(i; rho, mu) + E_s(i; rho, mu)
                     = sum_{p in i} omega_p * X_s^all(p; rho, mu)
e_s^all(i; rho, mu) = E_s^all(i; rho, mu) / F_i
```

`X_s(p; rho, mu)` is the frozen v0.2.1 knockout quantity.

The cohort is every team in the edition: 32/32/32/48. Group-eliminated teams
have `E_s = 0` but may have positive `E_s^grp`. `E_s^all` is weakly greater
than frozen `E_s` by construction; no ranking direction is expected.

## 2. Additional exact-clock in-match caution variant

This labeled post-hoc secondary revives the `lambda=0.5` variant disclosed on
2026-07-14 as explored, abandoned, and not adopted because it was collinear.
It carries no confirmatory claim.
For every ordinary caution interval used in `E_s^all`, including a
2014/2018/2022 carried-in proxy, define `q(c)` as the exact-clock portion of
the receipt/proxy match for which the caution remains live. It runs from
`t_c` to the earlier of a same-match stopping card or `T_end,m(c)`; a later
match stop does not shorten this first-match portion.

For a 2014/2018/2022 carried-in proxy, the proxy match is the team's first
knockout fixture and `t_c = 0`. The same-match stop rule applies from kick-off;
if no same-match stopping card exists, `q(c) = T_end,m(c)`.

With fixed `lambda = 0.5`:

```text
X_s'(p; rho, mu) = X_s^all(p; rho, mu) + lambda * sum_c q(c)
E_s'(i; rho, mu) = sum_{p in i} omega_p * X_s'(p; rho, mu)
e_s'(i; rho, mu) = E_s'(i; rho, mu) / F_i
```

Dismissal and served-suspension components are unchanged. This secondary is
weakly greater than `E_s^all` by construction. It is reported for the widened
cohort only and is not promoted to a primary specification. The value 0.5 is
fixed to match the exact variant disclosed in `docs/AMENDMENTS.md` on
2026-07-14; no sensitivity range is applied.

## 3. Reason-stripped variants

The stripped ledger excludes only cards classified `dissent` or
`time_wasting` in `data/derived/source/card_reasons.csv`. `other_nonfoul` and
`unknown` remain included; StatsBomb linkage never changes the written-source
class.

After filtering, card pairings, minute-level stop points, carried-in status,
automatic suspension triggers, and exposure terms are rebuilt in
chronological order. A `carry_in_suspension` decision whose trigger occurred
outside the tournament (and therefore has no in-edition `trigger_card_id`) is
outside the reason filter and is retained. A sourced extended or deferred
decision with an in-edition `trigger_card_id` is retained only if that trigger
card remains. A served term that the stripped in-edition sequence no longer
triggers is omitted from the stripped numerator. The observed full-ledger
`omega_p` is held fixed because it is an opportunity weight; the analysis
does not invent counterfactual lineups or injury histories.

The following are recomputed per edition:

- `E_s`, `e_s`, `E_s^all`, and `e_s^all`;
- the prespecified knockout-only card-timing displacement check, retaining its
  original knockout-team and knockout-match event scope;
- a separate expanded-cohort robustness check using every team's in-play
  player cards and provider foul events across group and knockout matches
  within the edition cutoff, excluding the third-place match. Its segment
  definitions, Monte Carlo settings, and card weights remain those of the
  frozen check. This check is computed only for editions with a complete
  reproducible foul-time feed: currently 2018, 2022, and 2026. The 2014
  expanded timing check is reported as `source_unavailable`; it does not
  create or enter a BH family, and incomplete event feeds are not imputed.

For both the knockout-only and expanded scopes, a reason-stripped timing
output recomputes only the frozen base within-team exchangeability null for
`Δ` and `W₁`. The existing foul-linked and score-state benign-channel
variants retain the full ledger and original knockout-only scope; they are
not crossed with the stripped ledger or expanded cohort. Any such factorial
cross requires a later dated amendment.

BH is applied separately within each `edition × statistic × ledger (full or
stripped) × cohort/event-scope` family. A team with no retained card after
filtering has an undefined statistic and p-value and is excluded from that
family's `m`; a team with one or two retained cards is computed and included
in `m` but retains the frozen non-evidentiary label.

`E_s'` and `e_s'` are not recomputed under the stripped ledger: they are a
collinear secondary and would not provide an independent reason-stripped
check beyond `E_s^all` and `e_s^all`.

The card set is smaller. Exposure may move in either direction: removed terms
reduce it, while removing a stopping card can lengthen a retained caution
interval. Timing displacement also has no expected direction.

## 4. Matchday-2 plus knockout in-match quantity

The cohort contains teams that reached the second knockout round: the
quarter-final in 2014/2018/2022 and the round of 16 in 2026. The event scope
is each cohort team's second scheduled group match (the fixture on the
edition's matchday-2 schedule) plus all of its knockout matches, excluding the
third-place match. Only in-play player cards enter.

For `lambda_md2 = 1.5`, with sensitivity `{1, 1.5, 2}`:

```text
w(c; lambda_md2) = 1              for Y
                   lambda_md2     for Y2 or R

X_s^md2(p; lambda_md2)
  = sum_c w(c; lambda_md2) * max(0, T_end,m(c) - t_c)

E_s^md2(i; lambda_md2) = sum_{p in i} omega_p * X_s^md2(p; lambda_md2)
e_s^md2(i; lambda_md2) = E_s^md2(i; lambda_md2) / F_i^md2
```

`F_i^md2` is the team's published match-level foul total in the same match
scope, consistent with the v0.2.1 definition of `F_i`; it is not reconstructed
from event-level feeds. There are no future fixture blocks, carried-in proxies,
or served-suspension terms. This is a new secondary quantity, so it has no
directional comparison with frozen `e_s`.

## 5. Cumulative fouls before cards

The descriptive scope is every team side in every included match, including
the third-place match; this scope is separate from the exposure denominators.
Only in-play player cards and in-play foul events enter the counts. Interval,
post-play, and penalty-shootout events do not enter.

For each team-match with a complete event-level foul feed, order provider
events by period, event clock, and provider sequence index. The provider
sequence index is unique within each current match feed and therefore makes
the order total. A provider with duplicate triples is blocked until a dated
amendment freezes an additional tiebreaker. For every in-play player card
publish:

- `fouls_strictly_before_card`: team foul events earlier in that order;
- `foul_linked`: whether the provider links the card to a foul event;
- `fouls_through_card`: the strict count plus one only when `foul_linked=true`
  and the provider's linked foul event is not already in the strict count. A
  combined foul/card event is added once; a separately recorded linked foul
  that already precedes the card is not added again. With no provider-native
  linked foul on a successfully matched provider card event, this equals
  `fouls_strictly_before_card`;
- project card ID, reason class, provider label, official source URL, and an
  aggregate provenance/status label.

A public audit row is emitted for every in-play player card, but cumulative
values are computed only when the edition has a complete event feed and that
card is matched to a provider event. A provider-unmatched card (including the
20 reconciled as `unmatched` in 2018) has
`reconciliation_status=unmatched`; `fouls_strictly_before_card`,
`foul_linked`, and `fouls_through_card` are blank. A source-unavailable card
has `reconciliation_status=source_unavailable` and the same blank fields.
There is no minute-only cross-source fallback and no guessed within-minute
order.

A separate public team-match summary emits exactly one row for every team
side in the included match census, so zero-card matches are not lost. It
contains edition, project match/team identifiers, provider label,
`has_in_play_player_card`, `first_card_id`, `fouls_before_first_card`, status,
and a public source URL (dataset-level for StatsBomb). A no-card row has
`status=no_card`, blank
`first_card_id`, and blank `fouls_before_first_card`; an unmatched first card
has `status=first_card_unmatched` and a blank count; a source-unavailable row
has `status=source_unavailable` and a blank count. It contains no
provider-native match/event identifier or order key.

Provider-native match/event identifiers, sequence indices, event-order keys,
and linked-event references are retained only in the rights-restricted
private audit sidecar. They are never written to the public CSV or report.
In particular, the public 2018/2022 output contains project-authored per-card
counts and conclusions but no StatsBomb event row or event identifier; its
provider label, source link, and derived fields inherit the StatsBomb logo,
Public Data User Agreement, non-commercial, and no-CC-BY carve-out already
stated in the repository rights boundary. For StatsBomb rows the public
source link is the dataset-level `https://github.com/statsbomb/open-data`, not
a match-file URL whose path carries a provider match identifier.

`fouls_before_first_card` is the strict count for the first in-play player
card; it is blank, not zero, when a team has no card or when that first card
is unmatched/source-unavailable. Provider event counts are not forced to
equal the published team-stat foul denominator.

Complete feeds currently exist for 2018/2022 (StatsBomb) and 2026 (FIFA, with
the known under-count disclosed). The archived 2014 FIFA timelines contain
zero foul events, FotMob does not expose a complete foul-event sequence, and
StatsBomb open data does not publish the 2014 men's World Cup. Therefore 2014
is `source_unavailable` until a complete reproducible event source is added;
totals must not be used to impute event order.

## 6. Timing-check candidates drafted but not adopted

These candidates receive no output under this amendment. Each needs a later
dated amendment after feasibility and minimum-cell checks:

- **Gradient association:** §5 authorizes only the descriptive per-card and
  first-card cumulative-foul table. No correlation, regression, gradient
  coefficient, or baseline-relative rate is computed. A later dated
  amendment must freeze the estimand, analysis unit, variables, zero/no-card
  handling, edition-level aggregation, and multiplicity before any gradient
  magnitude is reported.
- **Referee-conditioned null:** draw comparison fouls only from matches
  handled by the same referee within the edition; the minimum referee match
  count and fallback rule must be frozen first.
- **Opponent mirror:** compare the two teams' card-minus-foul displacement
  within the same fixture, then aggregate team values within edition; a rule
  for one-sided zero-card fixtures must be frozen first.
- **Comparable challenge:** match foul events on provider-native challenge
  features before comparing card timing. StatsBomb supports this for
  2018/2022, but the current 2026 FIFA feed lacks equivalent severity and
  location fields, so it cannot be a common-edition confirmatory check.

## 7. Execution gate and reporting

No values are produced until this wording is approved and appended to
`docs/AMENDMENTS.md`. After M104, ingest M101–M104, rerun source invariants,
then compute exposure quantities for all four editions and event-timing
outputs for every source-eligible edition (currently 2018/2022/2026), all
deterministically. Outputs are new labeled expanded-cohort tables and
`RESULTS.md` sections; they do not replace the frozen primary tables. This
amendment introduces no new confirmatory test; the status of checks already
prespecified in `docs/AMENDMENTS.md` is unchanged. All expanded-cohort timing
results, including the comparison of Argentina with other teams, are labeled
robustness/sensitivity analyses because their cohort or event scope differs
from the registered check. The §5 cumulative-foul output remains descriptive;
the deferred gradient association in §6 is not an authorized output. Editions
are never pooled.
