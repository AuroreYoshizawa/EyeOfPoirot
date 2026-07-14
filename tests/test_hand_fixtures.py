"""Small card/suspension fixtures checked by hand against archived sources."""

from __future__ import annotations

import csv
import unittest

from pipeline.build.expanded import _group_components
from pipeline.build.stages import _source_tables
from pipeline.config import ROOT, SOURCE


def read(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class HandCheckedFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = _source_tables(SOURCE)
        cls.cards = {
            row["card_id"]: row
            for row in read(ROOT / "data" / "derived" / "stages" / "s1-card-ledger.csv")
        }
        stripped_cards = {
            row["card_id"]: row
            for row in read(
                ROOT / "data" / "derived" / "stages" / "s9-stripped-card-ledger.csv"
            )
        }
        cls.group_card_audits = {
            "full": _group_components(cls.source, list(cls.cards.values()))[1],
            "stripped": _group_components(cls.source, list(stripped_cards.values()))[1],
        }
        cls.suspensions = {
            row["suspension_id"]: row
            for row in read(ROOT / "data" / "derived" / "stages" / "s4-suspensions.csv")
        }
        cls.opportunity = {
            (row["edition"], row["team_id"], row["player_id"]): row
            for row in read(ROOT / "data" / "derived" / "stages" / "s5-player-opportunity.csv")
        }
        cls.expanded_players = {
            (
                row["ledger"], row["edition"], row["team_id"], row["player_id"]
            ): row
            for row in read(
                ROOT / "data" / "derived" / "stages"
                / "s11-expanded-player-suspension-exposure.csv"
            )
        }
        cls.md2 = read(
            ROOT / "data" / "derived" / "results" / "md2-suspension-exposure.csv"
        )
        cls.first_cards = {
            (row["edition"], row["match_number"], row["team_id"]): row
            for row in read(
                ROOT / "data" / "derived" / "source" / "team_match_card_order.csv"
            )
        }

    def test_card_fixtures(self):
        fixtures = read(ROOT / "tests" / "fixtures" / "hand_checked_cards.csv")
        self.assertEqual({int(row["edition"]) for row in fixtures}, {2014, 2018, 2022, 2026})
        for fixture in fixtures:
            with self.subTest(card_id=fixture["card_id"], field=fixture["field"]):
                self.assertIn(fixture["card_id"], self.cards)
                self.assertEqual(
                    self.cards[fixture["card_id"]][fixture["field"]], fixture["expected"],
                    fixture["reason"],
                )

    def test_suspension_fixtures(self):
        fixtures = read(ROOT / "tests" / "fixtures" / "hand_checked_suspensions.csv")
        self.assertEqual({int(row["edition"]) for row in fixtures}, {2014, 2018, 2022, 2026})
        for fixture in fixtures:
            with self.subTest(suspension_id=fixture["suspension_id"]):
                self.assertIn(fixture["suspension_id"], self.suspensions)
                self.assertEqual(
                    self.suspensions[fixture["suspension_id"]]["service_status"],
                    fixture["service_status"], fixture["reason"],
                )

    def test_availability_fixtures(self):
        fixtures = read(ROOT / "tests" / "fixtures" / "hand_checked_availability.csv")
        self.assertEqual({int(row["edition"]) for row in fixtures}, {2014, 2018, 2022, 2026})
        for fixture in fixtures:
            key = (fixture["edition"], fixture["team_id"], fixture["player_id"])
            with self.subTest(key=key):
                self.assertIn(key, self.opportunity)
                observed = self.opportunity[key]
                for field in (
                    "union_unavailable_minutes", "opportunity_denominator_minutes", "omega"
                ):
                    self.assertEqual(observed[field], fixture[field], fixture["reason"])

    def test_expanded_group_and_partition_fixtures(self):
        fixtures = read(ROOT / "tests" / "fixtures" / "hand_checked_expanded.csv")
        for fixture in fixtures:
            with self.subTest(
                case=fixture["case"], ledger=fixture["ledger"],
                key=fixture["key"], field=fixture["field"],
            ):
                if fixture["case"] == "group_card":
                    observed = self.group_card_audits[fixture["ledger"]][fixture["key"]]
                    if fixture["field"] in {"l_grp", "q", "untriggered"}:
                        self.assertAlmostEqual(
                            float(observed[fixture["field"]]),
                            float(fixture["expected"]), places=7,
                            msg=fixture["reason"],
                        )
                    else:
                        self.assertEqual(
                            observed[fixture["field"]], fixture["expected"],
                            fixture["reason"],
                        )
                    continue
                edition, team_id, player_id = fixture["key"].split("|")
                observed = self.expanded_players[
                    (fixture["ledger"], edition, team_id, player_id)
                ]
                self.assertEqual(
                    observed[fixture["field"]], fixture["expected"],
                    fixture["reason"],
                )

    def test_md2_cohort_membership_fixture_and_denominator_scope(self):
        fixtures = read(ROOT / "tests" / "fixtures" / "hand_checked_md2_cohort.csv")
        expected = {
            (row["edition"], row["team_id"]): row for row in fixtures
        }
        observed = {
            (row["edition"], row["team_id"]): row
            for row in self.md2 if row["lambda_md2"] == "1.5"
        }
        self.assertEqual(set(observed), set(expected))

        reached_stage = {
            (row["edition"], row["team_id"], row["stage"])
            for row in self.source["fouls_team_match"]
        }
        for key, fixture in expected.items():
            self.assertIn(
                (fixture["edition"], fixture["team_id"], fixture["second_round_stage"]),
                reached_stage,
            )

        foul_totals = {}
        for row in self.source["fouls_team_match"]:
            key = (row["edition"], row["team_id"])
            if key not in expected:
                continue
            in_scope = (
                (row["stage"] == "group" and row["team_match_number"] == "2")
                or (row["stage"] != "group" and row["stage"] != "third_place")
            )
            if in_scope:
                foul_totals[key] = foul_totals.get(key, 0) + int(row["fouls"])
        for row in self.md2:
            key = (row["edition"], row["team_id"])
            self.assertEqual(int(row["fouls_md2"]), foul_totals[key])
            self.assertEqual(
                row["match_scope"], "group_matchday_2_plus_knockout_non_third"
            )

    def test_same_clock_first_card_uses_provider_order(self):
        # Haiti received two cards at displayed minute 79.  The provider
        # sequence places Placide first even though lexical project-card order
        # would place Nazon first.
        haiti = self.first_cards[("2026", "50", "43908")]
        self.assertEqual(haiti["first_card_id"], "2026-050-1833112852")
        self.assertEqual(haiti["fouls_before_first_card"], "15")

        # Croatia's two 32nd-minute cards have different strict foul counts,
        # making the provider-order choice observable in the public summary.
        croatia = self.first_cards[("2022", "61", "43938")]
        self.assertEqual(croatia["first_card_id"], "2022-061-18191200000582")
        self.assertEqual(croatia["fouls_before_first_card"], "2")


if __name__ == "__main__":
    unittest.main()
