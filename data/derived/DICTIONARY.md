# data/derived — column dictionary and build conventions

Built by `pipeline/build_cards_table.py` from the private raw archive (`data/raw/`, gitignored).
Regenerate with `python3 pipeline/build_cards_table.py`; acceptance-test results land in `build_report.md`.

## cards_{year}.csv / cards_all.csv — one row per card event

| Column | Meaning |
|---|---|
| `edition` | 2014 / 2018 / 2022 / 2026 |
| `match_number` | FIFA official match number (note: figures published before 2026-07-12 had 2022 #57/#58 labels swapped) |
| `fifa_match_id` | FIFA IdMatch (join key to calendars, timelines, report PDFs) |
| `stage`, `date_utc` | from FIFA calendar; group matches show "First stage"/group |
| `team`, `opponent`, `team_id` | card-receiving side |
| `is_official` | 1 = team official (coach/bench; timeline `IdPlayer` null). Excluded from every player metric; kept for the separate officials tally |
| `recipient`, `id_player` | player name parsed from the event description (authoritative naming comes later from lineup sources); FIFA player id |
| `card_type` | `Y` yellow, `Y2` second caution (red), `R` direct red |
| `minute_label`, `t_min` | FIFA MatchMinute label and its label-clock value: `"45'+2'"` → 47.0 (convention C2) |
| `period` | FIFA period code: 3=1H, 5=2H, 7=ET1, 9=ET2, 11=shootout |
| `basis` | W1 nominal clock: 90 for periods 3/5, 120 for 7/9/11 |
| `t_end_min`, `t_end_source` | actual end-of-play label minute; `timeline_period_label` (Type-8 event of last in-play period), `timeline_timestamps` (fallback), `fotmob` (2014: wall-clock halfs for 60 matches, announced ET2 board for 3 shootout matches — shootout always excluded), `fotmob_lower_bound` (2014 m049 BRA–CHI only: ET2 stoppage unrecorded in any source → T_end = 120.0 exact floor, understates late-card D1 by ≤ ~2′), `none` |
| `rho` | dismissal multiplier: 2 for Y2/R, else 1 |
| `W1` | `max(0, basis − t_min)`; yellows only (Y and Y2 rows — both are yellows shown); blank for R |
| `D1` | `rho × max(0, t_end_min − t_min)`; blank while t_end unknown |
| `N_horizon` | potential team fixtures remaining before the post-QF caution amnesty, never truncated by elimination: group card = remaining scheduled group matches + K (K=3 in 2026 [R32/R16/QF], else 2); R32→2, R16→1, QF/SF/3P/F→0 |
| `W2` | `W1 + 90 × N_horizon`, plain-yellow (Y) rows only; Y2/R deterrence is priced at the W2* stage together with ω |
| `first_yellow_t_min` | for Y2 rows: label minute of the player's first caution (needed for the W2* second-yellow term) |
| `event_description` | verbatim FIFA event text (en-GB) |

## match_exposure_{year}.csv — per team-match sums (players only)

`cards`, `sum_W1`, `sum_D1` (label convention), `sum_D1_endm1` (T_end−1′ convention, see below), `d1_complete` (0 if any card lacked t_end).

## Conventions and findings the numbers depend on

1. **Label-clock arithmetic (C2).** `"45'+2'"` counts as 47.0; period label ranges overlap by construction; differences vs media sources of ±1′ are expected (Wikipedia rounds differently).
2. **T_end (C5).** Read from the FIFA timeline's period-end (Type 8) `MatchMinute` label of the last in-play period — shootouts (period 11) never count. 2014 timelines are sparse backfill without period events; T_end comes from the FotMob substitute source with the shootout excluded by rule (ET matches: 120 + ET2 stoppage).
3. **Dual end-clock finding (2026-07-13 reconciliation).** The published 2026 figures reproduce exactly under the FIFA label convention; the published 2018/2022 figures reproduce exactly under `T_end − 1′`. Both are carried in `match_exposure_*` so either convention can be audited; the standardization decision is pending.
4. **2014 second cautions.** FIFA's 2014 backfill encodes a second yellow as a second Type-2 event with no red event. Rule: a player's second Type-2 in the same match is reclassified `Y2` (fires exactly three times: Palacios m010, Katsouranis m022, Duarte m052; the seven Type-3 events are the straight reds — total 10, matching the official record). The rule warns if it ever fires outside 2014.
5. **Red-card censuses vs official records.** 2014: 184 Y + 3 Y2 + 7 R; 2018: 220/2/2; 2022: 224/3/1; 2026 (through M100): 256/1/13. Official cards: 2022 ×7, 2026 ×14, none logged for 2014/2018 by FIFA's feeds (officials' cards in those editions would need report/press sources — open item).
6. **Not yet in this table:** ω (player importance) and W2\* — they require the player-minutes and unavailability tables (lineups from report PDFs / Wikipedia stage pages; injury evidence), which are the next build stage.
