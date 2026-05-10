"""批量加成入口 Flex"""
from rewrite.utils.liff_url import build_liff_url
from rewrite.views.customer_flex import _liff_id


def render_batch_allowance_entry(event_source=None) -> dict:
    """!批量加成 觸發 Quick Reply"""
    if not _liff_id():
        from rewrite.views.customer_flex import _liff_unavailable_bubble
        return {
            'type': 'flex',
            'altText': '⚠️ LIFF 未設定',
            'contents': _liff_unavailable_bubble('批量加成表單'),
        }

    return {
        'type': 'quick_reply',
        'text': '💰 點下方按鈕批量加成（颱風假/春節等批量調整 completed_trips 加成）',
        'quick_reply': {
            'items': [{
                'type': 'action',
                'action': {
                    'type': 'uri',
                    'label': '💰 開批量加成表單',
                    'uri': build_liff_url(_liff_id(), 'batch_allowance', event_source),
                },
            }],
        },
    }
