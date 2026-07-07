"""Pit Boss — live BattleBots Pro League predictions, publicly scored.

Reads everything from data/ in this repo; every data commit refreshes the site.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

INK = "#E8E4DC"
MUT = "#8A96A3"
AMBER = "#FFB300"
CANVAS = "#111418"
PANEL = "#191d23"
GRID = "#22262c"

st.set_page_config(page_title="Pit Boss — BattleBots Pro League predictions",
                   page_icon="🤖", layout="wide")

st.markdown(f"""
<style>
/* tokens — voices: Barlow Condensed announces, IBM Plex Sans explains,
   IBM Plex Mono is the instrument voice (every number). One accent: arena
   amber. Status colors are reserved for hit/miss state, nowhere else. */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;600&family=Barlow+Condensed:wght@600;700&display=swap');
:root {{
  --ink: {INK}; --ink-2: {MUT}; --canvas: {CANVAS}; --panel: {PANEL};
  --accent: {AMBER}; --rule: #2a2f36; --rule-strong: #3a4149;
  --hit: #4c9e6a; --miss: #b0524d;
}}
html, body, [class*="st-"] {{ font-family: 'IBM Plex Sans', sans-serif; }}
h1, h2, h3 {{ font-family: 'Barlow Condensed', sans-serif; letter-spacing: .02em; }}
.stTabs [data-baseweb="tab"] {{ border-radius: 2px; }}
div[data-testid="stMetric"] {{ background: var(--panel); padding: .6rem .9rem;
  border-radius: 2px; border: 1px solid var(--rule); }}
div[data-testid="stMetricValue"] {{ font-family: 'IBM Plex Mono', monospace; }}
#MainMenu, footer {{ visibility: hidden; }}
.fight {{ background: var(--panel); border: 1px solid var(--rule);
          border-left: 3px solid var(--accent); border-radius: 2px;
          padding: .9rem 1.1rem; margin-bottom: .8rem; }}
.fight .names {{ font-family: 'Barlow Condensed'; font-size: 1.5rem; font-weight: 700; }}
.fight .why {{ color: var(--ink-2); font-size: .85rem; margin-top: .35rem; }}
.bar {{ height: 10px; background: var(--rule); border-radius: 2px; margin: .45rem 0 .2rem; }}
.bar > div {{ height: 10px; background: var(--accent); border-radius: 2px; }}
.pct {{ color: var(--accent); font-weight: 600; font-family: 'IBM Plex Mono', monospace; }}
.disclaimer {{ color: var(--ink-2); font-size: .78rem; margin-top: 2rem;
               border-top: 1px solid var(--rule); padding-top: .8rem; }}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=600)
def load():
    d = {}
    d["pred"] = None
    weeks = sorted(Path("data/predictions").glob("week_*.csv"))
    if weeks:
        d["pred"] = pd.read_csv(weeks[-1])
    p = Path("data/predictions/scorecard.csv")
    d["scorecard"] = pd.read_csv(p) if p.exists() else None
    d["strengths"] = pd.read_csv("data/predictions/strengths.csv")
    d["buzz"] = pd.read_csv("data/clean/buzz.csv")
    d["hist"] = pd.read_parquet("data/clean/matches_hist.parquet")
    return d


def plotly_layout(fig: go.Figure, **kw) -> go.Figure:
    fig.update_layout(
        template=None, paper_bgcolor=CANVAS, plot_bgcolor=CANVAS,
        font=dict(family="IBM Plex Sans, sans-serif", color=INK, size=14),
        margin=dict(l=60, r=20, t=40, b=50), **kw)
    mono = dict(family="IBM Plex Mono, monospace", size=12)
    fig.update_xaxes(gridcolor=GRID, zeroline=False, tickfont=mono)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=mono)
    return fig


data = load()

st.title("PIT BOSS")
st.markdown(f"<span style='color:{MUT}'>Pre-registered win predictions for the live "
            "BattleBots Pro League season, powered by Bright Data — published before "
            "every episode, publicly scored after. "
            "<a href='https://github.com/Yazan-O/battlebots-pit-boss' style='color:#FFB300'>"
            "Verify the git timestamps yourself</a>.</span>", unsafe_allow_html=True)

