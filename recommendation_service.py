"""Relief centre recommendation logic for ReliefRoutes AI.

Pure functions (no Streamlit) so the same code can later be used as a tool
by the AI Relief Agent.
"""
import math

from routing_service import get_road_route, haversine_km

# ---- Planning assumptions: tune these for your scenario ----
WATER_L_PER_PERSON = 3          # litres of drinking water per person
FOOD_PACKETS_PER_PERSON = 1     # packets per person
PERSONS_PER_MEDICAL_KIT = 10    # one kit per this many people
MISSING_SUPPLY_PENALTY_MIN = 120  # score penalty (minutes) for 0% supply coverage
ROUTE_CANDIDATES = 4            # how many centres get a real OSRM road route
FALLBACK_SPEED_KMH = 40         # used only if OSRM is unavailable
FALLBACK_DETOUR = 1.4           # straight-line to road distance factor

SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def parse_needs(supplies_needed):
    """Turn the stored 'supplies_needed' (list or comma string) into a set of keys."""
    if isinstance(supplies_needed, (list, tuple, set)):
        text = ",".join(str(item) for item in supplies_needed)
    else:
        text = str(supplies_needed or "")
    text = text.lower()
    needs = set()
    if "water" in text:
        needs.add("water_litres")
    if "food" in text:
        needs.add("food_packets")
    if "medical" in text or "medicine" in text:
        needs.add("medical_kits")
    return needs


def required_quantities(emergency, already_sent=None):
    """Estimate how much of each needed supply this emergency still requires.

    already_sent: optional {supply key: quantity} from earlier dispatches, subtracted
    so a second dispatch only covers what is still missing.
    """
    people = max(int(emergency.get("people_affected") or 1), 1)
    quantities = {}
    for key in parse_needs(emergency.get("supplies_needed")):
        if key == "water_litres":
            quantities[key] = people * WATER_L_PER_PERSON
        elif key == "food_packets":
            quantities[key] = people * FOOD_PACKETS_PER_PERSON
        elif key == "medical_kits":
            quantities[key] = max(1, math.ceil(people / PERSONS_PER_MEDICAL_KIT))
    if already_sent:
        quantities = {k: v - int(already_sent.get(k, 0)) for k, v in quantities.items()}
        quantities = {k: v for k, v in quantities.items() if v > 0}
    return quantities


def supply_coverage(centre, required):
    """Average fraction (0-1) of the required supplies the centre can cover."""
    if not required:
        return 1.0
    ratios = [min(int(centre.get(key) or 0) / need, 1.0) for key, need in required.items()]
    return sum(ratios) / len(ratios)


def dispatch_plan(centre, required):
    """What would actually be sent: the smaller of need and stock, per item."""
    return {key: min(int(centre.get(key) or 0), need) for key, need in required.items()}


def recommend_centres(emergency, centres, top_n=3, route_fn=get_road_route, already_sent=None):
    """Return the best centres for one emergency, best first.

    Steps: keep Active centres with some matching stock -> shortlist by
    straight-line distance -> fetch road routes -> score (travel time plus a
    penalty for missing supplies; lower is better).
    """
    required = required_quantities(emergency, already_sent)
    lat, lon = emergency["latitude"], emergency["longitude"]

    shortlist = []
    for centre in centres:
        if centre.get("status", "Active") != "Active":
            continue
        coverage = supply_coverage(centre, required)
        if required and coverage == 0:
            continue
        straight = haversine_km(lat, lon, centre["latitude"], centre["longitude"])
        shortlist.append((straight, coverage, centre))

    shortlist.sort(key=lambda item: item[0])
    results = []
    for straight, coverage, centre in shortlist[:max(top_n, ROUTE_CANDIDATES)]:
        route = route_fn(centre["latitude"], centre["longitude"], lat, lon)
        estimated = route is None
        if estimated:
            distance = straight * FALLBACK_DETOUR
            route = {
                "points": [[centre["latitude"], centre["longitude"]], [lat, lon]],
                "distance_km": distance,
                "duration_min": distance / FALLBACK_SPEED_KMH * 60,
            }
        score = route["duration_min"] + (1 - coverage) * MISSING_SUPPLY_PENALTY_MIN
        results.append({
            "centre": centre,
            "coverage": coverage,
            "route": route,
            "estimated": estimated,
            "score": score,
            "plan": dispatch_plan(centre, required),
            "capacity_ok": int(centre.get("capacity") or 0) >= int(emergency.get("people_affected") or 0),
        })

    results.sort(key=lambda item: item["score"])
    return results[:top_n]
