"""Bystřice nad Pernštejnem and its surroundings (Vír, Rožná, Nedvědice, Pernštejn…).

- korunavysociny.cz – calendar of the destination agency based in Bystřice; one page per month
  with every event, each labelled with its micro-region. We keep Bystřicko + Nedvědicko.
- bystricenp.cz – the town's homepage calendar (mostly the culture house programme).
- regionbystricko.cz – micro-region calendar (village fairs, concerts) + the culture house's
  monthly programme post, which lists every show on its own line."""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..common import Event, categorize, clean, fetch, fold, parse_czech_range, shorten

CITY = "Bystřice nad Pernštejnem"

KORUNA = "korunavysociny.cz"
KORUNA_HOME = "https://www.korunavysociny.cz/akce-a-udalosti?cf31=Byst%C5%99icko"
KORUNA_MONTH = "https://www.korunavysociny.cz/akce-a-udalosti?y={y}&m={m}"
KEEP_AREAS = ("Bystřicko", "Nedvědicko")

TOWN = "bystricenp.cz"
TOWN_HOME = "https://www.bystricenp.cz/"
SKIP = re.compile(r"dárk|poukaz", re.I)

# 'Vánoční jarmark v Rožné' -> Rožná; only the common villages, otherwise we don't guess.
_PLACES = {
    "rozne": "Rožná", "rozna": "Rožná", "viru": "Vír", "vir": "Vír", "nedvedic": "Nedvědice",
    "strazku": "Strážek", "rovecnem": "Rovečné", "dolni rozince": "Dolní Rožínka",
    "doubravniku": "Doubravník", "cernviru": "Černvír", "pernstejn": "Pernštejn",
    "zvoli": "Zvole", "sikland": "Zvole", "rozsochy": "Rozsochy", "jimramov": "Jimramov",
    "dolni rozinka": "Dolní Rožínka", "rovecne": "Rovečné", "strazek": "Strážek",
    "dalecin": "Dalečín", "stepanov": "Štěpánov nad Svratkou", "nedvedice": "Nedvědice",
}


