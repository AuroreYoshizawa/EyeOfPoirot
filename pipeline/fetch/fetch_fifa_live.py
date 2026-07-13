#!/usr/bin/env python3
"""Archive FIFA live match payloads containing line-ups and substitutions."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from pipeline.config import EDITIONS, EXPECTED_COMPLETED, RAW


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) EyeOfPoirot/0.2"
MIN_GAP = 0.42
_last_request = 0.0


def loc(value) -> str:
    if isinstance(value, list) and value:
        return value[0].get("Description", "")
    return value or ""


def get(url: str) -> bytes:
    global _last_request
    errors = []
    for attempt in range(3):
        wait = MIN_GAP - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
            _last_request = time.monotonic()
            return payload
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            if attempt < 2:
                time.sleep(0.8 * 2**attempt)
    raise RuntimeError(f"failed {url}: {errors}")


def valid(path: Path, match_id: str) -> bool:
    try:
        payload = json.loads(path.read_text())
        return (
            isinstance(payload, dict)
            and str(payload.get("IdMatch")) == match_id
            and len((payload.get("HomeTeam") or {}).get("Players", [])) >= 11
            and len((payload.get("AwayTeam") or {}).get("Players", [])) >= 11
        )
    except (OSError, json.JSONDecodeError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("years", nargs="*", type=int, default=list(EDITIONS))
    args = parser.parse_args()
    counts = {}
    for year in args.years:
        if year not in EDITIONS:
            raise ValueError(f"unsupported edition: {year}")
        calendar = json.loads((RAW / str(year) / "fifa" / "calendar.json").read_text())["Results"]
        rows = [row for row in calendar if int(row["MatchNumber"]) <= EXPECTED_COMPLETED[year]]
        out = RAW / str(year) / "fifa" / "live"
        out.mkdir(parents=True, exist_ok=True)
        for row in rows:
            number = int(row["MatchNumber"])
            match_id = str(row["IdMatch"])
            url = (
                "https://api.fifa.com/api/v3/live/football/"
                f"{row['IdCompetition']}/{row['IdSeason']}/{row['IdStage']}/{match_id}?language=en"
            )
            target = out / f"m{number:03d}_{match_id}.json"
            if not valid(target, match_id):
                target.write_bytes(get(url))
            if not valid(target, match_id):
                raise ValueError(f"{year} m{number:03d}: invalid live payload")
        counts[year] = len(rows)
        print(f"{year}: archived/validated {len(rows)} live payloads", flush=True)
    print("total", sum(counts.values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
