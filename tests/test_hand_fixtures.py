"""Small card/suspension fixtures checked by hand against archived sources."""

from __future__ import annotations

import csv
import unittest

from pipeline.config import ROOT


def read(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class HandCheckedFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards = {
            row["card_id"]: row
            for row in read(ROOT / "data" / "derived" / "stages" / "s1-card-ledger.csv")
        }
        cls.suspensions = {
            row["suspension_id"]: row
            for row in read(ROOT / "data" / "derived" / "stages" / "s4-suspensions.csv")
        }
        cls.opportunity = {
            (row["edition"], row["team_id"], row["player_id"]): row
            for row in read(ROOT / "data" / "derived" / "stages" / "s5-player-opportunity.csv")
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


if __name__ == "__main__":
    unittest.main()
