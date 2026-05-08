"""帳務處理 Flex / Quick Reply

提供：
  render_accounting_menu(balance) — 顯示餘額 Flex + 3 個按鈕（入金/扣款 LIFF + 明細 message）
"""
from rewrite.views.customer_flex import _liff_id


PRIMARY = "#1565C0"
SUCCESS = "#2E7D32"
DANGER = "#D32F2F"
MUTED = "#999999"
BLACK = "#333333"


def _deposit_liff_url() -> str:
    return f"https://liff.line.me/{_liff_id()}?form=deposit"


def _weekly_payment_liff_url() -> str:
    return f"https://liff.line.me/{_liff_id()}?form=weekly_payment"


def render_accounting_menu(balance: int) -> dict:
    """!帳務處理 觸發的 Flex bubble：餘額 + 3 個按鈕"""
    if not _liff_id():
        from rewrite.views.customer_flex import _liff_unavailable_bubble
        return {
            'type': 'flex',
            'altText': '⚠️ LIFF 未設定',
            'contents': _liff_unavailable_bubble('帳務處理'),
        }

    # 餘額正負顏色
    balance_color = SUCCESS if balance >= 0 else DANGER
    balance_text = f"NT$ {balance:,}"

    bubble = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": PRIMARY, "paddingAll": "md",
            "contents": [{
                "type": "text", "text": "💰 帳務處理",
                "weight": "bold", "size": "lg", "color": "#ffffff",
            }],
        },
        "body": {
            "type": "box", "layout": "vertical",
            "alignItems": "center",
            "spacing": "sm",
            "paddingTop": "lg", "paddingBottom": "lg",
            "contents": [
                {"type": "text", "text": "目前帳戶餘額",
                 "size": "sm", "color": MUTED},
                {"type": "text", "text": balance_text,
                 "size": "3xl", "weight": "bold",
                 "color": balance_color, "margin": "sm"},
            ],
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {
                    "type": "button", "style": "primary", "height": "sm",
                    "color": SUCCESS,
                    "action": {
                        "type": "uri", "label": "➕ 記錄入金",
                        "uri": _deposit_liff_url(),
                    },
                },
                {
                    "type": "button", "style": "primary", "height": "sm",
                    "color": "#FF6D00",
                    "action": {
                        "type": "uri", "label": "💵 記錄上週扣款",
                        "uri": _weekly_payment_liff_url(),
                    },
                },
                {
                    "type": "button", "style": "secondary", "height": "sm",
                    "action": {
                        "type": "message", "label": "📒 查看明細",
                        "text": "acct_ledger_start",
                    },
                },
            ],
        },
    }
    return {
        'type': 'flex',
        'altText': f'帳戶餘額 {balance_text}',
        'contents': bubble,
    }
