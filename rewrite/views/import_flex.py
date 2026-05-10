"""匯入固定班次 LIFF 入口 Flex

提供：
  render_import_entry(event_source=None)
    — !匯入固定班次 觸發的 Flex（含 LIFF 按鈕點開表單）

LIFF App 共用 customer 的 LIFF_ID（單一 App，靠 ?form=import 路由）。

注意 event_source 必傳：LIFF SDK 的 getContext() 回傳的 groupId 是 UUID 格式
（≠ LINE Messaging API 的 33 字元 ID），不能用來 push，所以從 webhook event 拿
正確的群組 ID 塞進 URL 給前端 round-trip 回來才能 broadcast 結果。
"""
from rewrite.utils.liff_url import build_liff_url
from rewrite.views.customer_flex import _liff_id


PRIMARY = "#1565C0"
ACCENT = "#06C755"
DANGER = "#D32F2F"
MUTED = "#999999"
BLACK = "#333333"


def render_import_entry(event_source=None) -> dict:
    """!匯入固定班次 觸發的 LINE message：text + Quick Reply（uri 開 LIFF）

    Args:
        event_source: webhook event.source 物件（有 type/group_id/room_id）。
            傳了才能在群組廣播匯入結果；私聊時不需要。

    Quick Reply 按完即消失，不留歷史殘留。
    LIFF_ID 環境變數未設時 → 回錯誤 Flex bubble。
    """
    if not _liff_id():
        from rewrite.views.customer_flex import _liff_unavailable_bubble
        return {
            'type': 'flex',
            'altText': '⚠️ LIFF 未設定',
            'contents': _liff_unavailable_bubble('匯入表單'),
        }

    return {
        'type': 'quick_reply',
        'text': (
            '📥 點下方按鈕匯入固定班次（太陽週：星期日 → 星期六）\n\n'
            '⚠️ 一人操作即可，匯入完成會在群組通知大家'
        ),
        'quick_reply': {
            'items': [{
                'type': 'action',
                'action': {
                    'type': 'uri',
                    'label': '📋 開匯入表單',
                    'uri': build_liff_url(_liff_id(), 'import', event_source),
                },
            }],
        },
    }
