"""Map-first Route Planner page: mark places, edit data, auto-recommend routes, log dispatches."""
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from database import add_emergency_request, get_emergency_requests, update_request_status
from logistics import (
    DISPATCH_STATUSES, SEVERITIES, STOCK_LABELS, create_dispatch, delete_centre_and_stock,
    delete_emergency, dispatched_totals, get_centres_with_stock, get_dispatches,
    low_stock_alerts, set_initial_stock, update_dispatch_status, update_emergency,
)
from recommendation_service import SEVERITY_ORDER, parse_needs, recommend_centres, required_quantities
from relief_centres import CENTRE_STATUSES, add_relief_centre, update_relief_centre
from routing_service import forward_geocode, get_road_route, reverse_geocode

SEVERITY_COLOURS = {"Critical": "red", "High": "orange", "Medium": "blue", "Low": "green"}
SUPPLY_OPTIONS = ["Drinking Water", "Food", "Medical Kits", "Clothing", "Rescue Equipment", "Temporary Shelter"]
DEFAULT_CENTRE = [16.9, 82.2]


# Cached so Streamlit reruns do not hammer the free Nominatim / OSRM services.
@st.cache_data(ttl=600, show_spinner=False)
def _cached_route(a_lat, a_lon, b_lat, b_lon):
    return get_road_route(a_lat, a_lon, b_lat, b_lon)


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_reverse(lat, lon):
    return reverse_geocode(lat, lon)


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_forward(query):
    return forward_geocode(query)


def _route_fn(start_lat, start_lon, end_lat, end_lon):
    return _cached_route(round(start_lat, 5), round(start_lon, 5), round(end_lat, 5), round(end_lon, 5))


def _init_state():
    st.session_state.setdefault("rp_pending", None)
    st.session_state.setdefault("rp_pending_id", 0)
    st.session_state.setdefault("rp_last_click", None)


def _set_pending(lat, lon, label):
    st.session_state.rp_pending_id += 1
    st.session_state.rp_pending = {"lat": lat, "lon": lon, "label": label, "id": st.session_state.rp_pending_id}


def _fmt_supplies(quantities):
    return " · ".join(f"{STOCK_LABELS[k]} {v}" for k, v in quantities.items() if v)


