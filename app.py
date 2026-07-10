"""Pit Boss — a public forecasting-methodology experiment on the BattleBots Pro League.

Reads everything from data/ in this repo; every data commit refreshes the site.
Visual system: BROADCAST (notes/DESIGN_DIRECTION.md) — red corner vs blue corner,
gold reserved for the brand and THE RECORD.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BG = "#0B0D10"
SURFACE = "#14171C"
SURFACE2 = "#1A1E24"
INK = "#EDEAE2"
MUT = "#7E8894"
BORDER = "#232830"
GOLD = "#FFB300"
RED = "#E5484D"
BLUE = "#3B82F6"
HIT = "#4C9E6A"
MISS = "#B0524D"

st.set_page_config(page_title="Pit Boss — the BattleBots accountability experiment",
                   page_icon="assets/favicon.png", layout="wide")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;700&family=Barlow+Condensed:wght@600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root {{
  --bg:{BG}; --surface:{SURFACE}; --surface2:{SURFACE2}; --ink:{INK}; --muted:{MUT};
  --border:{BORDER}; --gold:{GOLD}; --red:{RED}; --blue:{BLUE}; --hit:{HIT}; --miss:{MISS};
  --disp:'Barlow Condensed',sans-serif; --body:'Archivo',sans-serif; --mono:'IBM Plex Mono',monospace;
}}
.stApp {{ background:var(--bg);
  background-image:radial-gradient(ellipse 90% 55% at 50% -12%, rgba(255,179,0,.05), transparent 60%); }}
html, body, [class*="st-"] {{ font-family:var(--body); }}
span[data-testid="stIconMaterial"], .material-symbols-rounded {{
  font-family:'Material Symbols Rounded' !important; }}
h1,h2,h3 {{ font-family:var(--disp); text-transform:uppercase; letter-spacing:.01em; }}
#MainMenu, footer {{ visibility:hidden; }}
.block-container {{ padding-top:2.2rem; max-width:1180px; }}

/* masthead */
.mast {{ display:flex; align-items:flex-end; justify-content:space-between; gap:1rem; flex-wrap:wrap; }}
.mast .t {{ font-family:var(--disp); font-weight:800; font-size:3.6rem; line-height:.9;
  text-transform:uppercase; }}
.mast .tag {{ color:var(--muted); font-size:.85rem; margin-top:.35rem; }}
.chip {{ background:var(--surface); border:1px solid var(--border); padding:.55rem 1rem;
  text-align:right; }}
.chip .lbl {{ color:var(--muted); font-size:.66rem; letter-spacing:.22em; }}
.chip .val {{ font-family:var(--mono); font-weight:600; font-size:1.25rem; color:var(--gold); }}
.chip .val small {{ color:var(--muted); font-size:.72rem; font-weight:400; }}
.haz {{ height:6px; margin:.8rem 0 .3rem;
  background:repeating-linear-gradient(45deg,var(--gold),var(--gold) 12px,transparent 12px,transparent 24px); }}

/* tabs as broadcast chrome */
.stTabs [data-baseweb="tab-list"] {{ gap:1.6rem; border-bottom:1px solid var(--border); }}
.stTabs [data-baseweb="tab"] {{ font-family:var(--disp); font-weight:700; font-size:1.05rem;
  letter-spacing:.12em; text-transform:uppercase; padding:.5rem 0; background:transparent; }}
.stTabs [aria-selected="true"] {{ color:var(--gold) !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background-color:var(--gold); height:3px; }}

/* fight plate — the signature element */
.plate {{ background:var(--surface); border:1px solid var(--border); position:relative;
  margin:1.1rem 0 1.6rem; opacity:0; transform:translateY(14px);
  animation:reveal .55s cubic-bezier(.16,1,.3,1) forwards; }}
.plate::before {{ content:""; position:absolute; top:0; bottom:0; left:0; width:5px; background:var(--red); }}
.plate::after  {{ content:""; position:absolute; top:0; bottom:0; right:0; width:5px; background:var(--blue); }}
@keyframes reveal {{ to {{ opacity:1; transform:none; }} }}
.plate:hover {{ box-shadow:0 10px 34px rgba(0,0,0,.5); }}
.tape {{ display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:1rem;
  padding:1.6rem 2.4rem .9rem; }}
.corner {{ display:flex; align-items:center; gap:.9rem; }}
.corner.b {{ flex-direction:row-reverse; text-align:right; }}
.corner .tag {{ font-family:var(--disp); font-weight:700; font-size:.72rem; letter-spacing:.24em; }}
.corner.r .tag {{ color:var(--red); }} .corner.b .tag {{ color:var(--blue); }}
.corner .nm {{ font-family:var(--disp); font-weight:800; font-size:2.5rem; line-height:.95;
  text-transform:uppercase; }}
.corner .cl {{ color:var(--muted); font-size:.7rem; letter-spacing:.14em; text-transform:uppercase;
  margin-top:.25rem; font-family:var(--mono); }}
.vs {{ font-family:var(--disp); font-weight:800; font-size:1.7rem; color:var(--ink);
  border-bottom:2px solid var(--gold); padding:0 .5rem .1rem; }}
.glyph svg {{ display:block; transition:transform .6s cubic-bezier(.16,1,.3,1); }}
.plate:hover .glyph.spin svg {{ transform:rotate(180deg); }}
.probwrap {{ padding:0 2.4rem 1.2rem; }}
.prob {{ display:flex; height:12px; background:var(--surface2); overflow:hidden; }}
.prob .pa {{ background:var(--red); transform-origin:left; animation:grow .9s cubic-bezier(.16,1,.3,1); }}
.prob .pb {{ background:var(--blue); flex:1; transform-origin:right; animation:grow .9s cubic-bezier(.16,1,.3,1); }}
@keyframes grow {{ from {{ transform:scaleX(0); }} }}
.probnum {{ display:flex; justify-content:space-between; align-items:baseline; margin-top:.55rem; }}
.probnum .a {{ color:var(--red); }} .probnum .b {{ color:var(--blue); }}
.probnum .a, .probnum .b {{ font-family:var(--mono); font-weight:600; font-size:1.35rem; }}
.probnum .mid {{ color:var(--muted); font-size:.68rem; letter-spacing:.18em; text-transform:uppercase; }}
.briefs {{ display:grid; grid-template-columns:1fr 1fr; border-top:1px solid var(--border); }}
.brief {{ padding:1.2rem 2.4rem 1.4rem; }}
.brief.r {{ border-right:1px solid var(--border); }}
.brief h4 {{ font-family:var(--disp); font-weight:700; font-size:.8rem; letter-spacing:.2em;
  margin:0 0 .2rem; text-transform:uppercase; }}
.brief.r h4 {{ color:var(--red); }} .brief.b h4 {{ color:var(--blue); }}
.brief ul {{ margin:0; padding:0; }}
.brief li {{ list-style:none; color:#B9C0C9; font-size:.83rem; line-height:1.5;
  padding-left:.95rem; position:relative; margin-top:.5rem; }}
.brief li::before {{ content:""; position:absolute; left:0; top:.55em; width:7px; height:2px; }}
.brief.r li::before {{ background:var(--red); }} .brief.b li::before {{ background:var(--blue); }}
details.tape-d {{ border-top:1px solid var(--border); }}
details.tape-d summary {{ cursor:pointer; color:var(--muted); font-family:var(--mono);
  font-size:.68rem; letter-spacing:.16em; padding:.55rem 2.4rem; list-style:none; }}
details.tape-d summary::before {{ content:"+ "; color:var(--gold); }}
details.tape-d[open] summary::before {{ content:"− "; }}
details.tape-d div {{ color:var(--muted); font-size:.8rem; padding:0 2.4rem .9rem; line-height:1.5; }}

/* record board */
.board {{ display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:var(--border);
  border:1px solid var(--border); margin:1.1rem 0; }}
.cell {{ background:var(--surface); padding:1.3rem 1.6rem; }}
.cell .lbl {{ color:var(--muted); font-size:.66rem; letter-spacing:.22em; text-transform:uppercase; }}
.cell .big {{ font-family:var(--mono); font-weight:600; font-size:2.6rem; color:var(--gold);
  text-shadow:0 0 22px rgba(255,179,0,.35); line-height:1.15; }}
.cell .sub {{ color:var(--muted); font-size:.72rem; font-family:var(--mono); }}
.row {{ display:grid; grid-template-columns:64px 1fr auto auto; gap:1.2rem; align-items:center;
  background:var(--surface); border:1px solid var(--border); border-top:none; padding:.7rem 1.3rem; }}
.row:first-of-type {{ border-top:1px solid var(--border); }}
.row .ep {{ font-family:var(--mono); color:var(--muted); font-size:.78rem; }}
.row .f {{ font-family:var(--disp); font-weight:700; font-size:1.15rem; text-transform:uppercase;
  letter-spacing:.03em; }}
.row .call {{ font-family:var(--mono); font-size:.78rem; color:var(--muted); text-align:right; }}
.row .call b {{ color:var(--ink); font-weight:500; }}
.pill {{ font-family:var(--disp); font-weight:700; font-size:.82rem; letter-spacing:.14em;
  padding:.18rem .7rem; min-width:4.6rem; text-align:center; }}
.pill.hit {{ background:rgba(76,158,106,.16); color:#7CC79A; border:1px solid rgba(76,158,106,.45); }}
.pill.miss {{ background:rgba(176,82,77,.14); color:#D98782; border:1px solid rgba(176,82,77,.45); }}
.proof {{ color:var(--muted); font-family:var(--mono); font-size:.72rem; margin-top:.7rem; }}
.proof a {{ color:var(--gold); }}

/* callout tiles (hype) */
.tile {{ background:var(--surface); border:1px solid var(--border); padding:.9rem 1.2rem; }}
.tile .lbl {{ color:var(--muted); font-size:.68rem; letter-spacing:.2em; text-transform:uppercase; }}
.tile .v {{ font-family:var(--disp); font-weight:800; font-size:1.9rem; text-transform:uppercase; }}
.tile .s {{ color:var(--muted); font-size:.75rem; font-family:var(--mono); }}

.note {{ color:var(--muted); font-size:.74rem; }}
.disclaimer {{ color:var(--muted); font-size:.76rem; margin-top:2.2rem;
  border-top:1px solid var(--border); padding-top:.8rem; }}

/* motion discipline */
@media (prefers-reduced-motion: reduce) {{
  .plate, .prob .pa, .prob .pb, .glyph svg {{ animation:none; transition:none; opacity:1; transform:none; }}
}}
/* small screens */
@media (max-width:700px) {{
  .mast .t {{ font-size:2.4rem; }}
  .chip {{ text-align:left; }}
  .chip .val {{ font-size:1rem; }}
  .tape {{ grid-template-columns:1fr; gap:.6rem; padding:1.2rem 1.2rem .8rem; }}
  .corner.b {{ flex-direction:row; text-align:left; }}
  .vs {{ display:none; }}
  .corner .nm {{ font-size:1.9rem; }}
  .briefs {{ grid-template-columns:1fr; }}
  .brief, .probwrap {{ padding-left:1.2rem; padding-right:1.2rem; }}
  .brief.r {{ border-right:none; border-bottom:1px solid var(--border); }}
  details.tape-d summary, details.tape-d div {{ padding-left:1.2rem; padding-right:1.2rem; }}
  .board {{ grid-template-columns:1fr; }}
  .row {{ grid-template-columns:1fr auto; }}
  .row .ep, .row .call {{ display:none; }}
}}
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
    d["wclass"] = dict(pd.read_csv("data/clean/weapon_classes.csv")[["bot", "weapon_class"]].values)
    return d


def glyph(cls: str, color: str, size: int = 46) -> str:
    """Original line-art weapon-class marks — our own SVG, no bot likenesses."""
    spin = cls in ("spinner-vertical", "spinner-horizontal")
    body = {
        "spinner-vertical": (f'<circle cx="23" cy="23" r="13" fill="none" stroke="{color}" stroke-width="2.4"/>'
                             f'<line x1="23" y1="6" x2="23" y2="40" stroke="{color}" stroke-width="2.4"/>'
                             f'<circle cx="23" cy="23" r="3" fill="{color}"/>'),
        "spinner-horizontal": (f'<line x1="4" y1="23" x2="42" y2="23" stroke="{color}" stroke-width="2.6"/>'
                               f'<rect x="2" y="20" width="7" height="6" fill="{color}"/>'
                               f'<rect x="37" y="20" width="7" height="6" fill="{color}"/>'
                               f'<circle cx="23" cy="23" r="4" fill="none" stroke="{color}" stroke-width="2"/>'),
        "hammer-saw": (f'<line x1="10" y1="36" x2="30" y2="12" stroke="{color}" stroke-width="2.6"/>'
                       f'<rect x="26" y="6" width="14" height="10" rx="1" fill="{color}"/>'),
        "flipper": (f'<path d="M6 34 L38 34 L38 20 Z" fill="none" stroke="{color}" stroke-width="2.4"/>'
                    f'<path d="M30 12 q6 -6 12 0" fill="none" stroke="{color}" stroke-width="2"/>'),
        "control-wedge": f'<path d="M6 35 L40 35 L40 22 Z" fill="{color}"/>',
        "crusher": (f'<path d="M10 12 L23 30 L36 12" fill="none" stroke="{color}" stroke-width="3"/>'
                    f'<line x1="23" y1="30" x2="23" y2="40" stroke="{color}" stroke-width="2.2"/>'),
        "multibot": (f'<rect x="6" y="18" width="14" height="14" fill="none" stroke="{color}" stroke-width="2.4"/>'
                     f'<rect x="26" y="13" width="11" height="11" fill="none" stroke="{color}" stroke-width="2.4"/>'),
    }.get(cls, f'<rect x="9" y="9" width="28" height="28" fill="none" stroke="{color}" stroke-width="2.4"/>')
    return (f'<span class="glyph{" spin" if spin else ""}"><svg width="{size}" height="{size}" '
            f'viewBox="0 0 46 46" xmlns="http://www.w3.org/2000/svg">{body}</svg></span>')


def plotly_layout(fig: go.Figure, **kw) -> go.Figure:
    fig.update_layout(
        template=None, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Archivo, sans-serif", color=INK, size=13),
        margin=dict(l=60, r=20, t=40, b=50), **kw)
    mono = dict(family="IBM Plex Mono, monospace", size=12)
    fig.update_xaxes(gridcolor=BORDER, zeroline=False, tickfont=mono)
    fig.update_yaxes(gridcolor=BORDER, zeroline=False, tickfont=mono, automargin=True)
    return fig


data = load()

# masthead — the record chip is the headline number
sc = data["scorecard"]
pre = sc[sc.preregistered] if sc is not None else None
chip = ""
if pre is not None and not pre.empty:
    chip = (f'<div class="chip"><div class="lbl">THE RECORD — FROZEN BEFORE AIR</div>'
            f'<div class="val">{int(pre.hit.sum())}/{len(pre)} <small>hits</small> · '
            f'{pre.log_loss.mean():.3f} <small>log-loss vs coin 0.693</small></div></div>')
st.markdown(f"""
<div class="mast">
  <div><div class="t">Pit Boss</div>
  <div class="tag">The data corner-man of the BattleBots Pro League.</div></div>
  {chip}
