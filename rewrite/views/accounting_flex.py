"""帳務處理 Flex / Quick Reply

提供：
  render_accounting_menu(balance) — 顯示餘額 Flex + 3 個按鈕（入金/扣款 LIFF + 明細 message）
  render_ledger_carousel(rows, balance, from_date, to_date, has_more)
    — Flex carousel 橫向翻頁（每 bubble 10 筆，最多 12 bubbles = 120 筆）
  render_ledger_text(rows, page_no, next_cursor, from_date, to_date)
    — text 格式（保留作備援；目前 sandbox 改走 carousel）
"""
from datetime import timezone, timedelta
from typing import Optional

from rewrite.utils.liff_url import build_liff_url
from rewrite.views.customer_flex import _liff_id


PRIMARY = "#1565C0"
SUCCESS = "#2E7D32"
DANGER = "#D32F2F"
MUTED = "#999999"
BLACK = "#333333"


def render_accounting_menu(balance: int, event_source=None) -> dict:
    """!帳務處理 觸發的 Flex bubble：餘額 + 3 個按鈕

    event_source 傳了，入金 / 扣款按鈕的 LIFF URL 會帶 gid/rid，
    submit 後 push 才會回到原群組。
    """
    if not _liff_id():
        from rewrite.views.customer_flex import _liff_unavailable_bubble
        return {
            'type': 'flex',
            'altText': '⚠️ LIFF 未設定',
            'contents': _liff_unavailable_bubble('帳務處理'),
        }
    deposit_uri = build_liff_url(_liff_id(), 'deposit', event_source)
    weekly_uri = build_liff_url(_liff_id(), 'weekly_payment', event_source)

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
                        "uri": deposit_uri,
                    },
                },
                {
                    "type": "button", "style": "primary", "height": "sm",
                    "color": "#FF6D00",
                    "action": {
                        "type": "uri", "label": "💵 記錄上週扣款",
                        "uri": weekly_uri,
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


# ============================================================
# Carousel 橫向翻頁版（仿診所班次風格）
# ============================================================

LEDGER_PAGE_SIZE = 7       # 7 列/bubble × 12 bubbles = 84 筆 max
LEDGER_CAROUSEL_MAX_BUBBLES = 12  # LINE Flex carousel 上限


def _ledger_carousel_row(rec: dict) -> dict:
    """Carousel bubble 內單筆 — 4 欄極簡 layout（避免 50KB 上限）：
       MM/DD  ±N,NNN  N,NNN  對方
    """
    dt = rec.get('occurred_at')
    if dt is not None:
        try:
            if getattr(dt, 'tzinfo', None) is not None:
                dt = dt.astimezone(timezone(timedelta(hours=8)))
        except Exception:
            pass
        dt_text = dt.strftime('%m/%d')
    else:
        dt_text = '—'

    type_str = rec.get('type') or ''
    is_in = (rec.get('amount_in') or 0) > 0
    if is_in:
        amt_text = f"+{int(rec.get('amount_in') or 0):,}"
    else:
        amt_text = f"-{int(rec.get('amount_out') or 0):,}"
    amt_color = SUCCESS if is_in else DANGER

    balance = int(rec.get('running_balance') or 0)
    if type_str == 'weekly_charge':
        note = '車資扣款'
    else:
        note = (rec.get('counterparty') or rec.get('memo') or '')[:8]

    return {
        "type": "box", "layout": "horizontal",
        "contents": [
            {"type": "text", "text": dt_text, "size": "xxs",
             "color": MUTED, "flex": 2},
            {"type": "text", "text": amt_text, "size": "xxs",
             "color": amt_color, "weight": "bold",
             "align": "end", "flex": 4},
            {"type": "text", "text": f"{balance:,}", "size": "xxs",
             "color": BLACK, "align": "end", "flex": 4},
            {"type": "text", "text": note, "size": "xxs",
             "color": MUTED, "flex": 5, "wrap": False, "margin": "sm"},
        ],
    }


def _ledger_bubble(
    page_rows: list[dict], page_no: int, total_pages: int,
    total_count: int, balance: int,
) -> dict:
    """單張 carousel bubble（極簡版避免 50KB 上限）"""
    body_rows = [_ledger_carousel_row(rec) for rec in page_rows]

    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": PRIMARY, "paddingAll": "sm",
            "contents": [
                {"type": "text", "text": f"📒 NT$ {balance:,}",
                 "weight": "bold", "size": "sm", "color": "#ffffff"},
                {"type": "text", "text": f"{page_no}/{total_pages}（共{total_count}筆）",
                 "size": "xxs", "color": "#E0E0E0"},
            ],
        },
        "body": {
            "type": "box", "layout": "vertical",
            "paddingAll": "sm",
            "contents": body_rows,
        },
    }


