from __future__ import annotations

import argparse
import html
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd


SEASONS = range(6, 13)
SCHEMA = [
    "match_id",
    "season",
    "wc",
    "date",
    "episode",
    "bot_a",
    "bot_b",
    "winner",
    "method",
    "method_raw",
    "stage",
    "weight_class",
]


def parse_season(wikitext: str, season_no: int) -> list[dict]:
    rows, _skipped, _sources = _parse_season_full(wikitext, season_no)
    return rows


def _parse_season_full(wikitext: str, season_no: int) -> tuple[list[dict], list[dict], Counter]:
    skipped: list[dict] = []
    events = []
    events.extend(_parse_roundn_brackets(wikitext, season_no, skipped))
    events.extend(_parse_result_tables(wikitext, season_no, skipped))
    events.extend(_parse_episode_blocks(wikitext, season_no, skipped))
    events.sort(key=lambda row: row["_pos"])

    rows: list[dict] = []
    seen: dict[tuple[str, str], int] = {}
    for event in events:
        key = _pair_key(event["bot_a"], event["bot_b"])
        if key in seen and _norm_name(rows[seen[key]]["winner"]) == _norm_name(event["winner"]):
            # same pair + same winner = one fight reported by two sources -> merge.
            # Same pair with a DIFFERENT winner is a genuine rematch and stays.
            existing = rows[seen[key]]
            if existing["date"] is None and event["date"] is not None:
                existing["date"] = event["date"]
            if existing["episode"] is None and event["episode"] is not None:
                existing["episode"] = event["episode"]
            skipped.append(_skip(season_no, "duplicate", f"{event['bot_a']} vs. {event['bot_b']}"))
            continue
        seen[key] = len(rows)
        rows.append(event)

    sources = Counter(row["_source"] for row in rows)
    for i, row in enumerate(rows, 1):
        row["match_id"] = f"s{season_no:02d}_{i:03d}"
        for key in ("_pos", "_source"):
            row.pop(key, None)
    _validate_rows(rows)
    return rows, skipped, sources


def _parse_roundn_brackets(wikitext: str, season_no: int, skipped: list[dict]) -> list[dict]:
    rows = []
    for block_match in re.finditer(r"(?s)\{\{#invoke:RoundN\|.*?\n\}\}", wikitext):
        stage = None
        base_pos = block_match.start()
        for offset, line in enumerate(block_match.group(0).splitlines()):
            stage_from_comment = _stage_from_text(line)
            if stage_from_comment:
                stage = stage_from_comment
            if not line.lstrip().startswith("|"):
                continue
            row = _parse_bracket_line(line, season_no, stage, base_pos + offset, skipped)
            if row:
                rows.append(row)
    return rows


def _parse_bracket_line(line: str, season_no: int, stage: str | None, pos: int, skipped: list[dict]) -> dict | None:
    tokens = _split_top_level(line)
    method_indexes = [i for i, token in enumerate(tokens) if _normalize_method(token)]
    if len(method_indexes) != 1:
        return None
    method_i = method_indexes[0]
    method_raw = _clean_method_raw(tokens[method_i])
    method = _normalize_method(method_raw)
    fields = [(i, _clean_bot(token)) for i, token in enumerate(tokens) if _is_bot_token(token, i)]
    if len(fields) < 2:
        skipped.append(_skip(season_no, "bracket_unreadable", line))
        return None
    bot_a = fields[0][1]
    bot_b = fields[1][1]
    winner_token = _nearest_bot_before(tokens, method_i)
    winner = _winner_from_pair(_clean_bot(winner_token), bot_a, bot_b)
    if not winner:
        bold = [_clean_bot(token) for _i, token in fields if "'''" in token]
        if len(bold) == 1:
            winner = _winner_from_pair(bold[0], bot_a, bot_b)
    if not winner:
        skipped.append(_skip(season_no, "bracket_winner_unmatched", line))
        return None
    return _row(season_no, None, None, bot_a, bot_b, winner, method, method_raw, stage or "qualifier", pos, "bracket")


