"""
測試過去態 mutation：
  update_completed_trip_fare
  update_completed_trip_category
  update_trip_category（現在態 trips，對稱）

策略：auto_commit=False + 最後 session.rollback()，不留痕跡。
"""
import sys
from datetime import date
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import Session
from sqlalchemy import text
from rewrite.tools.completed_trip import (
    query_completed_trip_by_id,
    update_completed_trip_fare,
    update_completed_trip_category,
)
from rewrite.tools.trip import update_trip_category


def banner(label):
    print(f'\n{"=" * 60}\n# {label}\n{"=" * 60}')


s = Session()
try:
    # ============================================================
    # 找一筆現在態 trips（測試 update_trip_category 用）
    # ============================================================
    banner('SETUP: 找一筆 trips row 測 update_trip_category')
    row = s.execute(text(
        "SELECT trip_id, category FROM trips ORDER BY trip_id DESC LIMIT 1"
    )).fetchone()
    if not row:
        print('  ❌ trips 沒資料，跳過 update_trip_category 測試')
        TEST_TRIP = None
    else:
        TEST_TRIP = (row[0], row[1])
        print(f'  trips trip_id={row[0]}, category={row[1]!r}')

    # ============================================================
    # update_completed_trip_fare — 動態抓現存 completed_trip
    # （hardcoded id 會被同步的 unique_code 衝突邏輯洗掉，改 dynamic 一勞永逸）
    # 優先挑有 modification_reason 的 row 測累加邏輯
    # ============================================================
    target_row = s.execute(text("""
        SELECT id FROM completed_trips
        WHERE modification_reason IS NOT NULL
        ORDER BY id DESC LIMIT 1
    """)).fetchone()
    if not target_row:
        # 沒有 modification_reason 的話退而求其次
        target_row = s.execute(text(
            "SELECT id FROM completed_trips ORDER BY id DESC LIMIT 1"
        )).fetchone()
    assert target_row, 'completed_trips 沒資料，無法測試'
    TARGET_ID = target_row[0]
    banner(f'M1: update_completed_trip_fare({TARGET_ID})')
    r = query_completed_trip_by_id(TARGET_ID, session=s)
    assert r.ok, f'{TARGET_ID} 應存在: {r.error}'
    before = r.data
    # 算原本 [N] 編號數，加完應該 N+1
    import re
    existing_marks = len(re.findall(r'\[(\d+)\]', before.modification_reason or ''))
    expected_next = existing_marks + 1
    print(f'  before: meter={before.meter_fare} extra={before.extra_fare} '
          f'mod={before.modification_reason!r}')

    # M1a: reason 空 → fail
    r = update_completed_trip_fare(
        session=s, completed_trip_id=TARGET_ID,
        meter_fare=1250, extra_fare=750,
        reason='', user_name='test',
        auto_commit=False,
    )
    print(f'  reason 空 → ok={r.ok} error={r.error!r}')
    assert not r.ok and '原因' in r.error

    # M1b: 都沒給 → fail
    r = update_completed_trip_fare(
        session=s, completed_trip_id=TARGET_ID,
        reason='測試', user_name='test',
        auto_commit=False,
    )
    print(f'  meter/extra 都沒給 → ok={r.ok} error={r.error!r}')
    assert not r.ok

    # M1c: 同樣的值 → fail（沒變動）
    r = update_completed_trip_fare(
        session=s, completed_trip_id=TARGET_ID,
        meter_fare=before.meter_fare, extra_fare=before.extra_fare,
        reason='測試', user_name='test',
        auto_commit=False,
    )
    print(f'  沒變動 → ok={r.ok} error={r.error!r}')
    assert not r.ok and '沒變動' in r.error

    # M1d: 改成 1500+800 → 應 success
    r = update_completed_trip_fare(
        session=s, completed_trip_id=TARGET_ID,
        meter_fare=1500, extra_fare=800,
        reason='測試: 加班計算錯誤', user_name='測試員',
        auto_commit=False,
    )
    assert r.ok, f'M1d failed: {r.error}'
    after = r.data
    print(f'  after:  meter={after.meter_fare} extra={after.extra_fare}')
    print(f'  modification_reason: {after.modification_reason!r}')
    assert after.meter_fare == 1500
    assert after.extra_fare == 800
    assert f'[{expected_next}]' in after.modification_reason, \
        f'累加應該變 [{expected_next}], 實際 mod: {after.modification_reason!r}'
    assert '改車資' in after.modification_reason
    assert '加班計算錯誤' in after.modification_reason

    # ============================================================
    # update_completed_trip_category — 改類別
    # ============================================================
    banner(f'M2: update_completed_trip_category({TARGET_ID})')
    # 算「不同 category」當改後目標
    other_category = '診所' if before.category != '診所' else '東洋'

    # M2a: reason 空 → fail
    r = update_completed_trip_category(
        session=s, completed_trip_id=TARGET_ID,
        new_category=other_category, reason='',
        auto_commit=False,
    )
    print(f'  reason 空 → ok={r.ok} error={r.error!r}')
    assert not r.ok

    # M2b: 同類別（before.category）→ fail
    r = update_completed_trip_category(
        session=s, completed_trip_id=TARGET_ID,
        new_category=before.category, reason='測試',
        auto_commit=False,
    )
    print(f'  同類別 → ok={r.ok} error={r.error!r}')
    assert not r.ok and '已是' in r.error

    # M2c: 無效類別 → fail
    r = update_completed_trip_category(
        session=s, completed_trip_id=TARGET_ID,
        new_category='飛機', reason='測試',
        auto_commit=False,
    )
    print(f'  無效類別 → ok={r.ok} error={r.error!r}')
    assert not r.ok and '無效' in r.error

    # M2d: 改成 other_category → success
    r = update_completed_trip_category(
        session=s, completed_trip_id=TARGET_ID,
        new_category=other_category, reason='測試: 報帳分類錯誤',
        user_name='測試員',
        auto_commit=False,
    )
    assert r.ok, f'M2d failed: {r.error}'
    print(f'  category: {before.category} → {r.data.category}')
    print(f'  modification_reason: {r.data.modification_reason!r}')
    assert r.data.category == other_category
    # category 的累加 = 上面 fare 的 expected_next + 1
    assert f'[{expected_next + 1}]' in r.data.modification_reason
    assert '改類別' in r.data.modification_reason

    # ============================================================
    # update_trip_category — 現在態（沒給 category 必填驗證範圍）
    # ============================================================
    if TEST_TRIP:
        banner(f'M3: update_trip_category({TEST_TRIP[0]})')
        trip_id, orig_cat = TEST_TRIP
        # 找一個跟原本不同的 category
        new_cat = '診所' if orig_cat != '診所' else '東洋'

        # M3a: reason 空 → fail
        r = update_trip_category(
            session=s, trip_id=trip_id,
            new_category=new_cat, reason='',
            auto_commit=False,
        )
        print(f'  reason 空 → ok={r.ok}')
        assert not r.ok

        # M3b: 同類別 → fail
        r = update_trip_category(
            session=s, trip_id=trip_id,
            new_category=orig_cat, reason='測試',
            auto_commit=False,
        )
        print(f'  同類別 → ok={r.ok}')
        assert not r.ok

        # M3c: 改類別 — 注意 R-5 鎖：如果 trip 在 30 分鐘內，會被鎖
        r = update_trip_category(
            session=s, trip_id=trip_id,
            new_category=new_cat, reason=f'測試: {orig_cat}→{new_cat} key 錯',
            user_name='測試員',
            auto_commit=False,
        )
        if r.ok:
            print(f'  category: {orig_cat} → {r.data.category}')
            assert r.data.category == new_cat
        elif r.meta.get('locked'):
            print(f'  ⚠️ 鎖內無法改 (R-5): {r.error}')
        else:
            print(f'  ❌ 失敗: {r.error}')
            raise AssertionError(r.error)

    # ============================================================
    # M4: 帳務勾稽警語只對「診所」類班次（東洋/臨時不警）
    # tx 內 seed（completed_trips ×2 + 該週 weekly_charge 分錄），
    # 遠未來日期避開真資料；最後跟全案一起 rollback
    # ============================================================
    banner('M4: 勾稽警語 — 診所警 / 東洋不警')
    from datetime import datetime, time as _time, timedelta
    from rewrite.utils.sun_week import sun_week_start
    from rewrite.tools.batch_allowance import execute_batch_allowance

    M4_DATE = date(2035, 2, 7)
    m4_ws = sun_week_start(M4_DATE)
    m4_we = m4_ws + timedelta(days=6)
    # 確認該週乾淨（無真 weekly_charge / 無真班次）
    from rewrite.tools.accounting import find_weekly_charge_for_week
    assert find_weekly_charge_for_week(session=s, week_end_date=m4_we) is None, \
        f'{m4_we} 該測試週不該已有 weekly_charge'
    n_real = s.execute(text(
        "SELECT COUNT(*) FROM completed_trips WHERE date >= :ws AND date <= :we"
    ), {'ws': m4_ws, 'we': m4_we}).scalar()
    assert n_real == 0, f'{m4_ws}~{m4_we} 不該有真班次（有 {n_real} 筆）'

    # seed 該週 weekly_charge（occurred_at = 該週六 23:59，
    # 對齊 accounting.record_weekly_charge 的寫入口徑）
    s.execute(text("""
        INSERT INTO account_ledger
            (occurred_at, type, counterparty, amount_in, amount_out,
             bank_name, bank_account_last4, reference_no, memo, created_at)
        VALUES (:oa, 'weekly_charge', '車資扣款', 0, 26270,
                NULL, NULL, NULL, :memo, NOW())
    """), {'oa': datetime.combine(m4_we, _time(23, 59)),
           'memo': f'週末 {m4_we.isoformat()} 扣款(測試勾稽)'})
    assert find_weekly_charge_for_week(session=s, week_end_date=m4_we) is not None

    def _seed_m4(cat, code):
        return s.execute(text("""
            INSERT INTO completed_trips
            (date, start_point, via_point, end_point, meter_fare, extra_fare,
             category, driver_id, unique_code, trip_type)
            VALUES (:d, '甲地', NULL, '乙地', 100, 0, :cat, NULL, :code, 'temp')
            RETURNING id
        """), {'d': M4_DATE, 'cat': cat, 'code': code}).fetchone()[0]

    clinic_id = _seed_m4('診所', 'test_audit_clinic')
    toyo_id = _seed_m4('東洋', 'test_audit_toyo')

    # M4a: 診所班次改車資 → 該週已記扣款 → 應有警語
    r = update_completed_trip_fare(
        session=s, completed_trip_id=clinic_id,
        meter_fare=150, reason='測試勾稽', user_name='test',
        auto_commit=False,
    )
    assert r.ok, r.error
    print(f'  診所 meta.warning = {r.meta.get("warning")!r}')
    assert r.meta.get('warning'), '診所類改車資該週已記扣款 → 應附警語'
    assert '已記扣款' in r.meta['warning'] and '26,270' in r.meta['warning']

    # M4b: 東洋班次改車資 → 不該有警語
    # （用戶實測回報 bug：東洋改車資誤跳「診所週扣款」警語）
    r = update_completed_trip_fare(
        session=s, completed_trip_id=toyo_id,
        meter_fare=150, reason='測試勾稽', user_name='test',
        auto_commit=False,
    )
    assert r.ok, r.error
    print(f'  東洋 meta.warning = {r.meta.get("warning")!r}')
    assert r.meta.get('warning') is None, '東洋類改車資不該跳週扣款警語'

    # M4c: 批量加成混合批（診所1+東洋1）→ 差額只算「診所」筆數（+50×1）
    r = execute_batch_allowance(
        session=s, date_from=M4_DATE, date_to=M4_DATE,
        amount=50, reason='測試混合批勾稽', user_name='test',
        auto_commit=False,
    )
    assert r.ok, r.error
    assert r.data['updated_count'] == 2  # 兩筆都有加成
    warns = r.data['weekly_charge_warnings']
    print(f'  批量(診所1+東洋1) warnings = {warns}')
    assert len(warns) == 1, '該週有診所班次 → 應出一則警語'
    assert '+50' in warns[0], f'差額應 = 50×診所1筆（非 ×2 筆）: {warns[0]!r}'

    # M4d: 批量加成純東洋批 → 該週有扣款也不警
    r = execute_batch_allowance(
        session=s, date_from=M4_DATE, date_to=M4_DATE,
        amount=50, reason='測試東洋批勾稽', category='東洋',
        user_name='test', auto_commit=False,
    )
    assert r.ok, r.error
    print(f'  批量(純東洋) warnings = {r.data["weekly_charge_warnings"]}')
    assert r.data['weekly_charge_warnings'] == [], '純東洋批不該出週扣款警語'

    # ============================================================
    # 全部 rollback，不留痕
    # ============================================================
    s.rollback()
    print('\n✅ 全部 mutation pass，已 rollback')

    # 確認 TARGET_ID 回到原樣
    r = query_completed_trip_by_id(TARGET_ID, session=s)
    assert r.ok
    final = r.data
    assert final.meter_fare == before.meter_fare, f'rollback 失敗: {final.meter_fare}'
    assert final.extra_fare == before.extra_fare
    assert final.category == before.category
    print(f'   {TARGET_ID} 回原狀: meter={final.meter_fare} extra={final.extra_fare} '
          f'category={final.category}')

finally:
    s.close()
