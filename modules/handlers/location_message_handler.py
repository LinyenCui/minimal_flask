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
        relay_work_id = None  # 本 chat 若是「到院通知接送群」→ 綁定的工作群 chat_id
        if not clinic:
            # 接送群 fallback：自己查無座標時，用綁定工作群的座標與地點名稱
            #（顯示行為與工作群一致）
            try:
                from modules.services.group_location_meta_service import find_work_by_relay
                _work = find_work_by_relay(chat_id)
                if _work:
                    clinic = get_for_chat(_work)
                    if clinic:
                        relay_work_id = _work
            except Exception:
                logger.warning("接送群座標 fallback 失敗", exc_info=True)
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
        # 讀取群組到院模板（接送群沿用綁定工作群的地點名稱/模板）
        from modules.services.group_location_meta_service import get as get_meta
        from modules.services.arrival_template import render_arrival_message
        meta = get_meta(relay_work_id or chat_id)
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

        # (a) 位置釘發在接送群 → reply 到院通知（免費）+ [✅ 收到] + 建事件
        #（節流按司機分開：同司機 20 分鐘窗內不重發；多車各自通知）；不走下面的 Flex 卡
        if relay_work_id:
            try:
                from modules.handlers.arrival_relay_handler import notify_relay_by_reply
                _driver = getattr(event.source, 'user_id', None) or 'unknown'
                notify_relay_by_reply(event.reply_token, chat_id, text, driver_key=_driver)
            except Exception:
                logger.error("接送群到院通知失敗", exc_info=True)
            return

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

        # (b) 位置釘發在有綁定接送群的工作群 → 工作群照常回 ETA（上面已回），
        # 另 push 一則通知到綁定的接送群（fallback，吃額度；同司機過節流才推）
        try:
            from modules.services.group_location_meta_service import get_relay_of
            from modules.handlers.arrival_relay_handler import notify_relay_by_push
            _relay = get_relay_of(chat_id)
            if _relay:
                _driver = getattr(event.source, 'user_id', None) or 'unknown'
                notify_relay_by_push(_relay, text, driver_key=_driver)
        except Exception:
            logger.error("到院通知轉發接送群失敗", exc_info=True)
    except Exception as e:
        logger.error(f"處理位置訊息失敗: {e}")
        reply_text(event.reply_token, "❌ 無法處理位置訊息，請稍後再試")
