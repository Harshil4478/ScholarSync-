import streamlit as st

import pandas as pd

import requests

import folium

from ui_theme import inject_css

from dashboard_page import render_dashboard

from weather_service import get_coordinates, get_weather

from map_service import create_relief_map

from relief_centres import add_relief_centre, get_relief_centres, delete_relief_centre

from routing_service import reverse_geocode, forward_geocode, get_road_route, haversine_km

from logistics import (

    get_centres_with_stock, set_initial_stock, delete_centre_and_stock, low_stock_alerts

)

from streamlit_folium import st_folium

from database import (

    add_emergency_request,

    get_emergency_requests,

    get_request_count,

    update_request_status,

    add_inventory_item,

    get_inventory,

    update_inventory_quantity

)

st.set_page_config(

    page_title="ReliefRoutes AI",

    page_icon="🚨",

    layout="wide"

)

inject_css()

st.title("🚨 ReliefRoutes AI")

st.caption(

    "Autonomous Emergency Response & Relief Coordination"

)

st.sidebar.title("Operations Center")

page = st.sidebar.radio(

    "Navigation",

    [

        "Overview",

        "Live Weather",

        "Emergency Requests",

        "Resource Inventory",

        "Relief Centre Management",

        "Route Planner",

        "AI Relief Agent"

    ]

)
# ---------------- OVERVIEW ----------------
if page == "Overview":
    render_dashboard()

elif page == "Live Weather":

    st.header("🌦️ Live Weather Monitoring")

    st.write(

        "Retrieve current weather conditions "

        "and rainfall forecasts."

    )

    city = st.text_input(

        "Enter city or district",

        value="Nellore"

    )

    if st.button("Fetch Live Weather", type="primary"):

        if not city.strip():

            st.warning("Enter a location.")

        else:

            try:

                with st.spinner("Fetching live weather..."):

                    location = get_coordinates(city.strip())

                    weather = get_weather(

                        location["latitude"],

                        location["longitude"]

                    )

                current = weather["current"]

                st.success(

                    f"Weather retrieved for "

                    f"{location['name']}, "

                    f"{location['country']}"

                )

                st.caption(

                    f"Data time: {current['time']}"

                )

                col1, col2, col3, col4 = st.columns(4)

                col1.metric(

                    "Temperature",

                    f"{current['temperature_2m']} °C"

                )

                col2.metric(

                    "Humidity",

                    f"{current['relative_humidity_2m']}%"

                )

                col3.metric(

                    "Rainfall",

                    f"{current['precipitation']} mm"

                )

                col4.metric(

                    "Wind Speed",

                    f"{current['wind_speed_10m']} km/h"

                )

                hourly = weather["hourly"]

                forecast = pd.DataFrame({

                    "Time": hourly["time"][:12],

                    "Temperature (°C)": hourly[

                        "temperature_2m"

                    ][:12],

                    "Rainfall (mm)": hourly[

                        "precipitation"

                    ][:12],

                    "Rain Probability (%)": hourly[

                        "precipitation_probability"

                    ][:12]

                })

                st.subheader("Rainfall Forecast")

                st.dataframe(

                    forecast,

                    use_container_width=True

                )

                rainfall_total = sum(

                    value or 0

                    for value in hourly["precipitation"][:6]

                )

                st.subheader("Weather Risk Indicator")

                if rainfall_total >= 30:

                    st.error(

                        "High rainfall watch: "

                        "Elevated rainfall forecast."

                    )

                elif rainfall_total >= 10:

                    st.warning(

                        "Moderate rainfall watch."

                    )

                else:

                    st.success(

                        "No elevated rainfall indication "

                        "from the six-hour forecast."

                    )

                st.caption(

                    "Source: Open-Meteo. Rainfall indicators "

                    "do not confirm flooding or road safety."

                )

            except requests.RequestException as error:

                st.error(f"Weather API error: {error}")

            except (ValueError, KeyError) as error:

                st.error(f"Data error: {error}")
# ---------------- EMERGENCY REQUESTS ----------------
elif page == "Emergency Requests":

    st.header("🚨 Emergency Request Management")

    st.write("Select the affected point on the map. The location name and GPS coordinates will be detected automatically.")

    st.subheader("📍 Select Affected Location")

    if "emergency_latitude" not in st.session_state:

        st.session_state.emergency_latitude = None

    if "emergency_longitude" not in st.session_state:

        st.session_state.emergency_longitude = None

    if "emergency_location_text" not in st.session_state:

        st.session_state.emergency_location_text = ""

    if "emergency_last_click" not in st.session_state:

        st.session_state.emergency_last_click = None
