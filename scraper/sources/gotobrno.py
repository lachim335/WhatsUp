"""gotobrno.cz – official events calendar of the city of Brno (TIC Brno).

The list is server-rendered and sorted by the next date; "Načíst další" loads the next 9 items
when requested as XHR (?pageload=<offset>). The table view carries the venue, not the time.
A few category passes (music, theatre, family…) tag events with their category."""
from __future__ import annotations

from datetime import date

from bs4 import BeautifulSoup

from ..common import Event, categorize, clean, fetch, parse_czech_range

NAME = "gotobrno.cz"
HOME = "https://www.gotobrno.cz/kalendar-akci/"
LIST = "https://www.gotobrno.cz/kalendar-akci/?pageload={off}&date={day}&type=table{cat}"
XHR = {"X-Requested-With": "XMLHttpRequest"}
MAX_PAGES = 80  # 9 items each
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
    for page in range(MAX_PAGES):
        html = fetch(LIST.format(off=page * 9, day=today.isoformat(), cat=f"&cat={cat}" if cat else ""),
                     headers=XHR)
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
    family = {item["url"] for item in _walk(today, horizon_end, FAMILY)}
    cat_of: dict[str, str] = {}
    for slug, ours in CATEGORY_PASSES:
        for item in _walk(today, horizon_end, slug):
            cat_of.setdefault(item["url"], ours)

    events: list[Event] = []
    for item in _walk(today, horizon_end):
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
