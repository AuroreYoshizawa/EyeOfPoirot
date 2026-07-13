#!/usr/bin/env python3
"""Build public normalized source observations from the private archive.

Cards, match clocks, and match identity are re-extracted from archived FIFA
and FotMob responses. The audited pre-freeze workbooks contribute only team
fouls, carded-player participation, and injury-evidence links. Their legacy
exposure formulas are never imported.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .config import (
    EDITIONS,
    EXPECTED_COMPLETED,
    EXPECTED_PLAYER_CARDS,
    EXPECTED_TEAM_MATCH_ROWS,
    RAW,
    SOURCE,
    stage_code,
)
from .io import as_float, as_int, ascii_tokens, fmt, name_key, read_csv, write_csv


CARD_TYPES = {2: "Y", 3: "R", 4: "Y2"}
PLAY_PERIOD_START = {3: 0.0, 5: 45.0, 7: 90.0, 9: 105.0}
ET_PERIODS = {7, 9}
FOTMOB_TEAM_ALIAS = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Côte d'Ivoire": "Ivory Coast",
    "Korea Republic": "South Korea",
    "United States": "USA",
}
HUFFPOST_TEAM_ALIAS = {
    "Bosnia-Herz.": "Bosnia-Herzegovina",
    "Bosnia and Herzegovina": "Bosnia-Herzegovina",
    "Ivory Coast": "Côte d'Ivoire",
    "South Korea": "Korea Republic",
    "USA": "United States",
}
# Four FIFA spellings/initial orders are not uniquely resolvable by a name
# normalizer. These crosswalks were checked against the card match, team and
# archived FotMob lineup before being frozen.
FIFA_FOTMOB_2014_OVERRIDES = {
    "213170": ("30744", "Masoud Shojaei"),
    "363578": ("253827", "Yong Lee"),
    "367555": ("132843", "Geoffroy Serey Die"),
    "311148": ("68253", "Benedikt Höwedes"),
}
# Five rows in the pre-freeze 2018 medical ledger used an adjacent fixture
# number. The player, opponent, interval, and linked report identify the
# correct match. Keeping the correction explicit prevents a silent join to a
# fixture in which the player's team did not participate.
MEDICAL_MATCH_NUMBER_OVERRIDES = {
    (2018, 15, "43926", "269058"): 16,  # James Rodríguez, Colombia v Japan
    (2018, 46, "43926", "269058"): 48,  # James Rodríguez, Senegal v Colombia
    (2018, 29, "43948", "311150"): 27,  # Mats Hummels, Germany v Sweden
    (2018, 19, "43835", "218083"): 18,  # Taisir Al-Jassim, Uruguay v Saudi Arabia
    (2018, 33, "43835", "218083"): 34,  # Taisir Al-Jassim, Saudi Arabia v Egypt
}
MEDICAL_SOURCE_OVERRIDES = {
    (2018, 16, "43926", "269058"): (
        "https://www.espn.com/soccer/story/_/id/37556874/"
        "colombia-james-rodriguez-not-starting-japan-calf-injury",
        "Left-calf injury kept James Rodríguez from starting against Japan; he entered as a substitute.",
    ),
    (2018, 48, "43926", "269058"): (
        "https://inside.fifa.com/tournaments/mens/worldcup/2018russia/news/"
        "jun-28-round-up-2973227",
        "FIFA reported James Rodríguez leaving the Senegal match with a muscle strain.",
    ),
    (2018, 56, "43926", "269058"): (
        "https://inside.fifa.com/tournaments/mens/worldcup/2018russia/news/"
        "england-into-quarter-finals-after-penalty-shootout-2981878",
        "FIFA reported Colombia playing England without the injured James Rodríguez.",
    ),
    (2018, 27, "43948", "311150"): (
        "https://www.sbs.com.au/news/article/"
        "germanys-hummels-unlikely-to-play-against-sweden-coach-low/zp4h7rtxw",
        "Reuters reported a training-ground neck injury made Hummels unavailable against Sweden.",
    ),
    (2018, 18, "43835", "218083"): (
        "https://www.lequipe.fr/Football/Actualites/"
        "Arabie-saoudite-taisir-al-jassim-sort-sur-blessure-contre-l-uruguay/913546",
        "A left-thigh injury forced Al-Jassim out against Uruguay before half-time.",
    ),
    (2018, 34, "43835", "218083"): (
        "https://www.si.com/soccer/2018/06/24/"
        "world-cup-preview-saudi-arabia-vs-egypt-classic-encounter-team-news-predictions-more",
        "The thigh injury sustained against Uruguay kept Al-Jassim unavailable against Egypt.",
    ),
}

MATCH_FIELDS = (
    "edition", "match_number", "match_id", "date_utc", "stage", "group_name",
    "home_team_id", "home_team", "away_team_id", "away_team", "nominal_minutes",
    "t_end_min", "t_end_source", "source_url", "source_archive",
)
CARD_FIELDS = (
    "card_id", "edition", "match_number", "match_id", "date_utc", "stage",
    "team_id", "team", "opponent", "recipient_type", "player_id", "player",
    "card_type", "minute_label", "t_min", "period", "event_scope", "nominal_basis_min",
    "t_end_min", "t_end_source", "source_url", "source_archive",
)
FOUL_FIELDS = (
    "edition", "match_number", "match_id", "stage", "team_id", "team", "opponent",
    "team_match_number", "fouls", "source_url", "source_archive",
)
PLAYER_MATCH_FIELDS = (
    "edition", "match_number", "match_id", "stage", "team_id", "team", "opponent",
    "team_match_number", "player_id", "player", "nominal_minutes", "lineup_status",
    "on_minute", "off_minute", "played_minutes", "source_url", "source_archive",
)
EVIDENCE_FIELDS = (
    "edition", "match_number", "match_id", "stage", "team_id", "team", "player_id",
    "player", "status", "start_minute", "end_minute", "unavailable_minutes",
    "evidence_tier", "evidence_note", "source_url", "source_archive",
)
SANCTION_DECISION_FIELDS = (
    "edition", "team_id", "team", "player_id", "player", "trigger_card_id",
    "decision_type", "service_match_numbers", "decision_status", "evidence_tier",
    "evidence_note", "source_url", "source_archive",
)
AUDIT_FIELDS = ("edition", "check", "observed", "expected", "status", "note")


def loc(value) -> str:
    if isinstance(value, list) and value:
        return value[0].get("Description", "")
    return value or ""


def parse_minute(label: str | None) -> float | None:
    if not label:
        return None
    match = re.match(r"^(\d+)'(?:\s*\+\s*(\d+)')?$", label.strip())
    if not match:
        return None
    return float(int(match.group(1)) + int(match.group(2) or 0))


def _load_calendars(raw_root: Path) -> dict[int, dict[int, dict]]:
    calendars: dict[int, dict[int, dict]] = {}
    for year in EDITIONS:
        payload = json.loads((raw_root / str(year) / "fifa" / "calendar.json").read_text())
        rows = {}
        for item in payload["Results"]:
            number = int(item["MatchNumber"])
            if year == 2026 and number > 100:
                continue
            is_group = bool(item.get("IdGroup"))
            home = item.get("Home") or {}
            away = item.get("Away") or {}
            rows[number] = {
                "edition": year,
                "match_number": number,
                "match_id": str(item["IdMatch"]),
                "id_stage": str(item["IdStage"]),
                "date_utc": item["Date"],
                "stage": stage_code(loc(item.get("StageName")), is_group),
                "group_name": loc(item.get("GroupName")),
                "home_team_id": str(home.get("IdTeam", "")),
                "home_team": loc(home.get("TeamName")),
                "away_team_id": str(away.get("IdTeam", "")),
                "away_team": loc(away.get("TeamName")),
            }
        if len(rows) != EXPECTED_COMPLETED[year]:
            raise ValueError(f"{year}: {len(rows)} completed/cutoff matches, expected {EXPECTED_COMPLETED[year]}")
        calendars[year] = rows
    return calendars


def _timeline_url(match: dict) -> str:
    return (
        "https://api.fifa.com/api/v3/timelines/17/"
        f"{match['season_id']}/{match['id_stage']}/{match['match_id']}?language=en"
    )


def _timeline_end(events: list[dict]) -> tuple[float | None, str]:
    ends = [event for event in events if event.get("Type") == 8 and event.get("Period") in PLAY_PERIOD_START]
    if not ends:
        return None, "missing"
    last = max(ends, key=lambda event: PLAY_PERIOD_START[event["Period"]])
    parsed = parse_minute(last.get("MatchMinute"))
    if parsed is not None:
        return parsed, "fifa_timeline_period_label"
    starts = [event for event in events if event.get("Type") == 7 and event.get("Period") == last["Period"]]
    if starts and last.get("Timestamp") and starts[0].get("Timestamp"):
        def timestamp(value: str) -> datetime:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))

        duration = (timestamp(last["Timestamp"]) - timestamp(starts[0]["Timestamp"])).total_seconds() / 60
        return PLAY_PERIOD_START[last["Period"]] + duration, "fifa_timeline_timestamps"
    return None, "missing"


def _fotmob_end(raw_root: Path) -> dict[int, tuple[float, str]]:
    payload = json.loads((raw_root / "2014" / "fotmob" / "end_of_play.json").read_text())
    rows = payload if isinstance(payload, list) else payload.get("matches", payload.get("results", []))
    result = {}
    for row in rows:
        number = int(row["match_number"])
        if row.get("t_end_minutes") is not None:
            result[number] = (float(row["t_end_minutes"]), "fotmob_period_clock")
        elif row.get("went_to_et"):
            # m049 has a proven 120-minute lower bound but no ET2 stoppage value.
            result[number] = (120.0, "fotmob_lower_bound")
    return result


def _load_timelines(raw_root: Path, calendars: dict[int, dict[int, dict]]):
    timeline_rows: dict[tuple[int, int], list[dict]] = {}
    timeline_paths: dict[tuple[int, int], Path] = {}
    for year, matches in calendars.items():
        for path in sorted((raw_root / str(year) / "fifa" / "timelines").glob("m*.json")):
            number = int(path.name[1:4])
            if number not in matches:
                continue
            timeline_rows[(year, number)] = json.loads(path.read_text()).get("Event", [])
            timeline_paths[(year, number)] = path
        missing = set(matches) - {number for y, number in timeline_rows if y == year}
        if missing:
            raise ValueError(f"{year}: missing timeline matches {sorted(missing)}")
    return timeline_rows, timeline_paths


def _build_matches(raw_root: Path, calendars, timelines, timeline_paths) -> list[dict]:
    fotmob_end = _fotmob_end(raw_root)
    output = []
    for year in EDITIONS:
        for number, base in sorted(calendars[year].items()):
            events = timelines[(year, number)]
            nominal = 120 if any(event.get("Period") in ET_PERIODS for event in events) else 90
            if year == 2014:
                t_end, source = fotmob_end[number]
            else:
                t_end, source = _timeline_end(events)
                if t_end is None:
                    raise ValueError(f"{year} m{number:03d}: missing T_end")
            match = dict(base)
            match["season_id"] = {2014: "251164", 2018: "254645", 2022: "255711", 2026: "285023"}[year]
            source_url = _timeline_url(match)
            output.append({
                **{key: match[key] for key in MATCH_FIELDS if key in match},
                "nominal_minutes": nominal,
                "t_end_min": fmt(t_end, 4),
                "t_end_source": source,
                "source_url": source_url if year != 2014 else "https://www.fotmob.com/api/data/matchDetails",
                "source_archive": str(timeline_paths[(year, number)].relative_to(raw_root.parent.parent)),
            })
    return output


def _event_name(event: dict) -> str:
    description = loc(event.get("EventDescription"))
    match = re.match(r"^(.*?)\s*\(", description)
    return (match.group(1) if match else description).strip()


def _build_cards(raw_root: Path, calendars, timelines, timeline_paths, matches: list[dict]) -> list[dict]:
    match_lookup = {(int(row["edition"]), int(row["match_number"])): row for row in matches}
    cards = []
    for year in EDITIONS:
        for number, match in sorted(calendars[year].items()):
            events = timelines[(year, number)]
            nominal = int(match_lookup[(year, number)]["nominal_minutes"])
            t_end = float(match_lookup[(year, number)]["t_end_min"])
            t_end_source = match_lookup[(year, number)]["t_end_source"]
            raw_cards = [event for event in events if event.get("Type") in CARD_TYPES]
            seen_yellow: set[str] = set()
            ordered = sorted(raw_cards, key=lambda event: parse_minute(event.get("MatchMinute")) or 9999)
            for event in ordered:
                player_id = str(event.get("IdPlayer") or "")
                card_type = CARD_TYPES[event["Type"]]
                if year == 2014 and card_type == "Y" and player_id:
                    if player_id in seen_yellow:
                        card_type = "Y2"
                    else:
                        seen_yellow.add(player_id)
                team_id = str(event.get("IdTeam") or "")
                if team_id == match["home_team_id"]:
                    team, opponent = match["home_team"], match["away_team"]
                elif team_id == match["away_team_id"]:
                    team, opponent = match["away_team"], match["home_team"]
                else:
                    raise ValueError(f"{year} m{number:03d}: card team {team_id} not in calendar")
                minute = parse_minute(event.get("MatchMinute"))
                if minute is None:
                    raise ValueError(f"{year} m{number:03d}: numeric minute missing for card {event.get('EventId')}")
                period = as_int(event.get("Period"), 0) or 0
                # FIFA uses 3/5/7/9 for the four in-play periods, 0 for an
                # interval, 10 for post-play administration, and 11 for the
                # penalty shoot-out. Retaining this distinction prevents
                # shoot-out and post-whistle cards entering E_m while keeping
                # the complete disciplinary census available for audit.
                event_scope = {
                    0: "interval",
                    3: "in_play",
                    5: "in_play",
                    7: "in_play",
                    9: "in_play",
                    10: "post_play",
                    11: "penalty_shootout",
                }.get(period, "unknown")
                if event_scope == "unknown":
                    raise ValueError(
                        f"{year} m{number:03d}: unknown FIFA card period {period}"
                    )
                basis = 120 if period in ET_PERIODS or (nominal == 120 and minute > 90) else 90
                source_match = dict(match)
                source_match["season_id"] = {2014: "251164", 2018: "254645", 2022: "255711", 2026: "285023"}[year]
                cards.append({
                    "card_id": f"{year}-{number:03d}-{event.get('EventId', len(cards) + 1)}",
                    "edition": year,
                    "match_number": number,
                    "match_id": match["match_id"],
                    "date_utc": match["date_utc"],
                    "stage": match["stage"],
                    "team_id": team_id,
                    "team": team,
                    "opponent": opponent,
                    "recipient_type": "player" if player_id else "official",
                    "player_id": player_id,
                    "player": _event_name(event),
                    "card_type": card_type,
                    "minute_label": event.get("MatchMinute", ""),
                    "t_min": fmt(minute, 3),
                    "period": period,
                    "event_scope": event_scope,
                    "nominal_basis_min": basis,
                    "t_end_min": fmt(t_end, 4),
                    "t_end_source": t_end_source,
                    "source_url": _timeline_url(source_match),
                    "source_archive": str(timeline_paths[(year, number)].relative_to(raw_root.parent.parent)),
                })
    # A handful of archived events omit EventDescription. Fill names from any
    # other card belonging to the same FIFA player id; identity never comes
    # from fuzzy name inference here.
    names: dict[tuple[int, str], str] = {}
    for row in cards:
        key = (int(row["edition"]), row["player_id"])
        if row["player_id"] and len(row["player"]) > len(names.get(key, "")):
            names[key] = row["player"]
    for row in cards:
        if row["recipient_type"] == "player" and not row["player"]:
            row["player"] = names.get((int(row["edition"]), row["player_id"]), "")
        if row["recipient_type"] == "player" and not row["player"]:
            raise ValueError(f"unresolved player name for {row['card_id']}")
    return cards


def _team_match_numbers(matches: list[dict]) -> dict[tuple[int, str, int], int]:
    appearances: dict[tuple[int, str], list[tuple[str, int]]] = defaultdict(list)
    for row in matches:
        year, number = int(row["edition"]), int(row["match_number"])
        appearances[(year, row["home_team_id"])].append((row["date_utc"], number))
        appearances[(year, row["away_team_id"])].append((row["date_utc"], number))
    result = {}
    for (year, team_id), values in appearances.items():
        for index, (_, number) in enumerate(sorted(values), start=1):
            result[(year, team_id, number)] = index
    return result


def _workbook_match_map(raw_root: Path, year: int) -> dict[int, str]:
    """Map a draft workbook's display sequence to the official FIFA match id."""
    path = raw_root / "draft_workbook_exports" / str(year) / "matches.csv"
    mapping = {}
    for row in read_csv(path):
        display_number = as_int(row.get("Match #"))
        match_id = str(as_int(row.get("FIFA match ID")) or "")
        if display_number is not None and match_id:
            mapping[display_number] = match_id
    return mapping