tab_week, tab_record, tab_board, tab_hype = st.tabs(
    ["THIS WEEK", "TRACK RECORD", "LEADERBOARD", "HYPE VS PERFORMANCE"])

with tab_week:
    pred = data["pred"]
    if pred is None:
        st.write("No prediction file yet.")
    else:
        wk = int(pred.week.iloc[0])
        tag = "pre-registered" if bool(pred.preregistered.iloc[0]) else "retrospective (honestly labeled)"
        st.subheader(f"Week {wk} — episode {int(pred.episode.iloc[0])}, airs {pred.date.iloc[0]} · {tag}")
        st.caption(f"predictions generated {pred.generated_at.iloc[0]} · model {pred.model_version.iloc[0]}")
        for r in pred.itertuples():
            fav, p = (r.bot_a, r.p_a) if r.p_a >= 0.5 else (r.bot_b, 1 - r.p_a)
            st.markdown(f"""
<div class="fight">
  <div class="names">{r.bot_a} <span style="color:{MUT}">vs</span> {r.bot_b}</div>
  <div class="bar"><div style="width:{r.p_a*100:.0f}%"></div></div>
  <div><span class="pct">{fav} {p:.0%}</span></div>
  <div class="why">{r.why}</div>
</div>""", unsafe_allow_html=True)

        st.divider()
        st.subheader("SCOUT REPORT")
        st.caption("Live intel per bot — Bright Data MCP server (search_engine + "
                   "scrape_as_markdown), condensed to 10 lines.")
        bots_this_week = sorted(set(pred.bot_a) | set(pred.bot_b))
        pick = st.selectbox("Scout this bot", bots_this_week)
        if st.button("Scout", type="primary"):
            import sys as _sys
            _sys.path.insert(0, "src")
            from pitboss import scout as _scout
            key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not key:
                try:
                    key = st.secrets["ANTHROPIC_API_KEY"]
                except Exception:
                    key = ""
            rep = None
            if key:
                try:
                    os.environ["ANTHROPIC_API_KEY"] = key
                    cached = _scout.load_cached(pick)
                    if cached and cached.get("generated") == str(pd.Timestamp.today().date()):
                        rep = cached
                    else:
                        src_ = _scout.gather(pick)
                        text = _scout.generate_report(pick, src_)
                        _scout.save(pick, text, src_)
                        rep = _scout.load_cached(pick)
                except Exception:
                    rep = _scout.load_cached(pick)
            else:
                rep = _scout.load_cached(pick)
            if rep:
                st.markdown(f"**{rep['bot']}** · report generated {rep['generated']}")
                st.text(rep["report"])
                st.caption("sources: " + " · ".join(rep["sources"]))
                if "note" in rep:
                    st.caption(rep["note"])
            else:
                st.write(f"No cached report for {pick} yet — reports refresh weekly.")

with tab_record:
    sc = data["scorecard"]
    if sc is None or sc.empty:
        st.write("First scored episode lands after the next air date.")
    else:
        coin = math.log(2)
        c1, c2, c3 = st.columns(3)
        c1.metric("fights scored", len(sc))
        c2.metric("hits", f"{int(sc.hit.sum())}/{len(sc)}")
        c3.metric("running log-loss vs coin 0.693", f"{sc.log_loss.mean():.3f}")
        sc2 = sc.reset_index()
        sc2["running"] = sc2.log_loss.expanding().mean()
        fig = go.Figure()
        fig.add_hline(y=coin, line=dict(color=MUT, dash="dash"),
                      annotation_text="coin flip", annotation_font_color=MUT)
        fig.add_trace(go.Scatter(x=sc2.index + 1, y=sc2.running, mode="lines+markers",
                                 line=dict(color=AMBER, width=2), showlegend=False))
        plotly_layout(fig, height=380,
                      xaxis_title="fights scored (chronological)",
                      yaxis_title="running log-loss (lower is better)")
        st.plotly_chart(fig, width="stretch")
        show = sc[["episode", "fight", "predicted_winner", "p_predicted",
                   "actual_winner", "hit", "preregistered"]].copy()
        show["hit"] = show.hit.map({1: "✓ hit", 0: "✗ miss"})
        styled = show.style.map(
            lambda v: f"color: {'#4c9e6a' if v == '✓ hit' else '#b0524d'}; font-weight: 600",
            subset=["hit"])
        st.dataframe(styled, hide_index=True, width="stretch")

