"""Visual theme and small HTML components for ReliefRoutes AI.

All user-typed text is escaped before it goes into HTML (locations and descriptions are
typed by the public, so they must never be trusted as markup).
"""
import html
from datetime import datetime

import streamlit as st

SEVERITY_COLOURS = {"Critical": "#ef4444", "High": "#f97316", "Medium": "#3b82f6", "Low": "#22c55e"}
STATUS_COLOURS = {
    "Pending": "#f59e0b", "In Progress": "#38bdf8", "Resolved": "#22c55e",
    "Approved": "#38bdf8", "On the way": "#a78bfa", "Delivered": "#22c55e", "Cancelled": "#94a3b8",
    "Active": "#22c55e", "Full": "#f59e0b", "Closed": "#94a3b8",
}
NAV_ICONS = {
    "Overview": "📊 Overview",
    "Live Weather": "🌦️ Live Weather",
    "Emergency Requests": "🚨 Emergency Requests",
    "Resource Inventory": "📦 Resource Inventory",
    "Relief Centre Management": "🏥 Relief Centres",
    "Route Planner": "🗺️ Route Planner",
    "AI Relief Agent": "🤖 AI Relief Agent",
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, .stApp, [class*="css"] { font-family: 'Inter', system-ui, sans-serif; }
.stApp {
  background:
    radial-gradient(1100px 560px at 8% -12%, rgba(34,211,238,.12), transparent 60%),
    radial-gradient(900px 480px at 100% 0%, rgba(244,63,94,.09), transparent 55%),
    #0b1220;
}
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1450px; }
h1, h2, h3 { letter-spacing: -0.02em; font-weight: 700; }
h2 { font-size: 1.55rem; }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0f1a30 0%, #0a1222 100%);
  border-right: 1px solid rgba(148,163,184,.12);
}
[data-testid="stSidebar"] .stRadio > label { display: none; }
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] { gap: .25rem; }
[data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] {
  padding: .6rem .8rem; border-radius: 12px; width: 100%;
  border: 1px solid transparent; transition: all .15s ease;
}
[data-testid="stSidebar"] .stRadio label[data-baseweb="radio"]:hover {
  background: rgba(148,163,184,.10);
}
[data-testid="stSidebar"] .stRadio label[data-baseweb="radio"]:has(input:checked) {
  background: linear-gradient(135deg, rgba(34,211,238,.18), rgba(59,130,246,.18));
  border-color: rgba(34,211,238,.45);
}
[data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] > div:first-child { display: none; }
.rr-brand { display:flex; align-items:center; gap:.7rem; padding:.4rem .2rem 1rem .2rem; }
.rr-brand-logo {
  width:42px; height:42px; border-radius:12px; display:flex; align-items:center; justify-content:center;
  font-size:1.35rem; background: linear-gradient(135deg,#ef4444,#f97316); box-shadow:0 8px 22px rgba(239,68,68,.35);
}
.rr-brand-name { font-weight:800; font-size:1.12rem; line-height:1.1; }
.rr-brand-tag { font-size:.72rem; color:#94a3b8; letter-spacing:.04em; text-transform:uppercase; }
.rr-sidebar-status {
  margin-top:1.2rem; padding:.85rem 1rem; border-radius:14px;
  background: rgba(148,163,184,.08); border:1px solid rgba(148,163,184,.14); font-size:.82rem; color:#cbd5e1;
}
.rr-sidebar-status b { color:#f1f5f9; }

/* ---------- hero ---------- */
.rr-hero {
  display:flex; justify-content:space-between; align-items:center; gap:1.5rem; flex-wrap:wrap;
  padding:1.6rem 1.8rem; border-radius:22px; margin-bottom:1.1rem;
  background: linear-gradient(120deg, rgba(34,211,238,.16), rgba(59,130,246,.12) 45%, rgba(239,68,68,.14));
  border:1px solid rgba(148,163,184,.20); box-shadow: 0 18px 50px rgba(2,6,23,.45);
}
.rr-hero-eyebrow { font-size:.74rem; letter-spacing:.14em; text-transform:uppercase; color:#67e8f9; font-weight:600; }
.rr-hero-title { font-size:2rem; font-weight:800; letter-spacing:-0.03em; margin:.15rem 0 .25rem 0; color:#f8fafc; }
.rr-hero-sub { color:#cbd5e1; font-size:.95rem; }
.rr-live {
  display:inline-flex; align-items:center; gap:.5rem; padding:.45rem .9rem; border-radius:999px;
  background: rgba(34,197,94,.14); border:1px solid rgba(34,197,94,.45); color:#86efac; font-weight:600; font-size:.8rem;
}
.rr-dot { width:9px; height:9px; border-radius:50%; background:#22c55e; box-shadow:0 0 0 0 rgba(34,197,94,.7); animation: rr-pulse 1.8s infinite; }
@keyframes rr-pulse { 0%{box-shadow:0 0 0 0 rgba(34,197,94,.6);} 70%{box-shadow:0 0 0 10px rgba(34,197,94,0);} 100%{box-shadow:0 0 0 0 rgba(34,197,94,0);} }

/* ---------- cards ---------- */
.rr-kpi {
  position:relative; overflow:hidden; padding:1.05rem 1.15rem; border-radius:18px; min-height:122px;
  background: linear-gradient(160deg, rgba(30,41,59,.85), rgba(15,23,42,.85));
  border:1px solid rgba(148,163,184,.16); transition: transform .15s ease, border-color .15s ease;
}
.rr-kpi:hover { transform: translateY(-3px); border-color: var(--accent); }
.rr-kpi::before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--accent); }
.rr-kpi-icon { position:absolute; right:.9rem; top:.7rem; font-size:1.5rem; opacity:.9; }
.rr-kpi-label { color:#94a3b8; font-size:.76rem; font-weight:600; text-transform:uppercase; letter-spacing:.07em; }
.rr-kpi-value { font-size:2.15rem; font-weight:800; color:#f8fafc; letter-spacing:-0.03em; margin-top:.25rem; line-height:1.1; }
.rr-kpi-sub { color:#94a3b8; font-size:.8rem; margin-top:.2rem; }
.rr-card {
  padding:1.1rem 1.2rem; border-radius:18px; margin-bottom:.75rem;
  background: linear-gradient(160deg, rgba(30,41,59,.70), rgba(15,23,42,.70));
  border:1px solid rgba(148,163,184,.16);
}
.rr-section { margin:1.2rem 0 .6rem 0; }
.rr-section-title { font-size:1.05rem; font-weight:700; color:#f1f5f9; }
.rr-section-sub { font-size:.8rem; color:#94a3b8; }

/* ---------- pills & feed ---------- */
.rr-pill {
  display:inline-block; padding:.12rem .6rem; border-radius:999px; font-size:.7rem; font-weight:700;
  letter-spacing:.04em; text-transform:uppercase; color:var(--c); background:color-mix(in srgb, var(--c) 16%, transparent);
  border:1px solid color-mix(in srgb, var(--c) 50%, transparent);
}
.rr-feed-item { display:flex; gap:.8rem; align-items:flex-start; padding:.75rem 0; border-bottom:1px solid rgba(148,163,184,.10); }
.rr-feed-item:last-child { border-bottom:none; }
.rr-feed-bar { width:4px; align-self:stretch; border-radius:4px; background:var(--c); }
.rr-feed-main { flex:1; min-width:0; }
.rr-feed-title { font-weight:600; color:#f1f5f9; font-size:.92rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.rr-feed-meta { color:#94a3b8; font-size:.78rem; margin-top:.1rem; }
.rr-empty { color:#94a3b8; font-size:.88rem; padding:.6rem 0; }

/* ---------- supply bars ---------- */
.rr-supply-name { display:flex; justify-content:space-between; align-items:center; margin-bottom:.45rem; }
.rr-supply-name b { color:#f1f5f9; font-size:.92rem; }
.rr-bar-row { display:flex; align-items:center; gap:.6rem; margin:.28rem 0; font-size:.76rem; color:#94a3b8; }
.rr-bar-label { width:78px; flex:none; }
.rr-bar-track { flex:1; height:8px; border-radius:99px; background:rgba(148,163,184,.16); overflow:hidden; }
.rr-bar-fill { height:100%; border-radius:99px; background:linear-gradient(90deg,#22d3ee,#3b82f6); }
.rr-bar-fill.low { background:linear-gradient(90deg,#f97316,#ef4444); }
.rr-bar-value { width:58px; text-align:right; flex:none; color:#e2e8f0; font-weight:600; }

/* ---------- widgets ---------- */
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"] {
  background: linear-gradient(135deg,#06b6d4,#3b82f6); border:none; color:white; font-weight:600;
  border-radius:12px; padding:.5rem 1.1rem; box-shadow:0 8px 20px rgba(59,130,246,.30); transition: all .15s ease;
}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button:hover { transform: translateY(-1px); filter: brightness(1.08); }
.stButton > button[kind="secondary"], .stFormSubmitButton > button[kind="secondary"] {
  border-radius:12px; border:1px solid rgba(148,163,184,.28); background: rgba(30,41,59,.6);
}
[data-testid="stMetric"] {
  background: linear-gradient(160deg, rgba(30,41,59,.75), rgba(15,23,42,.75));
  border:1px solid rgba(148,163,184,.16); border-radius:16px; padding:.8rem 1rem;
}
[data-testid="stExpander"] { border-radius:14px; border:1px solid rgba(148,163,184,.18); background: rgba(15,23,42,.55); }
[data-testid="stForm"] { border-radius:16px; border:1px solid rgba(148,163,184,.18); background: rgba(15,23,42,.45); }
.stTabs [data-baseweb="tab-list"] { gap:.4rem; }
.stTabs [data-baseweb="tab"] { border-radius:10px 10px 0 0; padding:.55rem 1rem; }
[data-testid="stDataFrame"], [data-testid="stDataEditor"] { border-radius:14px; overflow:hidden; border:1px solid rgba(148,163,184,.16); }
iframe[title="streamlit_folium.st_folium"] { border-radius:18px; border:1px solid rgba(148,163,184,.20); }
hr { border-color: rgba(148,163,184,.16); }
</style>
"""


def esc(value):
    return html.escape(str(value if value is not None else ""))


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def render(html_text):
    st.markdown(html_text, unsafe_allow_html=True)


def pill(text, colour):
    return f'<span class="rr-pill" style="--c:{colour}">{esc(text)}</span>'


def severity_pill(severity):
    return pill(severity, SEVERITY_COLOURS.get(severity, "#94a3b8"))


def status_pill(status):
    return pill(status, STATUS_COLOURS.get(status, "#94a3b8"))


def hero(title, subtitle, right_html=""):
    return (f'<div class="rr-hero"><div><div class="rr-hero-eyebrow">ReliefRoutes AI</div>'
            f'<div class="rr-hero-title">{esc(title)}</div><div class="rr-hero-sub">{esc(subtitle)}</div></div>'
            f'<div>{right_html}</div></div>')


def live_badge(text="LIVE"):
    return f'<span class="rr-live"><span class="rr-dot"></span>{esc(text)}</span>'


def kpi_card(label, value, sub="", colour="#22d3ee", icon=""):
    return (f'<div class="rr-kpi" style="--accent:{colour}"><div class="rr-kpi-icon">{icon}</div>'
            f'<div class="rr-kpi-label">{esc(label)}</div><div class="rr-kpi-value">{esc(value)}</div>'
            f'<div class="rr-kpi-sub">{esc(sub)}</div></div>')


def section(title, subtitle=""):
    sub = f'<div class="rr-section-sub">{esc(subtitle)}</div>' if subtitle else ""
    return f'<div class="rr-section"><div class="rr-section-title">{esc(title)}</div>{sub}</div>'


def supply_bar(label, value, max_value, low=False):
    pct = 0 if max_value <= 0 else max(0, min(100, round(value / max_value * 100)))
    cls = "rr-bar-fill low" if low else "rr-bar-fill"
    return (f'<div class="rr-bar-row"><div class="rr-bar-label">{esc(label)}</div>'
            f'<div class="rr-bar-track"><div class="{cls}" style="width:{pct}%"></div></div>'
            f'<div class="rr-bar-value">{esc(f"{int(value):,}")}</div></div>')


def feed_item(title, meta, colour, right_html=""):
    return (f'<div class="rr-feed-item" style="--c:{colour}"><div class="rr-feed-bar"></div>'
            f'<div class="rr-feed-main"><div class="rr-feed-title">{esc(title)}</div>'
            f'<div class="rr-feed-meta">{meta}</div></div><div>{right_html}</div></div>')


def time_ago(iso_text):
    try:
        delta = datetime.now() - datetime.fromisoformat(str(iso_text))
    except (TypeError, ValueError):
        return ""
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return f"{seconds // 86400} d ago"


def sidebar_brand():
    render('<div class="rr-brand"><div class="rr-brand-logo">🚨</div><div>'
           '<div class="rr-brand-name">ReliefRoutes AI</div>'
           '<div class="rr-brand-tag">Operations Center</div></div></div>')


def sidebar_status(active_emergencies, active_centres, pending_proposals):
    render('<div class="rr-sidebar-status">'
           f'<div>🚨 Active emergencies: <b>{int(active_emergencies)}</b></div>'
           f'<div>🏥 Active centres: <b>{int(active_centres)}</b></div>'
           f'<div>🤖 Awaiting approval: <b>{int(pending_proposals)}</b></div></div>')
