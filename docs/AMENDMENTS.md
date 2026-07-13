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
