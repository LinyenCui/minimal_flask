"""報表生成入口 Flex"""
from rewrite.utils.liff_url import build_liff_url
from rewrite.views.customer_flex import _liff_id


def render_report_entry(event_source=None) -> dict:
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
                    'uri': build_liff_url(_liff_id(), 'report', event_source),
                },
            }],
        },
    }
