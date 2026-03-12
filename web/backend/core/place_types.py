"""
Place type configuration — OSM queries, colors, labels, Garmin symbols.
Extracted from main_gui_enhanced.py and made GUI-independent.
"""

PLACE_TYPE_CONFIG = {
    "petrol": {
        "query": 'node["amenity"="fuel"]',
        "tag_key": "amenity",
        "tag_values": ["fuel"],
        "name": "Petrol Station",
        "emoji": "⛽",
        "color": "red",
        "default_distance_km": 0.1,
        "garmin_symbol": "Gas Station",
        "label_prefix": "Fuel",
        "on_route_only": False,
    },
    "supermarket": {
        "query": 'node["shop"="supermarket"]',
        "tag_key": "shop",
        "tag_values": ["supermarket"],
        "name": "Supermarket",
        "emoji": "🛒",
        "color": "blue",
        "default_distance_km": 0.1,
        "garmin_symbol": "Shopping Center",
        "label_prefix": "Market",
        "on_route_only": False,
    },
    "bakery": {
        "query": 'node["shop"="bakery"]',
        "tag_key": "shop",
        "tag_values": ["bakery"],
        "name": "Bakery",
        "emoji": "🥖",
        "color": "orange",
        "default_distance_km": 0.1,
        "garmin_symbol": "Restaurant",
        "label_prefix": "Bakery",
        "on_route_only": False,
    },
    "cafe": {
        "query": 'node["amenity"~"^(cafe|restaurant|fast_food)$"]',
        "tag_key": "amenity",
        "tag_values": ["cafe", "restaurant", "fast_food"],
        "name": "Café/Restaurant",
        "emoji": "☕",
        "color": "green",
        "default_distance_km": 0.1,
        "garmin_symbol": "Restaurant",
        "label_prefix": "Cafe",
        "on_route_only": False,
    },
    "repair": {
        "query": 'node["shop"~"^(car_repair|motorcycle)$"]',
        "tag_key": "shop",
        "tag_values": ["car_repair", "motorcycle"],
        "name": "Repair Shop",
        "emoji": "🔧",
        "color": "purple",
        "default_distance_km": 0.1,
        "garmin_symbol": "Car Repair",
        "label_prefix": "Repair",
        "on_route_only": False,
    },
    "accommodation": {
        "query": 'node["tourism"~"^(hotel|motel|guest_house|hostel|camp_site|caravan_site)$"]',
        "tag_key": "tourism",
        "tag_values": ["hotel", "motel", "guest_house", "hostel", "camp_site", "caravan_site"],
        "name": "Accommodation",
        "emoji": "🏨",
        "color": "brown",
        "default_distance_km": 0.1,
        "garmin_symbol": "Lodging",
        "label_prefix": "Hotel",
        "on_route_only": False,
    },
    "speed_camera": {
        "query": 'node["highway"="speed_camera"]',
        "tag_key": "highway",
        "tag_values": ["speed_camera"],
        "name": "Speed Camera",
        "emoji": "📷",
        "color": "darkred",
        "default_distance_km": 0.05,
        "garmin_symbol": "Danger",
        "label_prefix": "SpeedCam",
        "on_route_only": True,
    },
}


def get_config(place_type: str) -> dict:
    """Return config for a place type, raising KeyError if unknown."""
    return PLACE_TYPE_CONFIG[place_type]


def make_label(place_type: str, number: int) -> str:
    """Return a display label like 'Fuel 3' or 'Hotel 1'."""
    prefix = PLACE_TYPE_CONFIG.get(place_type, {}).get("label_prefix", "Place")
    return f"{prefix} {number}"


def make_waypoint_name(place: dict, number: int, max_len: int = 50) -> str:
    """Create a Garmin-compatible GPX waypoint name."""
    place_type = place.get("place_type", "unknown")
    prefix = make_label(place_type, number)
    distance = place.get("distance_km", 0.0)
    base_name = place.get("base_name", "Unknown")
    full = f"{prefix} ({distance:.1f}km) {base_name}"
    if len(full) > max_len:
        base_part = f"{prefix} ({distance:.1f}km) "
        available = max_len - len(base_part)
        if available > 3:
            full = base_part + base_name[: available - 3] + "..."
        else:
            full = f"{prefix} ({distance:.1f}km)"
    return full
