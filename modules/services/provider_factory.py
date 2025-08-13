import os
from modules.services.distance_service import LocalHaversineProvider, GoogleMapsProvider, DistanceProvider


def get_distance_provider() -> DistanceProvider:
    provider = os.getenv("MAPS_PROVIDER", "local").lower()
    if provider == "google" and os.getenv("GOOGLE_MAPS_API_KEY"):
        return GoogleMapsProvider()
    return LocalHaversineProvider()
