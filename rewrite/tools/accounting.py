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
