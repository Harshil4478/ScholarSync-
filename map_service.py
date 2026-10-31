
import requests
import folium


def geocode_location(place):
    url = "https://geocoding-api.open-meteo.com/v1/search"

    response = requests.get(
        url,
        params={
            "name": place,
            "count": 1,
            "language": "en",
            "format": "json"
        },
        timeout=15
    )

    response.raise_for_status()

    results = response.json().get("results", [])

    if not results:
        return None

    result = results[0]

    return {
        "latitude": result["latitude"],
        "longitude": result["longitude"],
        "name": result["name"],
        "country": result.get("country", "")
    }


def create_relief_map(emergencies, inventory):

    locations = []

    # Emergency markers
    for item in emergencies:

        latitude = item.get("latitude")
        longitude = item.get("longitude")

        if latitude is None or longitude is None:
            try:
                result = geocode_location(item["location"])
                if result:
                    latitude = result["latitude"]
                    longitude = result["longitude"]
            except requests.RequestException:
                continue

        if latitude is None or longitude is None:
            continue

        locations.append({
            "latitude": latitude,
            "longitude": longitude,
            "name": item["location"],
            "type": "Emergency",
            "severity": item["severity"],
            "status": item["status"],
            "description": item["description"]
        })

    # Resource centre markers
    for item in inventory:

        try:
            result = geocode_location(item["location"])

            if result:
                locations.append({
                    "latitude": result["latitude"],
                    "longitude": result["longitude"],
                    "name": item["location"],
                    "type": "Resource Centre",
                    "resource": item["resource_name"],
                    "quantity": item["quantity"],
                    "unit": item["unit"]
                })

        except requests.RequestException:
            continue

    if locations:

        center_lat = sum(
            x["latitude"] for x in locations
        ) / len(locations)

        center_lon = sum(
            x["longitude"] for x in locations
        ) / len(locations)

    else:
        center_lat = 20.5937
        center_lon = 78.9629

    relief_map = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=6,
        tiles="OpenStreetMap"
    )

    for item in locations:

        if item["type"] == "Emergency":

            colors = {
                "Critical": "red",
                "High": "orange",
                "Medium": "blue",
                "Low": "green"
            }

            color = colors.get(
                item["severity"], "gray"
            )

            popup = f"""
            <b>EMERGENCY REPORT</b><br>
            Location: {item['name']}<br>
            Severity: {item['severity']}<br>
            Status: {item['status']}<br>
            Description: {item['description']}
            """

            icon = "warning-sign"

        else:

            color = "green"

            popup = f"""
            <b>RESOURCE CENTRE</b><br>
            Location: {item['name']}<br>
            Resource: {item['resource']}<br>
            Quantity: {item['quantity']} {item['unit']}
            """

            icon = "home"

        folium.Marker(
            location=[
                item["latitude"],
                item["longitude"]
            ],
            popup=folium.Popup(popup, max_width=300),
            tooltip=item["name"],
            icon=folium.Icon(
                color=color,
                icon=icon
            )
        ).add_to(relief_map)

    return relief_map, locations