def _fotmob_fouls(path: Path) -> tuple[int, int] | None:
    payload = json.loads(path.read_text())
    groups = payload["content"]["stats"]["Periods"]["All"]["stats"]
    for group in groups:
        for stat in group.get("stats", []):
            if stat.get("key") == "fouls":
                home, away = stat["stats"]
                return int(home), int(away)
    return None


def _huffpost_fouls(path: Path) -> tuple[str, int, str, int]:
    """Return home name/fouls and away name/fouls from the archived table."""
    text = path.read_text(encoding="utf-8")
    teams_match = re.search(r"HPIN\.teams = (\[.*?\]);", text, flags=re.DOTALL)
    home_match = re.search(r"HPIN\.homeTeam = (\d+);", text)
    away_match = re.search(r"HPIN\.awayTeam = (\d+);", text)
    if not teams_match or not home_match or not away_match:
        raise ValueError(f"HuffPost team metadata missing: {path}")
    teams = {str(row["id"]): row["name"] for row in json.loads(teams_match.group(1))}
    fouls = {team_id: int(value) for team_id, value in re.findall(
        r'id="stat-(\d+)-fouls"[^>]*>(\d+)</td>', text
    )}
    home_id, away_id = home_match.group(1), away_match.group(1)
    if home_id not in fouls or away_id not in fouls:
        raise ValueError(f"HuffPost foul cells missing: {path}")
    return teams[home_id], fouls[home_id], teams[away_id], fouls[away_id]


