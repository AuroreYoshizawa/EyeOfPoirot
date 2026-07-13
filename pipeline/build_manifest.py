#!/usr/bin/env python3
"""Write the frozen SHA-256 inventory for private raw and public derived data.

The manifest contains hashes and repository-relative paths only. It does not
publish the raw bytes. The output file excludes itself so regeneration is
stable and can be checked with `shasum -a 256 -c` from the repository root.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "MANIFEST-sha256-2026-07-13.txt"
INPUT_ROOTS = (ROOT / "data" / "raw", ROOT / "data" / "derived")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_inputs(output: Path):
    for base in INPUT_ROOTS:
        if not base.exists():
            continue
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
