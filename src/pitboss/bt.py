"""Bradley-Terry with recency weighting + weapon-class matchup adjustment.

P(a beats b) = sigmoid(theta_a - theta_b + M[class_a, class_b]) with M antisymmetric,
fit by weighted MLE (scipy L-BFGS) with L2 regularization. Training matches are
weighted exp(-age_seasons/half_life). Chronological backtest, hyperparameters tuned
on validation seasons 8-11 only; season 12 held out (same protocol as elo.py).
Run: python -m src.pitboss.bt
"""
from __future__ import annotations

import math
import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pitboss.elo import load_matches, metrics, VAL_SEASONS, TEST_SEASON

CLEAN = Path("data/clean")


def load_weapon_classes() -> dict[str, str]:
    df = pd.read_csv(CLEAN / "weapon_classes.csv")
    return dict(zip(df.bot, df.weapon_class))


class BTModel:
    def __init__(self, half_life: float, l2_theta: float, l2_m: float):
        self.half_life = half_life
        self.l2_theta = l2_theta
        self.l2_m = l2_m
        self.theta: dict[str, float] = {}
        self.m: np.ndarray | None = None
        self.classes: list[str] = []

    def _matchup(self, ca: str, cb: str) -> tuple[int, int]:
        ia = self.classes.index(ca) if ca in self.classes else -1
        ib = self.classes.index(cb) if cb in self.classes else -1
        return ia, ib

    def fit(self, df: pd.DataFrame, wclass: dict[str, str], asof_season: int) -> "BTModel":
        bots = sorted(set(df.bot_a) | set(df.bot_b))
        self.classes = sorted(set(wclass.get(b, "other") for b in bots) | {"other"})
        n, c = len(bots), len(self.classes)
        bot_i = {b: i for i, b in enumerate(bots)}
        cls_i = {b: self.classes.index(wclass.get(b, "other")) for b in bots}

        ia = df.bot_a.map(bot_i).to_numpy()
        ib = df.bot_b.map(bot_i).to_numpy()
        ca = df.bot_a.map(cls_i).to_numpy()
        cb = df.bot_b.map(cls_i).to_numpy()
        y = (df.winner == df.bot_a).to_numpy(float)
        w = np.exp(-(asof_season - df.season.to_numpy(float)) / self.half_life)

        # params: n thetas + c*c matchup matrix (antisymmetry enforced via M - M.T)
        def unpack(x):
            return x[:n], (x[n:].reshape(c, c) - x[n:].reshape(c, c).T) / 2.0

        def nll(x):
            th, m = unpack(x)
            z = th[ia] - th[ib] + m[ca, cb]
            p = expit(z)
            eps = 1e-12
            ll = w * (y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps))
            return -ll.sum() + self.l2_theta * (th ** 2).sum() + self.l2_m * (m ** 2).sum()

        x0 = np.zeros(n + c * c)
        res = minimize(nll, x0, method="L-BFGS-B", options={"maxiter": 500})
        th, m = unpack(res.x)
        self.theta = {b: float(th[bot_i[b]]) for b in bots}
        self.m = m
        self._cls_of = lambda b: wclass.get(b, "other")
        return self

    def predict(self, bot_a: str, bot_b: str) -> float:
        th_a = self.theta.get(bot_a, 0.0)  # unseen bot: shrunk-to-mean prior
        th_b = self.theta.get(bot_b, 0.0)
        ia, ib = self._matchup(self._cls_of(bot_a), self._cls_of(bot_b))
        adj = float(self.m[ia, ib]) if (self.m is not None and ia >= 0 and ib >= 0) else 0.0
        return float(expit(th_a - th_b + adj))


def backtest(df: pd.DataFrame, wclass: dict[str, str], seasons: tuple[int, ...],
             half_life: float, l2_theta: float, l2_m: float) -> dict:
    """Episode-level rolling refit: before each eval episode, fit on ALL strictly
    earlier matches (prior seasons + earlier episodes of the same season) — the same
    information Elo has, and exactly what the weekly production loop does."""
    frames = []
    for s in seasons:
        test_season = df[df.season == s]
        # consecutive same-episode runs in document order (= chronological)
        ep_key = test_season.episode.fillna(-1).to_numpy()
        starts = [0] + [i for i in range(1, len(ep_key)) if ep_key[i] != ep_key[i - 1]]
        for j, st in enumerate(starts):
            en = starts[j + 1] if j + 1 < len(starts) else len(ep_key)
            block = test_season.iloc[st:en].copy()
            earlier = df[(df.season < s) | ((df.season == s) & (df.index < block.index.min()))]
            model = BTModel(half_life, l2_theta, l2_m).fit(earlier, wclass, asof_season=s)
            block["p_a"] = [model.predict(a, b) for a, b in zip(block.bot_a, block.bot_b)]
            frames.append(block)
    return metrics(pd.concat(frames))


def main() -> None:
    df = load_matches()
    wclass = load_weapon_classes()
    cov = sum(1 for b in set(df.bot_a) | set(df.bot_b) if wclass.get(b, "other") != "other")
    print(f"{len(df)} matches; weapon class known for {cov} bots")

    grid = list(product([3.0, 6.0, 12.0, 1e9], [0.3, 0.5, 1.0, 2.0], [1.0, 3.0, 10.0]))
    print(f"\nHyperparameter grid ({len(grid)} combos) on validation {VAL_SEASONS}:")
    best, best_ll = None, math.inf
    for hl, l2t, l2m in grid:
        m = backtest(df, wclass, VAL_SEASONS, hl, l2t, l2m)
        flag = ""
        if m["log_loss"] < best_ll:
            best, best_ll, flag = (hl, l2t, l2m), m["log_loss"], "  <- best"
        print(f"  hl={hl:<4} l2_th={l2t:<5} l2_m={l2m:<5}: ll={m['log_loss']:.4f} "
              f"brier={m['brier']:.4f} acc={m['accuracy']:.3f}{flag}")

    hl, l2t, l2m = best
    m = backtest(df, wclass, (TEST_SEASON,), hl, l2t, l2m)
    print(f"\nHELD-OUT season {TEST_SEASON}, hl={hl} l2_theta={l2t} l2_m={l2m}:")
    print(f"  log_loss={m['log_loss']:.4f}  brier={m['brier']:.4f}  "
          f"acc={m['accuracy']:.3f}  n={m['n']}")
    print("  (Elo baseline held-out: log_loss=0.6430, brier=0.2299 — BT ships as "
          "primary only if it beats BOTH)")


if __name__ == "__main__":
    main()