def _build_fouls(raw_root: Path, matches: list[dict]) -> tuple[list[dict], dict]:
    match_lookup = {(int(row["edition"]), int(row["match_number"])): row for row in matches}
    match_id_lookup = {(int(row["edition"]), row["match_id"]): row for row in matches}
    team_no = _team_match_numbers(matches)
    output = []
    pair_lookup = {
        (row["home_team"], row["away_team"]): row
        for row in matches if int(row["edition"]) == 2014
    }
    huff_index_path = raw_root / "2014" / "huffpost" / "index.json"
    huff_index = json.loads(huff_index_path.read_text())
    primary_by_match = {}
    for record in huff_index["matches"]:
        path = raw_root / record["archive_path"]
        home_raw, home_fouls, away_raw, away_fouls = _huffpost_fouls(path)
        home = HUFFPOST_TEAM_ALIAS.get(home_raw, home_raw)
        away = HUFFPOST_TEAM_ALIAS.get(away_raw, away_raw)
        match = pair_lookup.get((home, away))
        if match is None:
            raise ValueError(f"HuffPost pair not found in FIFA calendar: {home} vs {away}")
        number = int(match["match_number"])
        primary_by_match[number] = (home_fouls, away_fouls)
        for team_side, opp_side, fouls in (
            ("home", "away", home_fouls), ("away", "home", away_fouls)
        ):
            team_id = match[f"{team_side}_team_id"]
            output.append({
                "edition": 2014, "match_number": number, "match_id": match["match_id"],
                "stage": match["stage"], "team_id": team_id, "team": match[f"{team_side}_team"],
                "opponent": match[f"{opp_side}_team"],
                "team_match_number": team_no[(2014, team_id, number)], "fouls": fouls,
                "source_url": record["page_url"],
                "source_archive": str(path.relative_to(raw_root.parent.parent)),
            })
    comparisons = []
    for path in sorted((raw_root / "2014" / "fotmob" / "matches").glob("m*.json")):
        pair = _fotmob_fouls(path)
        if pair is None:
            continue
        number = int(path.name[1:4])
        comparisons.append({
            "match_number": number,
            "huffpost": primary_by_match[number],
            "fotmob": pair,
            "match": primary_by_match[number] == pair,
        })
    for year in (2018, 2022, 2026):
        path = raw_root / "draft_workbook_exports" / str(year) / "team-match.csv"
        for raw in read_csv(path):
            match_id = str(as_int(raw["Match ID"]) or "")
            match = match_id_lookup.get((year, match_id))
            if match is None:
                continue
            number = int(match["match_number"])
            team_id = str(as_int(raw["Team ID"]) or "")
            if team_id == match["home_team_id"]:
                team, opponent = match["home_team"], match["away_team"]
            elif team_id == match["away_team_id"]:
                team, opponent = match["away_team"], match["home_team"]
            else:
                raise ValueError(f"{year} m{number:03d}: foul team id {team_id} not in calendar")
            source_url = raw.get("FIFA team stats") or raw.get("FIFA stats API") or raw.get("Foul-stat source")
            if not source_url:
                raise ValueError(f"{year} m{number:03d} {team}: foul source missing")
            output.append({
                "edition": year, "match_number": number, "match_id": match["match_id"],
                "stage": match["stage"], "team_id": team_id, "team": team, "opponent": opponent,
                "team_match_number": team_no[(year, team_id, number)], "fouls": as_int(raw["Fouls"]),
                "source_url": source_url,
                "source_archive": str(path.relative_to(raw_root.parent.parent)),
            })
    crosscheck = {
        "overlap_matches": len(comparisons),
        "exact_matches": sum(row["match"] for row in comparisons),
        "differences": [row for row in comparisons if not row["match"]],
    }
    return sorted(output, key=lambda row: (int(row["edition"]), int(row["match_number"]), row["team_id"])), crosscheck


