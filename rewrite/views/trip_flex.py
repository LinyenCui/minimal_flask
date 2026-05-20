"""
班次相關 Flex Message 渲染器

提供：
  render_trip_detail(trip)           — 單筆詳情 bubble
  render_trip_list_carousel(trips)   — 多筆 carousel（按日分組）
"""

from collections import defaultdict
from typing import List, Optional
from rewrite.tools.trip import TripView, LOCK_MINUTES


# 主題色
PRIMARY = "#1565C0"
ACCENT = "#FF6D00"
DANGER = "#D32F2F"
SUCCESS = "#2E7D32"
MUTED = "#999999"
BLACK = "#333333"

# 狀態著色
STATUS_COLOR = {
    '準備': SUCCESS,
    '已完成': MUTED,
    '註銷': DANGER,
    '衝突': DANGER,
    '待派': "#E65100",   # 橘紅
    '請假': "#7B1FA2",   # 紫
}

WEEKDAY_TC = ['一', '二', '三', '四', '五', '六', '日']


# ============================================================
# 共用元件
# ============================================================

def _row(label: str, value: str, *, value_color: str = BLACK,
         value_weight: str = "regular", label_color: str = "#666666") -> dict:
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "contents": [
            {"type": "text", "text": label, "size": "sm",
             "color": label_color, "flex": 2},
            {"type": "text", "text": value, "size": "sm",
             "color": value_color, "weight": value_weight,
             "flex": 5, "wrap": True},
        ]
    }


def _separator(margin: str = "md"):
    return {"type": "separator", "margin": margin}


def _format_date_with_weekday(d):
    if not d:
        return '—'
    return f"{d.month}/{d.day} (星期{WEEKDAY_TC[d.weekday()]})"


def _format_money(v: Optional[int]) -> str:
    if v is None:
        return '—'
    return f"{v:+d} 元" if v < 0 else f"{v} 元"


# ============================================================
# 1. 班次詳情卡（單筆）
# ============================================================

def render_trip_detail(t: TripView) -> dict:
    """單筆班次詳情 → Flex Bubble"""
    body = []

    # 日期 + 時間
    body.append(_row("日期", _format_date_with_weekday(t.date)))
    body.append(_row("時間", str(t.time)[:5] if t.time else '—'))

    # 路線（temp 班次用 custom_*，避開「臨時地點」placeholder）
    sp, vp, ep = t.display_route()
    body.append(_row("起點", sp or '—'))
    if vp:
        body.append(_row("途經", vp))
    body.append(_row("終點", ep or '—'))

    body.append(_separator())

    # 狀態（三層障眼法）
    status_color = STATUS_COLOR.get(t.display_status, BLACK)
    status_text = f"{t.status_emoji} {t.display_status or '—'}"
    body.append(_row("狀態", status_text, value_color=status_color, value_weight="bold"))

    # 司機
    driver_text = f"#{t.driver_id}" if t.driver_id else '—'
    body.append(_row("司機", driver_text))

    # 車資
    body.append(_row("基本車資",
                     f"{t.meter_fare} 元" if t.meter_fare is not None else '—'))
    body.append(_row("加成", _format_money(t.extra_fare)))
    if t.actual_fare is not None and t.actual_fare != t.meter_fare:
        body.append(_row("實際車資", f"{t.actual_fare} 元",
                         value_color=PRIMARY, value_weight="bold"))

    # 類別
    body.append(_row("類別", t.category or '—'))

    # 請假/乘客資訊
    if t.passenger_leave_reason:
        body.append(_row("📝 請假原因", t.passenger_leave_reason,
                         value_color=STATUS_COLOR.get('請假')))
    if t.passenger_name:
        body.append(_row("乘客", t.passenger_name))

    # 鎖定提示（R-5）
    if t.is_locked:
        body.append(_separator())
        body.append({
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#FFEBEE",
            "paddingAll": "sm",
            "cornerRadius": "md",
            "contents": [{
                "type": "text",
                "text": f"⏰ 執行前 {LOCK_MINUTES} 分鐘內不可修改狀態（還有 {t.minutes_until_trip} 分執行）",
                "color": DANGER, "size": "sm", "weight": "bold", "wrap": True
            }]
        })

    bubble: dict = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": PRIMARY,
            "paddingAll": "md",
            "contents": [{
                "type": "text",
                "text": f"🚖 班次 #{t.trip_id} 詳情",
                "weight": "bold", "size": "lg", "color": "#ffffff",
            }]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": body,
        }
    }
    return bubble


