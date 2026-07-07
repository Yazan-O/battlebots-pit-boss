"""Signature analyses: weapon meta over time + hype vs performance.

python -m src.pitboss.analyses -> assets/weapon_meta.png, assets/hype_vs_perf.png
Numbers print to stdout; narrative lives in the README, sourced from these outputs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pitboss.aliases import canon, load as load_aliases
from pitboss.elo import load_matches

CLEAN = Path("data/clean")
PRED = Path("data/predictions")
INK = "#E8E4DC"
AMBER = "#FFB300"
CANVAS = "#111418"
GRID = "#22262c"
# muted companions to the single amber accent (accent stays reserved for the headline)
CLASS_COLORS = {
    "spinner-vertical": AMBER,
    "spinner-horizontal": "#8A96A3",
    "hammer-saw": "#5E6B78",
    "flipper": "#46525E",
    "control-wedge": "#333E49",
    "crusher": "#733d1e",
    "multibot": "#4a3a5e",
    "other": "#2a2f36",
}

LAYOUT = dict(
    template=None, paper_bgcolor=CANVAS, plot_bgcolor=CANVAS,
    font=dict(family="IBM Plex Sans, sans-serif", color=INK, size=14),
    margin=dict(l=70, r=30, t=60, b=60),
)


def weapon_meta() -> None:
    df = load_matches()
    wclass = dict(pd.read_csv(CLEAN / "weapon_classes.csv")[["bot", "weapon_class"]].values)
    df["winner_class"] = df.winner.map(lambda b: wclass.get(b, "other"))
    counts = df.groupby(["season", "winner_class"]).size().rename("n").reset_index()
    counts["share"] = counts.n / counts.groupby("season").n.transform("sum")
    share = counts
    share["wc"] = share.season - 5

    fig = go.Figure()
    for cls in CLASS_COLORS:
        sub = share[share.winner_class == cls]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub.wc, y=sub.share, name=cls.replace("-", " "),
            mode="lines+markers", line=dict(color=CLASS_COLORS[cls], width=3 if cls == "spinner-vertical" else 1.5),
            marker=dict(size=7 if cls == "spinner-vertical" else 5)))
    fig.update_layout(
        **LAYOUT, width=900, height=560,
        title=dict(text="Share of wins by weapon class, World Championship I–VII", font=dict(size=16)),
        xaxis=dict(title="World Championship", tickmode="array",
                   tickvals=list(range(1, 8)), ticktext=["I", "II", "III", "IV", "V", "VI", "VII"],
                   gridcolor=GRID, zeroline=False),
        yaxis=dict(title="share of wins", tickformat=".0%", gridcolor=GRID, zeroline=False),
        legend=dict(bgcolor=CANVAS, borderwidth=0),
    )
    fig.write_image("assets/weapon_meta.png", scale=2)

    wide = share.pivot_table(index="wc", columns="winner_class", values="share").fillna(0)
    print("win share by class per WC:")
    print((wide * 100).round(1).to_string())
    v = wide.get("spinner-vertical")
    print(f"\nvertical-spinner win share: WC I {v.iloc[0]:.0%} -> WC VII {v.iloc[-1]:.0%}")


def hype_vs_perf() -> None:
    buzz = pd.read_csv(CLEAN / "buzz.csv")
    table = load_aliases()
    buzz["bot"] = buzz.bot.map(lambda n: canon(n, table))
    agg = buzz.groupby("bot").mentions.sum().reset_index()
    strengths = pd.read_csv(PRED / "strengths.csv")
    m = strengths.merge(agg, on="bot", how="left").fillna({"mentions": 0})
    m["elo_rank"] = m.elo.rank(ascending=False)
    m["buzz_rank"] = m.mentions.rank(ascending=False)
    m["gap"] = m.elo_rank - m.buzz_rank  # positive = more hyped than good

    # label only points that stand apart; the no-buzz newcomer cluster gets one note
    m["label"] = m.apply(lambda r: r.bot if (r.mentions >= 3 or r.elo >= 1600) else "", axis=1)
    quiet = m[(m.label == "") & (m.mentions <= 1)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=m.mentions, y=m.elo, mode="markers+text",
        text=m.label, textposition="top center",
        textfont=dict(size=10, color=INK),
        marker=dict(color=AMBER, size=10, line=dict(color=INK, width=1)),
        showlegend=False))
    if len(quiet):
        fig.add_annotation(
            x=1.2, y=quiet.elo.mean(), ax=110, ay=40,
            text=f"{len(quiet)} bots nobody is talking about yet",
            font=dict(size=11, color="#8A96A3"), arrowcolor="#8A96A3")
    fig.update_layout(
        **LAYOUT, width=900, height=620,
        title=dict(text="Hype vs performance — fan mentions (all episodes) vs current Elo", font=dict(size=16)),
        xaxis=dict(title="fan-comment mentions (YouTube + Reddit)", gridcolor=GRID, zeroline=False),
        yaxis=dict(title="current Elo", gridcolor=GRID, zeroline=False),
    )
    fig.write_image("assets/hype_vs_perf.png", scale=2)

    talked = m[m.mentions >= 3]
    over = talked.sort_values("gap", ascending=False).head(3)
    under = m[m.elo_rank <= 8].sort_values("mentions").head(3)
    print("\nmost hyped relative to Elo (mentions>=3):")
    print(over[["bot", "mentions", "elo", "elo_rank", "buzz_rank"]].to_string(index=False))
    print("strong but under-discussed (Elo top-8, fewest mentions):")
    print(under[["bot", "mentions", "elo", "elo_rank"]].to_string(index=False))


if __name__ == "__main__":
    weapon_meta()
    hype_vs_perf()
    print("\nwrote assets/weapon_meta.png, assets/hype_vs_perf.png")
