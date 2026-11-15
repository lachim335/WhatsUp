"""Scrape all sources and write a single JSON feed for the static site.

    python -m scraper.main --out site/data/events.json --weeks 5
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
import zlib
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .common import Event, dedupe_key, fold
from .sources import kudyznudy, kulturafm, ostravainfo

TZ = ZoneInfo("Europe/Prague")
# Order = priority when the same event appears in several sources.
SOURCES = [
    (ostravainfo, "https://www.ostravainfo.cz/cz/akce/"),
    (kulturafm, "https://www.kulturafm.cz/program"),
    (kudyznudy, "https://www.kudyznudy.cz/kalendar-akci/moravskoslezsky-kraj"),
]
LONG_RUNNING_DAYS = 7


def collapse_daily_runs(events: list[Event], min_run: int = 3) -> list[Event]:
    """Some sources list an exhibition as a separate all-day event for every day.
    Merge runs of consecutive days (same title + venue, no start time) into one ranged event."""
    groups: dict[tuple, list[Event]] = defaultdict(list)
    rest: list[Event] = []
    for e in events:
        if e.time or e.end_date:
            rest.append(e)
        else:
            groups[(fold(e.title), e.venue)].append(e)

    for items in groups.values():
        items.sort(key=lambda e: e.date)
        run: list[Event] = []

        def flush():
            if len(run) >= min_run:
                first = run[0]
                first.end_date = run[-1].date
                rest.append(first)
            else:
                rest.extend(run)

        for e in items:
            if run and (date.fromisoformat(e.date) - date.fromisoformat(run[-1].date)).days > 1:
                flush()
                run = []
            if not run or e.date != run[-1].date:
                run.append(e)
        flush()
    return rest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site/data/events.json")
    ap.add_argument("--weeks", type=int, default=5, help="how far ahead to keep events")
    ap.add_argument("--only", help="run a single source (module name), for debugging")
    args = ap.parse_args()

    now = datetime.now(TZ)
    today = now.date()
    horizon_end = today + timedelta(weeks=args.weeks)

    merged: dict[str, dict] = {}
    report = []
    for module, home in SOURCES:
        if args.only and module.__name__.rsplit(".", 1)[-1] != args.only:
            continue
        entry = {"name": module.NAME, "url": home, "count": 0, "ok": True}
        try:
            events = collapse_daily_runs(module.scrape(today, horizon_end))
        except Exception as exc:  # one broken source must not kill the feed
            traceback.print_exc()
            entry.update(ok=False, error=f"{type(exc).__name__}: {exc}"[:300])
            report.append(entry)
            continue

        kept = 0
        for e in events:
            last_day = e.end_date or e.date
            if last_day < today.isoformat() or e.date > horizon_end.isoformat():
                continue
            key = dedupe_key(e)
            if key in merged:
                # keep the higher-priority record, but borrow missing bits from this one
                prev = merged[key]
                for f in ("image", "description", "tickets", "time", "venue"):
                    val = getattr(e, f)
                    if val and not prev.get(f):
                        prev[f] = val
                continue
            d = e.to_json()
            span = (date.fromisoformat(last_day) - date.fromisoformat(e.date)).days
            if span > LONG_RUNNING_DAYS:
                d["long"] = True
            d["id"] = f"{module.__name__.rsplit('.', 1)[-1]}-{zlib.crc32(key.encode()):08x}"
            merged[key] = d
            kept += 1
        entry["count"] = kept
        report.append(entry)
        print(f"{module.NAME}: {len(events)} scraped, {kept} kept", file=sys.stderr)

    events = sorted(merged.values(), key=lambda d: (d["date"], d.get("time") or "99:99", d["title"]))
    feed = {
        "generated": now.isoformat(timespec="seconds"),
        "from": today.isoformat(),
        "to": horizon_end.isoformat(),
        "sources": report,
        "events": events,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(feed, ensure_ascii=False, separators=(",", ":"))
    out.write_text(payload, encoding="utf-8")
    # Same data as a script, so the page also works when opened straight from disk (file://).
    out.with_suffix(".js").write_text(f"window.__FEED__={payload};\n", encoding="utf-8")
    print(f"wrote {len(events)} events -> {out}", file=sys.stderr)

    if not events:
        print("ERROR: no events at all, refusing to publish an empty feed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
