"""Shared paths and frozen constants for methodology v0.2."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
DERIVED = DATA / "derived"
SOURCE = DERIVED / "source"
STAGES = DERIVED / "stages"
RESULTS = DERIVED / "results"
FIGURES = ROOT / "figures" / "official"

EDITIONS = (2014, 2018, 2022, 2026)
EXPECTED_COMPLETED = {2014: 64, 2018: 64, 2022: 64, 2026: 100}
EXPECTED_PLAYER_CARDS = {2014: 194, 2018: 224, 2022: 228, 2026: 270}
EXPECTED_TEAM_MATCH_ROWS = {year: count * 2 for year, count in EXPECTED_COMPLETED.items()}
# The private event-level reconciliation is verified by hash and never
# published. The public table contains only project-authored aggregate
# conclusions allowed by the StatsBomb Public Data User Agreement.
EXPECTED_CARD_REASON_SB_EXTRA_SHA256 = (
    "48f4367295c67cb7bfae452d6eeab1790b89337f51ede73cedf4773a6aa49c91"
)
EXPECTED_CARD_REASON_SB_RECONCILIATION = {
    (2018, "Foul Committed"): (
        165, 4, 169, "not_aligned_to_fifa_espn_in_play_census=4",
    ),
    (2018, "Bad Behaviour"): (
        39, 1, 40, "not_aligned_to_fifa_espn_in_play_census=1",
    ),
    (2022, "Foul Committed"): (184, 0, 184, "none"),
    (2022, "Bad Behaviour"): (
        37, 7, 44,
        "fifa_event_scope_interval=1;post_play=4;penalty_shootout=2",
    ),
}
SEASON_IDS = {2014: "251164", 2018: "254645", 2022: "255711", 2026: "285023"}

PRIMARY_RHO = 2.0
PRIMARY_MU = 1.25
RHO_GRID = (1.0, 1.5, 2.0)
MU_GRID = (1.0, 1.25, 1.5)
DENOMINATORS = ("all", "knockout")

RULE_SOURCE_URLS = {
    # FIFA's 2026 reset explainer explicitly documents that the previous
    # World Cup rule was one cancellation after the quarter-finals.
    2014: (
        "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/"
        "articles/yellow-cards-reset-group-stage-quarter-final"
    ),
    2018: (
        "https://inside.fifa.com/tournaments/mens/worldcup/2018russia/news/"
        "a-disciplinary-reminder-for-russia-2018"
    ),
    2022: "https://www.fifa.com/en/articles/ten-queries-about-qatar-2022-world-cup",
    2026: (
        "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/"
        "articles/yellow-cards-reset-group-stage-quarter-final"
    ),
}


def stage_code(stage: str, is_group: bool = False) -> str:
    """Map FIFA's localized stage label to one stable code."""
    text = (stage or "").lower()
    if is_group or "first stage" in text or "group" in text:
        return "group"
    if "round of 32" in text:
        return "round_of_32"
    if "round of 16" in text or "eighth" in text:
        return "round_of_16"
    if "quarter" in text:
        return "quarter_final"
    if "semi" in text:
        return "semi_final"
    if "third" in text or "play-off" in text or "playoff" in text:
        return "third_place"
    if "final" in text:
        return "final"
    raise ValueError(f"unknown stage label: {stage!r}")


def is_knockout(stage: str) -> bool:
    return stage != "group"
