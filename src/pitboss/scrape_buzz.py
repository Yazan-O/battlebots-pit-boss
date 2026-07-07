from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from .brightdata import (collect, serp, DATASET_REDDIT_COMMENTS,
                         DATASET_YOUTUBE_COMMENTS, DATASET_YOUTUBE_VIDEOS)


REPO_ROOT = Path(__file__).resolve().parents[2]
CLEAN = REPO_ROOT / "data" / "clean"
BUZZ_PARQUET = CLEAN / "buzz.parquet"
BUZZ_CSV = CLEAN / "buzz.csv"
SCHEMA = ["episode", "bot", "mentions", "mean_sentiment", "yt_comments", "reddit_comments"]
EP101_FIGHTERS = {"HyperShock", "HUGE", "Malice", "End Game", "Golden Fury", "DeathRoll"}


@dataclass(frozen=True)
class Matcher:
    bot: str
    alias: str
    raw_re: re.Pattern
    norm_re: re.Pattern | None


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _args()
    aliases, aliases_by_key = _load_aliases()
    pro_bots = _load_pro_bots(aliases, aliases_by_key)
    matchers = _build_matchers(pro_bots, aliases, aliases_by_key)
    if args.fixture:
        _run_fixture(args.fixture, pro_bots, matchers)
    else:
        _run_live(pro_bots, matchers)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path)
    return parser.parse_args()


def _run_live(pro_bots: list[str], matchers: list[Matcher]) -> None:
    matches = pd.read_parquet(CLEAN / "matches_2026.parquet")
    episodes = sorted(int(x) for x in matches["episode"].dropna().unique())
    if not episodes:
        raise RuntimeError("matches_2026.parquet has no aired episodes")

    existing = _read_existing()
    new_rows: list[dict] = []
    for episode in episodes:
        if not existing.empty and (existing["episode"].astype(int) == episode).any():
            print(f"episode {episode} cached")
            continue
        video_url = _discover_youtube(episode)
        thread_urls = _discover_reddit(episode)
        youtube = collect(DATASET_YOUTUBE_COMMENTS, [{"url": video_url}], "youtube")
        reddit = collect(DATASET_REDDIT_COMMENTS, [{"url": u} for u in thread_urls], "reddit") if thread_urls else []
        rows, _ = _score_episode(
            episode,
            _comment_texts(youtube, "comment_text", source="youtube"),
            _comment_texts(reddit, "comment", fallback="comment_text", source="reddit"),
            pro_bots,
            matchers,
        )
        new_rows.extend(rows)
        print(f"episode {episode}: youtube={len(youtube)} reddit={len(reddit)}")

    if not new_rows and not existing.empty:
        print("no new episodes")
        return
    out = pd.concat([existing, pd.DataFrame(new_rows, columns=SCHEMA)], ignore_index=True)
    out = _typed(out).sort_values(["episode", "bot"]).reset_index(drop=True)
    out.to_parquet(BUZZ_PARQUET, index=False)
    out.to_csv(BUZZ_CSV, index=False)
    print(f"wrote {BUZZ_PARQUET}")
    print(f"wrote {BUZZ_CSV}")


def _run_fixture(path: Path, pro_bots: list[str], matchers: list[Matcher]) -> None:
    records = _load_records(path)
    rows, details = _score_episode(
        101,
        _comment_texts(records, "comment_text", source="youtube fixture"),
        [],
        pro_bots,
        matchers,
    )
    ranked = sorted(rows, key=lambda r: (-r["mentions"], r["bot"].casefold()))
    print(f"fixture={path}")
    print(f"youtube_comments={len(records)} reddit_comments=0 episode=101")
    print("top mentions:")
    print(_format_table(ranked[:10]))
    print("sample attributions:")
    for snippet, bot in details["attributions"][:5]:
        print(f"- {snippet} -> {bot}")
    _sanity_gate(ranked, details["samples"])


