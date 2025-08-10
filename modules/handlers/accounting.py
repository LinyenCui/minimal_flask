"""
帳務處理功能處理器
- show_accounting_menu(event): 顯示餘額與兩顆Quick Reply
- handle_deposit_start/input(event): 入金流程（單行輸入）
- handle_weekly_start/input(event): 上週扣款流程（單行金額）
- query_balance(session) -> int
- last_saturday_2359()

依專案風格：
- 使用 QuickReplyManager 組裝按鈕
- 使用 ResponseHandler 發送文字 + Quick Reply
- SQL 操作用 SQLAlchemy 的 db.session 與 sql_text
"""
from __future__ import annotations

import logging
from datetime import datetime, date, time as dt_time, timedelta
from typing import Tuple

from sqlalchemy import text as sql_text

from modules.models.base import db
from modules.utils.quick_reply_manager import QuickReplyManager
from modules.utils.response_handler import ResponseHandler
from modules.utils.conversation_context import conversation_manager, ActiveConversation
from modules.utils.taiwan_time import get_taiwan_time

logger = logging.getLogger(__name__)


def query_balance() -> int:
    """計算目前帳戶餘額（SUM(in) - SUM(out)）"""
    row = db.session.execute(sql_text(
        """
        SELECT COALESCE(SUM(amount_in),0) AS total_in,
               COALESCE(SUM(amount_out),0) AS total_out
        FROM account_ledger
        """
    )).fetchone()
    total_in = int(row[0] or 0) if row else 0
    total_out = int(row[1] or 0) if row else 0
    return total_in - total_out


def _accounting_quick_reply():
    buttons = [
        {"label": "➕ 記錄入金", "text": "acct_deposit_start", "type": "message"},
        {"label": "💵 記錄上週扣款", "text": "acct_weekly_start", "type": "message"},
        {"label": "📒 查看明細", "text": "acct_ledger_start", "type": "message"},
    ]
    return QuickReplyManager._build_quick_reply_data(buttons)


def show_accounting_menu(reply_token: str) -> None:
    """顯示帳戶餘額 + 二個Quick Reply按鈕"""
    balance = query_balance()
    text = f"💰 目前帳戶餘額：NT$ {balance:,}"
    response = {
        "type": QuickReplyManager.ResponseType.TEXT_WITH_QUICK_REPLY,
        "text": text,
        "quick_reply": _accounting_quick_reply(),
    }
    ResponseHandler.send_response(reply_token, response)


def handle_deposit_start(user_id: str, reply_token: str) -> None:
    """進入入金流程（單行輸入）"""
    conversation_manager.start_conversation(
        user_id=user_id,
        conversation_type='accounting_deposit',
        current_step='waiting_input',
        context_data={},
        prompt_message='請輸入：日期 金額 銀行名稱 後四碼',
        duration_minutes=5,
    )
    prompt = "請輸入：日期 金額 銀行名稱 後四碼（例：2025-07-14 30415 合作金庫 8123）"
    response = QuickReplyManager.create_text_response(prompt, QuickReplyManager.create_common_buttons()["abandon_operation"])
    ResponseHandler.send_response(reply_token, response)


def _parse_deposit_input(text: str) -> Tuple[date, int, str, str]:
    parts = text.strip().split()
    if len(parts) < 4:
        raise ValueError("格式錯誤")
    date_str, amount_str, bank_name, last4 = parts[0], parts[1], parts[2], parts[3]
    # 日期
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        raise ValueError("日期格式錯誤，需 YYYY-MM-DD")
    # 金額
    try:
        amount = int(amount_str)
        if amount <= 0:
            raise ValueError
    except Exception:
        raise ValueError("金額需為正整數")
    # 後四碼
    if not (len(last4) == 4 and last4.isdigit()):
        raise ValueError("後四碼需為4位數字")
    return d, amount, bank_name, last4


