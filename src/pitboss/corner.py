"""Corner Brief generator: per-side, data-grounded scouting notes for the next card.

For every fight on the next upcoming episode (min episode in upcoming.parquet),
emit a brief for EACH side: what the public record says that team should watch
for against THIS opponent. Every number is reproducible from repo data only;
prose is templated from computed values (no LLM calls, no invented wisdom).

KO-timing note (requirement 3): the clean match record carries no fight duration
(method_raw is one of 8 flat labels: KO / UD / SD / ...). The seconds parser is
implemented for completeness but the data yields zero timed KOs, so no timing
claim is ever emitted rather than a fabricated one.

Run: python -m src.pitboss.corner
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pitboss.aliases import canon, load as load_aliases

CLEAN = Path("data/clean")
OUT = Path("data/corner")
MIN_FIGHTS = 5          # below this: no meaningful record
THIN_MEETINGS = 8       # class-vs-class below this: too thin for an edge claim
MIN_TIMED_KO = 3        # per-bot timed KOs needed for a median-time claim


def _pct(n: int, d: int) -> int:
    return round(100 * n / d)


def parse_ko_seconds(method_raw: object) -> int | None:
    if not isinstance(method_raw, str):
        return None
    m = re.search(r"(\d+)\s*(?:s|sec|second)", method_raw.lower())
    return int(m.group(1)) if m else None


def load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict]:
    table = load_aliases()
    hist = pd.read_parquet(CLEAN / "matches_hist.parquet")
    for c in ("bot_a", "bot_b", "winner"):
        hist[c] = hist[c].map(lambda n: canon(n, table))
    cur = pd.read_parquet(CLEAN / "matches_2026.parquet")
    for c in ("bot_a", "bot_b", "winner"):
        cur[c] = cur[c].map(lambda n: canon(n, table))
    up = pd.read_parquet(CLEAN / "upcoming.parquet")
    for c in ("bot_a", "bot_b"):
        up[c] = up[c].map(lambda n: canon(n, table))

    wc = pd.read_csv(CLEAN / "weapon_classes.csv")
    wc["canon"] = wc["bot"].map(lambda n: canon(n, table))
    cls = dict(zip(wc["canon"], wc["weapon_class"]))
    return hist, cur, up, cls, table


def bot_profile(hist: pd.DataFrame, bot: str) -> dict:
    m = hist[(hist.bot_a == bot) | (hist.bot_b == bot)]
    wins = m[m.winner == bot]
    losses = m[m.winner != bot]
    timed = [s for s in (parse_ko_seconds(x) for x in m.method_raw) if s is not None]
    return {
        "fights": len(m),
        "wins": len(wins),
        "losses": len(losses),
        "wins_ko": int((wins.method == "KO").sum()),
        "losses_ko": int((losses.method == "KO").sum()),
        "timed_ko": timed,
    }


def class_record(hist: pd.DataFrame, cls: dict, ca: str, cb: str) -> dict:
    """Meetings where one bot is class ca and the other cb; wins counted for ca side."""
    ka = hist.bot_a.map(cls)
    kb = hist.bot_b.map(cls)
    a_is_ca = (ka == ca) & (kb == cb)
    a_is_cb = (ka == cb) & (kb == ca)
    meet = hist[a_is_ca | a_is_cb]
    if len(meet) == 0:
        return {"n": 0, "wins_ca": 0, "ko": 0}
    a_ca = a_is_ca.loc[meet.index]
    ca_won = ((a_ca & (meet.winner == meet.bot_a)) | (~a_ca & (meet.winner == meet.bot_b))).sum()
    return {"n": len(meet), "wins_ca": int(ca_won), "ko": int((meet.method == "KO").sum())}


def current_form(cur: pd.DataFrame, bot: str) -> str | None:
    m = cur[(cur.bot_a == bot) | (cur.bot_b == bot)]
    if len(m) == 0:
        return None
    w = int((m.winner == bot).sum())
    return f"2026 Pro League so far: {w}-{len(m) - w} in {len(m)} fight(s)."


def side_brief(hist, cur, cls, team: str, opp: str) -> list[str]:
    tp = bot_profile(hist, team)
    op = bot_profile(hist, opp)
    tc, oc = cls.get(team), cls.get(opp)
    if tc is None or oc is None:
        raise KeyError(f"missing weapon class for {team!r}({tc}) or {opp!r}({oc})")
    lines: list[str] = []

    # 1. opponent KO threat
    if op["fights"] >= MIN_FIGHTS and op["wins"] > 0:
        lines.append(
            f"{opp}'s finishing threat: {op['wins_ko']} of its {op['wins']} wins "
            f"({_pct(op['wins_ko'], op['wins'])}%) came by KO — "
            + ("few opponents survive to a decision." if _pct(op['wins_ko'], op['wins']) >= 55
               else "it more often grinds out decisions.")
        )

    # 2/3. class matchup
    if tc == oc:
        rec = class_record(hist, cls, tc, oc)
        lines.append(
            f"Mirror matchup — both bots are {tc}; class record offers no paper edge "
            f"({rec['n']} past {tc}-vs-{tc} meetings, {_pct(rec['ko'], rec['n'])}% ended in KO)."
            if rec["n"] else
            f"Mirror matchup — both bots are {tc}; no prior {tc}-vs-{tc} meetings on record."
        )
    else:
        rec = class_record(hist, cls, tc, oc)
        if rec["n"] == 0:
            lines.append(f"No recorded {tc}-vs-{oc} meetings — class matchup is uncharted.")
        else:
            wr = _pct(rec["wins_ca"], rec["n"])
            edge = ("the class is favored on paper" if wr > 50
                    else "the class is the underdog on paper" if wr < 50
                    else "the class is even on paper")
            thin = " (thin sample — read lightly)" if rec["n"] < THIN_MEETINGS else ""
            lines.append(
                f"{tc} has beaten {oc} in {wr}% of {rec['n']} recorded meetings — {edge}{thin}."
            )
            lines.append(
                f"Those {tc}-vs-{oc} fights ended in KO {_pct(rec['ko'], rec['n'])}% of the time — "
                + ("expect a finish, not the judges." if _pct(rec['ko'], rec['n']) >= 55
                   else "many go the distance.")
            )

    # 4. team vulnerability
    if tp["fights"] >= MIN_FIGHTS and tp["losses"] > 0:
        lines.append(
            f"{team}'s own exposure: knocked out in {tp['losses_ko']} of its {tp['losses']} losses "
            f"({_pct(tp['losses_ko'], tp['losses'])}%)"
            + (" — it can be finished." if _pct(tp['losses_ko'], tp['losses']) >= 40
               else " — hard to put away.")
        )

    # 5. team finishing
    if tp["fights"] >= MIN_FIGHTS and tp["wins"] > 0:
        lines.append(
            f"{team}'s {tp['wins']} wins: {_pct(tp['wins_ko'], tp['wins'])}% by KO."
        )

    # optional: median KO time (no timing data in clean record -> never fires)
    if len(op["timed_ko"]) >= MIN_TIMED_KO:
        med = int(pd.Series(op["timed_ko"]).median())
        lines.append(f"{opp}'s KO wins land fast — median {med}s across "
                     f"{len(op['timed_ko'])} timed finishes.")

    # 6. low-data honesty
    if tp["fights"] < MIN_FIGHTS:
        lines.insert(0,
            f"{team} has only {tp['fights']} recorded fight(s) — no meaningful record; "
            f"treat every claim about {team} here as unknown.")

    # 7. current-season form
    form = current_form(cur, team)
    lines.append(form if form else "No Pro League 2026 fights on record yet.")

    return lines[:5] if len(lines) > 5 else lines


def build_fight(hist, cur, cls, row) -> dict:
    a, b = row.bot_a, row.bot_b
    return {
        "bot_a": a, "bot_b": b, "group": row.group,
        "briefs": {
            a: {"vs": b, "lines": side_brief(hist, cur, cls, a, b),
                "footer": "Public-data view only — the team knows their bot."},
            b: {"vs": a, "lines": side_brief(hist, cur, cls, b, a),
                "footer": "Public-data view only — the team knows their bot."},
        },
    }


def main() -> None:
    hist, cur, up, cls, _ = load()
    ep = int(up.episode.min())
    card = up[up.episode == ep].reset_index(drop=True)
    if len(card) == 0:
        raise SystemExit("no fights on the next card")

    fights = [build_fight(hist, cur, cls, r) for r in card.itertuples()]
    week = f"{ep:02d}"
    payload = {"episode": ep, "date": str(card.date.iloc[0]), "fights": fights}

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"week_{week}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Corner Briefs — Episode {ep} ({card.date.iloc[0]}), {len(fights)} fights\n")
    for f in fights:
        print(f"{'=' * 66}\n{f['bot_a']}  vs  {f['bot_b']}   (group {f['group']})\n{'=' * 66}")
        for bot, br in f["briefs"].items():
            print(f"\n  [{bot}] — corner brief vs {br['vs']}:")
            for ln in br["lines"]:
                print(f"    - {ln}")
            print(f"    ({br['footer']})")
        print()
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
