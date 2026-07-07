"""Elo baseline over chronological historical matches.

Backtest protocol (leakage-disciplined): for each evaluated season, ratings are
built ONLY from strictly earlier matches. K is tuned on validation seasons 8-11;
season 12 (WC VII) is the held-out test and is never touched during tuning.
Run: python -m src.pitboss.elo
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pitboss.aliases import load as load_aliases

CLEAN = Path("data/clean")
BASE = 1500.0
VAL_SEASONS = (8, 9, 10, 11)
TEST_SEASON = 12


def load_matches() -> pd.DataFrame:
    df = pd.read_parquet(CLEAN / "matches_hist.parquet")
    table = load_aliases()
    for col in ("bot_a", "bot_b", "winner"):
        df[col] = df[col].map(lambda n: table.get(n, n))
    df["date_filled"] = df["date"].fillna("9999")
    return df.sort_values(["season", "date_filled", "match_id"]).reset_index(drop=True)


def p_win(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def run_elo(df: pd.DataFrame, k: float) -> pd.DataFrame:
    """Sequential Elo; returns df with p_a (pre-match prob bot_a wins)."""
    ratings: dict[str, float] = {}
    probs = np.empty(len(df))
    for i, row in enumerate(df.itertuples()):
        ra = ratings.get(row.bot_a, BASE)
        rb = ratings.get(row.bot_b, BASE)
        p = p_win(ra, rb)
        probs[i] = p
        sa = 1.0 if row.winner == row.bot_a else 0.0
        ratings[row.bot_a] = ra + k * (sa - p)
        ratings[row.bot_b] = rb + k * ((1 - sa) - (1 - p))
    out = df.copy()
    out["p_a"] = probs
    return out


def metrics(sub: pd.DataFrame) -> dict:
    y = (sub.winner == sub.bot_a).astype(float).to_numpy()
    p = sub.p_a.clip(1e-9, 1 - 1e-9).to_numpy()
    return {
        "n": len(sub),
        "log_loss": float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()),
        "brier": float(((p - y) ** 2).mean()),
        "accuracy": float(((p > 0.5) == (y == 1)).mean()),
    }


def backtest(df: pd.DataFrame, k: float, seasons: tuple[int, ...]) -> dict:
    scored = run_elo(df, k)
    sub = scored[scored.season.isin(seasons)]
    return metrics(sub)


def final_ratings(df: pd.DataFrame, k: float) -> pd.Series:
    ratings: dict[str, float] = {}
    for row in df.itertuples():
        ra = ratings.get(row.bot_a, BASE)
        rb = ratings.get(row.bot_b, BASE)
        p = p_win(ra, rb)
        sa = 1.0 if row.winner == row.bot_a else 0.0
        ratings[row.bot_a] = ra + k * (sa - p)
        ratings[row.bot_b] = rb + k * ((1 - sa) - (1 - p))
    return pd.Series(ratings).sort_values(ascending=False)


def main() -> None:
    df = load_matches()
    print(f"{len(df)} matches, seasons {df.season.min()}-{df.season.max()}, "
          f"{len(set(df.bot_a) | set(df.bot_b))} bots (canonical)")

    ks = [8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128]
    print("\nK tuning on validation seasons", VAL_SEASONS)
    best_k, best_ll = None, math.inf
    for k in ks:
        m = backtest(df, k, VAL_SEASONS)
        flag = ""
        if m["log_loss"] < best_ll:
            best_k, best_ll, flag = k, m["log_loss"], "  <- best"
        print(f"  K={k:>3}: log_loss={m['log_loss']:.4f} brier={m['brier']:.4f} "
              f"acc={m['accuracy']:.3f} (n={m['n']}){flag}")

    m = backtest(df, best_k, (TEST_SEASON,))
    print(f"\nHELD-OUT season {TEST_SEASON} (WC VII), K={best_k}:")
    print(f"  log_loss={m['log_loss']:.4f} (coin=0.6931)  brier={m['brier']:.4f} "
          f"(coin=0.25)  acc={m['accuracy']:.3f}  n={m['n']}")
    assert m["log_loss"] < math.log(2), "Elo does not beat the coin flip - audit the data"

    top = final_ratings(df, best_k).head(10)
    print("\nTop 10 all-time-through-2023 Elo:")
    for bot, r in top.items():
        print(f"  {r:7.1f}  {bot}")


if __name__ == "__main__":
    main()
