"""kudyznudy.cz – CzechTourism calendar. Only the first page per area is reachable without
ASP.NET postbacks, so this is a supplement (fairs, markets, festivals around the region)."""
from __future__ import annotations

from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..common import Event, categorize, clean, fetch, region_for_city, shorten

NAME = "kudyznudy.cz"
BASE = "https://www.kudyznudy.cz/"
AREAS = [
    "kalendar-akci/moravskoslezsky-kraj/ostravsko",
    "kalendar-akci/moravskoslezsky-kraj/beskydy-a-valassko",
]


def _meta(item, prop: str) -> str | None:
    el = item.find("meta", attrs={"itemprop": prop})
    return el.get("content") if el else None


def scrape(today: date, horizon_end: date) -> list[Event]:
    events: list[Event] = []
    for area in AREAS:
        soup = BeautifulSoup(fetch(urljoin(BASE, area)), "html.parser")
        for item in soup.select('[itemtype$="schema.org/Event"]'):
            name = item.select_one('[itemprop="name"]')
            link = item.select_one("h3 a[href]")
            start = _meta(item, "startDate")
            if not name or not link or not start:
                continue
            end = _meta(item, "endDate")
            loc = item.select_one('[itemprop="location"] [itemprop="name"]')
            city = clean(loc.get_text()).split(",")[0] if loc else None
            img = item.select_one("img[src]")
            title = clean(name.get_text())
            desc = _meta(item, "description")
            events.append(Event(
                title=title,
                date=start[:10],
                end_date=end[:10] if end and end[:10] != start[:10] else None,
                city=city,
                venue=None,
                region=region_for_city(city),
                category=categorize(title, desc),
                url=urljoin(BASE, link["href"]),
                image=img["src"] if img else None,
                description=shorten(desc),
                source=NAME,
            ))
    return events