</div>
<div class="haz"></div>
""", unsafe_allow_html=True)
with st.expander("What is this?"):
    st.markdown(f"""<span class="note">Before every episode, Pit Boss briefs <b>both corners
of every fight</b> — what the public record says each team should watch for — built on
Bright Data scraping and a model that earns its credibility the hard way: its numbers are
frozen in git before air and scored in public after, hits and misses forever. Not betting
advice — advice to builders. Corner briefs are a public-data view only — the teams know
their bots; every number is computable from data/clean/.
<a href="https://github.com/Yazan-O/battlebots-pit-boss" style="color:{GOLD}">Verify the
record yourself</a>.</span>""", unsafe_allow_html=True)

tab_week, tab_record, tab_board, tab_hype = st.tabs(
    ["FIGHT CARD", "THE RECORD", "POWER BOARD", "HYPE CHECK"])

with tab_week:
    pred = data["pred"]
    if pred is None:
        st.subheader("No registered fight card yet")
    else:
        wk = int(pred.week.iloc[0])
        ep = int(pred.episode.iloc[0])
        tag = ("FROZEN IN GIT BEFORE AIR" if bool(pred.preregistered.iloc[0])
               else "RETROSPECTIVE BACKFILL — NOT PART OF THE RECORD")
        st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:baseline;'
                    f'flex-wrap:wrap;margin-top:.4rem"><h3 style="margin:0">Week {wk} — Episode {ep} '
                    f'· airs {pred.date.iloc[0]}</h3><span style="font-family:var(--mono);color:{MUT};'
                    f'font-size:.68rem;letter-spacing:.16em">{tag} · {pred.model_version.iloc[0]}</span></div>',
                    unsafe_allow_html=True)
        corner_briefs = {}
        corner_path = Path(f"data/corner/week_{ep}.json")
        if corner_path.exists():
            cj = json.loads(corner_path.read_text(encoding="utf-8"))
            for f in cj.get("fights", []):
                corner_briefs[frozenset((f["bot_a"], f["bot_b"]))] = {
                    side: d["lines"] for side, d in f["briefs"].items()}
        # default view shows the data clause of the top 3 brief lines, verbatim up to
        # the em-dash; the full untruncated brief lives in the drawer below each plate
        def leads(lines: list[str]) -> list[str]:
            keep = [ln for ln in lines if not ln.startswith("No Pro League")]
            return [ln.split(" — ")[0].rstrip(".") for ln in keep[:2]]

        for i, r in enumerate(pred.itertuples()):
            ca, cb = data["wclass"].get(r.bot_a, "other"), data["wclass"].get(r.bot_b, "other")
            pa = round(r.p_a * 100)
            brief = corner_briefs.get(frozenset((r.bot_a, r.bot_b)), {})
            bl_a = "".join(f"<li>{ln}</li>" for ln in leads(brief.get(r.bot_a, [])))
            bl_b = "".join(f"<li>{ln}</li>" for ln in leads(brief.get(r.bot_b, [])))
            briefs_html = ""
            if bl_a or bl_b:
                briefs_html = (f'<div class="briefs">'
                               f'<div class="brief r"><h4>{r.bot_a}&#8217;s corner</h4><ul>{bl_a}</ul></div>'
                               f'<div class="brief b"><h4>{r.bot_b}&#8217;s corner</h4><ul>{bl_b}</ul></div></div>')
            full_a = "".join(f"<li>{ln}</li>" for ln in brief.get(r.bot_a, []))
            full_b = "".join(f"<li>{ln}</li>" for ln in brief.get(r.bot_b, []))
            drawer = (f'<div class="briefs" style="border-top:none">'
                      f'<div class="brief r" style="padding-top:.2rem"><h4>{r.bot_a} — full brief</h4><ul>{full_a}</ul></div>'
                      f'<div class="brief b" style="padding-top:.2rem"><h4>{r.bot_b} — full brief</h4><ul>{full_b}</ul></div></div>'
                      if (full_a or full_b) else "")
            st.markdown(f"""
