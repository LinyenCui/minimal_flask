"""帳務處理 Flex / Quick Reply

提供：
  render_accounting_menu(balance) — 顯示餘額 Flex + 3 個按鈕（入金/扣款 LIFF + 明細 message）
  render_ledger_list(rows, balance) — 顯示最近 N 筆明細 Flex
"""
from rewrite.views.customer_flex import _liff_id


PRIMARY = "#1565C0"
SUCCESS = "#2E7D32"
DANGER = "#D32F2F"
MUTED = "#999999"
BLACK = "#333333"


# 各 type 顯示對應
_TYPE_LABEL = {
    'deposit': '➕ 入金',
    'weekly_charge': '💵 週扣款',
    'manual_in': '➕ 入金',
    'manual_out': '💵 扣款',
    'adjustment': '⚙️ 調整',
}


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


def _ledger_row(rec: dict) -> dict:
    """單筆明細行（橫向 layout）：日期 / type / counterparty / amount"""
    occ = rec.get('occurred_at') or ''
    # ISO → MM/DD HH:MM
    short_dt = occ[5:16].replace('T', ' ') if len(occ) >= 16 else occ[:10]
    type_label = _TYPE_LABEL.get(rec.get('type'), rec.get('type') or '?')
    counterparty = (rec.get('counterparty') or '')[:14]
    amt_in = int(rec.get('amount_in') or 0)
    amt_out = int(rec.get('amount_out') or 0)
    if amt_in > 0:
        amt_text = f"+{amt_in:,}"
        amt_color = SUCCESS
    elif amt_out > 0:
        amt_text = f"-{amt_out:,}"
        amt_color = DANGER
    else:
        amt_text = "0"
        amt_color = MUTED

    return {
        "type": "box", "layout": "vertical",
        "spacing": "xs",
        "paddingTop": "sm", "paddingBottom": "sm",
        "contents": [
            {
                "type": "box", "layout": "horizontal", "spacing": "sm",
                "contents": [
                    {"type": "text", "text": short_dt, "size": "xs",
                     "color": MUTED, "flex": 3},
                    {"type": "text", "text": type_label, "size": "xs",
                     "color": BLACK, "weight": "bold", "flex": 3},
                    {"type": "text", "text": amt_text, "size": "sm",
                     "color": amt_color, "weight": "bold",
                     "align": "end", "flex": 4},
                ],
            },
            {
                "type": "text", "text": counterparty, "size": "xs",
                "color": MUTED, "wrap": False,
            } if counterparty else {"type": "filler"},
        ],
    }


def render_ledger_list(rows: list[dict], *, balance: int) -> dict:
    """最近明細 Flex bubble — 標題餘額 + 行列表"""
    if not rows:
        body_contents = [{
            "type": "text", "text": "📭 沒有任何明細記錄",
            "size": "md", "color": MUTED, "align": "center",
        }]
    else:
        body_contents = []
        for i, rec in enumerate(rows):
            body_contents.append(_ledger_row(rec))
            if i < len(rows) - 1:
                body_contents.append({"type": "separator", "margin": "xs"})

    balance_color = SUCCESS if balance >= 0 else DANGER
    bubble = {
        "type": "bubble", "size": "giga",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": PRIMARY,
            "paddingAll": "md",
            "contents": [
                {"type": "text", "text": "📒 帳務明細",
                 "weight": "bold", "size": "lg", "color": "#ffffff"},
                {"type": "text",
                 "text": f"目前餘額 NT$ {balance:,}（最近 {len(rows)} 筆）",
                 "size": "xs", "color": "#E0E0E0", "margin": "sm"},
            ],
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "xs",
            "paddingAll": "md",
            "contents": body_contents,
        },
        "footer": {
            "type": "box", "layout": "vertical",
            "contents": [{
                "type": "text",
                "text": "💡 入金 / 扣款 用 帳務處理 主選單按鈕",
                "size": "xxs", "color": MUTED, "align": "center", "wrap": True,
            }],
        },
    }
    return {
        'type': 'flex',
        'altText': f'帳務明細（最近 {len(rows)} 筆，餘額 {balance:,}）',
        'contents': bubble,
    }
