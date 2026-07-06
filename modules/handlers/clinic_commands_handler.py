import logging
import re
import time
from typing import Dict

from modules.services.clinic_location_service import get_for_chat, set_for_chat, clear_for_chat
from modules.services.chat_settings_service import set_avg_speed, get_avg_speed
import os

logger = logging.getLogger(__name__)

# 簡易等待狀態：在群組要求「設定診所」後，等待下一則位置訊息寫入
_WAIT_MAP: Dict[str, float] = {}
_WAIT_TTL_SEC = 10 * 60


def _normalize_spaces(s: str) -> str:
    s = s.replace("　", " ")  # 全形空白轉半形
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def set_wait_for_chat(chat_id: str) -> None:
    _WAIT_MAP[chat_id] = time.time() + _WAIT_TTL_SEC


def is_waiting_for_location(chat_id: str) -> bool:
    exp = _WAIT_MAP.get(chat_id)
    if not exp:
        return False
    if exp < time.time():
        _WAIT_MAP.pop(chat_id, None)
        return False
    return True


def clear_wait(chat_id: str) -> None:
    _WAIT_MAP.pop(chat_id, None)


def handle_clinic_commands(message_text: str, chat_id: str):
    """處理地點（診所）座標相關指令。回傳純文字。

    「設定地點」系列是「設定診所」的通用同義詞 — 每個群組可設定一個
    固定目的地並命名（group_location_meta.place_name），不限診所使用。
    """
    text = _normalize_spaces(message_text)

    # 通用同義詞 → 正規化成診所指令（座標表共用 clinic_locations）
    for alias, canon in (
        ("設定地點名稱", None),   # 名稱指令自己處理,不正規化
        ("查看地點名稱", None),
        ("設定地點", "設定診所"),
        ("查看地點座標", "查看診所座標"),
        ("清除地點座標", "清除診所座標"),
    ):
        if canon and (text == alias or text.startswith(alias + " ")):
            text = canon + text[len(alias):]
            break

    # === 地點命名（group_location_meta.place_name，提醒訊息會帶名稱）===
    if text.startswith("設定地點名稱 "):
        name = text[len("設定地點名稱 "):].strip()
        if not name:
            return "❌ 請給名稱，例如：設定地點名稱 達恩診所"
        if len(name) > 50:
            return "❌ 名稱太長（上限 50 字）"
        from modules.services.group_location_meta_service import set_name
        set_name(chat_id, name)
        return (f"✅ 已設定地點名稱：「{name}」\n"
                f"之後司機傳位置，提醒會顯示「來程車輛接近『{name}』」。")

    if text == "設定地點名稱":
        return "請輸入：設定地點名稱 <名稱>\n例如：設定地點名稱 達恩診所"

    if text == "查看地點名稱":
        from modules.services.group_location_meta_service import get as get_meta
        meta = get_meta(chat_id)
        if meta and meta.place_name:
            return f"📍 本群地點名稱：「{meta.place_name}」"
        return "尚未設定地點名稱（提醒會用預設文案）。\n輸入：設定地點名稱 <名稱>"

    if text.startswith("設定診所 "):
        parts = text.split(" ")
        if len(parts) >= 3:
            try:
                lat = float(parts[1])
                lng = float(parts[2])
            except ValueError:
                return "❌ 經緯度格式錯誤，請使用：設定診所 <緯度> <經度>\n例如：設定診所 22.999 120.222"
            set_for_chat(chat_id, lat, lng)
            clear_wait(chat_id)
            return f"✅ 已設定診所座標：({lat}, {lng})\n之後群組有人傳位置時，會自動計算距離與到院時間。"
        else:
            return "❌ 格式錯誤，請使用：設定診所 <緯度> <經度>\n例如：設定診所 22.999 120.222"

    if text == "設定診所":
        set_wait_for_chat(chat_id)
        return ("請傳一則「位置訊息」(＋→位置資訊) 作為診所座標,\n"
                "或直接打字座標,例如:22.9908 120.2133（等待 10 分鐘有效）")

    # 等待設定診所狀態中,收到「純座標文字」也接受(空白或逗號分隔)
    # — 補 UX:不一定要傳 pin,打字座標也能設
    if is_waiting_for_location(chat_id):
        coords = re.split(r"[,\s]+", text.strip())
        if len(coords) == 2:
            try:
                lat = float(coords[0])
                lng = float(coords[1])
                # 合理範圍檢查(台灣約 lat 21-26、lng 119-122),擋掉誤輸入
                if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                    raise ValueError
            except ValueError:
                return None  # 不是合法座標 → 不攔,讓它走原本流程
            set_for_chat(chat_id, lat, lng)
            clear_wait(chat_id)
            return (f"✅ 已設定診所座標：({lat}, {lng})\n"
                    f"之後群組有人傳位置時，會自動計算距離與到院時間。")

    if text == "查看診所座標":
        rec = get_for_chat(chat_id)
        if not rec:
            return "尚未設定診所座標。請輸入：設定診所 22.999 120.222，或先輸入『設定診所』再傳位置。"
        ts = rec.updated_at.strftime("%Y-%m-%d %H:%M") if rec.updated_at else "未知時間"
        return f"🏥 診所座標：({rec.latitude}, {rec.longitude})\n更新時間：{ts}"

    if text == "清除診所座標":
        clear_for_chat(chat_id)
        clear_wait(chat_id)
        return "已清除診所座標。"

    # === 平均車速設定 ===
    if text.startswith("設定平均車速 "):
        parts = text.split(" ")
        if len(parts) >= 2:
            try:
                kmh = float(parts[1])
                if kmh <= 0:
                    return "❌ 速度需為正數（km/h）"
            except ValueError:
                return "❌ 速度格式錯誤，請使用：設定平均車速 <km/h>\n例如：設定平均車速 30"
            set_avg_speed(chat_id, kmh)
            return f"✅ 已設定平均車速：{kmh} km/h"
        else:
            return "❌ 格式錯誤，請使用：設定平均車速 <km/h>\n例如：設定平均車速 30"

    if text == "查看平均車速":
        chat_avg = get_avg_speed(chat_id)
        if chat_avg and chat_avg > 0:
            return f"🏎️ 本群組平均車速：{chat_avg} km/h"
        env_avg = float(os.getenv("AVG_SPEED_KMH", 30))
        return f"🏎️ 尚未設定本群組平均車速，使用全域預設：{env_avg} km/h"

    return None