<div class="plate" style="animation-delay:{i * .12:.2f}s">
  <div class="tape">
    <div class="corner r">{glyph(ca, RED)}<div><div class="tag">RED CORNER</div>
      <div class="nm">{r.bot_a}</div><div class="cl">{ca.replace('-', ' ')}</div></div></div>
    <div class="vs">VS</div>
    <div class="corner b">{glyph(cb, BLUE)}<div><div class="tag">BLUE CORNER</div>
      <div class="nm">{r.bot_b}</div><div class="cl">{cb.replace('-', ' ')}</div></div></div>
  </div>
  <div class="probwrap">
    <div class="prob"><div class="pa" style="width:{pa}%"></div><div class="pb"></div></div>
    <div class="probnum"><span class="a">{pa}</span>
      <span class="mid">model lean — {"even" if pa == 50 else (r.bot_a if r.p_a > .5 else r.bot_b)}</span>
      <span class="b">{100 - pa}</span></div>
  </div>
  {briefs_html}
  <details class="tape-d"><summary>TALE OF THE TAPE</summary>
    <div>{r.why}</div>{drawer}</details>
</div>""", unsafe_allow_html=True)

        st.divider()
        st.subheader("SCOUT REPORT")
        bots_this_week = sorted(set(pred.bot_a) | set(pred.bot_b))
        c_sel, c_btn = st.columns([3, 1], vertical_alignment="bottom")
        pick = c_sel.selectbox("Live intel via the Bright Data MCP server", bots_this_week)
        if c_btn.button("Scout", type="primary", use_container_width=True):
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
    coin = math.log(2)
    # THE track record is pre-registered fights only — nothing else counts
    if pre is None or pre.empty:
        st.markdown(f"""
