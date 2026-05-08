"""預約叫車 Flex 入口

提供：
  render_booking_entry()  — !預約叫車 觸發的 Flex（含 LIFF 按鈕點開表單）

預約結果卡（建好後 push 給用戶）重用 rewrite.views.trip_flex.render_trip_detail。
"""
import os
from rewrite.views.customer_flex import _liff_id  # 共用 LIFF_ID 讀取邏輯


PRIMARY = "#1565C0"
ACCENT = "#06C755"      # LINE 綠
DANGER = "#D32F2F"
MUTED = "#999999"
BLACK = "#333333"


def _booking_liff_url() -> str:
    """組 booking 表單的 LIFF URL（共用 customer 的 LIFF App，靠 ?form=booking 路由）"""
    liff_id = _liff_id()
    return f"https://liff.line.me/{liff_id}?form=booking"


def render_booking_entry() -> dict:
    """!預約叫車 觸發的 LINE message：text + Quick Reply（uri 開 LIFF）

    Quick Reply 按完即消失，不留歷史殘留。
    LIFF_ID 環境變數未設時 → 回錯誤 Flex bubble。
    """
    if not _liff_id():
        from rewrite.views.customer_flex import _liff_unavailable_bubble
        return {
            'type': 'flex',
            'altText': '⚠️ LIFF 未設定',
            'contents': _liff_unavailable_bubble('預約表單'),
        }

    return {
        'type': 'quick_reply',
        'text': '📅 點下方按鈕預約叫車',
        'quick_reply': {
            'items': [{
                'type': 'action',
                'action': {
                    'type': 'uri',
                    'label': '📝 開填寫表單',
                    'uri': _booking_liff_url(),
                },
            }],
        },
    }
