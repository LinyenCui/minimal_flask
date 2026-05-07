"""固定班次（fixed_schedule）入口 Flex

提供：
  render_new_fixed_schedule_entry()  — !新增固定班次 觸發 LINE message + Quick Reply
"""
from rewrite.views.customer_flex import _liff_id


def _new_fixed_schedule_liff_url() -> str:
    """共用 LIFF App，靠 ?form=new_schedule 路由"""
    return f"https://liff.line.me/{_liff_id()}?form=new_schedule"


def render_new_fixed_schedule_entry() -> dict:
    """!新增固定班次 觸發的 LINE message：text + Quick Reply

    Quick Reply 按完即消失，跟其他三入口（customer / booking / import）同 pattern。
    LIFF_ID 環境變數未設時 → 回錯誤 Flex bubble。
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
                    'uri': _new_fixed_schedule_liff_url(),
                },
            }],
        },
    }
