"""
測試 spec §3.1 的兩個小型 mutation 工具：
  update_passenger_name  — 改乘客名（鎖內可、不需確認）
  record_fare_current    — 記錄現在態車資（鎖內可、不需確認）

驗證：
  - 改/清乘客名（含「沒變動 → fail」）
  - 改錶價/加成（含部分欄位 / 非整數 / 沒變動的拒絕）
  - 鎖內可（allow_in_lock=True）
  - R-6 audit log 寫入
  - modification_reason 累加格式
"""
import sys
from datetime import date, datetime, timedelta, time as dt_time
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import Session
from sqlalchemy import text
from rewrite.tools.trip import (
    update_passenger_name,
    record_fare_current,
    query_trip_by_id,
)

USER_ID = 'U6b520261e9199a21d25e6d20509eda3f'


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


def make_trip(session, trip_id, date_, time_, *,
              status='準備', driver_id=533, meter_fare=340, extra_fare=0,
              passenger_name=None, fake_ids):
    session.execute(text("DELETE FROM trips WHERE trip_id = :id"), {'id': trip_id})
    session.execute(text("""
        INSERT INTO trips (trip_id, date, time, start_point, end_point,
                           category, status, driver_id, meter_fare, extra_fare,
                           passenger_name)
        VALUES (:id, :d, :t, '龍埔街', '診所', '診所',
                :s, :drv, :mf, :ef, :pn)
    """), {
        'id': trip_id, 'd': date_, 't': time_,
        's': status, 'drv': driver_id,
        'mf': meter_fare, 'ef': extra_fare,
        'pn': passenger_name,
    })
    session.commit()
    fake_ids.append(trip_id)