def render_route_planner():
    _init_state()
    st.header("🗺️ Disaster Response & Route Planner")
    st.caption("Mark places on the map, edit data in the tables below, and the best centre and route update automatically.")

    emergencies = get_emergency_requests()
    centres = get_centres_with_stock()
    active = [
        e for e in emergencies
        if e.get("status") != "Resolved" and e.get("latitude") is not None and e.get("longitude") is not None
    ]
    active.sort(key=lambda e: (SEVERITY_ORDER.get(e.get("severity"), 9), -int(e.get("people_affected") or 0)))

    alerts = low_stock_alerts(centres)
    if alerts:
        with st.expander(f"⚠️ {len(alerts)} low-stock alert(s)"):
            for name, label, qty, threshold in alerts:
                st.write(f"**{name}**: {label} is {qty} (below {threshold})")

    selected, recommendations, already, fully_covered = None, [], {}, False
    if active:
        selected = st.selectbox(
            "Plan relief for emergency", active,
            format_func=lambda e: f"#{e['id']} · {e['location']} · {e['severity']} · {e['people_affected']} people",
        )
        already = dispatched_totals(selected["id"])
        fully_covered = bool(parse_needs(selected.get("supplies_needed"))) and not required_quantities(selected, already)
        if not fully_covered:
            recommendations = recommend_centres(selected, centres, top_n=3, route_fn=_route_fn, already_sent=already)
    else:
        st.info("No active emergencies yet. Use 'Add a place' on the right to mark one on the map.")

    map_col, panel_col = st.columns([2, 1])

    # ---------------- MAP ----------------
    with map_col:
        centre_point = DEFAULT_CENTRE
        if selected:
            centre_point = [selected["latitude"], selected["longitude"]]
        elif centres:
            centre_point = [centres[0]["latitude"], centres[0]["longitude"]]
        fmap = folium.Map(location=centre_point, zoom_start=8, tiles="OpenStreetMap")

        for e in active:
            folium.Marker(
                [e["latitude"], e["longitude"]],
                tooltip=f"Emergency #{e['id']} · {e['location']}",
                popup=(f"<b>EMERGENCY #{e['id']}</b><br>{e['location']}<br>Severity: {e['severity']}<br>"
                       f"People: {e['people_affected']}<br>Needs: {e['supplies_needed']}"),
                icon=folium.Icon(color=SEVERITY_COLOURS.get(e.get("severity"), "gray"), icon="warning-sign"),
            ).add_to(fmap)

        for c in centres:
            inactive = c.get("status", "Active") != "Active"
            folium.Marker(
                [c["latitude"], c["longitude"]],
                tooltip=f"{c['centre_name']} ({c.get('status', 'Active')})",
                popup=(f"<b>{c['centre_name']}</b> ({c.get('status', 'Active')})<br>{c['address']}<br>"
                       f"Water: {c['water_litres']} L · Food: {c['food_packets']} · Medical: {c['medical_kits']}"),
                icon=folium.Icon(color="gray" if inactive else "green", icon="home", prefix="glyphicon"),
            ).add_to(fmap)

        for rank, rec in enumerate(recommendations):
            best = rank == 0
            folium.PolyLine(
                rec["route"]["points"],
                color="#a855f7" if best else "#9ca3af",
                weight=6 if best else 3,
                opacity=0.9 if best else 0.7,
                dash_array=None if best else "8",
                tooltip=(f"{'BEST: ' if best else ''}{rec['centre']['centre_name']} · "
                         f"{rec['route']['distance_km']:.1f} km · {rec['route']['duration_min']:.0f} min"),
            ).add_to(fmap)

        pending = st.session_state.rp_pending
        if pending:
            folium.Marker([pending["lat"], pending["lon"]], tooltip="New place (not saved yet)",
                          icon=folium.Icon(color="purple", icon="star", prefix="glyphicon")).add_to(fmap)

        result = st_folium(fmap, height=560, width=None, returned_objects=["last_clicked"], key="rp_map")
        st.caption("🔴🟠🔵🟢 emergencies by severity · green house = relief centre (grey = Full/Closed) · "
                   "purple line = best route · grey dashed = alternatives")

        if st.session_state.get("rp_mode", "View only") != "View only" and result and result.get("last_clicked"):
            lat, lon = float(result["last_clicked"]["lat"]), float(result["last_clicked"]["lng"])
            key = (round(lat, 6), round(lon, 6))
            if key != st.session_state.rp_last_click:
                st.session_state.rp_last_click = key
                _set_pending(lat, lon, _cached_reverse(round(lat, 5), round(lon, 5)))
                st.rerun()

    # ---------------- RIGHT PANEL ----------------
    with panel_col:
        st.subheader("➕ Add a place")
        st.radio("Click the map to add…", ["View only", "Emergency", "Relief centre"], key="rp_mode", horizontal=True)
        search = st.text_input("…or search an address", key="rp_search", placeholder="e.g. Ongole, Andhra Pradesh")
        if st.button("📍 Find on map", key="rp_find"):
            found = _cached_forward(search.strip()) if search.strip() else None
            if found:
                _set_pending(found[0], found[1], search.strip())
                st.rerun()
            else:
                st.error("Could not find that place. Add town, district and state.")

        pending = st.session_state.rp_pending
        mode = st.session_state.get("rp_mode", "View only")
        if pending and mode == "View only":
            st.info("Choose Emergency or Relief centre above to save this pin.")
        elif pending:
            _render_add_form(pending, mode)

        st.divider()
        st.subheader("🚑 Best centres")
        if selected and already and any(already.values()):
            st.caption("Already dispatched: " + _fmt_supplies(already))
        if selected and fully_covered:
            st.success("Estimated needs are fully covered by earlier dispatches.")
        elif selected and not centres:
            st.warning("No relief centres registered yet.")
        elif selected and not recommendations:
            st.warning("No Active centre has the supplies this emergency still needs.")
        elif selected:
            _render_recommendations(selected, recommendations, already)

    # ---------------- TABLES ----------------
    st.divider()
    _render_dispatch_log()
    _render_centre_editor(centres)
    _render_emergency_editor(emergencies)