def _parse_result_tables(wikitext: str, season_no: int, skipped: list[dict]) -> list[dict]:
    rows = []
    for table, pos, heading in _iter_tables(wikitext):
        headers = _table_headers(table)
        header_text = " ".join(headers).casefold()
        if "winner" not in header_text or "method" not in header_text or "loser" not in header_text:
            continue
        if "losers" in header_text or 'colspan="2"' in table:
            skipped.append(_skip(season_no, "multi_bot_table", heading))
            continue
        stage = _stage_from_text(heading) or "qualifier"
        episode = None
        date = None
        row_i = 0
        for cells in _table_rows(table):
            if len(cells) < 4:
                continue
            if _looks_like_episode_cell(cells[0]):
                episode = _episode_from_text(cells[0]) or episode
                date = _date_from_text(cells[0]) or date
            winner, loser, method_raw = _winner_loser_method(cells)
            if not winner or not loser:
                continue
            method = _normalize_method(method_raw)
            if not method:
                skipped.append(_skip(season_no, "method_unrecognized", method_raw))
                continue
            row_i += 1
            rows.append(_row(season_no, date, episode, winner, loser, winner, method, _clean_method_raw(method_raw), stage, pos + row_i, "table"))
    return rows


def _parse_episode_blocks(wikitext: str, season_no: int, skipped: list[dict]) -> list[dict]:
    rows = []
    for block_match in re.finditer(r"(?ms)^\{\{Episode list/sublist.*?^\}\}", wikitext):
        block = block_match.group(0)
        episode = _field_int(block, "EpisodeNumber2")
        date = _start_date(block)
        block_stage = _stage_from_text(_field_text(block, "Title")) or "qualifier"
        card = _extract_card_text(block)
        if not card:
            continue
        items = _card_items(card, block_stage, season_no, skipped)
        winners = _winner_entries(block, card)
        winner_i = 0
        for item_i, item in enumerate(items):
            entry = None
            if item["consume_winner"]:
                if winner_i >= len(winners):
                    skipped.append(_skip(season_no, "winner_missing", item["raw"]))
                    continue
                entry = winners[winner_i]
                winner_i += 1
            if item["skip_reason"]:
                skipped.append(_skip(season_no, item["skip_reason"], item["raw"]))
                continue
            if entry is None:
                skipped.append(_skip(season_no, "winner_missing", item["raw"]))
                continue
            method = _normalize_method(entry["method_raw"])
            if not method:
                skipped.append(_skip(season_no, "method_unrecognized", entry["method_raw"]))
                continue
            winner = _winner_from_pair(entry["winner"], item["bot_a"], item["bot_b"])
            if not winner:
                skipped.append(_skip(season_no, "winner_unmatched", _episode_context(episode, item["raw"], entry["winner"])))
                continue
            rows.append(_row(
                season_no,
                date,
                episode,
                item["bot_a"],
                item["bot_b"],
                winner,
                method,
                entry["method_raw"],
                item["stage"],
                block_match.start() + item_i,
                "prose",
            ))
    return rows


def _extract_card_text(block: str) -> str | None:
    summary = block.split("|ShortSummary=", 1)[-1]
    before_line_color = summary.split("|LineColor=", 1)[0]
    paragraphs = before_line_color.split("<small>'''Digital-exclusive fights:", 1)[0].splitlines()
    card_lines = []
    taking = False
    for line in paragraphs:
        line = line.strip()
        if not line:
            continue
        if taking and (line == "----" or line.startswith("The winners")):
            break
        has_card_label = "Fight Card" in line or "Quarter Finals" in line or "Quarter-finals" in line
        if has_card_label and re.search(r"\bvs\.?\b", line, re.I):
            taking = True
        if taking and line != "----":
            card_lines.append(line)
    if not card_lines:
        return None
    return " ".join(card_lines)


def _card_items(card: str, default_stage: str, season_no: int, skipped: list[dict]) -> list[dict]:
    text = html.unescape(card)
    text = re.sub(r",\s*'''(?:MAIN EVENT|Main Event)", r"; '''Main Event", text)
    text = re.sub(r"\.\s*('''(?:Main Event|Semi|Final)|''\((?:semi|Semi|Final))", r"; \1", text)
    text = re.sub(r"\.\s*'''Quarter", r"; '''Quarter", text)
    chunks = [chunk.strip() for chunk in text.split(";")]
    items = []
    stage = default_stage
    youtube = False
    for chunk in chunks:
        if not chunk:
            continue
        lower = chunk.casefold()
        new_stage = _stage_from_text(chunk)
        if new_stage:
            stage = new_stage
        if "youtube exclusive" in lower or "youtube exclusives" in lower:
            youtube = True
        raw = chunk
        chunk = _drop_leading_label(chunk)
        if not re.search(r"\bvs\.?\b", chunk, re.I):
            continue
        skip_reason = None
        consume_winner = not youtube
        if youtube:
            skip_reason = "youtube_exclusive"
        elif any(marker in lower for marker in ("unaired", "exhibition", "science channel exclusive", "digital-exclusive")):
            skip_reason = "unaired_or_exhibition"
        elif "rumble" in lower or chunk.casefold().count(" vs") > 1 or " & " in chunk:
            skip_reason = "multi_bot"
        parts = re.split(r"\s+vs\.?\s+", chunk, flags=re.I)
        if len(parts) != 2:
            items.append({"raw": raw, "skip_reason": skip_reason or "multi_bot", "consume_winner": consume_winner})
            continue
        bot_a = _clean_bot(parts[0])
        bot_b = _clean_bot(parts[1])
        if not bot_a or not bot_b:
            items.append({"raw": raw, "skip_reason": "empty_bot", "consume_winner": consume_winner})
            continue
        items.append({
            "raw": raw,
            "bot_a": bot_a,
            "bot_b": bot_b,
            "stage": stage,
            "skip_reason": skip_reason,
            "consume_winner": consume_winner,
        })
    return items


