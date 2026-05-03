"""
測試 trips mutation：passenger_leave（首例）

驗證：
  - 30 分鐘鎖（R-5 decorator）
  - 三層障眼法（status='準備' + passenger_leave_reason）
  - modification_reason 累加
  - audit_log 寫入（R-6）
  - 各種拒絕情境
"""
import sys
from datetime import date, datetime, timedelta, time as dt_time
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import Session
from sqlalchemy import text
from rewrite.tools.trip import (
    passenger_leave,
    query_trip_by_id,
)

USER_ID = 'U6b520261e9199a21d25e6d20509eda3f'


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


session = Session()
test_trip_id = 99001
fake_ids = []
try:
    # ============================================================
    # 準備：建一個未來時間的測試 trip（離 30 分鐘以外）
    # ============================================================
    banner('準備 — 建測試 trip #99001 於現在 + 60 分鐘')
    now = datetime.now()
    target = (now + timedelta(minutes=60)).time().replace(microsecond=0)
    today = now.date()

    # 清理舊資料
    session.execute(text("DELETE FROM trips WHERE trip_id = :id"), {'id': test_trip_id})
    session.execute(text("""
        INSERT INTO trips (trip_id, date, time, start_point, end_point,
                           category, status, driver_id, meter_fare, extra_fare)
        VALUES (:id, :d, :t, '龍埔街', '診所', '診所', '準備', 533, 340, 0)
    """), {'id': test_trip_id, 'd': today, 't': target})
    session.commit()
    fake_ids.append(test_trip_id)
    print(f'  建立 #{test_trip_id} 於 {today} {target}（{60} 分鐘後）')

    # ============================================================
    # T1：未鎖窗外 → 應成功
    # ============================================================
    banner('T1: passenger_leave 未鎖內 → 應成功')
    r = passenger_leave(
        session=session,
        trip_id=test_trip_id,
        reason='龍埔街自己來',
        surcharge=-100,
        user_id=USER_ID,
        user_name='Linyan',
        via='quick_command',
    )
    assert r.ok, f'expected ok, got {r.error}'
    t = r.data
    print(f'  ✅ {t.status_emoji} display={t.display_status} '
          f'leave={t.passenger_leave_reason} extra={t.extra_fare}')
    assert t.status == '準備'
    assert t.display_status == '請假'  # 三層障眼法
    assert t.passenger_leave_reason == '龍埔街自己來'
    assert t.extra_fare == -100
    print(f'  ✅ 三層障眼法：display=「請假」 / status「準備」')

    # ============================================================
    # T2：再請假一次 → modification_reason 應累加
    # ============================================================
    banner('T2: 再請假一次（同 trip） → modification_reason 累加')
    r = passenger_leave(
        session=session,
        trip_id=test_trip_id,
        reason='第二次請假測試',
        surcharge=-50,
        user_id=USER_ID,
    )
    assert r.ok
    mod = session.execute(
        text("SELECT modification_reason FROM trips WHERE trip_id = :id"),
        {'id': test_trip_id}
    ).scalar()
    print(f'  modification_reason = {mod!r}')
    assert '[1]' in mod and '[2]' in mod, f'累加格式錯：{mod}'
    print(f'  ✅ 累加格式正確')

    # ============================================================
    # T3：原因為空 → 拒絕
    # ============================================================
    banner('T3: 原因為空字串 → 應拒絕')
    r = passenger_leave(session=session, trip_id=test_trip_id, reason='   ')
    assert not r.ok
    print(f'  ✅ {r.error}')

    # ============================================================
    # T4：surcharge 非整數 → 拒絕
    # ============================================================
    banner('T4: surcharge 非整數 → 應拒絕')
    r = passenger_leave(session=session, trip_id=test_trip_id, reason='測', surcharge='abc')
    assert not r.ok
    print(f'  ✅ {r.error}')

    # ============================================================
    # T5：trip 不存在 → 拒絕
    # ============================================================
    banner('T5: trip_id 不存在 → 應拒絕')
    r = passenger_leave(session=session, trip_id=99999, reason='測')
    assert not r.ok
    print(f'  ✅ {r.error}')

    # ============================================================
    # T6：30 分鐘鎖（建一個 20 分鐘後的 trip 再請假）
    # ============================================================
    banner('T6: 30 分鐘鎖（trip 在現在 + 20 分鐘）→ 應拒絕')
    locked_id = 99002
    locked_target = (now + timedelta(minutes=20)).time().replace(microsecond=0)
    session.execute(text("DELETE FROM trips WHERE trip_id = :id"), {'id': locked_id})
    session.execute(text("""
        INSERT INTO trips (trip_id, date, time, start_point, end_point,
                           category, status, driver_id, meter_fare, extra_fare)
        VALUES (:id, :d, :t, '龍埔街', '診所', '診所', '準備', 533, 340, 0)
    """), {'id': locked_id, 'd': today, 't': locked_target})
    session.commit()
    fake_ids.append(locked_id)

    r = passenger_leave(
        session=session, trip_id=locked_id, reason='測試鎖', surcharge=0,
        user_id=USER_ID,
    )
    assert not r.ok, f'應該被鎖擋，但 ok={r.ok}'
    print(f'  ✅ 鎖正確擋下：{r.error[:80]}')
    print(f'     meta: {r.meta}')

    # ============================================================
    # T7：audit log 已寫入
    # ============================================================
    banner('T7: audit_log 應有 T1+T2 的 2 筆 passenger_leave 紀錄')
    rows = session.execute(text("""
        SELECT id, action_type, target_id, reason, via, changed_fields, extra
        FROM audit_log
        WHERE target_table = 'trips'
          AND target_id = :id
          AND action_type = 'passenger_leave'
        ORDER BY created_at
    """), {'id': test_trip_id}).fetchall()
    print(f'  共 {len(rows)} 筆')
    for r in rows:
        print(f'    audit#{r[0]} {r[1]} target={r[2]} reason={r[3]!r} '
              f'via={r[4]} changed={r[5]}')
    assert len(rows) >= 2

    # ============================================================
    # T8：已完成的 trip → 拒絕
    # ============================================================
    banner('T8: status=「已完成」的 trip → 應拒絕請假')
    completed_id = 99003
    session.execute(text("DELETE FROM trips WHERE trip_id = :id"), {'id': completed_id})
    # 過去日 + 已完成 → 不會撞 30 分鐘鎖（因為時間已過）
    session.execute(text("""
        INSERT INTO trips (trip_id, date, time, start_point, end_point,
                           category, status, driver_id, meter_fare, extra_fare)
        VALUES (:id, '2025-01-01', '10:00', '龍埔街', '診所', '診所',
                '已完成', 533, 340, 0)
    """), {'id': completed_id})
    session.commit()
    fake_ids.append(completed_id)

    r = passenger_leave(session=session, trip_id=completed_id, reason='測')
    assert not r.ok
    print(f'  ✅ {r.error}')

    print('\n' + '='*60)
    print('✅ 全部 8 個 mutation 測試通過')
    print('   R-5 鎖 ✓ / R-6 audit ✓ / 三層障眼法 ✓ / 累加 ✓')
    print('='*60)

finally:
    # 清理 trips 測試資料
    for fid in fake_ids:
        try:
            session.execute(text("DELETE FROM trips WHERE trip_id = :id"), {'id': fid})
        except Exception:
            pass
    # 清 audit log（只清測試用 trip 的）
    if fake_ids:
        session.execute(text("""
            DELETE FROM audit_log
            WHERE target_table = 'trips' AND target_id = ANY(:ids)
        """), {'ids': fake_ids})
    session.commit()
    if fake_ids:
        print(f'\n🧹 清理測試 trips: {fake_ids} + 對應 audit_log')
    session.close()
