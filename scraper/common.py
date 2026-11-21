"""Shared helpers: HTTP session, Czech date parsing, category normalisation."""
from __future__ import annotations

import html
import re
import time
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import date

import requests

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36 WhatsUpEventFeed/1.0"
)

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "cs,en;q=0.5"})
_last_request = 0.0
REQUEST_DELAY = 0.8  # seconds between requests – be polite


def fetch(url: str, *, retries: int = 2, timeout: int = 30, headers: dict | None = None) -> str:
    """GET a page as text, with a polite delay and a couple of retries."""
    global _last_request
    for attempt in range(retries + 1):
        wait = REQUEST_DELAY - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
        try:
            r = _session.get(url, timeout=timeout, headers=headers)
            r.raise_for_status()
            r.encoding = r.apparent_encoding if not r.encoding or r.encoding.lower() == "iso-8859-1" else r.encoding
            return r.text
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


@dataclass
class Event:
    title: str
    date: str                     # YYYY-MM-DD (start)
    source: str
    url: str
    time: str | None = None       # HH:MM
    end_date: str | None = None   # YYYY-MM-DD
    end_time: str | None = None
    venue: str | None = None
    city: str | None = None
    region: str = "okoli"         # ostrava | fm | okoli | brno | bystrice
    category: str = "ostatni"
    image: str | None = None
    description: str | None = None
    tickets: str | None = None
    top: bool = False
    sold_out: bool = False
    kids: bool = False
    tags: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v not in (None, [], False, "")}


# ---------------------------------------------------------------- text utils

def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def fold(text: str) -> str:
    """Lowercase + strip diacritics, for matching and dedupe keys."""
    t = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def shorten(text: str | None, limit: int = 260) -> str | None:
    if text and "<" in text:
        text = re.sub(r"<(br|/p|/div|/li)[^>]*>", " ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
    text = clean(html.unescape(text or ""))
    if not text:
        return None
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",.;:–- ") + "…"


# ---------------------------------------------------------------- dates

MONTHS = {
    "ledna": 1, "leden": 1, "unora": 2, "unor": 2, "brezna": 3, "brezen": 3,
    "dubna": 4, "duben": 4, "kvetna": 5, "kveten": 5, "cervna": 6, "cerven": 6,
    "cervence": 7, "cervenec": 7, "srpna": 8, "srpen": 8, "zari": 9,
    "rijna": 10, "rijen": 10, "listopadu": 11, "listopad": 11,
    "prosince": 12, "prosinec": 12,
}

_DATE_WORD = re.compile(r"(\d{1,2})\.\s*([a-z]+)(?:\s+(\d{4}))?")
_DATE_NUM = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})?")
_TIME = re.compile(r"(\d{1,2})[:.](\d{2})")


def parse_czech_range(text: str, today: date) -> tuple[date, date | None, str | None] | None:
    """Parse strings like
        '15. listopadu 2026, 18:00'
        '20. listopadu - 21. listopadu 2026, 10:00'
        '21. listopadu 2026 - 06. ledna 2027'
        '15. 11. 2026'
    Returns (start, end_or_None, 'HH:MM' or None)."""
    t = fold(clean(text))
    # '20.–22. listopad 2026' -> '20. listopad – 22. listopad 2026'
    t = re.sub(r"(\d{1,2})\.\s*[-–]\s*(\d{1,2})\.\s*([a-z]{3,})", r"\1. \3 - \2. \3", t)
    parts: list[list[int | None]] = []
    for m in _DATE_WORD.finditer(t):
        month = MONTHS.get(m.group(2))
        if month:
            parts.append([int(m.group(1)), month, int(m.group(3)) if m.group(3) else None])
    if not parts:
        for m in _DATE_NUM.finditer(t):
            parts.append([int(m.group(1)), int(m.group(2)), int(m.group(3)) if m.group(3) else None])
    if not parts:
        return None

    # Fill missing years from the right (the year is usually only on the last date).
    year = next((p[2] for p in reversed(parts) if p[2]), None)
    for p in reversed(parts):
        if p[2] is None:
            p[2] = year
        year = p[2]
    if parts[0][2] is None:  # no year anywhere: assume the nearest upcoming
        y = today.year
        if (parts[0][1], parts[0][0]) < (today.month, today.day) and today.month - parts[0][1] > 6:
            y += 1
        for p in parts:
            p[2] = y
    # '20. prosince - 3. ledna 2027' -> start is in the previous year
    if len(parts) > 1 and (parts[0][2], parts[0][1]) > (parts[-1][2], parts[-1][1]):
        parts[0][2] -= 1

    try:
        start = date(parts[0][2], parts[0][1], parts[0][0])
        end = date(parts[-1][2], parts[-1][1], parts[-1][0]) if len(parts) > 1 else None
    except ValueError:
        return None
    if end and end <= start:
        end = None

    tm = _TIME.search(t)
    hhmm = f"{int(tm.group(1)):02d}:{tm.group(2)}" if tm else None
    return start, end, hhmm


