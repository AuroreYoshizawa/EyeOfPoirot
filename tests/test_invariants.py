"""Property tests required by methodology v0.2."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from pipeline.build.stages import run_stages
from pipeline.config import EDITIONS, EXPECTED_PLAYER_CARDS, SOURCE


def read(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class FrozenInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        cls.build = run_stages(SOURCE, root / "stages", root / "results")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_player_card_census(self):
        for edition, expected in EXPECTED_PLAYER_CARDS.items():
            observed = sum(1 for row in self.build["cards"] if int(row["edition"]) == edition)
            self.assertEqual(observed, expected)

    def test_exposure_is_nonnegative(self):
        self.assertTrue(all(float(row["exp_match_min"] or 0) >= 0 for row in self.build["match"]))
        self.assertTrue(all(float(row["exp_susp_min"] or 0) >= 0 for row in self.build["teams"]))

    def test_omega_is_bounded(self):
        values = [float(row["omega"]) for row in self.build["omega"]]
        self.assertTrue(values)
        self.assertGreaterEqual(min(values), 0)
        self.assertLessEqual(max(values), 1)

    def test_horizon_never_exceeds_reset_only_horizon(self):
        for row in self.build["cards"]:
            self.assertLessEqual(int(row["effective_horizon"]), int(row["base_horizon"]))

    def test_match_differences_are_antisymmetric(self):
        lookup = {
            (int(row["edition"]), int(row["match_number"]), row["team_id"]): row
            for row in self.build["match"]
        }
        for row in self.build["match"]:
            opponent = lookup[(int(row["edition"]), int(row["match_number"]), row["opponent_team_id"])]
            self.assertAlmostEqual(float(row["d_exp_match"]), -float(opponent["d_exp_match"]), places=7)
            if row["d_exp_match_per_foul"] and opponent["d_exp_match_per_foul"]:
                self.assertAlmostEqual(
                    float(row["d_exp_match_per_foul"]),
                    -float(opponent["d_exp_match_per_foul"]), places=7,
                )

    def test_positive_injury_intervals_have_urls(self):
        for row in self.build["source"]["availability_evidence"]:
            if float(row["unavailable_minutes"]) > 0:
                self.assertTrue(row["source_url"])

    def test_2026_cutoff(self):
        for table_name in ("cards", "match", "availability"):
            for row in self.build[table_name]:
                if int(row["edition"]) == 2026:
                    self.assertLessEqual(int(row["match_number"]), 100)

    def test_sensitivity_grid_is_complete(self):
        self.assertEqual(len(self.build["sensitivity"]), 4 * 3 * 3 * 2)
        for edition in EDITIONS:
            rows = [row for row in self.build["sensitivity"] if int(row["edition"]) == edition]
            self.assertEqual(len(rows), 18)

    def test_documented_disciplinary_decisions_override_defaults(self):
        suspensions = {row["suspension_id"]: row for row in self.build["suspensions"]}
        for match_number in (25, 54, 73):
            row = suspensions[
                f"2026-001-1759804476-dismissal-service-M{match_number}"
            ]
            self.assertEqual(row["service_status"], "served")
            self.assertEqual(row["decision_type"], "extended_suspension")
        balogun = suspensions["2026-081-1246412996-dismissal-service-M94"]
        self.assertEqual(balogun["service_status"], "deferred")
        self.assertEqual(balogun["lineup_status"], "starter")
        guarin = suspensions["2014-external-43926-200219-service-M5"]
        self.assertEqual(guarin["service_status"], "served")
        self.assertEqual(guarin["decision_type"], "carry_in_suspension")
        quansah = suspensions["2026-092-1977498691-dismissal-service-M99"]
        self.assertEqual(quansah["service_status"], "served")
        self.assertEqual(quansah["decision_type"], "extended_suspension")

    def test_end_minus_one_sensitivity_never_increases_exposure(self):
        match_rows = {
            (
                int(row["edition"]), int(row["match_number"]), row["team_id"],
                row["clock_variant"],
            ): row
            for row in self.build["match_clock_sensitivity"]
        }
        reductions = 0
        for key, source in match_rows.items():
            if key[3] != "source_end":
                continue
            alternate = match_rows[(key[0], key[1], key[2], "end_minus_one")]
            self.assertLessEqual(
                float(alternate["exp_match_min"]), float(source["exp_match_min"])
            )
            reductions += float(alternate["exp_match_min"]) < float(source["exp_match_min"])
        self.assertGreater(reductions, 0)

        suspension_rows = {
            (int(row["edition"]), row["denominator"], row["clock_variant"]): row
            for row in self.build["suspension_clock_sensitivity"]
        }
        for edition in EDITIONS:
            for denominator in ("all", "knockout"):
                source = suspension_rows[(edition, denominator, "source_end")]
                alternate = suspension_rows[(edition, denominator, "end_minus_one")]
                self.assertLessEqual(
                    float(alternate["exp_susp_min"]), float(source["exp_susp_min"])
                )

    def test_pooled_ratio_uses_ratio_of_sums(self):
        for summary in self.build["summaries"]:
            edition = int(summary["edition"])
            teams = [
                row for row in self.build["teams"]
                if int(row["edition"]) == edition and row["primary_cohort"] == "yes"
            ]
            expected = sum(float(row["exp_susp_min"]) for row in teams) / sum(
                int(row["fouls_all"]) for row in teams
            )
            self.assertAlmostEqual(
                float(summary["pooled_exp_susp_per_foul"]), expected, places=5
            )

    def test_penalty_shootout_cards_do_not_enter_match_exposure(self):
        shootout = [row for row in self.build["cards"] if row["event_scope"] == "penalty_shootout"]
        self.assertTrue(shootout)
        for row in shootout:
            self.assertEqual(float(row["exp_match_min_rho_2"]), 0)


if __name__ == "__main__":
    unittest.main()
