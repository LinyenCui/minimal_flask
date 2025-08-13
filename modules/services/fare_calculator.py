"""
TODO: Integrate Google Maps Distance Matrix API in the future.
This module currently provides config-driven fare calculation using local inputs only.
"""
from __future__ import annotations

import os
import math
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from decimal import Decimal, ROUND_HALF_UP, getcontext

# Lazy/guarded import: allow module to load even if PyYAML is missing
try:  # pragma: no cover - environment specific
    import yaml  # type: ignore
except Exception:  # ImportError or environment issues
    yaml = None  # type: ignore

logger = logging.getLogger(__name__)

_CONFIG_CACHE: Dict[str, Any] | None = None
_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "taxi_fares.yml"


def _load_yaml_config_file(config_path: Path) -> Dict[str, Any]:
    # If PyYAML is not available, fall back to defaults to avoid crashing routing
    if yaml is None:
        logger.warning("PyYAML 未安裝，改用內建預設車資配置。請在環境中安裝 PyYAML>=6.0.1。")
        return {
            "default": {
                "rounding_to": 5,
                "minimum_fare": 0,
                "waiting_granularity_sec": 60,
                "night": {"type": "multiplier", "value": 1.2},
            },
            "tainan": {
                "base_distance_km": 1.25,
                "base_fare": 85,
                "step_distance_m": 200,
                "step_fare": 5,
                "waiting_step_sec": 100,
                "waiting_step_fare": 5,
                "waiting_from_speed_kmh": 5,
                "use_default_night": True,
                "holiday_flat_extra": 50,
                "disaster_flat_extra": 50,
                "trunk_fee_enabled": False,
            },
        }
    if not config_path.exists():
        logger.warning(f"Taxi fare config not found at {config_path}. Using in-memory defaults.")
        # Minimal sane defaults matching provided Tainan sample
        return {
            "default": {
                "rounding_to": 5,
                "minimum_fare": 0,
                "waiting_granularity_sec": 60,
                "night": {"type": "multiplier", "value": 1.2},
            },
            "tainan": {
                "base_distance_km": 1.25,
                "base_fare": 85,
                "step_distance_m": 200,
                "step_fare": 5,
                "waiting_step_sec": 100,
                "waiting_step_fare": 5,
                "waiting_from_speed_kmh": 5,
                "use_default_night": True,
                "holiday_flat_extra": 50,
                "disaster_flat_extra": 50,
                "trunk_fee_enabled": False,
            },
        }

    try:
        with config_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to load taxi fare config: {e}. Using in-memory defaults.")
        return {
            "default": {
                "rounding_to": 5,
                "minimum_fare": 0,
                "waiting_granularity_sec": 60,
                "night": {"type": "multiplier", "value": 1.2},
            },
            "tainan": {
                "base_distance_km": 1.25,
                "base_fare": 85,
                "step_distance_m": 200,
                "step_fare": 5,
                "waiting_step_sec": 100,
                "waiting_step_fare": 5,
                "waiting_from_speed_kmh": 5,
                "use_default_night": True,
                "holiday_flat_extra": 50,
                "disaster_flat_extra": 50,
                "trunk_fee_enabled": False,
            },
        }


