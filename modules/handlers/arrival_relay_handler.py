"""到院通知接送群 handler

業務設計：
  接送群 = 接送人員 + 司機 + bot 的專用群。
  ・司機在接送群傳位置 → bot reply 到院通知（免費）＋建事件
  ・司機忘記、跑回工作群傳 → 工作群照常回 ETA 卡，另 push 一則到綁定的
    接送群（fallback，吃額度）
  ・到院通知附 [✅ 收到] 按鈕；60 秒沒人按 → push 催促一次，再 60 秒沒按
    → 最後催一次後停（最多 2 次）
  ・接送群對其他一切訊息靜默（不進 AI、不理指令）— webhook 靜默閘在
    modules/routes/webhook.py，白名單 = 本檔 ACK_HANDLERS 的關鍵字

綁定流程（指令橋接照 clinic_commands 模式，webhook 群組閘門前攔）：
  工作群「設定到院轉發」→ 生成 4 位數配對碼（TTL 10 分鐘）
  接送群「綁定到院通知 XXXX」→ 驗碼 → set_relay(工作群, 本群)
  工作群「查看到院轉發」/「取消到院轉發」→ 查詢 / 解除

事件節流：同一接送群 20 分鐘內只建立一個事件（新位置釘不重發通知、
不重啟催促；工作群自己的 ETA reply 不受節流影響照常回）。
"""
import logging
import random
import re
import threading
import time
from typing import Dict, Optional

from modules.utils.line_bot import reply_text, reply_message

logger = logging.getLogger(__name__)

# ============================================================
# 配對碼（DB 版：存 database_maintenance key-value 表，TTL 10 分鐘、一次性）
#
# ⚠️ 為什麼不用記憶體 dict：prod 走 gunicorn/Docker，發碼與驗碼的請求可能
# 落在不同 worker/實例（2026-07-22 實測：接送群連換 4 組新碼全部「錯誤或
# 已過期」）。DB 版程序無關、重啟也不掉碼。key='relay_pair_<code>'、
# value=工作群 chat_id、timestamp=生成時間（TTL 用 SQL 比對，時鐘自洽）。
# ============================================================
PAIR_CODE_TTL_SEC = 10 * 60  # 文案顯示用；SQL 端同步寫死 INTERVAL '10 minutes'


def _prune_expired_codes() -> None:
    from modules.models.base import db
    from sqlalchemy import text as _sql
    db.session.execute(_sql(
        "DELETE FROM database_maintenance "
        "WHERE key LIKE 'relay_pair_%' "
        "  AND timestamp < NOW() - INTERVAL '10 minutes'"))
    db.session.commit()


def _gen_pair_code(work_chat_id: str) -> str:
    """生成 4 位數配對碼並登記（同工作群重打會生新碼，舊碼仍在 TTL 內有效）。"""
    from modules.models.base import db
    from sqlalchemy import text as _sql
    _prune_expired_codes()
    code = f"{random.randint(0, 9999):04d}"
    for _ in range(20):  # ON CONFLICT DO NOTHING → rowcount=0 表示撞碼，重生
        r = db.session.execute(_sql(
            "INSERT INTO database_maintenance (key, value, timestamp, description) "
            "VALUES (:k, :v, NOW(), '到院轉發配對碼（10 分鐘 TTL、一次性）') "
            "ON CONFLICT (key) DO NOTHING"),
            {'k': f'relay_pair_{code}', 'v': work_chat_id})
        if r.rowcount:
            db.session.commit()
            return code
        code = f"{random.randint(0, 9999):04d}"
    db.session.commit()
    raise RuntimeError('配對碼生成連撞 20 次（理論上不可能）')


def _pop_valid_code(code: str) -> Optional[str]:
    """驗碼（一次性：DELETE..RETURNING 原子取走）。合法 → 工作群 chat_id；錯誤/過期 → None。"""
    from modules.models.base import db
    from sqlalchemy import text as _sql
    row = db.session.execute(_sql(
        "DELETE FROM database_maintenance "
        "WHERE key = :k AND timestamp >= NOW() - INTERVAL '10 minutes' "
        "RETURNING value"),
        {'k': f"relay_pair_{(code or '').strip()}"}).fetchone()
    db.session.commit()
    return row[0] if row else None