def _winner_entries(block: str, card: str) -> list[dict]:
    text = block.split(card, 1)[-1]
    text = text.split("|LineColor=", 1)[0]
    text = re.sub(r"The winners? of the YouTube exclusives?.*?(?=(?:\n|$))", "", text, flags=re.I | re.S)
    text = re.sub(r"The Giant Bolt Award winners were.*?(?=\n\n|$)", "", text, flags=re.I | re.S)
    entries = []
    for match in re.finditer(r"'''([^']+)'''\s*\(([^)]*)\)", text):
        method_raw = _method_from_parenthetical(match.group(2))
        if not _normalize_method(method_raw):
            continue
        entries.append({"winner": _clean_bot(match.group(1)), "method_raw": method_raw})
    return entries


def _drop_leading_label(text: str) -> str:
    text = re.sub(r"'{2,3}", "", text)
    text = re.sub(r"\([^)]*(?:quarter|semi|final)[^)]*\)\s*:?", "", text, flags=re.I)
    while ":" in text:
        prefix, rest = text.split(":", 1)
        if re.search(r"fight card|main event|quarter|semi|final|rumble|youtube", prefix, re.I):
            text = rest
        else:
            break
    return text.strip(" .")


def _iter_tables(wikitext: str):
    heading = ""
    depth = 0
    start = None
    lines = wikitext.splitlines(keepends=True)
    pos = 0
    for line in lines:
        clean = line.strip()
        heading_match = re.match(r"=+\s*(.*?)\s*=+$", clean)
        if heading_match and depth == 0:
            heading = heading_match.group(1)
        if clean.startswith("{|"):
            if depth == 0:
                start = pos
            depth += 1
        if clean.startswith("|}") and depth:
            depth -= 1
            if depth == 0 and start is not None:
                end = pos + len(line)
                yield wikitext[start:end], start, heading
                start = None
        pos += len(line)


def _table_headers(table: str) -> list[str]:
    headers = []
    for line in table.splitlines():
        if line.startswith("|-") and headers:
            break
        if line.startswith("!"):
            headers.extend(_split_table_header_line(line))
    return [_clean_wiki(header).casefold() for header in headers]


def _split_table_header_line(line: str) -> list[str]:
    parts = line[1:].split("!!")
    return [_cell_value(part) for part in parts]


def _table_rows(table: str) -> list[list[str]]:
    rows = []
    current: list[str] = []
    in_body = False
    for line in table.splitlines():
        stripped = line.strip()
        if stripped.startswith("|-"):
            if current:
                rows.append(current)
            current = []
            in_body = True
            continue
        if not in_body or not stripped.startswith("|") or stripped.startswith("|}"):
            continue
        current.extend(_split_table_cell_line(stripped))
    if current:
        rows.append(current)
    return [[_cell_value(cell) for cell in row] for row in rows]


def _split_table_cell_line(line: str) -> list[str]:
    if line.startswith("|"):
        line = line[1:]
    return _split_top_level(line, separator="||")


def _winner_loser_method(cells: list[str]) -> tuple[str | None, str | None, str | None]:
    values = [_clean_wiki(cell) for cell in cells]
    values = [value for value in values if value]
    for i in range(len(values) - 2):
        method = _normalize_method(values[i + 2])
        if method and _looks_like_bot(values[i]) and _looks_like_bot(values[i + 1]):
            return values[i], values[i + 1], values[i + 2]
    if len(values) >= 4:
        return values[-4], values[-3], values[-2]
    return None, None, None


