"""預約叫車 Flex 入口

提供：
  render_booking_entry(event_source=None)
    — !預約叫車 觸發的 Flex（含 LIFF 按鈕點開表單）

預約結果卡（建好後 push）重用 rewrite.views.trip_flex.render_trip_detail。

注意 event_source：在群組觸發時要把真 group_id 從 webhook 塞進 LIFF URL，
否則前端拿到的 LIFF UUID 不能 push 廣播（詳見 rewrite/utils/liff_url.py）。
"""
from rewrite.utils.liff_url import build_liff_url
from rewrite.views.customer_flex import _liff_id  # 共用 LIFF_ID 讀取邏輯


PRIMARY = "#1565C0"
ACCENT = "#06C755"      # LINE 綠
DANGER = "#D32F2F"
MUTED = "#999999"
BLACK = "#333333"


def render_booking_entry(event_source=None) -> dict:
    """!預約叫車 觸發的 LINE message：text + Quick Reply（uri 開 LIFF）

    Args:
        event_source: webhook event.source。群組裡觸發傳進來才能廣播結果。

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
                    'uri': build_liff_url(_liff_id(), 'booking', event_source),
                },
            }],
        },
    }
