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
    """!預約叫車 觸發的 Flex：點按鈕開 LIFF 預約表單

    LIFF_ID 環境變數未設時 → 回錯誤 bubble。
    """
    if not _liff_id():
        return {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": DANGER, "paddingAll": "md",
                "contents": [{
                    "type": "text", "text": "⚠️ LIFF 未設定",
                    "weight": "bold", "size": "lg", "color": "#ffffff",
                }],
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "contents": [
                    {"type": "text",
                     "text": "LIFF_ID 環境變數沒載入，預約表單暫不可用",
                     "size": "sm", "color": BLACK, "wrap": True},
                    {"type": "text",
                     "text": "💡 請確認 .env.dev 存在且含 LIFF_ID，並重啟 Flask",
                     "size": "xs", "color": MUTED, "wrap": True, "margin": "md"},
                ],
            },
        }

    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": PRIMARY, "paddingAll": "md",
            "contents": [{
                "type": "text", "text": "📅 預約叫車",
                "weight": "bold", "size": "lg", "color": "#ffffff",
            }],
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [{
                "type": "text",
                "text": "點下方按鈕開填寫表單",
                "size": "sm", "color": MUTED, "wrap": True,
            }],
        },
        "footer": {
            "type": "box", "layout": "vertical",
            "contents": [{
                "type": "button", "style": "primary", "height": "sm",
                "color": ACCENT,
                "action": {
                    "type": "uri",
                    "label": "📝 開填寫表單",
                    "uri": _booking_liff_url(),
                },
            }],
        },
    }
