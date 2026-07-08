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


def find_weekly_charge_for_week(*, session, week_end_date: _date) -> Optional[dict]:
    """查該太陽週（週末 = week_end_date 星期六）是否已有「有效」的週扣款分錄。

    - occurred_at 比對走 AT TIME ZONE 'UTC'（跟 ledger 讀取端同一套口徑）
    - 已被沖正（存在 type='void' 且 reference_no / memo 指回該筆）的分錄不算 —
      沖正後重記必須放行

    Returns:
        {'id', 'amount_out', 'occurred_at'} 或 None
    """
    row = session.execute(text("""
        SELECT a.id,
               COALESCE(a.amount_out, 0) AS amount_out,
               a.occurred_at AT TIME ZONE 'UTC' AS occurred_at
        FROM account_ledger a
        WHERE a.type = 'weekly_charge'
          AND (a.occurred_at AT TIME ZONE 'UTC')::date = :week_end
          AND NOT EXISTS (
              SELECT 1 FROM account_ledger v
              WHERE v.type = 'void'
                AND (v.reference_no = CAST(a.id AS text)
                     OR v.memo LIKE '沖正 #' || a.id || '：%')
          )
        ORDER BY a.id DESC
        LIMIT 1
    """), {'week_end': week_end_date}).fetchone()
    if not row:
        return None
    return {
        'id': int(row[0]),
        'amount_out': int(row[1] or 0),
        'occurred_at': row[2],
    }


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
    allow_duplicate: bool = False,
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

    防重複：同一週（同週六 23:59）已有「有效」weekly_charge 分錄 → fail。
    已被沖正的舊分錄不擋（沖正後重記是正常流程）。
    allow_duplicate=True 才放行（LIFF / AI 都預設 False，需明確覆蓋）。
    """
    if not isinstance(amount, int) or amount <= 0:
        return ToolResult.fail("amount 必須是正整數")
    # AI / 表單可能傳 str（'true' / '1'）→ coerce
    if isinstance(allow_duplicate, str):
        allow_duplicate = allow_duplicate.strip().lower() in ('true', '1', 'yes')

    occurred_at = _last_saturday_2359()
    week_end = occurred_at.date()
    memo = f"週末 {week_end.isoformat()} 扣款"

    if not allow_duplicate:
        existing = find_weekly_charge_for_week(session=session, week_end_date=week_end)
        if existing:
            return ToolResult.fail(
                f"❌ 該週（週末 {week_end.month}/{week_end.day}）已記過扣款 "
                f"NT$ {existing['amount_out']:,}（#{existing['id']}）。\n"
                f"💡 金額有誤請先沖正再重記 — 可輸入「沖正 {existing['id']}」。",
                existing_id=existing['id'],
                existing_amount=existing['amount_out'],
            )

    row = session.execute(text("""
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
    }).fetchone()
    ledger_id = int(row[0])

    write_audit(
        session=session,
        user_id=user_id, user_name=user_name,
        action_type='record_weekly_charge',
        target_table='account_ledger', target_id=ledger_id,
        before_state=None,
        after_state={
            'occurred_at': occurred_at.isoformat(),
            'amount_out': amount, 'memo': memo,
        },
        changed_fields=None,
        extra={'week_end_date': week_end.isoformat(),
               'allow_duplicate': bool(allow_duplicate)},
        via=via,
    )

    if auto_commit:
        session.commit()

    return ToolResult.success(
        data={
            'ledger_id': ledger_id,
            'amount': amount,
            'week_end_date': week_end.isoformat(),
            'occurred_at': occurred_at.isoformat(),
            'memo': memo,
        },
    )


# ============================================================
# 沖正（void）— 反向分錄更正記錯的帳
# ============================================================

_LEDGER_TYPE_LABELS = {
    'deposit': '入金',
    'weekly_charge': '扣款',
    'void': '沖正',
}


def _coerce_ledger_id(v):
    """AI 傳的 ledger_id 可能是 str → coerce 成 int，失敗回 None"""
    if isinstance(v, int):
        return v
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return None


def _fetch_ledger_entry(session, ledger_id: int) -> Optional[dict]:
    row = session.execute(text("""
        SELECT id,
               occurred_at AT TIME ZONE 'UTC' AS occurred_at,
               type, counterparty,
               COALESCE(amount_in, 0)  AS amount_in,
               COALESCE(amount_out, 0) AS amount_out,
               bank_name, bank_account_last4, reference_no, memo
        FROM account_ledger
        WHERE id = :id
    """), {'id': ledger_id}).fetchone()
    return dict(row._mapping) if row else None


