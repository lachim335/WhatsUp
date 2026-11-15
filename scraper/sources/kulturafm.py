"""kulturafm.cz – Kultura F≈M (city culture org of Frýdek-Místek): cinema, theatre, concerts, exhibitions."""
from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from ..common import Event, categorize, clean, fetch, shorten

NAME = "kulturafm.cz"
LISTING = "https://www.kulturafm.cz/filtry"
BASE = "https://www.kulturafm.cz/"

_GCAL_DATES = re.compile(r"dates=(\d{8})T(\d{6})/(\d{8})T(\d{6})")
_DETAIL = re.compile(r"(detail-akce/[^\s\"'&<>]+?/icalrepeat\.detail/-)")


def _dt(d: str, t: str) -> datetime:
    return datetime.strptime(d + t, "%Y%m%d%H%M%S")


def scrape(today: date, horizon_end: date) -> list[Event]:
    soup = BeautifulSoup(fetch(LISTING), "html.parser")
    events: list[Event] = []
    seen: set[str] = set()
    for box in soup.select("div.ea-event[id^=event-]"):
        eid = box.get("id")
        if eid in seen:
            continue
        seen.add(eid)

        title_el = box.select_one(".ea-event-title")
        gcal = box.find("a", href=_GCAL_DATES)
        if not title_el or not gcal:
            continue
        m = _GCAL_DATES.search(gcal["href"])
        start, end = _dt(m.group(1), m.group(2)), _dt(m.group(3), m.group(4))

        title = clean(title_el.get_text())
        cat_el = box.select_one(".ea-event-category")
        src_cat = clean(cat_el.get_text()) if cat_el else None
        icons = clean(box.select_one(".ea-icons-detail").get_text()) if box.select_one(".ea-icons-detail") else ""

        venue_el = box.select_one(".ea-event-info .fa-map-marker-alt")
        venue = clean(venue_el.parent.get_text()) if venue_el else None

        # The detail URL is embedded in the Google Calendar link: details=url:+http://kulturafm.cz/detail-akce/...
        dm = _DETAIL.search(gcal["href"]) or _DETAIL.search(str(box))
        url = "https://www.kulturafm.cz/" + dm.group(1) if dm else LISTING

        img = box.select_one(".ea-event-photo img")
        image = urljoin(BASE, quote(img["src"], safe="/:%")) if img and img.get("src") else None

        tickets_el = box.select_one(".ea-event-buy a[href]")
        detail = box.select_one(".ea-event-detail")
        desc = " ".join(p.get_text(" ") for p in detail.select("p")) if detail else None

        multi_day = end.date() > start.date()
        events.append(Event(
            title=title,
            date=start.date().isoformat(),
            time=start.strftime("%H:%M") if start.time().hour or start.time().minute else None,
            end_date=end.date().isoformat() if multi_day else None,
            end_time=end.strftime("%H:%M") if not multi_day and end > start and end.strftime("%H:%M") != "23:59" else None,
            venue=venue,
            city="Frýdek-Místek",
            region="fm",
            category=categorize(src_cat if src_cat and src_cat != "Ostatní" else None, title),
            url=url,
            image=image,
            description=shorten(desc),
            tickets=tickets_el["href"] if tickets_el else None,
            source=NAME,
            top="Tip" in icons,
            kids="Dětem" in icons,
        ))
    return events