# ============================================================
# 到院事件狀態（模組級 dict + Lock）
# key = (接送群 chat_id, 司機 user_id) → {started_at, acked, nag_count, timer}
# 節流按「司機」分開（2026-07-21 用戶需求；窗長 5 分鐘）：尖峰時段多車接連到達，
# 每台車都要各自通知；同一司機一趟連傳多次位置才被同窗吃掉。
# ============================================================
_EVENTS: Dict[tuple, dict] = {}
_EVENTS_LOCK = threading.Lock()
EVENT_THROTTLE_SEC = 5 * 60    # 同一（接送群×司機）5 分鐘內只建一個事件
NAG_INTERVAL_SEC = 60          # 催促間隔
MAX_NAGS = 2                   # 最多催 2 次
NAG_TEXT = "⏰ 提醒：來程車輛接近，尚未有人確認"


def start_arrival_event(relay_chat_id: str, driver_key: str = 'unknown') -> bool:
    """建立到院事件並排第一次催促。

    節流按（接送群×司機）：同司機 20 分鐘窗內已有事件 → 回 False
    （呼叫端不重發通知、不重啟催促）；不同司機各有各的窗，多車各自通知。
    回 True = 新事件已建立，催促計時已啟動。
    """
    if not relay_chat_id:
        return False
    key = (relay_chat_id, driver_key or 'unknown')
    now = time.time()
    old_timer = None
    with _EVENTS_LOCK:
        ev = _EVENTS.get(key)
        if ev and (now - ev['started_at']) < EVENT_THROTTLE_SEC:
            return False
        old_timer = ev.get('timer') if ev else None
        _EVENTS[key] = {
            'started_at': now, 'acked': False, 'nag_count': 0, 'timer': None,
        }
    if old_timer:
        try:
            old_timer.cancel()
        except Exception:
            pass
    _schedule_nag(key)
    logger.info(f"[relay] 到院事件建立: {relay_chat_id[:8]}… 司機={str(driver_key)[:8]}…")
    return True


def _schedule_nag(key: tuple) -> None:
    t = threading.Timer(NAG_INTERVAL_SEC, _nag, args=(key,))
    t.daemon = True
    with _EVENTS_LOCK:
        ev = _EVENTS.get(key)
        if ev is not None:
            ev['timer'] = t
    t.start()


def _nag(key: tuple) -> None:
    """催促計時到點：未 acked 且未達上限 → push 催促 + [✅ 收到]，再排下一次。"""
    with _EVENTS_LOCK:
        ev = _EVENTS.get(key)
        if not ev or ev['acked'] or ev['nag_count'] >= MAX_NAGS:
            return
        ev['nag_count'] += 1
        count = ev['nag_count']
    _push_to_relay(key[0], NAG_TEXT)  # push 失敗只 log，狀態機照走
    if count < MAX_NAGS:
        _schedule_nag(key)
    else:
        logger.info(f"[relay] 催促達上限（{MAX_NAGS} 次），停止: {key[0][:8]}…")


# ============================================================
# LINE 發送（reply 免費 / push 吃額度）
# ============================================================

def _ack_quick_reply():
    from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
    return QuickReply(items=[
        # label 加長讓圓片變大（顯示字）；text 維持「收到」（送出字/比對 key 不變）
        QuickReplyItem(action=MessageAction(label="✅ 收到，我去接", text="收到")),
    ])


def _build_ack_text_message(text: str, warn: Optional[str] = None):
    """到院通知 Flex 泡泡 + [✅ 收到] Quick Reply（一律泡泡 — 用戶定調求一致性）。

    warn（多車在途）→ 加一行紅色粗體警示；按鈕維持 Quick Reply
    （Flex 訊息一樣能掛，不產生常駐假按鈕）。
    """
    from linebot.v3.messaging import FlexMessage, FlexContainer
    contents = [{"type": "text", "text": text, "wrap": True, "size": "md"}]
    if warn:
        contents.append({"type": "text", "text": warn, "wrap": True, "size": "md",
                         "weight": "bold", "color": "#D32F2F", "margin": "md"})
    bubble = {
        "type": "bubble",
        "body": {"type": "box", "layout": "vertical", "contents": contents},
    }
    alt = f"{text[:40]}｜{warn[:18]}" if warn else text
    return FlexMessage(
        alt_text=alt[:400],
        contents=FlexContainer.from_dict(bubble),
        quick_reply=_ack_quick_reply(),
    )


