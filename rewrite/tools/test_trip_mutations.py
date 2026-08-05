"""
測試 trips mutation 第 1+2 批：
  passenger_leave / cancel_trip / mark_conflict /
  restore_to_ready / assign_driver / unassign_driver

驗證：
  - 30 分鐘鎖（R-5 decorator，allow_in_lock 兩種模式）
  - 三層障眼法（status='準備' + passenger_leave_reason）
  - modification_reason 累加
  - audit_log 寫入（R-6）
  - 各種拒絕情境（已完成/註銷/沒司機/換司機等）
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
    cancel_trip,
    mark_conflict,
    restore_to_ready,
    assign_driver,
    unassign_driver,
    query_trip_by_id,
)

USER_ID = 'U6b520261e9199a21d25e6d20509eda3f'


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


def make_trip(session, trip_id, date_, time_, *,
              status='準備', driver_id=533, extra_fare=0,
              modification_reason=None, fake_ids):
    """建測試 trip 的 helper（會 commit + 自動加進 fake_ids 清理）"""
    session.execute(text("DELETE FROM trips WHERE trip_id = :id"), {'id': trip_id})
    session.execute(text("""
        INSERT INTO trips (trip_id, date, time, start_point, end_point,
                           category, status, driver_id, meter_fare, extra_fare,
                           modification_reason)
        VALUES (:id, :d, :t, '龍埔街', '診所', '診所',
                :s, :drv, 340, :extra, :mod)
    """), {
        'id': trip_id, 'd': date_, 't': time_,
        's': status, 'drv': driver_id, 'extra': extra_fare,
        'mod': modification_reason,
    })
    session.commit()
    fake_ids.append(trip_id)


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

    # ============================================================
    # ===== 第 2 批 mutation 測試：cancel_trip =====
    # ============================================================

    # T9：cancel_trip 成功（建鎖外的 trip）
    banner('T9: cancel_trip 成功（建 #99010 鎖外）')
    cancel_id = 99010
    make_trip(session, cancel_id, today, target, fake_ids=fake_ids)
    r = cancel_trip(
        session=session, trip_id=cancel_id, reason='客戶取消',
        user_id=USER_ID, user_name='Linyan', via='quick_command',
    )
    assert r.ok, f'cancel failed: {r.error}'
    assert r.data.status == '註銷'
    assert r.data.display_status == '註銷'
    assert '註銷' in (r.data.modification_reason or '')
    print(f'  ✅ status={r.data.status} mod={r.data.modification_reason!r}')

    # T10：重複註銷 → 拒
    banner('T10: cancel_trip 重複註銷 → 應拒')
    r = cancel_trip(session=session, trip_id=cancel_id, user_id=USER_ID)
    assert not r.ok
    assert '已是註銷' in r.error
    print(f'  ✅ {r.error}')

    # T11：cancel_trip 鎖內 → 拒（用既有 #99002 在 +20min）
    banner('T11: cancel_trip 鎖內（#99002 在 +20min）→ 應拒')
    r = cancel_trip(session=session, trip_id=locked_id, user_id=USER_ID)
    assert not r.ok
    assert r.meta.get('locked'), f'meta 缺 locked: {r.meta}'
    print(f'  ✅ 鎖正確擋下：{r.error[:60]}')

    # ============================================================
    # ===== mark_conflict =====
    # ============================================================

    # T12：mark_conflict 成功
    banner('T12: mark_conflict 成功（建 #99011 鎖外）')
    conflict_id = 99011
    make_trip(session, conflict_id, today, target, fake_ids=fake_ids)
    r = mark_conflict(
        session=session, trip_id=conflict_id, reason='時間重疊',
        user_id=USER_ID, user_name='Linyan',
    )
    assert r.ok, f'mark_conflict failed: {r.error}'
    assert r.data.status == '衝突'
    assert '衝突' in (r.data.modification_reason or '')
    print(f'  ✅ status={r.data.status} mod={r.data.modification_reason!r}')

    # T13：mark_conflict 鎖內 → 拒
    banner('T13: mark_conflict 鎖內（#99002）→ 應拒')
    r = mark_conflict(session=session, trip_id=locked_id, user_id=USER_ID)
    assert not r.ok
    assert r.meta.get('locked')
    print(f'  ✅ 鎖正確擋下：{r.error[:60]}')

    # ============================================================
    # ===== restore_to_ready（allow_in_lock=True）=====
    # ============================================================

    # T14：從請假狀態恢復（用 #99001，T2 後 leave_reason + extra=-50）
    banner('T14: restore_to_ready 從請假恢復（#99001）')
    cur = session.execute(text("""
        SELECT status, passenger_leave_reason, extra_fare, driver_id
        FROM trips WHERE trip_id = :id
    """), {'id': test_trip_id}).fetchone()
    print(f'  before: status={cur[0]} leave={cur[1]!r} extra={cur[2]} driver={cur[3]}')
    r = restore_to_ready(
        session=session, trip_id=test_trip_id,
        user_id=USER_ID, user_name='Linyan',
    )
    assert r.ok, f'restore failed: {r.error}'
    assert r.data.status == '準備'
    assert r.data.passenger_leave_reason is None
    assert r.data.extra_fare == 0, f'extra_fare 應歸零（原 -50），實際 {r.data.extra_fare}'
    assert r.data.display_status == '準備'  # 不再是請假
    print(f'  ✅ 三層障眼法清掉：status={r.data.status} leave={r.data.passenger_leave_reason} extra={r.data.extra_fare}')

    # T15：待派（無司機）→ 拒
    banner('T15: restore_to_ready 待派（無司機）→ 應拒')
    pending_id = 99012
    make_trip(session, pending_id, today, target,
              status='待派', driver_id=None, fake_ids=fake_ids)
    r = restore_to_ready(session=session, trip_id=pending_id, user_id=USER_ID)
    assert not r.ok
    assert '指派' in r.error
    print(f'  ✅ {r.error}')

    # T16：鎖內可（驗證 allow_in_lock=True）
    banner('T16: restore_to_ready 鎖內可（鎖內+註銷 trip → restore 成功）')
    locked_cancel_id = 99013
    locked_t = (now + timedelta(minutes=15)).time().replace(microsecond=0)
    make_trip(session, locked_cancel_id, today, locked_t,
              status='註銷', modification_reason='[1] 註銷：測試',
              fake_ids=fake_ids)
    r = restore_to_ready(
        session=session, trip_id=locked_cancel_id, user_id=USER_ID,
    )
    assert r.ok, f'鎖內 restore 應成功（allow_in_lock=True），實際 fail: {r.error}'
    assert r.data.status == '準備'
    print(f'  ✅ 鎖內 restore 成功（allow_in_lock=True 生效）')

    # ============================================================
    # ===== assign_driver（allow_in_lock=True）=====
    # ============================================================

    # T17：從待派指派 → 升級為準備
    banner('T17: assign_driver 從待派指派 → 升級為準備（#99014）')
    assign_id = 99014
    make_trip(session, assign_id, today, target,
              status='待派', driver_id=None, fake_ids=fake_ids)
    r = assign_driver(
        session=session, trip_id=assign_id, driver_id=533,
        user_id=USER_ID, user_name='Linyan',
    )
    assert r.ok, f'assign failed: {r.error}'
    assert r.data.driver_id == 533
    assert r.data.status == '準備'
    print(f'  ✅ status={r.data.status} driver={r.data.driver_id}')

    # T18：換司機（533 → 5386）
    banner('T18: assign_driver 換司機（#99014: 533 → 5386）')
    r = assign_driver(
        session=session, trip_id=assign_id, driver_id=5386,
        user_id=USER_ID,
    )
    assert r.ok
    assert r.data.driver_id == 5386
    # 2026-07-31 用戶定調：指派/換司機是純調度動作、不影響車資，
    # 不可寫進 modification_reason（會污染請款報表的說明欄）。
    # 完整軌跡由 audit_log 保存。這個斷言原本反過來寫，是改行為時漏更新的過期測試。
    assert '換司機' not in (r.data.modification_reason or ''), (
        f'換司機不該進 modification_reason，實際：{r.data.modification_reason!r}')
    print(f'  ✅ driver={r.data.driver_id}（modification_reason 乾淨，軌跡在 audit_log）')

    # T19：司機不存在 → 拒
    banner('T19: assign_driver 司機不存在（id=88888）→ 應拒')
    r = assign_driver(
        session=session, trip_id=assign_id, driver_id=88888,
        user_id=USER_ID,
    )
    assert not r.ok
    assert '司機' in r.error
    print(f'  ✅ {r.error}')

    # T20：鎖內可
    banner('T20: assign_driver 鎖內可（鎖內待派 → assign 成功）')
    locked_assign_id = 99015
    make_trip(session, locked_assign_id, today, locked_t,
              status='待派', driver_id=None, fake_ids=fake_ids)
    r = assign_driver(
        session=session, trip_id=locked_assign_id, driver_id=533,
        user_id=USER_ID,
    )
    assert r.ok, f'鎖內 assign 應成功（allow_in_lock=True），實際 fail: {r.error}'
    assert r.data.driver_id == 533
    print(f'  ✅ 鎖內 assign 成功（allow_in_lock=True 生效）')

    # ============================================================
    # ===== unassign_driver（allow_in_lock=True）=====
    # ============================================================

    # T21：撤銷指派（driver→NULL, status→待派）
    banner('T21: unassign_driver 成功（#99014: driver=5386 → NULL, status→待派）')
    r = unassign_driver(
        session=session, trip_id=assign_id,
        user_id=USER_ID, user_name='Linyan',
    )
    assert r.ok, f'unassign failed: {r.error}'
    assert r.data.driver_id is None
    assert r.data.status == '待派'
    print(f'  ✅ status={r.data.status} driver={r.data.driver_id}')

    # T22：本來就沒司機 → 拒
    banner('T22: unassign_driver 本來就沒司機 → 應拒')
    r = unassign_driver(session=session, trip_id=assign_id, user_id=USER_ID)
    assert not r.ok
    assert '沒指派' in r.error
    print(f'  ✅ {r.error}')

    # ============================================================
    # ===== audit log 總檢查 =====
    # ============================================================
    banner('T23: audit_log 應有第 2 批的多種 action_type')
    rows = session.execute(text("""
        SELECT action_type, COUNT(*) AS n
        FROM audit_log
        WHERE target_table = 'trips' AND target_id = ANY(:ids)
        GROUP BY action_type
        ORDER BY action_type
    """), {'ids': fake_ids}).fetchall()
    print(f'  audit_log 統計（本次測試 trips 範圍）：')
    for r in rows:
        print(f'    {r[0]}: {r[1]} 筆')
    seen = {r[0] for r in rows}
    expected = {'passenger_leave', 'cancel_trip', 'mark_conflict',
                'restore_to_ready', 'assign_driver', 'unassign_driver'}
    missing = expected - seen
    assert not missing, f'audit_log 缺以下 action_type：{missing}'
    print(f'  ✅ 全部 {len(expected)} 種 mutation 都有 audit log')

    print('\n' + '='*60)
    print('✅ 全部 23 個 mutation 測試通過（第 1 批 + 第 2 批）')
    print('   R-5 鎖 ✓ / R-6 audit ✓ / 三層障眼法 ✓ / 累加 ✓')
    print('   工具：passenger_leave / cancel_trip / mark_conflict /')
    print('         restore_to_ready / assign_driver / unassign_driver')
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
