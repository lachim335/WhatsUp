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
| [kudyznudy.cz](https://www.kudyznudy.cz/kalendar-akci/moravskoslezsky-kraj) | doplněk: jarmarky, trhy, akce v Ostravsku a Beskydech |

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