session = Session()
fake_ids = []
try:
    now = datetime.now()
    target = (now + timedelta(minutes=60)).time().replace(microsecond=0)
    locked = (now + timedelta(minutes=15)).time().replace(microsecond=0)
    today = now.date()

    # ============================================================
    # ===== update_passenger_name =====
    # ============================================================

    # T1: 從 None 改成 "張三"
    banner('T1: update_passenger_name None → "張三"')
    pid = 99201
    make_trip(session, pid, today, target, fake_ids=fake_ids)
    r = update_passenger_name(
        session=session, trip_id=pid, passenger_name='張三',
        user_id=USER_ID, user_name='Linyan', via='quick_command',
    )
    assert r.ok, f'fail: {r.error}'
    assert r.data.passenger_name == '張三'
    print(f'  ✅ passenger_name={r.data.passenger_name!r}')

    # T2: "張三" → "李四"
    banner('T2: update_passenger_name "張三" → "李四"')
    r = update_passenger_name(
        session=session, trip_id=pid, passenger_name='李四',
        user_id=USER_ID,
    )
    assert r.ok
    assert r.data.passenger_name == '李四'
    assert '改乘客名' in (r.data.modification_reason or '')
    print(f'  ✅ passenger_name={r.data.passenger_name!r}')
    print(f'  mod_reason 含: {r.data.modification_reason!r}')

    # T3: 清空（"李四" → None）
    banner('T3: update_passenger_name "李四" → None（清空）')
    r = update_passenger_name(
        session=session, trip_id=pid, passenger_name=None,
        user_id=USER_ID,
    )
    assert r.ok
    assert r.data.passenger_name is None
    print(f'  ✅ 清空成功')

    # T4: 沒變動 → fail（再清一次）
    banner('T4: update_passenger_name 沒變動（None → None）→ 應拒')
    r = update_passenger_name(session=session, trip_id=pid, passenger_name='   ')
    assert not r.ok
    assert '沒變動' in r.error
    print(f'  ✅ {r.error}')

    # T5: trip 不存在 → 拒
    banner('T5: update_passenger_name trip_id 不存在 → 應拒')
    r = update_passenger_name(session=session, trip_id=999999, passenger_name='X')
    assert not r.ok
    print(f'  ✅ {r.error}')

    # T6: 鎖內可（allow_in_lock=True 驗證）
    banner('T6: update_passenger_name 鎖內可（驗證 allow_in_lock=True）')
    locked_id = 99202
    make_trip(session, locked_id, today, locked,
              passenger_name='舊名', fake_ids=fake_ids)
    r = update_passenger_name(
        session=session, trip_id=locked_id, passenger_name='鎖內改名',
        user_id=USER_ID,
    )
    assert r.ok, f'鎖內應成功（allow_in_lock=True），實際 fail: {r.error}'
    assert r.data.passenger_name == '鎖內改名'
    print(f'  ✅ 鎖內改名成功')

    # ============================================================
    # ===== record_fare_current =====
    # ============================================================

    # T7: 改 meter_fare（340 → 380）
    banner('T7: record_fare_current meter_fare 340 → 380')
    fid = 99203
    make_trip(session, fid, today, target,
              meter_fare=340, extra_fare=0, fake_ids=fake_ids)
    r = record_fare_current(
        session=session, trip_id=fid, meter_fare=380,
        user_id=USER_ID, user_name='Linyan',
    )
    assert r.ok, f'fail: {r.error}'
    assert r.data.meter_fare == 380
    assert r.data.extra_fare == 0  # 不動
    assert '錶價 340→380' in (r.data.modification_reason or '')
    print(f'  ✅ meter={r.data.meter_fare} extra={r.data.extra_fare}')
    print(f'  mod: {r.data.modification_reason!r}')

    # T8: 改 extra_fare（0 → 50）+ 帶 reason
    banner('T8: record_fare_current extra_fare 0 → 50 + reason')
    r = record_fare_current(
        session=session, trip_id=fid, extra_fare=50,
        reason='等候 25 分鐘',
        user_id=USER_ID,
    )
    assert r.ok
    assert r.data.extra_fare == 50
    assert r.data.meter_fare == 380  # 上次的，不動
    assert '加成 0→50' in (r.data.modification_reason or '')
    assert '等候 25 分鐘' in (r.data.modification_reason or '')
    print(f'  ✅ extra={r.data.extra_fare}')
    print(f'  mod 含 reason: {r.data.modification_reason!r}')

    # T9: 兩個都改
    banner('T9: record_fare_current 兩個都改')
    r = record_fare_current(
        session=session, trip_id=fid, meter_fare=400, extra_fare=80,
        user_id=USER_ID,
    )
    assert r.ok
    assert r.data.meter_fare == 400 and r.data.extra_fare == 80
    print(f'  ✅ meter={r.data.meter_fare} extra={r.data.extra_fare}')

    # T10: 都不給 → 拒
    banner('T10: record_fare_current 都不給 → 應拒')
    r = record_fare_current(session=session, trip_id=fid)
    assert not r.ok
    assert '至少' in r.error
    print(f'  ✅ {r.error}')

    # T11: 沒變動 → 拒（給跟現值一樣）
    banner('T11: record_fare_current 沒變動 → 應拒')
    r = record_fare_current(session=session, trip_id=fid, meter_fare=400)
    assert not r.ok
    assert '沒變動' in r.error
    print(f'  ✅ {r.error}')

    # T12: 非整數 → 拒
    banner('T12: record_fare_current meter_fare="abc" → 應拒')
    r = record_fare_current(session=session, trip_id=fid, meter_fare='abc')
    assert not r.ok
    print(f'  ✅ {r.error}')

    # T13: trip 不存在 → 拒
    banner('T13: record_fare_current trip_id 不存在 → 應拒')
    r = record_fare_current(session=session, trip_id=999999, meter_fare=300)
    assert not r.ok
    print(f'  ✅ {r.error}')

    # T14: 鎖內可（allow_in_lock=True 驗證）
    banner('T14: record_fare_current 鎖內可（驗證 allow_in_lock=True）')
    locked_fid = 99204
    make_trip(session, locked_fid, today, locked,
              meter_fare=340, extra_fare=0, fake_ids=fake_ids)
    r = record_fare_current(
        session=session, trip_id=locked_fid, meter_fare=420,
        user_id=USER_ID,
    )
    assert r.ok, f'鎖內應成功，實際 fail: {r.error}'
    assert r.data.meter_fare == 420
    print(f'  ✅ 鎖內改車資成功')

    # ============================================================
    # ===== audit log 總檢查 =====
    # ============================================================
    banner('T15: audit_log 應有兩種 action_type')
    rows = session.execute(text("""
        SELECT action_type, COUNT(*) AS n
        FROM audit_log
        WHERE target_table = 'trips' AND target_id = ANY(:ids)
              AND action_type IN ('update_passenger_name', 'record_fare_current')
        GROUP BY action_type
        ORDER BY action_type
    """), {'ids': fake_ids}).fetchall()
    print(f'  audit log 統計：')
    for r in rows:
        print(f'    {r[0]}: {r[1]} 筆')
    seen = {r[0] for r in rows}
    assert seen == {'update_passenger_name', 'record_fare_current'}, \
        f'缺 action_type: {seen}'
    print(f'  ✅ 兩種 action_type 都有 audit log')

    print('\n' + '='*60)
    print('✅ 全部 15 個小型 mutation 測試通過')
    print('   update_passenger_name / record_fare_current')
    print('   鎖內可 ✓ / 沒變動拒 ✓ / R-6 audit ✓ / 累加 ✓')
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
