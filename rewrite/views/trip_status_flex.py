"""
「[date][location]的狀態」狀態管理 picker

LIFF 不適合多步交互（看清單→批次按鈕→鍵入原因+加成），所以這個流程用
sandbox-handled Flex + Quick Reply 走，state 走 conversation_state。

提供：
  render_trip_status_picker(trips, date_label, location_label) → flex + quick_reply

Status mix 邏輯：
  全部準備（含「待派」）→ [全部請假] [全部註銷] [全部衝突] + 個別詳情
  全部非準備（請假/註銷/衝突）→ [全部改回準備] + 個別詳情
  混合 → 只給個別詳情（避免批次操作影響到不該動的）
"""
from typing import List

from rewrite.tools.trip import TripView
from rewrite.views.trip_flex import (
    PRIMARY, ACCENT, DANGER, SUCCESS, MUTED, BLACK, STATUS_COLOR,
    _format_date_with_weekday,
)


def _classify(trips: List[TripView]) -> tuple[list, list]:
    """回 (ready_trips, non_ready_trips)

    『請假』(三層障眼法) 雖然 status='準備'，但 passenger_leave_reason 有值 → 視為非準備
    """
    ready, non_ready = [], []
    for t in trips:
        if t.passenger_leave_reason:
            non_ready.append(t)
        elif t.status in ('準備', '待派'):
            ready.append(t)
        elif t.status in ('註銷', '衝突', '請假'):
            non_ready.append(t)
        else:
            ready.append(t)  # 預設視為準備
    return ready, non_ready


def _status_label(t: TripView) -> tuple[str, str]:
    """回 (display_text, color)"""
    if t.passenger_leave_reason:
        return f"🔵請假({t.passenger_leave_reason})", STATUS_COLOR.get('請假', '#7B1FA2')
    if t.status == '註銷':
        return "🚫註銷", DANGER
    if t.status == '衝突':
        return "⚠️衝突", DANGER
    if t.status == '待派':
        return "⏳待派", "#E65100"
    if t.status == '準備':
        return "✅準備", SUCCESS
    return f"·{t.status or '?'}", MUTED


def _status_row(t: TripView) -> dict:
    """單筆班次顯示行：時間 路線 狀態（tap → 班次詳情）"""
    time_text = str(t.time)[:5] if t.time else '—'
    sp, _, ep = t.display_route()
    route_text = f"{sp or '?'}→{ep or '?'}"
    status_text, status_color = _status_label(t)
    driver_text = f"🚗{t.driver_id}" if t.driver_id else "🚗?"

    return {
        'type': 'box',
        'layout': 'vertical',
        'spacing': 'xs',
        'paddingAll': 'xs',
        'action': {
            'type': 'message',
            'label': f'#{t.trip_id} 詳情',
            'text': f'班次詳情 {t.trip_id}',
        },
        'contents': [
            {
                'type': 'box', 'layout': 'horizontal', 'spacing': 'sm',
                'contents': [
                    {'type': 'text',
                     'text': (f'📌#{t.trip_id}' if t.trip_type == 'temp' else f'#{t.trip_id}'),
                     'size': 'sm', 'color': PRIMARY, 'weight': 'bold', 'flex': 2},
                    {'type': 'text', 'text': time_text, 'size': 'sm',
                     'color': BLACK, 'flex': 2},
                    {'type': 'text', 'text': driver_text, 'size': 'sm',
                     'color': MUTED, 'flex': 2, 'align': 'end'},
                ],
            },
            {
                'type': 'box', 'layout': 'horizontal', 'spacing': 'sm',
                'contents': [
                    {'type': 'text', 'text': route_text, 'size': 'xs',
                     'color': BLACK, 'flex': 5, 'wrap': True},
                ],
            },
            {
                'type': 'box', 'layout': 'horizontal', 'spacing': 'sm',
                'contents': [
                    {'type': 'text', 'text': status_text, 'size': 'xs',
                     'color': status_color, 'weight': 'bold', 'wrap': True},
                ],
            },
        ],
    }


def _qr(label: str, text: str) -> dict:
    return {'type': 'action', 'action': {'type': 'message', 'label': label, 'text': text}}


