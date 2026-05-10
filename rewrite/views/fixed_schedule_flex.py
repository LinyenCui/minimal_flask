"""固定班次（fixed_schedule）Flex

提供：
  render_new_fixed_schedule_entry(event_source=None)
    !新增固定班次 入口 Quick Reply
  render_fixed_schedule_detail(view, event_source=None)
    單筆詳情 bubble（含 編輯 / 請假 / 恢復 按鈕）
  render_fixed_schedule_list_carousel(views, event_source=None)
    多筆 carousel
"""
from collections import defaultdict
from typing import List, Optional
from rewrite.tools.fixed_schedule import FixedScheduleView
from rewrite.utils.liff_url import build_liff_url
from rewrite.views.customer_flex import _liff_id


# 主題色（未來態用紫色，跟過去態橘色 + 現在態藍色區分）
PRIMARY = "#6A1B9A"        # 紫
ACCENT = "#06C755"          # LINE 綠（按鈕）
LEAVE = "#7B1FA2"           # 請假紫
DANGER = "#D32F2F"
SUCCESS = "#2E7D32"
MUTED = "#999999"
BLACK = "#333333"

WEEKDAY_TC = ['一', '二', '三', '四', '五', '六', '日']
PER_BUBBLE = 1   # 每筆一張 bubble，方便附按鈕
MAX_BUBBLES = 12


def _new_fixed_schedule_liff_url(event_source=None) -> str:
    return build_liff_url(_liff_id(), 'new_schedule', event_source)


def _edit_liff_url(schedule_id: int, event_source=None) -> str:
    return build_liff_url(_liff_id(), 'edit_schedule', event_source, extra_params={'id': schedule_id})


def _leave_liff_url(schedule_id: int, event_source=None) -> str:
    return build_liff_url(_liff_id(), 'leave_schedule', event_source, extra_params={'id': schedule_id})


def _format_route_number(rn: Optional[str]) -> str:
    """'147' → '一/四/日'"""
    if not rn:
        return '—'
    wd_map = {'1': '一', '2': '二', '3': '三', '4': '四',
              '5': '五', '6': '六', '7': '日'}
    return '/'.join(wd_map.get(c, c) for c in rn)


def _short_route(view: FixedScheduleView) -> str:
    parts = [view.start_point or '?']
    if view.via_point:
        parts.append(f"經{view.via_point}")
    parts.append(view.end_point or '?')
    return '→'.join(p for p in parts if p)


def render_new_fixed_schedule_entry(event_source=None) -> dict:
    """!新增固定班次 觸發的 LINE message：text + Quick Reply

    Args:
        event_source: webhook event.source；群組裡觸發傳了，新增完才會 push 回群組。
    """
    if not _liff_id():
        from rewrite.views.customer_flex import _liff_unavailable_bubble
        return {
            'type': 'flex',
            'altText': '⚠️ LIFF 未設定',
            'contents': _liff_unavailable_bubble('新增固定班次表單'),
        }

    return {
        'type': 'quick_reply',
        'text': '📅 點下方按鈕新增固定班次模板',
        'quick_reply': {
            'items': [{
                'type': 'action',
                'action': {
                    'type': 'uri',
                    'label': '📝 開填寫表單',
                    'uri': _new_fixed_schedule_liff_url(event_source=event_source),
                },
            }],
        },
    }


# ============================================================
# 共用元件
# ============================================================

def _row(label: str, value: str, *, value_color: str = BLACK,
         value_weight: str = "regular") -> dict:
    return {
        "type": "box", "layout": "horizontal", "spacing": "sm",
        "contents": [
            {"type": "text", "text": label, "size": "sm", "color": "#666666", "flex": 2},
            {"type": "text", "text": value, "size": "sm", "color": value_color,
             "weight": value_weight, "flex": 5, "wrap": True},
        ],
    }


def _separator(margin: str = "md"):
    return {"type": "separator", "margin": margin}


