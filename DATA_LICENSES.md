# Data provenance & licenses

Pit Boss's own code and derived analytical outputs are covered by [LICENSE](LICENSE)
(source-available, gambling use prohibited). Third-party content keeps its own terms:

| What | Where in repo | Source | License / terms |
|---|---|---|---|
| Raw Wikipedia season wikitext | `data/raw/wikipedia/` | en.wikipedia.org (open API, `action=raw`) | CC BY-SA 4.0 — those snapshot files remain CC BY-SA; attribution: Wikipedia contributors, per-article history |
| Raw fan-wiki page snapshots | `data/raw/fandom/` | battlebots.fandom.com | CC BY-SA 3.0 — snapshots remain CC BY-SA; attribution: BattleBots Wiki contributors |
| Raw battlebots.com pages | `data/raw/battlebots/` | battlebots.com | © BattleBots Inc.; cached solely as scrape provenance/reproducibility evidence |
| YouTube/Reddit comment records | `data/raw/youtube/`, `data/raw/reddit/` | via Bright Data Web Scraper API | user-generated content quoted for analysis; per-platform terms |
| Match facts (who fought, who won) | `data/clean/*` | compiled from the above | facts are not copyrightable; the compilation and cleaning are ours, under LICENSE |

Match RESULTS are facts of record; our value-add (parsing, entity resolution,
validation, models) is what LICENSE governs. If any rights holder objects to a cached
snapshot, open an issue and it will be replaced with a fetch script.
