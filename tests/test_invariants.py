"""Property tests required by methodology v0.2."""

from __future__ import annotations

import csv
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from pipeline import build_manifest
from pipeline.build.expanded import STRIPPED_REASONS
from pipeline.build.stages import (
    _validate_sb_reconciliation,
    _validate_source_header,
    _validate_source_table_schema,
    run_stages,
    stage5_availability,
)
from pipeline.config import (
    EDITIONS,
    EXPECTED_CARD_REASON_SB_RECONCILIATION,
    EXPECTED_PLAYER_CARDS,
    SOURCE,
)
from pipeline.event_sources import _player_name_match


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

    def test_card_reason_audit_has_exact_coverage_and_provenance(self):
        source = self.build["source"]
        cards = {row["card_id"]: row for row in source["cards"]}
        expected = {
            row["card_id"] for row in source["cards"]
            if row["recipient_type"] == "player" and row["event_scope"] == "in_play"
        }
        reasons = source["card_reasons"]
        observed = [row["card_id"] for row in reasons]
        self.assertEqual(len(observed), len(set(observed)))
        self.assertEqual(set(observed), expected)
        self.assertEqual(len(observed), 908)

        for row in reasons:
            self.assertIn(
                row["reason_class"],
                {"foul_play", "dissent", "time_wasting", "other_nonfoul", "unknown"},
            )
            self.assertIn(
                row["source_tier"],
                {
                    "1_fifa", "2_federation_or_club", "3_established_mbm",
                    "4_documented_fallback",
                },
            )
            self.assertTrue(row["source_url"].startswith(("https://", "http://")))
            self.assertTrue(row["note"].strip())
            edition = int(cards[row["card_id"]]["edition"])
            if edition in {2014, 2026}:
                self.assertEqual(row["sb_foul_linked"], "not_available")
            else:
                self.assertIn(row["sb_foul_linked"], {"yes", "no", "unmatched"})
            disagreement = (
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
            if disagreement:
                self.assertIn("AUDIT", row["note"])

        reconciliation = source["card_reason_sb_reconciliation"]
        observed_reconciliation = {
            (int(row["edition"]), row["event_type"]): (
                int(row["in_play_census_events"]),
                int(row["outside_in_play_census_events"]),
                int(row["all_card_events"]),
                row["outside_scope_summary"],
            )
            for row in reconciliation
        }
        self.assertEqual(len(reconciliation), 4)
        self.assertEqual(
            observed_reconciliation, EXPECTED_CARD_REASON_SB_RECONCILIATION
        )
        for row in reconciliation:
            self.assertEqual(
                row["source_url"], "https://github.com/statsbomb/open-data"
            )
        full_bad_behaviour = {
            edition: observed_reconciliation[(edition, "Bad Behaviour")][2]
            for edition in (2018, 2022)
        }
        self.assertEqual(full_bad_behaviour, {2018: 40, 2022: 44})
        other_source_audits = {
            row["card_id"] for row in reasons
            if "AUDIT" in row["note"]
            and row["sb_foul_linked"] == "not_available"
        }
        self.assertEqual(other_source_audits, {"2026-087-1220002040"})

    def test_card_reason_public_schema_rejects_extra_fields(self):
        row = {
            "card_id": "card", "reason_class": "unknown",
            "sb_foul_linked": "not_available",
            "source_url": "https://example.invalid/source",
            "source_tier": "3_established_mbm", "note": "No reason stated.",
            "verbatim_quote": "must not cross the public boundary",
        }
        with self.assertRaisesRegex(ValueError, "frozen schema"):
            _validate_source_table_schema("card_reasons", [row])
        with self.assertRaisesRegex(ValueError, "frozen schema"):
            _validate_source_header(
                "card_reasons",
                (
                    "card_id", "reason_class", "sb_foul_linked", "source_url",
                    "source_tier", "note", "note",
                ),
            )
        reconciliation = list(self.build["source"]["card_reason_sb_reconciliation"])
        with self.assertRaisesRegex(ValueError, "audited counts"):
            _validate_sb_reconciliation(reconciliation[:-1])

    def test_stripped_ledger_rebuild_and_served_term_retention(self):
        source = self.build["source"]
        removed = {
            row["card_id"] for row in source["card_reasons"]
            if row["reason_class"] in STRIPPED_REASONS
        }
        full_ids = {row["card_id"] for row in self.build["cards"]}
        stripped_ids = {row["card_id"] for row in self.build["stripped_cards"]}
        self.assertEqual(stripped_ids, full_ids - removed)
        self.assertEqual(len(removed), 65)

        stripped_suspensions = self.build["stripped_suspensions"]
        self.assertTrue(all(
            not row["trigger_card_id"] or row["trigger_card_id"] in stripped_ids
            for row in stripped_suspensions
        ))
        full_external = {
            row["suspension_id"] for row in self.build["suspensions"]
            if not row["trigger_card_id"]
        }
        stripped_external = {
            row["suspension_id"] for row in stripped_suspensions
            if not row["trigger_card_id"]
        }
        self.assertEqual(stripped_external, full_external)
        stripped_suspension_ids = {
            row["suspension_id"] for row in stripped_suspensions
        }
        removed_trigger_terms = {
            row["suspension_id"] for row in self.build["suspensions"]
            if row["trigger_card_id"] in removed
        }
        self.assertTrue(removed_trigger_terms)
        self.assertFalse(removed_trigger_terms & stripped_suspension_ids)

    def test_expanded_omega_and_secondary_boundaries(self):
        by_player = {}
        for row in self.build["expanded_players"]:
            key = (int(row["edition"]), row["team_id"], row["player_id"])
            by_player.setdefault(key, {})[row["ledger"]] = row
        self.assertTrue(by_player)
        for ledgers in by_player.values():
            self.assertEqual(set(ledgers), {"full", "stripped"})
            self.assertEqual(ledgers["full"]["omega"], ledgers["stripped"]["omega"])
            self.assertTrue(ledgers["full"]["exp_susp_prime_min"])
            self.assertFalse(ledgers["stripped"]["exp_susp_prime_min"])

    def test_all_new_2026_rows_are_provisional_m100(self):
        for table_name in (
            "stripped_cards", "stripped_suspensions", "expanded_players",
            "expanded_teams", "md2", "timing", "stripped_correlations",
            "cumulative_cards", "cumulative_team_matches",
        ):
            rows = [
                row for row in self.build[table_name]
                if int(row["edition"]) == 2026
            ]
            self.assertTrue(rows, table_name)
            self.assertEqual(
                {row["edition_status"] for row in rows}, {"provisional_M100"},
                table_name,
            )
        for table_name in (
            "foul_event_segments", "card_event_order",
            "team_match_card_order", "team_outcomes",
        ):
            rows = [
                row for row in self.build["source"][table_name]
                if int(row["edition"]) == 2026
            ]
            self.assertTrue(rows, table_name)
            self.assertEqual(
                {row["edition_status"] for row in rows}, {"provisional_M100"},
                table_name,
            )
        audit_rows = [
            row for row in self.build["expanded_audit"]
            if str(row["edition"]) == "2026"
        ]
        self.assertTrue(audit_rows)
        self.assertEqual(
            {row["edition_status"] for row in audit_rows}, {"provisional_M100"}
        )

    def test_public_cumulative_tables_exclude_provider_native_keys(self):
        forbidden = {
            "provider_match_id", "provider_event_id", "provider_sequence_index",
            "provider_event_order_key", "provider_linked_event_reference",
            "sb_match_id", "sb_event_id", "order_key",
        }
        for table_name in (
            "foul_event_segments", "card_event_order", "team_match_card_order",
        ):
            rows = self.build["source"][table_name]
            self.assertTrue(rows)
            self.assertFalse(forbidden & set(rows[0]))
            for row in rows:
                if row.get("provider", "").startswith("StatsBomb"):
                    self.assertEqual(
                        row["source_url"], "https://github.com/statsbomb/open-data"
                    )
        for table_name in ("cumulative_cards", "cumulative_team_matches"):
            rows = self.build[table_name]
            self.assertTrue(rows)
            self.assertFalse(forbidden & set(rows[0]))
            for row in rows:
                if row.get("provider", "").startswith("StatsBomb"):
                    url_field = (
                        "event_source_url" if table_name == "cumulative_cards"
                        else "source_url"
                    )
                    self.assertEqual(
                        row[url_field], "https://github.com/statsbomb/open-data"
                    )

    def test_statsbomb_identity_aliases_do_not_enable_minute_only_fallback(self):
        matched, _ = _player_name_match(
            "CASEMIRO", "Carlos Henrique Casimiro"
        )
        self.assertTrue(matched)
        unmatched, _ = _player_name_match(
            "UNRELATED PLAYER", "Carlos Henrique Casimiro"
        )
        self.assertFalse(unmatched)

    def test_full_manifest_refuses_missing_raw_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_raw = Path(directory) / "raw"
            output = Path(directory) / "manifest.txt"
            with mock.patch.object(
                build_manifest, "REQUIRED_INPUTS", (missing_raw,)
            ):
                with self.assertRaisesRegex(
                    FileNotFoundError, "refusing to write a partial full manifest"
                ):
                    list(build_manifest.iter_inputs(output))

    def test_exposure_is_nonnegative(self):
        self.assertTrue(all(float(row["exp_match_min"] or 0) >= 0 for row in self.build["match"]))
        self.assertTrue(all(float(row["exp_susp_min"] or 0) >= 0 for row in self.build["teams"]))

    def test_omega_is_bounded(self):
        values = [float(row["omega"]) for row in self.build["omega"]]
        self.assertTrue(values)
        self.assertGreaterEqual(min(values), 0)
        self.assertLessEqual(max(values), 1)

    def test_full_carded_player_availability_grid(self):
        source = self.build["source"]
        carded = {
            (int(row["edition"]), row["team_id"], row["player_id"])
            for row in source["cards"] if row["recipient_type"] == "player"
        }
        matches_by_team = {}
        teams_by_edition = {edition: set() for edition in EDITIONS}
        for row in source["matches"]:
            edition = int(row["edition"])
            number = int(row["match_number"])
            for side in ("home", "away"):
                team_id = row[f"{side}_team_id"]
                teams_by_edition[edition].add(team_id)
                matches_by_team.setdefault((edition, team_id), set()).add(number)
        self.assertEqual(
            {edition: len(teams) for edition, teams in teams_by_edition.items()},
            {2014: 32, 2018: 32, 2022: 32, 2026: 48},
        )

        expected_grid = {
            (edition, team_id, player_id, match_number)
            for edition, team_id, player_id in carded
            for match_number in matches_by_team[(edition, team_id)]
        }
        participation_grid = [
            (
                int(row["edition"]), row["team_id"], row["player_id"],
                int(row["match_number"]),
            )
            for row in source["player_match"]
        ]
        availability_grid = [
            (
                int(row["edition"]), row["team_id"], row["player_id"],
                int(row["match_number"]),
            )
            for row in self.build["availability"]
        ]
        self.assertEqual(len(participation_grid), len(set(participation_grid)))
        self.assertEqual(len(availability_grid), len(set(availability_grid)))
        self.assertEqual(set(participation_grid), expected_grid)
        self.assertEqual(set(availability_grid), expected_grid)

        omega_keys = {
            (int(row["edition"]), row["team_id"], row["player_id"])
            for row in self.build["omega"]
        }
        self.assertEqual(omega_keys, carded)
        for row in self.build["omega"]:
            denominator = (
                float(row["team_nominal_minutes"])
                - float(row["union_unavailable_minutes"])
            )
            self.assertGreater(denominator, 0)
            self.assertAlmostEqual(
                float(row["opportunity_denominator_minutes"]), denominator, places=7
            )
            self.assertAlmostEqual(
                float(row["omega"]), float(row["played_minutes"]) / denominator,
                places=7,
            )

    def test_served_suspensions_have_absent_lineup_provenance(self):
        participation = {
            (
                int(row["edition"]), row["team_id"], row["player_id"],
                int(row["match_number"]),
            ): row
            for row in self.build["source"]["player_match"]
        }
        served = [
            row for row in self.build["suspensions"]
            if row["service_status"] == "served"
        ]
        self.assertTrue(served)
        for row in served:
            key = (
                int(row["edition"]), row["team_id"], row["player_id"],
                int(row["service_match_number"]),
            )
            self.assertIn(key, participation)
            observed = participation[key]
            self.assertEqual(row["lineup_status"], "absent")
            self.assertEqual(observed["lineup_status"], "absent")
            self.assertEqual(row["lineup_source_url"], observed["source_url"])
            self.assertEqual(
                row["lineup_source_archive"], observed["source_archive"]
            )

    def test_unexplained_absence_stays_in_denominator(self):
        tables = {
            "availability_evidence": [],
            "player_match": [{
                "edition": "2014", "team_id": "team", "team": "Team",
                "player_id": "player", "player": "Player", "match_number": "1",
                "match_id": "match", "stage": "group", "opponent": "Opponent",
                "team_match_number": "1", "nominal_minutes": "90",
                "lineup_status": "absent", "played_minutes": "0",
                "source_url": "https://example.invalid/lineup",
                "source_archive": "data/raw/example.json",
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            availability, omega = stage5_availability(
                tables, [], [], Path(directory)
            )
        self.assertEqual(len(availability), 1)
        self.assertEqual(availability[0]["availability_status"], "unexplained")
        self.assertEqual(availability[0]["injury_unavailable_minutes"], "0")
        self.assertEqual(availability[0]["union_unavailable_minutes"], "0")
        self.assertEqual(
            availability[0]["opportunity_denominator_minutes"], "90"
        )
        self.assertEqual(len(omega), 1)
        self.assertEqual(omega[0]["omega"], "0")

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