# Reset requested after a successful save: done here, before the text box exists.
    if st.session_state.get("emergency_reset"):

        st.session_state.emergency_latitude = None

        st.session_state.emergency_longitude = None

        st.session_state.emergency_location_text = ""

        st.session_state.emergency_last_click = None

        st.session_state.emergency_reset = False

    emergency_picker = folium.Map(location=[16.9, 82.2], zoom_start=8, tiles="OpenStreetMap")

    for existing in get_emergency_requests():

        if existing.get("latitude") is not None and existing.get("longitude") is not None:

            colour = {"Critical": "red", "High": "orange", "Medium": "blue", "Low": "green"}.get(existing.get("severity"), "gray")

            folium.Marker(

                [existing["latitude"], existing["longitude"]],

                tooltip=f"Emergency #{existing['id']} · {existing['location']}",

                popup=f"<b>{existing['severity']} emergency</b><br>{existing['location']}<br>Status: {existing['status']}",

                icon=folium.Icon(color=colour, icon="warning-sign")

            ).add_to(emergency_picker)

    if st.session_state.emergency_latitude is not None:

        folium.Marker(

            [st.session_state.emergency_latitude, st.session_state.emergency_longitude],

            tooltip="New emergency location",

            icon=folium.Icon(color="red", icon="plus-sign")

        ).add_to(emergency_picker)

    map_result = st_folium(

        emergency_picker, height=430, width=None,

        returned_objects=["last_clicked"], key="emergency_location_picker_v2"

    )

    if map_result and map_result.get("last_clicked"):

        point = map_result["last_clicked"]

        lat, lon = float(point["lat"]), float(point["lng"])

        click_key = (round(lat, 6), round(lon, 6))

        if click_key != st.session_state.emergency_last_click:

            st.session_state.emergency_last_click = click_key

            st.session_state.emergency_latitude = lat

            st.session_state.emergency_longitude = lon

            st.session_state.emergency_location_text = reverse_geocode(lat, lon)

            st.rerun()

    latitude = st.session_state.emergency_latitude

    longitude = st.session_state.emergency_longitude

    if latitude is not None and longitude is not None:

        st.success(f"Selected: {st.session_state.emergency_location_text}")

        c1, c2 = st.columns(2)

        c1.metric("Latitude", f"{latitude:.6f}")

        c2.metric("Longitude", f"{longitude:.6f}")

    else:

        st.info("Click the map to drop a red emergency marker and automatically identify the area.")

    location = st.text_input(

        "Affected Location / Area", key="emergency_location_text",

        placeholder="e.g. Ongole, Andhra Pradesh"

    )

    if st.button("📍 Find typed location on map", key="find_emergency_location"):

        found = forward_geocode(location)

        if found:

            st.session_state.emergency_latitude = found[0]

            st.session_state.emergency_longitude = found[1]

            st.session_state.emergency_last_click = (round(found[0], 6), round(found[1], 6))

            st.success(f"Map pin placed for: {found[2]}")

            st.rerun()

        else:

            st.error("Could not find that place. Try adding the town, district and state.")

    with st.form("emergency_form"):

        description = st.text_area("Describe the emergency")

        people = st.number_input("Number of people affected", min_value=1, value=1, step=1)

        severity = st.selectbox("Emergency Severity", ["Critical", "High", "Medium", "Low"])

        supplies = st.multiselect("Required Supplies", [

            "Drinking Water", "Food", "Medical Kits", "Clothing",

            "Rescue Equipment", "Temporary Shelter"

        ])

        submitted = st.form_submit_button("Register Emergency Request", type="primary")

        if submitted:

            if latitude is None or longitude is None:

                st.error("Select the affected point on the map first.")

            elif not location.strip() or not description.strip():

                st.error("Location and description are required.")

            elif not supplies:

                st.error("Select at least one required supply.")

            else:

                request_id = add_emergency_request(

                    location.strip(), description.strip(), int(people), severity,

                    supplies, float(latitude), float(longitude)

                )

                st.success(f"Emergency request #{request_id} registered and pinned on the disaster map!")

                st.session_state.emergency_reset = True

                st.rerun()

    st.divider()

    st.subheader("Registered Emergency Requests")

    records = get_emergency_requests()

    if records:

        for item in records:

            with st.expander(f"#{item['id']} | {item['location']} | {item['severity']} | {item['status']}"):

                st.write("**Description:**", item["description"])

                st.write("**People affected:**", item["people_affected"])

                st.write("**Required supplies:**", item["supplies_needed"])

                st.write("**Reported at:**", item["created_at"])

                st.write("**Coordinates:**", item["latitude"], item["longitude"])

                status_options = ["Pending", "In Progress", "Resolved"]

                current_status = item.get("status", "Pending")

                new_status = st.selectbox("Update request status", status_options,

                    index=status_options.index(current_status) if current_status in status_options else 0,

                    key=f"status_{item['id']}")

                if st.button("Update Status", key=f"update_{item['id']}"):

                    update_request_status(item["id"], new_status)

                    st.success("Status updated!")

                    st.rerun()

    else:

        st.info("No emergency reports yet. Register your first request above.")
