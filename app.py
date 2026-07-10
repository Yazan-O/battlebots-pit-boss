"""Pit Boss — a public forecasting-methodology experiment on the BattleBots Pro League.

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

st.set_page_config(page_title="Pit Boss — the BattleBots accountability experiment",
                   page_icon="assets/favicon.png", layout="wide")

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
.bar > div {{ height: 10px; background: var(--accent); border-radius: 2px;
              animation: sweep 1.1s cubic-bezier(.16,1,.3,1); }}
@keyframes sweep {{ from {{ width: 0; }} }}
.tape {{ display: flex; align-items: center; gap: .8rem; }}
.tape .corner {{ flex: 1; display: flex; align-items: center; gap: .55rem; }}
.tape .corner.right {{ flex-direction: row-reverse; text-align: right; }}
.tape .vs {{ color: var(--ink-2); font-family: 'Barlow Condensed'; font-size: 1.1rem; }}
.tape .cls {{ color: var(--ink-2); font-size: .72rem; text-transform: uppercase;
              letter-spacing: .06em; }}
.glyph svg {{ display: block; }}
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


def glyph(cls: str, size: int = 30) -> str:
    """Hand-drawn weapon-class glyphs — our own SVG, amber line-work."""
    a, m = AMBER, MUT
    body = {
        "spinner-vertical": f'<circle cx="15" cy="15" r="9" fill="none" stroke="{a}" stroke-width="2"/><line x1="15" y1="4" x2="15" y2="26" stroke="{a}" stroke-width="2"/>',
        "spinner-horizontal": f'<ellipse cx="15" cy="15" rx="11" ry="4.5" fill="none" stroke="{a}" stroke-width="2"/><line x1="2" y1="15" x2="28" y2="15" stroke="{a}" stroke-width="1"/>',
        "hammer-saw": f'<line x1="7" y1="24" x2="20" y2="8" stroke="{a}" stroke-width="2"/><rect x="17" y="4" width="9" height="7" rx="1" fill="{a}"/>',
        "flipper": f'<path d="M4 22 L24 22 L24 12 Z" fill="none" stroke="{a}" stroke-width="2"/><path d="M20 8 q4 -4 8 0" fill="none" stroke="{m}" stroke-width="1.6"/>',
        "control-wedge": f'<path d="M4 23 L26 23 L26 15 Z" fill="{a}"/>',
        "crusher": f'<path d="M6 8 L15 20 L24 8" fill="none" stroke="{a}" stroke-width="2.4"/><line x1="15" y1="20" x2="15" y2="26" stroke="{m}" stroke-width="1.6"/>',
        "multibot": f'<rect x="4" y="12" width="9" height="9" fill="none" stroke="{a}" stroke-width="2"/><rect x="17" y="9" width="7" height="7" fill="none" stroke="{a}" stroke-width="2"/>',
    }.get(cls, f'<rect x="6" y="6" width="18" height="18" fill="none" stroke="{m}" stroke-width="2"/>')
    return (f'<span class="glyph"><svg width="{size}" height="{size}" viewBox="0 0 30 30" '
            f'xmlns="http://www.w3.org/2000/svg">{body}</svg></span>')


def tile(col, label: str, value: str, sub: str = "") -> None:
    col.markdown(
        f"""<div style="background:{PANEL};border:1px solid #2a2f36;border-radius:2px;
        padding:.6rem .9rem"><div style="color:{MUT};font-size:.78rem">{label}</div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:1.5rem">{value}</div>
        <div style="color:{MUT};font-size:.78rem">{sub}</div></div>""",
        unsafe_allow_html=True)


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
st.markdown(f"""
<div style="height:8px;background:repeating-linear-gradient(45deg,{AMBER},{AMBER} 14px,
{CANVAS} 14px,{CANVAS} 28px);border-radius:2px;margin:-.4rem 0 .7rem"></div>
<span style='color:{MUT}'>A public experiment in honest forecasting methodology, run on
the BattleBots Pro League and powered by Bright Data. Every week the model's numbers
are frozen in git <b>before</b> the episode airs; after it airs, the model is scored in
public — hits and misses, forever. The forecasts are test specimens, not advice.
<a href='https://github.com/Yazan-O/battlebots-pit-boss' style='color:{AMBER}'>
Verify the timestamps yourself</a>.</span>""", unsafe_allow_html=True)

tab_week, tab_record, tab_board, tab_hype = st.tabs(
    ["FIGHT CARD", "THE RECORD", "POWER BOARD", "HYPE CHECK"])

with tab_week:
    pred = data["pred"]
    if pred is None:
        st.write("No registered fight card yet.")
    else:
        wk = int(pred.week.iloc[0])
        tag = ("frozen in git before air" if bool(pred.preregistered.iloc[0])
               else "retrospective backfill (honestly labeled, not part of the record)")
        st.subheader(f"Week {wk} fight card — episode {int(pred.episode.iloc[0])}, airs {pred.date.iloc[0]}")
        st.caption(f"model test specimens · {tag} · registered {pred.generated_at.iloc[0]} · {pred.model_version.iloc[0]}")
        wclass = dict(pd.read_csv("data/clean/weapon_classes.csv")[["bot", "weapon_class"]].values)
        for r in pred.itertuples():
            fav, p = (r.bot_a, r.p_a) if r.p_a >= 0.5 else (r.bot_b, 1 - r.p_a)
            ca, cb = wclass.get(r.bot_a, "other"), wclass.get(r.bot_b, "other")
            st.markdown(f"""
