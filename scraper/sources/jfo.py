"""Janáčkova filharmonie Ostrava – concert calendar (server-rendered WordPress list)."""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from ..common import Event, clean, fetch, shorten

NAME = "jfo.cz"
HOME = "https://www.jfo.cz/koncerty/kalendar-koncertu/"
LIST = "https://www.jfo.cz/koncerty/kalendar-koncertu/?count=60"


def scrape(today: date, horizon_end: date) -> list[Event]:
    soup = BeautifulSoup(fetch(LIST), "html.parser")
    out: list[Event] = []
    for item in soup.select("div.list__item"):
        a = item.select_one(".list__item__title a[href]")
        info = item.select_one(".list__info__text")
        if not a or not info:
            continue
        txt = clean(info.get_text(" "))
        m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", txt)
        if not m:
            continue
        d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if not today <= d <= horizon_end:
            continue
        tm = re.search(r"\b(\d{1,2}):(\d{2})\b", txt)
        seats = " ".join(clean(x.get_text(" ")) for x in item.select(".list__info__text"))
        desc = item.select_one(".list__item__description")
        img = item.select_one(".list__item__picture img[src]")
        kids = any(c.startswith("list__item--cyklus-male-") for c in item.get("class", []))  # family cycles
        out.append(Event(
            title=clean(a.get_text()),
            date=d.isoformat(),
            time=f"{int(tm.group(1)):02d}:{tm.group(2)}" if tm else None,
            venue="Janáčkova filharmonie",
            city="Ostrava",
            region="ostrava",
            category="hudba",
            url=a["href"],
            image=img["src"] if img else None,
            description=shorten(desc.get_text(" ")) if desc else None,
            source=NAME,
            sold_out=bool(re.search(r"vyprodáno", seats, re.I)),
            kids=kids,
        ))
    return out
