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
    """Entry share (how much of the field) + win rate (efficacy) per class.

    Win SHARE alone is participation-confounded: verticals win more fights mostly
    because more verticals enter. Entry share shows adoption; win rate shows edge.
    """
    df = load_matches()
    wclass = dict(pd.read_csv(CLEAN / "weapon_classes.csv")[["bot", "weapon_class"]].values)
    rows = []
    for r in df.itertuples():
        for bot in (r.bot_a, r.bot_b):
            rows.append({"season": r.season, "cls": wclass.get(bot, "other"),
                         "won": int(bot == r.winner)})
    app_df = pd.DataFrame(rows)
    agg = app_df.groupby(["season", "cls"]).agg(apps=("won", "size"), wins=("won", "sum")).reset_index()
    agg["entry_share"] = agg.apps / agg.groupby("season").apps.transform("sum")
    agg["win_rate"] = agg.wins / agg.apps
    agg["wc"] = agg.season - 5

    fig = go.Figure()
    for cls in ("spinner-vertical", "spinner-horizontal", "hammer-saw", "flipper", "control-wedge"):
        sub = agg[agg.cls == cls]
        hero = cls == "spinner-vertical"
        fig.add_trace(go.Scatter(
            x=sub.wc, y=sub.entry_share, name=f"{cls.replace('-', ' ')} — entry share",
            mode="lines+markers", line=dict(color=CLASS_COLORS[cls], width=3 if hero else 1.5),
            marker=dict(size=7 if hero else 5)))
        if hero:
            fig.add_trace(go.Scatter(
                x=sub.wc, y=sub.win_rate, name="vertical spinner — win rate",
                mode="lines+markers", line=dict(color=CLASS_COLORS[cls], width=1.5, dash="dot"),
                marker=dict(size=5)))
    fig.add_hline(y=0.5, line=dict(color="#555b63", dash="dash", width=1))
    fig.update_layout(
        **LAYOUT, width=900, height=560,
        title=dict(text="The vertical-spinner takeover is adoption, not dominance — "
                        "entry share (solid) vs win rate (dotted)", font=dict(size=15)),
        xaxis=dict(title="World Championship", tickmode="array",
                   tickvals=list(range(1, 8)), ticktext=["I", "II", "III", "IV", "V", "VI", "VII"],
                   gridcolor=GRID, zeroline=False),
        yaxis=dict(title="share / rate", tickformat=".0%", gridcolor=GRID, zeroline=False),
        legend=dict(bgcolor=CANVAS, borderwidth=0),
    )
    fig.write_image("assets/weapon_meta.png", scale=2)

    v = agg[agg.cls == "spinner-vertical"].sort_values("wc")
    print("vertical spinners per WC (entry share / win rate):")
    print(v[["wc", "entry_share", "win_rate"]].round(3).to_string(index=False))
    print("\nCaveat (recorded): weapon classes are current-era registry labels; a few "
          "bots ran different configurations in early seasons (e.g. Bite Force WC I).")


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
