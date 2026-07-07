from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from .brightdata import fetch


REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "clean"
FANDOM_URL = "https://battlebots.fandom.com/wiki/BattleBots_Pro_League"
EVENTS_URL = "https://battlebots.com/events/"
PLAYED_SCHEMA = [
    "match_id",
    "season",
    "group",
    "episode",
    "date",
    "bot_a",
    "bot_b",
    "winner",
    "method",
    "stage",
    "weight_class",
]
UPCOMING_SCHEMA = ["episode", "date", "bot_a", "bot_b", "group"]


def main() -> None:
    played = _parse_fandom(fetch(FANDOM_URL, "fandom"))
    cards = _parse_event_cards(fetch(EVENTS_URL, "battlebots"))
    today = date.today().isoformat()
    warnings = _assign_episodes(played, cards, today)
    upcoming = _upcoming_rows(cards, today)

    played_df = pd.DataFrame(played, columns=PLAYED_SCHEMA)
    upcoming_df = pd.DataFrame(upcoming, columns=UPCOMING_SCHEMA)
    played_df["episode"] = played_df["episode"].astype("Int64")
    upcoming_df["episode"] = upcoming_df["episode"].astype("Int64")
    new_played = _played_changes(played_df, OUT_DIR / "matches_2026.parquet")
    upcoming_changes = _row_changes(upcoming_df, OUT_DIR / "upcoming.parquet", UPCOMING_SCHEMA)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    played_df.to_parquet(OUT_DIR / "matches_2026.parquet", index=False)
    played_df.to_csv(OUT_DIR / "matches_2026.csv", index=False)
    upcoming_df.to_parquet(OUT_DIR / "upcoming.parquet", index=False)
    upcoming_df.to_csv(OUT_DIR / "upcoming.csv", index=False)

    for warning in warnings:
        print(warning)
    print(f"{new_played} new played fights, {upcoming_changes} new upcoming changes")
    print("Per-group played counts:")
    counts = Counter(row["group"] for row in played)
    for group in "ABCDEF":
        print(f"  {group}: {counts[group]}")
    print(f"Total played: {len(played)}")
    print("Upcoming card list:")
    for row in upcoming:
        group = row["group"] if row["group"] is not None else "?"
        print(f"  Episode {row['episode']} {row['date']} [{group}] {row['bot_a']} vs. {row['bot_b']}")
    print("Sample played rows:")
    for row in _sample_rows(played):
        print(f"  {row}")
    print("Sample upcoming rows:")
    for row in _sample_rows(upcoming):
        print(f"  {row}")
    print("Wrote data/clean/matches_2026.parquet")
    print("Wrote data/clean/matches_2026.csv")
    print("Wrote data/clean/upcoming.parquet")
    print("Wrote data/clean/upcoming.csv")


