"""
帳務處理 atomic tools（LIFF 用）

對齊 legacy modules/handlers/accounting.py 的業務邏輯：
  - account_ledger 表：amount_in / amount_out
  - payments 表：入金紀錄（含銀行 / 後四碼）
  - 餘額 = SUM(amount_in) - SUM(amount_out) from account_ledger
  - 入金時間鎖 09:00；週扣款鎖上週六 23:59
  - 防重複：同 payer + transferred_at + amount

⚠️ legacy SQL 邏輯穩定不重做，直接寫 atomic 形式 wrapper。
"""
import logging
from datetime import date as _date, datetime, time as _time, timedelta
from typing import Optional

from sqlalchemy import text

from rewrite.tools.base import ToolResult, write_audit
# 沿用 legacy taiwan_time helper 算上週六
from modules.utils.taiwan_time import get_taiwan_time

logger = logging.getLogger(__name__)


def query_balance(*, session) -> ToolResult:
    """回目前帳戶餘額（NT$ 整數）"""
    row = session.execute(text("""
        SELECT COALESCE(SUM(amount_in), 0) AS total_in,
               COALESCE(SUM(amount_out), 0) AS total_out
        FROM account_ledger
    """)).fetchone()
    total_in = int(row[0] or 0) if row else 0
    total_out = int(row[1] or 0) if row else 0
    balance = total_in - total_out
    return ToolResult.success(
        data={
            'balance': balance,
            'total_in': total_in,
            'total_out': total_out,
        },
    )


LEDGER_PAGE_SIZE = 10
LEDGER_CAROUSEL_MAX_ROWS = 84  # 12 bubbles × 7 rows / bubble (view 端切; 50KB 上限)


def query_ledger_carousel(
    *,
    session,
    from_date: Optional[_date] = None,
    to_date: Optional[_date] = None,
    limit: int = LEDGER_CAROUSEL_MAX_ROWS,
) -> ToolResult:
    """撈 carousel 用的 ledger（一次 N 筆，含 running_balance）

    跟 query_ledger_page 共用同一條 SQL，但不分頁；給 carousel view 用。
    """
    sql = text("""
        WITH all_with_balance AS (
            SELECT a.id,
                   a.occurred_at AT TIME ZONE 'UTC' AS occurred_at,
                   a.type,
                   a.counterparty,
                   COALESCE(a.amount_in, 0)  AS amount_in,
                   COALESCE(a.amount_out, 0) AS amount_out,
                   SUM(COALESCE(a.amount_in, 0) - COALESCE(a.amount_out, 0))
                     OVER (ORDER BY a.occurred_at ASC, a.id ASC
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_balance
            FROM account_ledger a
            WHERE (CAST(:from_date AS date) IS NULL
                   OR (a.occurred_at AT TIME ZONE 'UTC')::date >= CAST(:from_date AS date))
              AND (CAST(:to_date AS date) IS NULL
                   OR (a.occurred_at AT TIME ZONE 'UTC')::date <= CAST(:to_date AS date))
        )
        SELECT *
        FROM all_with_balance
        ORDER BY occurred_at DESC, id DESC
        LIMIT :limit
    """)
    rows = session.execute(sql, {
        'from_date': from_date,
        'to_date': to_date,
        'limit': limit + 1,  # +1 判斷 has_more
    }).fetchall()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    data = [dict(r._mapping) for r in page_rows]
    return ToolResult.success(data=data, has_more=has_more)


