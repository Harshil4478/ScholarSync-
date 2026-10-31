
import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def get_coordinates(city):
    response = requests.get(
        GEOCODING_URL,
        params={
            "name": city,
            "count": 1,
            "language": "en",
            "format": "json"
        },
        timeout=15
    )
    response.raise_for_status()

    results = response.json().get("results", [])

    if not results:
        raise ValueError(f"Location not found: {city}")

    place = results[0]

    return {
        "name": place["name"],
        "country": place.get("country", ""),
        "latitude": place["latitude"],
        "longitude": place["longitude"]
    }


def get_weather(latitude, longitude):
    response = requests.get(
        FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation",
                "rain",
                "wind_speed_10m",
                "weather_code"
            ],
            "hourly": [
                "precipitation_probability",
                "precipitation",
                "temperature_2m"
            ],
            "forecast_days": 2,
            "timezone": "auto"
        },
        timeout=20
    )

    response.raise_for_status()
    return response.json()
