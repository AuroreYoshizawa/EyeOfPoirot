#!/usr/bin/env python3
"""Fail if the public tree tracks raw snapshots or recognizable secrets."""

from __future__ import annotations

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
    print(f"public-tree check passed: files={len(files)}, raw_tracked=0, recognizable_secrets=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
