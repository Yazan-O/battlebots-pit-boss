"""Weekly prediction artifact — the pre-registration mechanism.

python -m src.pitboss.predict            -> data/predictions/week_<NN>.csv for the
                                            next unaired episode (committed BEFORE air
                                            time; the public git timestamp is the proof)
python -m src.pitboss.predict --episode 101 --retro
                                         -> retrospective file for an aired episode,
                                            marked preregistered=false (schema dry-run
                                            and honest backfill only, never presented
                                            as a pre-registration)

Also refreshes data/predictions/strengths.csv (current Elo per Pro League bot with
bootstrap CI + career record) for the dashboard leaderboard.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pitboss.aliases import load as load_aliases
from pitboss.elo import BASE, load_matches, p_win

K = 80
MODEL_VERSION = "elo-k80-v1"
CLEAN = Path("data/clean")
PRED = Path("data/predictions")
LOW_DATA_FIGHTS = 5
BOOTSTRAP = 300


def all_matches() -> pd.DataFrame:
    """Historical + played 2026 fights, canonical names, chronological."""
    hist = load_matches()  # already canonical + sorted
    cur = pd.read_parquet(CLEAN / "matches_2026.parquet")
    table = load_aliases()
    for col in ("bot_a", "bot_b", "winner"):
        cur[col] = cur[col].map(lambda n: table.get(n, n))
    cur = cur.sort_values(["episode", "match_id"])
    cols = ["bot_a", "bot_b", "winner", "season"]
    return pd.concat([hist[cols], cur[cols]], ignore_index=True)


def ratings_from(df: pd.DataFrame) -> tuple[dict[str, float], dict[str, list[int]]]:
    ratings: dict[str, float] = {}
    record: dict[str, list[int]] = {}
    for row in df.itertuples():
        ra = ratings.get(row.bot_a, BASE)
        rb = ratings.get(row.bot_b, BASE)
        p = p_win(ra, rb)
        sa = 1.0 if row.winner == row.bot_a else 0.0
        ratings[row.bot_a] = ra + K * (sa - p)
        ratings[row.bot_b] = rb + K * ((1 - sa) - (1 - p))
        record.setdefault(row.bot_a, [0, 0])[0 if sa else 1] += 1
        record.setdefault(row.bot_b, [0, 0])[1 if sa else 0] += 1
    return ratings, record


def why_line(a: str, b: str, ratings: dict, record: dict, wclass: dict) -> str:
    ra, rb = ratings.get(a, BASE), ratings.get(b, BASE)
    wa, la = record.get(a, [0, 0])
    wb, lb = record.get(b, [0, 0])
    fav, dog = (a, b) if ra >= rb else (b, a)
    edge = abs(ra - rb)
    bits = [f"{fav} carries a {edge:.0f}-point Elo edge ({ratings.get(fav, BASE):.0f} vs {ratings.get(dog, BASE):.0f})",
            f"career {wa}-{la} vs {wb}-{lb}"]
    ca, cb = wclass.get(a, "other"), wclass.get(b, "other")
    if ca != cb:
        bits.append(f"{ca.replace('-', ' ')} vs {cb.replace('-', ' ')}")
    for bot, (w, l) in ((a, (wa, la)), (b, (wb, lb))):
        if w + l < LOW_DATA_FIGHTS:
            bits.append(f"{bot} has only {w + l} recorded fights - low data, wide uncertainty")
    return "; ".join(bits)


def bootstrap_ci(df: pd.DataFrame, bots: list[str]) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    samples = {b: [] for b in bots}
    for _ in range(BOOTSTRAP):
        boot = df.sample(len(df), replace=True, random_state=rng.integers(2**31))
        r, _ = ratings_from(boot)
        for b in bots:
            samples[b].append(r.get(b, BASE))
    return pd.DataFrame({
        "bot": bots,
        "ci_lo": [float(np.percentile(samples[b], 5)) for b in bots],
        "ci_hi": [float(np.percentile(samples[b], 95)) for b in bots],
    })


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=int)
    ap.add_argument("--retro", action="store_true",
                    help="allow predicting an already-aired episode; marked preregistered=false")
    args = ap.parse_args()

    df = all_matches()
    upcoming = pd.read_parquet(CLEAN / "upcoming.parquet")
    played_eps = set(pd.read_parquet(CLEAN / "matches_2026.parquet").episode.dropna().astype(int))
    table = load_aliases()
    wclass = dict(pd.read_csv(CLEAN / "weapon_classes.csv")[["bot", "weapon_class"]].values)

    if args.episode:
        episode = args.episode
        if episode in played_eps and not args.retro:
            raise SystemExit(f"episode {episode} already aired; use --retro for an honest backfill")
    else:
        episode = int(upcoming.episode.min())

    if args.retro and episode in played_eps:
        cur = pd.read_parquet(CLEAN / "matches_2026.parquet")
        for col in ("bot_a", "bot_b"):
            cur[col] = cur[col].map(lambda n: table.get(n, n))
        card = cur[cur.episode == episode][["episode", "date", "bot_a", "bot_b"]]
        # ratings strictly before this episode
        hist_only = df[df.season < 2026]
        earlier = pd.read_parquet(CLEAN / "matches_2026.parquet")
        for col in ("bot_a", "bot_b", "winner"):
            earlier[col] = earlier[col].map(lambda n: table.get(n, n))
        earlier = earlier[earlier.episode < episode][["bot_a", "bot_b", "winner", "season"]]
        ratings, record = ratings_from(pd.concat([hist_only, earlier], ignore_index=True))
        preregistered = False
    else:
        card = upcoming[upcoming.episode == episode].copy()
        card["bot_a"] = card.bot_a.map(lambda n: table.get(n, n))
        card["bot_b"] = card.bot_b.map(lambda n: table.get(n, n))
        ratings, record = ratings_from(df)
        preregistered = True

    if card.empty:
        raise SystemExit(f"no fight card found for episode {episode}")

    week = episode - 100
    rows = []
    for r in card.itertuples():
        p_a = p_win(ratings.get(r.bot_a, BASE), ratings.get(r.bot_b, BASE))
        rows.append({
            "week": week, "episode": episode, "date": r.date,
            "fight": f"{r.bot_a} vs {r.bot_b}",
            "bot_a": r.bot_a, "bot_b": r.bot_b, "p_a": round(float(p_a), 4),
            "model_version": MODEL_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "preregistered": preregistered,
            "why": why_line(r.bot_a, r.bot_b, ratings, record, wclass),
        })
    out = pd.DataFrame(rows)
    PRED.mkdir(exist_ok=True)
    path = PRED / f"week_{week:02d}.csv"
    out.to_csv(path, index=False)
    print(f"wrote {path} (preregistered={preregistered})")
    print(out[["fight", "p_a", "why"]].to_string(index=False))

    # leaderboard strengths for the 24 Pro League bots
    pro = sorted(set(pd.read_parquet(CLEAN / "matches_2026.parquet").bot_a.map(lambda n: table.get(n, n)))
                 | set(pd.read_parquet(CLEAN / "matches_2026.parquet").bot_b.map(lambda n: table.get(n, n)))
                 | set(upcoming.bot_a.map(lambda n: table.get(n, n)))
                 | set(upcoming.bot_b.map(lambda n: table.get(n, n))))
    full_ratings, full_record = ratings_from(df)
    ci = bootstrap_ci(df, pro)
    strengths = pd.DataFrame({
        "bot": pro,
        "elo": [round(full_ratings.get(b, BASE), 1) for b in pro],
        "career_w": [full_record.get(b, [0, 0])[0] for b in pro],
        "career_l": [full_record.get(b, [0, 0])[1] for b in pro],
        "weapon_class": [wclass.get(b, "other") for b in pro],
    }).merge(ci, on="bot").sort_values("elo", ascending=False)
    strengths.to_csv(PRED / "strengths.csv", index=False)
    print(f"\nwrote {PRED / 'strengths.csv'} ({len(strengths)} bots); top 5:")
    print(strengths.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