def _push_to_relay(relay_chat_id: str, text: str,
                   warn: Optional[str] = None) -> None:
    """push 帶 [✅ 收到] 按鈕的文字到接送群。失敗只 log 不 raise。

    threading.Timer 的執行緒沒有 Flask app context（get_line_bot_api 讀
    current_app.config 會炸）→ 沒 context 時自己包一層。
    尊重 PUSH_NOTIFY 總開關（測試期關 push 省 LINE 月額度）。
    """
    try:
        from modules.utils.line_bot import (
            get_line_bot_api, push_notify_enabled,
        )
        if not push_notify_enabled():
            logger.info(f"[relay] push skipped (PUSH_NOTIFY off): {relay_chat_id[:8]}…")
            return
        from flask import has_app_context
        if has_app_context():
            api = get_line_bot_api()
        else:
            from app import app
            with app.app_context():
                api = get_line_bot_api()
        from linebot.v3.messaging import PushMessageRequest
        api.push_message(PushMessageRequest(
            to=relay_chat_id,
            messages=[_build_ack_text_message(text, warn=warn)],
        ))
        from modules.utils.push_stats import record_push
        record_push('relay', target_id=relay_chat_id)
        logger.info(f"[relay] pushed to {relay_chat_id[:8]}…")
    except Exception as e:
        logger.warning(f"[relay] push 失敗（只 log 不中斷）: {e}")


# ============================================================
# 位置釘 → 到院通知（location_message_handler 掛鉤點）
# ============================================================

def _open_event_count(relay_chat_id: str) -> int:
    """該接送群「在途」事件數 = 未確認且仍在節流窗內的事件（含剛建立的）"""
    now = time.time()
    with _EVENTS_LOCK:
        return sum(
            1 for key, ev in _EVENTS.items()
            if key[0] == relay_chat_id and not ev['acked']
            and (now - ev['started_at']) < EVENT_THROTTLE_SEC
        )


def _multi_car_warn(relay_chat_id: str) -> Optional[str]:
    """多車在途時的警示行（紅字用）— 按「收到」是一鍵全確認，要講明白"""
    n = _open_event_count(relay_chat_id)
    if n > 1:
        return f"⚠️ 目前在途共 {n} 趟（含先前未確認），按「收到」視為全部確認"
    return None


def notify_relay_by_reply(reply_token: str, relay_chat_id: str, text: str,
                          driver_key: str = 'unknown') -> None:
    """(a) 司機把位置釘直接發在接送群 → reply 到院通知（免費）+ 建事件。

    節流窗內已有「同司機」事件 → 不重發通知、不重啟催促（保持靜默）。
    """
    if not start_arrival_event(relay_chat_id, driver_key):
        logger.info(f"[relay] 節流中，接送群位置釘不重發通知: {relay_chat_id[:8]}…")
        return
    reply_message(reply_token, [_build_ack_text_message(text, warn=_multi_car_warn(relay_chat_id))])


def notify_relay_by_push(relay_chat_id: str, text: str,
                         driver_key: str = 'unknown') -> None:
    """(b) 位置釘發在有綁定的工作群 → push 通知到接送群（fallback，吃額度）。

    過「同司機」節流才推；push 失敗只 log。工作群自己的 ETA reply 由呼叫端照常回。
    """
    if not start_arrival_event(relay_chat_id, driver_key):
        logger.info(f"[relay] 節流中，不重 push 到接送群: {relay_chat_id[:8]}…")
        return
    _push_to_relay(relay_chat_id, text, warn=_multi_car_warn(relay_chat_id))


# ============================================================
# 接送群白名單文字（「收到」確認）
# ============================================================

def _resolve_member_name(chat_id: str, user_id: Optional[str]) -> Optional[str]:
    """查按「收到」的人的顯示名稱。

    群組/聊天室用 member profile API（成員不用加 bot 好友也查得到）；
    失敗退 get_user_display_name；再失敗回 None（文案退回無名版）。
    """
    if not user_id:
        return None
    try:
        from modules.utils.line_bot import get_line_bot_api
        api = get_line_bot_api()
        if chat_id and chat_id.startswith('C'):
            prof = api.get_group_member_profile(chat_id, user_id)
            return getattr(prof, 'display_name', None)
        if chat_id and chat_id.startswith('R'):
            prof = api.get_room_member_profile(chat_id, user_id)
            return getattr(prof, 'display_name', None)
    except Exception:
        logger.info("member profile 查詢失敗，退 get_user_display_name", exc_info=True)
    try:
        from modules.utils.line_bot import get_user_display_name
        return get_user_display_name(user_id)
    except Exception:
        return None


