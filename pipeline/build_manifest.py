#!/usr/bin/env python3
"""Write the SHA-256 inventory for private raw and public source/derived data.

The manifest contains hashes and repository-relative paths only. It does not
publish the raw bytes. The output file excludes itself so regeneration is
stable and can be checked with `shasum -a 256 -c` from the repository root.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "MANIFEST-sha256-2026-07-14.txt"
INPUT_ROOTS = (
    ROOT / "data" / "raw",
    ROOT / "data" / "derived",
    ROOT / "data" / "sources",
)
REQUIRED_INPUTS = (
    ROOT / "data" / "raw",
    ROOT / "data" / "derived" / "source" / "card_reasons.csv",
    ROOT / "data" / "derived" / "source" / "card_reason_sb_reconciliation.csv",
    ROOT / "data" / "derived" / "source" / "foul_event_segments.csv",
    ROOT / "data" / "derived" / "source" / "card_event_order.csv",
    ROOT / "data" / "derived" / "source" / "team_match_card_order.csv",
    ROOT / "data" / "derived" / "source" / "team_outcomes.csv",
    ROOT / "data" / "derived" / "stages" / "s9-stripped-card-ledger.csv",
    ROOT / "data" / "derived" / "stages" / "s10-stripped-suspensions.csv",
    ROOT / "data" / "derived" / "stages" / "s11-expanded-player-suspension-exposure.csv",
    ROOT / "data" / "derived" / "results" / "expanded-suspension-exposure.csv",
    ROOT / "data" / "derived" / "results" / "md2-suspension-exposure.csv",
    ROOT / "data" / "derived" / "results" / "card-timing-displacement.csv",
    ROOT / "data" / "derived" / "results" / "stripped-disclosed-correlations.csv",
    ROOT / "data" / "derived" / "results" / "cumulative-fouls-before-card.csv",
    ROOT / "data" / "derived" / "results" / "cumulative-fouls-before-first-card.csv",
    ROOT / "data" / "derived" / "results" / "expanded-audit.csv",
    ROOT / "data" / "sources" / "card-reason-evidence.md",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_inputs(output: Path):
    missing = [path for path in REQUIRED_INPUTS if not path.exists()]
    if missing:
        def display(path: Path) -> str:
            try:
                return path.relative_to(ROOT).as_posix()
            except ValueError:
                return str(path)

        relative = ", ".join(display(path) for path in missing)
        raise FileNotFoundError(
            "refusing to write a partial full manifest; missing: " + relative
        )
    for base in INPUT_ROOTS:
        for path in base.rglob("*"):
            if not path.is_file() or path == output:
                continue
            if path.name in {".DS_Store"} or path.name.startswith("._"):
                continue
            yield path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    rows = []
    for path in sorted(set(iter_inputs(output)), key=lambda item: item.relative_to(ROOT).as_posix()):
        rows.append(f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} hashes to {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
