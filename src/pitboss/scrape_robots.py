"""Robot registry: weapon/team per canonical bot, from battlebots.fandom.com infoboxes.

Output: data/clean/robots.parquet (+csv) and data/clean/weapon_classes.csv — the
auditable raw-weapon-text -> weapon-class mapping.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pitboss.brightdata import fetch

CLEAN = Path("data/clean")

CLASS_RULES = [
    ("multibot", r"multibot|multi-bot|cluster|two robots"),
    # horizontal before vertical so generic disk/drisk can default to vertical below
    ("spinner-horizontal", r"horizontal (spin|bar|disc|disk|drisk|tri-bar)|tri-bar|undercutter|shell spin|full[- ]body|ring spin|melty|tornado"),
    ("spinner-vertical", r"vertical (spin|disc|disk|drisk|bar)|drum|eggbeater|beater bar|disk spin|drisk"),
    ("hammer-saw", r"hammer|axe|saw|mace|flail"),
    ("flipper", r"flipper|flipping arm|launcher|pneumatic lift.*flip"),
    ("crusher", r"crusher|crushing|piercing jaw"),
    ("control-wedge", r"wedge|lifter|lifting|grabber|grappl|clamp|jaws|forks|plow"),
]


def weapon_class(raw: str) -> str:
    t = raw.casefold()
    for cls, pat in CLASS_RULES:
        if re.search(pat, t):
            return cls
    return "other"


def infobox_field(html: str, source: str) -> str:
    m = re.search(rf'data-source="{source}"(.*?)</(?:div|section)>', html, re.S)
    if not m:
        return ""
    txt = re.sub(r"<[^>]+>", " ", m.group(1))
    txt = re.sub(r"\s+", " ", txt).strip()
    txt = re.sub(rf"^{source}\s*", "", txt, flags=re.I)
    return txt[:200]


def fandom_url(name: str) -> str:
    from urllib.parse import quote
    # '#' is a fragment even when %-encoded on fandom ("Atom #94" lives at Atom_94)
    clean = name.replace("#", "").replace(" ", "_").replace("__", "_")
    return "https://battlebots.fandom.com/wiki/" + quote(clean)


def main() -> None:
    aliases = pd.read_csv(CLEAN / "aliases.csv")
    bots = sorted(set(aliases.canonical))
    rows, missing = [], []
    for name in bots:
        try:
            html = fetch(fandom_url(name), "fandom")
        except Exception as e:
            missing.append((name, str(e)[:80]))
            rows.append({"bot": name, "weapon_raw": "", "weapon_class": "other",
                         "team": "", "weight": "", "page": ""})
            continue
        weapon_raw = infobox_field(html, "weapons")
        rows.append({
            "bot": name,
            "weapon_raw": weapon_raw,
            "weapon_class": weapon_class(weapon_raw),
            "team": infobox_field(html, "team"),
            "weight": infobox_field(html, "weight"),
            "page": fandom_url(name),
        })
    df = pd.DataFrame(rows)
    df.to_parquet(CLEAN / "robots.parquet", index=False)
    df.to_csv(CLEAN / "robots.csv", index=False)
    df[["bot", "weapon_raw", "weapon_class"]].to_csv(CLEAN / "weapon_classes.csv", index=False)

    known = (df.weapon_class != "other").mean()
    print(f"{len(df)} bots; weapon class known: {known:.1%}")
    print(df.weapon_class.value_counts().to_string())
    if missing:
        print(f"MISSING pages ({len(missing)}):")
        for n, e in missing:
            print(" -", n, e)
    others = df[df.weapon_class == "other"][["bot", "weapon_raw"]]
    if len(others):
        print("class=other (audit these):")
        print(others.to_string(index=False))


if __name__ == "__main__":
    main()
