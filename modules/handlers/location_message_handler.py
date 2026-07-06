import logging
import os
from modules.services.clinic_location_service import get_for_chat, set_for_chat
from modules.handlers.clinic_commands_handler import is_waiting_for_location, clear_wait
from modules.services.chat_settings_service import get_avg_speed
from modules.services.distance_service import Point
from modules.services.provider_factory import get_distance_provider
from modules.utils.line_bot import reply_text, reply_message

logger = logging.getLogger(__name__)


def _get_chat_id(event) -> str:
    if hasattr(event.source, 'group_id') and event.source.group_id:
        return event.source.group_id
    if hasattr(event.source, 'room_id') and event.source.room_id:
        return event.source.room_id
    return getattr(event.source, 'user_id', None)


def handle_location_message(event):
    """處理來自LINE的 LocationMessage。"""
    try:
        chat_id = _get_chat_id(event)
        title = getattr(event.message, 'title', None) or getattr(event.message, 'address', None) or '位置'
        addr = getattr(event.message, 'address', None)
        lat = float(getattr(event.message, 'latitude'))
        lng = float(getattr(event.message, 'longitude'))
        logger.info(f"[location] chat_id={chat_id} lat={lat} lng={lng} title={title}")

        # 若正在等待設定診所座標，則將此位置存為診所
        if is_waiting_for_location(chat_id):
            set_for_chat(chat_id, lat, lng, address=addr)
            clear_wait(chat_id)
            reply_text(event.reply_token, f"✅ 已設定診所座標：({lat}, {lng})")
            return

        clinic = get_for_chat(chat_id)
        if not clinic:
            # 尚未設定診所：提供引導與 Quick Reply
            try:
                from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction, TextMessage
                quick = QuickReply(items=[QuickReplyItem(action=MessageAction(label="設定診所", text="設定診所"))])
                reply_message(event.reply_token, [TextMessage(text="尚未設定診所座標，請輸入：設定診所", quick_reply=quick)])
            except Exception:
                reply_text(event.reply_token, "尚未設定診所座標，請輸入：設定診所")
            return

        # 計算距離與 ETA（provider）
        arrival_log = logging.getLogger("arrival")
        arrival_log.info("enter location flow")
        provider = get_distance_provider()
        chat_avg = get_avg_speed(chat_id)
        origin = Point(latitude=lat, longitude=lng)
        dest = Point(latitude=clinic.latitude, longitude=clinic.longitude)

        provider_label = "本地直線"
        speed_note = ""
        used_speed = None
        try:
            distance = provider.distance_km(origin, dest)
            # 依 provider 實際結果設定文案
            if provider.label == "Google 路線":
                eta_min_val = provider.eta_min(distance, chat_avg)
                provider_label = "Google 路線"
                speed_note = "（以 Google 路線預估）"
                used_speed = None
            else:
                used_speed = chat_avg or float(os.getenv("AVG_SPEED_KMH", 30))
                eta_min_val = provider.eta_min(distance, chat_avg)
                provider_label = "本地直線"
                speed_note = f"（平均 {used_speed} km/h）"
        except Exception:
            # 回退到本地估算，避免沉默失敗
            arrival_log.error("provider calc failed", exc_info=True)
            from modules.services.geo_utils import haversine_km, eta_minutes
            distance = haversine_km(lat, lng, clinic.latitude, clinic.longitude)
            used_speed = chat_avg or float(os.getenv("AVG_SPEED_KMH", 30))
            eta_min_val = eta_minutes(distance, used_speed)
            provider_label = "本地直線"
            speed_note = f"（平均 {used_speed} km/h）"
        finally:
            arrival_log.info(f"exit location flow provider={provider_label}")

        # Google Maps 方向連結
        maps_url = (
            "https://www.google.com/maps/dir/?api=1&destination="
            f"{clinic.latitude},{clinic.longitude}&origin={lat},{lng}"
        )
        # 讀取群組到院模板
        from modules.services.group_location_meta_service import get as get_meta
        from modules.services.arrival_template import render_arrival_message
        meta = get_meta(chat_id)
        place_name = (meta.place_name if meta else None) or "診所"
        text = render_arrival_message(
            place_name,
            (meta.message_template if meta else None),
            {
                "place_name": place_name,
                "name": place_name,
                "distance_km": round(distance, 1),
                "eta_min": int(eta_min_val),
                "provider": provider_label,
                "speed": used_speed,
            },
        )

        # Flex 標題一律帶地點名稱（未命名預設「診所」，不特殊對待 — 用戶指示）
        header_text = f"🚗 注意：來程車輛接近「{place_name}」"

        # 文字為主，Flex 可選
        try:
            from linebot.v3.messaging import FlexMessage, FlexContainer, URIAction, ButtonComponent, BoxComponent, TextComponent
            flex = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": header_text, "weight": "bold", "size": "lg", "wrap": True},
                        {"type": "text", "text": f"距離：約 {distance:.1f} 公里", "margin": "md"},
                        {"type": "text", "text": f"ETA：約 {eta_min_val} 分", "margin": "sm"},
                        {"type": "text", "text": (f"提供者：{provider_label} {speed_note}").strip(), "size": "xs", "color": "#666666", "margin": "sm"},
                        {"type": "text", "text": f"司機位置：{title}", "wrap": True, "margin": "sm"},
                        {"type": "button", "style": "primary", "action": {"type": "uri", "label": "開啟 Google 地圖", "uri": maps_url}, "margin": "md"}
                    ]
                }
            }
            msg = {
                "type": "flex",
                "altText": header_text,
                "contents": flex
            }
            reply_message(event.reply_token, [msg])
        except Exception:
            reply_text(event.reply_token, text + f"\n地圖：{maps_url}")
    except Exception as e:
        logger.error(f"處理位置訊息失敗: {e}")
        reply_text(event.reply_token, "❌ 無法處理位置訊息，請稍後再試")
