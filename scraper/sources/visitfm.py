"""visitfm.cz – tourist information centre of Frýdek-Místek; events in F-M and the surrounding Beskydy
(Hukvaldy, Čeladná, Baška…). Server-rendered list, 10 items/page, sorted by start date."""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from ..common import Event, categorize, clean, fetch, fold, region_for_city

NAME = "visitfm.cz"
HOME = "https://www.visitfm.cz/cz/kalendar-akci"
PAGE = "https://www.visitfm.cz/cz/kalendar-akci/kalendar-akci?category=&day=&date_start=&date_end=&page={}"
MAX_PAGES = 30

_DMY = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\b")
# Same places under the names the other sources use, so the venue filter shows each place once.
VENUE_ALIASES = {
    "zamek frydek": "Muzeum Beskyd (zámek)",
    "knihovna fm": "Městská knihovna F-M",
    "rc klicek": "Klíček (hernička)",
    "namesti svobody": "Náměstí Svobody, Místek",
}
CATEGORIES = {"Kino": "film", "Sport": "sport", "Gastro": "trhy", "Pro děti": "deti"}


def _place(text: str) -> tuple[str | None, str | None]:
    """'Muzeum Beskyd, Zámecké nám. 1264, Frýdek- Místek' -> ('Muzeum Beskyd', 'Frýdek-Místek')
    'Retro Hotel Jiskra, Čeladná 786,' -> ('Retro Hotel Jiskra', 'Čeladná')"""
    parts = [p.strip() for p in clean(text).split(",") if p.strip()]
    if not parts:
        return None, None
    venue = parts[0]
    city = None
    if len(parts) > 1:
        city = re.sub(r"\s*-\s*", "-", re.sub(r"\d[\d\s/]*", "", parts[-1])).strip(" .-") or None
    if city and "frydek" in city.lower().replace("ý", "y"):
        city = "Frýdek-Místek"
    if not city and re.search(r"Fr[ýy]dek|M[ií]stek", venue):
        city = "Frýdek-Místek"
    return venue, city


def _parse(html: str) -> list[Event]:
    out: list[Event] = []
    for row in BeautifulSoup(html, "html.parser").select("div.row-list"):
        a = row.select_one("h2 a[href]")
        info = row.select_one("p")
        if not a or not info:
            continue
        b = info.find("b")
        when = clean(b.get_text()) if b else ""
        dates = _DMY.findall(when)
        if not dates:
            continue
        start = date(int(dates[0][2]), int(dates[0][1]), int(dates[0][0]))
        end = date(int(dates[-1][2]), int(dates[-1][1]), int(dates[-1][0]))
        tm = _TIME.search(when)
        place_txt = clean(info.get_text(" ").replace(b.get_text(), "", 1)) if b else ""
        venue, city = _place(place_txt)
        if venue:
            venue = VENUE_ALIASES.get(fold(venue), venue)
        title = re.sub(r"^KINO\s*\|\s*", "", clean(a.get_text()), flags=re.I)
        badge = row.select_one(".badge")
        src_cat = clean(badge.get_text()) if badge else ""
        cat = CATEGORIES.get(src_cat) or categorize(title)
        img = row.select_one("img[src]")
        out.append(Event(
            title=re.sub(r"^Výstava:\s*", "Výstava: ", title),
            date=start.isoformat(),
            end_date=end.isoformat() if end > start else None,
            time=f"{int(tm.group(1)):02d}:{tm.group(2)}" if tm else None,
            venue=venue,
            city=city or "Frýdek-Místek",
            region=region_for_city(city or "Frýdek-Místek"),
            category=cat if cat != "ostatni" else ("vystavy" if title.lower().startswith("výstava") else "ostatni"),
            url=a["href"],
            image=img["src"] if img and "noimage" not in img["src"] else None,
            source=NAME,
            kids=src_cat == "Pro děti",
        ))
    return out


def scrape(today: date, horizon_end: date) -> list[Event]:
    events: list[Event] = []
    seen: set[str] = set()
    for page in range(1, MAX_PAGES + 1):
        batch = _parse(fetch(PAGE.format(page)))
        if not batch:
            break
        fresh = [e for e in batch if e.url not in seen]
        if not fresh:
            break
        seen.update(e.url for e in fresh)
        events.extend(fresh)
        if min(e.date for e in batch) > horizon_end.isoformat():
            break  # list is sorted by start date
    return events