def _render_add_form(pending, mode):
    st.success(f"Pin: {pending['label']}")
    with st.form(f"rp_add_form_{pending['id']}"):
        if mode == "Emergency":
            location = st.text_input("Location", value=pending["label"])
            description = st.text_area("What happened?")
            people = st.number_input("People affected", min_value=1, value=100, step=10)
            severity = st.selectbox("Severity", SEVERITIES)
            supplies = st.multiselect("Required supplies", SUPPLY_OPTIONS, default=["Drinking Water", "Food"])
            if st.form_submit_button("Save emergency", type="primary"):
                if not location.strip() or not description.strip() or not supplies:
                    st.error("Add a location, description and at least one supply.")
                else:
                    add_emergency_request(location.strip(), description.strip(), int(people), severity,
                                          supplies, pending["lat"], pending["lon"])
                    st.session_state.rp_pending = None
                    st.rerun()
        else:
            name = st.text_input("Centre name")
            address = st.text_input("Address", value=pending["label"])
            capacity = st.number_input("Capacity (people)", min_value=1, value=200, step=10)
            water = st.number_input("Water (litres)", min_value=0, value=0, step=100)
            food = st.number_input("Food packets", min_value=0, value=0, step=50)
            medical = st.number_input("Medical kits", min_value=0, value=0, step=5)
            vehicles = st.number_input("Vehicles", min_value=0, value=0, step=1)
            if st.form_submit_button("Save relief centre", type="primary"):
                try:
                    centre_id = add_relief_centre(
                        centre_name=name, address=address, capacity=int(capacity),
                        vehicles=int(vehicles), latitude=pending["lat"], longitude=pending["lon"],
                    )
                    set_initial_stock(centre_id, water_litres=int(water), food_packets=int(food),
                                      medical_kits=int(medical))
                    st.session_state.rp_pending = None
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
    if st.button("Cancel pin", key=f"rp_cancel_{pending['id']}"):
        st.session_state.rp_pending = None
        st.rerun()


def _render_recommendations(emergency, recommendations, already):
    required = required_quantities(emergency, already)
    if required:
        st.caption("Still needed (estimate): " + _fmt_supplies(required))

    rows = [{
        "Rank": rank,
        "Centre": rec["centre"]["centre_name"],
        "Road km": round(rec["route"]["distance_km"], 1),
        "Drive min": round(rec["route"]["duration_min"]),
        "Supplies met": f"{rec['coverage'] * 100:.0f}%",
        "Route": "estimate" if rec["estimated"] else "road",
    } for rank, rec in enumerate(recommendations, start=1)]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    choice = st.radio(
        "Dispatch from", list(range(len(recommendations))),
        format_func=lambda i: f"{'⭐ ' if i == 0 else ''}{recommendations[i]['centre']['centre_name']}",
        key=f"rp_choice_{emergency['id']}",
    )
    rec = recommendations[choice]
    if rec["estimated"]:
        st.warning("Road routing was unavailable, so this uses an estimated straight-line route.")
    if rec["coverage"] < 1:
        st.warning("This centre cannot cover the full remaining need. Only available stock will be sent.")
    if not rec["capacity_ok"]:
        st.caption("Note: centre capacity is below the number of people affected.")
    if rec["plan"]:
        st.write("**Will be sent:** " + _fmt_supplies(rec["plan"]))

    if st.button("✅ Approve dispatch", type="primary", key=f"rp_approve_{emergency['id']}", disabled=not rec["plan"]):
        try:
            dispatch_id, sent = create_dispatch(
                emergency["id"], rec["centre"]["id"], rec["plan"],
                distance_km=rec["route"]["distance_km"], duration_min=rec["route"]["duration_min"],
            )
            st.success(f"Dispatch #{dispatch_id} approved from {rec['centre']['centre_name']}: {_fmt_supplies(sent)}")
            st.rerun()
        except ValueError as error:
            st.error(str(error))