# ============================================================
# 動作 Quick Reply（attach 到 reply message，不放 flex bubble footer）
# ============================================================

def build_trip_quick_reply(t: TripView, event_source=None) -> Optional[dict]:
    """
    依 trip 狀態產生 quickReply 物件（給 reply_message 附帶）

    狀態決策表（同 LIFF trip_status_form.html 的 validActionsFor）：
      已完成 / 鎖內              → 無
      鎖外 + 準備                → [⚙️ 狀態管理]（LIFF；form 內可選 請假/註銷/衝突）
      鎖外 + 請假/衝突/註銷      → [⚙️ 狀態管理]（LIFF；form 內可選 改回準備）
      其他                       → 無

    LIFF_ID 已設 → 一律一顆「狀態管理」LIFF URI 按鈕（請假含 reason+加成 chip，
    註銷/衝突 reason 可空，改回準備直接執行；都在 form 裡決定）。
    LIFF_ID 未設 → fallback 到原本的多顆文字 quick reply（backward compat）。

    event_source: webhook event.source（或 LIFF payload source dict），給
    build_liff_url 帶 gid/rid 用，缺則 LIFF 內 push 會 fallback 到使用者私聊。
    """
    if t.display_status == '已完成' or t.is_locked:
        return None

    if t.display_status == '準備':
        has_action = True
    elif t.display_status in ('請假', '衝突', '註銷'):
        has_action = True
    else:
        has_action = False
    if not has_action:
        return None

    # 優先用 LIFF 統一狀態管理面板
    from rewrite.views.customer_flex import _liff_id
    liff_id = _liff_id()
    if liff_id:
        from rewrite.utils.liff_url import build_liff_url
        uri = build_liff_url(
            liff_id, 'trip_status', event_source,
            extra_params={'trip_id': t.trip_id},
        )
        return {"items": [_qr_uri("⚙️ 狀態管理", uri)]}

    # Fallback（LIFF_ID 未設）：原文字 quick reply
    items = []
    if t.display_status == '準備':
        items.append(_qr_msg("❌ 註銷", f"班次註銷 {t.trip_id}"))
        items.append(_qr_msg("⚠️ 衝突", f"班次衝突 {t.trip_id}"))
        items.append(_qr_msg("🏷️ 請假", f"班次請假 {t.trip_id}"))
    elif t.display_status in ('請假', '衝突', '註銷'):
        items.append(_qr_msg("↩️ 改回準備", f"班次恢復 {t.trip_id}"))
    return {"items": items} if items else None


def _qr_msg(label: str, text: str) -> dict:
    """quickReply 的 message action item（按了發送 text 給 bot）"""
    return {
        "type": "action",
        "action": {"type": "message", "label": label, "text": text},
    }


def _qr_uri(label: str, uri: str) -> dict:
    """quickReply 的 uri action item（按了開 LIFF / 外部連結）"""
    return {
        "type": "action",
        "action": {"type": "uri", "label": label, "uri": uri},
    }


# 註：原本有 build_trip_list_batch_quick_reply (批次狀態管理 LIFF 入口),
# 因 iOS LIFF WebView 對同頁多次 fetch() 不穩、prefetch 失敗回退;
# 明天改走 Alternative A (單一 batch GET endpoint,前端只打一次 fetch)再加回。
# 批次 LIFF 後端 (rewrite/handlers/liff/trip.py 的 trip_batch_status_form
# 與 templates/liff/trip_batch_status_form.html) 暫保留作休眠,等明天接 A 方案。


# ============================================================
# 2. 班次列表 carousel（按日分組）
# ============================================================

PER_BUBBLE = 13   # 一張 bubble 最多裝 13 筆班次（同日超過會拆頁）
MAX_BUBBLES = 12  # carousel 最多 12 張 bubble


