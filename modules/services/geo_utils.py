import math
from typing import Optional

# Haversine distance between two lat/lon points in kilometers
# Formula assumes Earth radius ~ 6371 km

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def eta_minutes(distance_km: float, avg_kmh: float) -> int:
    if avg_kmh <= 0:
        return 0
    hours = distance_km / float(avg_kmh)
    minutes = hours * 60.0
    # Round to nearest minute
    return int(round(minutes))
