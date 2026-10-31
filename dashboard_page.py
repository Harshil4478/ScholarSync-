"""Overview dashboard: KPIs, live map, charts, supply levels, activity feed."""
from datetime import datetime

import altair as alt
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from agent_core import get_proposals
from database import get_emergency_requests
from logistics import (
    LOW_STOCK_THRESHOLDS, STOCK_LABELS, get_centres_with_stock, get_dispatches, low_stock_alerts,
)
from ui_theme import (
    SEVERITY_COLOURS, STATUS_COLOURS, esc, feed_item, hero, kpi_card, live_badge, render,
    section, severity_pill, status_pill, supply_bar, time_ago,
)

SEVERITIES = ["Critical", "High", "Medium", "Low"]
TEXT = "#cbd5e1"


# ------------------------------------------------------------------ pure data logic (easy to test)
def compute_kpis(emergencies, centres, dispatches, proposals):
    active = [e for e in emergencies if e.get("status") != "Resolved"]
    dispatched_ids = {d["emergency_id"] for d in dispatches if d["status"] != "Cancelled"}
    covered = [e for e in active if e["id"] in dispatched_ids]
    needs_attention = [e for e in active if e.get("severity") in ("Critical", "High") and e["id"] not in dispatched_ids]
    severity_rank = {name: i for i, name in enumerate(SEVERITIES)}
    needs_attention.sort(key=lambda e: (severity_rank.get(e["severity"], 9), -int(e.get("people_affected") or 0)))
    return {
        "active": active,
        "active_count": len(active),
        "critical_count": sum(1 for e in active if e.get("severity") == "Critical"),
        "people_affected": sum(int(e.get("people_affected") or 0) for e in active),
        "resolved_count": sum(1 for e in emergencies if e.get("status") == "Resolved"),
        "active_centres": sum(1 for c in centres if c.get("status", "Active") == "Active"),
        "in_transit": sum(1 for d in dispatches if d["status"] in ("Approved", "On the way")),
        "pending_proposals": len(proposals),
        "coverage_pct": round(len(covered) / len(active) * 100) if active else 100,
        "needs_attention": needs_attention,
    }


# ------------------------------------------------------------------ page
def render_dashboard():
    emergencies = get_emergency_requests()
    centres = get_centres_with_stock()
    dispatches = get_dispatches()
    pending = get_proposals("Pending")
    k = compute_kpis(emergencies, centres, dispatches, pending)

    right = live_badge("LIVE · " + datetime.now().strftime("%d %b %Y, %H:%M"))
    render(hero("Emergency Operations Dashboard",
                "Real-time view of emergencies, relief centres, supplies and dispatches.", right))

    cards = [
        kpi_card("Active emergencies", k["active_count"], f"{k['resolved_count']} resolved so far", "#ef4444", "🚨"),
        kpi_card("Critical", k["critical_count"], "need immediate action", "#f97316", "🔥"),
        kpi_card("People affected", f"{k['people_affected']:,}", "in active emergencies", "#a78bfa", "👥"),
        kpi_card("Relief centres", k["active_centres"], f"{len(centres)} registered", "#22c55e", "🏥"),
        kpi_card("Dispatches in transit", k["in_transit"], "approved or on the way", "#38bdf8", "🚚"),
        kpi_card("Response coverage", f"{k['coverage_pct']}%", f"{k['pending_proposals']} proposal(s) awaiting approval", "#22d3ee", "🎯"),
    ]
    for column, card in zip(st.columns(6), cards):
        column.markdown(card, unsafe_allow_html=True)

    alerts = low_stock_alerts(centres)
    if alerts:
        names = sorted({a[0] for a in alerts})
        st.warning(f"⚠️ Low stock at {len(names)} centre(s): {', '.join(names[:4])}"
                   f"{' …' if len(names) > 4 else ''}. Check 'Supply levels' below.")

    map_col, side_col = st.columns([5, 3])
    with map_col:
        render(section("Live disaster map", "Bubble size = people affected · pulsing red = critical · 🏥 = relief centre"))
        _render_map(k["active"], centres)
    with side_col:
        render(section("Emergencies by severity"))
        _render_severity_chart(k["active"])
        render(section("Needs attention", "Critical / High with no dispatch yet"))
        _render_needs_attention(k["needs_attention"])

    left, right_col = st.columns([3, 2])
    with left:
        render(section("Supply levels by centre", "Red bars are below the low-stock limit"))
        _render_supply_levels(centres)
    with right_col:
        render(section("Recent dispatches"))
        _render_dispatches(dispatches)

    chart_col, feed_col = st.columns([3, 2])
    with chart_col:
        render(section("Emergency reports over time"))
        _render_timeline(emergencies)
    with feed_col:
        render(section("Latest emergency reports"))
        _render_feed(emergencies)


