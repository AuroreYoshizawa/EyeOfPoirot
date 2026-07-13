"""Rendering checks for the generated Markdown report."""

from __future__ import annotations

import unittest

from pipeline.config import EDITIONS, RESULTS, SOURCE
from pipeline.io import read_csv
from pipeline.report import _markdown_table, _winner_match_rows


class MarkdownReportTests(unittest.TestCase):
    def test_table_cells_escape_source_value_separators(self):
        table = _markdown_table(
            ["Primary", "Status"],
            [["Brazil=2|Croatia=2", "PASS"]],
        )

        self.assertIn(r"Brazil=2\|Croatia=2", table)
        self.assertNotIn("| Brazil=2|Croatia=2 |", table)

    def test_knockout_figure_rows_use_winners_and_descending_delta(self):
        build = {
            "source": {"matches": read_csv(SOURCE / "matches.csv")},
            "match": read_csv(RESULTS / "match-exposure.csv"),
        }
        for edition in EDITIONS:
            with self.subTest(edition=edition):
                rows = _winner_match_rows(build, edition)
                winners = {
                    int(row["match_number"]): row["winner_team_id"]
                    for row in build["source"]["matches"]
                    if int(row["edition"]) == edition
                    and row["stage"] not in {"group", "third_place"}
                }
                self.assertEqual(len(rows), len(winners))
                self.assertTrue(all(row["stage"] != "third_place" for row in rows))
                self.assertTrue(all(
                    row["team_id"] == winners[int(row["match_number"])]
                    for row in rows
                ))
                deltas = [float(row["d_exp_match"]) for row in rows]
                self.assertEqual(deltas, sorted(deltas, reverse=True))

                prime_rows = _winner_match_rows(
                    build, edition, "d_exp_match_per_foul"
                )
                prime_deltas = [
                    float(row["d_exp_match_per_foul"]) for row in prime_rows
                ]
                self.assertEqual(prime_deltas, sorted(prime_deltas, reverse=True))
                match_lookup = {
                    (int(row["match_number"]), row["team_id"]): row
                    for row in build["match"]
                    if int(row["edition"]) == edition
                }
                for row in prime_rows:
                    opponent = match_lookup[
                        (int(row["match_number"]), row["opponent_team_id"])
                    ]
                    expected = (
                        float(row["exp_match_min"]) / int(row["fouls"])
                        - float(opponent["exp_match_min"]) / int(opponent["fouls"])
                    )
                    self.assertAlmostEqual(
                        float(row["d_exp_match_per_foul"]), expected, places=5
                    )


if __name__ == "__main__":
    unittest.main()
