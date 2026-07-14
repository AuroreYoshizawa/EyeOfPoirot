"""Frozen expanded-cohort amendment computations (2026-07-14).

All computations are standard-library-only and edition-specific.  The module
adds labeled robustness/secondary outputs; it never overwrites the v0.2.1
primary tables.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from pathlib import Path

from ..config import EDITIONS, PRIMARY_MU, PRIMARY_RHO, RESULTS, STAGES, is_knockout
from ..event_sources import SEGMENTS
from ..io import fmt, write_csv
from .stages import (
    CARD_LEDGER_FIELDS,
    EXPOSURE_STAGES,
    SUSPENSION_FIELDS,
    _card_sort,
    _card_suspension_component,
    _carried_in_cautions,
    _caution_interval,
    _caution_is_exact,
    _key,
    _primary_teams,
    stage1_cards,
    stage4_suspensions,
)


STRIPPED_REASONS = {"dissent", "time_wasting"}
EXPANDED_LAMBDA = 0.5
MD2_LAMBDAS = (1.0, 1.5, 2.0)
TIMING_RED_WEIGHT = 2.5
TIMING_PERMUTATIONS = 2_000
CORRELATION_PERMUTATIONS = 10_000
AMENDMENT_SEED = 20260713

EXPANDED_PLAYER_FIELDS = (
    "edition", "edition_status", "ledger", "team_id", "team", "player_id",
    "player", "rho", "mu", "lambda", "omega",
    "group_caution_min", "group_dismissal_min", "group_served_matches",
    "group_served_min", "knockout_in_match_min",
    "knockout_accumulation_window_min", "knockout_served_matches",
    "knockout_served_min", "exp_susp_grp_unweighted_min",
    "exp_susp_unweighted_min", "exp_susp_all_unweighted_min",
    "exact_clock_q_min", "exp_susp_prime_unweighted_min",
    "exp_susp_grp_min", "exp_susp_min", "exp_susp_all_min",
    "exp_susp_prime_min",
)

STRIPPED_CARD_FIELDS = (
    "card_id", "edition", "edition_status", *CARD_LEDGER_FIELDS[2:],
)
STRIPPED_SUSPENSION_FIELDS = (
    "suspension_id", "edition", "edition_status", *SUSPENSION_FIELDS[2:],
)

EXPANDED_TEAM_FIELDS = (
    "edition", "edition_status", "ledger", "cohort", "team_id", "team",
    "rho", "mu", "lambda", "fouls_all",
    "exp_susp_in_match_min", "exp_susp_accumulation_window_min",
    "exp_susp_served_min", "exp_susp_grp_min", "exp_susp_min",
    "exp_susp_all_min", "exp_susp_prime_min",
    "exp_susp_grp_per_foul", "exp_susp_per_foul",
    "exp_susp_all_per_foul", "exp_susp_prime_per_foul",
    "rank_exp_susp_grp_per_foul", "rank_exp_susp_per_foul",
    "rank_exp_susp_all_per_foul", "rank_exp_susp_prime_per_foul",
    "teams",
)

MD2_FIELDS = (
    "edition", "edition_status", "cohort", "team_id", "team", "lambda_md2",
    "card_events", "fouls_md2", "exp_susp_md2_min",
    "exp_susp_md2_per_foul", "rank", "teams", "match_scope",
)

TIMING_FIELDS = (
    "edition", "edition_status", "ledger", "event_scope", "cohort",
    "team_id", "team", "card_events", "foul_events", "red_weight",
    "mean_card_segment", "mean_foul_segment", "delta", "p_delta", "q_delta",
    "w1", "p_w1", "q_w1", "bh_m", "evidentiary_status", "source_status",
    "permutations", "seed", "note",
)

CORRELATION_FIELDS = (
    "edition", "edition_status", "ledger", "cohort", "metric", "outcome",
    "teams", "tau_b", "p_permutation", "permutations", "seed", "note",
)

CUMULATIVE_CARD_FIELDS = (
    "edition", "edition_status", "card_id", "match_number", "stage", "team_id",
    "team", "player_id", "player", "card_type", "minute_label", "reason_class",
    "provider", "reconciliation_status", "fouls_strictly_before_card",
    "foul_linked", "fouls_through_card", "provenance_status",
    "official_source_url", "event_source_url",
)

CUMULATIVE_TEAM_MATCH_FIELDS = (
    "edition", "edition_status", "match_number", "stage", "team_id", "team",
    "provider", "has_in_play_player_card", "first_card_id",
    "fouls_before_first_card", "status", "source_url",
)

EXPANDED_AUDIT_FIELDS = (
    "edition", "edition_status", "check", "observed", "expected", "status", "note",
)


def edition_status(edition: int) -> str:
    return "provisional_M100" if edition == 2026 else "final"


def stripped_source_tables(
    tables: dict[str, list[dict[str, str]]]
) -> tuple[dict[str, list[dict[str, str]]], set[str]]:
    removed = {
        row["card_id"] for row in tables["card_reasons"]
        if row["reason_class"] in STRIPPED_REASONS
    }
    stripped = {name: list(rows) for name, rows in tables.items()}
    stripped["cards"] = [
        row for row in tables["cards"] if row["card_id"] not in removed
    ]
    return stripped, removed


def build_stripped_ledger(
    tables: dict[str, list[dict[str, str]]], stage_dir: Path = STAGES,
) -> tuple[list[dict], list[dict], set[str]]:
    stripped_tables, removed = stripped_source_tables(tables)
    ledger = stage1_cards(
        stripped_tables, stage_dir, "s9-stripped-card-ledger.csv"
    )
    for row in ledger:
        row["edition_status"] = edition_status(int(row["edition"]))
    write_csv(
        stage_dir / "s9-stripped-card-ledger.csv", ledger, STRIPPED_CARD_FIELDS
    )
    suspensions = stage4_suspensions(
        stripped_tables, ledger, stage_dir, "s10-stripped-suspensions.csv"
    )
    for row in suspensions:
        row["edition_status"] = edition_status(int(row["edition"]))
    write_csv(
        stage_dir / "s10-stripped-suspensions.csv",
        suspensions, STRIPPED_SUSPENSION_FIELDS,
    )
    return ledger, suspensions, removed


def _team_match_numbers(tables: dict[str, list[dict[str, str]]]) -> dict[tuple[int, int, str], int]:
    return {
        (int(row["edition"]), int(row["match_number"]), row["team_id"]):
        int(row["team_match_number"])
        for row in tables["fouls_team_match"]
    }


def _group_components(
    tables: dict[str, list[dict[str, str]]], ledger: list[dict]
) -> tuple[dict[tuple[int, str, str], dict[str, float]], dict[str, dict]]:
    """Compute group-only components and retain per-card L_grp/q audit data."""
    team_match_no = _team_match_numbers(tables)
    components: dict[tuple[int, str, str], dict[str, float]] = defaultdict(
        lambda: {"caution": 0.0, "dismissal": 0.0, "q": 0.0}
    )
    card_audit: dict[str, dict] = {}
    by_player: dict[tuple[int, str, str], list[dict]] = defaultdict(list)
    for card in ledger:
        if card["stage"] == "group" and card["event_scope"] == "in_play":
            by_player[_key(card)].append(card)

    for key, player_cards in by_player.items():
        ordered = sorted(player_cards, key=_card_sort)
        same_match_first: set[str] = set()
        same_match_pair: dict[str, dict] = {}
        by_match: dict[int, list[dict]] = defaultdict(list)
        for card in ordered:
            by_match[int(card["match_number"])].append(card)
        for match_cards in by_match.values():
            event_rows = sorted(match_cards, key=_card_sort)
            for dismissal in (row for row in event_rows if row["card_type"] == "Y2"):
                candidates = [
                    row for row in event_rows
                    if row["card_type"] == "Y"
                    and float(row["t_min"]) <= float(dismissal["t_min"])
                    and row["card_id"] not in same_match_first
                ]
                if not candidates:
                    raise ValueError(
                        f"group Y2 lacks a retained first caution: {dismissal['card_id']}"
                    )
                first = candidates[-1]
                same_match_first.add(first["card_id"])
                same_match_pair[first["card_id"]] = dismissal

        accumulation_pair: dict[str, dict] = {}
        ordinary = [
            row for row in ordered
            if row["card_type"] == "Y" and row["card_id"] not in same_match_first
        ]
        for index in range(0, len(ordinary) - 1, 2):
            accumulation_pair[ordinary[index]["card_id"]] = ordinary[index + 1]

        for index, card in enumerate(ordered):
            player_component = components[key]
            if card["card_type"] in {"R", "Y2"}:
                dismissal = PRIMARY_RHO * max(
                    0.0, float(card["t_end_min"]) - float(card["t_min"])
                )
                player_component["dismissal"] += dismissal
                card_audit[card["card_id"]] = {
                    "kind": "dismissal", "l_grp": 0.0, "q": 0.0,
                    "stop_card_id": "", "untriggered": 0.0,
                }
                continue
            if card["card_type"] != "Y":
                continue
            t_min = float(card["t_min"])
            t_end = float(card["t_end_min"])
            team_number = team_match_no[(
                int(card["edition"]), int(card["match_number"]), card["team_id"]
            )]
            horizon = max(0, 3 - team_number)
            receipt = max(0.0, t_end - t_min) if "+" in card["minute_label"] else max(0.0, 90.0 - t_min)
            untriggered = receipt + 90.0 * horizon
            stoppers = [
                later for later in ordered[index + 1:]
                if later["card_type"] in {"R", "Y2"}
            ]
            if card["card_id"] in same_match_pair:
                stoppers.append(same_match_pair[card["card_id"]])
            if card["card_id"] in accumulation_pair:
                stoppers.append(accumulation_pair[card["card_id"]])
            stopper = min(stoppers, key=_card_sort) if stoppers else None
            if stopper is None:
                value = untriggered
            elif int(stopper["match_number"]) == int(card["match_number"]):
                cap = t_end if "+" in card["minute_label"] else 90.0
                value = max(0.0, min(float(stopper["t_min"]), cap) - t_min)
            else:
                stop_team_number = team_match_no[(
                    int(stopper["edition"]), int(stopper["match_number"]), stopper["team_id"]
                )]
                gap = max(0, stop_team_number - team_number - 1)
                value = receipt + 90.0 * gap + min(float(stopper["t_min"]), 90.0)
            value = min(value, untriggered)
            if value < -1e-9 or value > untriggered + 1e-9:
                raise ValueError(
                    f"invalid L_grp for {card['card_id']}: {value} / {untriggered}"
                )
            q = (
                max(0.0, min(float(stopper["t_min"]), t_end) - t_min)
                if stopper is not None
                and int(stopper["match_number"]) == int(card["match_number"])
                else max(0.0, t_end - t_min)
            )
            player_component["caution"] += value
            player_component["q"] += q
            card_audit[card["card_id"]] = {
                "kind": "caution", "l_grp": value, "q": q,
                "stop_card_id": stopper["card_id"] if stopper else "",
                "untriggered": untriggered,
            }
    return components, card_audit


def _knockout_components(card: dict) -> tuple[float, float]:
    """Return (in-match, accumulation-window) for one frozen E_s card term."""
    ordinary, dismissal = _card_suspension_component(card, PRIMARY_RHO)
    if dismissal:
        return dismissal, 0.0
    if not ordinary:
        return 0.0, 0.0
    t_min = float(card["t_min"])
    if card["stop_scope"] == "same_match":
        return ordinary, 0.0
    cap = float(card["t_end_min"]) if _caution_is_exact(card) else float(card["nominal_basis_min"])
    first_match = min(ordinary, max(0.0, cap - t_min))
    return first_match, max(0.0, ordinary - first_match)


def _exact_q(card: dict) -> float:
    t_min = float(card["t_min"])
    t_end = float(card["t_end_min"])
    if card.get("stop_scope") == "same_match":
        return max(0.0, min(float(card["stop_t_min"]), t_end) - t_min)
    return max(0.0, t_end - t_min)


def _foul_totals(tables: dict[str, list[dict[str, str]]]) -> dict[tuple[int, str], int]:
    totals: dict[tuple[int, str], int] = defaultdict(int)
    for row in tables["fouls_team_match"]:
        if row["stage"] != "third_place":
            totals[(int(row["edition"]), row["team_id"])] += int(row["fouls"])
    return totals


def _team_universe(tables: dict[str, list[dict[str, str]]]) -> dict[tuple[int, str], str]:
    return {
        (int(row["edition"]), row["team_id"]): row["team"]
        for row in tables["fouls_team_match"]
    }


def stage_expanded_exposure(
    tables: dict[str, list[dict[str, str]]],
    ledgers: dict[str, list[dict]],
    suspensions: dict[str, list[dict]],
    omega_rows: list[dict],
    stage_dir: Path = STAGES,
    result_dir: Path = RESULTS,
) -> tuple[list[dict], list[dict], dict[str, dict[str, dict]]]:
    """Compute E_s^grp, E_s^all, E_s', and stripped counterparts."""
    omega = {_key(row): float(row["omega"]) for row in omega_rows}
    player_names = {
        _key(row): (row["team"], row["player"]) for row in omega_rows
    }
    universe = _team_universe(tables)
    foul_totals = _foul_totals(tables)
    primary = _primary_teams(tables)
    match_lookup = {
        (int(row["edition"]), int(row["match_number"])): row
        for row in tables["matches"]
    }

    player_rows: list[dict] = []
    team_accum: dict[tuple[int, str, str], dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    group_card_audits: dict[str, dict[str, dict]] = {}

    for ledger_name in ("full", "stripped"):
        ledger = ledgers[ledger_name]
        suspension_rows = suspensions[ledger_name]
        group_components, group_card_audit = _group_components(tables, ledger)
        group_card_audits[ledger_name] = group_card_audit
        cards_by_player: dict[tuple[int, str, str], list[dict]] = defaultdict(list)
        for card in ledger:
            cards_by_player[_key(card)].append(card)
        carried_by_player: dict[tuple[int, str, str], list[dict]] = defaultdict(list)
        for pseudo in _carried_in_cautions(tables, ledger, primary):
            # The frozen E_s interval is nominal in the proxy match, but q(c)
            # needs that match's observed final clock rather than the original
            # group match clock carried by the source card.
            proxy = dict(pseudo)
            proxy_match = match_lookup[(int(proxy["edition"]), int(proxy["match_number"]))]
            proxy["t_end_min"] = proxy_match["t_end_min"]
            carried_by_player[_key(proxy)].append(proxy)

        served_group: dict[tuple[int, str, str], set[int]] = defaultdict(set)
        served_knockout: dict[tuple[int, str, str], set[int]] = defaultdict(set)
        for suspension in suspension_rows:
            if suspension["service_status"] != "served":
                continue
            destination = served_group if suspension["service_stage"] == "group" else served_knockout
            destination[_key(suspension)].add(int(suspension["service_match_number"]))

        for key in sorted(omega):
            edition, team_id, player_id = key
            team, player = player_names[key]
            group = group_components.get(
                key, {"caution": 0.0, "dismissal": 0.0, "q": 0.0}
            )
            group_served_count = len(served_group.get(key, set()))
            group_served_min = 90.0 * PRIMARY_MU * group_served_count
            group_unweighted = group["caution"] + group["dismissal"] + group_served_min

            knockout_in_match = 0.0
            knockout_window = 0.0
            exact_q = group["q"]
            for card in cards_by_player.get(key, []):
                in_match, window = _knockout_components(card)
                knockout_in_match += in_match
                knockout_window += window
                if (
                    ledger_name == "full"
                    and card["stage"] in EXPOSURE_STAGES
                    and card["card_type"] == "Y"
                ):
                    exact_q += _exact_q(card)
            for pseudo in carried_by_player.get(key, []):
                carried = _caution_interval(pseudo)
                # The disclosed component split assigns the whole carried-in
                # proxy to the accumulation-window component.
                knockout_window += carried
                if ledger_name == "full":
                    exact_q += _exact_q(pseudo)

            knockout_served_count = len(served_knockout.get(key, set()))
            knockout_served_min = 90.0 * PRIMARY_MU * knockout_served_count
            knockout_unweighted = knockout_in_match + knockout_window + knockout_served_min
            all_unweighted = group_unweighted + knockout_unweighted
            prime_unweighted = (
                all_unweighted + EXPANDED_LAMBDA * exact_q
                if ledger_name == "full" else None
            )
            weight = omega[key]
            weighted = {
                "in_match": weight * knockout_in_match,
                "window": weight * knockout_window,
                "served": weight * knockout_served_min,
                "group": weight * group_unweighted,
                "knockout": weight * knockout_unweighted,
                "all": weight * all_unweighted,
                "prime": weight * prime_unweighted if prime_unweighted is not None else None,
            }
            accumulator = team_accum[(edition, team_id, ledger_name)]
            for name in ("in_match", "window", "served", "group", "knockout", "all"):
                accumulator[name] += weighted[name]
            if weighted["prime"] is not None:
                accumulator["prime"] += weighted["prime"]

            player_rows.append({
                "edition": edition,
                "edition_status": edition_status(edition),
                "ledger": ledger_name,
                "team_id": team_id,
                "team": team,
                "player_id": player_id,
                "player": player,
                "rho": fmt(PRIMARY_RHO),
                "mu": fmt(PRIMARY_MU),
                "lambda": fmt(EXPANDED_LAMBDA) if ledger_name == "full" else "",
                "omega": fmt(weight, 9),
                "group_caution_min": fmt(group["caution"]),
                "group_dismissal_min": fmt(group["dismissal"]),
                "group_served_matches": group_served_count,
                "group_served_min": fmt(group_served_min),
                "knockout_in_match_min": fmt(knockout_in_match),
                "knockout_accumulation_window_min": fmt(knockout_window),
                "knockout_served_matches": knockout_served_count,
                "knockout_served_min": fmt(knockout_served_min),
                "exp_susp_grp_unweighted_min": fmt(group_unweighted),
                "exp_susp_unweighted_min": fmt(knockout_unweighted),
                "exp_susp_all_unweighted_min": fmt(all_unweighted),
                "exact_clock_q_min": fmt(exact_q) if ledger_name == "full" else "",
                "exp_susp_prime_unweighted_min": (
                    fmt(prime_unweighted) if prime_unweighted is not None else ""
                ),
                "exp_susp_grp_min": fmt(weighted["group"]),
                "exp_susp_min": fmt(weighted["knockout"]),
                "exp_susp_all_min": fmt(weighted["all"]),
                "exp_susp_prime_min": (
                    fmt(weighted["prime"]) if weighted["prime"] is not None else ""
                ),
            })

    raw_team_rows: list[dict] = []
    for (edition, team_id), team in sorted(universe.items()):
        for ledger_name in ("full", "stripped"):
            values = team_accum[(edition, team_id, ledger_name)]
            fouls = foul_totals[(edition, team_id)]
            if fouls <= 0:
                raise ValueError(f"non-positive expanded-cohort foul denominator: {(edition, team_id)}")
            raw_team_rows.append({
                "edition": edition,
                "edition_status": edition_status(edition),
                "ledger": ledger_name,
                "cohort": "all_teams",
                "team_id": team_id,
                "team": team,
                "rho": PRIMARY_RHO,
                "mu": PRIMARY_MU,
                "lambda": EXPANDED_LAMBDA if ledger_name == "full" else None,
                "fouls_all": fouls,
                "in_match": values["in_match"],
                "window": values["window"],
                "served": values["served"],
                "group": values["group"],
                "knockout": values["knockout"],
                "all": values["all"],
                "prime": values["prime"] if ledger_name == "full" else None,
                "group_rate": values["group"] / fouls,
                "knockout_rate": values["knockout"] / fouls,
                "all_rate": values["all"] / fouls,
                "prime_rate": values["prime"] / fouls if ledger_name == "full" else None,
            })

    rank_fields = {
        "group_rate": "rank_group",
        "knockout_rate": "rank_knockout",
        "all_rate": "rank_all",
        "prime_rate": "rank_prime",
    }
    for edition in EDITIONS:
        for ledger_name in ("full", "stripped"):
            selected = [
                row for row in raw_team_rows
                if row["edition"] == edition and row["ledger"] == ledger_name
            ]
            for value_field, rank_field in rank_fields.items():
                if value_field == "prime_rate" and ledger_name == "stripped":
                    for row in selected:
                        row[rank_field] = None
                    continue
                ordered = sorted(
                    selected, key=lambda row: (-row[value_field], row["team"], row["team_id"])
                )
                for rank, row in enumerate(ordered, start=1):
                    row[rank_field] = rank

    team_rows = []
    edition_team_counts = Counter(edition for edition, _ in universe)
    for row in sorted(
        raw_team_rows,
        key=lambda item: (item["edition"], item["ledger"], item["rank_all"]),
    ):
        team_rows.append({
            "edition": row["edition"],
            "edition_status": row["edition_status"],
            "ledger": row["ledger"],
            "cohort": row["cohort"],
            "team_id": row["team_id"],
            "team": row["team"],
            "rho": fmt(row["rho"]),
            "mu": fmt(row["mu"]),
            "lambda": fmt(row["lambda"]) if row["lambda"] is not None else "",
            "fouls_all": row["fouls_all"],
            "exp_susp_in_match_min": fmt(row["in_match"]),
            "exp_susp_accumulation_window_min": fmt(row["window"]),
            "exp_susp_served_min": fmt(row["served"]),
            "exp_susp_grp_min": fmt(row["group"]),
            "exp_susp_min": fmt(row["knockout"]),
            "exp_susp_all_min": fmt(row["all"]),
            "exp_susp_prime_min": fmt(row["prime"]) if row["prime"] is not None else "",
            "exp_susp_grp_per_foul": fmt(row["group_rate"]),
            "exp_susp_per_foul": fmt(row["knockout_rate"]),
            "exp_susp_all_per_foul": fmt(row["all_rate"]),
            "exp_susp_prime_per_foul": (
                fmt(row["prime_rate"]) if row["prime_rate"] is not None else ""
            ),
            "rank_exp_susp_grp_per_foul": row["rank_group"],
            "rank_exp_susp_per_foul": row["rank_knockout"],
            "rank_exp_susp_all_per_foul": row["rank_all"],
            "rank_exp_susp_prime_per_foul": row["rank_prime"] or "",
            "teams": edition_team_counts[row["edition"]],
        })

    write_csv(
        stage_dir / "s11-expanded-player-suspension-exposure.csv",
        player_rows, EXPANDED_PLAYER_FIELDS,
    )
    write_csv(
        result_dir / "expanded-suspension-exposure.csv",
        team_rows, EXPANDED_TEAM_FIELDS,
    )
    return player_rows, team_rows, group_card_audits


def stage_md2_exposure(
    tables: dict[str, list[dict[str, str]]],
    full_ledger: list[dict],
    omega_rows: list[dict],
    result_dir: Path = RESULTS,
) -> list[dict]:
    """Compute the fixed MD2-plus-knockout exact-clock secondary."""
    omega = {_key(row): float(row["omega"]) for row in omega_rows}
    universe = _team_universe(tables)
    second_round_stage = {2014: "quarter_final", 2018: "quarter_final", 2022: "quarter_final", 2026: "round_of_16"}
    cohort = {
        (int(row["edition"]), row["team_id"])
        for row in tables["fouls_team_match"]
        if row["stage"] == second_round_stage[int(row["edition"])]
    }
    scope_matches = {
        (int(row["edition"]), int(row["match_number"]), row["team_id"])
        for row in tables["fouls_team_match"]
        if (
            (row["stage"] == "group" and int(row["team_match_number"]) == 2)
            or (is_knockout(row["stage"]) and row["stage"] != "third_place")
        )
    }
    foul_totals: dict[tuple[int, str], int] = defaultdict(int)
    for row in tables["fouls_team_match"]:
        key = (int(row["edition"]), int(row["match_number"]), row["team_id"])
        if key in scope_matches and (int(row["edition"]), row["team_id"]) in cohort:
            foul_totals[(int(row["edition"]), row["team_id"])] += int(row["fouls"])

    exposure: dict[tuple[int, str, float], float] = defaultdict(float)
    card_counts: dict[tuple[int, str], int] = defaultdict(int)
    for card in full_ledger:
        edition = int(card["edition"])
        team_key = (edition, card["team_id"])
        scope_key = (edition, int(card["match_number"]), card["team_id"])
        if (
            team_key not in cohort or scope_key not in scope_matches
            or card["event_scope"] != "in_play"
        ):
            continue
        player_key = _key(card)
        if player_key not in omega:
            raise ValueError(f"md2 card lacks frozen full-ledger omega: {card['card_id']}")
        remainder = max(0.0, float(card["t_end_min"]) - float(card["t_min"]))
        card_counts[team_key] += 1
        for value in MD2_LAMBDAS:
            multiplier = 1.0 if card["card_type"] == "Y" else value
            exposure[(edition, card["team_id"], value)] += (
                omega[player_key] * multiplier * remainder
            )

    raw_rows = []
    for edition, team_id in sorted(cohort):
        fouls = foul_totals[(edition, team_id)]
        if fouls <= 0:
            raise ValueError(f"md2 cohort team has no published scope fouls: {(edition, team_id)}")
        for value in MD2_LAMBDAS:
            minutes = exposure[(edition, team_id, value)]
            raw_rows.append({
                "edition": edition,
                "edition_status": edition_status(edition),
                "cohort": "second_knockout_round_teams",
                "team_id": team_id,
                "team": universe[(edition, team_id)],
                "lambda_md2": value,
                "card_events": card_counts[(edition, team_id)],
                "fouls_md2": fouls,
                "minutes": minutes,
                "rate": minutes / fouls,
            })
    for edition in EDITIONS:
        for value in MD2_LAMBDAS:
            selected = [
                row for row in raw_rows
                if row["edition"] == edition and row["lambda_md2"] == value
            ]
            ordered = sorted(
                selected, key=lambda row: (-row["rate"], row["team"], row["team_id"])
            )
            for rank, row in enumerate(ordered, start=1):
                row["rank"] = rank
                row["teams"] = len(selected)
    output = [
        {
            "edition": row["edition"],
            "edition_status": row["edition_status"],
            "cohort": row["cohort"],
            "team_id": row["team_id"],
            "team": row["team"],
            "lambda_md2": fmt(row["lambda_md2"]),
            "card_events": row["card_events"],
            "fouls_md2": row["fouls_md2"],
            "exp_susp_md2_min": fmt(row["minutes"]),
            "exp_susp_md2_per_foul": fmt(row["rate"]),
            "rank": row["rank"],
            "teams": row["teams"],
            "match_scope": "group_matchday_2_plus_knockout_non_third",
        }
        for row in sorted(
            raw_rows,
            key=lambda item: (
                item["edition"], item["lambda_md2"], item["rank"]
            ),
        )
    ]
    write_csv(result_dir / "md2-suspension-exposure.csv", output, MD2_FIELDS)
    return output


def _card_segment(card: dict) -> int | None:
    period = int(card["period"])
    minute = float(card["t_min"])
    if period == 3:
        return 0 if minute < 15 else 1 if minute < 30 else 2
    if period == 5:
        return 3 if minute < 60 else 4 if minute < 75 else 5
    if period == 7:
        return 6
    if period == 9:
        return 7
    return None


def _weighted_distribution(
    segments: list[int], weights: list[float]
) -> tuple[list[float], float]:
    if not segments or len(segments) != len(weights):
        raise ValueError("timing distribution requires equally sized non-empty inputs")
    total = sum(weights)
    if total <= 0:
        raise ValueError("timing weights must sum positive")
    counts = [0.0] * len(SEGMENTS)
    for segment, weight in zip(segments, weights):
        counts[segment] += weight
    probabilities = [value / total for value in counts]
    # Compute the mean from weighted observations rather than from rounded
    # probabilities.  This keeps boundary-equal Monte Carlo draws on the
    # same side of the two-sided comparison across Python builds.
    mean = sum(
        segment * weight for segment, weight in zip(segments, weights)
    ) / total
    return probabilities, mean


def _timing_statistics(
    card_segments: list[int], card_weights: list[float], foul_segments: list[int]
) -> tuple[float, float, float, float]:
    card_distribution, card_mean = _weighted_distribution(card_segments, card_weights)
    foul_distribution, foul_mean = _weighted_distribution(
        foul_segments, [1.0] * len(foul_segments)
    )
    cumulative_card = cumulative_foul = 0.0
    w1 = 0.0
    for index in range(len(SEGMENTS) - 1):
        cumulative_card += card_distribution[index]
        cumulative_foul += foul_distribution[index]
        w1 += abs(cumulative_card - cumulative_foul)
    return card_mean, foul_mean, card_mean - foul_mean, w1


def _monte_carlo_timing(
    card_segments: list[int], card_weights: list[float], foul_segments: list[int]
) -> tuple[float, float, float, float, float, float]:
    card_mean, foul_mean, delta, w1 = _timing_statistics(
        card_segments, card_weights, foul_segments
    )
    if len(card_segments) > len(foul_segments):
        raise ValueError(
            "within-team timing null cannot sample cards without replacement: "
            f"cards={len(card_segments)} fouls={len(foul_segments)}"
        )
    rng = random.Random(AMENDMENT_SEED)
    extreme_delta = extreme_w1 = 0
    population = list(foul_segments)
    for _ in range(TIMING_PERMUTATIONS):
        sampled = rng.sample(population, len(card_segments))
        _, _, null_delta, null_w1 = _timing_statistics(
            sampled, card_weights, foul_segments
        )
        if abs(null_delta) >= abs(delta) - 1e-12:
            extreme_delta += 1
        if null_w1 >= w1 - 1e-12:
            extreme_w1 += 1
    return (
        card_mean,
        foul_mean,
        delta,
        (1 + extreme_delta) / (TIMING_PERMUTATIONS + 1),
        w1,
        (1 + extreme_w1) / (TIMING_PERMUTATIONS + 1),
    )


def _bh_adjust(rows: list[dict], p_field: str, q_field: str) -> None:
    eligible = [row for row in rows if row[p_field] is not None]
    ordered = sorted(
        eligible, key=lambda row: (row[p_field], row["team"], row["team_id"])
    )
    m = len(ordered)
    running = 1.0
    for rank in range(m, 0, -1):
        row = ordered[rank - 1]
        running = min(running, row[p_field] * m / rank)
        row[q_field] = min(1.0, running)
    for row in rows:
        row["bh_m"] = m


def stage_timing_displacement(
    tables: dict[str, list[dict[str, str]]],
    ledgers: dict[str, list[dict]],
    result_dir: Path = RESULTS,
) -> list[dict]:
    """Compute full/stripped base-null timing checks for both frozen scopes."""
    universe = _team_universe(tables)
    primary = _primary_teams(tables)
    segment_index = {name: index for index, name in enumerate(SEGMENTS)}
    foul_rows = tables["foul_event_segments"]
    raw_output: list[dict] = []

    for edition in EDITIONS:
        for ledger_name in ("full", "stripped"):
            edition_cards = [
                card for card in ledgers[ledger_name]
                if int(card["edition"]) == edition
                and card["event_scope"] == "in_play"
            ]
            for event_scope in ("knockout", "expanded"):
                if event_scope == "knockout":
                    team_ids = sorted(
                        team_id for year, team_id in primary if year == edition
                    )
                    cohort_name = "knockout_teams"
                    card_in_scope = lambda card: (
                        is_knockout(card["stage"]) and card["stage"] != "third_place"
                    )
                    foul_in_scope = lambda row: (
                        is_knockout(row["stage"]) and row["stage"] != "third_place"
                    )
                else:
                    team_ids = sorted(
                        team_id for year, team_id in universe if year == edition
                    )
                    cohort_name = "all_teams"
                    card_in_scope = lambda card: card["stage"] != "third_place"
                    foul_in_scope = lambda row: row["stage"] != "third_place"

                family: list[dict] = []
                for team_id in team_ids:
                    team = universe[(edition, team_id)]
                    if edition == 2014:
                        family.append({
                            "edition": edition,
                            "edition_status": "final",
                            "ledger": ledger_name,
                            "event_scope": event_scope,
                            "cohort": cohort_name,
                            "team_id": team_id,
                            "team": team,
                            "card_events": 0,
                            "foul_events": 0,
                            "red_weight": TIMING_RED_WEIGHT,
                            "mean_card_segment": None,
                            "mean_foul_segment": None,
                            "delta": None,
                            "p_delta": None,
                            "q_delta": None,
                            "w1": None,
                            "p_w1": None,
                            "q_w1": None,
                            "bh_m": 0,
                            "evidentiary_status": "source_unavailable",
                            "source_status": "source_unavailable",
                            "note": "Complete reproducible 2014 foul-event feed unavailable; no BH family created.",
                        })
                        continue
                    cards = sorted(
                        (
                            card for card in edition_cards
                            if card["team_id"] == team_id and card_in_scope(card)
                        ),
                        key=lambda card: (
                            int(card["match_number"]), int(card["period"]),
                            float(card["t_min"]), card["card_id"],
                        ),
                    )
                    card_segments = []
                    card_weights = []
                    for card in cards:
                        segment = _card_segment(card)
                        if segment is None:
                            raise ValueError(
                                f"in-play timing card lacks frozen segment: {card['card_id']}"
                            )
                        card_segments.append(segment)
                        card_weights.append(
                            TIMING_RED_WEIGHT if card["card_type"] == "R" else 1.0
                        )
                    counts = [0] * len(SEGMENTS)
                    for row in foul_rows:
                        if (
                            int(row["edition"]) == edition
                            and row["team_id"] == team_id
                            and foul_in_scope(row)
                        ):
                            counts[segment_index[row["segment"]]] += int(row["foul_events"])
                    foul_segments = [
                        index for index, count in enumerate(counts) for _ in range(count)
                    ]
                    if not foul_segments:
                        raise ValueError(
                            f"complete timing feed has no scoped fouls: {(edition, team_id, event_scope)}"
                        )
                    if not card_segments:
                        family.append({
                            "edition": edition,
                            "edition_status": edition_status(edition),
                            "ledger": ledger_name,
                            "event_scope": event_scope,
                            "cohort": cohort_name,
                            "team_id": team_id,
                            "team": team,
                            "card_events": 0,
                            "foul_events": len(foul_segments),
                            "red_weight": TIMING_RED_WEIGHT,
                            "mean_card_segment": None,
                            "mean_foul_segment": None,
                            "delta": None,
                            "p_delta": None,
                            "q_delta": None,
                            "w1": None,
                            "p_w1": None,
                            "q_w1": None,
                            "bh_m": 0,
                            "evidentiary_status": "zero_cards_excluded_from_m",
                            "source_status": (
                                "complete_with_known_undercount" if edition == 2026 else "complete"
                            ),
                            "note": "No retained card; statistic undefined and excluded from BH m.",
                        })
                        continue
                    card_mean, foul_mean, delta, p_delta, w1, p_w1 = _monte_carlo_timing(
                        card_segments, card_weights, foul_segments
                    )
                    family.append({
                        "edition": edition,
                        "edition_status": edition_status(edition),
                        "ledger": ledger_name,
                        "event_scope": event_scope,
                        "cohort": cohort_name,
                        "team_id": team_id,
                        "team": team,
                        "card_events": len(card_segments),
                        "foul_events": len(foul_segments),
                        "red_weight": TIMING_RED_WEIGHT,
                        "mean_card_segment": card_mean,
                        "mean_foul_segment": foul_mean,
                        "delta": delta,
                        "p_delta": p_delta,
                        "q_delta": None,
                        "w1": w1,
                        "p_w1": p_w1,
                        "q_w1": None,
                        "bh_m": 0,
                        "evidentiary_status": (
                            "evidentiary" if len(card_segments) >= 3
                            else "non_evidentiary_lt3_cards"
                        ),
                        "source_status": (
                            "complete_with_known_undercount" if edition == 2026 else "complete"
                        ),
                        "note": (
                            "Fewer than three retained cards; reported but non-evidentiary."
                            if len(card_segments) < 3 else ""
                        ),
                    })
                if edition != 2014:
                    _bh_adjust(family, "p_delta", "q_delta")
                    _bh_adjust(family, "p_w1", "q_w1")
                raw_output.extend(family)

    output = []
    for row in raw_output:
        output.append({
            "edition": row["edition"],
            "edition_status": row["edition_status"],
            "ledger": row["ledger"],
            "event_scope": row["event_scope"],
            "cohort": row["cohort"],
            "team_id": row["team_id"],
            "team": row["team"],
            "card_events": row["card_events"],
            "foul_events": row["foul_events"],
            "red_weight": fmt(row["red_weight"]),
            "mean_card_segment": fmt(row["mean_card_segment"]) if row["mean_card_segment"] is not None else "",
            "mean_foul_segment": fmt(row["mean_foul_segment"]) if row["mean_foul_segment"] is not None else "",
            "delta": fmt(row["delta"]) if row["delta"] is not None else "",
            "p_delta": fmt(row["p_delta"]) if row["p_delta"] is not None else "",
            "q_delta": fmt(row["q_delta"]) if row["q_delta"] is not None else "",
            "w1": fmt(row["w1"]) if row["w1"] is not None else "",
            "p_w1": fmt(row["p_w1"]) if row["p_w1"] is not None else "",
            "q_w1": fmt(row["q_w1"]) if row["q_w1"] is not None else "",
            "bh_m": row["bh_m"],
            "evidentiary_status": row["evidentiary_status"],
            "source_status": row["source_status"],
            "permutations": TIMING_PERMUTATIONS,
            "seed": AMENDMENT_SEED,
            "note": row["note"],
        })
    output.sort(key=lambda row: (
        int(row["edition"]), row["event_scope"], row["ledger"], row["team"]
    ))
    write_csv(result_dir / "card-timing-displacement.csv", output, TIMING_FIELDS)
    return output


def _kendall_tau_b(pairs: list[tuple[float, float]]) -> float | None:
    n = len(pairs)
    if n < 2:
        return None
    concordant = discordant = 0
    x_counts: dict[float, int] = defaultdict(int)
    y_counts: dict[float, int] = defaultdict(int)
    for x_value, y_value in pairs:
        x_counts[x_value] += 1
        y_counts[y_value] += 1
    for index in range(n - 1):
        for later in range(index + 1, n):
            dx = (pairs[index][0] > pairs[later][0]) - (pairs[index][0] < pairs[later][0])
            dy = (pairs[index][1] > pairs[later][1]) - (pairs[index][1] < pairs[later][1])
            product = dx * dy
            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1
    pair_count = n * (n - 1) / 2
    tied_x = sum(count * (count - 1) / 2 for count in x_counts.values())
    tied_y = sum(count * (count - 1) / 2 for count in y_counts.values())
    denominator = ((pair_count - tied_x) * (pair_count - tied_y)) ** 0.5
    return None if denominator == 0 else (concordant - discordant) / denominator


def _permutation_tau(pairs: list[tuple[float, float]]) -> tuple[float | None, float | None]:
    observed = _kendall_tau_b(pairs)
    if observed is None:
        return None, None
    rng = random.Random(AMENDMENT_SEED)
    x_values = [pair[0] for pair in pairs]
    y_values = [pair[1] for pair in pairs]
    extreme = 0
    for _ in range(CORRELATION_PERMUTATIONS):
        rng.shuffle(y_values)
        permuted = _kendall_tau_b(list(zip(x_values, y_values)))
        if permuted is not None and abs(permuted) >= abs(observed) - 1e-12:
            extreme += 1
    return observed, (1 + extreme) / (CORRELATION_PERMUTATIONS + 1)


def stage_stripped_correlations(
    tables: dict[str, list[dict[str, str]]],
    expanded_team_rows: list[dict],
    result_dir: Path = RESULTS,
) -> list[dict]:
    """Recompute the three disclosed associations under the stripped ledger."""
    primary = _primary_teams(tables)
    stripped = {
        (int(row["edition"]), row["team_id"]): row
        for row in expanded_team_rows if row["ledger"] == "stripped"
    }
    depth: dict[tuple[int, str], int] = defaultdict(int)
    for row in tables["fouls_team_match"]:
        if row["stage"] != "third_place":
            depth[(int(row["edition"]), row["team_id"])] += 1
    goals: dict[tuple[int, str], list[int]] = defaultdict(list)
    for row in tables["team_outcomes"]:
        if row["stage"] != "third_place":
            goals[(int(row["edition"]), row["team_id"])].append(int(row["goals_against"]))

    output = []
    for edition in EDITIONS:
        team_ids = sorted(team_id for year, team_id in primary if year == edition)
        rates = {
            team_id: float(stripped[(edition, team_id)]["exp_susp_per_foul"])
            for team_id in team_ids
        }
        windows = {
            team_id: (
                float(stripped[(edition, team_id)]["exp_susp_accumulation_window_min"])
                / int(stripped[(edition, team_id)]["fouls_all"])
            )
            for team_id in team_ids
        }
        conceded = {
            team_id: sum(goals[(edition, team_id)]) / len(goals[(edition, team_id)])
            for team_id in team_ids
        }
        definitions = (
            (
                "depth_total_e_s", "matches_played_excluding_third_place",
                [(rates[team_id], float(depth[(edition, team_id)])) for team_id in team_ids],
            ),
            (
                "conceded_total_e_s", "goals_conceded_per_match_excluding_third_place",
                [(rates[team_id], conceded[team_id]) for team_id in team_ids],
            ),
            (
                "conceded_accumulation_window", "goals_conceded_per_match_excluding_third_place",
                [(windows[team_id], conceded[team_id]) for team_id in team_ids],
            ),
        )
        for metric, outcome, pairs in definitions:
            tau, p_value = _permutation_tau(pairs)
            output.append({
                "edition": edition,
                "edition_status": edition_status(edition),
                "ledger": "stripped",
                "cohort": "knockout_teams",
                "metric": metric,
                "outcome": outcome,
                "teams": len(pairs),
                "tau_b": fmt(tau) if tau is not None else "",
                "p_permutation": fmt(p_value) if p_value is not None else "",
                "permutations": CORRELATION_PERMUTATIONS,
                "seed": AMENDMENT_SEED,
                "note": (
                    "Disclosed robustness; 2026 is provisional_M100 and not the confirmatory rerun."
                    if edition == 2026 else "Disclosed robustness; never pooled."
                ),
            })
    write_csv(
        result_dir / "stripped-disclosed-correlations.csv",
        output, CORRELATION_FIELDS,
    )
    return output


def stage_cumulative_fouls(
    tables: dict[str, list[dict[str, str]]],
    result_dir: Path = RESULTS,
) -> tuple[list[dict], list[dict]]:
    """Publish safe per-card and first-card cumulative-foul tables."""
    cards = {row["card_id"]: row for row in tables["cards"]}
    reasons = {row["card_id"]: row for row in tables["card_reasons"]}
    output = []
    for audit in tables["card_event_order"]:
        card = cards[audit["card_id"]]
        reason = reasons[audit["card_id"]]
        output.append({
            "edition": audit["edition"],
            "edition_status": audit["edition_status"],
            "card_id": audit["card_id"],
            "match_number": card["match_number"],
            "stage": card["stage"],
            "team_id": card["team_id"],
            "team": card["team"],
            "player_id": card["player_id"],
            "player": card["player"],
            "card_type": card["card_type"],
            "minute_label": card["minute_label"],
            "reason_class": reason["reason_class"],
            "provider": audit["provider"],
            "reconciliation_status": audit["reconciliation_status"],
            "fouls_strictly_before_card": audit["fouls_strictly_before_card"],
            "foul_linked": audit["foul_linked"],
            "fouls_through_card": audit["fouls_through_card"],
            "provenance_status": audit["provenance_status"],
            "official_source_url": card["source_url"],
            "event_source_url": audit["source_url"],
        })
    output.sort(key=lambda row: (
        int(row["edition"]), int(row["match_number"]), row["team_id"],
        float(cards[row["card_id"]]["t_min"]), row["card_id"],
    ))
    team_match_rows = [dict(row) for row in tables["team_match_card_order"]]
    write_csv(
        result_dir / "cumulative-fouls-before-card.csv",
        output, CUMULATIVE_CARD_FIELDS,
    )
    write_csv(
        result_dir / "cumulative-fouls-before-first-card.csv",
        team_match_rows, CUMULATIVE_TEAM_MATCH_FIELDS,
    )
    return output, team_match_rows


def stage_expanded_audit(
    tables: dict[str, list[dict[str, str]]],
    removed: set[str],
    full_ledger: list[dict],
    stripped_ledger: list[dict],
    full_suspensions: list[dict],
    stripped_suspensions: list[dict],
    expanded_player_rows: list[dict],
    full_team_rows: list[dict],
    expanded_team_rows: list[dict],
    md2_rows: list[dict],
    timing_rows: list[dict],
    correlation_rows: list[dict],
    cumulative_rows: list[dict],
    cumulative_team_rows: list[dict],
    result_dir: Path = RESULTS,
) -> list[dict]:
    """Validate amendment invariants and record independent anchor reconciliation."""
    audit: list[dict] = []

    def core(edition, check, observed, expected, passed, note=""):
        audit.append({
            "edition": edition,
            "edition_status": (
                edition_status(int(edition)) if str(edition).isdigit() else "mixed"
            ),
            "check": check,
            "observed": observed,
            "expected": expected,
            "status": "PASS" if passed else "FAIL",
            "note": note,
        })
        if not passed:
            raise ValueError(
                f"expanded amendment invariant failed: {edition} {check}: "
                f"observed={observed} expected={expected}"
            )

    def anchor(edition, check, observed, expected, passed, note=""):
        audit.append({
            "edition": edition,
            "edition_status": edition_status(int(edition)),
            "check": check,
            "observed": observed,
            "expected": expected,
            "status": "PASS" if passed else "AUDIT",
            "note": note or (
                "Independent frozen-text anchor reconciled."
                if passed else
                "Independent anchor mismatch retained as AUDIT; values were not force-fit."
            ),
        })

    reason_by_id = {row["card_id"]: row["reason_class"] for row in tables["card_reasons"]}
    removed_counts = Counter(reason_by_id[card_id] for card_id in removed)
    core(
        "all", "stripped_reason_filter",
        f"dissent={removed_counts['dissent']};time_wasting={removed_counts['time_wasting']};total={len(removed)}",
        "dissent=46;time_wasting=19;total=65",
        removed_counts == Counter({"dissent": 46, "time_wasting": 19}),
        "Only dissent and time_wasting are removed; other_nonfoul/unknown remain.",
    )

    full_card_ids = {row["card_id"] for row in full_ledger}
    stripped_card_ids = {row["card_id"] for row in stripped_ledger}
    core(
        "all", "stripped_card_census",
        len(stripped_card_ids), len(full_card_ids) - len(removed),
        (
            stripped_card_ids == full_card_ids - removed
            and not (stripped_card_ids & removed)
        ),
        "The stripped ledger is rebuilt after removing exactly the frozen reason set.",
    )
    stripped_trigger_ids = {
        row["trigger_card_id"] for row in stripped_suspensions
        if row["trigger_card_id"]
    }
    core(
        "all", "stripped_in_edition_suspension_triggers",
        len(stripped_trigger_ids - stripped_card_ids), 0,
        stripped_trigger_ids <= stripped_card_ids,
        "No stripped served/pending term may retain an in-edition trigger card that was removed.",
    )
    full_external = {
        row["suspension_id"] for row in full_suspensions
        if not row["trigger_card_id"]
    }
    stripped_external = {
        row["suspension_id"] for row in stripped_suspensions
        if not row["trigger_card_id"]
    }
    core(
        "all", "stripped_external_carry_in_retention",
        sorted(stripped_external), sorted(full_external),
        stripped_external == full_external,
        "Pre-tournament carry-in decisions have no in-edition trigger and remain retained.",
    )
    stripped_suspension_ids = {
        row["suspension_id"] for row in stripped_suspensions
    }
    removed_trigger_terms = {
        row["suspension_id"] for row in full_suspensions
        if row["trigger_card_id"] in removed
    }
    core(
        "all", "stripped_removed_trigger_terms_omitted",
        len(removed_trigger_terms & stripped_suspension_ids), 0,
        not (removed_trigger_terms & stripped_suspension_ids),
        f"Full-ledger terms whose trigger was stripped: {len(removed_trigger_terms)}.",
    )

    player_omega: dict[tuple[int, str, str], dict[str, str]] = defaultdict(dict)
    for row in expanded_player_rows:
        player_omega[
            (int(row["edition"]), row["team_id"], row["player_id"])
        ][row["ledger"]] = row["omega"]
    omega_mismatches = [
        key for key, values in player_omega.items()
        if set(values) != {"full", "stripped"}
        or values["full"] != values["stripped"]
    ]
    core(
        "all", "stripped_omega_held_fixed",
        len(omega_mismatches), 0, not omega_mismatches,
        "The observed full-ledger opportunity weight is reused without counterfactual lineups.",
    )

    expected_counts = {2014: 32, 2018: 32, 2022: 32, 2026: 48}
    for edition in EDITIONS:
        for ledger_name in ("full", "stripped"):
            rows = [
                row for row in expanded_team_rows
                if int(row["edition"]) == edition and row["ledger"] == ledger_name
            ]
            core(
                edition, f"expanded_team_count_{ledger_name}", len(rows),
                expected_counts[edition], len(rows) == expected_counts[edition],
            )
            core(
                edition, f"expanded_ge_knockout_{ledger_name}",
                sum(float(row["exp_susp_all_min"]) + 1e-8 >= float(row["exp_susp_min"]) for row in rows),
                len(rows),
                all(
                    float(row["exp_susp_all_min"]) + 1e-8 >= float(row["exp_susp_min"])
                    for row in rows
                ),
            )
            status_ok = all(
                row["edition_status"] == edition_status(edition) for row in rows
            )
            core(
                edition, f"expanded_edition_status_{ledger_name}",
                edition_status(edition) if status_ok else "mixed",
                edition_status(edition), status_ok,
            )
        full_rows = [
            row for row in expanded_team_rows
            if int(row["edition"]) == edition and row["ledger"] == "full"
        ]
        core(
            edition, "secondary_prime_ge_all",
            sum(
                float(row["exp_susp_prime_min"]) + 1e-8 >= float(row["exp_susp_all_min"])
                for row in full_rows
            ),
            len(full_rows),
            all(
                float(row["exp_susp_prime_min"]) + 1e-8 >= float(row["exp_susp_all_min"])
                for row in full_rows
            ),
        )
        stripped_rows = [
            row for row in expanded_team_rows
            if int(row["edition"]) == edition and row["ledger"] == "stripped"
        ]
        core(
            edition, "secondary_prime_full_ledger_only",
            sum(not row["exp_susp_prime_min"] for row in stripped_rows),
            len(stripped_rows),
            all(not row["exp_susp_prime_min"] for row in stripped_rows),
            "E_s prime is not recomputed under the stripped ledger.",
        )

    new_outputs = (
        stripped_ledger, stripped_suspensions, expanded_player_rows,
        expanded_team_rows, md2_rows, timing_rows, correlation_rows,
        cumulative_rows, cumulative_team_rows, tables["foul_event_segments"],
        tables["card_event_order"], tables["team_match_card_order"],
        tables["team_outcomes"],
    )
    provisional_rows = [
        row for rows in new_outputs for row in rows
        if int(row["edition"]) == 2026
    ]
    core(
        2026, "all_new_outputs_provisional_m100",
        sum(row["edition_status"] == "provisional_M100" for row in provisional_rows),
        len(provisional_rows),
        all(row["edition_status"] == "provisional_M100" for row in provisional_rows),
        "No M101-M104 input is ingested before the post-M104 confirmatory rerun.",
    )

    # The new full-ledger knockout component must reconstruct the already
    # published frozen E_s exactly; expanded tables are additive, not replacements.
    frozen = {
        (int(row["edition"]), row["team_id"]): float(row["exp_susp_min"])
        for row in full_team_rows
    }
    rebuilt = {
        (int(row["edition"]), row["team_id"]): float(row["exp_susp_min"])
        for row in expanded_team_rows if row["ledger"] == "full"
    }
    differences = {
        key: abs(rebuilt[key] - value)
        for key, value in frozen.items()
        if key in rebuilt
    }
    max_difference = max(differences.values(), default=0.0)
    core(
        "all", "frozen_e_s_reconstruction", fmt(max_difference, 9), "<=0.000001",
        set(frozen) == set(rebuilt) and max_difference <= 1e-6,
        "Full-ledger E_s is reconstructed before group exposure is added.",
    )

    md2_counts = {
        edition: len({
            row["team_id"] for row in md2_rows
            if int(row["edition"]) == edition and float(row["lambda_md2"]) == 1.5
        })
        for edition in EDITIONS
    }
    core(
        "all", "md2_second_round_cohort", md2_counts,
        {2014: 8, 2018: 8, 2022: 8, 2026: 16},
        md2_counts == {2014: 8, 2018: 8, 2022: 8, 2026: 16},
    )
    core(
        "all", "cumulative_card_exact_coverage", len(cumulative_rows),
        len(tables["card_event_order"]),
        len(cumulative_rows) == len(tables["card_event_order"]),
    )
    core(
        "all", "cumulative_team_match_exact_coverage", len(cumulative_team_rows),
        len(tables["matches"]) * 2,
        len(cumulative_team_rows) == len(tables["matches"]) * 2,
        "Zero-card team-match sides remain explicit.",
    )
    forbidden = {
        "provider_match_id", "provider_event_id", "provider_sequence_index",
        "provider_event_order_key", "provider_linked_event_reference",
        "sb_match_id", "sb_event_id", "order_key",
    }
    public_fields = set(CUMULATIVE_CARD_FIELDS) | set(CUMULATIVE_TEAM_MATCH_FIELDS)
    core(
        "all", "cumulative_public_private_schema_boundary",
        sorted(forbidden & public_fields), "[]", not (forbidden & public_fields),
        "Provider-native identifiers/order keys exist only in the ignored private sidecar.",
    )
    source_unavailable_2014 = [
        row for row in timing_rows
        if int(row["edition"]) == 2014
    ]
    core(
        2014, "expanded_timing_source_unavailable",
        sum(row["source_status"] == "source_unavailable" for row in source_unavailable_2014),
        len(source_unavailable_2014),
        all(row["source_status"] == "source_unavailable" for row in source_unavailable_2014),
        "No 2014 timing BH family is created.",
    )

    expanded_lookup = {
        (int(row["edition"]), row["ledger"], row["team"]): row
        for row in expanded_team_rows
    }
    for edition, target in ((2018, 16.61), (2022, 4.20)):
        row = expanded_lookup[(edition, "stripped", "Argentina")]
        observed = float(row["exp_susp_per_foul"])
        anchor(
            edition, "anchor_stripped_argentina_e_s",
            f"{observed:.2f}", f"{target:.2f}", round(observed, 2) == target,
        )
    for edition, target, rank in (
        (2014, 10.61, 17), (2018, 24.84, 5),
        (2022, 5.49, 31), (2026, 2.22, 48),
    ):
        row = expanded_lookup[(edition, "full", "Argentina")]
        observed = float(row["exp_susp_all_per_foul"])
        observed_rank = int(row["rank_exp_susp_all_per_foul"])
        anchor(
            edition, "anchor_argentina_e_s_all",
            f"{observed:.2f} ({observed_rank}/{row['teams']})",
            f"{target:.2f} ({rank}/{expected_counts[edition]})",
            round(observed, 2) == target and observed_rank == rank,
        )

    correlation_lookup = {
        (int(row["edition"]), row["metric"]): row for row in correlation_rows
    }
    for edition, target_tau, target_p in (
        (2018, 0.400, 0.034), (2022, 0.536, 0.005),
    ):
        row = correlation_lookup[(edition, "conceded_total_e_s")]
        tau = float(row["tau_b"])
        p_value = float(row["p_permutation"])
        anchor(
            edition, "anchor_stripped_e_s_vs_conceded",
            f"tau={tau:+.3f};p={p_value:.3f}",
            f"tau={target_tau:+.3f};p~={target_p:.3f}",
            abs(tau - target_tau) <= 0.001 and abs(p_value - target_p) <= 0.006,
            (
                "Official score rows give C=82, D=33 and five conceded-rate "
                "ties under frozen tau-b, yielding +0.417; the independent "
                "anchor remains unresolved."
                if edition == 2018 else "Independent frozen-text anchor reconciled."
            ),
        )

    md2_2022 = sorted(
        (
            row for row in md2_rows
            if int(row["edition"]) == 2022 and float(row["lambda_md2"]) == 1.5
        ),
        key=lambda row: int(row["rank"]),
    )
    france = next(row for row in md2_2022 if row["team"] == "France")
    argentina = next(row for row in md2_2022 if row["team"] == "Argentina")
    md2_passed = (
        md2_2022[0]["team"] == "France"
        and round(float(france["exp_susp_md2_per_foul"]), 2) == 5.17
        and round(float(argentina["exp_susp_md2_per_foul"]), 2) == 4.32
        and int(argentina["rank"]) == 4
    )
    anchor(
        2022, "anchor_md2_lambda_1_5",
        (
            f"top={md2_2022[0]['team']} {float(md2_2022[0]['exp_susp_md2_per_foul']):.2f};"
            f"Argentina={float(argentina['exp_susp_md2_per_foul']):.2f} "
            f"({argentina['rank']}/{argentina['teams']})"
        ),
        "top=France 5.17;Argentina=4.32 (4/8)", md2_passed,
    )

    timing = next(
        row for row in timing_rows
        if int(row["edition"]) == 2022 and row["ledger"] == "stripped"
        and row["event_scope"] == "knockout" and row["team"] == "Argentina"
    )
    timing_delta = float(timing["delta"])
    timing_p = float(timing["p_delta"])
    anchor(
        2022, "anchor_stripped_knockout_timing_argentina",
        f"delta={timing_delta:+.2f};p={timing_p:.3f};n={timing['card_events']}",
        "delta=+1.10;p~=0.063;n=11",
        (
            round(timing_delta, 2) == 1.10
            and abs(timing_p - 0.063) <= 0.006
            and int(timing["card_events"]) == 11
        ),
        (
            "The frozen without-replacement null gives an exact tail near "
            "0.048 and this seeded Monte Carlo estimate; a with-replacement "
            "draw is closer to 0.063 but is not the frozen null."
        ),
    )

    write_csv(result_dir / "expanded-audit.csv", audit, EXPANDED_AUDIT_FIELDS)
    return audit


def run_expanded_stages(
    tables: dict[str, list[dict[str, str]]],
    full_ledger: list[dict],
    full_suspensions: list[dict],
    omega_rows: list[dict],
    full_team_rows: list[dict],
    stage_dir: Path = STAGES,
    result_dir: Path = RESULTS,
) -> dict:
    stripped_ledger, stripped_suspensions, removed = build_stripped_ledger(
        tables, stage_dir
    )
    ledgers = {"full": full_ledger, "stripped": stripped_ledger}
    suspension_sets = {
        "full": full_suspensions, "stripped": stripped_suspensions,
    }
    players, teams, group_card_audits = stage_expanded_exposure(
        tables, ledgers, suspension_sets, omega_rows, stage_dir, result_dir
    )
    md2 = stage_md2_exposure(tables, full_ledger, omega_rows, result_dir)
    timing = stage_timing_displacement(tables, ledgers, result_dir)
    correlations = stage_stripped_correlations(tables, teams, result_dir)
    cumulative_cards, cumulative_team_matches = stage_cumulative_fouls(
        tables, result_dir
    )
    audit = stage_expanded_audit(
        tables, removed, full_ledger, stripped_ledger, full_suspensions,
        stripped_suspensions, players, full_team_rows, teams, md2, timing,
        correlations, cumulative_cards, cumulative_team_matches, result_dir,
    )
    return {
        "stripped_cards": stripped_ledger,
        "stripped_suspensions": stripped_suspensions,
        "stripped_removed_card_ids": removed,
        "expanded_players": players,
        "expanded_teams": teams,
        "group_card_audits": group_card_audits,
        "md2": md2,
        "timing": timing,
        "stripped_correlations": correlations,
        "cumulative_cards": cumulative_cards,
        "cumulative_team_matches": cumulative_team_matches,
        "expanded_audit": audit,
    }