def _score_name(query: str, candidate: str) -> int:
    q_tokens, c_tokens = ascii_tokens(query), ascii_tokens(candidate)
    if not q_tokens or not c_tokens:
        return 0
    if name_key(query) == name_key(candidate):
        return 120
    if set(q_tokens) == set(c_tokens):
        return 115
    q_key, c_key = "".join(q_tokens), "".join(c_tokens)
    if q_key in c_key or c_key in q_key:
        return 105
    score = 0
    if q_tokens[-1] == c_tokens[-1]:
        score += 75
        initials = q_tokens[:-1]
        candidate_given = c_tokens[:-1]
        if initials and all(any(part.startswith(initial) for part in candidate_given) for initial in initials):
            score += 25
    common = set(q_tokens) & set(c_tokens)
    score += 10 * len(common)
    if len(q_tokens) == 1 and q_tokens[0] in c_tokens:
        score = max(score, 90)
    return score


def _fotmob_lineup(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text())
    result = {}
    for side in ("homeTeam", "awayTeam"):
        team = payload["content"]["lineup"][side]
        players = {}
        for role in ("starters", "subs"):
            for player in team.get(role, []) or []:
                players[str(player["id"])] = {**player, "role": role}
        result[team["name"]] = {"players": players, "source": payload}
    return result


def _map_2014_players(raw_root: Path, cards: list[dict]) -> tuple[dict[str, tuple[str, str]], dict[int, dict]]:
    lineups = {}
    for path in sorted((raw_root / "2014" / "fotmob" / "matches").glob("m*.json")):
        lineups[int(path.name[1:4])] = {"path": path, "teams": _fotmob_lineup(path)}
    observations: dict[str, list[tuple[int, str, str, int]]] = defaultdict(list)
    for card in [row for row in cards if int(row["edition"]) == 2014 and row["recipient_type"] == "player"]:
        number = int(card["match_number"])
        fotmob_team = FOTMOB_TEAM_ALIAS.get(card["team"], card["team"])
        players = lineups[number]["teams"][fotmob_team]["players"]
        ranked = sorted(
            ((_score_name(card["player"], player["name"]), pid, player["name"]) for pid, player in players.items()),
            reverse=True,
        )
        if ranked and ranked[0][0] >= 75 and (len(ranked) == 1 or ranked[0][0] > ranked[1][0]):
            score, pid, name = ranked[0]
            observations[card["player_id"]].append((number, pid, name, score))
    mapping: dict[str, tuple[str, str]] = {}
    for fifa_id, values in observations.items():
        by_id = Counter(pid for _, pid, _, _ in values)
        best_id, count = by_id.most_common(1)[0]
        if len(by_id) > 1 and count == by_id.most_common(2)[1][1]:
            raise ValueError(f"2014 player {fifa_id}: conflicting FotMob mappings {values}")
        best_name = max((name for _, pid, name, _ in values if pid == best_id), key=len)
        mapping[fifa_id] = (best_id, best_name)
    mapping.update(FIFA_FOTMOB_2014_OVERRIDES)
    expected = {row["player_id"] for row in cards if int(row["edition"]) == 2014 and row["recipient_type"] == "player"}
    missing = sorted(expected - set(mapping))
    if missing:
        details = [(row["player_id"], row["team"], row["player"]) for row in cards if row["player_id"] in missing]
        raise ValueError(f"2014 unresolved FIFA→FotMob player mappings: {details}")
    return mapping, lineups