def render_trip_list_carousel(trips: List[TripView], *,
                               header_title: Optional[str] = None) -> dict:
    """
    多筆班次 → carousel

    分頁規則：
      1 筆               → 詳情卡
      同日 ≤ 13 筆        → 1 張 bubble
      同日 > 13 筆        → 拆多張 bubble，header 標 「第 X/Y 頁」
      跨日多筆            → 每日依上述規則展開
      總 bubble > 12     → 截 11 + 「還 N 頁」提示
    """
    if not trips:
        return _empty_bubble(header_title or "查詢結果")

    if len(trips) == 1:
        return render_trip_detail(trips[0])

    # 按日期分組（保持原順序）
    groups = defaultdict(list)
    order = []
    for t in trips:
        if t.date not in groups:
            order.append(t.date)
        groups[t.date].append(t)

    # 展開：每日依 PER_BUBBLE 拆頁
    bubbles = []
    for d in order:
        day_trips = groups[d]
        n_pages = (len(day_trips) + PER_BUBBLE - 1) // PER_BUBBLE
        for i in range(n_pages):
            page = day_trips[i * PER_BUBBLE:(i + 1) * PER_BUBBLE]
            page_info = (i + 1, n_pages, len(day_trips)) if n_pages > 1 else None
            bubbles.append(_render_day_bubble(d, page, page_info=page_info))

    # carousel 上限 12 張
    if len(bubbles) > MAX_BUBBLES:
        bubbles = bubbles[:MAX_BUBBLES - 1] + [
            _render_more_indicator(len(bubbles) - (MAX_BUBBLES - 1), total_trips=len(trips))
        ]

    if len(bubbles) == 1:
        return bubbles[0]
    return {"type": "carousel", "contents": bubbles}


def _empty_bubble(title: str) -> dict:
    return {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical",
            "contents": [
                {"type": "text", "text": title, "weight": "bold", "size": "lg"},
                {"type": "text", "text": "無資料", "color": MUTED, "margin": "md"},
            ]
        }
    }


def _render_day_bubble(d, trips_of_day: List[TripView], *,
                        page_info: Optional[tuple] = None) -> dict:
    """
    一天的班次 bubble（每筆可 tap 至詳情）

    page_info: (page_no, total_pages, total_count)，None 表單頁
    """
    rows = [_trip_row(t) for t in trips_of_day]

    sub_text = f"{len(trips_of_day)} 筆"
    if page_info:
        page_no, total_pages, total_count = page_info
        sub_text = f"第 {page_no}/{total_pages} 頁（共 {total_count} 筆）"

    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": PRIMARY,
            "paddingAll": "sm",
            "contents": [{
                "type": "text",
                "text": f"📅 {_format_date_with_weekday(d)}",
                "weight": "bold", "size": "sm", "color": "#ffffff",
            }, {
                "type": "text",
                "text": sub_text,
                "size": "xxs", "color": "#E0E0E0",
            }]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "xs",
            "contents": rows,
        }
    }


def _trip_row(t: TripView) -> dict:
    """Carousel 內一行班次（可 tap）"""
    time_text = str(t.time)[:5] if t.time else '—:—'
    driver_text = f"🚗{t.driver_id}" if t.driver_id else "🚗?"
    sp, _, ep = t.display_route()
    route_text = f"{sp or '?'}→{ep or '?'}"
    color = STATUS_COLOR.get(t.display_status, BLACK)

    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "xs",
        "paddingTop": "xs",
        "paddingBottom": "xs",
        "action": {
            "type": "postback",
            "label": f"#{t.trip_id} 詳情",
            "data": f"trip_detail:{t.trip_id}",
            "displayText": f"班次詳情 {t.trip_id}",
        },
        "contents": [
            {"type": "text", "text": t.status_emoji, "flex": 0, "size": "xs"},
            {"type": "text", "text": f"#{t.trip_id}", "flex": 2, "size": "xxs",
             "color": color, "weight": "bold"},
            {"type": "text", "text": time_text, "flex": 2, "size": "xxs",
             "color": BLACK},
            {"type": "text", "text": route_text, "flex": 5, "size": "xxs",
             "color": BLACK, "wrap": False},
            {"type": "text", "text": driver_text, "flex": 2, "size": "xxs",
             "color": MUTED, "align": "end"},
        ]
    }


def _render_more_indicator(remaining_bubbles: int, total_trips: int) -> dict:
    """超過 carousel 上限的提示 bubble（取代被截掉的最後一頁）"""
    return {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical",
            "alignItems": "center", "justifyContent": "center",
            "contents": [
                {"type": "text", "text": f"還有 {remaining_bubbles} 頁",
                 "weight": "bold", "size": "lg", "color": ACCENT},
                {"type": "text",
                 "text": f"（共 {total_trips} 筆，請縮小日期範圍）",
                 "size": "xs", "color": MUTED, "margin": "md", "wrap": True},
            ]
        }
    }
