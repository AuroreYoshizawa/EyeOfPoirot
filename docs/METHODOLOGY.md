# Methodology — sanction-exposure metrics (v0.2.1, frozen 2026-07-13)

This document is the frozen Phase A specification for *Eye of Poirot*. It is
written so that an independent analyst can rebuild every published quantity
from the event-level tables. Version 0.2 supersedes the draft `W1`, `D1`,
`W2`, `W2*`, `DDM`, `DDMF`, and `DF` nomenclature. Version 0.2.1 is a
pre-registration revision made later the same day, before 2026 M101 and
before any registration was submitted; its changes are enumerated in §6 and
in `docs/AMENDMENTS.md`.

**Analysis scope.** FIFA World Cups 2014, 2018, and 2022 in full, plus only
completed 2026 matches M1–M100. The unplayed 2026 semi-finals, third-place
match, and final (M101–M104) are outside this frozen snapshot.

**Third-place match exclusion.** Cards shown in a third-place match create no
exposure terms, and fouls committed in it enter no denominator. The fixture
itself stays in the schedule universe: a suspension actually served in a
third-place match still counts as a served match, and the availability
components of $\omega$ (minutes, squad membership, suspension and injury
intervals) include it. The rationale is that the third-place fixture carries
no onward qualification stake, so its own events are excluded, while
sanctions spilling into it from earlier matches remain real losses.

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
| $F_i$ | all-tournament fouls committed by team $i$ within the edition cutoff, excluding the third-place match |
| $M_p$ | nominal minutes played by player $p$ |
| $T_i$ | sum of nominal match durations for team $i$: 90 or 120 per match |
| $S_p$ | nominal minutes unavailable through a dismissal or a suspension being served |
| $I_p$ | nominal minutes unavailable through a documented injury or illness |

The normalized data model consists of match, card, team-match foul, player-
match participation, disciplinary-decision, suspension, availability, and
evidence tables. Player
and team identifiers are retained whenever a source exposes them; normalized
names are display fields, not join keys where an identifier exists.

FIFA period codes distinguish cards shown during play (`3`, `5`, `7`, `9`),
an interval (`0`), post-play administration (`10`), and a penalty shoot-out
(`11`). All remain in the card census. Only the in-play class enters $E_m$.

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

Complete 2014 team-match foul totals are taken from archived HuffPost World
Cup match-statistics pages, which credit Opta as data provider. FotMob has a
usable foul statistic for 19 of the 64 matches and is retained as an
independent cross-check: 13 match-level home/away pairs agree exactly and six
differ by one foul for one team. The complete HuffPost/Opta layer is used in
the published denominator; layers are never averaged or silently merged.