with tab_board:
    s = data["strengths"].sort_values("elo")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=s.elo, y=s.bot, mode="markers",
        error_x=dict(type="data", symmetric=False,
                     array=s.ci_hi - s.elo, arrayminus=s.elo - s.ci_lo,
                     color="#46525E", thickness=1.2),
        marker=dict(color=AMBER, size=9), showlegend=False,
        customdata=s[["career_w", "career_l", "weapon_class"]],
        hovertemplate="%{y}: %{x:.0f} · %{customdata[0]}-%{customdata[1]} · %{customdata[2]}<extra></extra>"))
    plotly_layout(fig, height=640, xaxis_title="Elo (90% bootstrap interval)",
                  title=dict(text="The 24 Pro League bots by current Elo", font=dict(size=16)))
    st.plotly_chart(fig, width="stretch")
    st.caption("Bots with few career fights carry wide intervals — that width is the "
               "honest uncertainty, not a bug. New bots start at the population mean (1500).")
    st.image("assets/weapon_meta.png",
             caption="The reboot-era meta: vertical spinners won 37% of fights in WC I, 57% by WC VII.")

with tab_hype:
    buzz = data["buzz"].groupby("bot").mentions.sum().reset_index()
    m = data["strengths"].merge(buzz, on="bot", how="left").fillna({"mentions": 0})
    m["label"] = m.apply(lambda r: r.bot if (r.mentions >= 3 or r.elo >= 1600) else "", axis=1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=m.mentions, y=m.elo, mode="markers+text", text=m.label,
        textposition="top center", textfont=dict(size=10, color=INK),
        marker=dict(color=AMBER, size=10, line=dict(color=INK, width=1)),
        hovertemplate="%{hovertext}: %{x} mentions, Elo %{y:.0f}<extra></extra>",
        hovertext=m.bot, showlegend=False))
    plotly_layout(fig, height=520,
                  xaxis_title="fan-comment mentions (YouTube + Reddit, via Bright Data)",
                  yaxis_title="current Elo")
    st.plotly_chart(fig, width="stretch")
    talked = m[m.mentions >= 3].copy()
    talked["elo_rank"] = m.elo.rank(ascending=False)[talked.index]
    talked["buzz_rank"] = m.mentions.rank(ascending=False)[talked.index]
    talked["gap"] = talked.elo_rank - talked.buzz_rank
    over = talked.sort_values(["gap", "mentions"], ascending=False).head(1)
    under = m[m.elo.rank(ascending=False) <= 8].sort_values("mentions").head(1)
    c1, c2 = st.columns(2)
    if len(over):
        o = over.iloc[0]
        c1.metric("most hyped vs rating", o.bot,
                  f"buzz #{int(o.buzz_rank)} · Elo #{int(o.elo_rank)}", delta_color="off")
    if len(under):
        u = under.iloc[0]
        c2.metric("most slept-on", u.bot,
                  f"Elo {u.elo:.0f} · {int(u.mentions)} mentions", delta_color="off")

st.markdown('<div class="disclaimer">Pit Boss is an entertainment and data-engineering '
            'project — a public test of forecasting methodology on a pre-taped TV show. '
            'Not betting advice. Please don\'t gamble with it. Data: Bright Data (Web '
            'Unlocker, SERP API, Web Scraper API, MCP) + Wikipedia\'s open API. '
            '#BattleBotsDev</div>', unsafe_allow_html=True)