def handle_deposit_input(conversation: ActiveConversation, message_text: str, user_id: str, reply_token: str) -> None:
    try:
        d, amount, bank_name, last4 = _parse_deposit_input(message_text)
    except ValueError as ve:
        ResponseHandler.send_response(reply_token, QuickReplyManager.create_text_response(f"❌ {ve}", QuickReplyManager.create_common_buttons()["abandon_operation"]))
        return

    payer = '達恩診所'
    transferred_dt = datetime.combine(d, dt_time(9, 0))

    # 防重複：同 payer + transferred_at + amount
    dup = db.session.execute(sql_text(
        """
        SELECT 1 FROM payments 
        WHERE payer = :payer AND transferred_at = :ts AND amount_twd = :amt
        LIMIT 1
        """
    ), {"payer": payer, "ts": transferred_dt, "amt": amount}).fetchone()

    if dup:
        ResponseHandler.send_response(reply_token, QuickReplyManager.create_text_response("⚠️ 已存在相同入金紀錄", _accounting_quick_reply()["items"]))
        return

    try:
        with db.session.begin():
            # 1) payments
            insert_payments = sql_text(
                """
                INSERT INTO payments(payer, amount_twd, transferred_at, bank_name, bank_account_last4, reference_no, notes, created_at)
                VALUES (:payer, :amount_twd, :transferred_at, :bank_name, :last4, NULL, '入金', NOW())
                RETURNING id
                """
            )
            pay_id = db.session.execute(insert_payments, {
                'payer': payer,
                'amount_twd': amount,
                'transferred_at': transferred_dt,
                'bank_name': bank_name,
                'last4': last4,
            }).fetchone()[0]

            # 2) account_ledger（鏡射）
            insert_ledger = sql_text(
                """
                INSERT INTO account_ledger(occurred_at, type, counterparty, amount_in, amount_out, bank_name, bank_account_last4, reference_no, memo, created_at)
                VALUES (:occurred_at, 'deposit', :counterparty, :amount_in, 0, :bank_name, :last4, :ref, '入金', NOW())
                """
            )
            db.session.execute(insert_ledger, {
                'occurred_at': transferred_dt,
                'counterparty': f"{bank_name} {last4}",
                'amount_in': amount,
                'bank_name': bank_name,
                'last4': last4,
                'ref': str(pay_id),
            })

        conversation_manager.end_conversation(user_id, "入金完成")
        success = f"✅ 已記錄入金 NT$ {amount:,}（{d.isoformat()} {bank_name} {last4}）"
        ResponseHandler.send_response(reply_token, QuickReplyManager.create_text_response(success))
        # 回覆最新餘額
        show_accounting_menu(reply_token)
    except Exception as e:
        logger.error(f"入金寫入失敗: {e}")
        ResponseHandler.send_response(reply_token, QuickReplyManager.create_text_response("❌ 入金寫入失敗，請稍後再試"))


def handle_weekly_start(user_id: str, reply_token: str) -> None:
    conversation_manager.start_conversation(
        user_id=user_id,
        conversation_type='accounting_weekly_charge',
        current_step='waiting_amount',
        context_data={},
        prompt_message='請輸入上週總金額（整數）',
        duration_minutes=5,
    )
    response = QuickReplyManager.create_text_response("請輸入上週總金額（整數）", QuickReplyManager.create_common_buttons()["abandon_operation"])
    ResponseHandler.send_response(reply_token, response)


def last_saturday_2359() -> datetime:
    now_tw = get_taiwan_time()
    today = now_tw.date()
    # Python: Monday=0..Sunday=6, Saturday=5
    days_since_saturday = (today.weekday() - 5) % 7
    target = today - timedelta(days=days_since_saturday)
    return datetime.combine(target, dt_time(23, 59))


def handle_weekly_input(conversation: ActiveConversation, message_text: str, user_id: str, reply_token: str) -> None:
    text = message_text.strip()
    try:
        amount = int(text)
        if amount <= 0:
            raise ValueError
    except Exception:
        ResponseHandler.send_response(reply_token, QuickReplyManager.create_text_response("❌ 金額需為正整數，請重新輸入", QuickReplyManager.create_common_buttons()["abandon_operation"]))
        return

    occurred_at = last_saturday_2359()
    memo = f"週末 {occurred_at.date().isoformat()} 扣款"
    try:
        with db.session.begin():
            db.session.execute(sql_text(
                """
                INSERT INTO account_ledger(occurred_at, type, counterparty, amount_in, amount_out, bank_name, bank_account_last4, reference_no, memo, created_at)
                VALUES (:occurred_at, 'weekly_charge', '車資扣款', 0, :amount_out, NULL, NULL, NULL, :memo, NOW())
                """
            ), {"occurred_at": occurred_at, "amount_out": amount, "memo": memo})

        conversation_manager.end_conversation(user_id, "週扣款完成")
        success = f"✅ 已記錄週扣款 NT$ {amount:,}（週末 {occurred_at.date().isoformat()}）"
        ResponseHandler.send_response(reply_token, QuickReplyManager.create_text_response(success))
        show_accounting_menu(reply_token)
    except Exception as e:
        logger.error(f"週扣款寫入失敗: {e}")
        ResponseHandler.send_response(reply_token, QuickReplyManager.create_text_response("❌ 寫入失敗，請稍後再試"))


