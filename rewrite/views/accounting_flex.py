"""帳務處理 Flex / Quick Reply

提供：
  render_accounting_menu(balance) — 顯示餘額 Flex + 3 個按鈕（入金/扣款 LIFF + 明細 message）
  render_ledger_text(rows, page_no, next_cursor, from_date, to_date)
    — 對齊 main 版：text 格式 + Quick Reply（下一頁/篩選區間/回帳務處理）
"""
from datetime import timezone, timedelta
from typing import Optional

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


def _fmt_amount(n: int, sign_force: bool = True) -> str:
    """格式化金額：強制顯示正負號"""
    if n is None:
        n = 0
    if sign_force:
        return ("+" if n >= 0 else "-") + f"{abs(n):,}"
    return f"{n:,}"


def _fmt_type(t: str) -> str:
    """type → 中文 label（對齊 main）"""
    if t == 'deposit':
        return '入金'
    if t == 'weekly_charge':
        return '扣款'
    return t or ''


def _fmt_line(row: dict) -> str:
    """單筆明細的 text 行（對齊 main _fmt_line）

    例：2026-05-03 07:59  扣款 📤 -25,330  | 餘額 66,255  · 車資扣款
    """
    dt = row.get('occurred_at')
    if dt is not None:
        try:
            if getattr(dt, 'tzinfo', None) is not None:
                dt = dt.astimezone(timezone(timedelta(hours=8)))
        except Exception:
            pass
        ts = dt.strftime('%Y-%m-%d %H:%M')
    else:
        ts = '----'

    amount_in = int(row.get('amount_in') or 0)
    amount_out = int(row.get('amount_out') or 0)
    if amount_in > 0:
        delta = f"📥 {_fmt_amount(amount_in)}"
    else:
        delta = f"📤 {_fmt_amount(-amount_out)}"

    balance = int(row.get('running_balance') or 0)
    type_str = row.get('type') or ''
    # 顯示文案：weekly_charge 強制顯示為「車資扣款」(對齊 main)
    if type_str == 'weekly_charge':
        note = '車資扣款'
    else:
        note = row.get('counterparty') or row.get('memo') or ''

    return f"{ts}  {_fmt_type(type_str)} {delta}  | 餘額 {balance:,}  · {note}"


def _build_ledger_quick_reply(
    next_cursor: Optional[tuple],
    from_date: Optional[str],
    to_date: Optional[str],
) -> dict:
    """組明細 Quick Reply（下一頁 / 篩選區間 / 回帳務處理）"""
    items = []
    if next_cursor:
        next_ts, next_id = next_cursor
        fd = from_date or ''
        td = to_date or ''
        payload = f"acct_ledger_next:{next_ts}:{next_id}:{fd}:{td}"
        items.append({
            'type': 'action',
            'action': {'type': 'message', 'label': '下一頁', 'text': payload},
        })
    items.append({
        'type': 'action',
        'action': {'type': 'message', 'label': '篩選區間', 'text': 'acct_ledger_range'},
    })
    items.append({
        'type': 'action',
        'action': {'type': 'message', 'label': '回帳務處理', 'text': '帳務處理'},
    })
    return {'items': items}


def render_ledger_text(
    rows: list[dict],
    *,
    page_no: int,
    next_cursor: Optional[tuple],
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    """帳務明細的 text + Quick Reply 訊息（對齊 main 版輸出格式）

    Returns dict for line_bot.py reply_message：
      type='text_with_quick_reply', text=明細, quick_reply={items: [...]}
    """
    if not rows:
        body_text = '目前查無明細'
    else:
        header = f"📒 帳戶明細（第 {page_no if page_no > 0 else '續'} 頁）\n" + "─" * 20 + "\n"
        body_lines = [_fmt_line(r) for r in rows]
        body_text = header + "\n".join(body_lines) + "\n" + "─" * 20

    return {
        'type': 'text_with_quick_reply',
        'text': body_text,
        'quick_reply': _build_ledger_quick_reply(next_cursor, from_date, to_date),
    }
