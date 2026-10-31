
import streamlit as st
import pandas as pd
import requests

from weather_service import get_coordinates, get_weather

from database import (
    add_emergency_request,
    get_emergency_requests,
    get_request_count,
    update_request_status
)

st.set_page_config(
    page_title="ReliefRoutes AI",
    page_icon="🚨",
    layout="wide"
)

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
        "Route Planner",
        "AI Relief Agent"
    ]
)


# ---------------- OVERVIEW ----------------

if page == "Overview":

    st.header("Emergency Operations Dashboard")

    requests_data = get_emergency_requests()

    active_requests = get_request_count()

    critical_requests = sum(
        1 for item in requests_data
        if item["severity"] == "Critical"
        and item["status"] != "Resolved"
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Active Emergencies",
        active_requests
    )

    col2.metric(
        "Critical Requests",
        critical_requests
    )

    col3.metric(
        "Total Reports",
        len(requests_data)
    )

    st.divider()

    st.subheader("Recent Emergency Reports")

    if requests_data:
        st.dataframe(
            pd.DataFrame(requests_data),
            use_container_width=True
        )
    else:
        st.info(
            "No emergency requests registered yet."
        )


# ---------------- LIVE WEATHER ----------------

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

    st.write(
        "Register and monitor affected locations "
        "and their relief requirements."
    )

    with st.form("emergency_form"):

        location = st.text_input(
            "Affected Location / Area"
        )

        description = st.text_area(
            "Describe the emergency"
        )

        people = st.number_input(
            "Number of people affected",
            min_value=1,
            max_value=1000000,
            value=10
        )

        severity = st.selectbox(
            "Emergency Severity",
            ["Critical", "High", "Medium", "Low"]
        )

        supplies = st.multiselect(
            "Required Supplies",
            [
                "Drinking Water",
                "Food",
                "Medical Kits",
                "Clothing",
                "Rescue Equipment",
                "Temporary Shelter"
            ]
        )

        st.subheader("Optional Location Coordinates")

        latitude = st.number_input(
            "Latitude",
            min_value=-90.0,
            max_value=90.0,
            value=0.0,
            format="%.6f"
        )

        longitude = st.number_input(
            "Longitude",
            min_value=-180.0,
            max_value=180.0,
            value=0.0,
            format="%.6f"
        )

        submitted = st.form_submit_button(
            "Register Emergency Request",
            type="primary"
        )

        if submitted:

            if not location.strip() or not description.strip():
                st.error(
                    "Location and description are required."
                )

            elif not supplies:
                st.error(
                    "Select at least one required supply."
                )

            else:
                request_id = add_emergency_request(
                    location.strip(),
                    description.strip(),
                    int(people),
                    severity,
                    supplies,
                    latitude if latitude != 0 else None,
                    longitude if longitude != 0 else None
                )

                st.success(
                    f"Emergency request #{request_id} registered!"
                )

                st.rerun()

    st.divider()

    st.subheader("Registered Emergency Requests")

    records = get_emergency_requests()

    if records:

        for item in records:

            with st.expander(
                f"#{item['id']} | {item['location']} | "
                f"{item['severity']} | {item['status']}"
            ):

                st.write(
                    "**Description:**",
                    item["description"]
                )

                st.write(
                    "**People affected:**",
                    item["people_affected"]
                )

                st.write(
                    "**Required supplies:**",
                    item["supplies_needed"]
                )

                st.write(
                    "**Reported at:**",
                    item["created_at"]
                )

                st.write(
                    "**Coordinates:**",
                    item["latitude"],
                    item["longitude"]
                )

                new_status = st.selectbox(
                    "Update request status",
                    ["Pending", "In Progress", "Resolved"],
                    index=[
                        "Pending",
                        "In Progress",
                        "Resolved"
                    ].index(item["status"]),
                    key=f"status_{item['id']}"
                )

                if st.button(
                    "Update Status",
                    key=f"update_{item['id']}"
                ):

                    update_request_status(
                        item["id"],
                        new_status
                    )

                    st.success("Status updated!")
                    st.rerun()

    else:
        st.info(
            "No emergency reports yet. Register your first request above."
        )


# ---------------- OTHER MODULES ----------------

elif page == "Resource Inventory":
    st.header("📦 Resource Inventory")
    st.info("Resource management module is coming next.")

elif page == "Route Planner":
    st.header("🗺️ Relief Route Planner")
    st.info("Road network and route optimization module is coming next.")

elif page == "AI Relief Agent":
    st.header("🤖 AI Relief Coordination Agent")
    st.info("Autonomous AI planning module is coming next.")