def _find_void_of(session, ledger_id: int) -> Optional[dict]:
    """查 #ledger_id 是否已被沖正過，回沖正分錄（dict）或 None"""
    row = session.execute(text("""
        SELECT id, type,
               occurred_at AT TIME ZONE 'UTC' AS occurred_at,
               COALESCE(amount_in, 0)  AS amount_in,
               COALESCE(amount_out, 0) AS amount_out,
               memo
        FROM account_ledger
        WHERE type = 'void'
          AND (reference_no = :rid OR memo LIKE :pat)
        ORDER BY id DESC
        LIMIT 1
    """), {'rid': str(ledger_id), 'pat': f'沖正 #{ledger_id}：%'}).fetchone()
    return dict(row._mapping) if row else None


def _fmt_entry_line(entry: dict) -> str:
    """單筆分錄 → 人話一行（給確認 / 錯誤訊息用）"""
    label = _LEDGER_TYPE_LABELS.get(entry.get('type'), entry.get('type') or '?')
    amount_in = int(entry.get('amount_in') or 0)
    amount_out = int(entry.get('amount_out') or 0)
    amt = f"+{amount_in:,}" if amount_in > 0 else f"-{amount_out:,}"
    dt = entry.get('occurred_at')
    dt_text = dt.strftime('%Y-%m-%d %H:%M') if dt is not None else '—'
    note = entry.get('memo') or entry.get('counterparty') or ''
    return f"#{entry['id']} {dt_text} {label} {amt}（{note}）"


def query_ledger_entry(
    *,
    session,
    ledger_id: int,
) -> ToolResult:
    """查單筆帳務分錄詳情（給沖正前確認用）

    Triggers: 「分錄 83」「帳務明細 #83 是哪筆」；沖正前 AI 必先 call 這個
    列出該筆內容給用戶確認。
    """
    lid = _coerce_ledger_id(ledger_id)
    if lid is None:
        return ToolResult.fail(f"ledger_id 必須是整數，收到: {ledger_id!r}")

    entry = _fetch_ledger_entry(session, lid)
    if not entry:
        return ToolResult.fail(
            f"❌ 找不到帳務分錄 #{lid}。\n"
            f"💡 可輸入「帳務處理」→「明細」確認分錄編號。"
        )

    voided_by = _find_void_of(session, lid)
    lines = [f"📒 帳務分錄 {_fmt_entry_line(entry)}"]
    if entry.get('type') == 'void':
        lines.append("（此筆本身是沖正分錄，不可再沖正）")
    elif voided_by:
        lines.append(f"⚠️ 此筆已被沖正：{_fmt_entry_line(voided_by)}")
    return ToolResult.success(
        data='\n'.join(lines),
        entry={k: (v.isoformat() if hasattr(v, 'isoformat') else v)
               for k, v in entry.items()},
        voided=bool(voided_by),
    )


