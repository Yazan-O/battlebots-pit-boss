"""Scout Report: live news/buzz for one bot via the Bright Data MCP server.

Data layer (always available with BRIGHTDATA_API_KEY): search_engine + scrape_as_markdown
through the hosted MCP server. LLM layer (needs ANTHROPIC_API_KEY): Claude Haiku
condenses the scraped sources into a 10-line scouting report. Without the LLM key the
dashboard serves the committed cached report from data/scout/<bot>.json.

python -m src.pitboss.scout "End Game"        -> gather sources, print them
python -m src.pitboss.scout "End Game" --llm  -> also generate + cache the report
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pitboss.brightdata import mcp_call

SCOUT_DIR = Path("data/scout")
SKIP_DOMAINS = ("youtube.com", "fandom.com", "wikipedia.org", "instagram.com",
                "tiktok.com", "facebook.com", "battlebots.shop", "twitter.com", "x.com")


def gather(bot: str) -> dict:
    """Search + scrape live sources about a bot; returns {query, results, pages}."""
    query = f'"{bot}" BattleBots Pro League 2026'
    found = mcp_call("search_engine", {"query": query})
    results = found.get("organic", []) if isinstance(found, dict) else []
    picks = []
    for r in results:
        url = r.get("link", "")
        if url and not any(d in url for d in SKIP_DOMAINS):
            picks.append({"url": url, "title": r.get("title", ""),
                          "description": r.get("description", "")})
        if len(picks) == 2:
            break
    pages = []
    for p in picks:
        page = mcp_call("scrape_as_markdown", {"url": p["url"]})
        text = page.get("text", "") if isinstance(page, dict) else str(page)
        pages.append({"url": p["url"], "title": p["title"], "markdown": text[:6000]})
    return {"bot": bot, "query": query, "results": results[:8], "pages": pages}


def generate_report(bot: str, sources: dict) -> str:
    import requests
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set - dashboard will serve the cached report")
    corpus = "\n\n".join(
        [f"SEARCH RESULTS:\n" + "\n".join(f"- {r.get('title')}: {r.get('description', '')}"
                                          for r in sources["results"])] +
        [f"PAGE {p['url']}:\n{p['markdown']}" for p in sources["pages"]])
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": "claude-haiku-4-5-20251001", "max_tokens": 600,
              "messages": [{"role": "user", "content":
                  f"You are a robot-combat scout. From ONLY the sources below, write a "
                  f"10-line scouting report on the BattleBots competitor '{bot}': recent "
                  f"form/damage, builder/team notes, fan buzz. Every line must be "
                  f"grounded in the sources; write 'no recent intel found' for anything "
                  f"the sources don't cover. No hype-words.\n\n{corpus}"}]},
        timeout=120)
    r.raise_for_status()
    return r.json()["content"][0]["text"]


def cached_path(bot: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", bot.casefold()).strip("-")
    return SCOUT_DIR / f"{slug}.json"


def load_cached(bot: str) -> dict | None:
    p = cached_path(bot)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save(bot: str, report: str, sources: dict) -> Path:
    SCOUT_DIR.mkdir(parents=True, exist_ok=True)
    p = cached_path(bot)
    p.write_text(json.dumps({
        "bot": bot, "generated": date.today().isoformat(),
        "report": report,
        "sources": [pg["url"] for pg in sources["pages"]] or
                   [r.get("link", "") for r in sources["results"][:3]],
    }, indent=1), encoding="utf-8")
    return p


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    bot = sys.argv[1]
    sources = gather(bot)
    print(f"query: {sources['query']}")
    for r in sources["results"][:5]:
        print("-", r.get("title", "")[:80], "|", r.get("link", ""))
    for p in sources["pages"]:
        print(f"\nPAGE {p['url']}\n{p['markdown'][:500]}")
    if "--llm" in sys.argv:
        report = generate_report(bot, sources)
        path = save(bot, report, sources)
        print(f"\nreport cached -> {path}\n{report}")