def _cell_value(cell: str) -> str:
    cell = cell.strip()
    if "|" in cell:
        parts = _split_top_level(cell)
        cell = parts[-1] if parts else cell
    return cell.strip()


def _split_top_level(text: str, separator: str = "|") -> list[str]:
    if separator == "||":
        return [part.strip() for part in re.split(r"\|\|", text)]
    parts = []
    start = 0
    brace_depth = 0
    link_depth = 0
    i = 0
    while i < len(text):
        two = text[i:i + 2]
        if two == "{{":
            brace_depth += 1
            i += 2
            continue
        if two == "}}" and brace_depth:
            brace_depth -= 1
            i += 2
            continue
        if two == "[[":
            link_depth += 1
            i += 2
            continue
        if two == "]]" and link_depth:
            link_depth -= 1
            i += 2
            continue
        if text[i] == separator and not brace_depth and not link_depth:
            parts.append(text[start:i].strip())
            start = i + 1
        i += 1
    parts.append(text[start:].strip())
    return parts


def _is_bot_token(token: str, index: int) -> bool:
    stripped = token.strip()
    if not stripped or _normalize_method(stripped):
        return False
    if index <= 1 and re.search(r"^(Battle|Final Battle|style=|widescore|bold_winner|3rdplace)", stripped, re.I):
        return False
    cleaned = _clean_bot(stripped)
    return bool(cleaned and _looks_like_bot(cleaned))


def _nearest_bot_before(tokens: list[str], method_i: int) -> str:
    for token in reversed(tokens[:method_i]):
        if _is_bot_token(token, 99):
            return token
    return ""


