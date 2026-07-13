"""Hand-derived assertions for the v0.2.1 rules (§3.2–§3.4, §5.1).

Each expectation below was recomputed by hand from the archived event data
before being written down; the tests read the committed build artifacts.
"""

from __future__ import annotations

import csv
import unittest

from pipeline.config import ROOT


def read(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class RuleV021Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.players = {
            (row["edition"], row["player_id"]): row
            for row in read(ROOT / "data" / "derived" / "results" / "player-suspension-exposure.csv")
        }
        cls.ledger = read(ROOT / "data" / "derived" / "stages" / "s1-card-ledger.csv")
        cls.match_rows = read(ROOT / "data" / "derived" / "results" / "match-exposure.csv")
        cls.teams = read(ROOT / "data" / "derived" / "results" / "team-suspension-exposure.csv")
        cls.fouls = read(ROOT / "data" / "derived" / "source" / "fouls_team_match.csv")
        cls.depth = read(ROOT / "data" / "derived" / "results" / "depth-check.csv")

    def test_group_only_discipline_creates_no_terms(self):
        # 2014 Wilson Palacios: group Y 27' -> same-match Y2 42' (M10), ban
        # served in a group match (M26). Knockout-impact scope prices all of
        # it at zero.
        row = self.players[("2014", "209827")]
        self.assertEqual(row["unweighted_exp_susp_min"], "0")
        self.assertEqual(row["served_suspension_matches"], "0")

    def test_group_earned_knockout_service_counts(self):
        # 2014 Jose Vazquez: two group cautions, ban served in the round of 16
        # (M51). The knockout service is knockout impact: 90 * 1.25 = 112.5.
        row = self.players[("2014", "379264")]
        self.assertEqual(row["served_suspension_min"], "112.5")
        self.assertEqual(row["ordinary_caution_min"], "0")

    def test_group_service_is_excluded(self):
        # 2014 Maximiliano Pereira: group dismissal (M7) served in a group
        # match (M23) — no term of any kind.
        row = self.players[("2014", "286481")]
        self.assertEqual(row["unweighted_exp_susp_min"], "0")

    def test_carried_in_caution_untriggered_is_180(self):
        # 2014 Neymar entered the knockout stage with one pending group
        # caution and received no further suspension-causing card in the
        # window: 90 + 90*1 = 180 carried-in minutes.
        row = self.players[("2014", "314197")]
        self.assertEqual(row["carried_in_caution_min"], "180")

    def test_carried_in_caution_stopped_at_trigger_minute(self):
        # 2014 Luiz Gustavo carried a pending group caution into the round of
        # 16 and was booked again there at 59': the carried-in interval stops
        # at minute 59 (same-match stop from minute 0).
        row = self.players[("2014", "367918")]
        self.assertEqual(row["carried_in_caution_min"], "59")
        self.assertEqual(row["served_suspension_min"], "112.5")

    def test_2026_has_no_carried_in_cautions(self):
        # 2026 group cautions are cancelled at the group-stage reset.
        for (edition, _), row in self.players.items():
            if edition == "2026":
                self.assertEqual(row["carried_in_caution_min"], "0")

    def test_semi_final_caution_uses_exact_clock(self):
        # 2022 semi-final (M61) ended at 95'. Romero's 68' caution prices
        # 95 - 68 = 27 exact minutes with no horizon block.
        cards = [
            row for row in self.ledger
            if row["edition"] == "2022" and row["stage"] == "semi_final"
            and row["card_type"] == "Y" and row["player"] == "ROMERO"
        ]
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(float(card["t_end_min"]) - float(card["t_min"]), 27.0)
        self.assertEqual(card["base_horizon"], "0")

    def test_stoppage_caution_not_floored_at_zero(self):
        # 2022 Cheddira: Y at 90'+1' (t=91) followed by Y2 at 90'+3' (t=93) in
        # the quarter-final. Stoppage receipt uses the exact clock, and the
        # same-match stop caps the interval at t2: 93 - 91 = 2 minutes.
        cards = [
            row for row in self.ledger
            if row["edition"] == "2022" and row["player"] == "CHEDDIRA"
            and row["card_type"] == "Y"
        ]
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(card["stop_scope"], "same_match")
        row = self.players[("2022", card["player_id"])]
        self.assertEqual(row["ordinary_caution_min"], "2")

    def test_cross_match_trigger_beyond_horizon_is_ignored(self):
        # 2018: a semi-final caution paired with a final caution lies beyond
        # the zero-fixture horizon; the interval stays at the exact-clock
        # remainder of the semi-final itself.
        pairs = [
            row for row in self.ledger
            if row["edition"] == "2018" and row["stage"] == "semi_final"
            and row["card_type"] == "Y" and row["stop_scope"] == "cross_match"
        ]
        for card in pairs:
            self.assertEqual(card["base_horizon"], "0")

    def test_third_place_excluded_from_match_rows_and_fouls(self):
        self.assertFalse([row for row in self.match_rows if row["stage"] == "third_place"])
        self.assertFalse([row for row in self.match_rows if row["stage"] == "group"])
        # 2014 Brazil played the third-place match; fouls_all must equal the
        # team's foul sum excluding it.
        brazil = next(
            row for row in self.teams
            if row["edition"] == "2014" and row["team"] == "Brazil"
        )
        expected = sum(
            int(row["fouls"]) for row in self.fouls
            if row["edition"] == "2014" and row["team"] == "Brazil"
            and row["stage"] != "third_place"
        )
        included = sum(
            int(row["fouls"]) for row in self.fouls
            if row["edition"] == "2014" and row["team"] == "Brazil"
        )
        self.assertEqual(int(brazil["fouls_all"]), expected)
        self.assertLess(expected, included)

    def test_depth_check_shape(self):
        self.assertEqual(
            {(row["edition"], row["teams"]) for row in self.depth},
            {("2014", "16"), ("2018", "16"), ("2022", "16"), ("2026", "32")},
        )
        for row in self.depth:
            self.assertEqual(row["permutations"], "10000")
            self.assertEqual(row["seed"], "20260713")
            self.assertEqual(row["depth_definition"], "matches_played_excluding_third_place")


if __name__ == "__main__":
    unittest.main()