def _status_from_workbook(value: str) -> str:
    text = (value or "").strip().lower()
    if text == "starter":
        return "starter"
    if text in {"used substitute", "substitute"}:
        return "used_substitute"
    if text in {"not used", "unused substitute"}:
        return "unused_substitute"
    if text == "absent":
        return "absent"
    raise ValueError(f"unknown lineup status: {value!r}")


def _sub_minute(substitution: dict) -> float:
    label = substitution.get("Minute") or ""
    parsed = re.match(r"^(\d+)'(?:\s*\+\s*(\d+)')?$", label.strip())
    if parsed:
        # Participation uses the nominal clock: a 45+4 substitution is at
        # nominal minute 45, while actual elapsed time remains available in
        # the card/event source for E_m.
        return float(parsed.group(1))
    # FIFA's 2026 feed uses blank labels at interval substitutions.
    interval_minute = {4: 45.0, 17: 90.0, 8: 105.0}.get(as_int(substitution.get("Period")))
    if interval_minute is None:
        raise ValueError(f"unresolved substitution minute: {substitution}")
    return interval_minute


def _build_player_matches(raw_root: Path, cards: list[dict], matches: list[dict]) -> tuple[list[dict], dict]:
    carded = {(int(row["edition"]), row["team_id"], row["player_id"])
              for row in cards if row["recipient_type"] == "player"}
    team_no = _team_match_numbers(matches)
    dismissals = {
        (int(row["edition"]), int(row["match_number"]), row["player_id"]):
            float(re.match(r"^(\d+)'", row["minute_label"]).group(1))
        for row in cards if row["recipient_type"] == "player" and row["card_type"] in {"R", "Y2"}
    }
    names: dict[tuple[int, str, str], str] = {}
    live_by_match = {}
    for match in matches:
        year, number = int(match["edition"]), int(match["match_number"])
        paths = list((raw_root / str(year) / "fifa" / "live").glob(f"m{number:03d}_*.json"))
        if len(paths) != 1:
            raise ValueError(f"{year} m{number:03d}: expected one FIFA live payload, found {len(paths)}")
        path = paths[0]
        payload = json.loads(path.read_text())
        live_by_match[(year, number)] = (payload, path)
        for side in ("HomeTeam", "AwayTeam"):
            team = payload[side]
            team_id = str(team["IdTeam"])
            for player in team.get("Players", []):
                player_id = str(player["IdPlayer"])
                names[(year, team_id, player_id)] = loc(player.get("PlayerName"))
    missing_names = sorted(carded - set(names))
    if missing_names:
        raise ValueError(f"carded FIFA players absent from every live roster: {missing_names}")

    output = []
    for match in matches:
        year, number, nominal = int(match["edition"]), int(match["match_number"]), int(match["nominal_minutes"])
        payload, path = live_by_match[(year, number)]
        for side_name, side, other in (("HomeTeam", "home", "away"), ("AwayTeam", "away", "home")):
            live_team = payload[side_name]
            team_id = str(live_team["IdTeam"])
            team_players = {(year, tid, pid) for y, tid, pid in carded if y == year and tid == team_id}
            roster = {str(player["IdPlayer"]): player for player in live_team.get("Players", [])}
            substitutions = live_team.get("Substitutions", []) or []
            on_map = {str(sub["IdPlayerOn"]): min(_sub_minute(sub), float(nominal))
                      for sub in substitutions if sub.get("IdPlayerOn")}
            off_map = {str(sub["IdPlayerOff"]): min(_sub_minute(sub), float(nominal))
                       for sub in substitutions if sub.get("IdPlayerOff")}
            source_url = (
                "https://api.fifa.com/api/v3/live/football/"
                f"{payload['IdCompetition']}/{payload['IdSeason']}/{payload['IdStage']}/{payload['IdMatch']}?language=en"
            )
            for _, _, player_id in sorted(team_players):
                player = roster.get(player_id)
                on = off = None
                played = 0.0
                if player is None:
                    status = "absent"
                elif as_int(player.get("Status")) == 1:
                    status, on, off = "starter", 0.0, off_map.get(player_id, float(nominal))
                elif player_id in on_map:
                    status, on, off = "used_substitute", on_map[player_id], off_map.get(player_id, float(nominal))
                else:
                    status = "unused_substitute"
                if on is not None and off is not None:
                    dismissal = dismissals.get((year, number, player_id))
                    if dismissal is not None:
                        off = min(off, dismissal)
                    played = max(0.0, off - on)
                output.append({
                    "edition": year, "match_number": number, "match_id": match["match_id"],
                    "stage": match["stage"], "team_id": team_id, "team": match[f"{side}_team"],
                    "opponent": match[f"{other}_team"], "team_match_number": team_no[(year, team_id, number)],
                    "player_id": player_id, "player": names[(year, team_id, player_id)],
                    "nominal_minutes": nominal, "lineup_status": status,
                    "on_minute": fmt(on, 3), "off_minute": fmt(off, 3), "played_minutes": fmt(played, 3),
                    "source_url": source_url, "source_archive": str(path.relative_to(raw_root.parent.parent)),
                })
    output.sort(key=lambda row: (
        int(row["edition"]), row["team_id"], row["player_id"], int(row["team_match_number"])
    ))

    # Draft workbook minutes were built from the same public endpoint. Keep a
    # comparison record, but never use workbook exposure formulas.
    primary = {(int(row["edition"]), row["match_id"], row["team_id"], row["player_id"]): row for row in output}
    comparison = {}
    for year in (2018, 2022, 2026):
        workbook_path = raw_root / "draft_workbook_exports" / str(year) / "player-match.csv"
        workbook_matches = _workbook_match_map(raw_root, year)
        compared = exact = 0
        differences = []
        for raw in read_csv(workbook_path):
            match_id = workbook_matches.get(as_int(raw["Match #"]) or -1, "")
            key = (year, match_id, str(as_int(raw["Team ID"]) or ""), str(as_int(raw["Player ID"]) or ""))
            if key not in primary:
                continue
            compared += 1
            old_minutes = as_float(raw.get("Played minutes"), 0.0) or 0.0
            new_minutes = float(primary[key]["played_minutes"] or 0)
            if abs(old_minutes - new_minutes) < 0.01:
                exact += 1
            elif len(differences) < 20:
                differences.append({"match_id": match_id, "player_id": key[3],
                                    "workbook": old_minutes, "fifa_live": new_minutes})
        comparison[year] = {"compared": compared, "exact": exact, "differences": differences}
    return output, comparison