def _score_episode(
    episode: int,
    youtube_texts: list[str],
    reddit_texts: list[str],
    pro_bots: list[str],
    matchers: list[Matcher],
) -> tuple[list[dict], dict]:
    analyzer = SentimentIntensityAnalyzer()
    source_counts = {"youtube": defaultdict(int), "reddit": defaultdict(int)}
    sentiments: dict[str, list[float]] = defaultdict(list)
    samples: dict[str, list[str]] = defaultdict(list)
    attributions: list[tuple[str, str]] = []

    for source, texts in (("youtube", youtube_texts), ("reddit", reddit_texts)):
        for text in texts:
            bots = _mentioned_bots(text, matchers)
            if not bots:
                continue
            for bot in bots:
                source_counts[source][bot] += 1
                if len(samples[bot]) < 5:
                    samples[bot].append(_snippet(text))
            if len(bots) == 1:
                bot = next(iter(bots))
                sentiments[bot].append(analyzer.polarity_scores(text)["compound"])
                if len(attributions) < 5:
                    attributions.append((_snippet(text), bot))

    rows = []
    for bot in pro_bots:
        yt = int(source_counts["youtube"][bot])
        rd = int(source_counts["reddit"][bot])
        scores = sentiments[bot]
        rows.append({
            "episode": int(episode),
            "bot": bot,
            "mentions": yt + rd,
            "mean_sentiment": sum(scores) / len(scores) if len(scores) >= 3 else None,
            "yt_comments": yt,
            "reddit_comments": rd,
        })
    return rows, {"samples": samples, "attributions": attributions}


def _mentioned_bots(text: str, matchers: list[Matcher]) -> set[str]:
    norm = _norm_words(text)
    bots = set()
    for matcher in matchers:
        if matcher.raw_re.search(text) or (matcher.norm_re is not None and matcher.norm_re.search(norm)):
            bots.add(matcher.bot)
    return bots


def _build_matchers(pro_bots: list[str], aliases: dict[str, str], aliases_by_key: dict[str, str]) -> list[Matcher]:
    pro_set = set(pro_bots)
    by_bot = {bot: {bot} for bot in pro_bots}
    for alias, canonical in aliases.items():
        bot = _canonical(canonical, aliases, aliases_by_key)
        if bot in pro_set:
            by_bot[bot].add(alias)
            by_bot[bot].add(bot)

    matchers = []
    for bot, names in by_bot.items():
        for alias in sorted(names, key=lambda x: (-len(x), x.casefold())):
            raw_re = re.compile(r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])", re.I)
            normalized = _norm_words(alias)
            norm_re = None
            if normalized:
                norm_re = re.compile(r"(?<![a-z0-9])" + re.escape(normalized) + r"(?![a-z0-9])")
            matchers.append(Matcher(bot, alias, raw_re, norm_re))
    return matchers


def _load_aliases() -> tuple[dict[str, str], dict[str, str]]:
    df = pd.read_csv(CLEAN / "aliases.csv", dtype=str).fillna("")
    aliases = dict(zip(df["alias"], df["canonical"]))
    by_key = {}
    for alias, canonical in aliases.items():
        by_key.setdefault(_norm_key(alias), canonical)
        by_key.setdefault(_norm_key(canonical), canonical)
    return aliases, by_key


def _load_pro_bots(aliases: dict[str, str], aliases_by_key: dict[str, str]) -> list[str]:
    bots = set()
    for path in (CLEAN / "matches_2026.parquet", CLEAN / "upcoming.parquet"):
        df = pd.read_parquet(path)
        for col in ("bot_a", "bot_b"):
            bots.update(_canonical(x, aliases, aliases_by_key) for x in df[col].dropna())
    if len(bots) != 24:
        raise RuntimeError(f"expected 24 Pro League bots, found {len(bots)}: {sorted(bots)}")
    return sorted(bots, key=str.casefold)


def _canonical(name: str, aliases: dict[str, str], aliases_by_key: dict[str, str]) -> str:
    value = str(name)
    return aliases.get(value) or aliases_by_key.get(_norm_key(value)) or value


def _ep_marketing_no(episode: int) -> int:
    # site numbers episodes 101, 102, ... ; YouTube titles say "EP 1", "EP 2", ...
    return episode - 100 if episode > 100 else episode


def _discover_youtube(episode: int) -> str:
    """SERP snippets truncate titles, so candidates are verified through the
    YouTube videos collector (full title) before one is accepted."""
    n = _ep_marketing_no(episode)
    data = serp(f"battlebots pro league ep {n} site:youtube.com")
    links = []
    for item in _serp_items(data):
        link = item.get("link") or item.get("url") or item.get("href") or ""
        vid = re.search(r"[?&]v=([\w-]{6,})", link)
        if _is_youtube_watch(link) and vid:
            watch = f"https://www.youtube.com/watch?v={vid.group(1)}"
            if watch not in links:
                links.append(watch)
        if len(links) == 5:
            break
    if not links:
        raise RuntimeError(f"no youtube watch links in SERP for episode {episode}")
    records = collect(DATASET_YOUTUBE_VIDEOS, [{"url": u} for u in links], "youtube")
    full = []
    for rec in records:
        title = str(rec.get("title") or "")
        url = str((rec.get("input") or {}).get("url") or rec.get("url") or "")
        full.append(f"{title} <{url}>")
        t = title.casefold()
        # official episode titles: "... | BATTLEBOTS PRO LEAGUE EP N | POWERED BY BRIGHT DATA"
        if ("battlebots pro league" in t and "powered by bright data" in t
                and _title_has_episode(title, n)):
            return url
    raise RuntimeError(f"no official Pro League ep {episode} video among verified candidates: {full}")


