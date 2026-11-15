"""Generic iCalendar (.ics) source – for venues that publish their programme as a calendar feed.

Add a venue by appending to FEEDS in scraper/main.py, e.g.
    ics.feed("stoun.cz", "https://www.stoun.cz/program.ics", venue="Klub STOUN", city="Frýdek-Místek")
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from ..common import Event, categorize, clean, fetch, region_for_city, shorten

TZ = ZoneInfo("Europe/Prague")
SKIP_TITLES = re.compile(r"zav[řr]eno|soukrom[áa] akce|private event", re.I)


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _unescape(v: str) -> str:
    return v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _parse_dt(value: str, params: dict[str, str]) -> tuple[date, str | None]:
    """Return (local date, 'HH:MM' or None for all-day)."""
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        return datetime.strptime(value[:8], "%Y%m%d").date(), None
    dt = datetime.strptime(value.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        dt = dt.replace(tzinfo=timezone.utc).astimezone(TZ)
    elif "TZID" in params:
        try:
            dt = dt.replace(tzinfo=ZoneInfo(params["TZID"])).astimezone(TZ)
        except Exception:
            pass
    return dt.date(), dt.strftime("%H:%M")


def parse_ics(text: str) -> list[dict]:
    events, cur = [], None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            if cur is not None:
                events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            head, value = line.split(":", 1)
            name, *rest = head.split(";")
            params = dict(p.split("=", 1) for p in rest if "=" in p)
            cur[name.upper()] = (value, params)
    return events


_OG_IMAGE = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', re.I)


def _og_image(page_url: str) -> str | None:
    try:
        m = _OG_IMAGE.search(fetch(page_url, retries=0))
    except Exception:
        return None
    return m.group(1) if m and "og-default" not in m.group(1) else None


def feed(name: str, url: str, *, venue: str, city: str, home: str | None = None,
         default_category: str = "hudba", images: bool = False):
    """images=True: .ics has no pictures, so fetch og:image from each event's page (only within the horizon)."""
    """Build a source entry (name, homepage, scrape function) for one .ics feed."""

    def scrape(today: date, horizon_end: date) -> list[Event]:
        out: list[Event] = []
        for ev in parse_ics(fetch(url)):
            if "DTSTART" not in ev or "SUMMARY" not in ev:
                continue
            title = clean(_unescape(ev["SUMMARY"][0]))
            status = ev.get("STATUS", ("",))[0].upper()
            if status == "CANCELLED" or SKIP_TITLES.search(title):
                continue
            d, t = _parse_dt(*ev["DTSTART"])
            end_d = end_t = None
            if "DTEND" in ev:
                end_d, end_t = _parse_dt(*ev["DTEND"])
                if t is None:  # all-day DTEND is exclusive
                    end_d = date.fromordinal(end_d.toordinal() - 1)
                # overnight club nights end "tomorrow" – that is not a multi-day event
                if t and end_d and (end_d - d).days <= 1:
                    end_d = None
                else:
                    end_t = None
            desc = _unescape(ev.get("DESCRIPTION", ("",))[0])
            cats = _unescape(ev.get("CATEGORIES", ("",))[0])
            cat = categorize(cats, title)
            out.append(Event(
                title=title,
                date=d.isoformat(),
                time=t,
                end_date=end_d.isoformat() if end_d and end_d > d else None,
                end_time=end_t if end_t and end_t not in ("00:00", t) else None,
                venue=venue,
                city=city,
                region=region_for_city(city),
                category=cat if cat != "ostatni" else default_category,
                url=ev.get("URL", (home or url,))[0],
                description=shorten(desc),
                source=name,
            ))
        if images:
            for e in out:
                if e.url and today.isoformat() <= e.date <= horizon_end.isoformat():
                    e.image = _og_image(e.url)
        return out

    return name, home or url, scrape