def _ack_received(reply_token: str, relay_chat_id: str,
                  user_id: Optional[str] = None) -> None:
    """[✅ 收到] — 確認該接送群「全部」進行中事件、停止所有催促。

    多車接連到達時各有各的事件，一個「收到」視為人員已注意到通知，全數確認。
    """
    timers = []
    with _EVENTS_LOCK:
        for key, ev in _EVENTS.items():
            if key[0] == relay_chat_id and not ev['acked']:
                ev['acked'] = True
                if ev.get('timer'):
                    timers.append(ev['timer'])
                ev['timer'] = None
    for t in timers:
        try:
            t.cancel()
        except Exception:
            pass
    name = _resolve_member_name(relay_chat_id, user_id)
    reply_text(reply_token, f"👌 {name} 已確認" if name else "👌 已確認")


# 關鍵字 → 處理器（接送群靜默閘的白名單，加 entry 即自動放行）。
# 🔧 延伸鉤子：未來「已接到乘客」等回報要加在這裡，例如：
#   '已接到乘客': _ack_picked_up,   # ← 只留結構，尚未實作
#   （處理器簽名：fn(reply_token, relay_chat_id, user_id)）
ACK_HANDLERS = {
    '收到': _ack_received,
    '確定': _ack_received,   # 手錶罐頭回覆常見詞（僅接送群靜默閘內生效，別處不受影響）
}


def handle_ack(reply_token: str, relay_chat_id: str, text: str,
               user_id: Optional[str] = None) -> bool:
    """接送群文字入口。認得關鍵字 → 處理並回 True；不認得 → False（呼叫端靜默跳過）。"""
    key = (text or '').strip().lstrip('/').strip()
    handler = ACK_HANDLERS.get(key)
    if not handler:
        return False
    handler(reply_token, relay_chat_id, user_id)
    return True


# ============================================================
# 綁定指令（webhook 群組閘門前的 PATCH 區攔，照 clinic_commands 模式）
# ============================================================

def _normalize_spaces(s: str) -> str:
    s = s.replace("　", " ")  # 全形空白轉半形
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def handle_relay_commands(message_text: str, chat_id: str) -> Optional[str]:
    """處理到院轉發綁定指令。命中 → 回覆文字；不命中 → None。"""
    from modules.services.group_location_meta_service import (
        set_relay, clear_relay, get_relay_of, find_work_by_relay,
    )
    text = _normalize_spaces(message_text)

    if text == '設定到院轉發':
        if find_work_by_relay(chat_id):
            return "❌ 本群是接送群，請到「工作群」輸入：設定到院轉發"
        code = _gen_pair_code(chat_id)
        return (
            "🚐 到院轉發設定\n"
            f"配對碼：{code}（10 分鐘內有效）\n\n"
            "請把機器人拉進接送群後，在該群輸入：\n"
            f"綁定到院通知 {code}"
        )

    if text.startswith('綁定到院通知'):
        code = text[len('綁定到院通知'):].strip()
        if not code:
            return ("請輸入：綁定到院通知 <配對碼>\n"
                    "（配對碼由工作群輸入「設定到院轉發」取得）")
        work_chat_id = _pop_valid_code(code)
        if not work_chat_id:
            return "❌ 配對碼錯誤或已過期，請回工作群重新輸入「設定到院轉發」"
        if work_chat_id == chat_id:
            return "❌ 請在「接送群」輸入綁定指令（不能把工作群綁定成自己的接送群）"
        set_relay(work_chat_id, chat_id)
        return (
            "✅ 綁定完成！本群已成為到院通知接送群。\n"
            "・司機在本群傳位置 → 立即收到到院通知\n"
            "・司機在工作群傳位置 → 通知也會轉發到本群\n"
            "・收到通知請點 [✅ 收到] 確認（60 秒未確認會提醒，最多 2 次）\n"
            "・本群其他訊息機器人一律靜默"
        )

    if text == '查看到院轉發':
        relay = get_relay_of(chat_id)
        if relay:
            return (f"📡 本群已綁定接送群（ID 末碼 …{relay[-6:]}）\n"
                    "取消請輸入：取消到院轉發")
        work = find_work_by_relay(chat_id)
        if work:
            return f"🚐 本群是接送群（綁定工作群 ID 末碼 …{work[-6:]}）"
        return ("尚未設定到院轉發。\n"
                "在工作群輸入「設定到院轉發」取得配對碼。")

    if text == '取消到院轉發':
        if not get_relay_of(chat_id):
            return "本群沒有綁定中的到院轉發。"
        clear_relay(chat_id)
        return "✅ 已取消到院轉發綁定。"

    return None
