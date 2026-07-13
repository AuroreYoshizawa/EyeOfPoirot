"""Rendering checks for the generated Markdown report."""

from __future__ import annotations

import unittest

from pipeline.report import _markdown_table


class MarkdownReportTests(unittest.TestCase):
    def test_table_cells_escape_source_value_separators(self):
        table = _markdown_table(
            ["Primary", "Status"],
            [["Brazil=2|Croatia=2", "PASS"]],
        )

        self.assertIn(r"Brazil=2\|Croatia=2", table)
        self.assertNotIn("| Brazil=2|Croatia=2 |", table)


if __name__ == "__main__":
    unittest.main()
