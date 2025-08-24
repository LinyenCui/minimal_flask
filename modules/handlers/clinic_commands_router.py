import re
import logging
from modules.utils.line_bot import reply_text
from modules.services.group_location_meta_service import set_name as _set_name, set_template as _set_tpl, get as _get_meta
from modules.services.clinic_location_service import set_for_chat as _set_location
from modules.handlers.clinic_commands_handler import handle_clinic_commands as _legacy_handler

logger = logging.getLogger(__name__)


def handle_clinic_meta_commands(message_text: str, chat_id: str, reply_token: str) -> bool:
    """輕路由：群組地點/平均車速/模板等命令集中處理。
    回傳 True 表示已處理；False 表示未匹配（交回上層）。
    """
    if not isinstance(message_text, str):
        return False

    text = message_text.strip()

    # 通用地點設定：設定地點 名稱 緯度 經度 | 設定地點 名稱 (緯度, 經度)
    if text.startswith("設定地點"):
        s = text.replace("　", " ")
        s = re.sub(r"\s+", " ", s)
        m = re.match(r"^設定地點\s+(.+?)\s*[（(]\s*([+-]?\d+(?:\.\d+)?)\s*[,，]\s*([+-]?\d+(?:\.\d+)?)\s*[)）]\s*$", s)
        if m:
            name = m.group(1).strip()
            try:
                lat = float(m.group(2)); lng = float(m.group(3))
            except ValueError:
                reply_text(reply_token, "❌ 座標格式錯誤，請確認緯度與經度是數字")
                return True
        else:
            parts = s.split(" ")
            if len(parts) >= 4:
                name = " ".join(parts[1:-2]).strip()
                try:
                    lat = float(parts[-2]); lng = float(parts[-1])
                except ValueError:
                    reply_text(reply_token, "❌ 格式錯誤，請用：設定地點 名稱 緯度 經度\n例如：設定地點 東洋 23.0380103 120.1498142")
                    return True
            else:
                reply_text(reply_token, "❌ 格式錯誤，請用：設定地點 名稱 緯度 經度\n也可用括號：設定地點 東洋 (23.0380103, 120.1498142)")
                return True
        _set_location(chat_id, lat, lng)
        _set_name(chat_id, name or "診所")
        reply_text(reply_token, f"✅ 已設定地點：{name or '診所'}（{lat}, {lng}）")
        return True

    # 舊命令快速轉接：設定診所 <緯度> <經度>
    if text.startswith("設定診所 "):
        s = text.replace("　", " ")
        parts = [p for p in s.split() if p]
        if len(parts) >= 3:
            try:
                lat = float(parts[-2]); lng = float(parts[-1])
                _set_location(chat_id, lat, lng)
                _set_name(chat_id, "診所")
                reply_text(reply_token, f"✅ 已設定地點：診所（{lat}, {lng}）")
                return True
            except ValueError:
                pass
        # 交回舊處理器（可能是不帶座標的引導）
        legacy = _legacy_handler(text, chat_id)
        if legacy:
            reply_text(reply_token, legacy)
            return True
        return False

    # 地點名稱/到院訊息
    if text.startswith("設定地點名稱"):
        name = text[len("設定地點名稱"):].strip().replace("\u3000", " ")
        if not name:
            reply_text(reply_token, "❌ 請提供名稱，例如：設定地點名稱 診所")
            return True
        _set_name(chat_id, name)
        reply_text(reply_token, f"✅ 已設定地點名稱：{name}")
        return True

    if text.startswith("設定到院訊息"):
        tpl = text[len("設定到院訊息"):].lstrip()
        _set_tpl(chat_id, tpl)
        reply_text(reply_token, f"✅ 已更新到院訊息（長度 {len(tpl)}）")
        return True

    if text == "查看到院設定":
        meta = _get_meta(chat_id)
        name = (meta.place_name if meta else None) or "（未設定，預設：診所）"
        has_tpl = bool(meta and meta.message_template)
        length = len(meta.message_template) if has_tpl else 0
        tpl_desc = f"自訂模板：{'有' if has_tpl else '無'}（長度 {length}）"
        reply_text(reply_token, f"🏷️ 到院設定\n名稱：{name}\n{tpl_desc}")
        return True

    if text == "恢復預設到院訊息":
        _set_tpl(chat_id, None)
        reply_text(reply_token, "✅ 已恢復預設到院訊息")
        return True

    # 交給舊的 clinic handler（平均車速等）
    legacy = _legacy_handler(text, chat_id)
    if legacy:
        reply_text(reply_token, legacy)
        return True

    return False