def query_ledger_page(
    *,
    session,
    from_date: Optional[_date] = None,
    to_date: Optional[_date] = None,
    last_ts: Optional[str] = None,
    last_id: Optional[int] = None,
) -> ToolResult:
    """撈帳務明細一頁（cursor-based，每頁 LEDGER_PAGE_SIZE 筆，附 running_balance）

    對齊 legacy modules/handlers/accounting._fetch_ledger_page。
    SQL 在指定日期範圍內 window function 累加餘額（occurred_at, id 升冪），
    再用 (last_ts, last_id) 翻頁過濾，最後 desc 排序回傳。

    Args:
        from_date / to_date: 日期範圍（None = 不限）
        last_ts / last_id: 上一頁最後一筆的 cursor (ISO str + int)

    Returns:
        data=[{id, occurred_at(ISO), type, counterparty, amount_in,
               amount_out, running_balance}, ...]
        meta:
          has_more: bool — 是否還有下一頁
          next_cursor: (ts, id) 或 None
    """
    sql = text("""
        WITH all_with_balance AS (
            SELECT a.id,
                   a.occurred_at AT TIME ZONE 'UTC' AS occurred_at,
                   a.type,
                   a.counterparty,
                   COALESCE(a.amount_in, 0)  AS amount_in,
                   COALESCE(a.amount_out, 0) AS amount_out,
                   SUM(COALESCE(a.amount_in, 0) - COALESCE(a.amount_out, 0))
                     OVER (ORDER BY a.occurred_at ASC, a.id ASC
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_balance
            FROM account_ledger a
            WHERE (CAST(:from_date AS date) IS NULL
                   OR (a.occurred_at AT TIME ZONE 'UTC')::date >= CAST(:from_date AS date))
              AND (CAST(:to_date AS date) IS NULL
                   OR (a.occurred_at AT TIME ZONE 'UTC')::date <= CAST(:to_date AS date))
        )
        SELECT *
        FROM all_with_balance
        WHERE (CAST(:last_ts AS timestamptz) IS NULL
               OR (occurred_at, id) < ((CAST(:last_ts AS timestamptz) AT TIME ZONE 'UTC'), :last_id))
        ORDER BY occurred_at DESC, id DESC
        LIMIT :limit
    """)

    fetch_limit = LEDGER_PAGE_SIZE + 1  # +1 用來判斷 has_more
    rows = session.execute(sql, {
        'from_date': from_date,
        'to_date': to_date,
        'last_ts': last_ts,
        'last_id': last_id,
        'limit': fetch_limit,
    }).fetchall()

    has_more = len(rows) > LEDGER_PAGE_SIZE
    page_rows = rows[:LEDGER_PAGE_SIZE]

    data = []
    for r in page_rows:
        d = dict(r._mapping)
        if d.get('occurred_at'):
            d['occurred_at'] = d['occurred_at']  # keep datetime for view to format
        data.append(d)

    next_cursor = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = (last.occurred_at.replace(tzinfo=None).isoformat() + '+00:00',
                       last.id)

    return ToolResult.success(
        data=data,
        has_more=has_more,
        next_cursor=next_cursor,
    )


def _last_saturday_2359() -> datetime:
    """上週六 23:59 — 對齊 legacy last_saturday_2359"""
    now_tw = get_taiwan_time()
    today = now_tw.date()
    # Python: Mon=0..Sun=6, Sat=5
    days_since_saturday = (today.weekday() - 5) % 7
    target = today - timedelta(days=days_since_saturday)
    return datetime.combine(target, _time(23, 59))