# ---------------- OTHER MODULES ----------------
elif page == "Resource Inventory":

    st.header("📦 Relief Resource Inventory")

    st.write("Register and track available relief supplies.")

    with st.form("inventory_form"):

        name = st.text_input("Resource Name")

        category = st.selectbox(

            "Category",

            [

                "Food",

                "Water",

                "Medical",

                "Clothing",

                "Rescue Equipment",

                "Vehicle",

                "Other"

            ]

        )

        quantity = st.number_input(

            "Available Quantity",

            min_value=0,

            step=1

        )

        unit = st.selectbox(

            "Unit",

            ["Packets", "Litres", "Kits", "Pieces", "Vehicles"]

        )

        centre_choice = st.selectbox(

            "Relief centre",

            [None] + get_centres_with_stock(),

            format_func=lambda c: ("Central warehouse / not linked to a centre" if c is None

                                   else f"#{c['id']} · {c['centre_name']}"),

        )

        location = st.text_input("Warehouse name (only if not linked to a centre)")

        st.caption("Use category Water, Food or Medical so the Route Planner counts this stock.")

        submitted = st.form_submit_button(

            "Add Resource",

            type="primary"

        )

        if submitted:

            try:

                add_inventory_item(

                    name,

                    category,

                    int(quantity),

                    unit,

                    centre_choice["centre_name"] if centre_choice else location,

                    centre_id=centre_choice["id"] if centre_choice else None,

                )

                st.success("Resource added successfully!")

                st.rerun()

            except ValueError as error:

                st.error(str(error))

    st.divider()

    st.subheader("Available Resources")

    inventory = get_inventory()

    if inventory:

        st.dataframe(

            pd.DataFrame(inventory),

            use_container_width=True

        )

        st.subheader("Update Stock")

        selected = st.selectbox(

            "Select resource",

            inventory,

            format_func=lambda item: (

                f"#{item['id']} - {item['resource_name']} "

                f"({item['location']})"

            )

        )

        new_quantity = st.number_input(

            "New Quantity",

            min_value=0,

            value=int(selected["quantity"]),

            key=f"quantity_{selected['id']}"

        )

        if st.button("Update Quantity"):

            update_inventory_quantity(

                selected["id"],

                int(new_quantity)

            )

            st.success("Inventory updated!")

            st.rerun()

    else:

        st.info("No resources registered yet.")

