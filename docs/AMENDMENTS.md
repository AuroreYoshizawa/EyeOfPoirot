# Methodology amendments and data errata

The v0.2 methodology was frozen on 2026-07-13 before 2026 Match 101. New
entries are append-only.

## Method amendments

- **End-clock boundary sensitivity (logged 2026-07-13).** The implementation
  checklist required an inclusive-versus-exclusive clock check that the first
  freeze commit did not state explicitly. The added variant replaces
  `T_end` with `T_end - 1` only for match exposure and the dismissal component
  of suspension exposure. Its expected direction is weakly downward. The
  primary specification is unchanged.
- **v0.2.1 pre-registration revision (logged 2026-07-13, before 2026 M101 and
  before any registration was submitted).** Review against the analyst's
  original commissioned definitions found that v0.2 had formalized four rules
  differently from the commission; one agreed rule was missing. Five changes,
  enumerated with expected directions in `docs/METHODOLOGY.md` §6: (1)
  knockout-impact scope with 2014–2022 carried-in cautions replaces
  whole-tournament pricing (down for group-carded players); (2) the
  second-caution stop rule moves from fixture to minute granularity (down for
  stopped intervals); (3) stoppage/extra-time cautions price the exact-clock
  remainder (up; no zero floor); (4) semi-final and final cautions price the
  exact-clock remainder (slightly up); (5) the third-place match is excluded
  at the event level while service and availability there still count (small,
  both directions). The §5.1 per-edition depth check was prespecified in the
  same revision before any correlation had been computed. No confirmatory
  analysis was run under the v0.2 variants; the v0.2 rules remain in the git
  history for audit.
- **Prespecified defensive-outcome association check (logged 2026-07-14,
  before the 2026 M101 kick-off).** Motivated by post-hoc exploration
  conducted 2026-07-13/14 on the full frozen data (2014–2022 complete, 2026
  M1–M100); every value in the disclosure below is therefore exploratory,
  and this entry binds only data unobserved at logging time: 2026 M101–M104
  and any future backward edition extension.

  *Definitions.* Conceded rate: goals conceded in regulation and extra time
  (shoot-outs excluded) in the team's matches excluding the third-place
  match, divided by those matches. $X_s$ decomposes exactly into three
  components: **in-match** (caution remainders and dismissal exact-clock
  terms), **accumulation-window** (the $90N$/stop-rule blocks plus the whole
  carried-in caution interval), and **served** ($90\mu$ blocks). Team
  component exposure is $\sum_p \omega_p \cdot$ component; per-foul rates
  use the primary $F_i$.

  *Primary prespecified test.* Per edition, never pooled, knockout-team
  cohort: Kendall $\tau_b$ between accumulation-window exposure per foul
  and conceded rate; two-sided permutation $p$, 10,000 permutations, seed
  20260713. Expected direction: positive.

  *Secondary (labeled).* The same test for total $e_s$; depth-partial
  Spearman given matches played (third place excluded); leave-one-team-out
  influence; a pre-tournament Elo variant once that table is archived.

  *Disclosure of the exploration that produced this entry.* Total $e_s$ vs
  conceded rate: $\tau_b$ = +0.128 / +0.349 / +0.485 / +0.032 for
  2014/2018/2022/2026-M100 (only 2022 significant, permutation
  p = 0.009); depth-partial Spearman survived only in 2022 (+0.562,
  p = 0.029). Component split: the association concentrates in the
  accumulation-window component (+0.264 / +0.417 / +0.451 / +0.080; 2018
  p = 0.029, 2022 p = 0.017), with the in-match and served components flat.
  Robustness probes: leaving out Argentina strengthened 2022; removing all
  Argentina fixtures weakened it mainly by zeroing Australia's knockout
  record (a design artifact); an explored variant adding
  $0.5\,(T_{end}-t)$ to caution intervals was abandoned as collinear with
  $e_s$ (rank correlation ≥ 0.985) and is not adopted. Given the number of
  explored cuts, the 2014–2022 values must not be read as confirmatory;
  the confirmatory sample is the full-2026 rebuild after M104 (marginal
  novelty: four matches) and, chiefly, any 2010/2006 extension collected
  under per-edition source fallbacks to be amended before collection.

## Reporting amendments

- **Winner-perspective match figures (logged 2026-07-13).** The official
  knockout `ΔE_m` figures now orient every fixture to FIFA's recorded winner,
  including shoot-out winners, and sort from highest to lowest. The
  methodology-excluded third-place fixture is omitted. This is a presentation
  rule only: both team perspectives remain in the result table and the
  antisymmetry invariant is unchanged.
- **Foul-normalized winner-perspective figures (logged 2026-07-13).** Added one
  `ΔE_m′` figure per edition, defined as winner `E_m / match fouls` minus
  opponent `E_m / match fouls`, sorted from highest to lowest. This is a
  reporting alias for the existing `Δe_m` result and does not divide an already
  normalized value again.

## Data errata

- **2018 medical-ledger fixture corrections (logged 2026-07-13).** Five rows
  in the pre-freeze ledger used unrelated adjacent fixture numbers: James
  Rodríguez M15→M16 and M46→M48, Mats Hummels M29→M27, and Taisir Al-Jassim
  M19→M18 and M33→M34. The pipeline now applies an explicit correction map and
  rejects any evidence row whose team did not play the joined match. Better
  ESPN, FIFA, Reuters/SBS, L'Équipe, and Sports Illustrated evidence replaces
  the prior Wikipedia links. Correct placement changes the primary 2018
  pooled `e_s` from 15.169217 to 15.319863.
- **Missing documented unavailability (logged 2026-07-13).** Added sourced
  full-match injury intervals for Mattia De Sciglio (2014 M8) and Mark
  Milligan (2014 M20). The current player-match availability table has no
  unexplained absence; the methodology still permits that status when future
  evidence is genuinely inconclusive.

## Source-audit notes

- **Documented disciplinary decisions (logged 2026-07-13).** Themba Zwane's
  M1 dismissal produced three sourced service matches (M25, M54, M73), all
  confirmed absent in the official lineups. FIFA formally deferred Folarin
  Balogun's M81 automatic ban, explaining his M94 eligibility; the row is
  `deferred`, not a lineup conflict. Fredy Guarín's qualifier ban carried into
  2014 M5 and is confirmed by the opening-match lineup. Jarell Quansah's
  two-match decision is retained; M99 is served inside the cutoff and the
  remaining term is after M100.
- **Independent match-page checks (logged 2026-07-13).** Four matches—2014
  M1, 2018 M16, 2022 M57, and 2026 M1—were checked against ESPN or Opta. Five
  checks agree. Two source-display differences remain `AUDIT`: Carlos
  Sánchez's red is minute 4 in FIFA and minute 3 at ESPN; ESPN collapses
  Denzel Dumfries's post-extra-time dismissal to minute 120 while FIFA period
  codes distinguish shoot-out and post-play administration.
- **2014 foul-layer cross-check (logged 2026-07-13).** The complete 64-match
  HuffPost/Opta team-stat layer is primary. Of 19 matches with an independent
  FotMob foul total, 13 agree exactly and six differ by one foul for one team.
  The discrepancy is published as audit metadata and is not silently merged.