# ---------------------------------------------------------------- categories

CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("deti", ("rodin", "deti", "detem", "pohad", "loutk")),
    ("hudba", ("hudb", "koncert", "festival hud", "jazz", "rock", "metal", "dj ", "filharmon", "orchestr", "kapela", "punk")),
    ("divadlo", ("divadl", "muzikal", "opera", "balet", "predstaveni", "stand-up", "standup", "comedy", "kabaret")),
    ("film", ("film", "kino", "promitan")),
    ("vystavy", ("vystav", "expozic", "galeri", "vernisaz")),
    ("trhy", ("advent", "vanocni trh", "vanocni mestec", "vanocni jarmark", "vanoce v ", "vanoce na ", "ostravske vanoce", "jarmark", "trhy", "trh ", "trziste", "gastro", "food", "pivni", "slavnost", "posviceni", "masopust", "rozsvec", "rozsvic", " pout", "burza", "vlacek")),
    ("festivaly", ("festival",)),
    ("sport", ("sport", "pohyb", "zavod", "beh ", "hokej", "fotbal", "turnaj", "cviceni", "hc ", " fc ", " fk ")),
    ("prednasky", ("besed", "predn", "prochaz", "komentovan", "prohlid", "workshop", "kurz", "dilna", "cestovat",
                   "krest knihy", "s autor", "poezie", "literatur", "muzeum meteorit", "smaltovan", "malovani")),
    ("tanec", ("tanec", "tanecn", "tancirn", "ples", "disco", "party", "zabava", "dnb", "swing")),
]


def categorize(*hints: str | None) -> str:
    """Map a source category and/or title onto our small set of categories.
    Hints are checked in order, so pass the source's own category first."""
    for hint in hints:
        if not hint:
            continue
        h = " " + fold(hint) + " "
        for key, needles in CATEGORY_RULES:
            if any(n in h for n in needles):
                return key
    return "ostatni"


def region_for_city(city: str | None) -> str:
    c = fold(city or "")
    if "frydek" in c or "mistek" in c:
        return "fm"
    if "ostrava" in c:
        return "ostrava"
    if c.startswith("brno") or c.startswith("brne"):
        return "brno"
    if "bystrice nad pern" in c:
        return "bystrice"
    return "okoli"


def dedupe_key(e: Event) -> str:
    return re.sub(r"[^a-z0-9]", "", fold(e.title))[:60] + "|" + e.date


_VENUE_NOISE = re.compile(r"\b(music|club|klub|hudebni|the|ostrava|bývalá|byvala|\(.*?\))\b")


def venue_key(venue: str | None) -> str:
    """Spelling-insensitive key for a venue: 'BARRÁK Music Club' == 'Barrák music club' == 'Barrák'."""
    if not venue:
        return ""
    v = re.sub(r"\(.*?\)", "", fold(venue))
    v = _VENUE_NOISE.sub(" ", v)
    return re.sub(r"[^a-z0-9]", "", v)


# Kids/family detection. Title + venue are reliable; descriptions only with explicit phrases.
_KIDS_TITLE = re.compile(r"\b(pohad|deti\b|detsk|detem|rodinn|pro rodiny|mikulas|cert|andel|loutk|batol|miminek|predskol|hernick|nejmensi|kids\b|family\b)")
_KIDS_VENUE = re.compile(r"loutek|ctyrlistek|\bzoo\b|svet techniky|detsky svet|klicek|hernick|rodinne centrum")
_KIDS_DESC = re.compile(r"pro deti|pro rodiny|rodiny s detmi|rodice s detmi|pro nejmensi|detske publikum|vhodne pro deti|deti od \d|od \d+ let\b")


_ADULT = re.compile(r"burles|kabaret|cabaret|\bsex|erotic|18\s*\+|od 18 let|\bparty\b|oldies|squid game|stand.?up|comedy|terapie|alkohol|whisk|degustac|\bples\b|pro dospel|singles")


def adult_only(title: str, venue: str | None, description: str | None) -> bool:
    return bool(_ADULT.search(fold(f"{title} {venue or ''}")) or re.search(r"od 18 let|18\s*\+|pro dospel", fold(description or "")))


def looks_like_kids(title: str, venue: str | None, description: str | None) -> bool:
    if adult_only(title, venue, description):
        return False
    return bool(_KIDS_TITLE.search(fold(title)) or _KIDS_VENUE.search(fold(venue or ""))
                or _KIDS_DESC.search(fold(description or "")))
