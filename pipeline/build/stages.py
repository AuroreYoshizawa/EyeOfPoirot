"""The eight deterministic analysis stages for methodology v0.2.

The module intentionally uses only the Python standard library. Public builds
therefore run from the committed normalized CSV files without network access
or a package-install step.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from ..config import (
    DENOMINATORS,
    EDITIONS,
    EXPECTED_CARD_REASON_SB_RECONCILIATION,
    EXPECTED_COMPLETED,
    EXPECTED_PLAYER_CARDS,
    MU_GRID,
    PRIMARY_MU,
    PRIMARY_RHO,
    RESULTS,
    RHO_GRID,
    RULE_SOURCE_URLS,
    SOURCE,
    STAGES,
    is_knockout,
)
from ..event_sources import (
    CARD_EVENT_ORDER_FIELDS,
    FOUL_EVENT_SEGMENT_FIELDS,
    TEAM_MATCH_CARD_ORDER_FIELDS,
    TEAM_OUTCOME_FIELDS,
)
from ..io import as_float, as_int, fmt, read_csv, write_csv


PLAY_PERIODS = {3, 5, 7, 9}
EXTRA_TIME_PERIODS = {7, 9}
# Stages whose cards create X_s terms (v0.2.1 knockout-impact scope): group
# and third-place cards are excluded at the event level.
EXPOSURE_STAGES = {"round_of_32", "round_of_16", "quarter_final", "semi_final", "final"}
# Post-quarter-final-reset stages whose cautions use the exact-clock remainder.
EXACT_CLOCK_STAGES = {"semi_final", "final"}

CARD_LEDGER_FIELDS = (
    "card_id", "edition", "match_number", "match_id", "date_utc", "stage",
    "team_id", "team", "opponent", "player_id", "player", "card_type",
    "minute_label", "t_min", "period", "event_scope", "nominal_basis_min",
    "t_end_min", "reset_window", "base_horizon", "effective_horizon",
    "accumulation_role", "paired_card_id", "stop_scope", "stop_card_id",
    "stop_match_number", "stop_t_min", "stop_gap_fixtures",
    "nominal_remainder_min",
    "exp_match_min_rho_1", "exp_match_min_rho_1_5", "exp_match_min_rho_2",
    "source_url", "source_archive",
)

SUSPENSION_FIELDS = (
    "suspension_id", "edition", "team_id", "team", "player_id", "player",
    "trigger_type", "trigger_card_id", "trigger_match_number", "trigger_match_id",
    "trigger_stage", "service_match_number", "service_match_id", "service_stage",
    "service_nominal_minutes", "service_status", "lineup_status",
    "rule_source_url", "lineup_source_url", "lineup_source_archive", "audit_note",
    "decision_type", "decision_status", "decision_source_url",
    "decision_source_archive", "decision_note",
)

AVAILABILITY_FIELDS = (
    "edition", "team_id", "team", "player_id", "player", "match_number",
    "match_id", "stage", "opponent", "team_match_number", "nominal_minutes",
    "lineup_status", "availability_status", "played_minutes",
    "suspension_unavailable_minutes", "injury_unavailable_minutes",
    "union_unavailable_minutes", "opportunity_denominator_minutes",
    "injury_source_url", "injury_evidence_note", "participation_source_url",
    "participation_source_archive",
)

OMEGA_FIELDS = (
    "edition", "team_id", "team", "player_id", "player", "played_minutes",
    "team_nominal_minutes", "suspension_unavailable_minutes",
    "injury_unavailable_minutes", "union_unavailable_minutes",
    "opportunity_denominator_minutes", "omega",
)

MATCH_EXPOSURE_FIELDS = (
    "edition", "match_number", "match_id", "date_utc", "stage", "venue_side",
    "team_id", "team", "opponent_team_id", "opponent", "primary_cohort",
    "in_play_player_cards", "fouls", "rho", "exp_match_min",
    "exp_match_per_foul", "opponent_exp_match_min",
    "opponent_exp_match_per_foul", "d_exp_match", "d_exp_match_per_foul",
)
MATCH_END_CLOCK_FIELDS = (
    MATCH_EXPOSURE_FIELDS[:14] + ("clock_variant",) + MATCH_EXPOSURE_FIELDS[14:]
)

PLAYER_SUSPENSION_FIELDS = (
    "edition", "team_id", "team", "player_id", "player", "primary_cohort",
    "rho", "mu", "ordinary_caution_min", "carried_in_caution_min",
    "dismissal_min", "served_suspension_matches", "served_suspension_min",
    "unweighted_exp_susp_min", "omega", "exp_susp_min",
)

DEPTH_CHECK_FIELDS = (
    "edition", "edition_status", "cohort", "teams", "depth_definition",
    "rho", "mu", "denominator", "tau_b", "p_permutation", "permutations",
    "seed", "note",
)

TEAM_SUSPENSION_FIELDS = (
    "edition", "team_id", "team", "primary_cohort", "rho", "mu",
    "exposed_players", "mean_omega", "fouls_all", "fouls_knockout", "exp_susp_min",
    "exp_susp_per_foul_all", "exp_susp_per_foul_knockout",
)

SENSITIVITY_FIELDS = (
    "edition", "rho", "mu", "denominator", "cohort", "teams",
    "exp_susp_min", "fouls", "pooled_exp_susp_per_foul",
)
SUSPENSION_END_CLOCK_FIELDS = (
    "edition", "clock_variant", "rho", "mu", "denominator", "cohort", "teams",
    "exp_susp_min", "fouls", "pooled_exp_susp_per_foul",
)

EDITION_SUMMARY_FIELDS = (
    "edition", "included_matches", "player_cards", "in_play_player_cards",
    "team_fouls", "knockout_teams", "served_suspension_matches",
    "deferred_suspensions", "suspension_conflicts", "rho", "mu",
    "pooled_exp_susp_per_foul",
)

BUILD_AUDIT_FIELDS = ("edition", "check", "observed", "expected", "status", "note")

CARD_REASON_SOURCE_FIELDS = (
    "card_id", "reason_class", "sb_foul_linked", "source_url",
    "source_tier", "note",
)
CARD_REASON_SB_RECONCILIATION_SOURCE_FIELDS = (
    "edition", "event_type", "in_play_census_events",
    "outside_in_play_census_events", "all_card_events",
    "outside_scope_summary", "source_url",
)
EXACT_SOURCE_SCHEMAS = {
    "card_reasons": CARD_REASON_SOURCE_FIELDS,
    "card_reason_sb_reconciliation": CARD_REASON_SB_RECONCILIATION_SOURCE_FIELDS,
    "foul_event_segments": FOUL_EVENT_SEGMENT_FIELDS,
    "card_event_order": CARD_EVENT_ORDER_FIELDS,
    "team_match_card_order": TEAM_MATCH_CARD_ORDER_FIELDS,
    "team_outcomes": TEAM_OUTCOME_FIELDS,
}


def _key(row: dict) -> tuple[int, str, str]:
    return int(row["edition"]), row["team_id"], row["player_id"]


def _reset_window(edition: int, stage: str) -> str:
    if edition == 2026:
        if stage == "group":
            return "group"
        if stage in {"round_of_32", "round_of_16", "quarter_final"}:
            return "knockout_pre_quarter_final_reset"
        return "post_quarter_final_reset"
    if stage in {"group", "round_of_16", "quarter_final"}:
        return "pre_quarter_final_reset"
    return "post_quarter_final_reset"


def _base_horizon(edition: int, stage: str, team_match_number: int) -> int:
    if stage == "group":
        if edition == 2026:
            return max(0, 3 - team_match_number)
        return max(0, 5 - team_match_number)
    if stage == "round_of_32":
        return 2 if edition == 2026 else 0
    if stage == "round_of_16":
        return 1
    return 0


def _card_sort(row: dict) -> tuple:
    return row["date_utc"], float(row["t_min"]), row["card_id"]


def _interval_union(intervals: Iterable[tuple[float, float]]) -> float:
    clean = sorted((max(0.0, a), max(0.0, b)) for a, b in intervals if b > a)
    if not clean:
        return 0.0
    total = 0.0
    start, end = clean[0]
    for next_start, next_end in clean[1:]:
        if next_start <= end:
            end = max(end, next_end)
        else:
            total += end - start
            start, end = next_start, next_end
    return total + end - start


def _validate_source_table_schema(name: str, rows: list[dict[str, str]]) -> None:
    """Reject extra, missing, or reordered fields at the public-data boundary."""
    expected = EXACT_SOURCE_SCHEMAS.get(name)
    if expected is None:
        return
    if not rows:
        raise ValueError(f"normalized source table is empty: {name}")
    for index, row in enumerate(rows, start=2):
        if tuple(row) != expected:
            raise ValueError(
                f"{name}.csv row {index} fields differ from the frozen schema: "
                f"observed={list(row)} expected={list(expected)}"
            )


def _validate_source_header(name: str, fieldnames: Iterable[str]) -> None:
    """Validate the literal CSV header, including duplicate field names."""
    expected = EXACT_SOURCE_SCHEMAS.get(name)
    if expected is not None and tuple(fieldnames) != expected:
        raise ValueError(
            f"{name}.csv header differs from the frozen schema: "
            f"observed={list(fieldnames)} expected={list(expected)}"
        )


def _validate_sb_reconciliation(rows: list[dict[str, str]]) -> None:
    """Require the frozen four-row StatsBomb aggregate reconciliation."""
    observed = {}
    for row in rows:
        key = (int(row["edition"]), row["event_type"])
        if key in observed:
            raise ValueError(f"duplicate StatsBomb aggregate reconciliation row: {key}")
        if row["source_url"] != "https://github.com/statsbomb/open-data":
            raise ValueError(
                "StatsBomb aggregate reconciliation lacks the official source URL: "
                f"{key}"
            )
        values = (
            int(row["in_play_census_events"]),
            int(row["outside_in_play_census_events"]),
            int(row["all_card_events"]),
            row["outside_scope_summary"],
        )
        if values[0] + values[1] != values[2]:
            raise ValueError(
                "StatsBomb aggregate reconciliation does not add up: "
                f"{key} values={values[:3]}"
            )
        observed[key] = values
    if observed != EXPECTED_CARD_REASON_SB_RECONCILIATION:
        missing = sorted(set(EXPECTED_CARD_REASON_SB_RECONCILIATION) - set(observed))
        extra = sorted(set(observed) - set(EXPECTED_CARD_REASON_SB_RECONCILIATION))
        wrong = sorted(
            key
            for key in set(observed) & set(EXPECTED_CARD_REASON_SB_RECONCILIATION)
            if observed[key] != EXPECTED_CARD_REASON_SB_RECONCILIATION[key]
        )
        raise ValueError(
            "StatsBomb aggregate reconciliation differs from the audited counts: "
            f"missing={missing} extra={extra} wrong={wrong}"
        )


def _source_tables(source_dir: Path = SOURCE) -> dict[str, list[dict[str, str]]]:
    names = (
        "matches", "cards", "card_reasons", "card_reason_sb_reconciliation",
        "fouls_team_match", "player_match", "availability_evidence",
        "sanction_decisions", "foul_event_segments", "card_event_order",
        "team_match_card_order", "team_outcomes", "source_audit",
    )
    missing = [str(source_dir / f"{name}.csv") for name in names if not (source_dir / f"{name}.csv").exists()]
    if missing:
        raise FileNotFoundError("normalized source tables missing: " + ", ".join(missing))
    tables = {}
    for name in names:
        path = source_dir / f"{name}.csv"
        with path.open(newline="", encoding="utf-8-sig") as handle:
            header = next(csv.reader(handle), [])
        _validate_source_header(name, header)
        tables[name] = read_csv(path)
    for name, rows in tables.items():
        _validate_source_table_schema(name, rows)
    _validate_sb_reconciliation(tables["card_reason_sb_reconciliation"])
    return tables


def stage1_cards(
    tables: dict[str, list[dict[str, str]]],
    stage_dir: Path = STAGES,
    output_name: str = "s1-card-ledger.csv",
) -> list[dict]:
    """Create the player-card ledger and apply the frozen horizon stop rule."""
    fouls = tables["fouls_team_match"]
    team_match_number = {
        (int(row["edition"]), int(row["match_number"]), row["team_id"]): int(row["team_match_number"])
        for row in fouls
    }
    rows: list[dict] = []
    for source in tables["cards"]:
        if source["recipient_type"] != "player":
            continue
        edition = int(source["edition"])
        number = int(source["match_number"])
        period = int(source["period"])
        scope = source.get("event_scope") or (
            "in_play" if period in PLAY_PERIODS else
            "interval" if period == 0 else
            "post_play" if period == 10 else
            "penalty_shootout" if period == 11 else "unknown"
        )
        if scope == "unknown":
            raise ValueError(f"unknown event scope for {source['card_id']}")
        t_min = float(source["t_min"])
        t_end = float(source["t_end_min"])
        basis = int(source["nominal_basis_min"])
        card_type = source["card_type"]
        horizon = _base_horizon(
            edition, source["stage"], team_match_number[(edition, number, source["team_id"])]
        ) if card_type == "Y" else 0
        match_values = {}
        for rho in RHO_GRID:
            multiplier = 1.0 if card_type == "Y" else rho
            value = multiplier * max(0.0, t_end - t_min) if scope == "in_play" else 0.0
            match_values[rho] = value
        rows.append({
            **{field: source.get(field, "") for field in (
                "card_id", "edition", "match_number", "match_id", "date_utc", "stage",
                "team_id", "team", "opponent", "player_id", "player", "card_type",
                "minute_label", "t_min", "period", "nominal_basis_min", "t_end_min",
                "source_url", "source_archive",
            )},
            "event_scope": scope,
            "reset_window": _reset_window(edition, source["stage"]),
            "base_horizon": horizon,
            "effective_horizon": horizon,
            "accumulation_role": "dismissal" if card_type in {"R", "Y2"} else "single_caution",
            "paired_card_id": "",
            "stop_scope": "", "stop_card_id": "", "stop_match_number": "",
            "stop_t_min": "", "stop_gap_fixtures": "",
            "nominal_remainder_min": fmt(max(0.0, basis - t_min)),
            "exp_match_min_rho_1": fmt(match_values[1.0]),
            "exp_match_min_rho_1_5": fmt(match_values[1.5]),
            "exp_match_min_rho_2": fmt(match_values[2.0]),
        })

    # A Y immediately followed by Y2 in the same match is a same-match pair,
    # not one half of the cross-match accumulation sequence.
    same_match_y: set[str] = set()
    by_player_match: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        by_player_match[(_key(row), int(row["match_number"]))].append(row)
    for event_rows in by_player_match.values():
        ordered = sorted(event_rows, key=_card_sort)
        for dismissal in [row for row in ordered if row["card_type"] == "Y2"]:
            candidates = [
                row for row in ordered
                if row["card_type"] == "Y" and float(row["t_min"]) <= float(dismissal["t_min"])
                and row["card_id"] not in same_match_y
            ]
            if not candidates:
                raise ValueError(f"Y2 lacks preceding Y: {dismissal['card_id']}")
            first = candidates[-1]
            first["effective_horizon"] = 0
            first["accumulation_role"] = "same_match_first_caution"
            first["paired_card_id"] = dismissal["card_id"]
            dismissal["paired_card_id"] = first["card_id"]
            same_match_y.add(first["card_id"])

    # Remaining ordinary cautions are paired chronologically within each
    # reset window. The first card's risk stops at the triggering fixture; the
    # triggering card itself receives zero forward-risk blocks.
    by_window: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        if row["card_type"] == "Y" and row["card_id"] not in same_match_y:
            by_window[(_key(row), row["reset_window"])].append(row)
    for caution_rows in by_window.values():
        ordered = sorted(caution_rows, key=_card_sort)
        for index in range(0, len(ordered) - 1, 2):
            first, trigger = ordered[index], ordered[index + 1]
            first_team_no = team_match_number[(int(first["edition"]), int(first["match_number"]), first["team_id"])]
            trigger_team_no = team_match_number[(int(trigger["edition"]), int(trigger["match_number"]), trigger["team_id"])]
            distance = max(0, trigger_team_no - first_team_no)
            first["effective_horizon"] = min(int(first["base_horizon"]), distance)
            first["accumulation_role"] = "accumulation_first_caution"
            first["paired_card_id"] = trigger["card_id"]
            trigger["effective_horizon"] = 0
            trigger["accumulation_role"] = "accumulation_trigger"
            trigger["paired_card_id"] = first["card_id"]

    # Minute-granular stop information (v0.2.1 §3.3): an ordinary caution's
    # risk interval ends at the player's next suspension-causing card in the
    # same reset window — its cross-match accumulation trigger, its same-match
    # Y2, or any dismissal — whichever comes first.
    by_player_reset_window: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        by_player_reset_window[(_key(row), row["reset_window"])].append(row)
    card_by_id = {row["card_id"]: row for row in rows}
    for window_rows in by_player_reset_window.values():
        ordered = sorted(window_rows, key=_card_sort)
        for index, row in enumerate(ordered):
            if row["card_type"] != "Y":
                continue
            stoppers = [
                later for later in ordered[index + 1:]
                if later["card_type"] in {"Y2", "R"}
            ]
            if row["accumulation_role"] == "accumulation_first_caution":
                stoppers.append(card_by_id[row["paired_card_id"]])
            if not stoppers:
                continue
            stopper = min(stoppers, key=_card_sort)
            same_match = int(stopper["match_number"]) == int(row["match_number"])
            gap = 0
            if not same_match:
                first_no = team_match_number[(int(row["edition"]), int(row["match_number"]), row["team_id"])]
                stop_no = team_match_number[(int(stopper["edition"]), int(stopper["match_number"]), stopper["team_id"])]
                gap = max(0, stop_no - first_no - 1)
            row["stop_scope"] = "same_match" if same_match else "cross_match"
            row["stop_card_id"] = stopper["card_id"]
            row["stop_match_number"] = stopper["match_number"]
            row["stop_t_min"] = stopper["t_min"]
            row["stop_gap_fixtures"] = gap

    rows.sort(key=lambda row: (int(row["edition"]), int(row["match_number"]), float(row["t_min"]), row["card_id"]))
    write_csv(stage_dir / output_name, rows, CARD_LEDGER_FIELDS)
    return rows


def stage2_fouls(tables: dict[str, list[dict[str, str]]], stage_dir: Path = STAGES) -> list[dict]:
    """Validate and copy the team-match foul layer used as denominators."""
    rows = sorted(
        tables["fouls_team_match"],
        key=lambda row: (int(row["edition"]), int(row["match_number"]), row["team_id"]),
    )
    if any(as_int(row["fouls"]) is None or int(row["fouls"]) < 0 for row in rows):
        raise ValueError("foul table contains a missing or negative value")
    write_csv(stage_dir / "s2-team-match-fouls.csv", rows, rows[0].keys())
    return rows


def stage3_minutes(tables: dict[str, list[dict[str, str]]], stage_dir: Path = STAGES) -> list[dict]:
    """Validate and copy official participation observations."""
    rows = sorted(
        tables["player_match"],
        key=lambda row: (
            int(row["edition"]), row["team_id"], row["player_id"], int(row["team_match_number"])
        ),
    )
    for row in rows:
        played = float(row["played_minutes"] or 0)
        nominal = float(row["nominal_minutes"])
        if not 0 <= played <= nominal:
            raise ValueError(f"invalid player minutes: {row}")
    write_csv(stage_dir / "s3-player-match-minutes.csv", rows, rows[0].keys())
    return rows


def _team_schedule(tables: dict[str, list[dict[str, str]]]) -> dict[tuple[int, str], list[dict]]:
    by_match = {(int(row["edition"]), int(row["match_number"])): row for row in tables["matches"]}
    result: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for row in tables["fouls_team_match"]:
        match = by_match[(int(row["edition"]), int(row["match_number"]))]
        result[(int(row["edition"]), row["team_id"])].append({
            "match_number": int(row["match_number"]),
            "match_id": row["match_id"],
            "stage": row["stage"],
            "team_match_number": int(row["team_match_number"]),
            "nominal_minutes": int(match["nominal_minutes"]),
        })
    for rows in result.values():
        rows.sort(key=lambda row: row["team_match_number"])
    return result


def stage4_suspensions(
    tables: dict[str, list[dict[str, str]]], card_ledger: list[dict],
    stage_dir: Path = STAGES, output_name: str = "s4-suspensions.csv",
) -> list[dict]:
    """Derive automatic sanctions, then apply sourced disciplinary decisions."""
    schedule = _team_schedule(tables)
    participation = {
        (int(row["edition"]), row["team_id"], row["player_id"], int(row["match_number"])): row
        for row in tables["player_match"]
    }
    triggers = [
        (row, "accumulation" if row["accumulation_role"] == "accumulation_trigger" else "dismissal")
        for row in card_ledger
        if row["accumulation_role"] == "accumulation_trigger" or row["card_type"] in {"R", "Y2"}
    ]
    decisions_by_trigger = {
        row["trigger_card_id"]: row
        for row in tables["sanction_decisions"] if row["trigger_card_id"]
    }
    external_decisions = [
        row for row in tables["sanction_decisions"] if not row["trigger_card_id"]
    ]
    output = []

    def service_game(edition: int, team_id: str, number: int) -> dict:
        game = next(
            (item for item in schedule[(edition, team_id)] if item["match_number"] == number),
            None,
        )
        if game is None:
            raise ValueError(f"disciplinary decision refers to unavailable service match: {edition} M{number}")
        return game

    def verified_status(decision_status: str, lineup: dict | None) -> tuple[str, str]:
        if decision_status == "deferred":
            return "deferred", "The sourced decision deferred execution; no served term is added."
        if decision_status == "pending":
            return "pending", "The sourced decision is pending within the observed cutoff."
        if lineup is None:
            return "conflict", "The sourced service match has no player participation row."
        if lineup["lineup_status"] == "absent":
            return "served", "The sourced service match is confirmed by an absent official lineup record."
        return (
            "conflict",
            "The sourced served decision conflicts with official lineup status "
            f"{lineup['lineup_status']!r}; no served term is added.",
        )

    def decision_fields(decision: dict | None) -> dict:
        if decision is None:
            return {
                "decision_type": "", "decision_status": "",
                "decision_source_url": "", "decision_source_archive": "", "decision_note": "",
            }
        return {
            "decision_type": decision["decision_type"],
            "decision_status": decision["decision_status"],
            "decision_source_url": decision["source_url"],
            "decision_source_archive": decision["source_archive"],
            "decision_note": decision["evidence_note"],
        }

    for trigger, trigger_type in triggers:
        edition = int(trigger["edition"])
        games = schedule[(edition, trigger["team_id"])]
        current_index = next(
            index for index, game in enumerate(games)
            if game["match_number"] == int(trigger["match_number"])
        )
        decision = decisions_by_trigger.get(trigger["card_id"])
        if decision:
            service_games = [
                service_game(edition, trigger["team_id"], int(number))
                for number in decision["service_match_numbers"].split("|")
            ]
        else:
            service_games = [games[current_index + 1]] if current_index + 1 < len(games) else []
        if not service_games:
            output.append({
                "suspension_id": f"{trigger['card_id']}-{trigger_type}-pending",
                "edition": edition, "team_id": trigger["team_id"], "team": trigger["team"],
                "player_id": trigger["player_id"], "player": trigger["player"],
                "trigger_type": trigger_type, "trigger_card_id": trigger["card_id"],
                "trigger_match_number": trigger["match_number"],
                "trigger_match_id": trigger["match_id"], "trigger_stage": trigger["stage"],
                "service_match_number": "", "service_match_id": "", "service_stage": "",
                "service_nominal_minutes": "", "service_status": "pending", "lineup_status": "",
                "rule_source_url": RULE_SOURCE_URLS[edition], "lineup_source_url": "",
                "lineup_source_archive": "",
                "audit_note": "No later observed team match within the edition cutoff.",
                **decision_fields(decision),
            })
            continue
        for game in service_games:
            if game["match_number"] <= int(trigger["match_number"]):
                raise ValueError(f"service match is not after trigger: {trigger['card_id']} M{game['match_number']}")
            lineup = participation.get((
                edition, trigger["team_id"], trigger["player_id"], game["match_number"]
            ))
            if decision:
                status, note = verified_status(decision["decision_status"], lineup)
            elif lineup is None:
                status, note = "conflict", "Trigger has a later team match but no player participation row."
            elif lineup["lineup_status"] == "absent":
                status, note = "served", "Next observed official lineup records the player as absent."
            else:
                status = "conflict"
                note = (
                    "Automatic sanction conflicts with next official lineup status "
                    f"{lineup['lineup_status']!r}; no served term is added."
                )
            output.append({
                "suspension_id": f"{trigger['card_id']}-{trigger_type}-service-M{game['match_number']}",
                "edition": edition, "team_id": trigger["team_id"], "team": trigger["team"],
                "player_id": trigger["player_id"], "player": trigger["player"],
                "trigger_type": trigger_type, "trigger_card_id": trigger["card_id"],
                "trigger_match_number": trigger["match_number"],
                "trigger_match_id": trigger["match_id"], "trigger_stage": trigger["stage"],
                "service_match_number": game["match_number"], "service_match_id": game["match_id"],
                "service_stage": game["stage"], "service_nominal_minutes": game["nominal_minutes"],
                "service_status": status, "lineup_status": lineup["lineup_status"] if lineup else "",
                "rule_source_url": RULE_SOURCE_URLS[edition],
                "lineup_source_url": lineup["source_url"] if lineup else "",
                "lineup_source_archive": lineup["source_archive"] if lineup else "",
                "audit_note": note, **decision_fields(decision),
            })

    # Carry-in bans have no tournament card trigger, but they still affect the
    # same carded-player opportunity denominator and served-match component.
    for decision in external_decisions:
        edition = int(decision["edition"])
        for number in decision["service_match_numbers"].split("|"):
            game = service_game(edition, decision["team_id"], int(number))
            lineup = participation.get((
                edition, decision["team_id"], decision["player_id"], game["match_number"]
            ))
            status, note = verified_status(decision["decision_status"], lineup)
            output.append({
                "suspension_id": (
                    f"{edition}-external-{decision['team_id']}-{decision['player_id']}"
                    f"-service-M{game['match_number']}"
                ),
                "edition": edition, "team_id": decision["team_id"], "team": decision["team"],
                "player_id": decision["player_id"], "player": decision["player"],
                "trigger_type": "external", "trigger_card_id": "", "trigger_match_number": "",
                "trigger_match_id": "", "trigger_stage": "", "service_match_number": game["match_number"],
                "service_match_id": game["match_id"], "service_stage": game["stage"],
                "service_nominal_minutes": game["nominal_minutes"], "service_status": status,
                "lineup_status": lineup["lineup_status"] if lineup else "",
                "rule_source_url": RULE_SOURCE_URLS[edition],
                "lineup_source_url": lineup["source_url"] if lineup else "",
                "lineup_source_archive": lineup["source_archive"] if lineup else "",
                "audit_note": note, **decision_fields(decision),
            })
    output.sort(key=lambda row: (
        int(row["edition"]), as_int(row["service_match_number"], 999) or 999,
        row["team_id"], row["player_id"], row["trigger_type"], row["suspension_id"],
    ))
    write_csv(stage_dir / output_name, output, SUSPENSION_FIELDS)
    return output


def _nominal_card_minute(label: str, nominal: float) -> float:
    # The part before '+' is the nominal clock. Stoppage does not make a
    # 45+4 substitution/card consume four additional nominal minutes.
    base = float(label.split("'")[0])
    return min(max(0.0, base), nominal)


def stage5_availability(
    tables: dict[str, list[dict[str, str]]], card_ledger: list[dict], suspensions: list[dict],
    stage_dir: Path = STAGES,
) -> tuple[list[dict], list[dict]]:
    """Union sanction/injury intervals and compute player opportunity weights."""
    dismissal_by_match: dict[tuple, list[dict]] = defaultdict(list)
    for row in card_ledger:
        if row["card_type"] in {"R", "Y2"} and row["event_scope"] in {"in_play", "interval"}:
            dismissal_by_match[(_key(row), int(row["match_number"]))].append(row)
    served = {
        (int(row["edition"]), row["team_id"], row["player_id"], int(row["service_match_number"]))
        for row in suspensions if row["service_status"] == "served"
    }
    injuries: dict[tuple, list[dict]] = defaultdict(list)
    for row in tables["availability_evidence"]:
        if float(row["unavailable_minutes"]) > 0 and not row["source_url"]:
            raise ValueError(f"positive injury interval lacks URL: {row}")
        injuries[(_key(row), int(row["match_number"]))].append(row)

    availability = []
    totals: dict[tuple, dict] = {}
    for row in tables["player_match"]:
        key = _key(row)
        match_number = int(row["match_number"])
        match_key = (key, match_number)
        nominal = float(row["nominal_minutes"])
        suspension_intervals: list[tuple[float, float]] = []
        if (key[0], key[1], key[2], match_number) in served:
            suspension_intervals.append((0.0, nominal))
        for card in dismissal_by_match.get(match_key, []):
            suspension_intervals.append((_nominal_card_minute(card["minute_label"], nominal), nominal))
        injury_rows = injuries.get(match_key, [])
        injury_intervals = [
            (max(0.0, float(item["start_minute"])), min(nominal, float(item["end_minute"])))
            for item in injury_rows
        ]
        suspension_minutes = _interval_union(suspension_intervals)
        injury_minutes = _interval_union(injury_intervals)
        union_minutes = _interval_union(suspension_intervals + injury_intervals)
        played = float(row["played_minutes"] or 0)
        denominator = nominal - union_minutes
        if denominator < -1e-8 or played > denominator + 1e-8:
            raise ValueError(
                f"availability denominator conflict for {key} m{match_number}: "
                f"played={played}, denominator={denominator}"
            )
        if suspension_minutes > 0:
            status = "suspended"
        elif injury_minutes > 0:
            status = "injured"
        elif row["lineup_status"] in {"starter", "used_substitute"}:
            status = "played"
        elif row["lineup_status"] == "unused_substitute":
            status = "bench"
        else:
            status = "unexplained"
        injury_urls = sorted({item["source_url"] for item in injury_rows if item["source_url"]})
        injury_notes = sorted({item["evidence_note"] for item in injury_rows if item["evidence_note"]})
        availability.append({
            "edition": row["edition"], "team_id": row["team_id"], "team": row["team"],
            "player_id": row["player_id"], "player": row["player"],
            "match_number": match_number, "match_id": row["match_id"], "stage": row["stage"],
            "opponent": row["opponent"], "team_match_number": row["team_match_number"],
            "nominal_minutes": row["nominal_minutes"], "lineup_status": row["lineup_status"],
            "availability_status": status, "played_minutes": fmt(played),
            "suspension_unavailable_minutes": fmt(suspension_minutes),
            "injury_unavailable_minutes": fmt(injury_minutes),
            "union_unavailable_minutes": fmt(union_minutes),
            "opportunity_denominator_minutes": fmt(denominator),
            "injury_source_url": " | ".join(injury_urls),
            "injury_evidence_note": " | ".join(injury_notes),
            "participation_source_url": row["source_url"],
            "participation_source_archive": row["source_archive"],
        })
        summary = totals.setdefault(key, {
            "edition": row["edition"], "team_id": row["team_id"], "team": row["team"],
            "player_id": row["player_id"], "player": row["player"], "played": 0.0,
            "nominal": 0.0, "suspension": 0.0, "injury": 0.0, "union": 0.0,
        })
        summary["played"] += played
        summary["nominal"] += nominal
        summary["suspension"] += suspension_minutes
        summary["injury"] += injury_minutes
        summary["union"] += union_minutes

    omega = []
    for key, row in sorted(totals.items()):
        denominator = row["nominal"] - row["union"]
        if denominator <= 0:
            raise ValueError(f"non-positive opportunity denominator for {key}: {denominator}")
        value = row["played"] / denominator
        if not -1e-9 <= value <= 1 + 1e-9:
            raise ValueError(f"omega outside [0,1] for {key}: {value}")
        omega.append({
            "edition": row["edition"], "team_id": row["team_id"], "team": row["team"],
            "player_id": row["player_id"], "player": row["player"],
            "played_minutes": fmt(row["played"]), "team_nominal_minutes": fmt(row["nominal"]),
            "suspension_unavailable_minutes": fmt(row["suspension"]),
            "injury_unavailable_minutes": fmt(row["injury"]),
            "union_unavailable_minutes": fmt(row["union"]),
            "opportunity_denominator_minutes": fmt(denominator), "omega": fmt(value, 9),
        })
    availability.sort(key=lambda row: (
        int(row["edition"]), row["team_id"], row["player_id"], int(row["team_match_number"])
    ))
    write_csv(stage_dir / "s5-availability.csv", availability, AVAILABILITY_FIELDS)
    write_csv(stage_dir / "s5-player-opportunity.csv", omega, OMEGA_FIELDS)
    return availability, omega


def _primary_teams(tables: dict[str, list[dict[str, str]]]) -> set[tuple[int, str]]:
    return {
        (int(row["edition"]), row["team_id"])
        for row in tables["fouls_team_match"] if is_knockout(row["stage"])
    }


def stage6_match_exposure(
    tables: dict[str, list[dict[str, str]]], card_ledger: list[dict], result_dir: Path = RESULTS
) -> tuple[list[dict], list[dict], list[dict]]:
    """Compute E_m for all team matches and the antisymmetric differentials."""
    primary = _primary_teams(tables)
    match_lookup = {(int(row["edition"]), int(row["match_number"])): row for row in tables["matches"]}
    card_sums: dict[tuple, dict[float, float]] = defaultdict(lambda: defaultdict(float))
    card_counts: dict[tuple, int] = defaultdict(int)
    for card in card_ledger:
        if card["event_scope"] != "in_play":
            continue
        key = (int(card["edition"]), int(card["match_number"]), card["team_id"])
        card_counts[key] += 1
        card_sums[key][1.0] += float(card["exp_match_min_rho_1"] or 0)
        card_sums[key][1.5] += float(card["exp_match_min_rho_1_5"] or 0)
        card_sums[key][2.0] += float(card["exp_match_min_rho_2"] or 0)

    base_rows = []
    for foul in tables["fouls_team_match"]:
        # §2.2: match exposure is defined for knockout matches other than the
        # third-place match.
        if not is_knockout(foul["stage"]) or foul["stage"] == "third_place":
            continue
        edition, number = int(foul["edition"]), int(foul["match_number"])
        match = match_lookup[(edition, number)]
        if foul["team_id"] == match["home_team_id"]:
            side, opponent_id = "home", match["away_team_id"]
        else:
            side, opponent_id = "away", match["home_team_id"]
        for rho in RHO_GRID:
            key = (edition, number, foul["team_id"])
            exposure = card_sums[key][rho]
            fouls = int(foul["fouls"])
            base_rows.append({
                "edition": edition, "match_number": number, "match_id": foul["match_id"],
                "date_utc": match["date_utc"], "stage": foul["stage"], "venue_side": side,
                "team_id": foul["team_id"], "team": foul["team"],
                "opponent_team_id": opponent_id, "opponent": foul["opponent"],
                "primary_cohort": "yes" if (edition, foul["team_id"]) in primary else "no",
                "in_play_player_cards": card_counts[key], "fouls": fouls, "rho": fmt(rho),
                "exp_match_min": exposure,
                "exp_match_per_foul": exposure / fouls if fouls else None,
            })
    lookup = {
        (row["edition"], row["match_number"], row["team_id"], float(row["rho"])): row
        for row in base_rows
    }
    output = []
    for row in base_rows:
        opponent = lookup[(row["edition"], row["match_number"], row["opponent_team_id"], float(row["rho"]))]
        own_rate, opponent_rate = row["exp_match_per_foul"], opponent["exp_match_per_foul"]
        output.append({
            **{key: row[key] for key in (
                "edition", "match_number", "match_id", "date_utc", "stage", "venue_side",
                "team_id", "team", "opponent_team_id", "opponent", "primary_cohort",
                "in_play_player_cards", "fouls", "rho",
            )},
            "exp_match_min": fmt(row["exp_match_min"]),
            "exp_match_per_foul": fmt(own_rate),
            "opponent_exp_match_min": fmt(opponent["exp_match_min"]),
            "opponent_exp_match_per_foul": fmt(opponent_rate),
            "d_exp_match": fmt(row["exp_match_min"] - opponent["exp_match_min"]),
            "d_exp_match_per_foul": fmt(
                own_rate - opponent_rate if own_rate is not None and opponent_rate is not None else None
            ),
        })
    output.sort(key=lambda row: (
        int(row["edition"]), int(row["match_number"]), float(row["rho"]), row["venue_side"] != "home"
    ))
    primary_rows = [row for row in output if float(row["rho"]) == PRIMARY_RHO]
    sensitivity_rows = [row for row in output if float(row["rho"]) != PRIMARY_RHO]

    # A separate off-by-one check shortens only formula components that use
    # the observed end clock. Nominal caution remainders remain unchanged.
    clock_sums: dict[tuple, float] = defaultdict(float)
    for card in card_ledger:
        if card["event_scope"] != "in_play":
            continue
        key = (int(card["edition"]), int(card["match_number"]), card["team_id"])
        multiplier = 1.0 if card["card_type"] == "Y" else PRIMARY_RHO
        for variant, offset in (("source_end", 0.0), ("end_minus_one", 1.0)):
            clock_sums[(key, variant)] += multiplier * max(
                0.0, float(card["t_end_min"]) - offset - float(card["t_min"])
            )
    clock_base = []
    for foul in tables["fouls_team_match"]:
        if not is_knockout(foul["stage"]) or foul["stage"] == "third_place":
            continue
        edition, number = int(foul["edition"]), int(foul["match_number"])
        match = match_lookup[(edition, number)]
        if foul["team_id"] == match["home_team_id"]:
            side, opponent_id = "home", match["away_team_id"]
        else:
            side, opponent_id = "away", match["home_team_id"]
        fouls = int(foul["fouls"])
        key = (edition, number, foul["team_id"])
        for variant in ("source_end", "end_minus_one"):
            exposure = clock_sums[(key, variant)]
            clock_base.append({
                "edition": edition, "match_number": number, "match_id": foul["match_id"],
                "date_utc": match["date_utc"], "stage": foul["stage"], "venue_side": side,
                "team_id": foul["team_id"], "team": foul["team"],
                "opponent_team_id": opponent_id, "opponent": foul["opponent"],
                "primary_cohort": "yes" if (edition, foul["team_id"]) in primary else "no",
                "in_play_player_cards": card_counts[key], "fouls": fouls,
                "rho": fmt(PRIMARY_RHO), "clock_variant": variant,
                "exp_match_min": exposure,
                "exp_match_per_foul": exposure / fouls if fouls else None,
            })
    clock_lookup = {
        (row["edition"], row["match_number"], row["team_id"], row["clock_variant"]): row
        for row in clock_base
    }
    clock_output = []
    for row in clock_base:
        opponent = clock_lookup[(
            row["edition"], row["match_number"], row["opponent_team_id"], row["clock_variant"]
        )]
        own_rate, opponent_rate = row["exp_match_per_foul"], opponent["exp_match_per_foul"]
        clock_output.append({
            **{key: row[key] for key in (
                "edition", "match_number", "match_id", "date_utc", "stage", "venue_side",
                "team_id", "team", "opponent_team_id", "opponent", "primary_cohort",
                "in_play_player_cards", "fouls", "rho", "clock_variant",
            )},
            "exp_match_min": fmt(row["exp_match_min"]),
            "exp_match_per_foul": fmt(own_rate),
            "opponent_exp_match_min": fmt(opponent["exp_match_min"]),
            "opponent_exp_match_per_foul": fmt(opponent_rate),
            "d_exp_match": fmt(row["exp_match_min"] - opponent["exp_match_min"]),
            "d_exp_match_per_foul": fmt(
                own_rate - opponent_rate if own_rate is not None and opponent_rate is not None else None
            ),
        })
    clock_output.sort(key=lambda row: (
        int(row["edition"]), int(row["match_number"]), row["clock_variant"],
        row["venue_side"] != "home",
    ))
    write_csv(result_dir / "match-exposure.csv", primary_rows, MATCH_EXPOSURE_FIELDS)
    write_csv(result_dir / "match-exposure-sensitivity.csv", output, MATCH_EXPOSURE_FIELDS)
    write_csv(
        result_dir / "match-end-clock-sensitivity.csv", clock_output, MATCH_END_CLOCK_FIELDS
    )
    return primary_rows, sensitivity_rows, clock_output


def _caution_is_exact(card: dict) -> bool:
    """§3.3 exact-clock remainder: SF/final cautions and stoppage/ET receipt."""
    if card["stage"] in EXACT_CLOCK_STAGES:
        return True
    if int(card["period"]) in EXTRA_TIME_PERIODS:
        return True
    return "+" in (card["minute_label"] or "")


def _caution_interval(card: dict, offset: float = 0.0) -> float:
    """§3.3 risk interval L(c) at minute granularity.

    `offset` implements the end-clock boundary sensitivity and shifts only
    the observed-clock cap, never the nominal basis.
    """
    t_min = float(card["t_min"])
    exact = _caution_is_exact(card)
    cap = (float(card["t_end_min"]) - offset) if exact else float(card["nominal_basis_min"])
    horizon = int(card["base_horizon"])
    untriggered = max(0.0, cap - t_min) + 90.0 * horizon
    if card["stop_scope"] == "same_match":
        value = max(0.0, min(float(card["stop_t_min"]), cap) - t_min)
    elif card["stop_scope"] == "cross_match" and int(card["stop_gap_fixtures"]) < horizon:
        value = (
            max(0.0, cap - t_min)
            + 90.0 * int(card["stop_gap_fixtures"])
            + min(float(card["stop_t_min"]), 90.0)
        )
    else:
        # No stop, or a cross-match trigger beyond the caution's horizon: the
        # risk interval had already ended at the reset (or, for exact-clock
        # SF/final cautions, at the final whistle) before the trigger.
        value = untriggered
    if value > untriggered + 1e-9:
        raise ValueError(
            f"stop rule exceeded untriggered interval for {card.get('card_id', card)}: "
            f"{value} > {untriggered}"
        )
    return value


def _card_suspension_component(card: dict, rho: float, offset: float = 0.0) -> tuple[float, float]:
    """§3.2/§3.4: (ordinary-caution, dismissal) X_s components of one card."""
    if card["stage"] not in EXPOSURE_STAGES:
        return 0.0, 0.0
    if card["card_type"] == "Y":
        return _caution_interval(card, offset), 0.0
    value = rho * max(0.0, float(card["t_end_min"]) - offset - float(card["t_min"]))
    return 0.0, value


def _carried_in_cautions(
    tables: dict[str, list[dict[str, str]]], card_ledger: list[dict],
    primary: set[tuple[int, str]],
) -> list[dict]:
    """§3.2 carried-in cautions for 2014–2022.

    A knockout-stage player entering with exactly one pending group caution is
    priced as if that caution had been shown at minute 0 of the team's first
    knockout match. Pending means the caution's accumulation pair was not
    completed inside the group stage; a group dismissal does not consume a
    caution. The pseudo-caution's stop is the earliest suspension-causing
    knockout card of the player inside the same reset window.
    """
    stage_by_match = {
        (int(row["edition"]), int(row["match_number"])): row["stage"]
        for row in tables["fouls_team_match"]
    }
    first_knockout: dict[tuple[int, str], tuple[int, int, str]] = {}
    for row in tables["fouls_team_match"]:
        if not is_knockout(row["stage"]):
            continue
        key = (int(row["edition"]), row["team_id"])
        entry = (int(row["team_match_number"]), int(row["match_number"]), row["stage"])
        if key not in first_knockout or entry < first_knockout[key]:
            first_knockout[key] = entry
    team_match_number = {
        (int(row["edition"]), int(row["match_number"]), row["team_id"]): int(row["team_match_number"])
        for row in tables["fouls_team_match"]
    }

    by_player_window: dict[tuple, list[dict]] = defaultdict(list)
    for row in card_ledger:
        by_player_window[(_key(row), row["reset_window"])].append(row)

    pseudo_cards = []
    for row in card_ledger:
        if row["card_type"] != "Y" or row["stage"] != "group":
            continue
        edition = int(row["edition"])
        if edition == 2026:
            continue
        key = (edition, row["team_id"])
        if key not in primary:
            continue
        if row["paired_card_id"]:
            trigger = row["paired_card_id"]
            trigger_stage = next(
                stage_by_match[(edition, int(other["match_number"]))]
                for other in by_player_window[(_key(row), row["reset_window"])]
                if other["card_id"] == trigger
            )
            if trigger_stage == "group":
                continue  # consumed inside the group stage
        knockout_no, knockout_match, knockout_stage = first_knockout[key]
        pseudo = {
            "card_id": f"{row['card_id']}-carried",
            "edition": row["edition"], "match_number": str(knockout_match),
            "stage": knockout_stage, "team_id": row["team_id"], "team": row["team"],
            "player_id": row["player_id"], "player": row["player"],
            "card_type": "Y", "minute_label": "0'", "t_min": "0", "period": "3",
            "nominal_basis_min": "90", "t_end_min": row["t_end_min"],
            "base_horizon": _base_horizon(edition, knockout_stage, knockout_no),
            "stop_scope": "", "stop_card_id": "", "stop_match_number": "",
            "stop_t_min": "", "stop_gap_fixtures": "",
        }
        stoppers = []
        for other in by_player_window[(_key(row), row["reset_window"])]:
            if stage_by_match[(edition, int(other["match_number"]))] == "group":
                continue
            if other["card_type"] in {"Y2", "R"}:
                stoppers.append(other)
            elif other["card_id"] == row.get("paired_card_id"):
                stoppers.append(other)
        if stoppers:
            stopper = min(stoppers, key=_card_sort)
            stop_no = team_match_number[(edition, int(stopper["match_number"]), stopper["team_id"])]
            same_match = int(stopper["match_number"]) == knockout_match
            pseudo["stop_scope"] = "same_match" if same_match else "cross_match"
            pseudo["stop_card_id"] = stopper["card_id"]
            pseudo["stop_match_number"] = stopper["match_number"]
            pseudo["stop_t_min"] = stopper["t_min"]
            pseudo["stop_gap_fixtures"] = max(0, stop_no - knockout_no - 1) if not same_match else 0
        pseudo_cards.append(pseudo)
    return pseudo_cards


def stage7_suspension_exposure(
    tables: dict[str, list[dict[str, str]]], card_ledger: list[dict], suspensions: list[dict],
    omega_rows: list[dict], result_dir: Path = RESULTS,
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """Compute player/team E_s and the full rho×mu×denominator grid."""
    primary = _primary_teams(tables)
    omega = {_key(row): float(row["omega"]) for row in omega_rows}
    names = {_key(row): (row["team"], row["player"]) for row in omega_rows}
    cards_by_player: dict[tuple, list[dict]] = defaultdict(list)
    for card in card_ledger:
        cards_by_player[_key(card)].append(card)
    carried_by_player: dict[tuple, list[dict]] = defaultdict(list)
    for pseudo in _carried_in_cautions(tables, card_ledger, primary):
        carried_by_player[_key(pseudo)].append(pseudo)
        if _key(pseudo) not in cards_by_player:
            cards_by_player[_key(pseudo)] = []
    # §3.4: a suspension counts only when the service match is a knockout
    # match (the third-place match included); group service is group impact.
    served_matches: dict[tuple, set[int]] = defaultdict(set)
    for row in suspensions:
        if row["service_status"] == "served" and row["service_stage"] != "group":
            served_matches[_key(row)].add(int(row["service_match_number"]))
    # §3.6: foul denominators exclude the third-place match in both variants.
    foul_totals: dict[tuple[int, str], dict[str, int]] = defaultdict(lambda: {"all": 0, "knockout": 0})
    team_names = {}
    for row in tables["fouls_team_match"]:
        key = (int(row["edition"]), row["team_id"])
        team_names[key] = row["team"]
        if row["stage"] == "third_place":
            continue
        foul_totals[key]["all"] += int(row["fouls"])
        if is_knockout(row["stage"]):
            foul_totals[key]["knockout"] += int(row["fouls"])

    player_grid = []
    team_grid_accum: dict[tuple, float] = defaultdict(float)
    team_exposed_keys: dict[tuple, set[tuple]] = defaultdict(set)
    for key, player_cards in sorted(cards_by_player.items()):
        edition, team_id, player_id = key
        if key not in omega:
            raise ValueError(f"missing omega for exposed player {key}")
        for rho in RHO_GRID:
            ordinary = dismissal = carried = 0.0
            for card in player_cards:
                ordinary_piece, dismissal_piece = _card_suspension_component(card, rho)
                ordinary += ordinary_piece
                dismissal += dismissal_piece
            for pseudo in carried_by_player.get(key, []):
                carried += _caution_interval(pseudo)
            for mu in MU_GRID:
                served_count = len(served_matches.get(key, set()))
                served_min = 90.0 * mu * served_count
                unweighted = ordinary + carried + dismissal + served_min
                weighted = omega[key] * unweighted
                team, player = names[key]
                player_grid.append({
                    "edition": edition, "team_id": team_id, "team": team,
                    "player_id": player_id, "player": player,
                    "primary_cohort": "yes" if (edition, team_id) in primary else "no",
                    "rho": fmt(rho), "mu": fmt(mu), "ordinary_caution_min": fmt(ordinary),
                    "carried_in_caution_min": fmt(carried),
                    "dismissal_min": fmt(dismissal), "served_suspension_matches": served_count,
                    "served_suspension_min": fmt(served_min),
                    "unweighted_exp_susp_min": fmt(unweighted), "omega": fmt(omega[key], 9),
                    "exp_susp_min": fmt(weighted),
                })
                team_grid_accum[(edition, team_id, rho, mu)] += weighted
                if unweighted > 0:
                    team_exposed_keys[(edition, team_id, rho, mu)].add(key)

    team_grid = []
    for (edition, team_id, rho, mu), exposure in sorted(team_grid_accum.items()):
        fouls_all = foul_totals[(edition, team_id)]["all"]
        fouls_knockout = foul_totals[(edition, team_id)]["knockout"]
        exposed = team_exposed_keys.get((edition, team_id, rho, mu), set())
        team_grid.append({
            "edition": edition, "team_id": team_id, "team": team_names[(edition, team_id)],
            "primary_cohort": "yes" if (edition, team_id) in primary else "no",
            "rho": fmt(rho), "mu": fmt(mu),
            "exposed_players": len(exposed),
            "mean_omega": fmt(
                sum(omega[key] for key in exposed) / len(exposed), 9
            ) if exposed else "",
            "fouls_all": fouls_all,
            "fouls_knockout": fouls_knockout, "exp_susp_min": fmt(exposure),
            "exp_susp_per_foul_all": fmt(exposure / fouls_all if fouls_all else None),
            "exp_susp_per_foul_knockout": fmt(
                exposure / fouls_knockout if fouls_knockout else None
            ),
        })

    sensitivity = []
    for edition in EDITIONS:
        for rho in RHO_GRID:
            for mu in MU_GRID:
                selected = [
                    row for row in team_grid
                    if int(row["edition"]) == edition and float(row["rho"]) == rho
                    and float(row["mu"]) == mu and row["primary_cohort"] == "yes"
                ]
                for denominator in DENOMINATORS:
                    foul_field = "fouls_all" if denominator == "all" else "fouls_knockout"
                    exposure = sum(float(row["exp_susp_min"]) for row in selected)
                    fouls = sum(int(row[foul_field]) for row in selected)
                    sensitivity.append({
                        "edition": edition, "rho": fmt(rho), "mu": fmt(mu),
                        "denominator": denominator, "cohort": "knockout_teams",
                        "teams": len(selected), "exp_susp_min": fmt(exposure), "fouls": fouls,
                        "pooled_exp_susp_per_foul": fmt(exposure / fouls if fouls else None),
                    })

    primary_players = [
        row for row in player_grid
        if float(row["rho"]) == PRIMARY_RHO and float(row["mu"]) == PRIMARY_MU
    ]
    primary_teams = [
        row for row in team_grid
        if float(row["rho"]) == PRIMARY_RHO and float(row["mu"]) == PRIMARY_MU
    ]

    clock_team_accum: dict[tuple[int, str, str], float] = defaultdict(float)
    for key, player_cards in sorted(cards_by_player.items()):
        edition, team_id, _ = key
        for variant, offset in (("source_end", 0.0), ("end_minus_one", 1.0)):
            ordinary = dismissal = 0.0
            for card in player_cards:
                ordinary_piece, dismissal_piece = _card_suspension_component(
                    card, PRIMARY_RHO, offset
                )
                ordinary += ordinary_piece
                dismissal += dismissal_piece
            for pseudo in carried_by_player.get(key, []):
                ordinary += _caution_interval(pseudo, offset)
            served_min = 90.0 * PRIMARY_MU * len(served_matches.get(key, set()))
            clock_team_accum[(edition, team_id, variant)] += (
                omega[key] * (ordinary + dismissal + served_min)
            )
    clock_sensitivity = []
    for edition in EDITIONS:
        primary_team_ids = sorted(team_id for year, team_id in primary if year == edition)
        for variant in ("source_end", "end_minus_one"):
            exposure = sum(
                clock_team_accum[(edition, team_id, variant)] for team_id in primary_team_ids
            )
            for denominator in DENOMINATORS:
                foul_field = "all" if denominator == "all" else "knockout"
                fouls = sum(
                    foul_totals[(edition, team_id)][foul_field] for team_id in primary_team_ids
                )
                clock_sensitivity.append({
                    "edition": edition, "clock_variant": variant,
                    "rho": fmt(PRIMARY_RHO), "mu": fmt(PRIMARY_MU),
                    "denominator": denominator, "cohort": "knockout_teams",
                    "teams": len(primary_team_ids), "exp_susp_min": fmt(exposure),
                    "fouls": fouls,
                    "pooled_exp_susp_per_foul": fmt(exposure / fouls if fouls else None),
                })
    write_csv(result_dir / "player-suspension-exposure.csv", primary_players, PLAYER_SUSPENSION_FIELDS)
    write_csv(result_dir / "team-suspension-exposure.csv", primary_teams, TEAM_SUSPENSION_FIELDS)
    write_csv(result_dir / "suspension-sensitivity.csv", sensitivity, SENSITIVITY_FIELDS)
    write_csv(
        result_dir / "suspension-end-clock-sensitivity.csv",
        clock_sensitivity, SUSPENSION_END_CLOCK_FIELDS,
    )
    return primary_players, primary_teams, sensitivity, player_grid, clock_sensitivity


def _kendall_tau_b(pairs: list[tuple[float, float]]) -> float | None:
    """Kendall tau-b with tie correction; None when a margin is fully tied."""
    n = len(pairs)
    if n < 2:
        return None
    concordant = discordant = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            dx = (pairs[i][0] > pairs[j][0]) - (pairs[i][0] < pairs[j][0])
            dy = (pairs[i][1] > pairs[j][1]) - (pairs[i][1] < pairs[j][1])
            product = dx * dy
            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1
    pair_count = n * (n - 1) / 2
    x_counts: dict[float, int] = defaultdict(int)
    y_counts: dict[float, int] = defaultdict(int)
    for x_value, y_value in pairs:
        x_counts[x_value] += 1
        y_counts[y_value] += 1
    tied_x = sum(count * (count - 1) / 2 for count in x_counts.values())
    tied_y = sum(count * (count - 1) / 2 for count in y_counts.values())
    denominator = ((pair_count - tied_x) * (pair_count - tied_y)) ** 0.5
    if denominator == 0:
        return None
    return (concordant - discordant) / denominator


DEPTH_CHECK_SEED = 20260713
DEPTH_CHECK_PERMUTATIONS = 10_000


def stage7_depth_check(
    tables: dict[str, list[dict[str, str]]], team_rows: list[dict], result_dir: Path = RESULTS,
) -> list[dict]:
    """§5.1 prespecified per-edition depth check: matches played vs e_s.

    Editions are never pooled. Depth excludes the third-place match. The
    permutation p is two-sided with a fixed seed so rebuilds are
    deterministic.
    """
    import random

    played: dict[tuple[int, str], int] = defaultdict(int)
    for row in tables["fouls_team_match"]:
        if row["stage"] == "third_place":
            continue
        played[(int(row["edition"]), row["team_id"])] += 1

    output = []
    for edition in EDITIONS:
        pairs = []
        for row in team_rows:
            if int(row["edition"]) != edition or row["primary_cohort"] != "yes":
                continue
            rate = row["exp_susp_per_foul_all"]
            if rate in ("", None):
                continue
            pairs.append((float(played[(edition, row["team_id"])]), float(rate)))
        observed = _kendall_tau_b(pairs)
        p_value = None
        if observed is not None:
            rng = random.Random(DEPTH_CHECK_SEED)
            rates = [rate for _, rate in pairs]
            depths = [depth for depth, _ in pairs]
            extreme = 0
            for _ in range(DEPTH_CHECK_PERMUTATIONS):
                rng.shuffle(rates)
                permuted = _kendall_tau_b(list(zip(depths, rates)))
                if permuted is not None and abs(permuted) >= abs(observed) - 1e-12:
                    extreme += 1
            p_value = (1 + extreme) / (DEPTH_CHECK_PERMUTATIONS + 1)
        output.append({
            "edition": edition,
            "edition_status": "provisional_M100" if edition == 2026 else "final",
            "cohort": "knockout_teams", "teams": len(pairs),
            "depth_definition": "matches_played_excluding_third_place",
            "rho": fmt(PRIMARY_RHO), "mu": fmt(PRIMARY_MU), "denominator": "all",
            "tau_b": fmt(observed, 6) if observed is not None else "",
            "p_permutation": fmt(p_value, 6) if p_value is not None else "",
            "permutations": DEPTH_CHECK_PERMUTATIONS, "seed": DEPTH_CHECK_SEED,
            "note": (
                "2026 depth is truncated at the M100 cutoff; recompute after M104."
                if edition == 2026 else ""
            ),
        })
    write_csv(result_dir / "depth-check.csv", output, DEPTH_CHECK_FIELDS)
    return output


def stage8_validate_and_summarize(
    tables: dict[str, list[dict[str, str]]], card_ledger: list[dict], suspensions: list[dict],
    availability_rows: list[dict], omega_rows: list[dict], match_rows: list[dict], team_rows: list[dict],
    sensitivity: list[dict], depth_rows: list[dict] | None = None, result_dir: Path = RESULTS,
) -> tuple[list[dict], list[dict]]:
    """Apply frozen invariants and emit build-audit and edition-summary tables."""
    audit = []

    def add(edition, check, observed, expected, passed, note=""):
        audit.append({
            "edition": edition, "check": check, "observed": observed, "expected": expected,
            "status": "PASS" if passed else "FAIL", "note": note,
        })
        if not passed:
            raise ValueError(f"{edition} {check}: observed {observed}, expected {expected}")

    source_card_lookup = {row["card_id"]: row for row in tables["cards"]}
    expected_reason_ids = {
        row["card_id"] for row in tables["cards"]
        if row["recipient_type"] == "player" and row["event_scope"] == "in_play"
    }
    reason_rows = tables["card_reasons"]
    reason_ids = [row["card_id"] for row in reason_rows]
    reason_coverage_ok = (
        len(reason_ids) == len(set(reason_ids))
        and set(reason_ids) == expected_reason_ids
    )
    add(
        "all", "card_reason_exact_coverage", len(reason_ids), len(expected_reason_ids),
        reason_coverage_ok,
        "Exactly one reason row is required for every in-play player card.",
    )
    reason_classes = {
        "foul_play", "dissent", "time_wasting", "other_nonfoul", "unknown",
    }
    source_tiers = {
        "1_fifa", "2_federation_or_club", "3_established_mbm",
        "4_documented_fallback",
    }
    sb_statuses = {"yes", "no", "unmatched", "not_available"}
    evidence_ok = all(
        row["reason_class"] in reason_classes
        and row["source_tier"] in source_tiers
        and row["sb_foul_linked"] in sb_statuses
        and row["source_url"].startswith(("https://", "http://"))
        and bool(row["note"].strip())
        for row in reason_rows
    )
    add(
        "all", "card_reason_evidence_fields", int(evidence_ok), 1, evidence_ok,
        "Classes, StatsBomb status, source tier, URL, and evidence note are validated.",
    )
    sb_scope_ok = all(
        (
            row["sb_foul_linked"] == "not_available"
            if int(source_card_lookup[row["card_id"]]["edition"]) in {2014, 2026}
            else row["sb_foul_linked"] != "not_available"
        )
        for row in reason_rows
    )
    add(
        "all", "card_reason_statsbomb_scope", int(sb_scope_ok), 1, sb_scope_ok,
        "2018/2022 require reconciliation; 2014/2026 are marked not_available.",
    )
    sb_conflicts = [
        row for row in reason_rows
        if (
            row["sb_foul_linked"] == "unmatched"
            or (
                row["reason_class"] == "foul_play"
                and row["sb_foul_linked"] == "no"
            )
            or (
                row["reason_class"] in {"dissent", "time_wasting", "other_nonfoul"}
                and row["sb_foul_linked"] == "yes"
            )
        )
    ]
    unflagged_conflicts = [row for row in sb_conflicts if "AUDIT" not in row["note"]]
    add(
        "all", "card_reason_conflicts_flagged", len(unflagged_conflicts), 0,
        not unflagged_conflicts,
        "StatsBomb disagreements and unmatched cards must be labeled AUDIT.",
    )
    audit.append({
        "edition": "2018/2022", "check": "statsbomb_card_reason_reconciliation",
        "observed": len(sb_conflicts), "expected": 0,
        "status": "AUDIT" if sb_conflicts else "PASS",
        "note": "Disagreements remain visible and are not silently merged.",
    })
    sb_conflict_ids = {row["card_id"] for row in sb_conflicts}
    other_reason_audits = [
        row for row in reason_rows
        if "AUDIT" in row["note"] and row["card_id"] not in sb_conflict_ids
    ]
    audit.append({
        "edition": "all", "check": "card_reason_other_source_audits",
        "observed": len(other_reason_audits), "expected": 0,
        "status": "AUDIT" if other_reason_audits else "PASS",
        "note": "Written-source conflicts remain visible and separate from StatsBomb reconciliation.",
    })
    sb_reconciliation_rows = tables["card_reason_sb_reconciliation"]
    status_for_type = {"Foul Committed": "yes", "Bad Behaviour": "no"}
    sb_reconciliation_ok = all(
        int(row["in_play_census_events"]) == sum(
            reason["sb_foul_linked"] == status_for_type[row["event_type"]]
            and reason["card_id"].startswith(f"{row['edition']}-")
            for reason in reason_rows
        )
        and int(row["in_play_census_events"])
        + int(row["outside_in_play_census_events"])
        == int(row["all_card_events"])
        for row in sb_reconciliation_rows
    )
    add(
        "2018/2022", "statsbomb_card_reason_aggregate_reconciliation",
        len(sb_reconciliation_rows), len(EXPECTED_CARD_REASON_SB_RECONCILIATION),
        sb_reconciliation_ok,
        "Four aggregate conclusions reconcile the private event ledger without "
        "redistributing event-level StatsBomb data.",
    )

    for edition in EDITIONS:
        year_cards = [row for row in card_ledger if int(row["edition"]) == edition]
        add(edition, "player_card_count", len(year_cards), EXPECTED_PLAYER_CARDS[edition],
            len(year_cards) == EXPECTED_PLAYER_CARDS[edition])
        matches = {int(row["match_number"]) for row in tables["matches"] if int(row["edition"]) == edition}
        add(edition, "included_match_count", len(matches), EXPECTED_COMPLETED[edition],
            len(matches) == EXPECTED_COMPLETED[edition])
        horizon_ok = all(int(row["effective_horizon"]) <= int(row["base_horizon"]) for row in year_cards)
        add(edition, "horizon_stop_rule", int(horizon_ok), 1, horizon_ok)
        omega_values = [float(row["omega"]) for row in omega_rows if int(row["edition"]) == edition]
        omega_ok = bool(omega_values) and all(0 <= value <= 1 for value in omega_values)
        add(edition, "omega_bounds", int(omega_ok), 1, omega_ok,
            f"min={min(omega_values):.9f}; max={max(omega_values):.9f}")
        exposure_ok = all(float(row["exp_match_min"] or 0) >= 0 for row in match_rows if int(row["edition"]) == edition)
        exposure_ok = exposure_ok and all(
            float(row["exp_susp_min"] or 0) >= 0 for row in team_rows if int(row["edition"]) == edition
        )
        add(edition, "nonnegative_exposure", int(exposure_ok), 1, exposure_ok)
        primary_match = [row for row in match_rows if int(row["edition"]) == edition]
        lookup = {(int(row["match_number"]), row["team_id"]): row for row in primary_match}
        anti_ok = all(
            abs(float(row["d_exp_match"]) + float(lookup[(int(row["match_number"]), row["opponent_team_id"])]["d_exp_match"])) < 1e-7
            for row in primary_match
        )
        add(edition, "match_delta_antisymmetry", int(anti_ok), 1, anti_ok)
        cutoff_ok = edition != 2026 or all(
            int(row["match_number"]) <= 100 for row in match_rows if int(row["edition"]) == 2026
        )
        add(edition, "2026_m100_cutoff", int(cutoff_ok), 1, cutoff_ok)
        scope_ok = all(
            row["stage"] in EXPOSURE_STAGES
            for row in match_rows if int(row["edition"]) == edition
        )
        add(edition, "match_rows_knockout_non_third_only", int(scope_ok), 1, scope_ok,
            "E_m rows cover knockout matches other than the third-place match.")

    group_service = [
        row for row in suspensions
        if row["service_status"] == "served" and row["service_stage"] == "group"
    ]
    audit.append({
        "edition": "all", "check": "group_service_excluded_from_x_s",
        "observed": len(group_service), "expected": "excluded",
        "status": "PASS",
        "note": "Group-served suspensions stay in the ledger but add no μ term (§3.4).",
    })
    if depth_rows is not None:
        expected_depth_teams = {2014: 16, 2018: 16, 2022: 16, 2026: 32}
        for row in depth_rows:
            edition = int(row["edition"])
            add(edition, "depth_check_team_count", int(row["teams"]),
                expected_depth_teams[edition], int(row["teams"]) == expected_depth_teams[edition])

    for row in tables["availability_evidence"]:
        if float(row["unavailable_minutes"]) > 0 and not row["source_url"]:
            raise ValueError(f"injury evidence URL invariant failed: {row}")
    audit.append({
        "edition": "all", "check": "positive_injury_url", "observed": "all",
        "expected": "all", "status": "PASS", "note": "Every positive interval has a URL."
    })
    unexplained = [row for row in availability_rows if row["availability_status"] == "unexplained"]
    audit.append({
        "edition": "all", "check": "unexplained_availability_rows",
        "observed": len(unexplained), "expected": 0,
        "status": "PASS" if not unexplained else "AUDIT",
        "note": "Unexplained is permitted but remains visible and contributes no injury interval.",
    })

    conflicts = [row for row in suspensions if row["service_status"] == "conflict"]
    conflict_note = "No suspension-lineup conflicts."
    if conflicts:
        conflict_note = "Conflicts are retained and excluded from served terms: " + "; ".join(
            f"{row['edition']} M{row['trigger_match_number']} {row['player']}"
            for row in conflicts
        )
    audit.append({
        "edition": "all", "check": "suspension_lineup_conflicts", "observed": len(conflicts),
        "expected": 0, "status": "PASS" if not conflicts else "AUDIT",
        "note": conflict_note,
    })
    decision_rows = [row for row in suspensions if row["decision_type"]]
    audit.append({
        "edition": "all", "check": "documented_sanction_decisions",
        "observed": len({row["decision_source_url"] for row in decision_rows}),
        "expected": len(tables["sanction_decisions"]), "status": "PASS",
        "note": "Sourced overrides are retained alongside lineup verification.",
    })

    summaries = []
    for edition in EDITIONS:
        primary_sensitivity = next(
            row for row in sensitivity
            if int(row["edition"]) == edition and float(row["rho"]) == PRIMARY_RHO
            and float(row["mu"]) == PRIMARY_MU and row["denominator"] == "all"
        )
        summaries.append({
            "edition": edition,
            "included_matches": sum(1 for row in tables["matches"] if int(row["edition"]) == edition),
            "player_cards": sum(1 for row in card_ledger if int(row["edition"]) == edition),
            "in_play_player_cards": sum(
                1 for row in card_ledger if int(row["edition"]) == edition and row["event_scope"] == "in_play"
            ),
            "team_fouls": sum(int(row["fouls"]) for row in tables["fouls_team_match"] if int(row["edition"]) == edition),
            "knockout_teams": int(primary_sensitivity["teams"]),
            "served_suspension_matches": sum(
                1 for row in suspensions if int(row["edition"]) == edition and row["service_status"] == "served"
            ),
            "deferred_suspensions": sum(
                1 for row in suspensions
                if int(row["edition"]) == edition and row["service_status"] == "deferred"
            ),
            "suspension_conflicts": sum(
                1 for row in suspensions if int(row["edition"]) == edition and row["service_status"] == "conflict"
            ),
            "rho": fmt(PRIMARY_RHO), "mu": fmt(PRIMARY_MU),
            "pooled_exp_susp_per_foul": primary_sensitivity["pooled_exp_susp_per_foul"],
        })
    write_csv(result_dir / "build-audit.csv", audit, BUILD_AUDIT_FIELDS)
    write_csv(result_dir / "edition-summary.csv", summaries, EDITION_SUMMARY_FIELDS)
    return audit, summaries


def run_stages(source_dir: Path = SOURCE, stage_dir: Path = STAGES, result_dir: Path = RESULTS) -> dict:
    """Run all eight stages and return materialized tables for reporting."""
    tables = _source_tables(source_dir)
    cards = stage1_cards(tables, stage_dir)
    fouls = stage2_fouls(tables, stage_dir)
    minutes = stage3_minutes(tables, stage_dir)
    suspensions = stage4_suspensions(tables, cards, stage_dir)
    availability, omega = stage5_availability(tables, cards, suspensions, stage_dir)
    match_rows, match_sensitivity, match_clock_sensitivity = stage6_match_exposure(
        tables, cards, result_dir
    )
    player_rows, team_rows, sensitivity, player_grid, suspension_clock_sensitivity = stage7_suspension_exposure(
        tables, cards, suspensions, omega, result_dir
    )
    depth = stage7_depth_check(tables, team_rows, result_dir)
    audit, summaries = stage8_validate_and_summarize(
        tables, cards, suspensions, availability, omega, match_rows, team_rows, sensitivity,
        depth, result_dir
    )
    # Imported here so the base-stage helpers above are fully defined before
    # the amendment module reuses them; this avoids a module-load cycle.
    from .expanded import run_expanded_stages

    expanded = run_expanded_stages(
        tables, cards, suspensions, omega, team_rows, stage_dir, result_dir
    )
    return {
        "source": tables, "cards": cards, "fouls": fouls, "minutes": minutes,
        "suspensions": suspensions, "availability": availability, "omega": omega,
        "match": match_rows, "match_sensitivity": match_sensitivity,
        "match_clock_sensitivity": match_clock_sensitivity,
        "players": player_rows, "teams": team_rows, "sensitivity": sensitivity,
        "suspension_clock_sensitivity": suspension_clock_sensitivity,
        "player_grid": player_grid, "depth": depth, "audit": audit, "summaries": summaries,
        **expanded,
    }
