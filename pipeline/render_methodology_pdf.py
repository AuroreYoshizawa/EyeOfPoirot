#!/usr/bin/env python3
"""Render the frozen Markdown methodology to its registration PDF."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "METHODOLOGY.md"
OUTPUT = ROOT / "output" / "pdf" / "METHODOLOGY-v0.2.pdf"
FILTER = ROOT / "pipeline" / "pagebreak_methodology.lua"


def main() -> int:
    for executable in ("pandoc", "xelatex"):
        if shutil.which(executable) is None:
            raise SystemExit(f"missing required executable: {executable}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "pandoc",
            str(SOURCE),
            "--from=markdown+tex_math_dollars",
            "--pdf-engine=xelatex",
            f"--lua-filter={FILTER}",
            "--toc",
            "--metadata",
            "title=Eye of Poirot — Methodology v0.2",
            "-V",
            "geometry:margin=0.72in",
            "-V",
            "fontsize=10pt",
            "-V",
            "colorlinks=true",
            "-V",
            "linkcolor=blue",
            "-V",
            "urlcolor=blue",
            "-o",
            str(OUTPUT),
        ],
        cwd=ROOT,
        check=True,
    )
    print(OUTPUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
