"""CLI plumbing shared by the eight named build-stage modules."""

from __future__ import annotations

from .stages import (
    _source_tables,
    stage1_cards,
    stage2_fouls,
    stage3_minutes,
    stage4_suspensions,
    stage5_availability,
    stage6_match_exposure,
    stage7_suspension_exposure,
    stage8_validate_and_summarize,
)


def run_through(stage: int) -> dict:
    if not 1 <= stage <= 8:
        raise ValueError("stage must be between 1 and 8")
    tables = _source_tables()
    result: dict = {"source": tables}
    cards = stage1_cards(tables)
    result["cards"] = cards
    if stage == 1:
        return result
    result["fouls"] = stage2_fouls(tables)
    if stage == 2:
        return result
    result["minutes"] = stage3_minutes(tables)
    if stage == 3:
        return result
    suspensions = stage4_suspensions(tables, cards)
    result["suspensions"] = suspensions
    if stage == 4:
        return result
    availability, omega = stage5_availability(tables, cards, suspensions)
    result.update(availability=availability, omega=omega)
    if stage == 5:
        return result
    match_rows, match_sensitivity, match_clock_sensitivity = stage6_match_exposure(
        tables, cards
    )
    result.update(
        match=match_rows,
        match_sensitivity=match_sensitivity,
        match_clock_sensitivity=match_clock_sensitivity,
    )
    if stage == 6:
        return result
    players, teams, sensitivity, player_grid, suspension_clock_sensitivity = (
        stage7_suspension_exposure(
            tables, cards, suspensions, omega
        )
    )
    result.update(
        players=players,
        teams=teams,
        sensitivity=sensitivity,
        player_grid=player_grid,
        suspension_clock_sensitivity=suspension_clock_sensitivity,
    )
    if stage == 7:
        return result
    audit, summaries = stage8_validate_and_summarize(
        tables,
        cards,
        suspensions,
        availability,
        omega,
        match_rows,
        teams,
        sensitivity,
    )
    result.update(audit=audit, summaries=summaries)
    return result


def main_for_stage(stage: int) -> int:
    result = run_through(stage)
    latest = {
        1: "cards", 2: "fouls", 3: "minutes", 4: "suspensions",
        5: "omega", 6: "match", 7: "teams", 8: "audit",
    }[stage]
    print(f"stage {stage} complete: {latest}={len(result[latest])}")
    return 0
