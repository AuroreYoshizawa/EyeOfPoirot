"""Keep the published independent-match audit synchronized with source tables."""

from __future__ import annotations

import csv
import unittest
from collections import Counter

from pipeline.config import ROOT


def read(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class IndependentMatchCrosscheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards = read(ROOT / "data" / "derived" / "source" / "cards.csv")
        cls.matches = read(ROOT / "data" / "derived" / "source" / "matches.csv")
        cls.checks = read(ROOT / "data" / "sources" / "independent-match-checks.csv")

    def test_four_editions_and_four_matches_are_checked(self):
        self.assertEqual({int(row["edition"]) for row in self.checks}, {2014, 2018, 2022, 2026})
        self.assertEqual(
            {(int(row["edition"]), int(row["match_number"])) for row in self.checks},
            {(2014, 1), (2018, 16), (2022, 57), (2026, 1)},
        )

    def test_primary_values_are_current(self):
        player_cards = [row for row in self.cards if row["recipient_type"] == "player"]
        values = {}

        counts_2014 = Counter(
            row["team"] for row in player_cards
            if int(row["edition"]) == 2014 and int(row["match_number"]) == 1
        )
        values["2014-m001-card-counts"] = (
            f"Brazil={counts_2014['Brazil']}|Croatia={counts_2014['Croatia']}"
        )
        match_2014 = next(
            row for row in self.matches
            if int(row["edition"]) == 2014 and int(row["match_number"]) == 1
        )
        values["2014-m001-end-clock"] = str(round(float(match_2014["t_end_min"])))

        cards_2018 = [
            row for row in player_cards
            if int(row["edition"]) == 2018 and int(row["match_number"]) == 16
        ]
        types_2018 = Counter(row["card_type"] for row in cards_2018)
        values["2018-m016-card-types"] = f"Y={types_2018['Y']}|R={types_2018['R']}"
        red_2018 = next(row for row in cards_2018 if row["card_type"] == "R")
        values["2018-m016-red-minute"] = str(int(float(red_2018["t_min"])))

        dumfries = sorted(
            (
                row for row in player_cards
                if int(row["edition"]) == 2022 and int(row["match_number"]) == 57
                and row["player"] == "DUMFRIES" and row["card_type"] in {"Y", "Y2"}
            ),
            key=lambda row: float(row["t_min"]),
        )
        values["2022-m057-dumfries-scope"] = "|".join(
            f"{row['card_type']}@{row['event_scope']}" for row in dumfries
        )

        reds_2026 = [
            row for row in player_cards
            if int(row["edition"]) == 2026 and int(row["match_number"]) == 1
            and row["card_type"] == "R"
        ]
        values["2026-m001-red-count"] = str(len(reds_2026))
        surname_order = {"Sphephelo SITHOLE": "SITHOLE", "Themba ZWANE": "ZWANE", "Cesar MONTES": "MONTES"}
        values["2026-m001-red-recipients"] = "|".join(
            surname_order[row["player"]] for row in sorted(reds_2026, key=lambda row: float(row["t_min"]))
        )

        self.assertEqual(set(values), {row["check_id"] for row in self.checks})
        for row in self.checks:
            with self.subTest(check_id=row["check_id"]):
                self.assertEqual(row["primary_value"], values[row["check_id"]])
                self.assertTrue(row["independent_source_url"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
