"""匯入固定班次 LIFF 入口 Flex

提供：
  render_import_entry()  — !匯入固定班次 觸發的 Flex（含 LIFF 按鈕點開表單）

LIFF App 共用 customer 的 LIFF_ID（單一 App，靠 ?form=import 路由）。
"""
from rewrite.views.customer_flex import _liff_id


PRIMARY = "#1565C0"
ACCENT = "#06C755"
DANGER = "#D32F2F"
MUTED = "#999999"
BLACK = "#333333"


def _import_liff_url() -> str:
    """組匯入表單的 LIFF URL（共用 LIFF App，靠 ?form=import 路由）"""
    return f"https://liff.line.me/{_liff_id()}?form=import"


def render_import_entry() -> dict:
    """!匯入固定班次 觸發的 LINE message：text + Quick Reply（uri 開 LIFF）

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
                    'uri': _import_liff_url(),
                },
            }],
        },
    }