elif page == "Relief Centre Management":

    st.header("🏥 Relief Centre Management")

    st.write(

        "Register verified relief centres, record their GPS locations, "

        "and track the supplies and capacity available at each centre."

    )

    st.subheader("📍 Select Relief Centre Location")

    if "centre_latitude" not in st.session_state:

        st.session_state.centre_latitude = None

    if "centre_longitude" not in st.session_state:

        st.session_state.centre_longitude = None

    centre_picker = folium.Map(

        location=[16.9, 82.2],

        zoom_start=8,

        tiles="OpenStreetMap"

    )

    if st.session_state.centre_latitude is not None and st.session_state.centre_longitude is not None:

        folium.Marker(

            [st.session_state.centre_latitude, st.session_state.centre_longitude],

            tooltip="Selected relief centre",

            icon=folium.Icon(color="green", icon="home", prefix="glyphicon")

        ).add_to(centre_picker)

    centre_map_result = st_folium(

        centre_picker,

        height=350,

        width=None,

        returned_objects=["last_clicked"],

        key="relief_centre_location_picker"

    )

    if centre_map_result and centre_map_result.get("last_clicked"):

        selected_centre_point = centre_map_result["last_clicked"]

        st.session_state.centre_latitude = float(selected_centre_point["lat"])

        st.session_state.centre_longitude = float(selected_centre_point["lng"])

    if (st.session_state.centre_latitude is not None

            and st.session_state.centre_longitude is not None):

        st.success("Relief centre coordinates selected.")

        coord_col1, coord_col2 = st.columns(2)

        coord_col1.metric("Latitude", f"{st.session_state.centre_latitude:.6f}")

        coord_col2.metric("Longitude", f"{st.session_state.centre_longitude:.6f}")

    else:

        st.info("Click the map to select the exact relief centre location before registering it.")

    centre_name = st.text_input(

        "Relief Centre Name", key="centre_name_input",

        placeholder="e.g. Ongole Government School Relief Centre"

    )

    centre_address = st.text_input(

        "Full Address / Area", key="centre_address_input",

        placeholder="Street, area, district, state"

    )

    if st.button("📍 Find centre address on map", key="find_centre_address"):

        found_centre = forward_geocode(centre_address)

        if found_centre:

            st.session_state.centre_latitude = found_centre[0]

            st.session_state.centre_longitude = found_centre[1]

            st.success(f"Centre pin placed for: {found_centre[2]}")

            st.rerun()

        else:

            st.error("Could not find that address. Try a more specific address with district and state.")

    with st.form("relief_centre_form"):

        contact_person = st.text_input("Centre Contact Person")

        contact_phone = st.text_input("Contact Phone Number")

        capacity = st.number_input("Maximum People Capacity", min_value=1, value=100, step=10)

        st.markdown("**Available supplies at this centre**")

        supply_col1, supply_col2 = st.columns(2)

        with supply_col1:

            water_litres = st.number_input("Drinking Water (litres)", min_value=0, value=0, step=10)

            food_packets = st.number_input("Food Packets", min_value=0, value=0, step=10)

        with supply_col2:

            medical_kits = st.number_input("Medical Kits", min_value=0, value=0, step=1)

            vehicles = st.number_input("Available Vehicles", min_value=0, value=0, step=1)

        centre_submitted = st.form_submit_button("Register Relief Centre", type="primary")

        if centre_submitted:

            if not centre_name.strip() or not centre_address.strip():

                st.error("Centre name and full address are required.")

            elif st.session_state.centre_latitude is None or st.session_state.centre_longitude is None:

                st.error("Please click the map and select this centre's GPS location first.")

            else:

                try:

                    centre_id = add_relief_centre(

                        centre_name=centre_name.strip(),

                        address=centre_address.strip(),

                        contact_person=contact_person.strip(),

                        phone=contact_phone.strip(),

                        capacity=int(capacity),

                        water_litres=int(water_litres),

                        food_packets=int(food_packets),

                        medical_kits=int(medical_kits),

                        vehicles=int(vehicles),

                        latitude=float(st.session_state.centre_latitude),

                        longitude=float(st.session_state.centre_longitude)

                    )

                    set_initial_stock(centre_id, water_litres=int(water_litres),

                                      food_packets=int(food_packets), medical_kits=int(medical_kits))

                    st.success(f"Relief centre #{centre_id} registered successfully!")

                    st.session_state.centre_latitude = None

                    st.session_state.centre_longitude = None

                    st.rerun()

                except Exception as error:

                    st.error(f"Could not register relief centre: {error}")

    st.divider()

    st.subheader("Registered Relief Centres")

    centres = get_centres_with_stock()

    if centres:

        st.dataframe(

            pd.DataFrame(centres)[[

                "id", "centre_name", "address", "capacity", "water_litres",

                "food_packets", "medical_kits", "vehicles", "latitude", "longitude"

            ]],

            use_container_width=True,

            hide_index=True

        )

        for centre in centres:

            with st.expander(f"{centre['centre_name']} — {centre['address']}"):

                st.write(f"**Contact:** {centre['contact_person'] or 'Not provided'}")

                st.write(f"**Phone:** {centre['phone'] or 'Not provided'}")

                st.write(f"**Capacity:** {centre['capacity']} people")

                st.write(

                    f"**Supplies:** {centre['water_litres']} L water · "

                    f"{centre['food_packets']} food packets · "

                    f"{centre['medical_kits']} medical kits · "

                    f"{centre['vehicles']} vehicles"

                )

                st.caption(

                    f"GPS: {centre['latitude']:.6f}, {centre['longitude']:.6f}"

                )

                confirm_delete = st.checkbox(

                    "I understand this permanently removes this centre",

                    key=f"confirm_delete_centre_{centre['id']}"

                )

                if st.button(

                    "🗑️ Delete this relief centre",

                    key=f"delete_centre_{centre['id']}",

                    type="secondary",

                    disabled=not confirm_delete

                ):

                    if delete_centre_and_stock(centre["id"]):

                        st.success(f"Relief centre #{centre['id']} deleted.")

                    else:

                        st.warning("That relief centre was already removed.")

                    st.rerun()

    else:

        st.info("No relief centres registered yet. Register the first centre above.")

elif page == "Route Planner":

    from route_planner_page import render_route_planner

    render_route_planner()

elif page == "AI Relief Agent":

    from ai_agent_page import render_ai_agent

    render_ai_agent()
