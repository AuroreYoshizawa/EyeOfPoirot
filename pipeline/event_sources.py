"""Normalize event-order inputs without crossing the public/private boundary.

The private archive contains provider-native event identifiers and complete
event streams.  Public builds need only project-authored segment aggregates
and cumulative counts.  This module performs that reduction during a raw
owner build and writes the identifier-bearing reconciliation to an ignored
private sidecar.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

# Keep the schemas narrow and explicit.  In particular, no provider-native
# match/event identifier, sequence index, order key, or linked-event reference
# is permitted in these public tables.
FOUL_EVENT_SEGMENT_FIELDS = (
    "edition", "edition_status", "match_number", "stage", "team_id", "team",
    "segment", "foul_events", "provider", "feed_status", "source_url",
)
CARD_EVENT_ORDER_FIELDS = (
    "edition", "edition_status", "card_id", "provider",
    "reconciliation_status", "fouls_strictly_before_card", "foul_linked",
    "fouls_through_card", "provenance_status", "source_url",
)
TEAM_MATCH_CARD_ORDER_FIELDS = (
    "edition", "edition_status", "match_number", "stage", "team_id", "team",
    "provider", "has_in_play_player_card", "first_card_id",
    "fouls_before_first_card", "status", "source_url",
)
TEAM_OUTCOME_FIELDS = (
    "edition", "edition_status", "match_number", "stage", "team_id", "team",
    "goals_for", "goals_against", "source_url",
)

PRIVATE_CARD_ORDER_FIELDS = (
    "edition", "project_match_number", "project_card_id", "project_team_id",
    "provider", "provider_match_id", "provider_event_id",
    "provider_sequence_index", "provider_event_order_key",
    "provider_linked_event_reference", "provider_event_type",
    "fouls_strictly_before_card", "foul_linked", "fouls_through_card",
)

SEGMENTS = (
    "00_0_15", "01_15_30", "02_30_half_time", "03_45_60",
    "04_60_75", "05_75_full_time", "06_extra_time_1", "07_extra_time_2",
)

STATSBOMB_URL = "https://github.com/statsbomb/open-data"
FIFA_URLS = {
    2014: "https://www.fifa.com/tournaments/mens/worldcup/2014brazil",
    2018: "https://www.fifa.com/tournaments/mens/worldcup/2018russia",
    2022: "https://www.fifa.com/tournaments/mens/worldcup/qatar2022",
    2026: "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026",
}

STATSBOMB_MATCH_FILES = {
    2018: Path("card-reason-audit/pages/2018/statsbomb-matches-43-3.json"),
    2022: Path("card-reason-audit/pages/2022/statsbomb/matches_2022.json"),
}


def _normalize(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value or "")
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", plain.lower()))


# FIFA's public display aliases and StatsBomb's player names occasionally
# share no literal token.  These reviewed identity equivalences make those
# joins explicit; event clocks are never used as a name-free fallback.
STATSBOMB_PLAYER_NAME_ALIASES = {
    "taiseer": "Taisir Jabir Al Jassim",
    "casemiro": "Carlos Henrique Casimiro",
    "m treziguet": "Mahmoud Ibrahim Hassan",
    "a fathi": "Ahmed Fathy Abdel Meneim Ibrahim",
    "el kajoui": "Munir Mohand Mohamedi",
    "mikel": "John Michael Nchekwube Obinna",
    "hallfredsson": "Emil Hallfreðsson",
    "chaaleli": "Ghilane Chalali",
    "fernandinho": "Fernando Luiz Roza",
    "gazinskii": "Yury Gazinskiy",
    "al abed": "Nawaf Shaker Al Abid",
    "mohammed": "Ismaeel Mohammad Mohammad",
    "fred": "Frederico Rodrigues Santos",
    "hatan": "Hattan Babhir",
    "marquinhos": "Marcos Aoás Corrêa",
    "vitinha": "Vitor Machado Ferreira",
}


def _team_key(value: str) -> str:
    normalized = _normalize(value)
    return {
        "south korea": "korea republic",
        "united states of america": "united states",
    }.get(normalized, normalized)


def _parse_minute(label: str | None) -> float | None:
    if not label:
        return None
    match = re.match(r"^(\d+)'(?:\s*\+\s*(\d+)')?$", label.strip())
    if not match:
        return None
    return float(int(match.group(1)) + int(match.group(2) or 0))


def _timestamp_seconds(value: str) -> float:
    """Convert a StatsBomb period-local timestamp to a sortable scalar."""
    match = re.match(r"^(\d+):(\d+):(\d+(?:\.\d+)?)$", value or "")
    if not match:
        raise ValueError(f"invalid provider event timestamp: {value!r}")
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))


def _segment(period: int, minute: float, *, provider: str) -> str | None:
    if provider == "statsbomb":
        if period == 1:
            return SEGMENTS[0] if minute < 15 else SEGMENTS[1] if minute < 30 else SEGMENTS[2]
        if period == 2:
            return SEGMENTS[3] if minute < 60 else SEGMENTS[4] if minute < 75 else SEGMENTS[5]
        if period == 3:
            return SEGMENTS[6]
        if period == 4:
            return SEGMENTS[7]
        return None
    if provider == "fifa":
        if period == 3:
            return SEGMENTS[0] if minute < 15 else SEGMENTS[1] if minute < 30 else SEGMENTS[2]
        if period == 5:
            return SEGMENTS[3] if minute < 60 else SEGMENTS[4] if minute < 75 else SEGMENTS[5]
        if period == 7:
            return SEGMENTS[6]
        if period == 9:
            return SEGMENTS[7]
        return None
    raise ValueError(f"unknown event provider: {provider}")


def _edition_status(edition: int) -> str:
    return "provisional_M100" if edition == 2026 else "final"


def _statsbomb_card(event: dict) -> tuple[str, str] | None:
    event_type = event.get("type", {}).get("name")
    if event_type == "Foul Committed":
        card = event.get("foul_committed", {}).get("card")
        linkage = "true"
    elif event_type == "Bad Behaviour":
        card = event.get("bad_behaviour", {}).get("card")
        linkage = "false"
    else:
        return None
    if not card:
        return None
    return card.get("name", ""), linkage


def _expected_statsbomb_card(card_type: str) -> str:
    return {"Y": "Yellow Card", "Y2": "Second Yellow", "R": "Red Card"}[card_type]


def _player_name_match(project_name: str, provider_name: str) -> tuple[bool, int]:
    """Return an audited identity match and a literal-overlap strength."""
    project = _normalize(project_name)
    provider = _normalize(provider_name)
    project_tokens = [token for token in project.split() if len(token) >= 3]
    provider_tokens = provider.split()
    provider_compact = "".join(provider_tokens)
    overlap = sum(
        token in provider_tokens or token in provider_compact
        for token in project_tokens
    )
    alias = STATSBOMB_PLAYER_NAME_ALIASES.get(project)
    alias_match = alias is not None and _normalize(alias) == provider
    return overlap > 0 or alias_match, overlap


def _statsbomb_match_map(
    raw_root: Path, edition: int, matches: list[dict]
) -> tuple[dict[int, int], dict[int, dict]]:
    project = {
        int(row["match_number"]): row
        for row in matches if int(row["edition"]) == edition
    }
    project_lookup = {
        (
            row["date_utc"][:10],
            frozenset({_team_key(row["home_team"]), _team_key(row["away_team"])}),
        ): number
        for number, row in project.items()
    }
    path = raw_root / STATSBOMB_MATCH_FILES[edition]
    provider_matches = json.loads(path.read_text(encoding="utf-8"))
    number_by_provider_id: dict[int, int] = {}
    metadata_by_number: dict[int, dict] = {}
    for provider_match in provider_matches:
        key = (
            provider_match["match_date"],
            frozenset({
                _team_key(provider_match["home_team"]["home_team_name"]),
                _team_key(provider_match["away_team"]["away_team_name"]),
            }),
        )
        if key not in project_lookup:
            raise ValueError(f"StatsBomb match cannot be joined to project census: {key}")
        number = project_lookup[key]
        provider_id = int(provider_match["match_id"])
        if provider_id in number_by_provider_id or number in metadata_by_number:
            raise ValueError(f"duplicate StatsBomb match join: {edition} M{number}")
        number_by_provider_id[provider_id] = number
        metadata_by_number[number] = provider_match
    if set(metadata_by_number) != set(project):
        raise ValueError(
            f"{edition} StatsBomb match coverage differs from project census: "
            f"missing={sorted(set(project) - set(metadata_by_number))}"
        )
    return number_by_provider_id, metadata_by_number


def _statsbomb_event_path(raw_root: Path, edition: int, provider_match_id: int) -> Path:
    if edition == 2018:
        return (
            raw_root / "card-reason-audit" / "pages" / "2018"
            / f"statsbomb-events-{provider_match_id}.json"
        )
    return (
        raw_root / "card-reason-audit" / "pages" / "2022" / "statsbomb"
        / f"{provider_match_id}-events.json"
    )


def _event_team_ids(match: dict, provider_match: dict) -> dict[str, str]:
    project_by_name = {
        _team_key(match["home_team"]): match["home_team_id"],
        _team_key(match["away_team"]): match["away_team_id"],
    }
    result = {}
    for side in ("home", "away"):
        provider_name = provider_match[f"{side}_team"][f"{side}_team_name"]
        key = _team_key(provider_name)
        if key not in project_by_name:
            raise ValueError(
                f"provider team cannot be joined to project IDs: {provider_name!r}"
            )
        result[key] = project_by_name[key]
    return result


def _match_statsbomb_cards(
    edition: int,
    matches: list[dict],
    cards: list[dict],
    reasons: dict[str, dict],
    events_by_number: dict[int, list[dict]],
    provider_matches: dict[int, dict],
) -> dict[str, dict]:
    """Join provider card events using team, type, linkage, name, and clock.

    FIFA display names occasionally use a short alias that shares no literal
    token with the provider's full legal name.  Those identities are listed
    explicitly above.  There is no minute-only cross-source fallback.
    """
    project_matches = {
        int(row["match_number"]): row
        for row in matches if int(row["edition"]) == edition
    }
    output: dict[str, dict] = {}
    for number, match in sorted(project_matches.items()):
        provider_team_ids = _event_team_ids(match, provider_matches[number])
        provider_cards = [
            event for event in events_by_number[number]
            if _statsbomb_card(event) is not None
        ]
        used: set[str] = set()
        project_cards = sorted(
            (
                row for row in cards
                if int(row["edition"]) == edition
                and int(row["match_number"]) == number
                and row["recipient_type"] == "player"
                and row["event_scope"] == "in_play"
                and reasons[row["card_id"]]["sb_foul_linked"] != "unmatched"
            ),
            key=lambda row: (float(row["t_min"]), row["card_id"]),
        )
        for card in project_cards:
            status = reasons[card["card_id"]]["sb_foul_linked"]
            expected_link = {"yes": "true", "no": "false"}[status]
            candidates = []
            for event in provider_cards:
                if event["id"] in used:
                    continue
                provider_card, foul_linked = _statsbomb_card(event) or ("", "")
                provider_team = _team_key(event.get("team", {}).get("name", ""))
                if (
                    provider_card != _expected_statsbomb_card(card["card_type"])
                    or foul_linked != expected_link
                    or provider_team_ids.get(provider_team) != card["team_id"]
                ):
                    continue
                name_match, overlap = _player_name_match(
                    card["player"], event.get("player", {}).get("name", "")
                )
                if not name_match:
                    continue
                minute_distance = abs(int(event["minute"]) + 1 - float(card["t_min"]))
                candidates.append((overlap, minute_distance, int(event["index"]), event))
            if not candidates:
                raise ValueError(
                    f"no audited StatsBomb card join for {card['card_id']}: "
                    "identity/team/type/linkage match unavailable"
                )
            ranked = sorted(candidates, key=lambda item: (-item[0], item[1], item[2]))
            best_quality = (ranked[0][0], ranked[0][1])
            if sum((item[0], item[1]) == best_quality for item in ranked) != 1:
                raise ValueError(
                    f"ambiguous audited StatsBomb card join for {card['card_id']}"
                )
            _, _, _, event = ranked[0]
            used.add(event["id"])
            output[card["card_id"]] = event
    expected = {
        row["card_id"]
        for row in cards
        if int(row["edition"]) == edition
        and row["recipient_type"] == "player"
        and row["event_scope"] == "in_play"
        and reasons[row["card_id"]]["sb_foul_linked"] in {"yes", "no"}
    }
    if set(output) != expected:
        raise ValueError(
            f"{edition} StatsBomb card joins differ from audited matched set: "
            f"missing={sorted(expected - set(output))[:10]} "
            f"extra={sorted(set(output) - expected)[:10]}"
        )
    return output


def _read_statsbomb(
    raw_root: Path, edition: int, matches: list[dict]
) -> tuple[dict[int, int], dict[int, dict], dict[int, list[dict]]]:
    number_by_provider_id, provider_matches = _statsbomb_match_map(
        raw_root, edition, matches
    )
    events_by_number = {}
    for provider_id, number in sorted(number_by_provider_id.items(), key=lambda item: item[1]):
        path = _statsbomb_event_path(raw_root, edition, provider_id)
        events = json.loads(path.read_text(encoding="utf-8"))
        triples = [
            (int(event["period"]), _timestamp_seconds(event["timestamp"]), int(event["index"]))
            for event in events
        ]
        if len(triples) != len(set(triples)):
            raise ValueError(
                f"{edition} M{number}: duplicate provider period/clock/index triple"
            )
        events_by_number[number] = events
    return number_by_provider_id, provider_matches, events_by_number


def _fifa_timeline_paths(raw_root: Path, edition: int, matches: list[dict]) -> dict[int, Path]:
    expected = {
        int(row["match_number"])
        for row in matches if int(row["edition"]) == edition
    }
    result = {}
    for path in sorted((raw_root / str(edition) / "fifa" / "timelines").glob("m*.json")):
        number = int(path.name[1:4])
        if number in expected:
            if number in result:
                raise ValueError(f"duplicate FIFA timeline for {edition} M{number}")
            result[number] = path
    if set(result) != expected:
        raise ValueError(
            f"{edition} FIFA timeline coverage differs from match census: "
            f"missing={sorted(expected - set(result))}"
        )
    return result


def _public_segment_rows(
    matches: list[dict], segment_counts: dict[tuple[int, int, str, str], int]
) -> list[dict]:
    output = []
    for match in sorted(matches, key=lambda row: (int(row["edition"]), int(row["match_number"]))):
        edition = int(match["edition"])
        if edition not in {2018, 2022, 2026}:
            continue
        provider = "StatsBomb open data" if edition in {2018, 2022} else "FIFA timeline"
        source_url = STATSBOMB_URL if edition in {2018, 2022} else FIFA_URLS[2026]
        for side in ("home", "away"):
            team_id = match[f"{side}_team_id"]
            team = match[f"{side}_team"]
            for segment in SEGMENTS:
                output.append({
                    "edition": edition,
                    "edition_status": _edition_status(edition),
                    "match_number": int(match["match_number"]),
                    "stage": match["stage"],
                    "team_id": team_id,
                    "team": team,
                    "segment": segment,
                    "foul_events": segment_counts[(edition, int(match["match_number"]), team_id, segment)],
                    "provider": provider,
                    "feed_status": "complete_with_known_undercount" if edition == 2026 else "complete",
                    "source_url": source_url,
                })
    return output


def _write_private_sidecar(raw_root: Path, rows: list[dict]) -> Path:
    path = raw_root / "expanded-cohort" / "card-event-order-private.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=PRIVATE_CARD_ORDER_FIELDS,
            lineterminator="\n", extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def _team_outcomes(raw_root: Path, matches: list[dict]) -> list[dict]:
    project = {
        (int(row["edition"]), int(row["match_number"])): row for row in matches
    }
    output = []
    for edition in sorted({int(row["edition"]) for row in matches}):
        payload = json.loads(
            (raw_root / str(edition) / "fifa" / "calendar.json").read_text(encoding="utf-8")
        )
        calendar = {
            int(item["MatchNumber"]): item for item in payload["Results"]
            if (edition != 2026 or int(item["MatchNumber"]) <= 100)
        }
        for number in sorted(
            number for year, number in project if year == edition
        ):
            match = project[(edition, number)]
            item = calendar[number]
            home_goals = int(item["HomeTeamScore"])
            away_goals = int(item["AwayTeamScore"])
            for side, goals_for, goals_against in (
                ("home", home_goals, away_goals),
                ("away", away_goals, home_goals),
            ):
                output.append({
                    "edition": edition,
                    "edition_status": _edition_status(edition),
                    "match_number": number,
                    "stage": match["stage"],
                    "team_id": match[f"{side}_team_id"],
                    "team": match[f"{side}_team"],
                    "goals_for": goals_for,
                    "goals_against": goals_against,
                    "source_url": FIFA_URLS[edition],
                })
    return output


def build_event_sources(
    raw_root: Path,
    matches: list[dict],
    cards: list[dict],
    card_reasons: list[dict],
) -> dict[str, list[dict]]:
    """Return public reductions and update the private order-audit sidecar."""
    reasons = {row["card_id"]: row for row in card_reasons}
    match_lookup = {
        (int(row["edition"]), int(row["match_number"])): row for row in matches
    }
    segment_counts: dict[tuple[int, int, str, str], int] = defaultdict(int)
    public_by_card: dict[str, dict] = {}
    internal_card_order: dict[str, tuple[int, float, int]] = {}
    private_rows: list[dict] = []

    # 2018/2022: StatsBomb event order and provider-native foul linkage.
    for edition in (2018, 2022):
        number_by_provider_id, provider_matches, events_by_number = _read_statsbomb(
            raw_root, edition, matches
        )
        provider_id_by_number = {
            number: provider_id for provider_id, number in number_by_provider_id.items()
        }
        matched = _match_statsbomb_cards(
            edition, matches, cards, reasons, events_by_number, provider_matches
        )
        project_matches = {
            int(row["match_number"]): row
            for row in matches if int(row["edition"]) == edition
        }
        for number, events in sorted(events_by_number.items()):
            match = project_matches[number]
            provider_team_ids = _event_team_ids(match, provider_matches[number])
            order = {
                event["id"]: (
                    int(event["period"]), _timestamp_seconds(event["timestamp"]), int(event["index"])
                )
                for event in events
            }
            fouls_by_team: dict[str, list[dict]] = defaultdict(list)
            for event in events:
                if event.get("type", {}).get("name") != "Foul Committed":
                    continue
                provider_team = _team_key(event.get("team", {}).get("name", ""))
                team_id = provider_team_ids.get(provider_team)
                if team_id is None:
                    raise ValueError(
                        f"{edition} M{number}: foul team is outside project match: {provider_team}"
                    )
                segment = _segment(
                    int(event["period"]), float(event["minute"]), provider="statsbomb"
                )
                if segment is None:
                    continue
                segment_counts[(edition, number, team_id, segment)] += 1
                fouls_by_team[team_id].append(event)

            for card in (
                row for row in cards
                if int(row["edition"]) == edition
                and int(row["match_number"]) == number
                and row["recipient_type"] == "player"
                and row["event_scope"] == "in_play"
            ):
                status = reasons[card["card_id"]]["sb_foul_linked"]
                if status == "unmatched":
                    public_by_card[card["card_id"]] = {
                        "edition": edition,
                        "edition_status": _edition_status(edition),
                        "card_id": card["card_id"],
                        "provider": "StatsBomb open data",
                        "reconciliation_status": "unmatched",
                        "fouls_strictly_before_card": "",
                        "foul_linked": "",
                        "fouls_through_card": "",
                        "provenance_status": "provider_card_unmatched",
                        "source_url": STATSBOMB_URL,
                    }
                    continue
                event = matched[card["card_id"]]
                card_order = order[event["id"]]
                internal_card_order[card["card_id"]] = card_order
                strict = sum(
                    order[foul["id"]] < card_order
                    for foul in fouls_by_team[card["team_id"]]
                )
                foul_linked = event.get("type", {}).get("name") == "Foul Committed"
                through = strict + (1 if foul_linked else 0)
                public_by_card[card["card_id"]] = {
                    "edition": edition,
                    "edition_status": _edition_status(edition),
                    "card_id": card["card_id"],
                    "provider": "StatsBomb open data",
                    "reconciliation_status": "matched",
                    "fouls_strictly_before_card": strict,
                    "foul_linked": "true" if foul_linked else "false",
                    "fouls_through_card": through,
                    "provenance_status": "provider_card_matched_and_ordered",
                    "source_url": STATSBOMB_URL,
                }
                private_rows.append({
                    "edition": edition,
                    "project_match_number": number,
                    "project_card_id": card["card_id"],
                    "project_team_id": card["team_id"],
                    "provider": "StatsBomb open data",
                    "provider_match_id": provider_id_by_number[number],
                    "provider_event_id": event["id"],
                    "provider_sequence_index": event["index"],
                    "provider_event_order_key": "|".join(map(str, card_order)),
                    "provider_linked_event_reference": event["id"] if foul_linked else "",
                    "provider_event_type": event.get("type", {}).get("name", ""),
                    "fouls_strictly_before_card": strict,
                    "foul_linked": "true" if foul_linked else "false",
                    "fouls_through_card": through,
                })

    # 2026: FIFA cards and fouls share the same ordered timeline.  FIFA does
    # not publish a provider-native card-to-foul link, so foul_linked=false
    # means "no native link", not an inference that no foul occurred.
    timeline_paths = _fifa_timeline_paths(raw_root, 2026, matches)
    cards_2026 = {
        row["card_id"]: row for row in cards
        if int(row["edition"]) == 2026
        and row["recipient_type"] == "player"
        and row["event_scope"] == "in_play"
    }
    seen_2026_cards: set[str] = set()
    for number, path in sorted(timeline_paths.items()):
        events = json.loads(path.read_text(encoding="utf-8")).get("Event", [])
        indexed = list(enumerate(events))
        order = {}
        for index, event in indexed:
            minute = _parse_minute(event.get("MatchMinute"))
            if minute is None:
                # Non-clock administrative events cannot enter the in-play
                # foul/card tables, but they remain in the private archive.
                continue
            event_id = str(event.get("EventId", ""))
            if not event_id or event_id in order:
                raise ValueError(
                    f"2026 M{number}: clocked FIFA event lacks a unique EventId"
                )
            order[event_id] = (
                int(event.get("Period", -1)), minute, index
            )
        triples = list(order.values())
        if len(triples) != len(set(triples)):
            raise ValueError(f"2026 M{number}: duplicate FIFA period/clock/index triple")
        match = match_lookup[(2026, number)]
        match_team_ids = {match["home_team_id"], match["away_team_id"]}
        fouls_by_team: dict[str, list[dict]] = defaultdict(list)
        for index, event in indexed:
            if event.get("Type") != 18 or int(event.get("Period", -1)) not in {3, 5, 7, 9}:
                continue
            team_id = str(event.get("IdTeam") or "")
            if team_id not in match_team_ids:
                raise ValueError(f"2026 M{number}: FIFA foul team is outside match: {team_id}")
            minute = _parse_minute(event.get("MatchMinute"))
            if minute is None:
                raise ValueError(f"2026 M{number}: foul lacks a usable event clock")
            segment = _segment(int(event["Period"]), minute, provider="fifa")
            if segment is None:
                continue
            segment_counts[(2026, number, team_id, segment)] += 1
            fouls_by_team[team_id].append(event)
        provider_cards = {
            str(event.get("EventId")): event for _, event in indexed
            if event.get("Type") in {2, 3, 4}
            and int(event.get("Period", -1)) in {3, 5, 7, 9}
            and event.get("IdPlayer")
        }
        for card_id, card in sorted(cards_2026.items()):
            if int(card["match_number"]) != number:
                continue
            provider_event_id = card_id.rsplit("-", 1)[-1]
            event = provider_cards.get(provider_event_id)
            if event is None:
                raise ValueError(f"2026 project card lacks its FIFA provider event: {card_id}")
            if str(event.get("IdTeam") or "") != card["team_id"]:
                raise ValueError(f"2026 card/team provider join failed: {card_id}")
            card_order = order[provider_event_id]
            internal_card_order[card_id] = card_order
            strict = sum(
                order[str(foul["EventId"])] < card_order
                for foul in fouls_by_team[card["team_id"]]
            )
            public_by_card[card_id] = {
                "edition": 2026,
                "edition_status": "provisional_M100",
                "card_id": card_id,
                "provider": "FIFA timeline",
                "reconciliation_status": "matched",
                "fouls_strictly_before_card": strict,
                "foul_linked": "false",
                "fouls_through_card": strict,
                "provenance_status": "provider_card_matched_no_native_foul_link",
                "source_url": FIFA_URLS[2026],
            }
            private_rows.append({
                "edition": 2026,
                "project_match_number": number,
                "project_card_id": card_id,
                "project_team_id": card["team_id"],
                "provider": "FIFA timeline",
                "provider_match_id": match["match_id"],
                "provider_event_id": provider_event_id,
                "provider_sequence_index": card_order[2],
                "provider_event_order_key": "|".join(map(str, card_order)),
                "provider_linked_event_reference": "",
                "provider_event_type": event.get("Type"),
                "fouls_strictly_before_card": strict,
                "foul_linked": "false",
                "fouls_through_card": strict,
            })
            seen_2026_cards.add(card_id)
    if seen_2026_cards != set(cards_2026):
        raise ValueError(
            "2026 FIFA order coverage differs from in-play player-card census: "
            f"missing={sorted(set(cards_2026) - seen_2026_cards)}"
        )

    # 2014 has an official card census but no complete reproducible foul-event
    # sequence.  Emit explicit source-unavailable rows; never impute order.
    for card in cards:
        if (
            int(card["edition"]) == 2014
            and card["recipient_type"] == "player"
            and card["event_scope"] == "in_play"
        ):
            public_by_card[card["card_id"]] = {
                "edition": 2014,
                "edition_status": "final",
                "card_id": card["card_id"],
                "provider": "source_unavailable",
                "reconciliation_status": "source_unavailable",
                "fouls_strictly_before_card": "",
                "foul_linked": "",
                "fouls_through_card": "",
                "provenance_status": "complete_event_source_unavailable",
                "source_url": FIFA_URLS[2014],
            }

    expected_card_ids = {
        row["card_id"] for row in cards
        if row["recipient_type"] == "player" and row["event_scope"] == "in_play"
    }
    if set(public_by_card) != expected_card_ids:
        raise ValueError(
            "public cumulative-card audit does not cover the exact card census: "
            f"missing={sorted(expected_card_ids - set(public_by_card))[:10]} "
            f"extra={sorted(set(public_by_card) - expected_card_ids)[:10]}"
        )

    public_cards = [
        public_by_card[card_id] for card_id in sorted(
            public_by_card,
            key=lambda value: (
                int(value.split("-", 1)[0]),
                int(value.split("-", 2)[1]),
                value,
            ),
        )
    ]
    card_order_lookup = {row["card_id"]: row for row in public_cards}
    cards_by_team_match: dict[tuple[int, int, str], list[dict]] = defaultdict(list)
    for card in cards:
        if card["recipient_type"] == "player" and card["event_scope"] == "in_play":
            cards_by_team_match[
                (int(card["edition"]), int(card["match_number"]), card["team_id"])
            ].append(card)

    team_match_rows = []
    for match in sorted(matches, key=lambda row: (int(row["edition"]), int(row["match_number"]))):
        edition = int(match["edition"])
        number = int(match["match_number"])
        provider = (
            "source_unavailable" if edition == 2014
            else "StatsBomb open data" if edition in {2018, 2022}
            else "FIFA timeline"
        )
        source_url = STATSBOMB_URL if edition in {2018, 2022} else FIFA_URLS[edition]
        for side in ("home", "away"):
            team_id = match[f"{side}_team_id"]
            team_cards = cards_by_team_match.get((edition, number, team_id), [])
            first = None
            if team_cards:
                earliest_clock = min(
                    (int(row["period"]), float(row["t_min"]))
                    for row in team_cards
                )
                earliest = [
                    row for row in team_cards
                    if (int(row["period"]), float(row["t_min"])) == earliest_clock
                ]
                if edition == 2014:
                    # No event-order feed exists; the count remains blank and
                    # the project card census supplies only the displayed ID.
                    first = min(earliest, key=lambda row: row["card_id"])
                elif len(earliest) == 1:
                    first = earliest[0]
                else:
                    missing_order = [
                        row["card_id"] for row in earliest
                        if row["card_id"] not in internal_card_order
                    ]
                    if missing_order:
                        raise ValueError(
                            f"cannot resolve same-clock first card without provider order: "
                            f"{edition} M{number} {team_id} {missing_order}"
                        )
                    first = min(
                        earliest, key=lambda row: internal_card_order[row["card_id"]]
                    )
            first_audit = card_order_lookup[first["card_id"]] if first else None
            if edition == 2014:
                status = "source_unavailable"
                first_count = ""
            elif first is None:
                status = "no_card"
                first_count = ""
            elif first_audit["reconciliation_status"] == "unmatched":
                status = "first_card_unmatched"
                first_count = ""
            else:
                status = "first_card_matched"
                first_count = first_audit["fouls_strictly_before_card"]
            team_match_rows.append({
                "edition": edition,
                "edition_status": _edition_status(edition),
                "match_number": number,
                "stage": match["stage"],
                "team_id": team_id,
                "team": match[f"{side}_team"],
                "provider": provider,
                "has_in_play_player_card": "yes" if first else "no",
                "first_card_id": first["card_id"] if first else "",
                "fouls_before_first_card": first_count,
                "status": status,
                "source_url": source_url,
            })

    private_rows.sort(key=lambda row: (
        int(row["edition"]), int(row["project_match_number"]),
        row["project_team_id"], row["provider_event_order_key"], row["project_card_id"],
    ))
    _write_private_sidecar(raw_root, private_rows)

    # Provider identifiers must remain absent even if a future edit expands a
    # row.  The schema check makes this boundary fail closed.
    forbidden = {
        "provider_match_id", "provider_event_id", "provider_sequence_index",
        "provider_event_order_key", "provider_linked_event_reference",
        "sb_match_id", "sb_event_id", "event_id", "order_key",
    }
    public_tables = {
        "foul_event_segments": _public_segment_rows(matches, segment_counts),
        "card_event_order": public_cards,
        "team_match_card_order": team_match_rows,
        "team_outcomes": _team_outcomes(raw_root, matches),
    }
    schemas = {
        "foul_event_segments": FOUL_EVENT_SEGMENT_FIELDS,
        "card_event_order": CARD_EVENT_ORDER_FIELDS,
        "team_match_card_order": TEAM_MATCH_CARD_ORDER_FIELDS,
        "team_outcomes": TEAM_OUTCOME_FIELDS,
    }
    for name, rows in public_tables.items():
        expected_fields = schemas[name]
        if not rows or any(tuple(row) != expected_fields for row in rows):
            raise ValueError(f"{name}: public event table differs from its exact schema")
        if forbidden.intersection(expected_fields):
            raise ValueError(f"{name}: provider-native field crossed the public boundary")

    if len(public_tables["team_match_card_order"]) != len(matches) * 2:
        raise ValueError("team-match cumulative summary lost a zero-card match side")
    status_counts = Counter(row["reconciliation_status"] for row in public_cards)
    if status_counts["unmatched"] != 20:
        raise ValueError(
            f"StatsBomb unmatched-card count drifted: {status_counts['unmatched']} != 20"
        )
    return public_tables
