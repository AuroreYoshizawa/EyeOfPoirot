# Methodology — sanction-exposure metrics (v0.2, frozen 2026-07-13)

This document is the frozen Phase A specification for *Eye of Poirot*. It is
written so that an independent analyst can rebuild every published quantity
from the event-level tables. Version 0.2 supersedes the draft `W1`, `D1`,
`W2`, `W2*`, `DDM`, `DDMF`, and `DF` nomenclature.

**Analysis scope.** FIFA World Cups 2014, 2018, and 2022 in full, plus only
completed 2026 matches M1–M100. The unplayed 2026 semi-finals, third-place
match, and final (M101–M104) are outside this frozen snapshot.

**Analysis cohort.** Match exposure is reported for every knockout match.
Suspension exposure is reported for every team that entered the knockout
stage; full-tournament tables may retain eliminated group-stage teams as an
auditable secondary cohort.

## 0. Design goal and claim boundary

A card is converted to **sanction exposure**, measured in minutes. The match
metric prices the remaining in-play time affected by a card. The suspension
metric also prices the time for which a caution remains capable of triggering
a future ban and the nominal time lost when a ban or dismissal is served.

These quantities are descriptive. They do not identify referee intent,
causation, or whether an individual foul deserved a card. Score state, foul
severity, field position, player behaviour, tactics, and referee assignment
remain uncontrolled unless a later registered amendment says otherwise.

## 1. Data model and sources

### 1.1 Match, event, and player tables

For edition $y$, team $i$, match $m$, player $p$, and card event
$c$:

| Symbol | Meaning |
|---|---|
| $t_c$ | cumulative event minute from the source label; `45'+2'` becomes 47 |
| $T_{end,m}$ | end of the final in-play period, including stoppage and extra time but excluding a penalty shoot-out |
| $F_{im}$ | fouls committed by team $i$ in match $m$ |
| $F_i$ | all-tournament fouls committed by team $i$ within the edition cutoff |
| $M_p$ | nominal minutes played by player $p$ |
| $T_i$ | sum of nominal match durations for team $i$: 90 or 120 per match |
| $S_p$ | nominal minutes unavailable through a dismissal or a suspension being served |
| $I_p$ | nominal minutes unavailable through a documented injury or illness |

The normalized data model consists of match, card, team-match foul, player-
match participation, suspension, availability, and evidence tables. Player
and team identifiers are retained whenever a source exposes them; normalized
names are display fields, not join keys where an identifier exists.

### 1.2 Source hierarchy

