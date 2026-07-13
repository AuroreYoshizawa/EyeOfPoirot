#!/usr/bin/env python3
"""Build the per-card normalized table (T2) from the raw-source archive.

Inputs (data/raw/, private archive):
  {year}/fifa/calendar.json                 match metadata (numbers, stages, teams, dates)
  {year}/fifa/timelines/m{NNN}_{id}.json    event feed: cards (Type 2/3/4), period starts/ends (Type 7/8)
  2014/fotmob/end_of_play.json              T_end substitute for 2014 (FIFA 2014 timelines are sparse backfill)

Outputs (data/derived/):
  cards_{year}.csv, cards_all.csv           one row per card event
  match_exposure_{year}.csv                 per team-match W1/D1 sums (players only)
  build_report.md                           coverage, reconciliation and acceptance-test results

Conventions (mirror docs/METHODOLOGY.md):
  C2  label-clock arithmetic: "45'+2'" -> 47.0; period boundaries may overlap, accepted.
  C5  T_end = MatchMinute label of the last in-play period's Type-8 event (shootout period 11 excluded).
      Fallback: wall-clock duration of that period from timestamps; else null.
  W1  = max(0, basis - t), basis 120 for cards in ET periods (7/9/11), else 90. Yellows only.
  D1  = rho * max(0, T_end - t), rho = 2 for Y2/R else 1. Null if T_end unknown.
  N   = potential fixtures remaining before the post-QF caution amnesty (never elimination-truncated):
        group card: remaining scheduled group matches of that team + K (K = 3 in 2026 [R32,R16,QF], else 2)
        R32 -> 2, R16 -> 1, QF/SF/3P/F -> 0.
  W2  = W1 + 90*N, yellow rows only (Y2/R handled at the W2* stage together with omega).
  Officials (IdPlayer null) carry is_official=1 and are excluded from all player sums.
"""

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "derived"

EDITIONS = [2014, 2018, 2022, 2026]
K_KNOCKOUT_BEFORE_AMNESTY = {2014: 2, 2018: 2, 2022: 2, 2026: 3}
CARD_TYPES = {2: "Y", 3: "R", 4: "Y2"}
RHO = {"Y": 1, "Y2": 2, "R": 2}
ET_PERIODS = {7, 9, 11}
PLAY_PERIOD_NOMINAL_START = {3: 0.0, 5: 45.0, 7: 90.0, 9: 105.0}


def loc(x):
    """FIFA locale-list -> plain string."""
    if isinstance(x, list) and x:
        return x[0].get("Description", "")
    return x or ""


def parse_minute(label):
    """"45'+2'" -> (47.0, 45, 2); "31'" -> (31.0, 31, 0). Returns (t, base, added) or None."""
    if not label:
        return None
    m = re.match(r"^(\d+)'(?:\s*\+\s*(\d+)')?$", label.strip())
    if not m:
        return None
    base, added = int(m.group(1)), int(m.group(2) or 0)
    return float(base + added), base, added


def official_name(desc):
    m = re.match(r"^(.*?)\s*\(", desc or "")
    return m.group(1).strip() if m else (desc or "").strip()


def load_calendar(year):
    cal = json.load(open(RAW / f"{year}/fifa/calendar.json"))["Results"]
    matches = {}
    for r in cal:
        n = r["MatchNumber"]
        matches[n] = {
            "match_number": n,
            "fifa_match_id": r["IdMatch"],
            "date": r["Date"],
            "stage": loc(r.get("StageName")),
            "group": loc(r.get("GroupName")),
            "is_group": bool(r.get("IdGroup")) or bool(loc(r.get("GroupName"))),
            "home_id": str(r["Home"]["IdTeam"]) if r.get("Home") else None,
            "away_id": str(r["Away"]["IdTeam"]) if r.get("Away") else None,
            "home": loc((r.get("Home") or {}).get("TeamName")),
            "away": loc((r.get("Away") or {}).get("TeamName")),
            "status": r.get("MatchStatus"),
        }
    return matches


