import os
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import requests

from modules.services.geo_utils import haversine_km, eta_minutes

logger = logging.getLogger("arrival")


@dataclass
class Point:
    latitude: float
    longitude: float


class DistanceProvider:
    def distance_km(self, origin: Point, dest: Point) -> float:  # pragma: no cover - interface
        raise NotImplementedError

    def eta_min(self, distance_km_value: float, chat_avg_kmh: Optional[float]) -> int:  # pragma: no cover - interface
        raise NotImplementedError

    @property
    def label(self) -> str:
        return "本地直線"


class LocalHaversineProvider(DistanceProvider):
    def distance_km(self, origin: Point, dest: Point) -> float:
        return haversine_km(origin.latitude, origin.longitude, dest.latitude, dest.longitude)

    def eta_min(self, distance_km_value: float, chat_avg_kmh: Optional[float]) -> int:
        avg = chat_avg_kmh if chat_avg_kmh and chat_avg_kmh > 0 else float(os.getenv("AVG_SPEED_KMH", 30))
        return eta_minutes(distance_km_value, avg)

    @property
    def label(self) -> str:
        return "本地直線"


class GoogleMapsProvider(DistanceProvider):
    def __init__(self, fallback: DistanceProvider | None = None):
        self._fallback = fallback or LocalHaversineProvider()
        self._api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self._enabled = os.getenv("MAPS_PROVIDER", "local").lower() == "google" and bool(self._api_key)
        self._last_used_google = False
        self._last_distance_km = None
        self._last_duration_min = None

    def _query(self, origin: Point, dest: Point) -> Optional[Tuple[float, int]]:
        if not self._enabled:
            return None
        try:
            url = (
                "https://maps.googleapis.com/maps/api/distancematrix/json?origins="
                f"{origin.latitude},{origin.longitude}&destinations={dest.latitude},{dest.longitude}"
                "&mode=driving&units=metric&language=zh-TW&key="
                f"{self._api_key}"
            )
            resp = requests.get(url, timeout=3)
            if resp.status_code != 200:
                logger.warning("Google DistanceMatrix 非200，回退本地 provider")
                return None
            data = resp.json()
            if data.get("status") != "OK":
                logger.warning("Google DistanceMatrix 狀態非OK，回退本地 provider")
                return None
            rows = data.get("rows") or []
            elements = rows[0].get("elements") if rows else []
            elem = elements[0] if elements else None
            if not elem or elem.get("status") != "OK":
                logger.warning("Google DistanceMatrix 元素無結果，回退本地 provider")
                return None
            meters = elem["distance"]["value"]
            seconds = elem["duration"]["value"]
            return meters / 1000.0, int(round(seconds / 60.0))
        except Exception as e:
            logger.warning(f"Google DistanceMatrix 失敗，回退本地 provider: {type(e).__name__}")
            return None

    def distance_km(self, origin: Point, dest: Point) -> float:
        result = self._query(origin, dest)
        if result is None:
            # fallback
            self._last_used_google = False
            self._last_distance_km = self._fallback.distance_km(origin, dest)
            self._last_duration_min = None
            return self._last_distance_km
        distance_km_value, duration_min = result
        self._last_used_google = True
        self._last_distance_km = distance_km_value
        self._last_duration_min = duration_min
        return distance_km_value

    def eta_min(self, distance_km_value: float, chat_avg_kmh: Optional[float]) -> int:
        # 若剛剛成功使用 Google，優先使用其 duration
        if self._enabled and self._last_used_google and self._last_duration_min is not None:
            return int(self._last_duration_min)
        # 否則回退到本地估算
        return self._fallback.eta_min(distance_km_value, chat_avg_kmh)

    @property
    def label(self) -> str:
        # 回報實際使用情況，而非僅環境設定
        return "Google 路線" if (self._enabled and self._last_used_google) else "本地直線"