def load_config(city_env: str = "TAXI_CITY", default_city: str = "tainan") -> Dict[str, Any]:
    """Load taxi fare configuration. Allows city override via environment.

    Returns a dict with keys: default, <city>.
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        cfg = _load_yaml_config_file(_CONFIG_PATH)
        _CONFIG_CACHE = cfg
    city = os.getenv(city_env, default_city) or default_city
    return {"config": _CONFIG_CACHE, "city": city}


def _round_to_increment_half_up(value: float, increment: int) -> int:
    if increment <= 1:
        return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    # Use Decimal to avoid bankers rounding surprises
    getcontext().rounding = ROUND_HALF_UP
    inc = Decimal(increment)
    d = Decimal(value)
    result = (d / inc).quantize(Decimal("1")) * inc
    return int(result)


def calculate_fare(
    distance_km: float,
    waiting_min: int = 0,
    period: str = "日間",
    city: Optional[str] = None,
    holiday_extra: bool = False,
    disaster_extra: bool = False,
) -> Dict[str, Any]:
    """Compute taxi fare using config-driven parameters.

    Steps per spec:
      1) base within base_distance_km
      2) distance steps (ceil by default)
      3) waiting time steps (floor via integer division)
      4) night multiplier if period == '夜間'
      5) holiday/disaster flat extras
      6) rounding to nearest configured increment (e.g., 5)
      7) minimum fare enforcement
    """
    loaded = load_config()
    cfg = loaded["config"]
    calc_city = city or loaded["city"] or "tainan"
    city_cfg = cfg.get(calc_city, {})
    default_cfg = cfg.get("default", {})

    # Extract config with robust fallbacks
    base_distance_km = float(city_cfg.get("base_distance_km", 1.25))
    base_fare = int(city_cfg.get("base_fare", 85))
    step_distance_m = int(city_cfg.get("step_distance_m", 200))
    step_fare = int(city_cfg.get("step_fare", 5))

    waiting_step_sec = int(city_cfg.get("waiting_step_sec", 100))
    waiting_step_fare = int(city_cfg.get("waiting_step_fare", 5))

    use_default_night = bool(city_cfg.get("use_default_night", True))
    night_cfg = default_cfg.get("night", {"type": "multiplier", "value": 1.2}) if use_default_night else city_cfg.get("night", {})

    rounding_to = int(default_cfg.get("rounding_to", 5))
    minimum_fare = int(default_cfg.get("minimum_fare", 0))

    holiday_flat_extra = int(city_cfg.get("holiday_flat_extra", 0)) if holiday_extra else 0
    disaster_flat_extra = int(city_cfg.get("disaster_flat_extra", 0)) if disaster_extra else 0

    # Base and distance part
    subtotal_meter = base_fare
    extra_distance_km = max(0.0, float(distance_km) - base_distance_km)
    if extra_distance_km > 0 and step_distance_m > 0 and step_fare > 0:
        steps = math.ceil((extra_distance_km * 1000.0) / float(step_distance_m))
        distance_part = steps * step_fare
    else:
        distance_part = 0

    # Waiting part
    waiting_seconds = max(0, int(waiting_min)) * 60
    if waiting_seconds > 0 and waiting_step_sec > 0 and waiting_step_fare > 0:
        wait_steps = waiting_seconds // waiting_step_sec
        waiting_part = wait_steps * waiting_step_fare
    else:
        waiting_part = 0

    subtotal = subtotal_meter + distance_part + waiting_part

    # Night extra
    night_extra_amount = 0
    if period == "夜間" and night_cfg and night_cfg.get("type") == "multiplier":
        multiplier = float(night_cfg.get("value", 1.2))
        if multiplier > 1.0:
            night_extra_amount = int(Decimal(subtotal * (multiplier - 1)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    # Add holiday/disaster flat extras
    running_total = subtotal + night_extra_amount + holiday_flat_extra + disaster_flat_extra

    # Rounding and minimum fare
    total_after_rounding = _round_to_increment_half_up(running_total, max(1, rounding_to))
    if minimum_fare > 0 and total_after_rounding < minimum_fare:
        total_after_rounding = minimum_fare

    result = {
        "city": calc_city,
        "distance_km": float(round(distance_km, 3)),
        "waiting_min": int(max(0, waiting_min)),
        "period": "夜間" if period == "夜間" else "日間",
        "breakdown": {
            "base_fare": int(base_fare),
            "distance_part": int(distance_part),
            "waiting_part": int(waiting_part),
            "night_extra": int(night_extra_amount),
            "holiday_extra": int(holiday_flat_extra),
            "disaster_extra": int(disaster_flat_extra),
        },
        "round_to": int(rounding_to),
        "total": int(total_after_rounding),
    }
    return result


def format_text(result: Dict[str, Any]) -> str:
    city_label = {
        "tainan": "台南",
    }.get(result.get("city", "tainan"), result.get("city", ""))

    br = result.get("breakdown", {})
    base_fare = br.get("base_fare", 0)
    distance_part = br.get("distance_part", 0)
    waiting_part = br.get("waiting_part", 0)
    night_extra = br.get("night_extra", 0)
    holiday_extra = br.get("holiday_extra", 0)
    disaster_extra = br.get("disaster_extra", 0)

    parts = [f"基礎 {base_fare}", f"里程 {distance_part}", f"停等 {waiting_part}"]
    if night_extra:
        parts.append(f"夜間加成 {night_extra}")
    if holiday_extra:
        parts.append(f"節慶加成 {holiday_extra}")
    if disaster_extra:
        parts.append(f"天災加成 {disaster_extra}")

    details = " + ".join(parts)

    return (
        f"🚕 {city_label}車資試算\n"
        f"里程：{result.get('distance_km')} km\n"
        f"停等：{result.get('waiting_min')} 分\n"
        f"時段：{result.get('period')}\n"
        f"小計：{details}\n"
        f"＝ 合計 {result.get('total')} 元（四捨五入至 {result.get('round_to')} 元）"
    )


def maps_future_stub(distance_km: float, duration_min: int) -> Dict[str, Any]:
    return {
        "distance_km": float(distance_km),
        "duration_min": int(duration_min),
        "note": "TODO: Google Maps Distance Matrix API",
    }
