#!/usr/bin/env python3
"""Archive the free HuffPost/Opta 2014 match-stat JSON layer.

The index exposes exactly 64 English match pages. Each page references a
HTML table whose `*-fouls` cells include match-level fouls. Some historical
JSON callbacks now return 403, so the page itself is the complete archive
target. Existing valid files are reused; requests are throttled and retried.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pipeline.config import RAW


INDEX_URL = "https://data.huffingtonpost.com/2014/world-cup/statistics"
PAGE_PREFIX = "https://data.huffingtonpost.com/2014/world-cup/matches/"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) EyeOfPoirot/0.2"
OUT = RAW / "2014" / "huffpost"
MIN_GAP = 0.45
_last_request = 0.0


def _get(url: str) -> bytes:
    global _last_request
    errors = []
    for attempt in range(3):
        wait = MIN_GAP - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
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


def _valid_json(path: Path) -> bool:
    try:
        json.loads(path.read_text())
        return path.stat().st_size > 1000
    except (OSError, json.JSONDecodeError):
        return False


def _valid_html(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
        return path.stat().st_size > 10000 and text.count("-fouls\"") >= 2 and "Source: Opta" in text
    except OSError:
        return False


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    index_path = OUT / "statistics.html"
    if not index_path.exists() or index_path.stat().st_size < 10000:
        index_path.write_bytes(_get(INDEX_URL))
    html = index_path.read_text(encoding="utf-8")
    pattern = r'href="(/2014/world-cup/matches/([^"/]+)-(\d+))"'
    links = sorted({(path, pair, match_id) for path, pair, match_id in re.findall(pattern, html)})
    if len(links) != 64:
        raise ValueError(f"index exposes {len(links)} unique matches, expected 64")
    records = []
    page_dir = OUT / "matches"
    page_dir.mkdir(exist_ok=True)
    for relative, pair, match_id in links:
        home_slug, away_slug = pair.split("-vs-")
        page_url = f"https://data.huffingtonpost.com{relative}"
        target = page_dir / f"{match_id}.html"
        if not _valid_html(target):
            target.write_bytes(_get(page_url))
        if not _valid_html(target):
            raise ValueError(f"{match_id}: page lacks two foul cells or Opta attribution")
        records.append({
            "huffpost_match_id": int(match_id),
            "home_slug": home_slug,
            "away_slug": away_slug,
            "page_url": page_url,
            "json_url": f"{PAGE_PREFIX}{match_id}.json",
            "archive_path": str(target.relative_to(RAW)),
        })
    snapshot = {
        "source": "HuffPost Data match pages; statistics credited there to Opta",
        "index_url": INDEX_URL,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "matches": records,
    }
    (OUT / "index.json").write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"archived and validated {len(records)} HuffPost/Opta match-stat pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