1. FIFA calendar, timeline/event, team-statistics, and match-centre data;
2. FIFA Full-Time Match Reports and tournament technical reports;
3. national federation or club statements;
4. established match reports (including BBC, ESPN, Reuters, and L'Équipe);
5. FotMob, Transfermarkt, or Wikipedia as a documented fallback or
   cross-check.

FIFA's archived 2014 timelines do not contain usable final-period markers.
For 2014 only, $T_{end,m}$ is reconstructed from archived FotMob
`matchDetails` period timestamps. In penalty-shoot-out matches, `gameEnded`
is not used because it includes the shoot-out; $T_{end,m}$ is 120 plus the
announced second-extra-time added time. If that announcement is absent, 120
is retained as an explicit lower bound rather than imputed.

Raw responses and PDFs are held in the private, gitignored archive. Public
derived tables carry source URLs, extraction notes, and the snapshot manifest
needed to recollect or audit them.

### 1.3 Event scope

Card type is one of ordinary yellow (`Y`), second caution in the same match
followed by dismissal (`Y2`), or direct red (`R`). Cards to coaches or other
team officials are retained in the event census but excluded from all player
metrics. A card shown during a penalty shoot-out is outside the in-play match
metric and is separately flagged.

### 1.4 Frozen rule and collection references

- [FIFA: 2026 double reset](https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/yellow-cards-reset-group-stage-quarter-final)
- [FIFA Council: 2026 regulations amendment](https://inside.fifa.com/organisation/fifa-council/news/council-update-regulations-world-cup-2026)
- [FIFA: Russia 2018 disciplinary reminder](https://inside.fifa.com/tournaments/mens/worldcup/2018russia/news/a-disciplinary-reminder-for-russia-2018)
- [FIFA: Qatar 2022 suspension explanation](https://www.fifa.com/en/articles/ten-queries-about-qatar-2022-world-cup)
- FIFA calendar and timeline endpoints are recorded per row in the raw
  manifest and public derived tables.
- FotMob 2014 fallback endpoint pattern:
  `https://www.fotmob.com/api/data/matchDetails?matchId=<match_id>`.

## 2. Match exposure $E_m$

### 2.1 Per-card exposure

For a player card shown during an in-play period:

$$
x_m(c;\rho)=\rho_c\max(0,T_{end,m(c)}-t_c),
\qquad
\rho_c=
\begin{cases}
1,&c=Y,\\
\rho,&c\in\{Y2,R\}.
\end{cases}
$$

The primary dismissal multiplier is $\rho=2$. Sensitivity values are
$\rho\in\{1,1.5,2\}$. A second-yellow event is represented once as `Y2`;
its earlier yellow remains an ordinary yellow event, so no card event is
silently discarded.

### 2.2 Team-match exposure and differentials

$$
E_m(i,m;\rho)=\sum_{c:\,i(c)=i,\,m(c)=m}x_m(c;\rho).
$$

For opponent $o$:

$$
\Delta E_m(i,m)=E_m(i,m)-E_m(o,m).
$$

Positive values mean that team $i$ carried more remaining-time card
exposure than its opponent. The two team perspectives for a match must be
exact opposites.

The foul-normalized quantities are

$$
e_m(i,m)=\frac{E_m(i,m)}{F_{im}},
\qquad
\Delta e_m(i,m)=e_m(i,m)-e_m(o,m).
$$

If either foul denominator is zero or missing, the corresponding normalized
quantity is missing and is never replaced by zero.

## 3. Suspension exposure $E_s$

### 3.1 Reset windows

A **reset window** is a sequence of matches over which single cautions carry
forward.

- 2014, 2018, and 2022: one window from the group stage through the
  quarter-finals; single cautions are cancelled after the quarter-finals.
- 2026: the group stage is one window and R32–R16–quarter-final is a second
  window; single cautions are cancelled after the group stage and again after
  the quarter-finals.

This 2026 treatment follows FIFA's 28 April 2026 rules amendment. A 2026 group
card therefore never carries into the knockout stage.

### 3.2 Nominal in-match remainder

For a caution, define

$$
r(c)=\max(0,B_c-t_c),
\qquad
B_c=\begin{cases}90,&\text{regulation period},\\120,&\text{extra time}.
\end{cases}
$$

Stoppage-time labels can therefore yield zero nominal remainder. They are not
shifted back by one minute.

### 3.3 Accumulation horizon

Let $N(c)$ be the number of the team's potential fixtures strictly after the
card and before the applicable reset, following the full bracket path. The
horizon is not shortened by the team's actual elimination.

If the player receives a second caution within the same window—either in a
later match or as a same-match `Y2`—the earlier caution's forward-risk interval
stops at that triggering event. A cross-match triggering caution has no
forward-risk blocks in that window; it instead creates a served suspension
term. Thus a risk interval is never counted beyond the event that realizes it.

Examples before any trigger:

| Edition/window | MD1 | MD2 | MD3 | R32 | R16 | QF | SF/final/third place |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2014/2018/2022 | 4 | 3 | 2 | — | 1 | 0 | 0 |
| 2026 group window | 2 | 1 | 0 | — | — | — | — |
| 2026 knockout window | — | — | — | 2 | 1 | 0 | 0 |

### 3.4 Player-level sanction minutes

For player $p$, let $C_p^Y$ be ordinary cautions, $C_p^D$ be dismissal
events (`Y2` or `R`), $D_p$ be the number of suspension matches actually
served after a dismissal within the observed edition, and $A_p$ be the
number of cross-match two-caution suspension matches actually served. Then

$$
X_s(p;\rho,\mu)=
\sum_{c\in C_p^Y}\left[r(c)+90N(c)\right]
+\sum_{c\in C_p^D}\rho\max(0,T_{end,m(c)}-t_c)
+90\mu\,(D_p+A_p).
$$

The primary served-suspension multiplier is $\mu=1.25$, with sensitivity
$\mu\in\{1,1.25,1.5\}$. Suspension terms are included only when the loss is
observed within the edition cutoff. Pending sanctions after the team's final
observed match are recorded but do not create fictitious served minutes.

### 3.5 Player opportunity weight $\omega$

$$
\omega_p=\frac{M_p}{T_i-\left|S_p\cup I_p\right|}.
$$

All components use nominal match minutes. `S` and `I` are interval sets and
are unioned before subtraction so overlapping reasons cannot be counted
twice. The denominator includes only matches in which the player belonged to
the tournament squad. Values must satisfy $0\le\omega_p\le1$; a violation
is a data error, not a value to clip silently.

`I_p` includes a documented in-match injury remainder and documented whole-
match absences. A substitution alone is not injury evidence. Every positive
injury interval must have a source URL and an evidence note. An unexplained
absence stays in the denominator. `S_p` includes the in-match remainder after
a dismissal and a suspension actually served.

### 3.6 Team exposure and normalization

$$
E_s(i;\rho,\mu)=\sum_{p\in i}\omega_p X_s(p;\rho,\mu),
\qquad
e_s(i;\rho,\mu)=\frac{E_s(i;\rho,\mu)}{F_i}.
$$

The primary denominator is all fouls committed by the team across group and
knockout matches within the edition cutoff. A prespecified sensitivity uses
knockout-stage fouls only. The edition pooled ratio is

$$
\bar e_s=\frac{\sum_i E_s(i)}{\sum_i F_i},
$$

not the unweighted mean of team ratios.

## 4. Availability, suspension, and evidence coding

Availability is coded at player × team-match grain with one of:
`played`, `bench`, `suspended`, `injured`, or `unexplained`. Only players with
positive unweighted sanction minutes $X_s>0$ require complete availability
coding for the primary build.

1. Participation and bench status come from official line-ups or the best
   archived match record.
2. Suspensions are derived from the chronological card ledger and checked
   against the next official line-up.
3. Injury/illness requires explicit evidence. A commentary phrase such as
   "replaced because of an injury" may establish the in-match remainder; a
   whole-match absence requires an independent team or media report.
4. If evidence cannot distinguish tactical non-selection from injury, status
   is `unexplained` and injury minutes are zero.

Each positive injury row contains `player`, `match`, `status`, interval,
`source_url`, evidence tier, and a short quotation-free paraphrase. The
evidence audit is published in `data/sources/injury-evidence.md`.

## 5. Prespecified sensitivity and quality control

The full grid is

$$
\rho\in\{1,1.5,2\},\qquad \mu\in\{1,1.25,1.5\},
$$

crossed with all-tournament versus knockout-only foul denominators. The
primary setting is $(\rho,\mu)=(2,1.25)$ with all-tournament fouls.

Required invariants:

- player-card census: 2014 = 194, 2018 = 224, 2022 = 228, 2026 M1–M100 = 270;
- $E_m\ge0$, $E_s\ge0$, and $0\le\omega\le1$;
- the second-caution stop rule never yields a horizon longer than the
  reset-only horizon;
- two match perspectives satisfy $\Delta E_m(i,m)=-\Delta E_m(o,m)$, and
  likewise for $\Delta e_m$ when defined;
- every positive injury interval has a non-empty source URL;
- 2026 inputs and outputs contain no event from M101–M104.

Hand-checked fixtures cover regulation stoppage, extra time, shoot-outs,
direct red, same-match second caution, cross-match accumulation, a reset, and
an injury-adjusted opportunity denominator in every edition where applicable.

## 6. Frozen disclosure and amendments

The analyst had seen earlier exploratory rankings and Argentina-focused
draft figures for 2018, 2022, and 2026 before freezing v0.2. Those drafts used
the superseded `W1/D1/W2/W2*` family and included two known rule errors: a
semi-final accumulation block after the quarter-final reset, and 2026 group
cautions carrying into the knockout stage. They are not confirmatory outputs.

This document, the input manifest, and the analysis cutoff were frozen on
2026-07-13 before 2026 M101. Any later change to a definition, inclusion rule,
source hierarchy, parameter, or test must be dated in `docs/AMENDMENTS.md`
with its reason and its expected directional effect. Corrections to raw
transcription that do not change a rule are logged as data errata. No silent
back-editing is permitted after registration.

## 7. Symbol and output migration

| Draft label | v0.2 label / disposition |
|---|---|
| `D1` | $E_m$, exact match exposure |
| `D1 difference` | $\Delta E_m$ |
| `D1/foul difference` | $\Delta e_m$ |
| `W1` | $r(c)$, retained only as a nominal within-match component |
| `W2`, `W2*`, adjusted `W2*` | superseded by $X_s$, $E_s$, and $e_s$ |
| `DDM`, `DDMF`, `DF` | retired; use `sanction_exposure` and the symbols above |

Canonical machine-readable columns are `exp_match_min`, `exp_susp_min`,
`d_exp_match`, `exp_match_per_foul`, `exp_susp_per_foul`, and `omega`.
Official figure filenames spell out `match-exposure` or
`suspension-exposure`; draft abbreviations do not appear in final figures.

## Version history

- **v0.2 (2026-07-13).** Terminology reset to sanction exposure; unified
  end-clock convention; formal 2026 two-window reset; second-caution stop
  rule; primary $\rho$, $\mu$, denominator, evidence, sensitivity, and
  amendment rules frozen; scope extended to 2014 and capped at 2026 M100.
- **v0.1 (2026-07-12).** Exploratory draft. Superseded and retained only for
  provenance through the archived draft figures.
