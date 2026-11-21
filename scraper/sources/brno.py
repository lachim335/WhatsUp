"""Brno venues scraped directly (GoTo Brno misses many club nights and family programmes):
Fléda, Kabinet MÚZ, Stará Pekárna, Zoo Brno. Kino Scala comes via jsonld.page in main.py."""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..common import Event, categorize, clean, fetch, fold, shorten

CITY = "Brno"


def _ev(**kw) -> Event:
    return Event(city=CITY, region="brno", **kw)


def _in_range(d: date, today: date, horizon_end: date, end: date | None = None) -> bool:
    return d <= horizon_end and (end or d) >= today


# ---------------------------------------------------------------- Fléda (music club)

FLEDA = "fleda.cz"
FLEDA_HOME = "https://www.fleda.cz/program"


def scrape_fleda(today: date, horizon_end: date) -> list[Event]:
    soup = BeautifulSoup(fetch(FLEDA_HOME), "html.parser")
    out: list[Event] = []
    for tm in soup.select("time[datetime]"):
        row = tm.find_parent("div", class_="grid-12")
        a = row.select_one("h3 a[href]") if row else None
        if not a:
            continue
        stamp = tm["datetime"]  # 2026-11-24T20:00:00
        d = date.fromisoformat(stamp[:10])
        if not _in_range(d, today, horizon_end):
            continue
        title = clean(a.get_text())
        tickets = next((x["href"] for x in row.select("a[href^=http]") if "Vstupenky" in x.get_text()), None)
        cat = categorize(title)
        out.append(_ev(
            title=title, date=d.isoformat(), time=stamp[11:16] if len(stamp) > 15 else None,
            venue="Fléda", category=cat if cat != "ostatni" else "hudba",
            url=urljoin(FLEDA_HOME, a["href"]), tickets=tickets, source=FLEDA,
        ))
    return out


# ---------------------------------------------------------------- Kabinet MÚZ (club, theatre)

KABINET = "kabinetmuz.cz"
KABINET_HOME = "https://www.kabinetmuz.cz/program"


def scrape_kabinet(today: date, horizon_end: date) -> list[Event]:
    soup = BeautifulSoup(fetch(KABINET_HOME), "html.parser")
    out: list[Event] = []
    for a in soup.select("a.program__item[href]"):
        m = re.search(r"/program/(\d{4}-\d{2}-\d{2})-", a["href"])
        title = a.select_one(".program__title")
        if not m or not title:
            continue
        d = date.fromisoformat(m.group(1))
        if not _in_range(d, today, horizon_end):
            continue
        img = re.search(r"url\('([^']+)'\)", (a.select_one(".program__img") or {}).get("style", "") or "")
        t = clean(title.get_text())
        cat = categorize(t)
        out.append(_ev(
            title=t, date=d.isoformat(), venue="Kabinet MÚZ",
            category=cat if cat != "ostatni" else "hudba",
            url=urljoin(KABINET_HOME, a["href"]),
            image=urljoin(KABINET_HOME, img.group(1)) if img else None, source=KABINET,
        ))
    return out


# ---------------------------------------------------------------- Stará Pekárna (music club)

PEKARNA = "starapekarna.cz"
PEKARNA_HOME = "https://www.starapekarna.cz/"


def scrape_pekarna(today: date, horizon_end: date) -> list[Event]:
    soup = BeautifulSoup(fetch(PEKARNA_HOME), "html.parser")
    out: list[Event] = []
    for box in soup.select("div.flex-box"):
        res = box.select_one("a[href^='/rezervace/']")
        bands = [clean(b.get_text()) for b in box.select(".band-title")]
        m = re.search(r"(\d{4}-\d{2}-\d{2})", res["href"]) if res else None
        if not m or not bands:
            continue
        d = date.fromisoformat(m.group(1))
        if not _in_range(d, today, horizon_end):
            continue
        desc = box.select_one(".description")
        img = box.select_one("img.day-image[src]")
        tickets = box.select_one("a.sms-ticket[href]")
        title = " + ".join(bands)
        cat = categorize(title)
        out.append(_ev(
            title=title, date=d.isoformat(), venue="Stará Pekárna",
            category=cat if cat != "ostatni" else "hudba",
            url=urljoin(PEKARNA_HOME, res["href"]), image=img["src"] if img else None,
            description=shorten(desc.get_text(" ")) if desc else None,
            tickets=tickets["href"] if tickets else None, source=PEKARNA,
        ))
    return out


# ---------------------------------------------------------------- Zoo Brno

ZOO = "zoobrno.cz"
ZOO_HOME = "https://www.zoobrno.cz/akce"


def scrape_zoo(today: date, horizon_end: date) -> list[Event]:
    soup = BeautifulSoup(fetch(ZOO_HOME), "html.parser")
    out: list[Event] = []
    for art in soup.select("article.cross4_item"):
        a = art.select_one("h2 a[href]")
        times = [t["datetime"][:10] for t in art.select(".time time[datetime]")]
        if not a or not times:
            continue
        start = date.fromisoformat(times[0])
        end = date.fromisoformat(times[-1]) if len(times) > 1 else None
        if not _in_range(start, today, horizon_end, end):
            continue
        tags = [fold(clean(t.get_text())) for t in art.select(".tags_item")]
        when = clean(art.select_one(".time").get_text(" "))
        hm = re.findall(r"\b(\d{1,2}):(\d{2})\b", when)
        title = clean(a.get_text())
        img = art.select_one("img[src]")
        kids = any("deti" in t for t in tags)
        cat = categorize(title)
        out.append(_ev(
            title=title, date=start.isoformat(), end_date=end.isoformat() if end and end > start else None,
            time=f"{int(hm[0][0]):02d}:{hm[0][1]}" if hm else None,
            end_time=f"{int(hm[1][0]):02d}:{hm[1][1]}" if len(hm) > 1 and not end else None,
            venue="Zoo Brno", category=cat if cat != "ostatni" else ("deti" if kids else "ostatni"),
            url=urljoin(ZOO_HOME, a["href"]), image=urljoin(ZOO_HOME, img["src"]) if img else None,
            source=ZOO, kids=kids,
        ))
    return out


SOURCES = [
    (FLEDA, FLEDA_HOME, scrape_fleda),
    (KABINET, KABINET_HOME, scrape_kabinet),
    (PEKARNA, PEKARNA_HOME, scrape_pekarna),
    (ZOO, ZOO_HOME, scrape_zoo),
]