def render_trip_status_picker(
    trips: List[TripView],
    *,
    date_label: str,
    location_label: str,
) -> dict:
    """渲染狀態 picker（Flex bubble + status-aware Quick Reply）

    Returns dict for line_bot.py reply_message：
      type='flex_with_quick_reply', contents=<bubble>, quick_reply={'items': [...]}
    """
    if not trips:
        # 由 caller 顯示「沒找到班次」訊息，這裡其實不會被叫到
        return {
            'type': 'text',
            'text': f'📭 沒找到 {date_label} {location_label} 的班次',
        }

    ready, non_ready = _classify(trips)

    # ---------------- Quick Reply 按鈕 ----------------
    items: list = []

    if len(ready) == len(trips):
        # 全準備 → 三類批次操作
        items.append(_qr('🏥 全部請假', '全部請假'))
        items.append(_qr('🚫 全部註銷', '全部註銷'))
        items.append(_qr('⚠️ 全部衝突', '全部衝突'))
    elif len(non_ready) == len(trips):
        # 全非準備 → 改回準備
        items.append(_qr('✅ 全部改回準備', '全部改回準備'))
    # 混合狀態：不放批次按鈕（避免誤動已註銷的班次）

    # 個別詳情按鈕（最多 3 個）
    for t in trips[:3]:
        items.append(_qr(f'#{t.trip_id}詳情', f'班次詳情 {t.trip_id}'))

    items.append(_qr('❌ 取消', '結束對話'))

    # LINE 上限 13 個 quick reply
    items = items[:13]

    # ---------------- Flex bubble ----------------
    rows: list = []
    rows_to_show = trips[:8]  # 最多顯示 8 筆
    for i, t in enumerate(rows_to_show):
        rows.append(_status_row(t))
        if i < len(rows_to_show) - 1:
            rows.append({'type': 'separator', 'margin': 'xs'})
    if len(trips) > 8:
        rows.append({'type': 'separator', 'margin': 'xs'})
        rows.append({
            'type': 'text',
            'text': f'…還有 {len(trips) - 8} 筆（請點個別詳情查看）',
            'size': 'xs', 'color': MUTED, 'margin': 'sm', 'align': 'center',
        })

    # 統計摘要
    summary_parts = []
    if ready:
        summary_parts.append(f'準備 {len(ready)}')
    leave_count = sum(1 for t in trips if t.passenger_leave_reason)
    if leave_count:
        summary_parts.append(f'請假 {leave_count}')
    cancelled_count = sum(1 for t in trips if t.status == '註銷')
    if cancelled_count:
        summary_parts.append(f'註銷 {cancelled_count}')
    conflict_count = sum(1 for t in trips if t.status == '衝突')
    if conflict_count:
        summary_parts.append(f'衝突 {conflict_count}')
    summary = '｜'.join(summary_parts) if summary_parts else f'{len(trips)} 筆'

    bubble = {
        'type': 'bubble',
        'size': 'mega',
        'header': {
            'type': 'box',
            'layout': 'vertical',
            'backgroundColor': PRIMARY,
            'paddingAll': 'md',
            'contents': [
                {'type': 'text',
                 'text': f'📍 {date_label}｜{location_label}',
                 'color': '#ffffff', 'weight': 'bold', 'size': 'md',
                 'wrap': True},
                {'type': 'text',
                 'text': f'共 {len(trips)} 筆 · {summary}',
                 'color': '#E0E0E0', 'size': 'xs', 'margin': 'sm'},
            ],
        },
        'body': {
            'type': 'box',
            'layout': 'vertical',
            'spacing': 'sm',
            'paddingAll': 'md',
            'contents': rows,
        },
        'footer': {
            'type': 'box',
            'layout': 'vertical',
            'paddingAll': 'sm',
            'contents': [{
                'type': 'text',
                'text': '👇 點下方按鈕批次操作，或點上方項目看單筆詳情',
                'size': 'xxs', 'color': MUTED, 'wrap': True, 'align': 'center',
            }],
        },
    }

    return {
        'type': 'flex_with_quick_reply',
        'altText': f'{date_label} {location_label} 狀態（{len(trips)} 筆）',
        'contents': bubble,
        'quick_reply': {'items': items},
    }