def _ledger_more_bubble(remaining_count: int) -> dict:
    """超過 12 bubbles 上限的提示 bubble"""
    return {
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical",
            "alignItems": "center", "justifyContent": "center",
            "contents": [
                {"type": "text", "text": f"還有 {remaining_count}+ 筆",
                 "weight": "bold", "size": "lg", "color": "#FF6D00"},
                {"type": "text",
                 "text": "請按「篩選區間」縮範圍",
                 "size": "xs", "color": MUTED, "margin": "md", "wrap": True},
            ],
        },
    }


def render_ledger_carousel(
    rows: list[dict],
    *,
    balance: int,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    has_more: bool = False,
) -> dict:
    """帳務明細 Flex carousel — 橫向翻頁

    rows 已是按 occurred_at desc 排好的；切成 LEDGER_PAGE_SIZE 一組形成多 bubble。
    超過 LEDGER_CAROUSEL_MAX_BUBBLES（12 張）就最後一張顯示「還有 N 筆」提示。
    """
    if not rows:
        # 空 bubble + 篩選 quick reply
        empty_bubble = {
            "type": "bubble", "size": "kilo",
            "body": {
                "type": "box", "layout": "vertical",
                "alignItems": "center", "justifyContent": "center",
                "contents": [
                    {"type": "text", "text": "📭 沒有符合條件的明細",
                     "size": "md", "color": MUTED, "align": "center"},
                ],
            },
        }
        return {
            'type': 'flex_with_quick_reply',
            'altText': '帳務明細（無資料）',
            'contents': empty_bubble,
            'quick_reply': _build_ledger_quick_reply(None, from_date, to_date),
        }

    # 切頁
    pages = [rows[i:i + LEDGER_PAGE_SIZE]
             for i in range(0, len(rows), LEDGER_PAGE_SIZE)]
    total_pages = len(pages)
    total_count = len(rows)

    bubbles = []
    take_pages = pages[:LEDGER_CAROUSEL_MAX_BUBBLES]
    for i, page in enumerate(take_pages):
        bubbles.append(_ledger_bubble(
            page, page_no=i + 1, total_pages=total_pages,
            total_count=total_count, balance=balance,
        ))

    if has_more or total_pages > LEDGER_CAROUSEL_MAX_BUBBLES:
        # 替換最後一張 bubble 為「還有 N+ 筆」提示
        bubbles = bubbles[:LEDGER_CAROUSEL_MAX_BUBBLES - 1]
        if has_more:
            bubbles.append(_ledger_more_bubble(0))  # 不知精確數，顯示 N+
        else:
            remaining = total_count - (LEDGER_CAROUSEL_MAX_BUBBLES - 1) * LEDGER_PAGE_SIZE
            bubbles.append(_ledger_more_bubble(remaining))

    container = bubbles[0] if len(bubbles) == 1 else {
        "type": "carousel", "contents": bubbles,
    }

    range_alt = f'（{from_date}~{to_date}）' if (from_date and to_date) else ''
    return {
        'type': 'flex_with_quick_reply',
        'altText': f'帳務明細{range_alt}（{total_count} 筆，餘額 {balance:,}）',
        'contents': container,
        'quick_reply': _build_ledger_quick_reply(None, from_date, to_date),
    }