def _build_action_buttons(view: FixedScheduleView, event_source=None) -> list:
    """根據 status 動態生按鈕（footer 內）

    準備     → 編輯 + 請假
    請假/註銷 → 編輯 + 恢復
    其他     → 只有編輯
    """
    btns = [{
        "type": "button", "style": "primary", "height": "sm",
        "color": ACCENT,
        "action": {"type": "uri", "label": "📝 編輯",
                   "uri": _edit_liff_url(view.id, event_source=event_source)},
    }]

    status = view.status or ''
    if status == '準備':
        btns.append({
            "type": "button", "style": "secondary", "height": "sm",
            "action": {"type": "uri", "label": "🏷️ 請假",
                       "uri": _leave_liff_url(view.id, event_source=event_source)},
        })
    elif status in ('請假', '註銷'):
        btns.append({
            "type": "button", "style": "secondary", "height": "sm",
            "action": {
                "type": "message", "label": "↩️ 恢復",
                "text": f"固定班次恢復 {view.id}",
            },
        })
    return btns


# ============================================================
# 詳情卡（單筆）
# ============================================================

def render_fixed_schedule_detail(view: FixedScheduleView, event_source=None) -> dict:
    """單筆固定班次 → bubble（含 編輯 / 請假 / 恢復 按鈕）

    event_source 傳了，編輯/請假按鈕的 LIFF URL 會帶 gid/rid，
    submit 後 push 才會回到原群組（不是操作者私聊）。
    """
    body = []

    body.append(_row("週幾", _format_route_number(view.route_number)))
    body.append(_row("時間", str(view.departure_time)[:5] if view.departure_time else '—'))
    body.append(_row("起點", view.start_point or '—'))
    if view.via_point:
        body.append(_row("途經", view.via_point))
    body.append(_row("終點", view.end_point or '—'))

    body.append(_separator())
    body.append(_row("狀態",
                     f"{view.status_emoji} {view.status or '—'}",
                     value_color=LEAVE if view.status == '請假' else
                                 DANGER if view.status == '註銷' else SUCCESS,
                     value_weight="bold"))
    body.append(_row("類別", view.category or '—'))
    body.append(_row("司機", str(view.driver_id) if view.driver_id else '—'))
    if view.direction:
        body.append(_row("方向", view.direction))

    if view.base_fare is not None or view.surcharge is not None:
        body.append(_separator())
        if view.base_fare is not None:
            body.append(_row("基本車資", f"{view.base_fare} 元"))
        if view.surcharge is not None and view.surcharge != 0:
            body.append(_row("加成", f"{view.surcharge:+d} 元",
                             value_color=LEAVE if view.surcharge < 0 else BLACK))

    if view.note:
        body.append(_separator())
        body.append(_row("備註", view.note, value_color=MUTED))

    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": PRIMARY, "paddingAll": "md",
            "contents": [{
                "type": "text", "text": f"📅 固定班次 #{view.id}",
                "weight": "bold", "size": "lg", "color": "#ffffff",
            }],
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": body,
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": _build_action_buttons(view, event_source=event_source),
        },
    }


# ============================================================
# 多筆 carousel
# ============================================================

def render_fixed_schedule_list_carousel(views: List[FixedScheduleView], event_source=None) -> dict:
    """多筆固定班次 → carousel（每張一筆，含按鈕）"""
    if not views:
        return _empty_bubble()

    if len(views) == 1:
        return render_fixed_schedule_detail(views[0], event_source=event_source)

    bubbles = [render_fixed_schedule_detail(v, event_source=event_source) for v in views[:MAX_BUBBLES]]
    if len(views) > MAX_BUBBLES:
        bubbles[-1] = _more_bubble(remaining=len(views) - (MAX_BUBBLES - 1),
                                   total=len(views))
    return {"type": "carousel", "contents": bubbles}


def _empty_bubble() -> dict:
    return {
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical",
            "contents": [
                {"type": "text", "text": "📅 固定班次", "weight": "bold", "size": "lg"},
                {"type": "text", "text": "查無資料", "color": MUTED, "margin": "md"},
            ],
        },
    }


def _more_bubble(remaining: int, total: int) -> dict:
    return {
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical",
            "alignItems": "center", "justifyContent": "center",
            "contents": [
                {"type": "text", "text": f"還有 {remaining} 筆",
                 "weight": "bold", "size": "lg", "color": PRIMARY},
                {"type": "text", "text": f"（共 {total} 筆，請縮小範圍）",
                 "size": "xs", "color": MUTED, "margin": "md", "wrap": True},
            ],
        },
    }
