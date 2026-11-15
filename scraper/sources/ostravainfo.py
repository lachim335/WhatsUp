"""ostravainfo.cz – official Ostrava tourist portal, server-rendered listing, 24 events/page."""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..common import Event, categorize, clean, fetch, parse_czech_range, region_for_city

NAME = "ostravainfo.cz"
HOME = "https://www.ostravainfo.cz/cz/akce/"
BASE = "https://www.ostravainfo.cz/"
PAGE_SIZE = 24
MAX_PAGES = 45

# Venues outside Ostrava proper are sometimes written as "Kostel sv. Valentina, Příbor".
_CITY_SUFFIX = re.compile(r",\s*([A-ZÁ-Ž][^,]+)$")


def _parse_page(html: str, today: date) -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[Event] = []
    for li in soup.select("li.list-event__item"):
        a = li.select_one(".list-event__item__title a")
        when = li.select_one(".in-date__item")
        if not a or not when:
            continue
        parsed = parse_czech_range(when.get_text(" "), today)
        if not parsed:
            continue
        start, end, hhmm = parsed
        url = urljoin(BASE, a.get("href", ""))
        venue_el = li.select_one(".list-event__item__title span")
        venue = clean(venue_el.get_text()) if venue_el else None

        city = "Ostrava"
        if venue:
            m = _CITY_SUFFIX.search(venue)
            if m and "ostrav" not in m.group(1).lower():
                city = m.group(1).strip()
        region = "ostrava" if city == "Ostrava" else region_for_city(city)

        # category = URL segment: /cz/akce/<category>/<id>-<slug>.html
        m = re.search(r"/akce/([^/]+)/\d+", url)
        src_cat = m.group(1) if m else None
        title = clean(a.get("title") or a.get_text())

        img = li.select_one("img")
        img_src = img.get("data-src") or img.get("src") if img else None
        flags = clean(" ".join(x.get_text() for x in li.select(".akce_zrusena, .akce_top, .in-date__item--secondary"))).upper()

        out.append(Event(
            title=title,
            date=start.isoformat(),
            end_date=end.isoformat() if end else None,
            time=hhmm,
            venue=venue,
            city=city,
            region=region,
            category=categorize(src_cat if src_cat != "ostatni" else None, title),
            url=url,
            image=urljoin(BASE, img_src) if img_src else None,
            source=NAME,
            top="TOP" in flags or "TIP" in flags,
            sold_out="VYPRODÁNO" in flags,
            kids=src_cat == "rodina",
        ))
    return out


def scrape(today: date, horizon_end: date) -> list[Event]:
    events: list[Event] = []
    seen: set[str] = set()
    for page in range(MAX_PAGES):
        url = HOME if page == 0 else f"{HOME}?from={page * PAGE_SIZE}"
        batch = _parse_page(fetch(url), today)
        if not batch:
            break
        fresh = [e for e in batch if e.url not in seen]
        seen.update(e.url for e in batch)
        events.extend(fresh)
        # The listing is sorted by start date (after a few promoted TOP items on page 1).
        # Stop once a whole page of regular items starts beyond our horizon.
        regular = [e for e in batch if not e.top] or batch
        if min(e.date for e in regular) > horizon_end.isoformat():
            break
    return events
