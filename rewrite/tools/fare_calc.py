"""
車資試算 atomic tool（純函數，無 DB）

對齊 v0.1 前 modules/services/fare_calculator.py 行為，搬回 rewrite 形態：
  - 純函數 + ToolResult
  - 沒 session / 沒 audit log（無 DB 操作）
  - 設定檔仍讀 config/taxi_fares.yml（PyYAML 缺則用內建預設）

公開 API:
  calculate_fare(*, distance_km, waiting_min=0, period='日間',
                 holiday_extra=False, disaster_extra=False, city=None)
      → ToolResult.data = dict（breakdown / total / city / ...）

  format_text(result_dict) → str  # 給 router.py 的 reply 用

  parse_command(text) → ToolResult.data = dict(distance_km, waiting_min, period)
      解析「車資試算 8.5 3 夜間」這類用戶輸入，支援全形數字 / 前綴 / # /  /
"""
from __future__ import annotations

import math
import os
import re
import logging
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # type: ignore

from rewrite.tools.base import ToolResult

logger = logging.getLogger(__name__)

# rewrite/tools/fare_calc.py → rewrite/tools → rewrite → minimal_flask/config/
_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "taxi_fares.yml"

_CONFIG_CACHE: Optional[Dict[str, Any]] = None

_DEFAULT_CONFIG: Dict[str, Any] = {
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


def _load_config_file() -> Dict[str, Any]:
    if yaml is None:
        logger.warning("PyYAML 未安裝，改用內建預設車資配置")
        return _DEFAULT_CONFIG
    if not _CONFIG_PATH.exists():
        logger.warning(f"車資 config 找不到 {_CONFIG_PATH}，改用內建預設")
        return _DEFAULT_CONFIG
    try:
        with _CONFIG_PATH.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or _DEFAULT_CONFIG
    except Exception as e:
        logger.warning(f"車資 config 載入失敗（{e}），改用內建預設")
        return _DEFAULT_CONFIG


def _load_config() -> Dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        _CONFIG_CACHE = _load_config_file()
    city = os.getenv("TAXI_CITY", "tainan") or "tainan"
    return {"config": _CONFIG_CACHE, "city": city}


def _round_to_increment(value: float, increment: int) -> int:
    """四捨五入到最接近的 increment 倍數（5 → 四捨五入到 5 元）"""
    if increment <= 1:
        return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    getcontext().rounding = ROUND_HALF_UP
    inc = Decimal(increment)
    return int((Decimal(value) / inc).quantize(Decimal("1")) * inc)


def calculate_fare(
    *,
    distance_km,
    waiting_min=0,
    period: str = "日間",
    city: Optional[str] = None,
    holiday_extra: bool = False,
    disaster_extra: bool = False,
) -> ToolResult:
    """計算車資。

    參數對 AI / 用戶輸入的 str 做 coerce（CLAUDE.md 規範）。

    步驟：
      1) 起跳價（base_distance_km 內）
      2) 距離跳表（ceil 跳數）
      3) 停等跳表（floor 整除）
      4) 夜間倍率（period='夜間'）
      5) 節慶 / 天災 flat 加成
      6) 四捨五入到 rounding_to（預設 5 元）
      7) minimum_fare 保底
    """
    # ---- type coerce ----
    try:
        distance_km = float(distance_km)
    except (TypeError, ValueError):
        return ToolResult.fail(f"distance_km 不是數字: {distance_km!r}")
    try:
        waiting_min = int(waiting_min) if waiting_min is not None else 0
    except (TypeError, ValueError):
        return ToolResult.fail(f"waiting_min 不是整數: {waiting_min!r}")

    if distance_km < 0:
        return ToolResult.fail("distance_km 不可為負")
    if waiting_min < 0:
        return ToolResult.fail("waiting_min 不可為負")
    period = period or "日間"
    if period not in ("日間", "夜間"):
        return ToolResult.fail(f"period 必須是「日間」或「夜間」，收到 {period!r}")

    loaded = _load_config()
    cfg = loaded["config"]
    calc_city = (city or loaded["city"] or "tainan")
    city_cfg = cfg.get(calc_city, {})
    default_cfg = cfg.get("default", {})

    base_distance_km = float(city_cfg.get("base_distance_km", 1.25))
    base_fare = int(city_cfg.get("base_fare", 85))
    step_distance_m = int(city_cfg.get("step_distance_m", 200))
    step_fare = int(city_cfg.get("step_fare", 5))
    waiting_step_sec = int(city_cfg.get("waiting_step_sec", 100))
    waiting_step_fare = int(city_cfg.get("waiting_step_fare", 5))

    use_default_night = bool(city_cfg.get("use_default_night", True))
    night_cfg = (default_cfg.get("night", {"type": "multiplier", "value": 1.2})
                 if use_default_night else city_cfg.get("night", {}))

    rounding_to = int(default_cfg.get("rounding_to", 5))
    minimum_fare = int(default_cfg.get("minimum_fare", 0))

    holiday_flat_extra = int(city_cfg.get("holiday_flat_extra", 0)) if holiday_extra else 0
    disaster_flat_extra = int(city_cfg.get("disaster_flat_extra", 0)) if disaster_extra else 0

    # ---- 距離 ----
    extra_distance_km = max(0.0, distance_km - base_distance_km)
    if extra_distance_km > 0 and step_distance_m > 0 and step_fare > 0:
        steps = math.ceil((extra_distance_km * 1000.0) / float(step_distance_m))
        distance_part = steps * step_fare
    else:
        distance_part = 0

    # ---- 停等 ----
    waiting_seconds = waiting_min * 60
    if waiting_seconds > 0 and waiting_step_sec > 0 and waiting_step_fare > 0:
        waiting_part = (waiting_seconds // waiting_step_sec) * waiting_step_fare
    else:
        waiting_part = 0

    subtotal = base_fare + distance_part + waiting_part

    # ---- 夜間 ----
    night_extra = 0
    if period == "夜間" and night_cfg and night_cfg.get("type") == "multiplier":
        multiplier = float(night_cfg.get("value", 1.2))
        if multiplier > 1.0:
            night_extra = int(
                Decimal(subtotal * (multiplier - 1)).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )

    running_total = subtotal + night_extra + holiday_flat_extra + disaster_flat_extra
    total = _round_to_increment(running_total, max(1, rounding_to))
    if minimum_fare > 0 and total < minimum_fare:
        total = minimum_fare

    return ToolResult.success(data={
        "city": calc_city,
        "distance_km": round(distance_km, 3),
        "waiting_min": waiting_min,
        "period": period,
        "breakdown": {
            "base_fare": int(base_fare),
            "distance_part": int(distance_part),
            "waiting_part": int(waiting_part),
            "night_extra": int(night_extra),
            "holiday_extra": int(holiday_flat_extra),
            "disaster_extra": int(disaster_flat_extra),
        },
        "round_to": int(rounding_to),
        "total": int(total),
    })


def format_text(result: Dict[str, Any]) -> str:
    """渲染成 LINE 純文字訊息（沿用 v0.1 前格式）"""
    city_label = {"tainan": "台南"}.get(result.get("city", "tainan"),
                                        result.get("city", ""))
    br = result.get("breakdown", {})
    parts = [
        f"基礎 {br.get('base_fare', 0)}",
        f"里程 {br.get('distance_part', 0)}",
        f"停等 {br.get('waiting_part', 0)}",
    ]
    if br.get("night_extra"):
        parts.append(f"夜間加成 {br['night_extra']}")
    if br.get("holiday_extra"):
        parts.append(f"節慶加成 {br['holiday_extra']}")
    if br.get("disaster_extra"):
        parts.append(f"天災加成 {br['disaster_extra']}")
    details = " + ".join(parts)
    return (
        f"🚕 {city_label}車資試算\n"
        f"里程：{result.get('distance_km')} km\n"
        f"停等：{result.get('waiting_min')} 分\n"
        f"時段：{result.get('period')}\n"
        f"小計：{details}\n"
        f"＝ 合計 {result.get('total')} 元（四捨五入至 {result.get('round_to')} 元）"
    )


# ---- 指令解析（router 用）----

# 全形數字 / 全形小數點 → 半形
_FULLWIDTH_DIGITS = {ord(c): ord('0') + i for i, c in enumerate('０１２３４５６７８９')}

_FARE_CMD_PATTERN = re.compile(
    r"^車資試算\s+([0-9]+(?:\.[0-9]+)?)\s*([0-9]+)?\s*(日間|夜間)?\s*$"
)


def _normalize(text: str) -> str:
    return (text or "").translate(_FULLWIDTH_DIGITS).replace('．', '.').strip()


def parse_command(text: str) -> ToolResult:
    """解析「車資試算 <公里> [停等分鐘] [日間|夜間]」。

    支援前綴 / 或 #（router.py 也會剝），全形數字 / 小數點。
    回 ToolResult.data = {distance_km, waiting_min, period} 給 calculate_fare。
    """
    if not isinstance(text, str):
        return ToolResult.fail("text 必須是字串")
    norm = _normalize(text)
    # router.py 已剝過 / #，這裡再保險一次
    while norm.startswith(('/', '#')):
        norm = norm[1:].lstrip()
    m = _FARE_CMD_PATTERN.match(norm)
    if not m:
        return ToolResult.fail("用法：車資試算 <公里> [停等分鐘] [日間|夜間]")
    return ToolResult.success(data={
        "distance_km": float(m.group(1)),
        "waiting_min": int(m.group(2)) if m.group(2) else 0,
        "period": m.group(3) or "日間",
    })
