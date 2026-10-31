import requests
import pandas as pd
import streamlit as st
from weather_service import get_coordinates, get_weather

st.set_page_config(
    page_title="ReliefRoutes AI",
    page_icon="🚨",
    layout="wide"
)

st.title("🚨 ReliefRoutes AI")
st.caption("Autonomous Emergency Response & Relief Coordination")

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

if page == "Overview":
    st.header("Emergency Operations Dashboard")

    col1, col2, col3 = st.columns(3)
    col1.metric("Active Emergencies", "0")
    col2.metric("Available Supplies", "0")
    col3.metric("Active Dispatches", "0")

    st.info("Welcome to the ReliefRoutes Operations Center.")

elif page == "Live Weather":
    st.header("🌦️ Live Weather Monitoring")

    st.write(
        "Retrieve real-time weather conditions "
        "and rainfall forecasts for your selected location."
    )

    city = st.text_input(
        "Enter city or district",
        value="Coimbatore"
    )

    if st.button("Fetch Live Weather", type="primary"):
        if not city.strip():
            st.warning("Please enter a location.")
        else:
            try:
                with st.spinner("Retrieving live weather data..."):
                    location = get_coordinates(city.strip())

                    weather = get_weather(
                        location["latitude"],
                        location["longitude"]
                    )

                current = weather["current"]

                st.success(
                    f"Weather retrieved for "
                    f"{location['name']}, {location['country']}"
                )

                st.caption(
                    f"Data time: {current['time']} | "
                    f"Timezone: {weather.get('timezone', 'Local')}"
                )

                col1, col2, col3, col4 = st.columns(4)

                col1.metric(
                    "Temperature",
                    f"{current['temperature_2m']} °C"
                )

                col2.metric(
                    "Humidity",
                    f"{current['relative_humidity_2m']} %"
                )

                col3.metric(
                    "Rainfall",
                    f"{current['precipitation']} mm"
                )

                col4.metric(
                    "Wind Speed",
                    f"{current['wind_speed_10m']} km/h"
                )

                st.subheader("Rainfall Forecast")

                hourly = weather["hourly"]

                forecast = {
                    "Time": hourly["time"][:12],
                    "Temperature (°C)": hourly["temperature_2m"][:12],
                    "Rainfall (mm)": hourly["precipitation"][:12],
                    "Rain Probability (%)": hourly[
                        "precipitation_probability"
                    ][:12]
                }

                st.dataframe(pd.DataFrame(forecast), use_container_width=True)

                next_six_hours = hourly["precipitation"][:6]
                rainfall_total = sum(
                    value or 0 for value in next_six_hours
                )

                st.subheader("Weather Risk Indicator")

                if rainfall_total >= 30:
                    st.error(
                        "High rainfall watch: "
                        "Forecast rainfall is elevated."
                    )
                elif rainfall_total >= 10:
                    st.warning(
                        "Moderate rainfall watch: "
                        "Monitor upcoming conditions."
                    )
                else:
                    st.success(
                        "No elevated rainfall indication "
                        "from this six-hour forecast."
                    )

                st.caption(
                    "This is a rainfall screening indicator, "
                    "not a confirmed flood or road safety assessment."
                )

                st.caption(
                    "Source: Open-Meteo API"
                )

            except requests.RequestException as error:
                st.error(f"Weather service error: {error}")

            except (ValueError, KeyError) as error:
                st.error(f"Could not process weather data: {error}")

elif page == "Emergency Requests":
    st.header("🚨 Emergency Request Management")

elif page == "Resource Inventory":
    st.header("📦 Resource Inventory")

elif page == "Route Planner":
    st.header("🗺️ Relief Route Planner")

elif page == "AI Relief Agent":
    st.header("🤖 AI Relief Coordination Agent")