def _discover_reddit(episode: int) -> list[str]:
    data = serp(f"battlebots pro league episode {_ep_marketing_no(episode)} reddit")
    urls = []
    seen = set()
    for item in _serp_items(data):
        link = item.get("link") or item.get("url") or item.get("href") or ""
        if not _is_reddit_thread(link):
            continue
        clean = _clean_url(link)
        if clean in seen:
            continue
        seen.add(clean)
        urls.append(clean)
        if len(urls) == 2:
            break
    return urls


def _serp_items(data: dict) -> list[dict]:
    items = []
    for key in ("organic", "videos"):
        value = data.get(key, [])
        if isinstance(value, list):
            items.extend(x for x in value if isinstance(x, dict))
    return items


def _is_youtube_watch(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.netloc.casefold().endswith("youtube.com") and parsed.path == "/watch"


def _is_reddit_thread(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.netloc.casefold().endswith("reddit.com") and re.match(r"^/r/battlebots/comments/[^/]+", parsed.path, re.I) is not None


def _clean_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") + "/", "", ""))


def _title_has_episode(title: str, episode: int) -> bool:
    terms = {str(episode)}
    if episode >= 100:
        terms.add(str(episode - 100))
    return any(re.search(rf"(?<!\d){re.escape(term)}(?!\d)", title) for term in terms)


def _comment_texts(records: list[dict], primary: str, *, source: str, fallback: str | None = None) -> list[str]:
    texts = []
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError(f"{source} comment record is not an object: {type(record).__name__}")
        field = primary if primary in record else fallback if fallback and fallback in record else None
        if field is None:
            raise RuntimeError(f"{source} comments missing {primary!r}/{fallback!r}; available keys: {sorted(record)}")
        value = record.get(field)
        if value is not None and str(value).strip():
            texts.append(str(value))
    return texts


def _load_records(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise RuntimeError(f"{path} must contain a JSON list, got {type(data).__name__}")
    return data


def _read_existing() -> pd.DataFrame:
    if not BUZZ_PARQUET.exists():
        return pd.DataFrame(columns=SCHEMA)
    existing = pd.read_parquet(BUZZ_PARQUET)
    missing = [c for c in SCHEMA if c not in existing.columns]
    if missing:
        raise RuntimeError(f"{BUZZ_PARQUET} missing columns: {missing}")
    return existing[SCHEMA]


def _typed(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["episode"] = out["episode"].astype("int64")
    out["bot"] = out["bot"].astype(str)
    out["mentions"] = out["mentions"].astype("int64")
    out["mean_sentiment"] = pd.array(out["mean_sentiment"], dtype="Float64")
    out["yt_comments"] = out["yt_comments"].astype("int64")
    out["reddit_comments"] = out["reddit_comments"].astype("int64")
    return out[SCHEMA]


def _format_table(rows: list[dict]) -> str:
    df = pd.DataFrame(rows, columns=SCHEMA)
    if df.empty:
        return "(empty)"
    df = df[["bot", "mentions", "mean_sentiment", "yt_comments", "reddit_comments"]]
    return df.to_string(
        index=False,
        na_rep="None",
        formatters={"mean_sentiment": lambda x: "None" if pd.isna(x) else f"{x:.4f}"},
    )


def _sanity_gate(ranked: list[dict], samples: dict[str, list[str]]) -> None:
    top_six = {row["bot"] for row in ranked[:6]}
    extra = top_six - EP101_FIGHTERS
    missing = EP101_FIGHTERS - top_six
    if not extra and not missing:
        print("SANITY gate: PASS")
        return
    print(f"SANITY gate: FAIL top_six={sorted(top_six)} missing={sorted(missing)} extra={sorted(extra)}")
    for bot in sorted(extra):
        print(f"WHY {bot}:")
        for sample in samples.get(bot, [])[:5]:
            print(f"- {sample}")
    raise SystemExit(1)


def _norm_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).casefold())


def _norm_words(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).casefold()).strip()


def _snippet(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:160]


if __name__ == "__main__":
    main()