# ====== 明細查詢（帳戶存摺） ======

LEDGER_PAGE_SIZE = 10

def _fetch_ledger_page(from_date: str | None, to_date: str | None, last_ts: str | None, last_id: int | None, limit: int = LEDGER_PAGE_SIZE + 1):
    sql = sql_text(
        """
        WITH baseline_rows AS (
            SELECT (COALESCE(a.amount_in,0) - COALESCE(a.amount_out,0)) AS delta
            FROM account_ledger a
            WHERE (:last_ts IS NOT NULL)
              AND (:from_date IS NULL OR a.occurred_at::date >= CAST(:from_date AS date))
              AND (:to_date   IS NULL OR a.occurred_at::date <= CAST(:to_date AS date))
              AND (a.occurred_at, a.id) <= (CAST(:last_ts AS timestamptz), :last_id)
        ), baseline AS (
            SELECT COALESCE(SUM(delta),0) AS start_balance FROM baseline_rows
        ), rows AS (
            SELECT a.id,
                   a.occurred_at,
                   a.type,
                   a.counterparty,
                   COALESCE(a.amount_in,0)  AS amount_in,
                   COALESCE(a.amount_out,0) AS amount_out,
                   (COALESCE(a.amount_in,0) - COALESCE(a.amount_out,0)) AS delta
            FROM account_ledger a
            WHERE (:from_date IS NULL OR a.occurred_at::date >= CAST(:from_date AS date))
              AND (:to_date   IS NULL OR a.occurred_at::date <= CAST(:to_date AS date))
              AND (:last_ts IS NULL OR (a.occurred_at, a.id) > (CAST(:last_ts AS timestamptz), :last_id))
            ORDER BY a.occurred_at ASC, a.id ASC
            LIMIT :limit
        )
        SELECT r.*, (b.start_balance + SUM(delta) OVER (ORDER BY r.occurred_at, r.id)) AS running_balance
        FROM rows r CROSS JOIN baseline b
        ORDER BY r.occurred_at ASC, r.id ASC;
        """
    )

    params = {
        'from_date': from_date,
        'to_date': to_date,
        'last_ts': last_ts,
        'last_id': last_id,
        'limit': limit,
    }
    rows = db.session.execute(sql, params).fetchall()
    return rows


def _fmt_amount(n: int, sign_force: bool = True) -> str:
    if n is None:
        n = 0
    if sign_force:
        return ("+" if n >= 0 else "-") + f"{abs(n):,}"
    return f"{n:,}"


def _fmt_type(t: str) -> str:
    if t == 'deposit':
        return '入金'
    if t == 'weekly_charge':
        return '扣款'
    return t or ''


def _fmt_line(row) -> str:
    ts = row.occurred_at.strftime('%Y-%m-%d %H:%M') if row.occurred_at else '----'
    if (row.amount_in or 0) > 0:
        delta = f"📥 {_fmt_amount(row.amount_in)}"
    else:
        delta = f"📤 {_fmt_amount(-int(row.amount_out or 0))}"
    balance = f"{int(row.running_balance or 0):,}"
    # 顯示文案：weekly_charge 強制顯示為「車資扣款」(不受資料表原文字影響)
    if (row.type or '') == 'weekly_charge':
        note = '車資扣款'
    else:
        note = row.counterparty or row.memo or ''
    return f"{ts}  {_fmt_type(row.type)} {delta}  | 餘額 {balance}  · {note}"


def _ledger_reply_text(rows, page_no: int) -> str:
    header = f"📒 帳戶明細（第 {page_no if page_no>0 else '續'} 頁）\n" + "─"*20 + "\n"
    lines = [ _fmt_line(r) for r in rows ]
    body = "\n".join(lines)
    if not body:
        return "目前查無明細"
    return header + body + "\n" + "─"*20


def _ledger_quick_reply(next_cursor: tuple | None, from_date: str | None, to_date: str | None):
    items = []
    if next_cursor:
        next_ts, next_id = next_cursor
        fd = from_date or ''
        td = to_date or ''
        payload = f"acct_ledger_next:{next_ts}:{next_id}:{fd}:{td}"
        items.append({"label": "下一頁", "text": payload, "type": "message"})
    items.append({"label": "篩選區間", "text": "acct_ledger_range", "type": "message"})
    items.append({"label": "回帳務處理", "text": "help_category_accounting", "type": "message"})
    return QuickReplyManager._build_quick_reply_data(items)