def _months(today: date, horizon_end: date):
    y, m = today.year, today.month
    while (y, m) <= (horizon_end.year, horizon_end.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def _city(title: str) -> str:
    t = fold(title)
    if "bystric" in t:
        return CITY
    for key, name in _PLACES.items():
        if re.search(rf"\b{key}", t):
            return name
    return CITY


def _times(text: str) -> tuple[str | None, str | None]:
    found = re.findall(r"\b(\d{1,2}):(\d{2})\b", text)
    fmt = [f"{int(h):02d}:{mm}" for h, mm in found]
    return (fmt[0] if fmt else None, fmt[1] if len(fmt) > 1 else None)


def scrape_koruna(today: date, horizon_end: date) -> list[Event]:
    events: list[Event] = []
    seen: set[str] = set()
    for y, m in _months(today, horizon_end):
        soup = BeautifulSoup(fetch(KORUNA_MONTH.format(y=y, m=m)), "html.parser")
        for it in soup.select("div.item[data-link-id]"):
            label = it.select_one(".mod-labels a")
            area = clean(label.get_text()) if label else ""
            a = it.select_one("h2 a[href]")
            dur = it.select_one(".duration")
            if area not in KEEP_AREAS or not a or not dur or it["data-link-id"] in seen:
                continue
            seen.add(it["data-link-id"])
            when = clean(dur.get_text(" "))
            parsed = parse_czech_range(when, today)
            if not parsed:
                continue
            start, end, _ = parsed
            if start > horizon_end or (end or start) < today:
                continue
            t_from, t_to = _times(when)
            same_day = not end or end == start
            title = clean(a.get_text()).rstrip(".")
            desc = it.select_one(".inner")
            desc_txt = clean(desc.get_text(" ")).replace("…", "").strip() if desc else None
            img = it.select_one("img[src]")
            city = _city(title)
            events.append(Event(
                title=title,
                date=start.isoformat(),
                end_date=end.isoformat() if not same_day else None,
                time=t_from,
                end_time=t_to if same_day else None,
                city=city,
                region="bystrice",
                category=categorize(title, desc_txt),
                url=urljoin(KORUNA_HOME, a["href"]),
                image=urljoin(KORUNA_HOME, img["src"]) if img else None,
                description=shorten(desc_txt),
                source=KORUNA,
            ))
    return events


def scrape_town(today: date, horizon_end: date) -> list[Event]:
    soup = BeautifulSoup(fetch(TOWN_HOME), "html.parser")
    box = soup.find(id="section-calendar")
    events: list[Event] = []
    for a in (box.select("a.js-event[href]") if box else []):
        row = a.find_parent("div", class_="row")
        if not row:
            continue
        cols = row.find_all("div", recursive=False)
        parsed = parse_czech_range(clean(cols[0].get_text(" ")), today) if cols else None
        title = clean(a.get_text())
        if not parsed or SKIP.search(title):
            continue
        start, end, _ = parsed
        if start > horizon_end or (end or start) < today:
            continue
        desc = row.select_one("p")
        desc_txt = clean(desc.get_text(" ")).rstrip(". ") if desc else None
        img = row.select_one("img[src]")
        events.append(Event(
            title=title,
            date=start.isoformat(),
            end_date=end.isoformat() if end and end > start else None,
            city=CITY,
            region="bystrice",
            category=categorize(title, desc_txt),
            url=urljoin(TOWN_HOME, a["href"]),
            image=urljoin("https:", img["src"]).replace(" ", "%20") if img else None,
            description=shorten(desc_txt),
            source=TOWN,
        ))
    return events


REGION = "regionbystricko.cz"
REGION_HOME = "https://www.regionbystricko.cz/kalendar-akci-bystricka/"
KD = "Kulturní dům Bystřice"
# '– kinokavárna – Neděle – 1. 11. / 15:00 – Předprodej od 2. 11.'
_KD_LINE = re.compile(r"^[-–]\s*(?:(?P<kind>[^–-]+?)\s*[–-]\s*)?\w+\s*[–-]?\s*(?P<d>\d{1,2})\.\s*(?P<m>\d{1,2})\.\s*/\s*(?P<t>\d{1,2}:\d{2})")
_KD_KINDS = {"kinokavarna": "film", "divadlo": "divadlo", "ples": "tanec", "koncert": "hudba",
             "talkshow": "prednasky", "pohadka": "deti"}
_REGION_CATS = {"divadlo": "divadlo", "detske": "deti", "film": "film", "hudba": "hudba",
                "trhy": "trhy", "sportovni": "sport", "vystava": "vystavy", "ples": "tanec",
                "zabava": "tanec", "vzdelavaci": "prednasky", "cteni detem": "deti"}


def _kd_programme(url: str, year: int, month: int, today: date, horizon_end: date) -> list[Event]:
    soup = BeautifulSoup(fetch(url), "html.parser")
    lines = [clean(x) for x in soup.get_text("\n").split("\n")]
    lines = [x for x in lines if x]
    out: list[Event] = []
    for prev, line in zip(lines, lines[1:]):
        m = _KD_LINE.match(line)
        if not m or len(prev) > 120:
            continue
        mo = int(m.group("m"))
        d = date(year + (1 if mo < month else 0), mo, int(m.group("d")))
        if not today <= d <= horizon_end:
            continue
        kind = fold(m.group("kind") or "")
        cat = _KD_KINDS.get(kind) or categorize(prev, kind)
        out.append(Event(
            title=prev, date=d.isoformat(), time=f"{int(m.group('t')[:-3]):02d}{m.group('t')[-3:]}",
            venue=KD, city=CITY, region="bystrice", category=cat, url=url, source=REGION,
            kids=cat == "deti",
        ))
    return out


def scrape_region(today: date, horizon_end: date) -> list[Event]:
    soup = BeautifulSoup(fetch(REGION_HOME), "html.parser")
    out: list[Event] = []
    for tr in soup.select("tr"):
        dat, info = tr.select_one("td.dat"), tr.select_one("td.info")
        a = info.select_one("h3 a[href]") if info else None
        if not dat or not a:
            continue
        title = clean(a.get_text())
        url = urljoin(REGION_HOME, a["href"])
        when = clean(dat.get_text(" "))
        parsed = parse_czech_range(when.split("až")[0] + (" - " + when.split("až")[1] if "až" in when else ""), today)
        if not parsed:
            continue
        start, end, tm = parsed
        if fold(title).startswith("kd bystrice"):  # monthly programme of the culture house
            out.extend(_kd_programme(url, start.year, start.month, today, horizon_end))
            continue
        if start > horizon_end or (end or start) < today:
            continue
        kind = dat.select("strong")
        kind = fold(clean(kind[-1].get_text())) if len(kind) > 1 else ""
        place = info.select_one(".lok strong")
        place = clean(place.get_text()) if place else ""
        city = _city(place) if place else _city(title)
        desc = info.select_one(".te")
        desc_txt = clean(desc.get_text(" ")).rstrip("…") if desc else None
        guess = categorize(title, desc_txt)
        cat = guess if guess != "ostatni" else _REGION_CATS.get(kind, "ostatni")
        out.append(Event(
            # bare 'Vánoční jarmark' -> 'Vánoční jarmark (Rožná)', so villages don't merge
            title=f"{title} ({city})" if city != CITY and len(title.split()) <= 5 else title,
            date=start.isoformat(),
            end_date=end.isoformat() if end and end > start else None,
            time=tm if tm and tm != "00:00" else None,
            venue=place or None, city=city, region="bystrice", category=cat, url=url,
            description=shorten(desc_txt), source=REGION, kids=cat == "deti",
        ))
    return out


SOURCES = [
    (KORUNA, KORUNA_HOME, scrape_koruna),
    (TOWN, TOWN_HOME, scrape_town),
    (REGION, REGION_HOME, scrape_region),
]
