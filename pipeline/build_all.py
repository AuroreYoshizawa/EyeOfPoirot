#!/usr/bin/env python3
"""One-command public and raw-owner builds for methodology v0.2."""

from __future__ import annotations

import argparse

from .build.stages import run_stages
from .report import generate_reports
from .source import build_sources


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--from-derived", action="store_true",
        help="rebuild results/figures from committed normalized source CSVs without network access",
    )
    mode.add_argument(
        "--from-raw", action="store_true",
        help="re-extract normalized source CSVs from the private raw archive, then rebuild everything",
    )
    args = parser.parse_args()
    if args.from_raw:
        counts = build_sources()
        print("source extraction:", ", ".join(f"{key}={value}" for key, value in counts.items()))
    build = run_stages()
    generated = generate_reports(build)
    print(
        "analysis build:",
        f"cards={len(build['cards'])}",
        f"match_rows={len(build['match'])}",
        f"team_rows={len(build['teams'])}",
        f"sensitivity_rows={len(build['sensitivity'])}",
    )
    print(f"reports/figures generated: {len(generated)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