def start_ledger(reply_token: str, user_id: str) -> None:
    rows = _fetch_ledger_page(None, None, None, None, LEDGER_PAGE_SIZE + 1)
    if not rows:
        ResponseHandler.send_response(reply_token, QuickReplyManager.create_text_response("目前查無明細", _ledger_quick_reply(None, None, None)))
        return
    has_more = len(rows) > LEDGER_PAGE_SIZE
    page_rows = rows[:LEDGER_PAGE_SIZE]
    text = _ledger_reply_text(page_rows, page_no=1)
    next_cursor = None
    if has_more:
        last = page_rows[-1]
        next_cursor = (last.occurred_at.isoformat(), last.id)
    resp = {
        "type": QuickReplyManager.ResponseType.TEXT_WITH_QUICK_REPLY,
        "text": text,
        "quick_reply": _ledger_quick_reply(next_cursor, None, None),
    }
    ResponseHandler.send_response(reply_token, resp)


def next_ledger(reply_token: str, cursor_ts: str, cursor_id: int, from_date: str | None, to_date: str | None, page_no: int) -> None:
    rows = _fetch_ledger_page(from_date, to_date, cursor_ts, cursor_id, LEDGER_PAGE_SIZE + 1)
    if not rows:
        ResponseHandler.send_response(reply_token, QuickReplyManager.create_text_response("目前查無明細", _ledger_quick_reply(None, from_date, to_date)))
        return
    has_more = len(rows) > LEDGER_PAGE_SIZE
    page_rows = rows[:LEDGER_PAGE_SIZE]
    text = _ledger_reply_text(page_rows, page_no=page_no)
    next_cursor = None
    if has_more:
        last = page_rows[-1]
        next_cursor = (last.occurred_at.isoformat(), last.id)
    resp = {
        "type": QuickReplyManager.ResponseType.TEXT_WITH_QUICK_REPLY,
        "text": text,
        "quick_reply": _ledger_quick_reply(next_cursor, from_date, to_date),
    }
    ResponseHandler.send_response(reply_token, resp)


def range_ledger_start(user_id: str, reply_token: str) -> None:
    # 啟動區間對話
    conversation_manager.start_conversation(user_id, 'accounting_ledger_range', 'waiting_range', {}, '請輸入區間 YYYY-MM-DD YYYY-MM-DD', 5)
    prompt = "請輸入：YYYY-MM-DD YYYY-MM-DD"
    ResponseHandler.send_response(reply_token, QuickReplyManager.create_text_response(prompt, QuickReplyManager.create_common_buttons()["abandon_operation"]))


def handle_range_input(conversation: ActiveConversation, message_text: str, user_id: str, reply_token: str) -> None:
    try:
        parts = message_text.strip().split()
        if len(parts) != 2:
            raise ValueError
        fd = datetime.strptime(parts[0], '%Y-%m-%d').date().isoformat()
        td = datetime.strptime(parts[1], '%Y-%m-%d').date().isoformat()
    except Exception:
        ResponseHandler.send_response(reply_token, QuickReplyManager.create_text_response("格式：YYYY-MM-DD YYYY-MM-DD，請重新輸入", QuickReplyManager.create_common_buttons()["abandon_operation"]))
        return
    # 顯示第1頁
    rows = _fetch_ledger_page(fd, td, None, None, LEDGER_PAGE_SIZE + 1)
    conversation_manager.end_conversation(user_id, 'ledger range applied')
    if not rows:
        ResponseHandler.send_response(reply_token, QuickReplyManager.create_text_response("目前查無明細", _ledger_quick_reply(None, fd, td)))
        return
    has_more = len(rows) > LEDGER_PAGE_SIZE
    page_rows = rows[:LEDGER_PAGE_SIZE]
    text = _ledger_reply_text(page_rows, page_no=1)
    next_cursor = None
    if has_more:
        last = page_rows[-1]
        next_cursor = (last.occurred_at.isoformat(), last.id)
    resp = {
        "type": QuickReplyManager.ResponseType.TEXT_WITH_QUICK_REPLY,
        "text": text,
        "quick_reply": _ledger_quick_reply(next_cursor, fd, td),
    }
    ResponseHandler.send_response(reply_token, resp)
