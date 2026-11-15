"""Stará aréna (Ostrava) – the site is a Nuxt app; this uses the same JSON API its own pages call."""
from __future__ import annotations

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..common import Event, categorize, clean, fetch, shorten

NAME = "staraarena.cz"
HOME = "https://www.staraarena.cz/repertoar"
API = "https://www.staraarena.cz/api/event?lang=cs&paginate=50&page={page}&orderBy=date_from&orderWay=asc"
IMG = "https://monstermedia.s3-central.vshosting.cloud/staraarena.prod/images/event/list/{}"
TZ = ZoneInfo("Europe/Prague")


def _names(items) -> list[str]:
    return [i.get("name", "") for i in items or [] if isinstance(i, dict)]


def scrape(today: date, horizon_end: date) -> list[Event]:
    events: list[Event] = []
    page, last = 1, 1
    while page <= min(last, 10):
        data = json.loads(fetch(API.format(page=page)))
        last = data.get("lastPage") or 1
        for e in data.get("data", []):
            if not e.get("active", True) or e.get("cancelled") or not e.get("dateFrom"):
                continue
            start = datetime.fromisoformat(e["dateFrom"].replace("Z", "+00:00")).astimezone(TZ)
            if start.date() < today:
                continue
            group = e.get("eventGroup") or {}
            kinds = _names(e.get("types")) + _names(e.get("genres")) + [((e.get("type") or {}).get("name") or "")]
            kinds_txt = " ".join(kinds)
            title = clean(e.get("name") or group.get("name"))
            sale = e.get("onlineSaleLink") or group.get("onlineSaleLink") or {}
            kids = "Pohádka" in kinds_txt
            if kids:
                cat = "deti"
            elif "Koncert" in kinds_txt:
                cat = "hudba"
            elif any(k in kinds_txt for k in ("Divadlo", "Komedie", "Drama", "Kabaret", "Stand-up", "Improvizace")):
                cat = "divadlo"
            else:
                cat = categorize(title)
            events.append(Event(
                title=title,
                date=start.date().isoformat(),
                time=start.strftime("%H:%M"),
                venue="Stará aréna",
                city="Ostrava",
                region="ostrava",
                category=cat,
                url=f"https://www.staraarena.cz/repertoar/{e['eventGroupId']}/{group.get('slug') or e.get('slug')}",
                image=IMG.format(group["listImageFileName"]) if group.get("listImageFileName") else None,
                description=shorten(e.get("shortDescription") or group.get("descriptionPlainShort") or group.get("shortDescription")),
                tickets=sale.get("url") if isinstance(sale, dict) else None,
                source=NAME,
                sold_out=bool(e.get("soldOut")),
                kids=kids,
                tags=["Vstup zdarma"] if "Zdarma" in kinds_txt else [],
            ))
        page += 1
    return events
