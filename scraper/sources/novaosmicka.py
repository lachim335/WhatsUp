"""Nová Osmička (Frýdek-Místek) – official public API, documented at https://www.novaosmicka.cz/developers"""
from __future__ import annotations

import json
from datetime import date

from ..common import Event, categorize, clean, fetch, shorten

NAME = "novaosmicka.cz"
HOME = "https://www.novaosmicka.cz/program"
API = "https://www.novaosmicka.cz/api/v1/events?upcoming=true&per_page=100&lang=cs&page={page}"


def _time(t: str | None) -> str | None:
    return t[:5] if t else None


def scrape(today: date, horizon_end: date) -> list[Event]:
    events: list[Event] = []
    page, last = 1, 1
    while page <= min(last, 10):
        data = json.loads(fetch(API.format(page=page)))
        last = data.get("meta", {}).get("last_page", 1)
        for e in data.get("data", []):
            if e.get("status") != "published" or e.get("cancelled_at"):
                continue
            tags = [t.get("name", "") for t in e.get("tags") or []]
            cat_name = (e.get("category") or {}).get("name")
            loc = (e.get("location") or {}).get("name")
            start, end = e["date_from"], e.get("date_to")
            events.append(Event(
                title=clean(e["name"]),
                date=start,
                end_date=end if end and end != start else None,
                time=_time(e.get("time_from")),
                end_time=_time(e.get("time_to")) if not end or end == start else None,
                venue=f"Nová Osmička – {loc}" if loc else "Nová Osmička",
                city="Frýdek-Místek",
                region="fm",
                category=categorize(cat_name, " ".join(tags), e["name"]),
                url=f"https://www.novaosmicka.cz/program/{e['slug']}",
                image=e.get("banner_url"),
                description=shorten(e.get("short_description") or e.get("description")),
                tickets=e.get("tickets_url"),
                source=NAME,
                kids=any(t in ("Pro děti", "Pro rodiny") for t in tags),
                tags=[t for t in tags if t in ("Vstup zdarma", "Venkovní", "Živá hudba")],
            ))
        page += 1
    return events
