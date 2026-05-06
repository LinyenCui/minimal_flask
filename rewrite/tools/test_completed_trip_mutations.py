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
    # update_completed_trip_fare — 用 trip 820（log 已知 meter=1250 extra=750）
    # ============================================================
    banner('M1: update_completed_trip_fare(820)')
    r = query_completed_trip_by_id(820, session=s)
    assert r.ok, f'820 應存在: {r.error}'
    before = r.data
    print(f'  before: meter={before.meter_fare} extra={before.extra_fare} '
          f'mod={before.modification_reason!r}')

    # M1a: reason 空 → fail
    r = update_completed_trip_fare(
        session=s, completed_trip_id=820,
        meter_fare=1250, extra_fare=750,
        reason='', user_name='test',
        auto_commit=False,
    )
    print(f'  reason 空 → ok={r.ok} error={r.error!r}')
    assert not r.ok and '原因' in r.error

    # M1b: 都沒給 → fail
    r = update_completed_trip_fare(
        session=s, completed_trip_id=820,
        reason='測試', user_name='test',
        auto_commit=False,
    )
    print(f'  meter/extra 都沒給 → ok={r.ok} error={r.error!r}')
    assert not r.ok

    # M1c: 同樣的值 → fail（沒變動）
    r = update_completed_trip_fare(
        session=s, completed_trip_id=820,
        meter_fare=before.meter_fare, extra_fare=before.extra_fare,
        reason='測試', user_name='test',
        auto_commit=False,
    )
    print(f'  沒變動 → ok={r.ok} error={r.error!r}')
    assert not r.ok and '沒變動' in r.error

    # M1d: 改成 1500+800 → 應 success
    r = update_completed_trip_fare(
        session=s, completed_trip_id=820,
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
    assert '[2]' in after.modification_reason  # 累加成功
    assert '改車資' in after.modification_reason
    assert '加班計算錯誤' in after.modification_reason

    # ============================================================
    # update_completed_trip_category — 改類別
    # ============================================================
    banner('M2: update_completed_trip_category(820)')

    # M2a: reason 空 → fail
    r = update_completed_trip_category(
        session=s, completed_trip_id=820,
        new_category='診所', reason='',
        auto_commit=False,
    )
    print(f'  reason 空 → ok={r.ok} error={r.error!r}')
    assert not r.ok

    # M2b: 同類別 → fail（從 M1 之後 820 還是東洋）
    r = update_completed_trip_category(
        session=s, completed_trip_id=820,
        new_category='東洋', reason='測試',
        auto_commit=False,
    )
    print(f'  同類別 → ok={r.ok} error={r.error!r}')
    assert not r.ok and '已是' in r.error

    # M2c: 無效類別 → fail
    r = update_completed_trip_category(
        session=s, completed_trip_id=820,
        new_category='飛機', reason='測試',
        auto_commit=False,
    )
    print(f'  無效類別 → ok={r.ok} error={r.error!r}')
    assert not r.ok and '無效' in r.error

    # M2d: 改成診所 → success
    r = update_completed_trip_category(
        session=s, completed_trip_id=820,
        new_category='診所', reason='測試: 報帳分類錯誤',
        user_name='測試員',
        auto_commit=False,
    )
    assert r.ok, f'M2d failed: {r.error}'
    print(f'  category: 東洋 → {r.data.category}')
    print(f'  modification_reason: {r.data.modification_reason!r}')
    assert r.data.category == '診所'
    assert '[3]' in r.data.modification_reason  # 累加 [3]
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
    # 全部 rollback，不留痕
    # ============================================================
    s.rollback()
    print('\n✅ 全部 mutation pass，已 rollback')

    # 確認 820 回到原樣
    r = query_completed_trip_by_id(820, session=s)
    assert r.ok
    final = r.data
    assert final.meter_fare == before.meter_fare, f'rollback 失敗: {final.meter_fare}'
    assert final.extra_fare == before.extra_fare
    assert final.category == before.category
    print(f'   820 回原狀: meter={final.meter_fare} extra={final.extra_fare} '
          f'category={final.category}')

finally:
    s.close()