def _evidence_tier(url: str) -> int:
    host = url.lower()
    if "fifa.com" in host or ".org/" in host and ("federation" in host or "club" in host):
        return 2
    if any(domain in host for domain in (
        "reuters.com", "espn.com", "time.com", "bbc.", "theguardian.com",
        "fourfourtwo.com", "lequipe.fr", "si.com", "sbs.com.au",
        "independent.co.uk", "goal.com", "eltiempo.com",
    )):
        return 3
    return 4


def _build_evidence(raw_root: Path, cards: list[dict], matches: list[dict]) -> list[dict]:
    match_lookup = {(int(row["edition"]), int(row["match_number"])): row for row in matches}
    match_id_lookup = {(int(row["edition"]), row["match_id"]): row for row in matches}
    carded = {(int(row["edition"]), row["team_id"], row["player_id"])
              for row in cards if row["recipient_type"] == "player"}
    output = []
    specs = ((2018, "medical-ledger.csv"), (2022, "medical-ledger.csv"), (2026, "injury-ledger.csv"))
    for year, filename in specs:
        path = raw_root / "draft_workbook_exports" / str(year) / filename
        workbook_matches = _workbook_match_map(raw_root, year)
        for raw in read_csv(path):
            display_number = as_int(raw["Match #"])
            team_id = str(as_int(raw["Team ID"]) or "")
            player_id = str(as_int(raw["Player ID"]) or "")
            corrected_number = MEDICAL_MATCH_NUMBER_OVERRIDES.get(
                (year, display_number or -1, team_id, player_id)
            )
            if corrected_number is not None:
                match = match_lookup.get((year, corrected_number))
            else:
                match_id = workbook_matches.get(display_number or -1, "")
                match = match_id_lookup.get((year, match_id))
            if match is None:
                continue
            number = int(match["match_number"])
            sides = {
                match["home_team_id"]: match["home_team"],
                match["away_team_id"]: match["away_team"],
            }
            if team_id not in sides:
                raise ValueError(
                    f"{year} medical ledger joins {team_id} to unrelated M{number}; "
                    "add an audited match-number correction"
                )
            if (year, team_id, player_id) not in carded:
                continue
            unavailable = as_float(raw["Unavailable minutes"], 0.0) or 0.0
            source_url = (raw.get("Source URL") or "").strip()
            source_override = MEDICAL_SOURCE_OVERRIDES.get((year, number, team_id, player_id))
            evidence_note = raw.get("Evidence", "").strip()
            if source_override:
                source_url, evidence_note = source_override
            if unavailable <= 0:
                continue
            if not source_url:
                raise ValueError(f"{year} m{number:03d} {player_id}: positive injury interval without URL")
            start, end = as_float(raw["Start"], 0.0), as_float(raw["End"])
            if start is None or end is None or not 0 <= start < end <= float(match["nominal_minutes"]):
                raise ValueError(f"{year} M{number} {player_id}: invalid injury interval")
            status = "injured_full_match" if start == 0 and end == float(match["nominal_minutes"]) else "injured_interval"
            output.append({
                "edition": year, "match_number": number, "match_id": match["match_id"],
                "stage": match["stage"], "team_id": team_id, "team": sides[team_id],
                "player_id": player_id, "player": raw["Player"], "status": status,
                "start_minute": fmt(start, 3), "end_minute": fmt(end, 3),
                "unavailable_minutes": fmt(unavailable, 3), "evidence_tier": _evidence_tier(source_url),
                "evidence_note": evidence_note, "source_url": source_url,
                "source_archive": str(path.relative_to(raw_root.parent.parent)),
            })

    # The pre-freeze workbooks did not include 2014. Keep manually researched
    # intervals in one raw ledger, then normalize them through the same schema
    # and validation path as the workbook-derived evidence.
    manual_path = raw_root / "manual" / "availability-evidence.csv"
    seen = {
        (
            int(row["edition"]), int(row["match_number"]), row["team_id"], row["player_id"],
            float(row["start_minute"]), float(row["end_minute"]),
        )
        for row in output
    }
    if manual_path.exists():
        for raw in read_csv(manual_path):
            year = as_int(raw.get("edition"))
            number = as_int(raw.get("match_number"))
            team_id = str(as_int(raw.get("team_id")) or "")
            player_id = str(as_int(raw.get("player_id")) or "")
            if year not in EDITIONS or number is None:
                raise ValueError(f"invalid manual availability edition/match: {raw}")
            match = match_lookup.get((year, number))
            if match is None:
                raise ValueError(f"manual availability refers to excluded match: {year} M{number}")
            sides = {
                match["home_team_id"]: match["home_team"],
                match["away_team_id"]: match["away_team"],
            }
            if team_id not in sides:
                raise ValueError(f"manual availability team not in match: {year} M{number} {team_id}")
            if (year, team_id, player_id) not in carded:
                raise ValueError(f"manual availability player is outside carded cohort: {raw}")
            start = as_float(raw.get("start_minute"))
            end = as_float(raw.get("end_minute"))
            nominal = float(match["nominal_minutes"])
            if start is None or end is None or not 0 <= start < end <= nominal:
                raise ValueError(f"invalid manual availability interval: {raw}")
            source_url = (raw.get("source_url") or "").strip()
            if not source_url:
                raise ValueError(f"positive manual availability interval lacks URL: {raw}")
            key = (year, number, team_id, player_id, start, end)
            if key in seen:
                raise ValueError(f"duplicate availability interval: {key}")
            seen.add(key)
            output.append({
                "edition": year, "match_number": number, "match_id": match["match_id"],
                "stage": match["stage"], "team_id": team_id, "team": sides[team_id],
                "player_id": player_id, "player": raw["player"], "status": raw["status"],
                "start_minute": fmt(start, 3), "end_minute": fmt(end, 3),
                "unavailable_minutes": fmt(end - start, 3),
                "evidence_tier": _evidence_tier(source_url),
                "evidence_note": raw.get("evidence_note", "").strip(),
                "source_url": source_url,
                "source_archive": str(manual_path.relative_to(raw_root.parent.parent)),
            })
    return sorted(output, key=lambda row: (
        int(row["edition"]), int(row["match_number"]), row["team_id"], row["player_id"]
    ))