def stage_horizon(match, team_id, matches, year):
    """N: potential fixtures before the post-QF amnesty node."""
    stage = match["stage"].lower()
    if match["is_group"]:
        later_group = sum(
            1 for m in matches.values()
            if m["is_group"] and team_id in (m["home_id"], m["away_id"]) and m["date"] > match["date"]
        )
        return later_group + K_KNOCKOUT_BEFORE_AMNESTY[year]
    if "round of 32" in stage:
        return 2
    if "round of 16" in stage:
        return 1
    return 0  # QF, SF, third place, final: at/after the amnesty node


def t_end_from_timeline(events):
    """(t_end, source) from the last in-play period's Type-8 label; timestamp fallback."""
    ends = [e for e in events if e.get("Type") == 8 and e.get("Period") in PLAY_PERIOD_NOMINAL_START]
    if not ends:
        return None, "none"
    last = max(ends, key=lambda e: PLAY_PERIOD_NOMINAL_START[e["Period"]])
    parsed = parse_minute(last.get("MatchMinute"))
    if parsed:
        return parsed[0], "timeline_period_label"
    # fallback: wall clock duration of that period
    starts = [e for e in events if e.get("Type") == 7 and e.get("Period") == last["Period"]]
    if starts and last.get("Timestamp") and starts[0].get("Timestamp"):
        from datetime import datetime

        def ts(x):
            return datetime.fromisoformat(x.replace("Z", "+00:00"))

        dur_min = (ts(last["Timestamp"]) - ts(starts[0]["Timestamp"])).total_seconds() / 60.0
        return PLAY_PERIOD_NOMINAL_START[last["Period"]] + dur_min, "timeline_timestamps"
    return None, "none"


def load_fotmob_2014():
    p = RAW / "2014/fotmob/end_of_play.json"
    if not p.exists():
        return {}
    data = json.load(open(p))
    rows = data if isinstance(data, list) else data.get("matches", data.get("results", []))
    out = {}
    for r in rows:
        if r.get("t_end_minutes") is not None:
            out[r["match_number"]] = (float(r["t_end_minutes"]), "fotmob")
        elif r.get("went_to_et"):
            # m049 BRA-CHI: ET2 stoppage unrecorded anywhere; explicit lower-bound fill
            out[r["match_number"]] = (120.0, "fotmob_lower_bound")
    return out


