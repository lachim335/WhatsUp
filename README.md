# Co se děje – Ostrava & Frýdek-Místek

Tmavý web s přehledem kulturních akcí na nadcházející víkendy. Data se každý den automaticky stahují z veřejných kalendářů a web se sám nasadí na GitHub Pages.

## Zdroje

| Zdroj | Co pokrývá |
|---|---|
| [ostravainfo.cz](https://www.ostravainfo.cz/cz/akce/) | oficiální kalendář Ostravy: divadla, koncerty, kluby, sport, výstavy… |
| [kulturafm.cz](https://www.kulturafm.cz/program) | Kultura F≈M: Kino Vlast, Národní dům, Nová scéna Vlast, výstavy |
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

## Přidání dalšího zdroje

Vytvoř `scraper/sources/<nazev>.py` s konstantou `NAME` a funkcí `scrape(today, horizon_end) -> list[Event]`, pak ho přidej do `SOURCES` v `scraper/main.py`. Kategorie se mapují funkcí `categorize()` v `scraper/common.py`.