# ------------------------------------------------------------------ pieces
def _render_map(active, centres):
    points = [(e["latitude"], e["longitude"]) for e in active if e.get("latitude") is not None]
    points += [(c["latitude"], c["longitude"]) for c in centres]
    fmap = folium.Map(location=[16.0, 80.0], zoom_start=7, tiles="OpenStreetMap", control_scale=True)
    for e in active:
        if e.get("latitude") is None:
            continue
        colour = SEVERITY_COLOURS.get(e.get("severity"), "#94a3b8")
        popup = (f"<b>#{e['id']} {esc(e['location'])}</b><br>{esc(e['severity'])} · {esc(e['status'])}"
                 f"<br>{int(e['people_affected'])} people<br>Needs: {esc(e['supplies_needed'])}")
        radius = 7 + min(int(e.get("people_affected") or 0) ** 0.5, 30)
        if e.get("severity") == "Critical":
            icon = folium.DivIcon(
                icon_size=(34, 34), icon_anchor=(17, 17),
                html=('<style>@keyframes rrp{0%{transform:scale(.6);opacity:.9}100%{transform:scale(2.2);opacity:0}}</style>'
                      '<div style="position:relative;width:34px;height:34px">'
                      '<div style="position:absolute;inset:6px;border-radius:50%;background:#ef4444;'
                      'box-shadow:0 0 14px #ef4444"></div>'
                      '<div style="position:absolute;inset:6px;border-radius:50%;border:2px solid #ef4444;'
                      'animation:rrp 1.8s infinite"></div></div>'))
            folium.Marker([e["latitude"], e["longitude"]], icon=icon, tooltip=f"#{e['id']} {e['location']}",
                          popup=folium.Popup(popup, max_width=260)).add_to(fmap)
        else:
            folium.CircleMarker([e["latitude"], e["longitude"]], radius=radius, color=colour, weight=2,
                                fill=True, fill_color=colour, fill_opacity=.45,
                                tooltip=f"#{e['id']} {e['location']}",
                                popup=folium.Popup(popup, max_width=260)).add_to(fmap)
    for c in centres:
        closed = c.get("status", "Active") != "Active"
        colour = "#64748b" if closed else "#22c55e"
        popup = (f"<b>{esc(c['centre_name'])}</b> ({esc(c.get('status', 'Active'))})<br>{esc(c['address'])}"
                 f"<br>Water {c['water_litres']} L · Food {c['food_packets']} · Medical {c['medical_kits']}")
        icon = folium.DivIcon(
            icon_size=(30, 30), icon_anchor=(15, 15),
            html=(f'<div style="width:30px;height:30px;border-radius:9px;background:{colour};display:flex;'
                  'align-items:center;justify-content:center;font-size:16px;border:2px solid rgba(255,255,255,.85);'
                  f'box-shadow:0 4px 12px rgba(0,0,0,.5)">🏥</div>'))
        folium.Marker([c["latitude"], c["longitude"]], icon=icon, tooltip=c["centre_name"],
                      popup=folium.Popup(popup, max_width=260)).add_to(fmap)
    if points:
        fmap.fit_bounds([[min(p[0] for p in points), min(p[1] for p in points)],
                         [max(p[0] for p in points), max(p[1] for p in points)]], padding=(40, 40), max_zoom=11)
    st_folium(fmap, height=430, use_container_width=True, returned_objects=[], key="dash_map")


def _style_chart(chart):
    return (chart.properties(background="transparent")
            .configure_view(strokeWidth=0)
            .configure_axis(labelColor=TEXT, titleColor=TEXT, gridColor="#1e293b", domainColor="#334155", tickColor="#334155")
            .configure_legend(labelColor=TEXT, titleColor=TEXT, labelFontSize=12, symbolType="circle"))


def _render_severity_chart(active):
    counts = pd.DataFrame({"severity": SEVERITIES,
                           "count": [sum(1 for e in active if e.get("severity") == s) for s in SEVERITIES]})
    if counts["count"].sum() == 0:
        render('<div class="rr-card"><div class="rr-empty">No active emergencies. 🎉</div></div>')
        return
    chart = alt.Chart(counts[counts["count"] > 0]).mark_arc(innerRadius=58, outerRadius=100, stroke="#0b1220", strokeWidth=3).encode(
        theta=alt.Theta("count:Q"),
        color=alt.Color("severity:N", scale=alt.Scale(domain=SEVERITIES, range=[SEVERITY_COLOURS[s] for s in SEVERITIES]),
                        legend=alt.Legend(title=None, orient="right")),
        tooltip=["severity", "count"],
    ).properties(height=210)
    st.altair_chart(_style_chart(chart), use_container_width=True, theme=None)