def build_edition(year, report):
    matches = load_calendar(year)
    fotmob = load_fotmob_2014() if year == 2014 else {}
    rows = []
    tl_files = sorted((RAW / f"{year}/fifa/timelines").glob("m*.json"))
    t_end_missing = []
    for f in tl_files:
        n = int(f.name[1:4])
        match = matches[n]
        events = json.load(open(f)).get("Event", [])
        t_end, t_end_src = t_end_from_timeline(events)
        if t_end is None and n in fotmob:
            t_end, t_end_src = fotmob[n]
        if t_end is None:
            t_end_missing.append(n)
        had_et = any(e.get("Period") in ET_PERIODS for e in events)

        cards = [e for e in events if e.get("Type") in CARD_TYPES]
        # 2014-era encoding: a second caution appears as a second Type-2 event with no
        # Type-3/4 red event (verified: Palacios m010, Katsouranis m022, Duarte m052 = the
        # three 2014 second-yellow dismissals; straight reds are Type 3). Reclassify the
        # later yellow of such a pair as Y2. Modern editions encode the second caution as
        # Type 4 directly, so this should never fire there — warn if it does.
        seen_yellow = {}
        for e in sorted((c for c in cards if c["Type"] == 2 and c.get("IdPlayer")),
                        key=lambda c: (parse_minute(c.get("MatchMinute")) or (9e9, 0, 0))[0]):
            pid = e["IdPlayer"]
            if pid in seen_yellow:
                e["_reclass_y2"] = True
                if year != 2014:
                    report["warnings"].append(
                        f"{year} m{n:03d}: double Type-2 for player {pid} reclassified to Y2 — verify")
            else:
                seen_yellow[pid] = True
        # first-yellow lookup for Y2 linkage
        first_yellow = {}
        for e in sorted(cards, key=lambda e: (parse_minute(e.get("MatchMinute")) or (9e9,))[0] if isinstance((parse_minute(e.get("MatchMinute")) or (9e9,)), tuple) else 9e9):
            if e["Type"] == 2 and e.get("IdPlayer") and e["IdPlayer"] not in first_yellow:
                first_yellow[e["IdPlayer"]] = parse_minute(e.get("MatchMinute"))

        for e in cards:
            ct = "Y2" if e.get("_reclass_y2") else CARD_TYPES[e["Type"]]
            parsed = parse_minute(e.get("MatchMinute"))
            t = parsed[0] if parsed else None
            period = e.get("Period")
            team_id = str(e.get("IdTeam") or "")
            if team_id == match["home_id"]:
                team, opp = match["home"], match["away"]
            elif team_id == match["away_id"]:
                team, opp = match["away"], match["home"]
            else:
                team, opp = "?", "?"
                report["warnings"].append(f"{year} m{n:03d}: card team id {team_id} not in calendar")
            desc = loc(e.get("EventDescription"))
            is_official = e.get("IdPlayer") is None
            # ET basis: trust Period when present; else infer from match context
            if period in ET_PERIODS:
                basis = 120.0
            elif period in (3, 5):
                basis = 90.0
            else:
                basis = 120.0 if (had_et and t is not None and t > 90) else 90.0

            # W1 is a yellow-card quantity (Y and Y2 both are yellows shown); direct reds carry no W1
            w1 = max(0.0, basis - t) if (t is not None and ct in ("Y", "Y2")) else None
            d1 = RHO[ct] * max(0.0, t_end - t) if (t is not None and t_end is not None) else None
            N = stage_horizon(match, team_id, matches, year)
            w2 = (w1 + 90 * N) if (ct == "Y" and w1 is not None) else None
            fy = first_yellow.get(e.get("IdPlayer")) if ct == "Y2" else None

            rows.append({
                "edition": year,
                "match_number": n,
                "fifa_match_id": match["fifa_match_id"],
                "stage": match["stage"] or (f"Group {match['group']}" if match["group"] else ""),
                "date_utc": match["date"],
                "team": team,
                "opponent": opp,
                "team_id": team_id,
                "is_official": int(is_official),
                "recipient": official_name(desc) if is_official else (desc.split(" (")[0].strip() if desc else ""),
                "id_player": e.get("IdPlayer") or "",
                "card_type": ct,
                "minute_label": e.get("MatchMinute") or "",
                "t_min": t,
                "period": period,
                "basis": basis,
                "t_end_min": t_end,
                "t_end_source": t_end_src,
                "rho": RHO[ct],
                "W1": round(w1, 2) if w1 is not None else "",
                "D1": round(d1, 2) if d1 is not None else "",
                "N_horizon": N,
                "W2": round(w2, 2) if w2 is not None else "",
                "first_yellow_t_min": fy[0] if fy else "",
                "event_description": desc,
            })
    report.setdefault("t_end_missing", {})[year] = t_end_missing
    return rows


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