def _clean_bot(text: str) -> str:
    text = _clean_wiki(text)
    text = re.sub(r"^#\s*\d+\s*", "", text)
    text = re.sub(r"\s*\((?:Home Team|Replacement for .*?|partial showing)\)\s*", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .,:;")


def _clean_wiki(text: str) -> str:
    text = html.unescape(str(text))
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\{\{(?:flagicon|color box|Color box|ref label|note label|Tooltip|efn|anchor)[^{}]*\}\}", " ", text)
    text = re.sub(r"\[\[[^|\]]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"'{2,5}", "", text)
    text = re.sub(r"\{\{[^{}]*\}\}", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _method_from_parenthetical(text: str) -> str:
    return _clean_method_raw(text.split(",", 1)[0])


def _clean_method_raw(text: str) -> str:
    text = _clean_wiki(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalize_method(method_raw: str | None) -> str | None:
    if not method_raw:
        return None
    text = _clean_method_raw(method_raw).casefold()
    if "double" in text:
        return None
    if re.search(r"\bko\b|knockout", text, re.I):
        return "KO"
    if re.search(r"\b(?:ud|sd|jd)\b|split|unanimous|appealed", text, re.I):
        return "JD"
    return None


def _norm_name(name: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", name.casefold())


def _winner_from_pair(winner: str, bot_a: str, bot_b: str) -> str | None:
    winner_norm = _norm_name(winner)
    if winner_norm == _norm_name(bot_a):
        return bot_a
    if winner_norm == _norm_name(bot_b):
        return bot_b
    return None


def _pair_key(bot_a: str, bot_b: str) -> tuple[str, str]:
    return tuple(sorted((_norm_name(bot_a), _norm_name(bot_b))))


def _looks_like_bot(text: str) -> bool:
    text = text.strip()
    if not text or text.isdigit():
        return False
    if re.search(r"^(Episode|Battle|Time|Method|Winner|Loser|Round|style=)", text, re.I):
        return False
    return bool(re.search(r"[A-Za-z0-9]", text))


def _looks_like_episode_cell(text: str) -> bool:
    return "[[#" in text or bool(re.search(r"\(\w+ \d{1,2}, \d{4}\)", text))


def _episode_from_text(text: str) -> int | None:
    match = re.search(r"\[\[#(\d+)\|", text)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(\d+)\b", _clean_wiki(text))
    return int(match.group(1)) if match else None


def _date_from_text(text: str) -> str | None:
    match = re.search(r"\(([A-Za-z]+ \d{1,2}, \d{4})\)", text)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%B %d, %Y").date().isoformat()


def _field_int(block: str, field: str) -> int | None:
    match = re.search(rf"\|{re.escape(field)}\s*=\s*(\d+)", block)
    return int(match.group(1)) if match else None


def _field_text(block: str, field: str) -> str:
    match = re.search(rf"\|{re.escape(field)}\s*=\s*(.*)", block)
    return _clean_wiki(match.group(1)) if match else ""


def _start_date(block: str) -> str | None:
    match = re.search(r"OriginalAirDate\s*=\s*\{\{Start date\|(\d{4})\|(\d{1,2})\|(\d{1,2})", block)
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    return f"{year:04d}-{month:02d}-{day:02d}"


def _stage_from_text(text: str) -> str | None:
    lower = text.casefold()
    if "round of 32" in lower or " r32" in lower or "battle r32" in lower:
        return "R32"
    if "round of 16" in lower or " r16" in lower or "battle r16" in lower:
        return "R16"
    if "quarter" in lower or " qf" in lower or "battle qf" in lower:
        return "QF"
    if "semi" in lower or " sf" in lower or "battle sf" in lower:
        return "SF"
    if re.search(r"\bfinal\b|\bfinals\b|championship", lower):
        return "F"
    return None


def _row(
    season_no: int,
    date: str | None,
    episode: int | None,
    bot_a: str,
    bot_b: str,
    winner: str,
    method: str,
    method_raw: str,
    stage: str,
    pos: int,
    source: str,
) -> dict:
    return {
        "_pos": pos,
        "_source": source,
        "match_id": "",
        "season": season_no,
        "wc": season_no - 5,
        "date": date,
        "episode": episode,
        "bot_a": bot_a,
        "bot_b": bot_b,
        "winner": winner,
        "method": method,
        "method_raw": method_raw,
        "stage": stage,
        "weight_class": "heavyweight",
    }


def _skip(season_no: int, reason: str, context: str) -> dict:
    return {"season": season_no, "reason": reason, "context": context[:300]}


def _episode_context(episode: int | None, fight: str, winner: str) -> str:
    return f"episode={episode}; fight={fight}; winner={winner}"


def _validate_rows(rows: list[dict]) -> None:
    for row in rows:
        if not row["bot_a"] or not row["bot_b"]:
            raise AssertionError(f"empty bot name: {row}")
        if row["winner"] not in {row["bot_a"], row["bot_b"]}:
            raise AssertionError(f"winner not in pair: {row}")
        if row["method"] not in {"KO", "JD"}:
            raise AssertionError(f"bad method: {row}")


def _fetch_season(season_no: int) -> str:
    from src.pitboss.brightdata import fetch_open

    url = f"https://en.wikipedia.org/w/index.php?title=BattleBots_season_{season_no}&action=raw"
    return fetch_open(url, "wikipedia")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    all_rows: list[dict] = []
    season_counts = {}
    total_skipped = 0
    for season_no in SEASONS:
        if args.fixtures:
            wikitext = (Path(args.fixtures) / f"season_{season_no}.txt").read_text(encoding="utf-8")
        else:
            wikitext = _fetch_season(season_no)
        rows, skipped, sources = _parse_season_full(wikitext, season_no)
        season_counts[season_no] = len(rows)
        all_rows.extend(rows)
        total_skipped += len(skipped)
        print(f"Season {season_no}: parsed {len(rows)} fights; skipped {len(skipped)}")
        print(f"  source split: {_format_counter(sources)}")
        print(f"  skipped: {_format_counter(Counter(item['reason'] for item in skipped))}")
        for sample in rows[:3]:
            print(f"  sample: {sample}")

    _validate_rows(all_rows)
    if not 135 <= season_counts.get(12, 0) <= 137:
        raise AssertionError(f"season 12 count outside acceptance range: {season_counts.get(12, 0)}")
    modern_total = sum(season_counts.get(season_no, 0) for season_no in (10, 11, 12))
    if modern_total < 300:
        raise AssertionError(f"seasons 10+11+12 below acceptance threshold: {modern_total}")
    print(f"TOTAL: parsed {len(all_rows)} fights; skipped {total_skipped}")
    print("Assertions: winners_in_pair=0 violations; empty_bot_names=0; methods={KO,JD}")

    if args.write or not args.fixtures:
        out_dir = Path("data") / "clean"
        out_dir.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(all_rows, columns=SCHEMA)
        df.to_parquet(out_dir / "matches_hist.parquet", index=False)
        df.to_csv(out_dir / "matches_hist.csv", index=False)
        print("Wrote data/clean/matches_hist.parquet")
        print("Wrote data/clean/matches_hist.csv")


def _format_counter(counter: Counter) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{key}={counter[key]}" for key in sorted(counter))


if __name__ == "__main__":
    main()
