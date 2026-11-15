"""Family-oriented venues that only publish HTML listings.

Each scraper here is small; they share date helpers. Register them in scraper/main.py via SOURCES.
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..common import Event, categorize, clean, fetch, fold, shorten

MONTH_ABBR = {"led": 1, "uno": 2, "bre": 3, "dub": 4, "kve": 5, "cvn": 6,
              "cvc": 7, "srp": 8, "zar": 9, "rij": 10, "lis": 11, "pro": 12}
_TIME = re.compile(r"(?:\bod\s+|\bv\s+|\b)(\d{1,2})[:.](\d{2})(?:\s*(?:hod|h\b|–|-))")
_DMY = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})")


def _nearest_year(month: int, day: int, today: date) -> date:
    """A day/month without a year: the occurrence closest to today (allowing ~2 months in the past)."""
    for y in (today.year, today.year + 1):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        if (d - today).days >= -60:
            return d
    return date(today.year + 1, month, min(day, 28))


def _time_in(text: str) -> str | None:
    m = _TIME.search(text or "")
    if m and int(m.group(1)) < 24:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return None


def _soup(url: str) -> BeautifulSoup:
    return BeautifulSoup(fetch(url), "html.parser")


# ------------------------------------------------------------------ Dolní Vítkovice (Svět techniky, Gong, U6…)

DV_NAME = "dolnivitkovice.cz"
DV_HOME = "https://www.dolnivitkovice.cz/kalendar-akci"
_DV_KIDS = ("svet techniky", "detsky svet", "u6")


def dolni_vitkovice(today: date, horizon_end: date) -> list[Event]:
    events: list[Event] = []
    seen: set[str] = set()
    for page in range(1, 9):
        url = f"{DV_HOME}?from={today.isoformat()}&to={horizon_end.isoformat()}&page={page}"
        cards = _soup(url).select("article.EventCard")
        fresh = 0
        for c in cards:
            a = c.select_one(".EventCard-title a, a.EventCard-titleLink")
            if not a or a["href"] in seen:
                continue
            seen.add(a["href"])
            fresh += 1
            title = clean(a.get_text())
            if "zrušeno" in title.lower():
                continue
            nums = clean(c.select_one(".EventCard-dayNum").get_text()) if c.select_one(".EventCard-dayNum") else ""
            mons = fold(clean(c.select_one(".EventCard-dayMonth").get_text())) if c.select_one(".EventCard-dayMonth") else ""
            days = [int(x) for x in re.findall(r"\d+", nums)]
            months = [MONTH_ABBR.get(m[:3]) for m in re.findall(r"[a-z]+", mons)]
            if not days or not months or None in months:
                continue
            if len(days) == 2 and len(months) == 1:
                months = months * 2
            end = _nearest_year(months[-1], days[-1], today) if len(days) > 1 else None
            if end:
                start_year = end.year - (1 if months[0] > months[-1] else 0)
                try:
                    start = date(start_year, months[0], days[0])
                except ValueError:
                    continue
            else:
                start = _nearest_year(months[0], days[0], today)
            meta = [clean(m.get_text()) for m in c.select(".EventCard-metaItem")]
            times = [m for m in meta if re.match(r"\d{1,2}:\d{2}", m)]
            venue_bits = [m for m in meta if m and m not in times and m.lower() != "vyprodáno"]
            t = re.findall(r"\d{1,2}:\d{2}", times[0]) if times else []
            body = c.select_one(".EventCard-body p, .EventCard-perex, .EventCard-text")
            img = c.select_one("img[src]")
            venue = venue_bits[-1] if venue_bits else "Dolní oblast Vítkovice"
            v = fold(venue + " " + title)
            events.append(Event(
                title=title,
                date=start.isoformat(),
                end_date=end.isoformat() if end and end > start else None,
                time=t[0] if t and not end else None,
                end_time=t[1] if len(t) > 1 and not end else None,
                venue=venue,
                city="Ostrava",
                region="ostrava",
                category=categorize(title, body.get_text() if body else None),
                url=urljoin(DV_HOME, a["href"]),
                image=urljoin(DV_HOME, img["src"]) if img else None,
                description=shorten(body.get_text() if body else None),
                source=DV_NAME,
                sold_out="vyprodáno" in " ".join(meta).lower(),
                kids=any(k in v for k in _DV_KIDS),
            ))
        if not cards or not fresh:
            break
    return events


# ------------------------------------------------------------------ Zoo Ostrava

ZOO_NAME = "zoo-ostrava.cz"
ZOO_HOME = "https://www.zoo-ostrava.cz/cz/akce-v-zoo/seznam-akci-v-zoo-ostrava/"
ZOO_BASE = "https://www.zoo-ostrava.cz/"


def zoo(today: date, horizon_end: date) -> list[Event]:
    events: list[Event] = []
    for item in _soup(ZOO_HOME).select("div.akce-item"):
        a = item.select_one("a.name")
        try:
            d = int(item.select_one(".day").get_text())
            m = MONTH_ABBR[fold(item.select_one(".month").get_text().strip())[:3]]
            y = int(item.select_one(".year").get_text())
            start = date(y, m, d)
        except (AttributeError, KeyError, ValueError):
            continue
        if not a:
            continue
        text = item.select_one(".text")
        title = clean(a.get_text())
        events.append(Event(
            title=title,
            date=start.isoformat(),
            venue="Zoo Ostrava",
            city="Ostrava",
            region="ostrava",
            category=categorize(title) if categorize(title) != "ostatni" else "deti",
            url=urljoin(ZOO_BASE, a["href"]),
            description=shorten(text.get_text(" ") if text else None),
            source=ZOO_NAME,
            kids=True,
        ))
    return events


# ------------------------------------------------------------------ Muzeum Beskyd Frýdek-Místek

MB_NAME = "muzeumbeskyd.com"
MB_HOME = "https://www.muzeumbeskyd.com/program/akce/"
MB_BASE = "https://www.muzeumbeskyd.com/"


def muzeum_beskyd(today: date, horizon_end: date) -> list[Event]:
    events: list[Event] = []
    for box in _soup(MB_HOME).select("div.Articleout"):
        heads = box.select(".Articleinpadd h2")
        if len(heads) < 2:
            continue
        dates = _DMY.findall(heads[0].get_text())
        if not dates:
            continue
        start = date(int(dates[0][2]), int(dates[0][1]), int(dates[0][0]))
        end = date(int(dates[-1][2]), int(dates[-1][1]), int(dates[-1][0]))
        if end < today or start > horizon_end:
            continue
        href = box.get("phref") or (box.select_one("a.AlinkA") or {}).get("href")
        url = urljoin(MB_BASE, href) if href else MB_HOME
        title = clean(heads[1].get_text())
        pad = box.select_one(".Articleinpadd")
        desc = clean(pad.get_text(" ")) if pad else ""
        for h in heads:
            desc = desc.replace(clean(h.get_text()), "")
        desc = desc.replace("zobrazit více ⟶", "").strip()
        detail_text = ""
        if title.endswith("...") or not _time_in(desc):
            try:  # the listing truncates titles and rarely shows the time; the detail page has both
                detail = BeautifulSoup(fetch(url, retries=0), "html.parser")
                h1 = detail.select_one("h1")
                if h1 and title.endswith("..."):
                    title = clean(h1.get_text())
                main = detail.select_one(".Articleinpadd, article, #content, main") or detail
                detail_text = clean(main.get_text(" "))
            except Exception:
                pass
        title = title.rstrip(". ") if title.endswith("...") else title
        style = (box.select_one(".Articleimg") or {}).get("style", "")
        im = re.search(r"url\(([^)]+)\)", style)
        hay = f"{title} {desc} {detail_text}"
        events.append(Event(
            title=title,
            date=start.isoformat(),
            end_date=end.isoformat() if end > start else None,
            time=_time_in(desc) or _time_in(detail_text),
            venue="Muzeum Beskyd (zámek)",
            city="Frýdek-Místek",
            region="fm",
            category=(c if (c := categorize(title)) != "ostatni" else "prednasky"),
            url=url,
            image=urljoin(MB_BASE, im.group(1).strip("'\"")) if im else None,
            description=shorten(desc),
            source=MB_NAME,
            kids=bool(re.search(r"\bd[eě]t[ií]|rodin|pohád", hay, re.I)),
        ))
    return events


# ------------------------------------------------------------------ Městská knihovna Frýdek-Místek

KN_NAME = "knihovnafm.cz"
KN_HOME = "https://www.knihovnafm.cz/akce/"
KN_BASE = "https://www.knihovnafm.cz/"


def knihovna_fm(today: date, horizon_end: date) -> list[Event]:
    events: list[Event] = []
    for item in _soup(KN_HOME).select("div.blogitem"):
        when = item.select_one(".Bdatakce")
        a = item.select_one("a.blogitema")
        h3 = item.select_one("h3")
        if not when or not a or not h3:
            continue  # undated items are long-running exhibitions/notices
        m = _DMY.search(when.get_text())
        if not m:
            continue
        start = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        text_el = item.select_one(".blogtext")
        desc = clean(text_el.get_text(" ")) if text_el else ""
        desc = desc.replace(clean(when.get_text()), "").replace(clean(h3.get_text()), "").strip()
        title = clean(h3.get_text())
        img = item.select_one("img[src]")
        hay = f"{title} {desc}"
        events.append(Event(
            title=title,
            date=start.isoformat(),
            time=_time_in(desc),
            venue="Městská knihovna F-M",
            city="Frýdek-Místek",
            region="fm",
            category=(c if (c := categorize(title)) != "ostatni" else "prednasky"),
            url=urljoin(KN_BASE, a["href"]),
            image=urljoin(KN_BASE, img["src"]) if img else None,
            description=shorten(desc),
            source=KN_NAME,
            kids=bool(re.search(r"\bd[eě]t[ií]|rodin|pohád|pro nejmenší|předškol", hay, re.I)),
        ))
    return events


# ------------------------------------------------------------------ SVČ Klíč Frýdek-Místek (leisure centre for kids)

KL_NAME = "klicfm.cz"
KL_HOME = "https://www.klicfm.cz/akce"
KL_BASE = "https://www.klicfm.cz/"


def klic_fm(today: date, horizon_end: date) -> list[Event]:
    events: list[Event] = []
    for card in _soup(KL_HOME).select("div.card"):
        a = card.select_one(".card-title a[href]")
        if not a:
            continue
        info = [clean(li.get_text()) for li in card.select("ul li")]
        dates = next((_DMY.findall(x) for x in info if _DMY.search(x)), [])
        if not dates:
            continue
        start = date(int(dates[0][2]), int(dates[0][1]), int(dates[0][0]))
        end = date(int(dates[-1][2]), int(dates[-1][1]), int(dates[-1][0]))
        age = next((x for x in info if x.lower().startswith("věk")), None)
        place = next((x for x in info if re.search(r"\d{3}|budova|centrum|klíč", x, re.I) and not _DMY.search(x) and x != age and "Kč" not in x), None)
        price = next((x for x in info if "Kč" in x or "zdarma" in x.lower()), None)
        desc_el = card.select_one("p.line-clamp, .card-body > p")
        desc = clean(desc_el.get_text(" ")) if desc_el else ""
        title = clean(a.get_text())
        ages = [int(x) for x in re.findall(r"\d+", age or "")]
        kids = not ages or ages[0] < 15
        img = card.select_one("img[src]")
        tags = [age.replace("Věk", "Věk").replace("-", "–")] if age else []
        if price and "zdarma" in price.lower():
            tags.append("Vstup zdarma")
        venue = "SVČ Klíč"
        if place:
            venue = "Klíček (hernička)" if "klíček" in place.lower() else "SVČ Klíč"
        events.append(Event(
            title=title,
            date=start.isoformat(),
            end_date=end.isoformat() if end > start else None,
            time=_time_in(desc),
            venue=venue,
            city="Frýdek-Místek",
            region="fm",
            category="deti" if kids else (c if (c := categorize(title, desc)) != "ostatni" else "prednasky"),
            url=urljoin(KL_BASE, a["href"]),
            image=img["src"] if img else None,
            description=shorten(desc),
            source=KL_NAME,
            kids=kids,
            tags=tags,
        ))
    return events


SOURCES = [
    (DV_NAME, DV_HOME, dolni_vitkovice),
    (ZOO_NAME, ZOO_HOME, zoo),
    (MB_NAME, MB_HOME, muzeum_beskyd),
    (KN_NAME, KN_HOME, knihovna_fm),
    (KL_NAME, KL_HOME, klic_fm),
]
