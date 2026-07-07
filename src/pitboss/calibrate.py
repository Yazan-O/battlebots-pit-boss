"""Calibration of the primary model (Elo K=80) on out-of-sample predictions.

Reliability diagram over all backtest seasons (8-12) -> assets/calibration.png.
Run: python -m src.pitboss.calibrate
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pitboss.elo import load_matches, run_elo, metrics

K = 80
EVAL_SEASONS = (8, 9, 10, 11, 12)
INK = "#E8E4DC"
AMBER = "#FFB300"
CANVAS = "#111418"


def main() -> None:
    df = load_matches()
    scored = run_elo(df, K)
    sub = scored[scored.season.isin(EVAL_SEASONS)].copy()
    m = metrics(sub)
    print(f"eval n={m['n']} log_loss={m['log_loss']:.4f} brier={m['brier']:.4f}")

    # true symmetrization: each fight contributes both sides, (p, y) and (1-p, 1-y).
    # Needed because table-parsed fights store the winner as bot_a, so the raw a-side
    # is winner-biased and would fake an above-diagonal curve.
    p_a = sub.p_a.to_numpy()
    y_a = (sub.winner == sub.bot_a).to_numpy(float)
    p = np.concatenate([p_a, 1 - p_a])
    y = np.concatenate([y_a, 1 - y_a])

    bins = np.linspace(0.0, 1.0, 11)
    idx = np.clip(np.digitize(p, bins) - 1, 0, 9)
    rows = []
    for b in range(10):
        mask = idx == b
        if mask.sum() == 0:
            continue
        rows.append({
            "bin_mid": (bins[b] + bins[b + 1]) / 2,
            "pred_mean": p[mask].mean(),
            "emp_rate": y[mask].mean(),
            "n": int(mask.sum()),
        })
    cal = pd.DataFrame(rows)
    print(cal.to_string(index=False))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines",
                             line=dict(color="#555b63", dash="dash", width=1),
                             showlegend=False))
    fig.add_trace(go.Scatter(
        x=cal.pred_mean, y=cal.emp_rate, mode="markers+lines",
        marker=dict(color=AMBER, size=np.sqrt(cal.n) * 1.6, line=dict(color=INK, width=1)),
        line=dict(color=AMBER, width=2), showlegend=False,
        text=[f"n={n}" for n in cal.n], hoverinfo="text"))
    fig.update_layout(
        template=None, paper_bgcolor=CANVAS, plot_bgcolor=CANVAS,
        font=dict(family="IBM Plex Sans, sans-serif", color=INK, size=14),
        title=dict(text=f"Elo (K={K}) calibration — out-of-sample, seasons 8–12 (n={m['n']})",
                   font=dict(size=16)),
        xaxis=dict(title="predicted win probability", range=[0, 1], gridcolor="#22262c",
                   zeroline=False),
        yaxis=dict(title="empirical win rate", range=[0, 1], gridcolor="#22262c",
                   zeroline=False),
        width=800, height=600, margin=dict(l=70, r=30, t=60, b=60),
    )
    out = Path("assets/calibration.png")
    fig.write_image(out, scale=2)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
