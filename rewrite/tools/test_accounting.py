"""
測試帳務 atomic tools：
  record_deposit         — 原行為不變（含防重複）
  record_weekly_charge   — 週扣款防重複 / allow_duplicate 放行 / 沖正後重記放行
  void_ledger_entry      — 沖正正常 / 重複沖正被擋 / 沖正後餘額回原值
  query_ledger_entry     — 單筆分錄查詢（沖正前確認用）
  weekly_charge_prefill  — 週扣款表單預填

策略：auto_commit=False + 最後 session.rollback()，不留痕跡。
"""
import sys
from datetime import date, timedelta
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import Session
from sqlalchemy import text
from rewrite.tools.accounting import (
    query_balance,
    record_deposit,
    record_weekly_charge,
    void_ledger_entry,
    query_ledger_entry,
    weekly_charge_prefill,
    find_weekly_charge_for_week,
    _last_saturday_2359,
)


def banner(label):
    print(f'\n{"=" * 60}\n# {label}\n{"=" * 60}')


def balance(s) -> int:
    r = query_balance(session=s)
    assert r.ok
    return r.data['balance']


s = Session()
try:
    WEEK_END = _last_saturday_2359().date()

    # ============================================================
    # SETUP: 同 tx 內清掉該週已存在的 weekly_charge（含其沖正分錄）
    # 讓防重複測試 deterministic；最後 rollback 全部還原
    # ============================================================
    banner(f'SETUP: 清空週末 {WEEK_END} 的 weekly_charge（tx 內，會 rollback）')
    deleted = s.execute(text("""
        DELETE FROM account_ledger v
        USING account_ledger a
        WHERE v.type = 'void'
          AND a.type = 'weekly_charge'
          AND (a.occurred_at AT TIME ZONE 'UTC')::date = :we
          AND (v.reference_no = CAST(a.id AS text)
               OR v.memo LIKE '沖正 #' || a.id || '：%')
    """), {'we': WEEK_END}).rowcount
    deleted2 = s.execute(text("""
        DELETE FROM account_ledger
        WHERE type = 'weekly_charge'
          AND (occurred_at AT TIME ZONE 'UTC')::date = :we
    """), {'we': WEEK_END}).rowcount
    print(f'  清掉 void {deleted} 筆 / weekly_charge {deleted2} 筆')
    assert find_weekly_charge_for_week(session=s, week_end_date=WEEK_END) is None

    BALANCE_0 = balance(s)
    print(f'  起始餘額: {BALANCE_0:,}')

    # ============================================================
    # D1: record_deposit 原行為不變
    # ============================================================
    banner('D1: record_deposit 正常 + 防重複')
    DEP_DATE = date(2030, 1, 2)  # 未來日期，避免撞既有資料
    r = record_deposit(
        session=s, deposit_date=DEP_DATE, amount=12345,
        bank_name='測試銀行', last4='9876',
        user_name='test', via='test', auto_commit=False,
    )
    print(f'  首次 → ok={r.ok} data={r.data}')
    assert r.ok and r.data['payment_id']
    assert balance(s) == BALANCE_0 + 12345

    r = record_deposit(
        session=s, deposit_date=DEP_DATE, amount=12345,
        bank_name='測試銀行', last4='9876',
        user_name='test', via='test', auto_commit=False,
    )
    print(f'  重複 → ok={r.ok} error={r.error!r}')
    assert not r.ok and '已存在' in r.error

    r = record_deposit(
        session=s, deposit_date=DEP_DATE, amount=100,
        bank_name='測試銀行', last4='98a6',
        user_name='test', via='test', auto_commit=False,
    )
    print(f'  last4 非數字 → ok={r.ok} error={r.error!r}')
    assert not r.ok

    BALANCE_AFTER_DEP = balance(s)

    # ============================================================
    # W1: record_weekly_charge 首次 OK
    # ============================================================
    banner('W1: record_weekly_charge 首次')
    r = record_weekly_charge(
        session=s, amount=25000,
        user_name='test', via='test', auto_commit=False,
    )
    print(f'  → ok={r.ok} data={r.data}')
    assert r.ok
    CHARGE_A = r.data['ledger_id']
    assert CHARGE_A and r.data['week_end_date'] == WEEK_END.isoformat()
    assert balance(s) == BALANCE_AFTER_DEP - 25000

    # ============================================================
    # W2: 同週重複 → 被擋
    # ============================================================
    banner('W2: 同週重複記扣款 → fail')
    r = record_weekly_charge(
        session=s, amount=26000,
        user_name='test', via='test', auto_commit=False,
    )
    print(f'  → ok={r.ok} error={r.error!r}')
    assert not r.ok
    assert '已記過扣款' in r.error and f'#{CHARGE_A}' in r.error
    assert '25,000' in r.error  # 訊息帶既有金額
    assert r.meta.get('existing_id') == CHARGE_A
    assert balance(s) == BALANCE_AFTER_DEP - 25000  # 沒寫進去

    # ============================================================
    # Q1: query_ledger_entry（沖正前確認）
    # ============================================================
    banner('Q1: query_ledger_entry')
    r = query_ledger_entry(session=s, ledger_id=str(CHARGE_A))  # str coerce
    print(f'  → ok={r.ok}\n  {r.data}')
    assert r.ok and f'#{CHARGE_A}' in r.data and '扣款' in r.data
    assert r.meta.get('voided') is False

    r = query_ledger_entry(session=s, ledger_id=99999999)
    print(f'  不存在 → ok={r.ok} error={r.error!r}')
    assert not r.ok and '找不到' in r.error

    r = query_ledger_entry(session=s, ledger_id='abc')
    print(f'  非整數 → ok={r.ok} error={r.error!r}')
    assert not r.ok

    # ============================================================
    # V1: 沖正 → 餘額回原值
    # ============================================================
    banner('V1: void_ledger_entry 正常沖正')
    r = void_ledger_entry(
        session=s, ledger_id=CHARGE_A, reason='金額記錯',
        user_name='test', via='test', auto_commit=False,
    )
    print(f'  → ok={r.ok}\n  {r.data}')
    assert r.ok
    VOID_A = r.meta['void_id']
    assert r.meta['original_id'] == CHARGE_A
    assert r.meta['amount_in'] == 25000  # 反號：原支出 → 沖回收入
    assert balance(s) == BALANCE_AFTER_DEP  # 餘額回原值
    # 沖正後該週不再有「有效」扣款
    assert find_weekly_charge_for_week(session=s, week_end_date=WEEK_END) is None

    # V1b: reason 空 → fail
    r = void_ledger_entry(session=s, ledger_id=CHARGE_A, reason='  ',
                          auto_commit=False)
    print(f'  reason 空 → ok={r.ok} error={r.error!r}')
    assert not r.ok and '原因' in r.error

    # ============================================================
    # V2: 重複沖正 → 被擋
    # ============================================================
    banner('V2: 重複沖正 → fail')
    r = void_ledger_entry(
        session=s, ledger_id=CHARGE_A, reason='再沖一次',
        user_name='test', via='test', auto_commit=False,
    )
    print(f'  → ok={r.ok} error={r.error!r}')
    assert not r.ok and '已被沖正' in r.error and f'#{VOID_A}' in r.error

    # V2b: 沖正「沖正分錄」→ 被擋
    r = void_ledger_entry(
        session=s, ledger_id=VOID_A, reason='沖沖正',
        user_name='test', via='test', auto_commit=False,
    )
    print(f'  沖沖正分錄 → ok={r.ok} error={r.error!r}')
    assert not r.ok and '沖正分錄' in r.error

    # V2c: 不存在 → fail
    r = void_ledger_entry(session=s, ledger_id=99999999, reason='x',
                          auto_commit=False)
    print(f'  不存在 → ok={r.ok} error={r.error!r}')
    assert not r.ok and '找不到' in r.error

    # ============================================================
    # W3: 沖正後重記 → 放行（不需 allow_duplicate）
    # ============================================================
    banner('W3: 沖正後重記扣款 → OK')
    r = record_weekly_charge(
        session=s, amount=26000,
        user_name='test', via='test', auto_commit=False,
    )
    print(f'  → ok={r.ok} data={r.data}')
    assert r.ok
    CHARGE_B = r.data['ledger_id']
    assert balance(s) == BALANCE_AFTER_DEP - 26000

    # ============================================================
    # W4: allow_duplicate=True 明確覆蓋 → 放行
    # ============================================================
    banner('W4: allow_duplicate=True → 放行')
    r = record_weekly_charge(
        session=s, amount=100, allow_duplicate=True,
        user_name='test', via='test', auto_commit=False,
    )
    print(f'  → ok={r.ok} data={r.data}')
    assert r.ok and r.data['ledger_id'] != CHARGE_B
    assert balance(s) == BALANCE_AFTER_DEP - 26100

    # ============================================================
    # P1: weekly_charge_prefill
    # ============================================================
    banner('P1: weekly_charge_prefill')
    r = weekly_charge_prefill(session=s)
    print(f'  → ok={r.ok} data={r.data}')
    assert r.ok
    d = r.data
    assert d['week_end'] == WEEK_END.isoformat()
    assert date.fromisoformat(d['week_end']) - date.fromisoformat(d['week_start']) \
        == timedelta(days=6)
    assert isinstance(d['trip_count'], int) and isinstance(d['total_amount'], int)
    assert d['total_amount'] >= 0
    # 該週目前有兩筆有效扣款（B + allow_dup 那筆）→ existing_charge 取最新
    assert d['existing_charge'] is not None

    print('\n✅ test_accounting 全部通過')
finally:
    s.rollback()
    s.close()
    print('（已 rollback，不留測試資料）')
