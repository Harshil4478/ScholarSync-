# 🚨 ReliefRoutes AI

### AI-Powered Emergency Response & Relief Coordination Platform

ReliefRoutes AI is an intelligent disaster-response platform designed to support emergency relief operations during floods, cyclones, and other natural disasters.

The platform helps identify affected locations, manage emergency requests, monitor available resources, coordinate relief centres, and plan road routes for delivering essential supplies.

## 🌍 Problem Statement

During natural disasters, emergency response teams often face challenges such as:
- Difficulty identifying affected locations.
- Lack of real-time visibility into available resources.
- Poor coordination between relief centres.
- Delays in delivering essential supplies.
- Difficulty selecting suitable routes for relief transportation.

## 💡 Our Solution

ReliefRoutes AI brings emergency requests, relief-centre inventory, weather information, route planning, and AI-assisted coordination into one platform.

## ✨ Key Features

- **Emergency Management:** Register emergencies, record severity, affected population, required supplies, and GPS coordinates.
- **Live Weather Monitoring:** Retrieve current weather conditions and rainfall forecasts.
- **Resource Inventory:** Track available food, water, medical supplies, and other resources.
- **Relief Centre Management:** Register centres, GPS locations, capacity, and available supplies.
- **Interactive Disaster Map:** Visualise emergency locations and relief centres.
- **Route Planning:** Calculate road routes between emergency locations and relief centres.
- **AI Relief Agent:** Support emergency-response decisions through AI-assisted coordination.

## 🛠️ Technology Stack

- Python
- Streamlit
- SQLite
- Folium
- OpenStreetMap
- OSRM
- Open-Meteo
- Pandas
- Altair

## 🏗️ Project Structure

```text
ReliefRoutes-AI/
│
├── app.py
├── dashboard_page.py
├── ui_theme.py
├── database.py
├── logistics.py
├── agent_core.py
├── weather_service.py
├── map_service.py
├── routing_service.py
├── relief_centres.py
├── route_planner_page.py
├── ai_agent_page.py
├── requirements.txt
└── README.md
```

## 🚀 Installation and Setup

1. Clone the repository:

```bash
git clone https://github.com/Harshil4478/ReliefRoutes-AI.git
```

2. Navigate to the project directory:

```bash
cd ReliefRoutes-AI
```

3. Create a virtual environment:

```bash
python -m venv venv
```

4. Activate it on Windows:

```bash
venv\Scripts\activate
```

5. Install dependencies:

```bash
pip install -r requirements.txt
```

6. Run the application:

```bash
streamlit run app.py
```

## 🎯 Project Theme

Climate, Resource Infrastructure & Global Supply Resilience.

## 👥 Team

Developed as part of a GenAI Buildathon project.

## ⚠️ Disclaimer

Weather forecasts and calculated road routes are decision-support information. They do not independently verify flood conditions, road closures, or route safety. Emergency decisions should be confirmed by authorised response personnel.
