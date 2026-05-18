"""drug_diagnosis_links LIFF entry message.

This module only renders a Quick Reply that opens the read/preview LIFF form.
It does not access the database or modify any routing for /dx or /drug.
"""

from rewrite.utils.liff_url import build_liff_url
from rewrite.views.customer_flex import _liff_id


def render_drug_diagnosis_link_entry(event_source=None) -> dict:
    """Render the v3 drug-diagnosis link maintenance LIFF entry."""
    if not _liff_id():
        from rewrite.views.customer_flex import _liff_unavailable_bubble

        return {
            "type": "flex",
            "altText": "LIFF 未設定",
            "contents": _liff_unavailable_bubble("藥診關聯維護表單"),
        }

    return {
        "type": "quick_reply",
        "text": "🔗 點下方按鈕開啟藥名 ↔ 診斷碼關聯維護表單",
        "quick_reply": {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "uri",
                        "label": "開藥診關聯表單",
                        "uri": build_liff_url(
                            _liff_id(),
                            "drug_dx_link",
                            event_source,
                        ),
                    },
                }
            ],
        },
    }