<div class="board"><div class="cell"><div class="lbl">Pre-registered fights scored</div>
<div class="big">0</div><div class="sub">the card is frozen — scores land after air</div></div>
<div class="cell"><div class="lbl">Hits</div><div class="big">—</div>
<div class="sub">nothing here is ever backfilled</div></div>
<div class="cell"><div class="lbl">Coin flip to beat</div><div class="big">0.693</div>
<div class="sub">log-loss of always saying 50/50</div></div></div>""", unsafe_allow_html=True)
    else:
        ll = pre.log_loss.mean()
        st.markdown(f"""
<div class="board">
<div class="cell"><div class="lbl">Hits — pre-registered only</div>
  <div class="big">{int(pre.hit.sum())}/{len(pre)}</div>
  <div class="sub">frozen in git before air, scored after</div></div>
<div class="cell"><div class="lbl">Running log-loss</div>
  <div class="big">{ll:.3f}</div><div class="sub">lower is better</div></div>
<div class="cell"><div class="lbl">Coin flip</div>
  <div class="big" style="color:{MUT};text-shadow:none">0.693</div>
  <div class="sub">{"beating the coin by " + format(coin - ll, ".3f") if ll < coin
                     else "behind the coin by " + format(ll - coin, ".3f")}</div></div>
</div>""", unsafe_allow_html=True)
        rows = ""
        for r in pre.itertuples():
            ok = int(r.hit) == 1
            rows += (f'<div class="row"><span class="ep">EP {int(r.episode)}</span>'
                     f'<span class="f">{r.fight}</span>'
                     f'<span class="call">model leaned <b>{r.predicted_winner}</b> {r.p_predicted:.0%} '
                     f'· won: <b>{r.actual_winner}</b></span>'
                     f'<span class="pill {"hit" if ok else "miss"}">{"HIT" if ok else "MISS"}</span></div>')
        st.markdown(rows, unsafe_allow_html=True)
        st.markdown('<div class="proof">Every row was committed to git before the episode aired — '
                    '<a href="https://github.com/Yazan-O/battlebots-pit-boss/commits/main/data/predictions">'
                    'verify the timestamps</a>.</div>', unsafe_allow_html=True)
        if len(pre) >= 3:
            sc2 = pre.reset_index()
            sc2["running"] = sc2.log_loss.expanding().mean()
            fig = go.Figure()
            fig.add_hline(y=coin, line=dict(color=MUT, dash="dash"),
                          annotation_text="coin flip", annotation_font_color=MUT)
            fig.add_trace(go.Scatter(x=sc2.index + 1, y=sc2.running, mode="lines+markers",
                                     line=dict(color=GOLD, width=2), showlegend=False))
            plotly_layout(fig, height=320,
                          xaxis_title="pre-registered fights (chronological)",
                          yaxis_title="running log-loss")
            fig.update_xaxes(dtick=1)
            st.plotly_chart(fig, width="stretch")
    retro = sc[~sc.preregistered] if sc is not None else None
    if retro is not None and not retro.empty:
        with st.expander("Retrospective validation — episode 1 aired before Pit Boss went "
                         "live; honest backfill, NOT part of the record"):
            rows = ""
            for r in retro.itertuples():
                ok = int(r.hit) == 1
                rows += (f'<div class="row" style="opacity:.75"><span class="ep">EP {int(r.episode)}</span>'
                         f'<span class="f">{r.fight}</span>'
                         f'<span class="call">model leaned <b>{r.predicted_winner}</b> {r.p_predicted:.0%} '
                         f'· won: <b>{r.actual_winner}</b></span>'
                         f'<span class="pill {"hit" if ok else "miss"}">{"HIT" if ok else "MISS"}</span></div>')
            st.markdown(rows, unsafe_allow_html=True)

with tab_board:
    s = data["strengths"].sort_values("elo")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=s.elo, y=s.bot, mode="markers",
        error_x=dict(type="data", symmetric=False,
                     array=s.ci_hi - s.elo, arrayminus=s.elo - s.ci_lo,
                     color="#3A4149", thickness=1.2),
        marker=dict(color=GOLD, size=9), showlegend=False,
        customdata=s[["career_w", "career_l", "weapon_class"]],
        hovertemplate="%{y}: %{x:.0f} · %{customdata[0]}-%{customdata[1]} · %{customdata[2]}<extra></extra>"))
    plotly_layout(fig, height=640, xaxis_title="Elo (90% bootstrap interval)",
                  title=dict(text="THE 24 PRO LEAGUE BOTS BY CURRENT ELO",
                             font=dict(family="Barlow Condensed", size=18)))
    st.plotly_chart(fig, width="stretch")
    with st.expander("How to read the intervals"):
        st.markdown('<div class="note">Parametric bootstrap (chronology-preserving) for bots '
                    'with 5+ recorded fights; bots below that show the population prior band — '
                    'an honest "could be anywhere in the field" instead of fake precision. New '
                    'bots start at the population mean (1500).</div>', unsafe_allow_html=True)
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
        marker=dict(color=GOLD, size=10, line=dict(color=BG, width=1)),
        hovertemplate="%{hovertext}: %{x} mentions, Elo %{y:.0f}<extra></extra>",
        hovertext=m.bot, showlegend=False))
    plotly_layout(fig, height=500,
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
        c1.markdown(f'<div class="tile"><div class="lbl">Most hyped vs rating</div>'
                    f'<div class="v">{o.bot}</div><div class="s">buzz #{int(o.buzz_rank)} · '
                    f'Elo #{int(o.elo_rank)}</div></div>', unsafe_allow_html=True)
    if len(under):
        u = under.iloc[0]
        c2.markdown(f'<div class="tile"><div class="lbl">Most slept-on</div>'
                    f'<div class="v">{u.bot}</div><div class="s">Elo {u.elo:.0f} · '
                    f'{int(u.mentions)} mentions</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="note" style="margin-top:.8rem">Buzz counts are exposure-biased: '
                'bots that fought in an aired episode get talked about. Read this as attention '
                'vs rating, not merit vs rating.</div>', unsafe_allow_html=True)

st.markdown('<div class="disclaimer">Pit Boss is an entertainment and data-engineering '
            'project — a public test of forecasting methodology on a pre-taped TV show. '
            'Not betting advice. Please don\'t gamble with it. Data: Bright Data (Web '
            'Unlocker, SERP API, Web Scraper API, MCP) + Wikipedia\'s open API. '
            '#BattleBotsDev</div>', unsafe_allow_html=True)
