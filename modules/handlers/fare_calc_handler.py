import re
import logging
from typing import Optional

from modules.services.fare_calculator import calculate_fare, format_text

logger = logging.getLogger(__name__)

# 支援可選前綴 / 或 ＃，支援全形數字與全形小數點
FARE_CMD_PATTERN = re.compile(
    r"^(?:[\s/＃#]*)?(?:車資試算)\s+([0-9０-９]+(?:[\.．][0-9０-９]+)?)\s*([0-9０-９]+)?\s*(日間|夜間)?\s*$"
)


def _to_halfwidth_digits(text: str) -> str:
    mapping = {ord(c): ord('0') + i for i, c in enumerate('０１２３４５６７８９')}
    text = text.translate(mapping)
    return text.replace('．', '.')


def is_fare_calc_command(message_text: str) -> bool:
    if not isinstance(message_text, str):
        return False
    normalized = _to_halfwidth_digits(message_text.strip())
    return bool(FARE_CMD_PATTERN.match(normalized))


def looks_like_fare_calc(message_text: str) -> bool:
    """Lenient heuristic to detect fare calc intent.
    Accepts strings containing '車資試算' with optional leading '/' or '#'.
    """
    if not isinstance(message_text, str):
        return False
    text = _to_halfwidth_digits(message_text).strip()
    # strip leading slashes and hashes
    while text and text[0] in ('/', '＃', '#'):
        text = text[1:].lstrip()
    return text.startswith("車資試算") or ("車資試算" in text)


def handle_fare_calc(message_text: str) -> str:
    """Parse command and return formatted text (Traditional Chinese)."""
    try:
        normalized = _to_halfwidth_digits(message_text.strip())
        m = FARE_CMD_PATTERN.match(normalized)
        if not m:
            return "用法：車資試算 <公里> [停等分鐘] [日間|夜間]"
        distance_str = m.group(1)
        waiting_str: Optional[str] = m.group(2)
        period: Optional[str] = m.group(3)

        distance_km = float(distance_str)
        waiting_min = int(waiting_str) if waiting_str is not None else 0
        period = period or "日間"

        if distance_km < 0 or waiting_min < 0:
            return "❌ 參數不可為負數\n用法：車資試算 <公里> [停等分鐘] [日間|夜間]"

        result = calculate_fare(distance_km=distance_km, waiting_min=waiting_min, period=period)
        return format_text(result)

    except Exception as e:
        logger.error(f"車資試算處理失敗: {e}")
        return "❌ 車資試算失敗，請檢查格式或稍後再試\n用法：車資試算 <公里> [停等分鐘] [日間|夜間]"