def void_ledger_entry(
    *,
    session,
    ledger_id: int,
    reason: str,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """沖正一筆帳務分錄（反向分錄，不刪原筆）

    做法：新增一筆 type='void' 的反向分錄 —
      - 金額反號：amount_in ↔ amount_out 對調
      - occurred_at = 現在（台灣時間，跟檔內既有寫法一致存 naive wall time）
      - counterparty = '沖正 #原ID'、memo = '沖正 #原ID：原因'、
        reference_no = 原ID（機器可追）

    防呆：
      - 原筆不存在 → fail
      - 原筆本身是沖正分錄 → fail
      - 原筆已被沖正過 → fail（顯示先前沖正筆）

    ⚠️ 沖正入金時 payments 表原紀錄保留不動（僅更正 ledger 帳面）。
    """
    lid = _coerce_ledger_id(ledger_id)
    if lid is None:
        return ToolResult.fail(f"ledger_id 必須是整數，收到: {ledger_id!r}")
    if not reason or not str(reason).strip():
        return ToolResult.fail("請提供沖正原因")
    reason = str(reason).strip()

    original = _fetch_ledger_entry(session, lid)
    if not original:
        return ToolResult.fail(
            f"❌ 找不到帳務分錄 #{lid}。\n"
            f"💡 可輸入「帳務處理」→「明細」確認分錄編號。"
        )
    if original.get('type') == 'void' or (original.get('memo') or '').startswith('沖正 #'):
        return ToolResult.fail(
            f"❌ 分錄 #{lid} 本身是沖正分錄，不能再沖正。\n"
            f"💡 若沖錯了，請對「原始分錄」重新記帳。"
        )
    prev_void = _find_void_of(session, lid)
    if prev_void:
        return ToolResult.fail(
            f"❌ 分錄 #{lid} 已被沖正過：{_fmt_entry_line(prev_void)}\n"
            f"💡 同一筆不能沖正兩次。",
            void_id=prev_void['id'],
        )

    orig_in = int(original.get('amount_in') or 0)
    orig_out = int(original.get('amount_out') or 0)
    if orig_in == 0 and orig_out == 0:
        return ToolResult.fail(f"❌ 分錄 #{lid} 金額為 0，無需沖正。")

    # 反向分錄：金額對調（原支出 → 沖回收入；原收入 → 沖回支出）
    occurred_at = get_taiwan_time().replace(tzinfo=None)
    memo = f"沖正 #{lid}：{reason}"
    row = session.execute(text("""
        INSERT INTO account_ledger
            (occurred_at, type, counterparty,
             amount_in, amount_out,
             bank_name, bank_account_last4, reference_no, memo, created_at)
        VALUES
            (:occurred_at, 'void', :counterparty,
             :amount_in, :amount_out,
             NULL, NULL, :ref, :memo, NOW())
        RETURNING id
    """), {
        'occurred_at': occurred_at,
        'counterparty': f'沖正 #{lid}',
        'amount_in': orig_out,   # 反號
        'amount_out': orig_in,   # 反號
        'ref': str(lid),
        'memo': memo,
    }).fetchone()
    void_id = int(row[0])

    write_audit(
        session=session,
        user_id=user_id, user_name=user_name,
        action_type='void_ledger_entry',
        target_table='account_ledger', target_id=void_id,
        before_state=original,
        after_state={
            'void_id': void_id,
            'occurred_at': occurred_at.isoformat(),
            'amount_in': orig_out, 'amount_out': orig_in,
            'memo': memo,
        },
        changed_fields=None,
        reason=reason,
        extra={'original_ledger_id': lid},
        via=via,
    )

    if auto_commit:
        session.commit()

    delta = f"+{orig_out:,}" if orig_out > 0 else f"-{orig_in:,}"
    msg = (
        f"✅ 已沖正分錄 {_fmt_entry_line(original)}\n"
        f"沖正分錄：#{void_id} {delta}\n"
        f"原因：{reason}"
    )
    return ToolResult.success(
        data=msg,
        void_id=void_id,
        original_id=lid,
        amount_in=orig_out,
        amount_out=orig_in,
    )


# ============================================================
# 週扣款表單預填（LIFF weekly_payment 用）
# ============================================================

def weekly_charge_prefill(*, session) -> ToolResult:
    """算週扣款表單的預填資訊

    週界跟 record_weekly_charge 的鎖定時間一致（週末 = _last_saturday_2359 的
    星期六），該週 = 週日 ~ 該週六。金額口徑 = 診所類別已完成班次的實收總額
    （實收 = 錶價 + 加成，重用 aggregate_completed_trips，
    同 report_service 週報表的實收算法）。

    Returns data:
        {
            'week_start': 'YYYY-MM-DD',   # 週日
            'week_end': 'YYYY-MM-DD',     # 週六（= 扣款鎖定日）
            'trip_count': int,            # 診所已完成班次數
            'total_amount': int,          # 實收總額
            'existing_charge': {'id', 'amount'} | None,  # 該週已記的扣款
        }
    """
    week_end = _last_saturday_2359().date()
    week_start = week_end - timedelta(days=6)

    # lazy import 避免 accounting ↔ completed_trip 循環 import
    from rewrite.tools.completed_trip import aggregate_completed_trips
    agg = aggregate_completed_trips(
        session=session,
        date_from=week_start, date_to=week_end,
        category='診所',
    )
    if agg.ok:
        trip_count = int(agg.data.get('total_count') or 0)
        total_amount = int(agg.data.get('sum_amount') or 0)
    else:
        # 「範圍內沒有已完成班次」→ 0 趟 0 元，表單照樣可手填
        trip_count = 0
        total_amount = 0

    existing = find_weekly_charge_for_week(session=session, week_end_date=week_end)
    return ToolResult.success(
        data={
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'trip_count': trip_count,
            'total_amount': total_amount,
            'existing_charge': (
                {'id': existing['id'], 'amount': existing['amount_out']}
                if existing else None
            ),
        },
    )