def _build_sanction_decisions(
    raw_root: Path, cards: list[dict], matches: list[dict], player_matches: list[dict]
) -> list[dict]:
    """Normalize sourced disciplinary decisions that modify automatic bans."""
    path = raw_root / "manual" / "sanction-decisions.csv"
    if not path.exists():
        return []
    card_lookup = {
        row["card_id"]: row for row in cards if row["recipient_type"] == "player"
    }
    carded = {
        (int(row["edition"]), row["team_id"], row["player_id"])
        for row in cards if row["recipient_type"] == "player"
    }
    team_matches: dict[tuple[int, str], dict[int, dict]] = defaultdict(dict)
    for match in matches:
        year = int(match["edition"])
        number = int(match["match_number"])
        team_matches[(year, match["home_team_id"])][number] = match
        team_matches[(year, match["away_team_id"])][number] = match
    participation_keys = {
        (int(row["edition"]), row["team_id"], row["player_id"], int(row["match_number"]))
        for row in player_matches
    }
    allowed_types = {"carry_in_suspension", "extended_suspension", "deferred_suspension"}
    allowed_statuses = {"served", "deferred", "pending"}
    output = []
    seen_trigger_cards = set()
    for raw in read_csv(path):
        year = as_int(raw.get("edition"))
        team_id = str(as_int(raw.get("team_id")) or "")
        player_id = str(as_int(raw.get("player_id")) or "")
        trigger_card_id = (raw.get("trigger_card_id") or "").strip()
        decision_type = (raw.get("decision_type") or "").strip()
        decision_status = (raw.get("decision_status") or "").strip()
        source_url = (raw.get("source_url") or "").strip()
        if year not in EDITIONS or (year, team_id, player_id) not in carded:
            raise ValueError(f"sanction decision player is outside carded cohort: {raw}")
        if decision_type not in allowed_types or decision_status not in allowed_statuses:
            raise ValueError(f"invalid sanction decision type/status: {raw}")
        if not source_url:
            raise ValueError(f"sanction decision lacks source URL: {raw}")
        if trigger_card_id:
            if trigger_card_id in seen_trigger_cards:
                raise ValueError(f"duplicate sanction decision trigger: {trigger_card_id}")
            seen_trigger_cards.add(trigger_card_id)
            trigger = card_lookup.get(trigger_card_id)
            if trigger is None or (
                int(trigger["edition"]), trigger["team_id"], trigger["player_id"]
            ) != (year, team_id, player_id):
                raise ValueError(f"sanction trigger does not match player: {raw}")
        service_numbers = [
            int(value) for value in (raw.get("service_match_numbers") or "").split("|") if value
        ]
        if not service_numbers:
            raise ValueError(f"sanction decision has no service match: {raw}")
        if len(service_numbers) != len(set(service_numbers)):
            raise ValueError(f"duplicate sanction service match: {raw}")
        games = team_matches.get((year, team_id), {})
        if any(number not in games for number in service_numbers):
            raise ValueError(f"sanction service match is outside team schedule: {raw}")
        if any((year, team_id, player_id, number) not in participation_keys for number in service_numbers):
            raise ValueError(f"sanction service match lacks lineup observation: {raw}")
        first_match = games[service_numbers[0]]
        team = (
            first_match["home_team"]
            if first_match["home_team_id"] == team_id else first_match["away_team"]
        )
        tier = as_int(raw.get("evidence_tier"))
        if tier is None or tier not in {1, 2, 3, 4}:
            raise ValueError(f"invalid sanction evidence tier: {raw}")
        output.append({
            "edition": year, "team_id": team_id, "team": team,
            "player_id": player_id, "player": raw["player"],
            "trigger_card_id": trigger_card_id, "decision_type": decision_type,
            "service_match_numbers": "|".join(str(number) for number in service_numbers),
            "decision_status": decision_status, "evidence_tier": tier,
            "evidence_note": raw.get("evidence_note", "").strip(),
            "source_url": source_url,
            "source_archive": str(path.relative_to(raw_root.parent.parent)),
        })
    return sorted(output, key=lambda row: (
        int(row["edition"]), row["team_id"], row["player_id"], row["decision_type"]
    ))


def _timeline_foul_events(timelines, year: int) -> int:
    return sum(1 for (event_year, _), events in timelines.items() if event_year == year
               for event in events if event.get("Type") == 18)


