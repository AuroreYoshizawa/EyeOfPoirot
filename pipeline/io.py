"""Small deterministic CSV and value helpers (standard library only)."""

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path
from typing import Iterable, Mapping


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[Mapping], fieldnames: Iterable[str] | None = None) -> None:
    materialized = [dict(row) for row in rows]
    if fieldnames is None:
        if not materialized:
            raise ValueError(f"fieldnames required for empty table: {path}")
        fieldnames = materialized[0].keys()
    fields = list(fieldnames)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(materialized)


def as_int(value, default: int | None = None) -> int | None:
    if value is None or str(value).strip() == "":
        return default
    return int(float(str(value)))


def as_float(value, default: float | None = None) -> float | None:
    if value is None or str(value).strip() == "":
        return default
    return float(str(value))


def fmt(value: float | int | None, digits: int = 6) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    rounded = round(float(value), digits)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.{digits}f}".rstrip("0").rstrip(".")


def ascii_tokens(value: str) -> list[str]:
    plain = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().upper()
    return [token for token in re.findall(r"[A-Z0-9]+", plain) if token not in {"JR", "JUNIOR", "II", "III"}]


def name_key(value: str) -> str:
    return "".join(ascii_tokens(value))
