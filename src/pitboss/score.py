"""Public scorecard: join predictions with actual results, append running metrics.

python -m src.pitboss.score  -> updates data/predictions/scorecard.csv from every
week_<NN>.csv whose fights now have results in matches_2026.parquet.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pitboss.aliases import canon, load as load_aliases

CLEAN = Path("data/clean")
PRED = Path("data/predictions")


def main() -> None:
    table = load_aliases()
    played = pd.read_parquet(CLEAN / "matches_2026.parquet")
    for col in ("bot_a", "bot_b", "winner"):
        played[col] = played[col].map(lambda n: canon(n, table))
    # keyed by (episode, pair) so a season rematch can never overwrite an
    # earlier result; results without an assigned episode fall back to pair-only
    results, results_no_ep = {}, {}
    for r in played.itertuples():
        pair = frozenset((r.bot_a, r.bot_b))
        if pd.notna(r.episode):
            results[(int(r.episode), pair)] = r.winner
        else:
            results_no_ep[pair] = r.winner

    today = pd.Timestamp.today().date().isoformat()
    rows, unresolved = [], []
    for path in sorted(PRED.glob("week_*.csv")):
        wk = pd.read_csv(path)
        for r in wk.itertuples():
            pair = frozenset((r.bot_a, r.bot_b))
            winner = results.get((int(r.episode), pair)) or results_no_ep.get(pair)
            if winner is None:
                if bool(r.preregistered) and str(r.date) < today:
                    unresolved.append(f"ep{r.episode}: {r.fight}")
                continue
            p_winner = r.p_a if winner == r.bot_a else 1.0 - r.p_a
            rows.append({
                "week": r.week, "episode": r.episode, "fight": r.fight,
                "predicted_winner": r.bot_a if r.p_a >= 0.5 else r.bot_b,
                "p_predicted": round(max(r.p_a, 1 - r.p_a), 4),
                "actual_winner": winner,
                "hit": int((r.p_a >= 0.5) == (winner == r.bot_a)),
                "log_loss": round(-math.log(max(p_winner, 1e-9)), 4),
                "preregistered": bool(r.preregistered),
                "model_version": r.model_version,
            })
    if unresolved:
        # an aired pre-registered episode MUST reconcile: fail closed, go red in CI
        raise SystemExit("UNRESOLVED aired pre-registered fights (source stale or "
                         f"parse drift): {unresolved}")
    if not rows:
        raise SystemExit("no scored fights yet - no week file overlaps played results")
    sc = pd.DataFrame(rows).sort_values(["episode", "fight"]).reset_index(drop=True)
    sc.to_csv(PRED / "scorecard.csv", index=False)

    coin = math.log(2)
    print(sc.to_string(index=False))
    for label, sub in (("ALL", sc), ("PRE-REGISTERED ONLY", sc[sc.preregistered])):
        if len(sub):
            print(f"{label}: {sub.hit.sum()}/{len(sub)} hits, "
                  f"running log-loss {sub.log_loss.mean():.4f} vs coin {coin:.4f}")
    print(f"wrote {PRED / 'scorecard.csv'}")


if __name__ == "__main__":
    main()
