"""
測試 R-3 統一請假介面 apply_leave

驗證：
  - target_id 在 trips → 走 passenger_leave 成功（三層障眼法仍生效）
  - target_id 在 fixed_schedules → 回 fallback 訊息（不執行）
  - target_id 不存在 → fail
  - 鎖內 trips → 仍被 R-5 鎖擋下（透過底層 passenger_leave 的 decorator）
  - 型別錯誤 → fail
"""
import sys
from datetime import date, datetime, timedelta, time as dt_time
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import Session
from sqlalchemy import text
from rewrite.tools.leave import apply_leave

USER_ID = 'U6b520261e9199a21d25e6d20509eda3f'


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


session = Session()
fake_ids = []
try:
    now = datetime.now()
    target_time = (now + timedelta(minutes=60)).time().replace(microsecond=0)
    locked_time = (now + timedelta(minutes=20)).time().replace(microsecond=0)
    today = now.date()

    # ============================================================
    # 準備：建一個 trips 測試 trip
    # ============================================================
    trips_id = 99100
    session.execute(text("DELETE FROM trips WHERE trip_id = :id"), {'id': trips_id})
    session.execute(text("""
        INSERT INTO trips (trip_id, date, time, start_point, end_point,
                           category, status, driver_id, meter_fare, extra_fare)
        VALUES (:id, :d, :t, '龍埔街', '診所', '診所', '準備', 533, 340, 0)
    """), {'id': trips_id, 'd': today, 't': target_time})
    session.commit()
    fake_ids.append(trips_id)

    # ============================================================
    # T1：target_id 在 trips → 走 passenger_leave 成功
    # ============================================================
    banner(f'T1: target_id={trips_id} 在 trips → 應走 passenger_leave 成功')
    r = apply_leave(
        session=session,
        target_id=trips_id,
        reason='出國度假',
        surcharge=-100,
        user_id=USER_ID,
        user_name='Linyan',
        via='ai_agent',
    )
    assert r.ok, f'expected ok, got {r.error}'
    assert r.meta.get('routed_to') == 'trips', f'meta routed_to: {r.meta}'
    t = r.data
    assert t.status == '準備'  # 三層障眼法
    assert t.display_status == '請假'
    assert t.passenger_leave_reason == '出國度假'
    assert t.extra_fare == -100
    print(f'  ✅ routed_to=trips, display={t.display_status}, '
          f'leave={t.passenger_leave_reason}, extra={t.extra_fare}')

    # ============================================================
    # T2：target_id 在 fixed_schedules → 回 fallback（不執行）
    # ============================================================
    banner('T2: target_id=1 在 fixed_schedules → 應回 fallback 訊息')
    # 先檢查 fixed_schedules id=1 確實存在
    fixed_exists = session.execute(
        text("SELECT 1 FROM fixed_schedules WHERE id = 1")
    ).fetchone()
    assert fixed_exists, '前置條件失敗：fixed_schedules id=1 不存在'

    r = apply_leave(
        session=session,
        target_id=1,
        reason='測試 fallback',
        user_id=USER_ID,
    )
    assert not r.ok, '應回 fallback fail'
    assert r.meta.get('routed_to') == 'fixed_schedules'
    assert r.meta.get('sandbox_command'), 'meta 應有 sandbox_command 提示'
    assert '！固定班次' in r.meta['sandbox_command']
    print(f'  ✅ routed_to=fixed_schedules')
    print(f'  訊息：{r.error[:80]}...')
    print(f'  sandbox_command: {r.meta["sandbox_command"]!r}')

    # ============================================================
    # T3：target_id 不存在 → fail（routed_to='none'）
    # ============================================================
    banner('T3: target_id=999999 不存在 → 應 fail')
    r = apply_leave(
        session=session,
        target_id=999999,
        reason='測試',
    )
    assert not r.ok
    assert r.meta.get('routed_to') == 'none'
    print(f'  ✅ {r.error}')

    # ============================================================
    # T4：型別錯誤 → fail
    # ============================================================
    banner('T4: target_id="abc" 非整數 → 應拒')
    r = apply_leave(session=session, target_id='abc', reason='測')
    assert not r.ok
    assert r.meta.get('routed_to') == 'none'
    print(f'  ✅ {r.error}')

    # ============================================================
    # T5：鎖內 trips → 應被 R-5 擋（透過 passenger_leave 的 decorator）
    # ============================================================
    banner('T5: 鎖內 trips（+20min）→ 應被 R-5 鎖擋')
    locked_id = 99101
    session.execute(text("DELETE FROM trips WHERE trip_id = :id"), {'id': locked_id})
    session.execute(text("""
        INSERT INTO trips (trip_id, date, time, start_point, end_point,
                           category, status, driver_id, meter_fare, extra_fare)
        VALUES (:id, :d, :t, '龍埔街', '診所', '診所', '準備', 533, 340, 0)
    """), {'id': locked_id, 'd': today, 't': locked_time})
    session.commit()
    fake_ids.append(locked_id)

    r = apply_leave(
        session=session,
        target_id=locked_id,
        reason='鎖內測試',
        surcharge=0,
        user_id=USER_ID,
    )
    assert not r.ok, f'應被鎖擋，但 ok={r.ok}'
    # routed_to=trips（路由有走到 trips 路徑），但結果失敗
    assert r.meta.get('routed_to') == 'trips', f'meta: {r.meta}'
    assert r.meta.get('locked'), 'meta 應有 locked=True'
    print(f'  ✅ routed_to=trips 但被鎖擋下：{r.error[:60]}')
    print(f'     meta: locked={r.meta.get("locked")}, '
          f'minutes_left={r.meta.get("minutes_left")}')

    # ============================================================
    # T6：audit log 應只在 T1 寫入（fallback / fail 路徑不寫）
    # ============================================================
    banner('T6: audit_log 只應在 T1 trips 路徑寫入（fallback / fail 不寫）')
    rows = session.execute(text("""
        SELECT action_type, target_id
        FROM audit_log
        WHERE target_table = 'trips' AND target_id = ANY(:ids)
              AND action_type = 'passenger_leave'
        ORDER BY created_at
    """), {'ids': fake_ids}).fetchall()
    print(f'  trips audit 共 {len(rows)} 筆（應 = 1，只有 T1）')
    for r in rows:
        print(f'    {r[0]} target={r[1]}')
    assert len(rows) == 1, f'應只有 1 筆，實際 {len(rows)}'
    assert rows[0][1] == trips_id
    # fixed_schedules / 不存在路徑不應有 audit
    fixed_audit = session.execute(text("""
        SELECT COUNT(*) FROM audit_log
        WHERE target_table = 'fixed_schedules' AND target_id = 1
              AND created_at >= NOW() - INTERVAL '5 minutes'
    """)).scalar()
    assert fixed_audit == 0, f'fallback 路徑不該寫 audit，實際 {fixed_audit}'
    print(f'  ✅ fallback 路徑沒寫 audit（fixed_schedules count={fixed_audit}）')

    print('\n' + '='*60)
    print('✅ 全部 6 個 apply_leave 測試通過（R-3 統一介面）')
    print('   trips 路徑 ✓ / fixed_schedules fallback ✓ / not-found ✓')
    print('   型別驗證 ✓ / R-5 鎖透傳 ✓ / audit 只在 trips 路徑寫 ✓')
    print('='*60)

finally:
    for fid in fake_ids:
        try:
            session.execute(text("DELETE FROM trips WHERE trip_id = :id"), {'id': fid})
        except Exception:
            pass
    if fake_ids:
        session.execute(text("""
            DELETE FROM audit_log
            WHERE target_table = 'trips' AND target_id = ANY(:ids)
        """), {'ids': fake_ids})
    session.commit()
    if fake_ids:
        print(f'\n🧹 清理測試 trips: {fake_ids} + 對應 audit_log')
    session.close()