def _validate(
    cards, fouls, player_matches, evidence, sanction_decisions, timelines,
    foul_crosscheck, participation_crosscheck,
) -> list[dict]:
    audit = []
    participation_keys = {
        (int(row["edition"]), row["match_id"], row["team_id"], row["player_id"])
        for row in player_matches
    }
    for year in EDITIONS:
        player_cards = sum(1 for row in cards if int(row["edition"]) == year and row["recipient_type"] == "player")
        foul_rows = sum(1 for row in fouls if int(row["edition"]) == year)
        checks = (
            ("player_card_count", player_cards, EXPECTED_PLAYER_CARDS[year], "frozen card census"),
            ("team_match_foul_rows", foul_rows, EXPECTED_TEAM_MATCH_ROWS[year], "two rows per included match"),
        )
        for check, observed, expected, note in checks:
            status = "PASS" if observed == expected else "FAIL"
            audit.append({"edition": year, "check": check, "observed": observed, "expected": expected,
                          "status": status, "note": note})
            if status == "FAIL":
                raise ValueError(f"{year} {check}: {observed}, expected {expected}")
        event_count = _timeline_foul_events(timelines, year)
        table_total = sum(int(row["fouls"]) for row in fouls if int(row["edition"]) == year)
        audit.append({
            "edition": year, "check": "foul_event_vs_team_stat_layers", "observed": event_count,
            "expected": table_total, "status": "AUDIT", "note": "event and team-stat layers are retained separately",
        })
        exposed = {(row["team_id"], row["player_id"]) for row in cards
                   if int(row["edition"]) == year and row["recipient_type"] == "player"}
        covered = {(row["team_id"], row["player_id"]) for row in player_matches if int(row["edition"]) == year}
        missing = exposed - covered
        audit.append({
            "edition": year, "check": "carded_player_participation_coverage", "observed": len(exposed - missing),
            "expected": len(exposed), "status": "PASS" if not missing else "FAIL",
            "note": "all carded players have tournament participation rows",
        })
        if missing:
            raise ValueError(f"{year}: missing player-match coverage {sorted(missing)}")
        if year in participation_crosscheck:
            comparison = participation_crosscheck[year]
            audit.append({
                "edition": year,
                "check": "fifa_live_vs_draft_player_minutes",
                "observed": comparison["exact"],
                "expected": comparison["compared"],
                "status": "PASS" if comparison["exact"] == comparison["compared"] else "AUDIT",
                "note": "FIFA live is primary; sample differences=" + json.dumps(
                    comparison["differences"], ensure_ascii=False, separators=(",", ":")
                ),
            })
    for row in evidence:
        if float(row["unavailable_minutes"]) > 0 and not row["source_url"]:
            raise ValueError(f"positive injury interval lacks source: {row}")
        key = (int(row["edition"]), row["match_id"], row["team_id"], row["player_id"])
        if key not in participation_keys:
            raise ValueError(f"availability evidence lacks matching participation row: {row}")
    audit.append({
        "edition": "all", "check": "availability_evidence_participation_join",
        "observed": len(evidence), "expected": len(evidence), "status": "PASS",
        "note": "Every evidence row joins to the same player, team, and official match.",
    })
    audit.append({
        "edition": 2018, "check": "medical_match_number_corrections",
        "observed": len(MEDICAL_MATCH_NUMBER_OVERRIDES), "expected": 5, "status": "PASS",
        "note": "Explicit correction map for five pre-freeze ledger fixture-number errors.",
    })
    for row in sanction_decisions:
        if not row["source_url"]:
            raise ValueError(f"sanction decision lacks source: {row}")
    audit.append({
        "edition": "all", "check": "documented_sanction_decisions",
        "observed": len(sanction_decisions), "expected": len(sanction_decisions),
        "status": "PASS", "note": "Every override retains a public decision source URL.",
    })
    audit.append({
        "edition": 2014,
        "check": "huffpost_opta_vs_fotmob_foul_overlap",
        "observed": foul_crosscheck["exact_matches"],
        "expected": foul_crosscheck["overlap_matches"],
        "status": "AUDIT" if foul_crosscheck["differences"] else "PASS",
        "note": "complete HuffPost/Opta layer retained; differences=" + json.dumps(
            foul_crosscheck["differences"], ensure_ascii=False, separators=(",", ":")
        ),
    })
    if any(int(row["edition"]) == 2026 and int(row["match_number"]) > 100 for table in (cards, fouls, player_matches, evidence) for row in table):
        raise ValueError("2026 cutoff violation: source table contains M101-M104")
    if any(
        int(row["edition"]) == 2026
        and any(int(number) > 100 for number in row["service_match_numbers"].split("|") if number)
        for row in sanction_decisions
    ):
        raise ValueError("2026 cutoff violation: sanction decision contains M101-M104")
    return audit


def build_sources(raw_root: Path = RAW, output_dir: Path = SOURCE) -> dict[str, int]:
    calendars = _load_calendars(raw_root)
    timelines, timeline_paths = _load_timelines(raw_root, calendars)
    matches = _build_matches(raw_root, calendars, timelines, timeline_paths)
    cards = _build_cards(raw_root, calendars, timelines, timeline_paths, matches)
    fouls, foul_crosscheck = _build_fouls(raw_root, matches)
    player_matches, participation_crosscheck = _build_player_matches(raw_root, cards, matches)
    evidence = _build_evidence(raw_root, cards, matches)
    sanction_decisions = _build_sanction_decisions(raw_root, cards, matches, player_matches)
    audit = _validate(
        cards, fouls, player_matches, evidence, sanction_decisions, timelines,
        foul_crosscheck, participation_crosscheck,
    )
    write_csv(output_dir / "matches.csv", matches, MATCH_FIELDS)
    write_csv(output_dir / "cards.csv", cards, CARD_FIELDS)
    write_csv(output_dir / "fouls_team_match.csv", fouls, FOUL_FIELDS)
    write_csv(output_dir / "player_match.csv", player_matches, PLAYER_MATCH_FIELDS)
    write_csv(output_dir / "availability_evidence.csv", evidence, EVIDENCE_FIELDS)
    write_csv(output_dir / "sanction_decisions.csv", sanction_decisions, SANCTION_DECISION_FIELDS)
    write_csv(output_dir / "source_audit.csv", audit, AUDIT_FIELDS)
    return {
        "matches": len(matches), "cards": len(cards), "fouls": len(fouls),
        "player_match": len(player_matches), "availability_evidence": len(evidence),
        "sanction_decisions": len(sanction_decisions),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, default=RAW)
    parser.add_argument("--output", type=Path, default=SOURCE)
    args = parser.parse_args()
    counts = build_sources(args.raw_root.resolve(), args.output.resolve())
    print("normalized source tables:", ", ".join(f"{key}={value}" for key, value in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
