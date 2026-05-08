"""報表生成入口 Flex"""
from rewrite.views.customer_flex import _liff_id


def _report_liff_url() -> str:
    return f"https://liff.line.me/{_liff_id()}?form=report"


def render_report_entry() -> dict:
    """!產報表 / !生成報表 觸發的 LINE message + Quick Reply"""
    if not _liff_id():
        from rewrite.views.customer_flex import _liff_unavailable_bubble
        return {
            'type': 'flex',
            'altText': '⚠️ LIFF 未設定',
            'contents': _liff_unavailable_bubble('報表表單'),
        }

    return {
        'type': 'quick_reply',
        'text': '📊 點下方按鈕產生報表（日 / 週 / 月）',
        'quick_reply': {
            'items': [{
                'type': 'action',
                'action': {
                    'type': 'uri',
                    'label': '📊 開報表表單',
                    'uri': _report_liff_url(),
                },
            }],
        },
    }
