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

    # 路線
    body.append(_row("起點", t.start_point or '—'))
    if t.via_point:
        body.append(_row("途經", t.via_point))
    body.append(_row("終點", t.end_point or '—'))

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

    # ----- footer -----
    footer_buttons = _build_action_buttons(t)

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
    if footer_buttons:
        bubble["footer"] = {
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "contents": footer_buttons,
        }
    return bubble


def _build_action_buttons(t: TripView) -> List[dict]:
    """動作按鈕（依狀態 + 鎖定 條件渲染）— UI-2"""
    buttons = []

    # 鎖定中：不顯示狀態變更類按鈕
    if t.is_locked or t.display_status in ('已完成', '註銷'):
        return []

    # 「準備」狀態 → 給註銷/衝突/請假
    if t.display_status == '準備':
        for label, status, color in [
            ('❌ 註銷', '註銷', DANGER),
            ('⚠️ 衝突', '衝突', "#E65100"),
            ('🏷️ 請假', '請假', "#7B1FA2"),
        ]:
            buttons.append({
                "type": "button",
                "style": "secondary",
                "height": "sm",
                "action": {
                    "type": "postback",
                    "label": label,
                    "data": f"trip_status:{t.trip_id}:{status}",
                    "displayText": f"{label} #{t.trip_id}",
                }
            })

    # 「請假」狀態 → 給「恢復準備」
    elif t.display_status == '請假':
        buttons.append({
            "type": "button", "style": "secondary", "height": "sm",
            "action": {
                "type": "postback",
                "label": "↩️ 恢復準備",
                "data": f"trip_restore:{t.trip_id}",
                "displayText": f"恢復 #{t.trip_id}",
            }
        })

    return buttons


# ============================================================
# 2. 班次列表 carousel（按日分組）
# ============================================================

def render_trip_list_carousel(trips: List[TripView], *,
                               header_title: Optional[str] = None) -> dict:
    """
    多筆班次 → carousel（每日 1 bubble）

    1 筆 → 詳情卡
    2-12 天 → carousel
    > 12 天 → 取前 11 + 「還 N 天」
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

    bubbles = [_render_day_bubble(d, groups[d]) for d in order[:12]]

    if len(order) > 12:
        bubbles[-1] = _render_more_indicator(len(order) - 11, total_trips=len(trips))

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


def _render_day_bubble(d, trips_of_day: List[TripView]) -> dict:
    """一天的班次 bubble（每筆可 tap 至詳情）"""
    rows = []
    for t in trips_of_day[:13]:  # 一張卡最多 13 行
        rows.append(_trip_row(t))

    if len(trips_of_day) > 13:
        rows.append({
            "type": "text",
            "text": f"⋯ 還 {len(trips_of_day) - 13} 筆",
            "color": MUTED, "size": "xs", "align": "center", "margin": "sm",
        })

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
                "weight": "bold", "size": "md", "color": "#ffffff",
            }, {
                "type": "text",
                "text": f"{len(trips_of_day)} 筆",
                "size": "xs", "color": "#E0E0E0",
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
    route_text = f"{t.start_point or '?'}→{t.end_point or '?'}"
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
            {"type": "text", "text": t.status_emoji, "flex": 0, "size": "sm"},
            {"type": "text", "text": f"#{t.trip_id}", "flex": 2, "size": "xs",
             "color": color, "weight": "bold"},
            {"type": "text", "text": time_text, "flex": 2, "size": "xs",
             "color": BLACK},
            {"type": "text", "text": route_text, "flex": 5, "size": "xs",
             "color": BLACK, "wrap": False},
            {"type": "text", "text": driver_text, "flex": 2, "size": "xs",
             "color": MUTED, "align": "end"},
        ]
    }


def _render_more_indicator(remaining_days: int, total_trips: int) -> dict:
    return {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical",
            "alignItems": "center", "justifyContent": "center",
            "contents": [
                {"type": "text", "text": f"還有 {remaining_days} 天",
                 "weight": "bold", "size": "xl", "color": ACCENT},
                {"type": "text",
                 "text": f"（共 {total_trips} 筆，請縮小範圍）",
                 "size": "sm", "color": MUTED, "margin": "md", "wrap": True},
            ]
        }
    }
