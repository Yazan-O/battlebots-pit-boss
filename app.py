"""Pit Boss — a public forecasting-methodology experiment on the BattleBots Pro League.

Reads everything from data/ in this repo; every data commit refreshes the site.
Visual system: BROADCAST (notes/DESIGN_DIRECTION.md) — red corner vs blue corner,
gold reserved for the brand and THE RECORD.
"""
from __future__ import annotations

import json
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
.mid {{ text-align:center; }}
.vs {{ font-family:var(--disp); font-weight:800; font-size:1.7rem; color:var(--ink);
  border-bottom:2px solid var(--gold); padding:0 .5rem .1rem; display:inline-block; }}
.leanto {{ font-family:var(--mono); font-size:.66rem; letter-spacing:.14em; margin-top:.45rem;
  color:var(--muted); }}
.leanto.r {{ color:var(--red); }} .leanto.b {{ color:var(--blue); }}
.glyph svg {{ display:block; transition:transform .6s cubic-bezier(.16,1,.3,1); }}
.plate:hover .glyph.spin svg {{ transform:rotate(180deg); }}
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
details.pm {{ background:var(--surface); border:1px solid var(--border); border-top:none; }}
details.pm summary::before {{ color:var(--miss); }}
details.pm summary {{ color:#D98782; }}
.pmlist {{ margin:0; padding:0; }}
.pmlist li {{ list-style:none; color:#B9C0C9; font-size:.82rem; line-height:1.55;
  padding-left:.95rem; position:relative; margin-bottom:.5rem; }}
.pmlist li::before {{ content:""; position:absolute; left:0; top:.55em; width:7px; height:2px;
  background:var(--miss); }}
.pmlist li.receipt {{ color:var(--muted); font-family:var(--mono); font-size:.72rem;
  line-height:1.5; margin-top:.7rem; padding-top:.7rem; border-top:1px solid var(--border); }}
.pmlist li.receipt::before {{ display:none; }}

/* callout tiles (hype) */
.tile {{ background:var(--surface); border:1px solid var(--border); padding:.9rem 1.2rem; }}
.tile .lbl {{ color:var(--muted); font-size:.68rem; letter-spacing:.2em; text-transform:uppercase; }}
.tile .v {{ font-family:var(--disp); font-weight:800; font-size:1.9rem; text-transform:uppercase; }}
.tile .s {{ color:var(--muted); font-size:.75rem; font-family:var(--mono); }}

.note {{ color:var(--muted); font-size:.74rem; }}
.disclaimer {{ color:var(--muted); font-size:.76rem; margin-top:2.2rem;
  border-top:1px solid var(--border); padding-top:.8rem; }}

/* roster cards — illustrated chassis flip cards, one per bot */
.cc-grid {{ display:flex; flex-wrap:wrap; gap:1rem; margin:1.2rem 0 1.6rem; }}
.cc-card {{ width:234px; }}
.cc-toggle {{ position:absolute; width:1px; height:1px; margin:-1px; padding:0; border:0;
  overflow:hidden; white-space:nowrap; opacity:0; clip:rect(0,0,0,0); clip-path:inset(50%); }}
.cc-scene {{ display:block; width:234px; height:428px; perspective:1200px; cursor:pointer;
  -webkit-tap-highlight-color:transparent; }}
.cc-scene--red {{ --accent:var(--red); }} .cc-scene--gold {{ --accent:var(--gold); }}
.cc-scene--blue {{ --accent:var(--blue); }}
.cc-toggle:focus-visible ~ .cc-scene {{ outline:2px solid var(--gold); outline-offset:3px; }}
.cc-card-inner {{ position:relative; width:100%; height:100%; transition:transform .3s ease;
  transform-style:preserve-3d; }}
.cc-toggle:checked ~ .cc-scene .cc-card-inner {{ transform:rotateY(180deg); }}
.cc-face {{ position:absolute; inset:0; display:flex; flex-direction:column;
  background:radial-gradient(circle at 28% 15%, rgba(255,255,255,.035), transparent 55%), var(--surface);
  border:1px solid var(--border); border-radius:2px; backface-visibility:hidden;
  -webkit-backface-visibility:hidden; overflow:hidden; box-sizing:border-box; }}
.cc-back {{ transform:rotateY(180deg); padding:14px 14px 10px; }}
.cc-art {{ position:relative; background:linear-gradient(180deg,var(--surface2),var(--surface) 85%);
  border-bottom:1px solid var(--border); }}
.cc-silhouette {{ width:100%; height:172px; display:block; }}
.cc-silhouette .tech {{ stroke:var(--border); stroke-width:1; fill:none; }}
.cc-silhouette .tech .cc-tagtext {{ stroke:none; fill:var(--muted); font-family:var(--mono);
  font-size:7px; letter-spacing:.04em; }}
.cc-silhouette .hull {{ fill:none; stroke:var(--accent); stroke-width:2.2; stroke-linejoin:round;
  stroke-linecap:round; }}
.cc-silhouette .seam {{ stroke:var(--accent); stroke-width:1; opacity:.45; }}
.cc-silhouette .rivet {{ fill:var(--accent); opacity:.7; }}
.cc-silhouette .wheel {{ fill:none; stroke:var(--muted); stroke-width:1.3; }}
.cc-silhouette .wheel .hub {{ fill:var(--muted); stroke:none; }}
.cc-silhouette .accent .hinge {{ fill:var(--accent); stroke:none; }}
.cc-silhouette .accent .arm {{ fill:none; stroke:var(--accent); stroke-width:2.4; stroke-linecap:round;
  stroke-linejoin:round; }}
.cc-silhouette .accent circle:not(.hinge):not(.rivet):not(.hub) {{ fill:none; stroke:var(--accent);
  stroke-width:2; }}
.cc-silhouette .accent .drum {{ fill:none; stroke:var(--accent); stroke-width:1.8; }}
.cc-silhouette .teeth {{ stroke:var(--accent); stroke-width:1.3; opacity:.85; }}
.cc-silhouette .hatch line, .cc-silhouette .hatch2 line {{ stroke:var(--accent); stroke-width:.9; opacity:.5; }}
.cc-silhouette .flame {{ stroke:var(--gold); stroke-width:1.2; stroke-linecap:round; opacity:.8; fill:none; }}
.cc-silhouette .wedge {{ fill:var(--accent); opacity:.85; }}
.cc-silhouette .piston {{ fill:none; stroke:var(--accent); stroke-width:1.6; }}
.cc-silhouette .piston-rod {{ stroke:var(--accent); stroke-width:1.2; }}
.cc-silhouette .skirt-bar {{ fill:none; stroke:var(--accent); stroke-width:2; }}
.cc-silhouette .skirt {{ fill:var(--surface); stroke:var(--accent); stroke-width:2; }}
.cc-silhouette .dim {{ stroke:var(--muted); stroke-width:.8; }}
.cc-silhouette .dim .cc-dimtext {{ stroke:none; fill:var(--muted); font-family:var(--mono);
  font-size:7.5px; letter-spacing:.04em; }}
.cc-class-tag {{ position:absolute; top:8px; right:10px; font-family:var(--mono); font-size:9.5px;
  letter-spacing:.07em; color:var(--accent); }}
.cc-front-mid {{ padding:12px 14px 6px; }}
.cc-name {{ margin:0; font-family:var(--disp); font-weight:800; letter-spacing:.01em;
  text-transform:uppercase; font-size:24px; line-height:1.05; color:var(--ink); }}
.cc-name--sm {{ font-size:18px; }}
.cc-team {{ margin:6px 0 0; font-size:12px; color:var(--muted); }}
.cc-front-bottom {{ margin-top:auto; border-top:1px solid var(--border); padding:10px 14px 8px;
  display:flex; align-items:flex-end; justify-content:space-between; gap:10px; }}
.cc-label {{ display:block; font-family:var(--mono); font-size:9px; letter-spacing:.08em;
  color:var(--muted); margin-bottom:5px; }}
.cc-value {{ font-family:var(--mono); font-size:14px; color:var(--ink); }}
.cc-pips {{ display:flex; gap:5px; }}
.cc-pip {{ width:12px; height:12px; border-radius:1px; border:1px solid var(--border); background:var(--surface2); }}
.cc-pip--win {{ background:var(--hit); border-color:var(--hit); }}
.cc-pip--loss {{ background:var(--miss); border-color:var(--miss); }}
.cc-pip--none {{ background:transparent; border-style:dashed; }}
.cc-hint {{ display:block; text-align:center; font-family:var(--mono); font-size:9px; letter-spacing:.08em;
  color:var(--muted); padding:0 0 8px; }}
.cc-back .cc-hint {{ margin-top:auto; padding-top:8px; }}
.cc-back-head {{ display:flex; align-items:center; justify-content:space-between; gap:8px;
  border-bottom:1px solid var(--border); padding-bottom:8px; margin-bottom:10px; }}
.cc-badge {{ font-family:var(--mono); font-size:8px; letter-spacing:.05em; padding:3px 5px;
  border:1px solid var(--border); white-space:nowrap; }}
.cc-badge--confirmed {{ color:var(--gold); border-color:var(--gold); }}
.cc-badge--new {{ color:var(--muted); }}
.cc-stats {{ margin:0 0 8px; display:flex; flex-direction:column; gap:7px; }}
.cc-stats > div {{ display:flex; flex-direction:column; gap:1px; }}
.cc-stats dt {{ font-family:var(--mono); font-size:9px; letter-spacing:.08em; color:var(--muted); }}
.cc-stats dd {{ margin:0; font-size:12px; line-height:1.3; color:var(--ink); }}
.cc-ci {{ font-family:var(--mono); font-size:10px; color:var(--muted); }}
.cc-log {{ width:100%; border-collapse:collapse; font-family:var(--mono); font-size:9.5px; }}
.cc-log th {{ text-align:left; color:var(--muted); font-weight:400; letter-spacing:.04em;
  border-bottom:1px solid var(--border); padding:3px; }}
.cc-log td {{ padding:3px; border-bottom:1px solid var(--border); color:var(--ink); }}
.cc-log .cc-w {{ color:var(--hit); }}
.cc-log .cc-l {{ color:var(--miss); }}

/* motion discipline */
@media (prefers-reduced-motion: reduce) {{
  .plate, .prob .pa, .prob .pb, .glyph svg {{ animation:none; transition:none; opacity:1; transform:none; }}
  .cc-card-inner {{ transition:none; }}
}}
/* small screens */
@media (max-width:700px) {{
  .mast .t {{ font-size:2.4rem; }}
  .chip {{ text-align:left; }}
  .chip .val {{ font-size:1rem; }}
  .tape {{ grid-template-columns:1fr; gap:.6rem; padding:1.2rem 1.2rem .8rem; }}
  .corner.b {{ flex-direction:row; text-align:left; }}
  .mid {{ order:3; }}
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
    d["weeks"] = pd.concat([pd.read_csv(w) for w in weeks]) if weeks else None
    d["season"] = pd.read_csv("data/clean/matches_2026.csv")
    d["robots"] = pd.read_csv("data/clean/robots.csv")
    d["hist"] = pd.read_parquet("data/clean/matches_hist.parquet")
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


# ---------------------------------------------------------------------------
# ROSTER CARDS — original illustrated chassis per bot, no photos/3D likenesses.
# Every drawing is authored from that bot's real weapon-spec text (data/clean/
# robots.csv weapon_raw); hull silhouette is original illustration (not spec
# data), weapon accent is grounded in real text via classify_accent() below —
# an auditable keyword table, first match wins, never invented.
# ---------------------------------------------------------------------------
_ACCENT_KEYWORDS_VERTICAL = [
    ("eggbeater", "articulating-drum", "articulating"),  # tuple: kw, type-if-2nd-kw, 2nd-kw
    ("flamethrower", "disc-flame", None), ("flame", "disc-flame", None),
    ("hydraulic", "disc-hydraulic-wedge", None), ("wedge", "disc-hydraulic-wedge", None),
    ("axe", "disc-axe", None), ("lift", "disc-lifter", None),
    ("2x", "twin-separate", None), ("twin", "twin-separate", None),
    ("drum", "single-drum", None),
]


def classify_accent(weapon_class: str, weapon_raw: str) -> str:
    """Deterministic, auditable: first literal keyword match in the real weapon_raw
    text wins. Never invents a weapon feature not present in the source text."""
    t = (weapon_raw or "").lower()
    if weapon_class == "hammer-saw":
        return "articulating-saw"
    if weapon_class == "spinner-horizontal":
        return "bar-tucked" if "undercutter" in t else "bar-exposed"
    if "eggbeater" in t:
        return "articulating-drum" if "articulating" in t else "eggbeater-drum"
    for kw, atype, _ in _ACCENT_KEYWORDS_VERTICAL[1:]:
        if kw in t:
            return atype
    return "generic-disc"


def hull_family(bot: str, weapon_class: str) -> str:
    """Stable per-bot hull pick (name hash, not random) — reproducible across runs."""
    if weapon_class == "hammer-saw":
        return "hex-tank"
    if weapon_class == "spinner-horizontal":
        return "wing"
    import hashlib as _hashlib
    hsh = int(_hashlib.md5(bot.encode()).hexdigest(), 16)
    return "diamond" if hsh % 2 == 0 else "zigzag"


_HULLS = {
    "diamond": dict(
        path="M20,86 L74,40 L118,50 L160,44 L212,86 L160,128 L118,122 L74,132 Z",
        seams=[(74, 40, 74, 132), (118, 50, 118, 122), (160, 44, 160, 128)],
        rivets=[(74, 46), (74, 126), (160, 50), (160, 122), (118, 56), (118, 116)],
        wheels=[(48, 52), (48, 120), (186, 52), (186, 120)], wheel_r=7,
        dim=(20, 212, 150, 163)),
    "zigzag": dict(
        path="M40,132 L40,88 L52,68 L64,80 L76,62 L88,78 L100,58 L112,78 L124,62 L136,80 L148,66 L156,88 L156,132 Z",
        seams=[(64, 80, 64, 132), (100, 58, 100, 132), (136, 80, 136, 132)],
        rivets=[(64, 86), (64, 126), (100, 64), (100, 126), (136, 86), (136, 126)],
        wheels=[], tank_wheels=[(42, 126), (134, 126)],
        dim=(40, 156, 150, 163)),
    "wing": dict(
        path="M24,98 L58,72 L120,68 L156,44 L192,72 L210,98 L192,124 L156,150 L120,130 L58,126 Z",
        seams=[(58, 72, 58, 126), (120, 68, 120, 130), (156, 44, 156, 150)],
        rivets=[(58, 80), (58, 118), (156, 54), (156, 140)],
        wheels=[(40, 98), (196, 98)], wheel_r=6,
        dim=(24, 210, 158, 167)),
    "hex-tank": dict(
        path="M40,100 L194,100 L206,112 L206,142 L194,154 L40,154 L28,142 L28,112 Z",
        seams=[(60, 100, 60, 154), (120, 100, 120, 154), (170, 100, 170, 154)],
        rivets=[(60, 106), (60, 148), (120, 106), (120, 148), (170, 106), (170, 148)],
        wheels=[], tank_wheels=[(34, 144), (174, 144)],
        dim=(28, 206, 160, 170)),
}
_ACCENT_CENTER = {"diamond": (150, 86), "zigzag": (167, 74), "wing": (117, 97), "hex-tank": (150, 40)}


def _hull_svg(h: dict) -> str:
    seams = " ".join(f"M{x1},{y1} L{x2},{y2}" for x1, y1, x2, y2 in h["seams"])
    rivets = "".join(f'<circle class="rivet" cx="{x}" cy="{y}" r="1.6"/>' for x, y in h["rivets"])
    wheels = "".join(
        f'<circle cx="{x}" cy="{y}" r="{h.get("wheel_r",7)}"/><circle cx="{x}" cy="{y}" r="2" class="hub"/>'
        for x, y in h.get("wheels", []))
    tank = ""
    for x, y in h.get("tank_wheels", []):
        tank += (f'<rect x="{x}" y="{y}" width="26" height="10" rx="1"/>'
                 f'<line x1="{x+4}" y1="{y}" x2="{x+10}" y2="{y+10}"/>'
                 f'<line x1="{x+12}" y1="{y}" x2="{x+18}" y2="{y+10}"/>'
                 f'<line x1="{x+20}" y1="{y}" x2="{x+26}" y2="{y+10}"/>')
    return (f'<g class="hull"><path d="{h["path"]}"/><path d="{seams}" class="seam"/>{rivets}</g>'
            f'<g class="wheel">{wheels}{tank}</g>')


def _dim_svg(h: dict, label: str) -> str:
    x1, x2, ly, ty = h["dim"]
    return (f'<g class="dim"><line x1="{x1}" y1="{ly}" x2="{x2}" y2="{ly}"/>'
            f'<line x1="{x1}" y1="{ly-4}" x2="{x1}" y2="{ly+4}"/>'
            f'<line x1="{x2}" y1="{ly-4}" x2="{x2}" y2="{ly+4}"/>'
            f'<text x="{(x1+x2)//2}" y="{ty}" text-anchor="middle" class="cc-dimtext">{label}</text></g>')


def _accent_svg(accent_type: str, cx: int, cy: int) -> str:
    """One drawing function per accent_type — grounded weapon shape, always
    clear of the top-left corner tag and within the 172-height viewBox."""
    if accent_type == "eggbeater-drum":
        return (f'<g class="accent">'
                f'<ellipse class="drum" cx="{cx}" cy="{cy}" rx="34" ry="12" transform="rotate(30 {cx} {cy})"/>'
                f'<ellipse class="drum" cx="{cx}" cy="{cy}" rx="34" ry="12" transform="rotate(-30 {cx} {cy})"/>'
                f'<circle cx="{cx}" cy="{cy}" r="6"/>'
                f'<g class="hatch">'
                f'<line x1="{cx-18}" y1="{cy-16}" x2="{cx-10}" y2="{cy-8}"/>'
                f'<line x1="{cx-8}" y1="{cy-20}" x2="{cx+2}" y2="{cy-10}"/>'
                f'<line x1="{cx+6}" y1="{cy-22}" x2="{cx+16}" y2="{cy-12}"/>'
                f'<line x1="{cx-18}" y1="{cy+16}" x2="{cx-10}" y2="{cy+8}"/>'
                f'<line x1="{cx-8}" y1="{cy+20}" x2="{cx+2}" y2="{cy+10}"/>'
                f'<line x1="{cx+6}" y1="{cy+22}" x2="{cx+16}" y2="{cy+12}"/>'
                f'</g></g>')
    if accent_type == "single-drum":
        return (f'<g class="accent"><ellipse class="drum" cx="{cx}" cy="{cy}" rx="30" ry="16"/>'
                f'<circle cx="{cx}" cy="{cy}" r="5"/>'
                f'<g class="hatch">'
                f'<line x1="{cx-24}" y1="{cy}" x2="{cx-14}" y2="{cy}"/>'
                f'<line x1="{cx-6}" y1="{cy}" x2="{cx+2}" y2="{cy}"/>'
                f'<line x1="{cx+10}" y1="{cy}" x2="{cx+20}" y2="{cy}"/>'
                f'</g></g>')
    if accent_type == "disc-lifter":
        return (f'<g class="accent"><circle cx="{cx}" cy="{cy}" r="30"/>'
                f'<g class="teeth">'
                f'<line x1="{cx}" y1="{cy-30}" x2="{cx}" y2="{cy+30}"/>'
                f'<line x1="{cx-30}" y1="{cy}" x2="{cx+30}" y2="{cy}"/>'
                f'<line x1="{cx-21}" y1="{cy-21}" x2="{cx+21}" y2="{cy+21}"/>'
                f'<line x1="{cx-21}" y1="{cy+21}" x2="{cx+21}" y2="{cy-21}"/>'
                f'<line x1="{cx-15}" y1="{cy-28}" x2="{cx-22}" y2="{cy-36}"/>'
                f'<line x1="{cx+15}" y1="{cy-28}" x2="{cx+22}" y2="{cy-36}"/></g>'
                f'<circle cx="{cx}" cy="{cy}" r="5" class="hinge"/>'
                f'<path d="M{cx-34},{cy+32} L{cx+24},{cy+44} L{cx+24},{cy+52} L{cx-34},{cy+40} Z" class="wedge"/>'
                f'<circle class="rivet" cx="{cx-32}" cy="{cy+34}" r="1.6"/></g>')
    if accent_type == "disc-axe":
        return (f'<g class="accent"><circle cx="{cx}" cy="{cy}" r="26"/>'
                f'<g class="teeth">'
                f'<line x1="{cx}" y1="{cy-26}" x2="{cx}" y2="{cy+26}"/>'
                f'<line x1="{cx-26}" y1="{cy}" x2="{cx+26}" y2="{cy}"/>'
                f'<line x1="{cx-18}" y1="{cy-18}" x2="{cx+18}" y2="{cy+18}"/>'
                f'<line x1="{cx-18}" y1="{cy+18}" x2="{cx+18}" y2="{cy-18}"/></g>'
                f'<path d="M{cx+22},{cy-10} Q{cx+44},{cy-14} {cx+40},{cy+6} Q{cx+36},{cy+16} {cx+20},{cy+8} Z" class="wedge"/>'
                f'</g>')
    if accent_type == "disc-hydraulic-wedge":
        return (f'<g class="accent"><circle cx="{cx}" cy="{cy}" r="26"/>'
                f'<g class="teeth">'
                f'<line x1="{cx}" y1="{cy-26}" x2="{cx}" y2="{cy+26}"/>'
                f'<line x1="{cx-26}" y1="{cy}" x2="{cx+26}" y2="{cy}"/>'
                f'<line x1="{cx-18}" y1="{cy-18}" x2="{cx+18}" y2="{cy+18}"/>'
                f'<line x1="{cx-18}" y1="{cy+18}" x2="{cx+18}" y2="{cy-18}"/></g>'
                f'<path d="M{cx-30},{cy+28} L{cx+18},{cy+38} L{cx+18},{cy+46} L{cx-30},{cy+36} Z" class="wedge"/>'
                f'<rect x="{cx-40}" y="{cy+22}" width="6" height="14" class="piston"/>'
                f'<line x1="{cx-37}" y1="{cy+22}" x2="{cx-37}" y2="{cy+10}" class="piston-rod"/></g>')
    if accent_type == "twin-separate":
        return (f'<g class="accent">'
                f'<circle cx="{cx-24}" cy="{cy-14}" r="16"/>'
                f'<g class="teeth"><line x1="{cx-24}" y1="{cy-30}" x2="{cx-24}" y2="{cy+2}"/>'
                f'<line x1="{cx-40}" y1="{cy-14}" x2="{cx-8}" y2="{cy-14}"/></g>'
                f'<circle cx="{cx-24}" cy="{cy-14}" r="3" class="hinge"/>'
                f'<circle cx="{cx+22}" cy="{cy+16}" r="16"/>'
                f'<g class="teeth"><line x1="{cx+22}" y1="{cy}" x2="{cx+22}" y2="{cy+32}"/>'
                f'<line x1="{cx+6}" y1="{cy+16}" x2="{cx+38}" y2="{cy+16}"/></g>'
                f'<circle cx="{cx+22}" cy="{cy+16}" r="3" class="hinge"/></g>')
    if accent_type == "disc-flame":
        return (f'<g class="accent"><circle cx="{cx}" cy="{cy}" r="28"/>'
                f'<g class="teeth">'
                f'<line x1="{cx}" y1="{cy-28}" x2="{cx}" y2="{cy+28}"/>'
                f'<line x1="{cx-28}" y1="{cy}" x2="{cx+28}" y2="{cy}"/>'
                f'<line x1="{cx-20}" y1="{cy-20}" x2="{cx+20}" y2="{cy+20}"/>'
                f'<line x1="{cx-20}" y1="{cy+20}" x2="{cx+20}" y2="{cy-20}"/></g>'
                f'<path d="M{cx+26},{cy-22} L{cx+34},{cy-32} M{cx+32},{cy-16} L{cx+42},{cy-24} '
                f'M{cx+36},{cy-6} L{cx+46},{cy-12}" class="flame"/></g>')
    if accent_type == "articulating-drum":
        ax, ay = cx - 46, cy + 34
        return (f'<g class="accent"><path d="M{ax},{ay} L{ax+18}, {ay-30} L{ax+40},{ay-50}" class="arm"/>'
                f'<circle cx="{ax+18}" cy="{ay-30}" r="5" class="hinge"/>'
                f'<ellipse class="drum" cx="{ax+40}" cy="{ay-50}" rx="22" ry="8" transform="rotate(25 {ax+40} {ay-50})"/>'
                f'<ellipse class="drum" cx="{ax+40}" cy="{ay-50}" rx="22" ry="8" transform="rotate(-25 {ax+40} {ay-50})"/>'
                f'<circle cx="{ax+40}" cy="{ay-50}" r="4"/></g>')
    if accent_type == "articulating-saw":
        return (f'<g class="accent"><path d="M{cx-63},{cy+60} L{cx-45},{cy+30} L{cx-17},{cy+10}" class="arm"/>'
                f'<circle cx="{cx-45}" cy="{cy+30}" r="5" class="hinge"/><circle cx="{cx-17}" cy="{cy+10}" r="5" class="hinge"/>'
                f'<circle cx="{cx}" cy="{cy}" r="15"/>'
                f'<g class="teeth"><line x1="{cx}" y1="{cy-15}" x2="{cx}" y2="{cy+15}"/>'
                f'<line x1="{cx-15}" y1="{cy}" x2="{cx+15}" y2="{cy}"/>'
                f'<line x1="{cx-11}" y1="{cy-11}" x2="{cx+11}" y2="{cy+11}"/>'
                f'<line x1="{cx-11}" y1="{cy+11}" x2="{cx+11}" y2="{cy-11}"/>'
                f'<line x1="{cx-7}" y1="{cy-14}" x2="{cx-13}" y2="{cy-20}"/>'
                f'<line x1="{cx+7}" y1="{cy-14}" x2="{cx+13}" y2="{cy-20}"/></g>'
                f'<path d="M{cx+16},{cy+12} L{cx+10},{cy+2} M{cx+22},{cy+8} L{cx+18},{cy-4} '
                f'M{cx+28},{cy+4} L{cx+26},{cy-8}" class="flame"/></g>')
    if accent_type == "bar-tucked":
        ticks = "".join(f'<line x1="{cx-39+i*12}" y1="{cy+8}" x2="{cx-39+i*12}" y2="{cy+17}"/>' for i in range(8))
        skirt_ticks = "".join(f'<line x1="{cx-37+i*17}" y1="{cy+20}" x2="{cx-37+i*17}" y2="{cy+32}"/>' for i in range(6))
        return (f'<g class="accent"><rect x="{cx-45}" y="{cy+8}" width="90" height="9" rx="4" class="skirt-bar"/>'
                f'<g class="hatch2">{ticks}</g>'
                f'<path d="M{cx-51},{cy+20} L{cx+51},{cy+20} L{cx+51},{cy+32} L{cx-51},{cy+32} Z" class="skirt"/>'
                f'{skirt_ticks}</g>')
    if accent_type == "bar-exposed":
        ticks = "".join(f'<line x1="{cx-47+i*11}" y1="{cy}" x2="{cx-47+i*11}" y2="{cy+11}"/>' for i in range(10))
        return (f'<g class="accent"><rect x="{cx-55}" y="{cy}" width="110" height="11" rx="5" class="skirt-bar"/>'
                f'<g class="hatch2">{ticks}</g>'
                f'<circle cx="{cx-55}" cy="{cy+5}" r="4" class="hinge"/>'
                f'<circle cx="{cx+55}" cy="{cy+5}" r="4" class="hinge"/></g>')
    # generic-disc
    return (f'<g class="accent"><circle cx="{cx}" cy="{cy}" r="30"/>'
            f'<g class="teeth">'
            f'<line x1="{cx}" y1="{cy-30}" x2="{cx}" y2="{cy+30}"/>'
            f'<line x1="{cx-30}" y1="{cy}" x2="{cx+30}" y2="{cy}"/>'
            f'<line x1="{cx-21}" y1="{cy-21}" x2="{cx+21}" y2="{cy+21}"/>'
            f'<line x1="{cx-21}" y1="{cy+21}" x2="{cx+21}" y2="{cy-21}"/></g>'
            f'<circle cx="{cx}" cy="{cy}" r="5" class="hinge"/></g>')


def chassis_svg(bot: str, weapon_class: str, weapon_raw: str, idx: int) -> str:
    accent_type = classify_accent(weapon_class, weapon_raw)
    hf = hull_family(bot, weapon_class)
    h = _HULLS[hf]
    cx, cy = _ACCENT_CENTER[hf]
    tag = f"BB&#8209;{idx:02d}"
    label = f'{weapon_class.upper()} &middot; {accent_type.upper().replace("-", " ")}'
    return (f'<svg viewBox="0 0 234 172" class="cc-silhouette" xmlns="http://www.w3.org/2000/svg" '
            f'role="img" aria-label="{bot}: original illustration authored from its public weapon '
            f'spec, not a photograph or 3D scan">'
            f'<g class="tech"><path d="M8,10 L8,20 M8,10 L18,10"/><path d="M226,10 L226,20 M226,10 L216,10"/>'
            f'<path d="M8,148 L8,138 M8,148 L18,148"/><path d="M226,148 L226,138 M226,148 L216,148"/>'
            f'<text x="12" y="24" class="cc-tagtext">{tag}</text></g>'
            f'{_hull_svg(h)}{_accent_svg(accent_type, cx, cy)}{_dim_svg(h, label)}</svg>')


def recent_fights(bot: str, hist: pd.DataFrame, season: pd.DataFrame, n: int = 4) -> list[dict]:
    """Real fight history for one bot, chronological, most recent last N."""
    rows = []
    for df in (hist, season):
        sub = df[(df.bot_a == bot) | (df.bot_b == bot)]
        for r in sub.itertuples():
            if not isinstance(r.date, str) or not r.date:
                continue  # a handful of historical rows have no recorded date — skip, don't fabricate
            opp = r.bot_b if r.bot_a == bot else r.bot_a
            method = r.method if isinstance(r.method, str) and r.method else "—"
            rows.append({"date": r.date, "opp": opp,
                        "result": "W" if r.winner == bot else "L", "method": method})
    rows.sort(key=lambda x: x["date"])
    return rows[-n:]


def _clean_field(s, prefix: str) -> str:
    if not isinstance(s, str) or not s:
        return "—"
    s = s.replace(prefix, "").strip()
    return s.split("(")[0].split("[")[0].strip() or "—"


def bot_card(r, idx: int, hist: pd.DataFrame, season: pd.DataFrame) -> str:
    """Flip card: front = illustrated chassis + weight/form, back = full stat sheet."""
    color_cls = {"hammer-saw": "gold", "spinner-horizontal": "blue"}.get(r.weapon_class, "red")
    svg = chassis_svg(r.bot, r.weapon_class, r.weapon_raw or "", idx)
    fights = recent_fights(r.bot, hist, season, n=4)
    padded = fights + [None] * (4 - len(fights))
    pips = "".join(
        f'<span class="cc-pip cc-pip--none" title="No prior record"></span>' if f is None else
        f'<span class="cc-pip cc-pip--{"win" if f["result"]=="W" else "loss"}" '
        f'title="{f["date"]} vs {f["opp"]} — {f["result"]} ({f["method"]})"></span>'
        for f in padded)
    badge = ('<span class="cc-badge cc-badge--new">LOW DATA</span>' if r.ci_kind == "prior-band"
             else '<span class="cc-badge cc-badge--confirmed">CONFIRMED RECORD</span>')
    log_rows = "".join(
        f'<tr><td>{f["date"]}</td><td>{f["opp"]}</td>'
        f'<td class="cc-{"w" if f["result"]=="W" else "l"}">{f["result"]}</td><td>{f["method"]}</td></tr>'
        for f in fights) or '<tr><td colspan="4" style="color:var(--muted)">No recorded fights</td></tr>'
    weight = _clean_field(r.weight, "> Weight ")
    weapon_disp = _clean_field(r.weapon_raw, "> Weapons ")
    team_disp = _clean_field(r.team, "> Team ")
    return f"""
<div class="cc-card">
  <input type="checkbox" id="cc-flip-{idx}" class="cc-toggle" aria-label="Flip {r.bot} card to show full stats">
  <label for="cc-flip-{idx}" class="cc-scene cc-scene--{color_cls}">
    <div class="cc-card-inner">
      <div class="cc-face cc-front">
        <div class="cc-art">{svg}<span class="cc-class-tag">{r.weapon_class.upper()}</span></div>
        <div class="cc-front-mid"><h3 class="cc-name">{r.bot.upper()}</h3>
          <p class="cc-team">{team_disp}</p></div>
        <div class="cc-front-bottom">
          <div class="cc-weight"><span class="cc-label">WEIGHT</span><span class="cc-value">{weight}</span></div>
          <div class="cc-form"><span class="cc-label">FORM</span><div class="cc-pips">{pips}</div></div>
        </div>
        <span class="cc-hint">TAP FOR STATS &#8635;</span>
      </div>
      <div class="cc-face cc-back">
        <div class="cc-back-head"><h3 class="cc-name cc-name--sm">{r.bot.upper()}</h3>{badge}</div>
        <dl class="cc-stats">
          <div><dt>ELO</dt><dd>{r.elo:.0f} <span class="cc-ci">(90% CI {r.ci_lo:.0f}&ndash;{r.ci_hi:.0f})</span></dd></div>
          <div><dt>WEAPON</dt><dd>{weapon_disp}</dd></div>
          <div><dt>RECORD</dt><dd>{r.career_w}&ndash;{r.career_l} <span class="cc-ci">career</span></dd></div>
        </dl>
        <table class="cc-log"><thead><tr><th>DATE</th><th>OPP</th><th>RES</th><th>MTHD</th></tr></thead>
          <tbody>{log_rows}</tbody></table>
        <span class="cc-hint">TAP FOR FRONT &#8635;</span>
      </div>
    </div>
  </label>
</div>"""


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
    chip = (f'<div class="chip"><div class="lbl">OUR READS, GRADED IN PUBLIC</div>'
            f'<div class="val">{int(pre.hit.sum())}/{len(pre)} <small>confirmed · frozen in git '
            f'before air</small></div></div>')
st.markdown(f"""
<div class="mast">
  <div><div class="t">Pit Boss</div>
  <div class="tag">The data corner-man of the BattleBots Pro League.</div></div>
  {chip}
</div>
<div class="haz"></div>
""", unsafe_allow_html=True)
with st.expander("What is this?"):
    st.markdown(f"""<span class="note">Before every episode, Pit Boss talks to <b>both corners
of every fight</b> — what the public record says each team should watch for, built on Bright
Data scraping. The briefs earn their credibility the hard way: every read is frozen in git
before air and graded in public after, right or wrong, forever. Not betting advice — advice
to builders. Corner briefs are a public-data view only — the teams know their bots; every
number is computable from data/clean/.
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
        tag = ("BRIEFED + FROZEN IN GIT BEFORE AIR" if bool(pred.preregistered.iloc[0])
               else "RETROSPECTIVE BACKFILL — NOT PART OF THE RECORD")
        st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:baseline;'
                    f'flex-wrap:wrap;margin-top:.4rem"><h3 style="margin:0">Week {wk} — Episode {ep} '
                    f'· airs {pred.date.iloc[0]}</h3><span style="font-family:var(--mono);color:{MUT};'
                    f'font-size:.68rem;letter-spacing:.16em">{tag}</span></div>',
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
            return [ln.split(" — ")[0].rstrip(".") for ln in keep[:3]]

        for i, r in enumerate(pred.itertuples()):
            ca, cb = data["wclass"].get(r.bot_a, "other"), data["wclass"].get(r.bot_b, "other")
            if r.p_a > 0.5:
                lean = f'<div class="leanto r">&#9666; LEANING {r.bot_a.upper()}</div>'
            elif r.p_a < 0.5:
                lean = f'<div class="leanto b">LEANING {r.bot_b.upper()} &#9656;</div>'
            else:
                lean = '<div class="leanto">DEAD EVEN</div>'
            brief = corner_briefs.get(frozenset((r.bot_a, r.bot_b)), {})
            bl_a = "".join(f"<li>{ln}</li>" for ln in leads(brief.get(r.bot_a, [])))
            bl_b = "".join(f"<li>{ln}</li>" for ln in leads(brief.get(r.bot_b, [])))
            briefs_html = ""
            if bl_a or bl_b:
                briefs_html = (f'<div class="briefs">'
                               f'<div class="brief r"><h4>{r.bot_a}&#8217;s corner — watch for</h4><ul>{bl_a}</ul></div>'
                               f'<div class="brief b"><h4>{r.bot_b}&#8217;s corner — watch for</h4><ul>{bl_b}</ul></div></div>')
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
    <div class="mid"><div class="vs">VS</div>{lean}</div>
    <div class="corner b">{glyph(cb, BLUE)}<div><div class="tag">BLUE CORNER</div>
      <div class="nm">{r.bot_b}</div><div class="cl">{cb.replace('-', ' ')}</div></div></div>
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
    # the accountable record: our pre-air reads, graded in public — nothing else counts
    import re as _re

    def post_mortem(r) -> str:
        """Data-grounded miss analysis: what happened, why the data-driven read broke,
        and the verbatim git receipt of what was frozen — no hindsight rewriting."""
        wk = data["weeks"]
        frozen = ""
        if wk is not None:
            m = wk[(wk.episode == r.episode) & (wk.fight == r.fight)]
            if not m.empty:
                frozen = m.iloc[0].why
        season = data["season"]
        res = season[(season.episode == r.episode) &
                     (season.winner == r.actual_winner)]
        method = ""
        if not res.empty and isinstance(res.iloc[0].method, str) and res.iloc[0].method:
            method = " by " + {"KO": "knockout", "JD": "judges' decision"}.get(
                res.iloc[0].method, res.iloc[0].method)
        loser = r.fight.replace(r.actual_winner, "").replace(" vs ", "").strip()
        lines = [f"<b>What happened:</b> {r.actual_winner} beat {loser}{method} — the corner "
                 f"we leaned away from took it."]
        if r.p_predicted < 0.60:
            lines.append("<b>Why it broke:</b> a thin lean, not a conviction — the public "
                         "record called this one close to even, and close fights break both ways.")
        lowdata = _re.search(r"(\w[\w' .-]*) has only \d+ recorded fight", frozen or "")
        if lowdata:
            lines.append(f"<b>The data gap:</b> {lowdata.group(1).strip()}'s public record "
                         "was nearly empty, so the read leaned on weapon-class history instead "
                         "of the bot itself — the first kind of read to break.")
        if r.p_predicted >= 0.60 and not lowdata:
            lines.append(f"<b>Why it broke:</b> the public record clearly favored "
                         f"{r.predicted_winner}; {r.actual_winner} beat the paper. The result "
                         "feeds straight back into the ratings — a miss the board learns from.")
        html = "".join(f"<li>{ln}</li>" for ln in lines)
        if frozen:
            html += (f'<li class="receipt">The exact line committed to git before air: '
                     f'&ldquo;{frozen}&rdquo;</li>')
        return html

    def grade_rows(df, dim: bool = False) -> str:
        rows = ""
        style = ' style="opacity:.75"' if dim else ""
        for r in df.itertuples():
            ok = int(r.hit) == 1
            rows += (f'<div class="row"{style}>'
                     f'<span class="ep">EP {int(r.episode)}</span>'
                     f'<span class="f">{r.fight}</span>'
                     f'<span class="call">our read: <b>{r.predicted_winner}</b> '
                     f'· result: <b>{r.actual_winner}</b></span>'
                     f'<span class="pill {"hit" if ok else "miss"}">'
                     f'{"&#10003; CONFIRMED" if ok else "&#10007; MISSED"}</span></div>')
            if not ok:
                rows += (f'<details class="tape-d pm"{style}><summary>WHY WE MISSED IT'
                         f'</summary><div><ul class="pmlist">{post_mortem(r)}</ul></div>'
                         f'</details>')
        return rows

    if pre is None or pre.empty:
        st.markdown("""
<div class="board"><div class="cell"><div class="lbl">Reads graded</div>
<div class="big">0</div><div class="sub">the briefs are frozen — grading lands after air</div></div>
<div class="cell"><div class="lbl">Confirmed</div><div class="big">—</div>
<div class="sub">nothing here is ever backfilled</div></div>
<div class="cell"><div class="lbl">The rule</div><div class="big">BEFORE AIR</div>
<div class="sub">a brief written after the fight doesn't count</div></div></div>""",
                    unsafe_allow_html=True)
    else:
        nxt = ""
        if data["pred"] is not None and bool(data["pred"].preregistered.iloc[0]):
            nxt = (f'<div class="cell"><div class="lbl">Next grading</div>'
                   f'<div class="big">{data["pred"].date.iloc[0][5:].replace("-", "/")}</div>'
                   f'<div class="sub">episode {int(data["pred"].episode.iloc[0])} — '
                   f'briefs already frozen</div></div>')
        st.markdown(f"""
<div class="board">
<div class="cell"><div class="lbl">Reads confirmed — pre-air only</div>
  <div class="big">{int(pre.hit.sum())}/{len(pre)}</div>
  <div class="sub">frozen in git before air, graded after</div></div>
<div class="cell"><div class="lbl">Episodes graded</div>
  <div class="big">{pre.episode.nunique()}</div>
  <div class="sub">misses stay on the board forever</div></div>
{nxt}</div>""", unsafe_allow_html=True)
        st.markdown(grade_rows(pre), unsafe_allow_html=True)
        st.markdown('<div class="proof">Every brief was committed to git before the episode '
                    'aired — <a href="https://github.com/Yazan-O/battlebots-pit-boss/commits/'
                    'main/data/predictions">verify the timestamps</a>.</div>',
                    unsafe_allow_html=True)
    retro = sc[~sc.preregistered] if sc is not None else None
    if retro is not None and not retro.empty:
        with st.expander("Test run on episode 1 — it aired before Pit Boss went live; "
                         "honest backfill, NOT part of the record"):
            st.markdown(grade_rows(retro, dim=True), unsafe_allow_html=True)

with tab_board:
    st.subheader("THE ROSTER")
    st.markdown('<div class="note" style="margin:-.4rem 0 1rem">Click a card for the full stat '
                'sheet. Every drawing is authored from that bot&#8217;s real public weapon spec '
                '(data/clean/robots.csv) — no bot photo or 3D likeness anywhere, by design.</div>',
                unsafe_allow_html=True)
    roster = (data["strengths"]
              .merge(data["robots"][["bot", "weapon_raw", "team", "weight"]], on="bot", how="left")
              .sort_values("bot"))
    cards = "".join(bot_card(r, i, data["hist"], data["season"])
                    for i, r in enumerate(roster.itertuples(), 1))
    st.markdown(f'<div class="cc-grid">{cards}</div>', unsafe_allow_html=True)

    st.divider()
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