def _render_needs_attention(items):
    if not items:
        render('<div class="rr-card"><div class="rr-empty">✅ Every Critical / High emergency has a dispatch.</div></div>')
        return
    rows = "".join(
        feed_item(f"#{e['id']} · {e['location']}",
                  f"{int(e['people_affected']):,} people · needs {esc(e['supplies_needed'])}",
                  SEVERITY_COLOURS.get(e["severity"], "#94a3b8"), severity_pill(e["severity"]))
        for e in items[:5])
    extra = f'<div class="rr-feed-meta">+ {len(items) - 5} more</div>' if len(items) > 5 else ""
    render(f'<div class="rr-card">{rows}{extra}</div>')


def _render_supply_levels(centres):
    if not centres:
        render('<div class="rr-card"><div class="rr-empty">No relief centres registered yet.</div></div>')
        return
    maxima = {key: max([int(c[key]) for c in centres] + [LOW_STOCK_THRESHOLDS[key] * 2]) for key in LOW_STOCK_THRESHOLDS}
    blocks = []
    for c in sorted(centres, key=lambda item: item["centre_name"].lower()):
        bars = "".join(
            supply_bar(STOCK_LABELS[key], int(c[key]), maxima[key], low=int(c[key]) < LOW_STOCK_THRESHOLDS[key])
            for key in LOW_STOCK_THRESHOLDS)
        blocks.append(f'<div class="rr-card"><div class="rr-supply-name"><b>{esc(c["centre_name"])}</b>'
                      f'{status_pill(c.get("status", "Active"))}</div>{bars}</div>')
    render("".join(blocks[:6]))
    if len(blocks) > 6:
        st.caption(f"Showing 6 of {len(blocks)} centres. See Relief Centres for the full list.")


def _render_dispatches(dispatches):
    if not dispatches:
        render('<div class="rr-card"><div class="rr-empty">No dispatches yet. Approve one from the Route Planner or AI agent.</div></div>')
        return
    rows = []
    for d in dispatches[:6]:
        sent = " · ".join(f"{STOCK_LABELS[k]} {d[k]}" for k in STOCK_LABELS if d[k])
        rows.append(feed_item(f"{d['centre_name']} → emergency #{d['emergency_id']}",
                              f"{esc(sent)} · {time_ago(d['created_at'])}",
                              STATUS_COLOURS.get(d["status"], "#94a3b8"), status_pill(d["status"])))
    render(f'<div class="rr-card">{"".join(rows)}</div>')


def _render_timeline(emergencies):
    if not emergencies:
        render('<div class="rr-card"><div class="rr-empty">No reports yet.</div></div>')
        return
    frame = pd.DataFrame(emergencies)
    frame["day"] = pd.to_datetime(frame["created_at"], errors="coerce").dt.date
    daily = frame.dropna(subset=["day"]).groupby("day").size().reset_index(name="reports")
    daily["day"] = pd.to_datetime(daily["day"])
    base = alt.Chart(daily).encode(x=alt.X("day:T", title=None), y=alt.Y("reports:Q", title="Reports", axis=alt.Axis(tickMinStep=1)),
                                   tooltip=[alt.Tooltip("day:T", title="Date"), "reports"])
    chart = (base.mark_area(line={"color": "#22d3ee"}, color="#22d3ee", opacity=0.22, interpolate="monotone")
             + base.mark_circle(color="#22d3ee", size=60)).properties(height=240)
    st.altair_chart(_style_chart(chart), use_container_width=True, theme=None)


def _render_feed(emergencies):
    if not emergencies:
        render('<div class="rr-card"><div class="rr-empty">No reports yet.</div></div>')
        return
    latest = sorted(emergencies, key=lambda e: str(e.get("created_at")), reverse=True)[:6]
    rows = "".join(
        feed_item(f"#{e['id']} · {e['location']}",
                  f"{int(e['people_affected']):,} people · {time_ago(e.get('created_at'))} · {status_pill(e['status'])}",
                  SEVERITY_COLOURS.get(e["severity"], "#94a3b8"), severity_pill(e["severity"]))
        for e in latest)
    render(f'<div class="rr-card">{rows}</div>')
