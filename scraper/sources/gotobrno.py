"""gotobrno.cz – official events calendar of the city of Brno (TIC Brno).

The list is server-rendered and sorted by the next date; "Načíst další" loads the next 9 items
when requested as XHR (?pageload=<offset>). The table view carries the venue, not the time.
A few category passes (music, theatre, family…) tag events with their category."""
from __future__ import annotations

from datetime import date

import time

import requests
from bs4 import BeautifulSoup

from ..common import Event, categorize, clean, fetch, parse_czech_range

NAME = "gotobrno.cz"
HOME = "https://www.gotobrno.cz/kalendar-akci/"
LIST = "https://www.gotobrno.cz/kalendar-akci/?pageload={off}&date={day}&type=table{cat}"
XHR = {"X-Requested-With": "XMLHttpRequest"}
MAX_PAGES = 80  # 9 items each
TAG_BUDGET = 240  # seconds; the category passes are skipped when the site is slow
# their category slug -> ours (first match wins). "Pro rodiny" is broad (markets, Christmas
# fair…), so it only sets the kids flag and the category comes from the title.
CATEGORY_PASSES = [("divadlo", "divadlo"), ("hudba", "hudba"), ("vystava", "vystavy"),
                   ("festivaly", "festivaly")]
FAMILY = "pro-rodiny"


def _items(html: str):
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("li.c-grid__item a.b-card[href]"):
        title = a.select_one(".b-card__title")
        if not title:
            continue
        # several dates of a repeated show are separated by <br>
        dates = [clean(d) for s in a.select(".pull-left .item-icon") for d in s.get_text("\n").split("\n")]
        place = a.select_one(".pull-right .item-icon")
        img = a.select_one("img[src]")
        yield {
            "url": a["href"],
            "title": clean(title.get_text()),
            "dates": [d for d in dates if d],
            "venue": clean(place.get_text(" ")) if place else None,
            "image": img["src"] if img else None,
        }


def _walk(today: date, horizon_end: date, cat: str = ""):
    """Yield list items until the list moves past the horizon."""
    seen: set[str] = set()
    failures = 0
    for page in range(MAX_PAGES):
        url = LIST.format(off=page * 9, day=today.isoformat(), cat=f"&cat={cat}" if cat else "")
        try:
            html = fetch(url, headers=XHR, timeout=45, retries=3)
        except requests.RequestException:
            # the site is sometimes slow; lose one page of 9 rather than the whole calendar
            failures += 1
            if failures > 3:
                raise
            continue
        batch = [i for i in _items(html) if i["url"] not in seen]
        if not batch:
            return
        firsts = []
        for item in batch:
            seen.add(item["url"])
            parsed = parse_czech_range(item["dates"][0], today) if item["dates"] else None
            if parsed:
                firsts.append(parsed[0])
            yield item
        if firsts and min(firsts) > horizon_end:
            return


def scrape(today: date, horizon_end: date) -> list[Event]:
    t0 = time.monotonic()
    items = list(_walk(today, horizon_end))  # the calendar itself – must succeed

    # Category passes only add tags. When the site is slow (it sometimes takes 7 s a page)
    # or a pass fails, stop and fall back to guessing the category from the title.
    family: set[str] = set()
    cat_of: dict[str, str] = {}
    try:
        for slug, ours in [(FAMILY, None), *CATEGORY_PASSES]:
            for item in _walk(today, horizon_end, slug):
                if time.monotonic() - t0 > TAG_BUDGET:
                    raise TimeoutError
                if ours:
                    cat_of.setdefault(item["url"], ours)
                else:
                    family.add(item["url"])
    except (requests.RequestException, TimeoutError):
        pass

    events: list[Event] = []
    for item in items:
        # one line per date ('21. listopad 2026', '12. prosinec 2026'), or a range on one line
        for when in item["dates"]:
            parsed = parse_czech_range(when, today)
            if not parsed:
                continue
            start, end, tm = parsed
            if start > horizon_end or (end or start) < today:
                continue
            guess = categorize(item["title"], item["venue"])
            # titles are more specific than the site's tags ('Mikuláš na Provázku' is for kids)
            cat = guess if guess in ("deti", "trhy", "film") else cat_of.get(item["url"]) or guess
            events.append(Event(
                title=item["title"],
                date=start.isoformat(),
                end_date=end.isoformat() if end and end > start else None,
                time=tm,
                venue=item["venue"],
                city="Brno",
                region="brno",
                category=cat,
                url=item["url"],
                image=item["image"],
                source=NAME,
                kids=item["url"] in family or cat == "deti",
            ))
    return events
