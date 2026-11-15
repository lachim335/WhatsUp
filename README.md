# Co se děje – Ostrava & Frýdek-Místek

Tmavý web s přehledem kulturních akcí na nadcházející víkendy. Data se každý den automaticky stahují z veřejných kalendářů a web se sám nasadí na GitHub Pages.

## Zdroje

| Zdroj | Co pokrývá |
|---|---|
| [ostravainfo.cz](https://www.ostravainfo.cz/cz/akce/) | oficiální kalendář Ostravy: divadla, koncerty, kluby, sport, výstavy… |
| [kulturafm.cz](https://www.kulturafm.cz/program) | Kultura F≈M: Kino Vlast, Národní dům, Nová scéna Vlast, výstavy |
| [novaosmicka.cz](https://www.novaosmicka.cz/program) | Nová Osmička (F-M), přes jejich [veřejné API](https://www.novaosmicka.cz/developers) |
| [stoun.cz](https://www.stoun.cz/program) | klub STOUN (F-M), iCal export `program.ics` |
| [barrak-club.cz](https://www.barrak-club.cz/cz) | Barrák Music Club (Ostrava), JSON-LD na webu |
| [staraarena.cz](https://www.staraarena.cz/repertoar) | Stará aréna (Ostrava), JSON API, které používá jejich web |
| [dolnivitkovice.cz](https://www.dolnivitkovice.cz/kalendar-akci) | Dolní Vítkovice: Svět techniky, U6, Gong, Bolt Tower |
| [zoo-ostrava.cz](https://www.zoo-ostrava.cz/cz/akce-v-zoo/seznam-akci-v-zoo-ostrava/) | akce v Zoo Ostrava |
| [muzeumbeskyd.com](https://www.muzeumbeskyd.com/program/akce/) | Muzeum Beskyd (zámek F-M) |
| [knihovnafm.cz](https://www.knihovnafm.cz/akce/) | Městská knihovna F-M |
| [klicfm.cz](https://www.klicfm.cz/akce) | SVČ Klíč F-M: akce pro děti s věkovým rozmezím |
| [kudyznudy.cz](https://www.kudyznudy.cz/kalendar-akci/moravskoslezsky-kraj) | doplněk: jarmarky, trhy, akce v Ostravsku a Beskydech |

Akce pro děti se poznají podle zdroje (kategorie, věk) a podle názvu nebo místa (pohádka, Mikuláš, Divadlo loutek, zoo, Svět techniky…). Akce zjevně pro dospělé (stand-up, burleska, 18+) se nikdy jako dětské neoznačí. Pravidla jsou v `looks_like_kids()` a `adult_only()` v `scraper/common.py`.

Každý zdroj je samostatný modul v `scraper/sources/`. Když jeden selže, ostatní normálně proběhnou a selhání se zobrazí v patičce webu.

## Lokální spuštění

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m scraper.main            # -> site/data/events.json
cd site && python3 -m http.server 8000      # http://localhost:8000
```

Užitečné přepínače: `--weeks 8` (jak daleko dopředu), `--only kulturafm` (jen jeden zdroj).

## Hosting na GitHub Pages

1. Vytvoř na GitHubu nový **veřejný** repozitář (např. `whatsup`) a pushni do něj tento projekt.
2. V repozitáři otevři **Settings → Pages** a jako *Source* vyber **GitHub Actions**.
3. V **Actions** spusť workflow *Aktualizace akcí a nasazení* (tlačítko *Run workflow*), nebo počkej na další push.
4. Web poběží na `https://<uživatel>.github.io/<repozitář>/`.

Workflow `.github/workflows/update.yml` běží každý den ráno a navíc ve čtvrtek a pátek odpoledne. Stáhne akce, commitne `site/data/events.json` (díky tomu GitHub nevypne naplánovaný běh kvůli neaktivitě) a nasadí web.

## Přidání dalšího podniku

Nejdřív zjisti, jestli podnik nenabízí strojově čitelná data. Pak stačí jeden řádek v `SOURCES` v `scraper/main.py`:

```python
# podnik má kalendář .ics (hledej "program.ics", "webcal:", "Přidat do kalendáře")
ics.feed("klub.cz", "https://www.klub.cz/program.ics", venue="Klub X", city="Ostrava", images=True),
# web má schema.org Event v JSON-LD (v HTML hledej "application/ld+json" a "Event")
jsonld.page("klub.cz", "https://www.klub.cz/program", venue="Klub X", city="Ostrava"),
```

Na ostatní weby napiš vlastní modul `scraper/sources/<nazev>.py` s funkcí `scrape(today, horizon_end) -> list[Event]`. Pořadí v `SOURCES` určuje prioritu: když se stejná akce objeví ve více zdrojích (shodný název a den, nebo shodné místo, den a čas), zůstane záznam z dřívějšího zdroje.