Player participation for all four editions is reconstructed from archived
FIFA live match-centre payloads using FIFA player identifiers. Stoppage labels
are reduced to the nominal clock for participation (for example, `45+4`
maps to nominal minute 45) while their cumulative value remains in the event
table for $E_m$.

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
- [HuffPost 2014 World Cup statistics, data credited to Opta](https://data.huffingtonpost.com/2014/world-cup/statistics)
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

Match exposure is defined for knockout matches other than the third-place
match, which is excluded together with its fouls (§Third-place match
exclusion).

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

For the winner-perspective figures, the same normalized differential is
displayed as

$$
\Delta E_m'(i,m)=\frac{E_m(i,m)}{F_{im}}
-\frac{E_m(o,m)}{F_{om}}=\Delta e_m(i,m),
$$

where $i$ is the FIFA-recorded winner. The prime is a reporting label, not an
additional division applied to $e_m$.

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

### 3.2 Knockout-impact scope

$X_s$ prices only the knockout impact of the disciplinary record. Terms are
created by:

- cards shown in knockout matches other than the third-place match;
- for 2014, 2018, and 2022 only, a **carried-in caution**: a player entering
  the knockout stage with exactly one pending single caution from the group
  stage is treated as if that caution had been shown at minute 0 of the
  team's first knockout match. The group card itself creates no term; the
  carried-in caution replaces it. Because cautions pair chronologically, at
  most one caution can be pending at knockout entry.

2026 group cautions are cancelled at the group-stage reset and never create a
term. Group cards otherwise create no direct terms: in-group risk and a
suspension served in a group match are group-stage impact and outside this
metric. A suspension earned in the group stage but actually served in a
knockout match is knockout impact and enters the served term of §3.4.

### 3.3 Caution risk intervals

Each in-scope ordinary caution $c$ opens a risk interval $L(c)$ that runs
until the earliest of the applicable reset or the player's next
suspension-causing card (a cumulative second caution or any dismissal),
measured at minute granularity.

**In-match remainder.** The default remainder is nominal,

$$
r(c)=\max(0,B_c-t_c),
\qquad
B_c=\begin{cases}90,&\text{regulation period},\\120,&\text{extra time},
\end{cases}
$$

with two exact-clock replacements in which the remainder is
$\max(0,T_{end,m(c)}-t_c)$ instead:

1. a caution received in stoppage time or in extra time — its remaining
   threat runs on the observed clock, so a stoppage-time caution is not
   priced at zero;
2. any caution shown in a semi-final or a final — after the quarter-final
   reset no future fixture can be reached by accumulation, and while the
   semi-final is being played neither side knows who will advance, so the
   live threat is a same-match second caution costing the next fixture, and
   that threat runs on the observed clock for the exact remaining minutes.

**Horizon blocks.** Untriggered, the interval extends past the current match
by $90N(c)$ fixture blocks, where $N(c)$ counts the team's potential fixtures
strictly after the card and before the applicable reset, following the full
bracket path and not shortened by the team's actual elimination. Semi-final
and final cautions have $N=0$ and use the exact-clock remainder above.

| Edition | R32 | R16 | QF | SF/final |
|---|---:|---:|---:|---:|
| 2014/2018/2022 | — | 1 | 0 | exact clock |
| 2026 | 2 | 1 | 0 | exact clock |

A carried-in caution at minute 0 of the first knockout match prices
$90+90N$ of that match, so 180 minutes at a 2014–2022 round of 16.

**Stop rule (minute granularity).** If the interval is stopped by a
suspension-causing card at $t_2$:

- same match: $L(c)=\max(0,\min(t_2,K_c)-t_c)$, where $K_c$ is the
  applicable in-match cap — $B_c$ for the nominal case, $T_{end,m(c)}$ for
  the two exact-clock cases;
- later match (nominal-remainder cautions only): $L(c)=r(c)+90G+\min(t_2,90)$,
  where $G$ counts the team's fixtures strictly between the two matches.

The triggering card itself receives no forward blocks: a same-match `Y2`
keeps only its dismissal term, and a cross-match triggering caution keeps its
own in-match remainder. A stopped interval never exceeds its untriggered
value.

### 3.4 Player-level sanction minutes

For player $p$, let $C_p^{Y}$ be in-scope ordinary cautions (§3.2, a
carried-in caution included), $L(c)$ the §3.3 risk interval, $C_p^{D}$ be
in-scope dismissal events (`Y2` or `R`), and $D_p$, $A_p$ be the numbers of
dismissal and two-caution suspension matches actually served **in knockout
matches** — the third-place match included — within the observed edition,
whether the suspension was earned in the group stage or the knockout stage.
Then

$$
X_s(p;\rho,\mu)=
\sum_{c\in C_p^{Y}} L(c)
+\sum_{c\in C_p^{D}}\rho\max(0,T_{end,m(c)}-t_c)
+90\mu\,(D_p+A_p).
$$

The primary served-suspension multiplier is $\mu=1.25$, with sensitivity
$\mu\in\{1,1.25,1.5\}$. Suspension terms are included only when the loss is
observed within the edition cutoff. Pending sanctions after the team's final
observed match are recorded but do not create fictitious served minutes.
An automatic sanction is initially mapped to the next team match. A sourced
disciplinary decision may enumerate additional service matches, carry a ban
into the tournament, or defer execution. Only the enumerated matches enter
$D_p+A_p$, and every claimed served match must also be confirmed by the
official lineup. A deferred decision is published as `deferred` and creates no
served term.

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
knockout matches within the edition cutoff, excluding the third-place match.
A prespecified sensitivity uses knockout-stage fouls only, likewise excluding
the third-place match. The edition pooled ratio is

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
2. Automatic suspensions are derived from the chronological card ledger;
   sourced disciplinary decisions may extend, carry in, or defer them. Every
   claimed service match is checked against its official line-up.
3. Injury/illness requires explicit evidence. A commentary phrase such as
   "replaced because of an injury" may establish the in-match remainder; a
   whole-match absence requires an independent team or media report.
4. If evidence cannot distinguish tactical non-selection from injury, status
   is `unexplained` and injury minutes are zero.

If a rule-derived suspension trigger conflicts with the next official lineup,
both observations are published with status `conflict`; the event remains in
the card ledger, but no served-suspension term or unavailable interval is
inferred. This implements the requirement that $D_p$ and $A_p$ count only
losses observed as served.

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

A boundary sensitivity replaces $T_{end,m}$ by $T_{end,m}-1$ in every
component that uses the observed final-whistle clock: $x_m(c;\rho)$, the
dismissal term in $X_s$, and the exact-clock caution remainders of §3.3
(stoppage/extra-time receipt and semi-final/final cautions). Nominal caution
remainders $r(c)$ and served-match blocks are unchanged. This checks
inclusive-versus-exclusive end-minute coding and is not a second primary
specification.

### 5.1 Prespecified descriptive depth check

After each edition's full computation, the association between tournament
depth and $e_s$ is reported as a prespecified descriptive confound check:

- unit: knockout-stage teams of one edition; depth = number of matches
  played within the edition cutoff, excluding the third-place match (so a
  losing semi-finalist and a finalist differ);
- statistic: Kendall $\tau_b$ between depth and $e_s$ at the primary
  setting, with a within-edition permutation $p$ (10,000 permutations,
  two-sided, fixed seed 20260713);
- editions are reported separately and never pooled: cross-edition strength
  structures differ too much for a pooled coefficient to be meaningful;
- a prespecified secondary depth proxy repeats the test with the World
  Football Elo pre-tournament rating (eloratings.net) in place of matches
  played, once that table is collected and archived;
- claim boundary: this is a descriptive check of whether $e_s$ drifts
  mechanically with tournament depth. Depth is partly endogenous to
  discipline itself (suspensions weaken teams), so the coefficient is not an
  estimate of a causal strength effect and is not reported as one.

Required invariants:

- player-card census: 2014 = 194, 2018 = 224, 2022 = 228, 2026 M1–M100 = 270;
- $E_m\ge0$, $E_s\ge0$, and $0\le\omega\le1$;
- the stop rule never yields an interval longer than the untriggered
  interval;
- group-stage and third-place cards create no exposure terms, and served
  suspensions are counted only when the service match is a knockout match;
- two match perspectives satisfy $\Delta E_m(i,m)=-\Delta E_m(o,m)$, and
  likewise for $\Delta e_m$ when defined;
- every positive injury interval has a non-empty source URL;
- sourced disciplinary decisions retain their decision URL and lineup check;
- 2026 inputs and outputs contain no event from M101–M104.

Hand-checked fixtures cover regulation stoppage, extra time, shoot-outs,
direct red, same-match second caution, cross-match accumulation, a reset, and
an injury-adjusted opportunity denominator in every edition where applicable.
Four matches—one per edition—also have an independent ESPN/Opta match-page
check; source-display differences remain visible as `AUDIT`, not forced
agreements.

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

**v0.2.1 pre-registration revision (2026-07-13, before 2026 M101 and before
any registration).** Review against the analyst's original commissioned
definitions found that v0.2 had formalized four rules differently from the
commission, and one agreed rule was added. All five changes were applied
before the OSF submission; no confirmatory analysis had been run under
either variant. The changes and their expected directional effects on
$X_s$:

1. knockout-impact scope replaces whole-tournament pricing (group cards now
   enter only as a 2014–2022 carried-in caution; group-served suspensions no
   longer count) — decreases $X_s$ for players carded in the group stage;
2. the second-caution stop rule is applied at minute granularity instead of
   whole-fixture granularity — decreases stopped intervals;
3. cautions received in stoppage time or extra time use the exact-clock
   remainder — increases those intervals (a stoppage caution is no longer
   floored at zero);
4. semi-final and final cautions use the exact-clock remainder — increases
   those intervals slightly relative to a nominal remainder;
5. the third-place match is excluded at the event level (no exposure terms,
   no denominator fouls; service and availability there still count) —
   removes small amounts from both numerator and denominator.

A prespecified depth check (§5.1) was added at the same time, before any
correlation had been computed. No registration existed under the v0.2 rules.

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

- **v0.2.1 (2026-07-13, pre-registration).** Knockout-impact scope with
  2014–2022 carried-in cautions; minute-granular stop rule; exact-clock
  remainders for stoppage/extra-time and semi-final/final cautions;
  event-level third-place exclusion; knockout-only served-suspension
  counting; prespecified depth check (§5.1); boundary sensitivity extended
  to all observed-clock components. Enumerated with directions in §6.
- **v0.2 (2026-07-13).** Terminology reset to sanction exposure; unified
  end-clock convention; formal 2026 two-window reset; second-caution stop
  rule; primary $\rho$, $\mu$, denominator, evidence, sensitivity, and
  amendment rules frozen; scope extended to 2014 and capped at 2026 M100.
- **v0.1 (2026-07-12).** Exploratory draft. Superseded and retained only for
  provenance through the archived draft figures.
