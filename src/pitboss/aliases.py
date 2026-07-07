"""Entity resolution: one canonical name per robot.

Builds data/clean/aliases.csv from every name seen in the match data.
Grouping key: casefold + alphanumerics only. Canonical spelling: the variant
used in the most recent season (Pro League 2026 spelling wins where the bot
competes there), ties broken by frequency.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

CLEAN = Path("data/clean")

# variants a normalized key cannot catch (verified 2026-07-06):
# - SlamMow!/SlawMow! -> Slammo! : battlebots.fandom.com/wiki/SlamMow! redirects to
#   Slammo! (same Team Danby bot); SlawMow! is a Wikipedia typo in season 10.
# - SMEE...: Wikipedia season 11 uses both 11-E and 13-E spellings for the same bot.
# - "Mammoth *": footnote asterisk leaked from a season-8 results table.
MANUAL = {
    "SlamMow!": "Slammo!",
    "SlawMow!": "Slammo!",
    "SMEEEEEEEEEEEEE": "SMEEEEEEEEEEE",
    "Mammoth *": "Mammoth",
}

# 2026 Pro League roster spellings (battlebots.fandom.com/wiki/BattleBots_Pro_League,
# snapshot data/raw/battlebots/2026-07-06/fandom-proleague.html) — these win as
# canonical so current-season joins are exact.
PRO_LEAGUE_2026 = [
    "Manta", "Skorpios", "Terrortops", "Valkyrie",
    "Disarray", "MadCatter", "Magnitude", "Tombstone",
    "Cobalt", "Copperhead", "JackPot", "The Twins",
    "Malice", "Golden Fury", "DeathRoll", "End Game",
    "Bloodsport", "HUGE", "HyperShock", "Minotaur",
    "Witch Doctor", "Ribbot", "Switchback", "Orbitron",
]


def norm_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def build() -> pd.DataFrame:
    df = pd.read_parquet(CLEAN / "matches_hist.parquet")
    names = pd.concat([
        df[["bot_a", "season"]].rename(columns={"bot_a": "name"}),
        df[["bot_b", "season"]].rename(columns={"bot_b": "name"}),
    ])
    names["name"] = names["name"].replace(MANUAL)
    pro_by_key = {norm_key(n): n for n in PRO_LEAGUE_2026}

    canonical: dict[str, str] = {}
    for key, grp in names.assign(key=names["name"].map(norm_key)).groupby("key"):
        if key in pro_by_key:
            canonical[key] = pro_by_key[key]
        else:
            latest = grp[grp.season == grp.season.max()]
            canonical[key] = latest["name"].mode().iloc[0]

    raw_names = set(pd.concat([df.bot_a, df.bot_b])) | set(MANUAL) | set(PRO_LEAGUE_2026)
    rows = []
    for raw in sorted(raw_names):
        target = MANUAL.get(raw, raw)
        canon = canonical.get(norm_key(target), target)
        rows.append({"alias": raw, "canonical": canon})
    out = pd.DataFrame(rows)

    canon_set = set(out.canonical)
    keys = {}
    for c in canon_set:
        k = norm_key(c)
        assert k not in keys, f"two canonicals share key {k!r}: {keys[k]!r} vs {c!r}"
        keys[k] = c
    return out


def load() -> dict[str, str]:
    df = pd.read_csv(CLEAN / "aliases.csv")
    return dict(zip(df.alias, df.canonical))


def canon(name: str, table: dict[str, str]) -> str:
    if name in table:
        return table[name]
    key = norm_key(name)
    for alias, canonical in table.items():
        if norm_key(alias) == key:
            return canonical
    return name


if __name__ == "__main__":
    out = build()
    out.to_csv(CLEAN / "aliases.csv", index=False)
    merged = out[out.alias != out.canonical]
    print(f"{len(out)} aliases, {len(set(out.canonical))} canonical bots, "
          f"{len(merged)} non-identity mappings:")
    print(merged.to_string(index=False))