def _parse_fandom(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []
    for group in "ABCDEF":
        standings, fights = _group_tables(soup, group)
        expected = _standings(standings, group)
        group_rows = _fight_rows(fights, group)
        _check_standings(group, expected, group_rows)
        rows.extend(group_rows)
    rows.sort(key=lambda row: (row["group"], row["bot_a"].casefold(), row["bot_b"].casefold()))
    for i, row in enumerate(rows, 1):
        row["match_id"] = f"pl26_{i:03d}"
    return rows


def _group_tables(soup: BeautifulSoup, group: str):
    marker = soup.find(id=f"Group_{group}")
    if marker is None:
        raise AssertionError(f"missing Group_{group} section")
    heading = marker.find_parent(re.compile("^h[1-6]$"))
    if heading is None:
        raise AssertionError(f"Group_{group} has no heading")
    tables = []
    node = heading
    while True:
        node = node.find_next_sibling()
        if node is None:
            break
        if node.name == "h3" and node.find(id=re.compile("^Group_[A-F]$")):
            break
        if node.name == "table" and "fandom-table" in node.get("class", []):
            tables.append(node)
    if len(tables) < 2:
        raise AssertionError(f"Group {group} expected standings and fights tables, found {len(tables)}")
    return tables[0], tables[1]


def _standings(table, group: str) -> dict[str, tuple[str, int, int]]:
    headers = [_text(th) for th in table.find_all("th")]
    if "Robot" not in headers or "Win/Loss Record" not in headers:
        raise AssertionError(f"Group {group} standings headers drifted: {headers}")
    records = {}
    for tr in table.find_all("tr")[1:]:
        cells = [_text(cell) for cell in tr.find_all(["td", "th"])]
        if len(cells) < 3 or cells[2].casefold() == "tbd":
            continue
        match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", cells[2])
        if match is None:
            raise AssertionError(f"Group {group} bad Win/Loss Record for {cells[1]}: {cells[2]}")
        records[_norm_name(cells[1])] = (cells[1], int(match.group(1)), int(match.group(2)))
    return records


def _fight_rows(table, group: str) -> list[dict]:
    rows = []
    for td in table.find_all("td"):
        text = _text(td)
        if " vs" not in text or text.startswith("Group Winner"):
            continue
        links = [a for a in td.find_all("a") if _text(a)]
        if len(links) != 2:
            raise AssertionError(f"Group {group} fight cell has {len(links)} bot links: {text}")
        bot_a, bot_b = (_text(links[0]), _text(links[1]))
        bold_winners = []
        for bot in links:
            bold = _own_bot_bold(bot, td)
            if bold is not None:
                bold_winners.append(_text(bot))
        if len(bold_winners) > 1:
            raise AssertionError(f"Group {group} multiple winners in fight cell: {text}")
        if not bold_winners:
            continue
        winner = bold_winners[0]
        rows.append({
            "match_id": "",
            "season": 2026,
            "group": group,
            "episode": None,
            "date": None,
            "bot_a": bot_a,
            "bot_b": bot_b,
            "winner": winner,
            "method": None,
            "stage": "group",
            "weight_class": "heavyweight",
        })
    return rows


def _own_bot_bold(a, td):
    node = a.parent
    while node is not None and node is not td:
        if getattr(node, "name", None) == "b":
            links = [link for link in node.find_all("a") if _text(link)]
            return node if len(links) == 1 else None
        node = node.parent
    return None


def _check_standings(group: str, expected: dict[str, tuple[str, int, int]], rows: list[dict]) -> None:
    actual = defaultdict(lambda: [0, 0])
    for row in rows:
        winner = _norm_name(row["winner"])
        loser = _norm_name(row["bot_b"] if winner == _norm_name(row["bot_a"]) else row["bot_a"])
        actual[winner][0] += 1
        actual[loser][1] += 1
    for key, (bot, wins, losses) in expected.items():
        got = tuple(actual[key])
        if got != (wins, losses):
            raise AssertionError(f"standings mismatch group {group} bot {bot}: parsed {got[0]}-{got[1]}, standings {wins}-{losses}")


def _parse_event_cards(events_html: str) -> list[dict]:
    urls = _event_urls(events_html)
    if not urls:
        raise AssertionError("no BattleBots Pro League event links found on /events/")
    cards = []
    for url in urls:
        cards.extend(_parse_event_page(url, fetch(url, "battlebots")))
    cards.sort(key=lambda row: (row["date"], row["episode"], row["group"] or "", row["bot_a"], row["bot_b"]))
    return cards


def _event_urls(html: str) -> list[str]:
    urls = set()
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all("a", href=True):
        _add_event_url(urls, tag["href"])
    for match in re.finditer(r"https?://battlebots\.com/event/battlebots-pro-league-[^\"'<\\\s]+", html):
        _add_event_url(urls, match.group(0))
    episodes = sorted(_episode_from_url(url) for url in urls if _episode_from_url(url) is not None)
    if episodes:
        for episode in range(min(101, episodes[0]), episodes[-1] + 1):
            urls.add(f"https://battlebots.com/event/battlebots-pro-league-episode-{episode}/")
    return sorted(urls, key=_url_sort_key)


def _add_event_url(urls: set[str], href: str) -> None:
    url = urljoin(EVENTS_URL, href).split("#", 1)[0].split("?", 1)[0]
    if re.fullmatch(r"https://battlebots\.com/event/battlebots-pro-league-[a-z0-9-]+/?", url):
        urls.add(url.rstrip("/") + "/")


def _url_sort_key(url: str):
    episode = _episode_from_url(url)
    return (episode is None, episode or 9999, url)


def _episode_from_url(url: str) -> int | None:
    match = re.search(r"episode-(\d+)", url)
    return int(match.group(1)) if match else None


def _parse_event_page(url: str, html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    episode = _episode_from_url(url) or _episode_from_text(soup.get_text(" ", strip=True))
    if episode is None:
        raise AssertionError(f"could not derive episode from {url}")
    event_date = _event_date(soup, url)
    tables = soup.select("table.bbpl-custom-table")
    if not tables:
        raise AssertionError(f"no bbpl-custom-table found on {url}")
    rows = []
    for table in tables:
        for tr in table.select("tbody tr"):
            cells = [_text(td) for td in tr.find_all("td")]
            if len(cells) < 3:
                continue
            rows.append({
                "episode": episode,
                "date": event_date,
                "group": cells[0] or None,
                "bot_a": cells[1],
                "bot_b": cells[2],
            })
    if not rows:
        raise AssertionError(f"bbpl-custom-table has no fight rows on {url}")
    return rows


def _event_date(soup: BeautifulSoup, url: str) -> str:
    for script in soup.find_all("script", type="application/ld+json"):
        text = script.string or script.get_text()
        if not text.strip():
            continue
        data = json.loads(text)
        for item in _walk_json(data):
            if isinstance(item, dict) and item.get("@type") == "Event" and item.get("startDate"):
                return item["startDate"][:10]
    abbr = soup.find("abbr", title=re.compile(r"^\d{4}-\d{2}-\d{2}$"))
    if abbr is not None:
        return abbr["title"]
    text = soup.get_text(" ", strip=True)
    match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(20\d{2})", text)
    if match:
        parsed = pd.to_datetime(" ".join(match.groups())).date()
        return parsed.isoformat()
    raise AssertionError(f"could not derive event date from {url}")


def _walk_json(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _episode_from_text(text: str) -> int | None:
    match = re.search(r"Episode\s+(\d+)", text, re.I)
    return int(match.group(1)) if match else None


def _assign_episodes(played: list[dict], cards: list[dict], today: str) -> list[str]:
    by_group_pair = {}
    by_pair = {}
    for card in cards:
        if card["date"] >= today:
            continue
        pair = _pair_key(card["bot_a"], card["bot_b"])
        by_pair[pair] = card
        if card["group"]:
            by_group_pair[(card["group"], pair)] = card
    warnings = []
    for row in played:
        pair = _pair_key(row["bot_a"], row["bot_b"])
        card = by_group_pair.get((row["group"], pair)) or by_pair.get(pair)
        if card is None:
            warnings.append(f"WARNING played fight has no aired episode card: Group {row['group']} {row['bot_a']} vs. {row['bot_b']}")
            continue
        row["episode"] = card["episode"]
        row["date"] = card["date"]
    return warnings


def _upcoming_rows(cards: list[dict], today: str) -> list[dict]:
    return [
        {"episode": row["episode"], "date": row["date"], "bot_a": row["bot_a"], "bot_b": row["bot_b"], "group": row["group"]}
        for row in cards
        if row["date"] >= today
    ]


def _played_changes(df: pd.DataFrame, path: Path) -> int:
    if not path.exists():
        return len(df)
    old = {row["match_id"]: row for row in _records(pd.read_parquet(path), PLAYED_SCHEMA)}
    return sum(1 for row in _records(df, PLAYED_SCHEMA) if old.get(row["match_id"]) != row)


def _row_changes(df: pd.DataFrame, path: Path, columns: list[str]) -> int:
    if not path.exists():
        return len(df)
    old = {_tuple_record(row, columns) for row in _records(pd.read_parquet(path), columns)}
    new = {_tuple_record(row, columns) for row in _records(df, columns)}
    return len(new.symmetric_difference(old))


def _records(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    data = []
    normalized = df.reindex(columns=columns)
    for record in normalized.where(pd.notna(normalized), None).to_dict("records"):
        data.append({key: _clean_scalar(value) for key, value in record.items()})
    return data


def _tuple_record(row: dict, columns: list[str]) -> tuple:
    return tuple(row.get(column) for column in columns)


def _clean_scalar(value):
    if hasattr(value, "item"):
        value = value.item()
    if pd.isna(value):
        return None
    return value


def _sample_rows(rows: list[dict]) -> list[dict]:
    return rows[:3]


def _pair_key(bot_a: str, bot_b: str) -> tuple[str, str]:
    return tuple(sorted((_norm_name(bot_a), _norm_name(bot_b))))


def _norm_name(name: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", name.casefold())


def _text(tag) -> str:
    return re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()


if __name__ == "__main__":
    main()