<div class="fight">
  <div class="tape">
    <div class="corner">{glyph(ca)}<div><div class="names">{r.bot_a}</div>
      <div class="cls">{ca.replace('-', ' ')}</div></div></div>
    <div class="vs">VS</div>
    <div class="corner right">{glyph(cb)}<div><div class="names">{r.bot_b}</div>
      <div class="cls">{cb.replace('-', ' ')}</div></div></div>
  </div>
  <div class="bar"><div style="width:{r.p_a*100:.0f}%"></div></div>
  <div><span class="pct">model leans {fav} {p:.0%}</span>
       <span style="color:{MUT};font-size:.8rem"> · uncertainty is the product, not a bug</span></div>
  <div class="why">TALE OF THE TAPE — {r.why}</div>
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
    pre = sc[sc.preregistered] if sc is not None else None
    coin = math.log(2)
    # THE track record is pre-registered fights only — nothing else counts
    if pre is None or pre.empty:
        st.subheader("Awaiting the first pre-registered result")
        st.markdown(f"<span style='color:{MUT}'>The week-2 fight card is committed and "
                    "frozen (see the git timestamp) — the first accountable scores land "
                    "when episode 102 airs. Nothing here will ever be backfilled.</span>",
                    unsafe_allow_html=True)
    else:
        c1, c2, c3 = st.columns(3)
        tile(c1, "pre-registered fights scored", str(len(pre)))
        tile(c2, "hits", f"{int(pre.hit.sum())}/{len(pre)}")
        tile(c3, "running log-loss", f"{pre.log_loss.mean():.3f}", "coin flip = 0.693")
        sc2 = pre.reset_index()
        sc2["running"] = sc2.log_loss.expanding().mean()
        fig = go.Figure()
        fig.add_hline(y=coin, line=dict(color=MUT, dash="dash"),
                      annotation_text="coin flip", annotation_font_color=MUT)
        fig.add_trace(go.Scatter(x=sc2.index + 1, y=sc2.running, mode="lines+markers",
                                 line=dict(color=AMBER, width=2), showlegend=False))
        plotly_layout(fig, height=380,
                      xaxis_title="pre-registered fights (chronological)",
                      yaxis_title="running log-loss (lower is better)")
        st.plotly_chart(fig, width="stretch")

    def scoretable(df):
        show = df[["episode", "fight", "predicted_winner", "p_predicted",
                   "actual_winner", "hit"]].copy()
        show["hit"] = show.hit.map({1: "✓ hit", 0: "✗ miss"})
        return show.style.map(
            lambda v: f"color: {'#4c9e6a' if v == '✓ hit' else '#b0524d'}; font-weight: 600",
            subset=["hit"])

    if pre is not None and not pre.empty:
        st.dataframe(scoretable(pre), hide_index=True, width="stretch")
    retro = sc[~sc.preregistered] if sc is not None else None
    if retro is not None and not retro.empty:
        with st.expander("Retrospective validation (episode 1 aired before Pit Boss "
                         "went live — honest backfill, model trained only on prior "
                         "data, NOT part of the accountable record)"):
            st.dataframe(scoretable(retro), hide_index=True, width="stretch")

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
    st.caption("Intervals: parametric bootstrap (chronology-preserving) for bots with "
               "5+ recorded fights; bots below that show the population prior band — "
               "an honest 'could be anywhere in the field' instead of fake precision. "
               "New bots start at the population mean (1500).")
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
        tile(c1, "most hyped vs rating", o.bot, f"buzz #{int(o.buzz_rank)} · Elo #{int(o.elo_rank)}")
    if len(under):
        u = under.iloc[0]
        tile(c2, "most slept-on", u.bot, f"Elo {u.elo:.0f} · {int(u.mentions)} mentions")
    st.caption("Buzz counts are exposure-biased: bots that fought in an aired episode "
               "get talked about. Read this as attention vs rating, not merit vs rating.")

st.markdown('<div class="disclaimer">Pit Boss is an entertainment and data-engineering '
            'project — a public test of forecasting methodology on a pre-taped TV show. '
            'Not betting advice. Please don\'t gamble with it. Data: Bright Data (Web '
            'Unlocker, SERP API, Web Scraper API, MCP) + Wikipedia\'s open API. '
            '#BattleBotsDev</div>', unsafe_allow_html=True)