def record_deposit(
    *,
    session,
    deposit_date: _date,
    amount: int,
    bank_name: str,
    last4: str,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """記錄入金（同時寫 payments + account_ledger）

    對齊 legacy handle_deposit_input：
      - payer 固定 '達恩診所'
      - transferred_at = deposit_date 09:00
      - 防重複：同 payer + transferred_at + amount → fail
    """
    # 驗證
    if not deposit_date:
        return ToolResult.fail("deposit_date 必填")
    if not isinstance(amount, int) or amount <= 0:
        return ToolResult.fail("amount 必須是正整數")
    if not bank_name or not bank_name.strip():
        return ToolResult.fail("bank_name 必填")
    if not last4 or not (len(last4) == 4 and last4.isdigit()):
        return ToolResult.fail("last4 必須是 4 位數字")

    payer = '達恩診所'
    transferred_dt = datetime.combine(deposit_date, _time(9, 0))
    bank_name = bank_name.strip()

    # 防重複
    dup = session.execute(text("""
        SELECT 1 FROM payments
        WHERE payer = :payer AND transferred_at = :ts AND amount_twd = :amt
        LIMIT 1
    """), {'payer': payer, 'ts': transferred_dt, 'amt': amount}).fetchone()
    if dup:
        return ToolResult.fail(
            f"⚠️ 已存在相同入金紀錄（{deposit_date.isoformat()} {amount} {bank_name}）"
        )

    # 1) payments
    pay_row = session.execute(text("""
        INSERT INTO payments
            (payer, amount_twd, transferred_at,
             bank_name, bank_account_last4, reference_no, notes, created_at)
        VALUES
            (:payer, :amount, :ts,
             :bank_name, :last4, NULL, '入金', NOW())
        RETURNING id
    """), {
        'payer': payer, 'amount': amount, 'ts': transferred_dt,
        'bank_name': bank_name, 'last4': last4,
    }).fetchone()
    pay_id = pay_row[0]

    # 2) account_ledger 鏡射
    session.execute(text("""
        INSERT INTO account_ledger
            (occurred_at, type, counterparty,
             amount_in, amount_out,
             bank_name, bank_account_last4, reference_no, memo, created_at)
        VALUES
            (:occurred_at, 'deposit', :counterparty,
             :amount_in, 0,
             :bank_name, :last4, :ref, '入金', NOW())
    """), {
        'occurred_at': transferred_dt,
        'counterparty': f"{bank_name} {last4}",
        'amount_in': amount,
        'bank_name': bank_name, 'last4': last4,
        'ref': str(pay_id),
    })

    # audit
    write_audit(
        session=session,
        user_id=user_id, user_name=user_name,
        action_type='record_deposit',
        target_table='payments', target_id=pay_id,
        before_state=None,
        after_state={
            'payer': payer, 'amount': amount,
            'transferred_at': transferred_dt.isoformat(),
            'bank': bank_name, 'last4': last4,
        },
        changed_fields=None,
        extra={'deposit_date': deposit_date.isoformat()},
        via=via,
    )

    if auto_commit:
        session.commit()

    return ToolResult.success(
        data={
            'payment_id': pay_id,
            'amount': amount,
            'deposit_date': deposit_date.isoformat(),
            'bank_name': bank_name,
            'last4': last4,
        },
    )


def record_weekly_charge(
    *,
    session,
    amount: int,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """記錄上週扣款（鎖定上週六 23:59）

    對齊 legacy handle_weekly_input：
      - occurred_at = 上週六 23:59
      - type='weekly_charge', counterparty='車資扣款'
      - amount_out = amount
    """
    if not isinstance(amount, int) or amount <= 0:
        return ToolResult.fail("amount 必須是正整數")

    occurred_at = _last_saturday_2359()
    memo = f"週末 {occurred_at.date().isoformat()} 扣款"

    session.execute(text("""
        INSERT INTO account_ledger
            (occurred_at, type, counterparty,
             amount_in, amount_out,
             bank_name, bank_account_last4, reference_no, memo, created_at)
        VALUES
            (:occurred_at, 'weekly_charge', '車資扣款',
             0, :amount_out,
             NULL, NULL, NULL, :memo, NOW())
        RETURNING id
    """), {
        'occurred_at': occurred_at, 'amount_out': amount, 'memo': memo,
    })

    write_audit(
        session=session,
        user_id=user_id, user_name=user_name,
        action_type='record_weekly_charge',
        target_table='account_ledger', target_id=0,  # batch-ish
        before_state=None,
        after_state={
            'occurred_at': occurred_at.isoformat(),
            'amount_out': amount, 'memo': memo,
        },
        changed_fields=None, extra={'week_end_date': occurred_at.date().isoformat()},
        via=via,
    )

    if auto_commit:
        session.commit()

    return ToolResult.success(
        data={
            'amount': amount,
            'week_end_date': occurred_at.date().isoformat(),
            'occurred_at': occurred_at.isoformat(),
            'memo': memo,
        },
    )