def _render_dispatch_log():
    st.subheader("📋 Dispatch log")
    dispatches = get_dispatches()
    if not dispatches:
        st.info("No dispatches yet. Approve one from the 'Best centres' panel.")
        return
    columns = ["id", "emergency_id", "centre_name", "water_litres", "food_packets", "medical_kits",
               "distance_km", "duration_min", "status", "created_at"]
    original = pd.DataFrame(dispatches)[columns]
    edited = st.data_editor(
        original, hide_index=True, use_container_width=True, key="rp_dispatch_editor",
        disabled=[c for c in columns if c != "status"],
        column_config={"status": st.column_config.SelectboxColumn("Status", options=DISPATCH_STATUSES, required=True),
                       "distance_km": st.column_config.NumberColumn(format="%.1f"),
                       "duration_min": st.column_config.NumberColumn(format="%.0f")},
    )
    st.caption("Cancelling a dispatch returns its supplies to the centre.")
    if st.button("💾 Save dispatch status changes", key="rp_save_dispatches"):
        changed = 0
        try:
            for _, row in edited.iterrows():
                before = original[original["id"] == row["id"]].iloc[0]
                if row["status"] != before["status"]:
                    changed += int(update_dispatch_status(int(row["id"]), row["status"]))
        except ValueError as error:
            st.error(str(error))
            return
        st.success(f"{changed} dispatch status change(s) saved.")
        st.rerun()


def _render_centre_editor(centres):
    st.subheader("🏥 Relief centres (edit directly, then save)")
    if not centres:
        st.info("No relief centres yet.")
        return
    columns = ["id", "centre_name", "status", "capacity", "vehicles", "water_litres", "food_packets", "medical_kits"]
    original = pd.DataFrame(centres)[columns]
    table = original.copy()
    table["delete"] = False
    edited = st.data_editor(
        table, hide_index=True, use_container_width=True, key="rp_centre_editor",
        disabled=["id", "water_litres", "food_packets", "medical_kits"],
        column_config={
            "status": st.column_config.SelectboxColumn("Status", options=CENTRE_STATUSES, required=True),
            "delete": st.column_config.CheckboxColumn("Delete?"),
        },
    )
    st.caption("Supply columns are totals from Resource Inventory. Change stock there.")
    if st.button("💾 Save centre changes", key="rp_save_centres"):
        changed = deleted = 0
        try:
            for _, row in edited.iterrows():
                centre_id = int(row["id"])
                if row["delete"]:
                    deleted += int(delete_centre_and_stock(centre_id))
                    continue
                before = original[original["id"] == centre_id].iloc[0]
                fields = {c: row[c] for c in ("centre_name", "status", "capacity", "vehicles") if row[c] != before[c]}
                for key in ("capacity", "vehicles"):
                    if key in fields:
                        fields[key] = int(fields[key])
                if fields:
                    update_relief_centre(centre_id, **fields)
                    changed += 1
        except ValueError as error:
            st.error(str(error))
            return
        st.success(f"Saved: {changed} updated, {deleted} deleted.")
        st.rerun()


def _render_emergency_editor(emergencies):
    st.subheader("🚨 Emergencies (edit directly, then save)")
    if not emergencies:
        st.info("No emergencies yet.")
        return
    statuses = ["Pending", "In Progress", "Resolved"]
    columns = ["id", "location", "severity", "people_affected", "status"]
    original = pd.DataFrame(emergencies)[columns]
    table = original.copy()
    table["delete"] = False
    edited = st.data_editor(
        table, hide_index=True, use_container_width=True, key="rp_emergency_editor", disabled=["id"],
        column_config={
            "severity": st.column_config.SelectboxColumn("Severity", options=SEVERITIES, required=True),
            "status": st.column_config.SelectboxColumn("Status", options=statuses, required=True),
            "delete": st.column_config.CheckboxColumn("Delete?"),
        },
    )
    if st.button("💾 Save emergency changes", key="rp_save_emergencies"):
        changed = deleted = 0
        try:
            for _, row in edited.iterrows():
                emergency_id = int(row["id"])
                if row["delete"]:
                    deleted += int(delete_emergency(emergency_id))
                    continue
                before = original[original["id"] == emergency_id].iloc[0]
                if row["status"] != before["status"]:
                    update_request_status(emergency_id, row["status"])
                    changed += 1
                fields = {c: row[c] for c in ("location", "severity", "people_affected") if row[c] != before[c]}
                if fields:
                    update_emergency(emergency_id, **fields)
                    changed += 1
        except ValueError as error:
            st.error(str(error))
            return
        st.success(f"Saved: {changed} change(s), {deleted} deleted.")
        st.rerun()