ACCEPTANCE = [
    # (edition, match_number, {team_name_substring: expected_player_D1_sum})
    (2022, 57, {"Argentina": 292, "Netherlands": 260}),
    (2022, 58, {"Brazil": 196, "Croatia": 96}),
    (2026, 100, {"Argentina": 66, "Switzerland": 187}),
    (2018, 50, {"Argentina": 259, "France": 47}),
    (2018, 64, {"France": 122, "Croatia": 2}),
]
ACCEPTANCE_W1 = [
    (2026, 95, {"Argentina": 0, "Egypt": 0}),
    (2026, 86, {"Argentina": 5, "Cabo Verde": 22}),
    (2026, 92, {"England": 129, "Mexico": 19}),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"warnings": []}
    all_rows = []
    for year in EDITIONS:
        rows = build_edition(year, report)
        write_csv(OUT / f"cards_{year}.csv", rows)
        all_rows.extend(rows)
    write_csv(OUT / "cards_all.csv", all_rows)

    # per team-match exposure sums (players only)
    expo = {}
    for r in all_rows:
        if r["is_official"]:
            continue
        key = (r["edition"], r["match_number"], r["team"])
        e = expo.setdefault(key, {"edition": r["edition"], "match_number": r["match_number"],
                                  "team": r["team"], "opponent": r["opponent"],
                                  "cards": 0, "sum_W1": 0.0, "sum_D1": 0.0, "sum_D1_endm1": 0.0,
                                  "d1_complete": 1})
        e["cards"] += 1
        if r["W1"] != "":
            e["sum_W1"] += float(r["W1"])
        if r["D1"] != "":
            e["sum_D1"] += float(r["D1"])
            # same sum under the alternative end-clock convention (T_end minus one label minute)
            if r["t_end_min"] is not None and r["t_min"] is not None:
                e["sum_D1_endm1"] += r["rho"] * max(0.0, (r["t_end_min"] - 1) - r["t_min"])
        else:
            e["d1_complete"] = 0
    expo_rows = sorted(expo.values(), key=lambda x: (x["edition"], x["match_number"], x["team"]))
    for year in EDITIONS:
        write_csv(OUT / f"match_exposure_{year}.csv", [e for e in expo_rows if e["edition"] == year])

    # ---- report ----
    lines = ["# Cards table build report", ""]
    for year in EDITIONS:
        rows = [r for r in all_rows if r["edition"] == year]
        players = [r for r in rows if not r["is_official"]]
        officials = [r for r in rows if r["is_official"]]
        bytype = {t: sum(1 for r in players if r["card_type"] == t) for t in ("Y", "Y2", "R")}
        miss = report["t_end_missing"][year]
        lines.append(
            f"- **{year}**: {len(players)} player cards (Y {bytype['Y']} / Y2 {bytype['Y2']} / R {bytype['R']}), "
            f"{len(officials)} official cards; matches missing T_end: {len(miss)}"
            + (f" -> D1 blank there ({miss[:6]}{'...' if len(miss) > 6 else ''})" if miss else "")
        )
    lines.append("")
    lines.append("## Acceptance tests (player-only sums vs published figure values)")
    failures = 0
    for year, n, expect in ACCEPTANCE:
        for team_sub, want in expect.items():
            ent = next((e for k, e in expo.items()
                        if k[0] == year and k[1] == n and team_sub.lower() in k[2].lower()), None)
            got, got_m1 = (ent["sum_D1"], ent["sum_D1_endm1"]) if ent else (0.0, 0.0)
            if abs(got - want) < 0.51:
                lines.append(f"- PASS {year} m{n:03d} {team_sub}: D1 {got:.1f} vs figure {want}")
            elif abs(got_m1 - want) < 0.51:
                lines.append(f"- PASS* {year} m{n:03d} {team_sub}: figure {want} == T_end-1' convention "
                             f"(label convention gives {got:.1f})")
            else:
                failures += 1
                lines.append(f"- FAIL {year} m{n:03d} {team_sub}: D1 {got:.1f} (T_end-1': {got_m1:.1f}) vs figure {want}")
    for year, n, expect in ACCEPTANCE_W1:
        for team_sub, want in expect.items():
            got = next((e["sum_W1"] for k, e in expo.items()
                        if k[0] == year and k[1] == n and team_sub.lower() in k[2].lower()), 0.0)
            ok = abs(got - want) < 0.51
            failures += (not ok)
            lines.append(f"- {'PASS' if ok else 'FAIL'} {year} m{n:03d} {team_sub}: W1 {got:.1f} vs figure {want}")
    if report["warnings"]:
        lines += ["", "## Warnings"] + [f"- {w}" for w in report["warnings"]]
    (OUT / "build_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nrows total={len(all_rows)}  acceptance failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
