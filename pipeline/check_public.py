#!/usr/bin/env python3
"""Fail if the public tree tracks raw snapshots or recognizable secrets."""

from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

from .config import ROOT


SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
}

EVENT_DERIVED_PUBLIC_CSVS = (
    "data/derived/source/foul_event_segments.csv",
    "data/derived/source/card_event_order.csv",
    "data/derived/source/team_match_card_order.csv",
    "data/derived/source/team_outcomes.csv",
    "data/derived/results/cumulative-fouls-before-card.csv",
    "data/derived/results/cumulative-fouls-before-first-card.csv",
)
FORBIDDEN_PROVIDER_FIELDS = {
    "provider_match_id", "provider_event_id", "provider_sequence_index",
    "provider_event_order_key", "provider_linked_event_reference",
    "sb_match_id", "sb_event_id", "order_key",
}
STATSBOMB_DATASET_URL = "https://github.com/statsbomb/open-data"


def tracked_files() -> list[Path]:
    command = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"],
        cwd=ROOT, capture_output=True, check=False,
    )
    if command.returncode == 0:
        return [ROOT / item.decode() for item in command.stdout.split(b"\0") if item]
    return [
        path for path in ROOT.rglob("*") if path.is_file()
        and ".git" not in path.parts and "tmp" not in path.parts
    ]


def public_event_csv_failures() -> list[str]:
    """Enforce the frozen public/private event-order boundary."""
    failures = []
    for relative in EVENT_DERIVED_PUBLIC_CSVS:
        path = ROOT / relative
        if not path.exists():
            failures.append(f"missing public event-derived CSV: {relative}")
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or ())
            forbidden = sorted(fields & FORBIDDEN_PROVIDER_FIELDS)
            if forbidden:
                failures.append(
                    f"provider-native field in public CSV {relative}: {forbidden}"
                )
            for line_number, row in enumerate(reader, start=2):
                if not row.get("provider", "").startswith("StatsBomb"):
                    continue
                for field in ("source_url", "event_source_url"):
                    value = row.get(field, "")
                    if value and value != STATSBOMB_DATASET_URL:
                        failures.append(
                            f"non-dataset StatsBomb URL in {relative}:{line_number} "
                            f"field={field}"
                        )
    return failures


def main() -> int:
    files = tracked_files()
    raw = [path for path in files if path.relative_to(ROOT).parts[:2] == ("data", "raw")]
    if raw:
        for path in raw:
            print("tracked private raw file:", path.relative_to(ROOT))
        return 1
    failures = []
    for path in files:
        try:
            if path.stat().st_size > 5_000_000:
                continue
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                failures.append((label, path.relative_to(ROOT)))
    if failures:
        for label, path in failures:
            print(f"possible {label}: {path}")
        return 1
    event_failures = public_event_csv_failures()
    if event_failures:
        for failure in event_failures:
            print(failure)
        return 1
    print(
        f"public-tree check passed: files={len(files)}, raw_tracked=0, "
        "recognizable_secrets=0, provider_native_event_fields=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
