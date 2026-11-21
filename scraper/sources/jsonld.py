"""Generic schema.org Event (JSON-LD) source – for venue websites that embed structured event data.

Add a venue by appending to SOURCES in scraper/main.py, e.g.
    jsonld.page("barrak-club.cz", "https://www.barrak-club.cz/cz", venue="Barrák Music Club", city="Ostrava")
"""
from __future__ import annotations

import html
import json
import re
from datetime import date, datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from ..common import Event, categorize, clean, fetch, region_for_city, shorten

TZ = ZoneInfo("Europe/Prague")
_LD = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)


def find_events(page: str) -> list[dict]:
    found: list[dict] = []

    def walk(x):
        if isinstance(x, list):
            for i in x:
                walk(i)
        elif isinstance(x, dict):
            if "Event" in str(x.get("@type", "")):
                found.append(x)
            else:
                for v in x.values():
                    walk(v)

    for block in _LD.findall(page):
        try:
            walk(json.loads(block, strict=False))
        except json.JSONDecodeError:
            continue
    return found


def _when(value: str) -> tuple[date, str | None]:
    v = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return date.fromisoformat(v), None
    dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    if dt.tzinfo:
        dt = dt.astimezone(TZ)
    return dt.date(), dt.strftime("%H:%M")


def _first(x):
    return x[0] if isinstance(x, list) and x else x


def page(name: str, url: str, *, venue: str, city: str, default_category: str = "hudba",
         category: str | None = None):
    """Build a source entry (name, homepage, scrape function) for one page with JSON-LD events."""

    def scrape(today: date, horizon_end: date) -> list[Event]:
        out: list[Event] = []
        for ev in find_events(fetch(url)):
            if not ev.get("name") or not ev.get("startDate"):
                continue
            if "Cancelled" in str(ev.get("eventStatus", "")):
                continue
            try:
                d, t = _when(ev["startDate"])
                end_d, end_t = _when(ev["endDate"]) if ev.get("endDate") else (None, None)
            except ValueError:
                continue
            if end_d and t and (end_d - d).days <= 1:
                end_d = None  # overnight, not multi-day
            title = clean(html.unescape(ev["name"]))
            offers = _first(ev.get("offers")) or {}
            image = _first(ev.get("image"))
            if isinstance(image, dict):
                image = image.get("url")
            link = ev.get("url") or url
            out.append(Event(
                title=title,
                date=d.isoformat(),
                time=t,
                end_date=end_d.isoformat() if end_d and end_d > d else None,
                end_time=end_t if end_d is None and end_t and end_t != t else None,
                venue=venue,
                city=city,
                region=region_for_city(city),
                category=category or (c if (c := categorize(title)) != "ostatni" else default_category),
                url=urljoin(url, link),
                image=urljoin(url, image) if isinstance(image, str) else None,
                description=shorten(html.unescape(ev.get("description") or "")),
                tickets=offers.get("url") if isinstance(offers, dict) else None,
                source=name,
                sold_out="SoldOut" in str(offers.get("availability", "")) if isinstance(offers, dict) else False,
            ))
        return out

    return name, url, scrape
