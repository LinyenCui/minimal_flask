"""
測試 fixed_schedule atomic tools

⚠️ 在 dev DB 造假固定班次（id=99701-99703）測試後清理 + 對應 audit_log
"""
import sys
from datetime import time
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import Session
from sqlalchemy import text

from rewrite.tools.fixed_schedule import (
    query_fixed_schedule,
    get_fixed_schedule_by_id,
    update_fixed_schedule,
    apply_fixed_schedule_leave,
    restore_fixed_schedule,
)


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


session = Session()
fake_ids = [99701, 99702, 99703]
# fs_start_point_fkey → customers.short_name：測試客戶要自帶
# （本地 customers 會被 Render 同步 TRUNCATE 洗掉，不能假設存在）
_fixture_customers = ['測試街A', '測試街B']
try:
    # 準備 — 造測試客戶（FK 需要）+ 3 筆假固定班次
    for sn in _fixture_customers:
        session.execute(text("""
            INSERT INTO customers (name, short_name, address)
            VALUES (:sn, :sn, '測試地址')
            ON CONFLICT DO NOTHING
        """), {'sn': sn})
    for fid in fake_ids:
        session.execute(text("DELETE FROM fixed_schedules WHERE id = :id"), {'id': fid})
    session.execute(text("""
        INSERT INTO fixed_schedules
        (id, route_number, departure_time, start_point, via_point, end_point,
         base_fare, surcharge, category, driver_id, direction, status, note)
        VALUES
        (99701, 'TEST', '06:10:00', '測試街A', NULL, '診所', 200, 0, '診所', '533', '來', '準備', NULL),
        (99702, 'TEST', '07:30:00', '測試街B', '經過站', '診所', 250, 0, '診所', '5386', '來', '準備', NULL),
        (99703, 'TEST', '15:30:00', '診所', NULL, '測試街A', 200, 0, '診所', '533', '回', '準備', NULL)
    """))
    session.commit()
    print(f'✅ 建好 3 個假固定班次：{fake_ids}')

    # ============================================================
    # T1: 多條件查詢
    # ============================================================
    banner('T1: query_fixed_schedule(route_number=TEST)')
    r = query_fixed_schedule(session=session, route_number='TEST')
    assert r.ok and len(r.data) == 3
    print(f'  ✅ 找到 {len(r.data)} 筆 TEST 路線')

    # ============================================================
    # T2: customer_short_name 過濾（match start/via/end）
    # ============================================================
    banner('T2: customer_short_name=測試街A → match start_point + end_point')
    r = query_fixed_schedule(session=session,
                             customer_short_name='測試街A',
                             route_number='TEST')
    assert r.ok and len(r.data) == 2  # 99701 (start) + 99703 (end)
    print(f'  ✅ {len(r.data)} 筆（99701 start + 99703 end）')

    # ============================================================
    # T3: get_fixed_schedule_by_id
    # ============================================================
    banner('T3: get_fixed_schedule_by_id(99701)')
    r = get_fixed_schedule_by_id(99701, session=session)
    assert r.ok
    fs = r.data
    print(f'  ✅ #{fs.id}: {fs.short_route()} 司機{fs.driver_id} {fs.status_emoji}')

    # ============================================================
    # T4: update_fixed_schedule（多欄位）
    # ============================================================
    banner('T4: update_fixed_schedule(99701, base_fare=300, departure_time=06:30)')
    r = update_fixed_schedule(
        session=session, schedule_id=99701,
        base_fare=300, departure_time='06:30:00',
        user_id='test', user_name='Linyan',
    )
    assert r.ok, f'update 失敗：{r.error}'
    fs = r.data
    assert fs.base_fare == 300
    assert str(fs.departure_time) == '06:30:00'
    print(f'  ✅ base_fare={fs.base_fare}, departure_time={fs.departure_time}')

    # ============================================================
    # T5: update 沒變動 → 拒
    # ============================================================
    banner('T5: update 同樣的值 → 應拒')
    r = update_fixed_schedule(
        session=session, schedule_id=99701, base_fare=300,
    )
    assert not r.ok and '沒有實際變動' in r.error
    print(f'  ✅ {r.error}')

    # ============================================================
    # T6: update 不允許的欄位 → 拒
    # ============================================================
    banner('T6: update 不允許的欄位（id, status）→ 應拒')
    r = update_fixed_schedule(
        session=session, schedule_id=99701, status='請假',
    )
    assert not r.ok and '不允許' in r.error
    print(f'  ✅ {r.error}（用 apply_fixed_schedule_leave 才能改 status）')

    # ============================================================
    # T7: apply_fixed_schedule_leave
    # ============================================================
    banner('T7: apply_fixed_schedule_leave(99702, 出國, -50)')
    r = apply_fixed_schedule_leave(
        session=session, schedule_id=99702,
        reason='出國', surcharge=-50,
        user_id='test', user_name='Linyan',
    )
    assert r.ok, f'leave 失敗：{r.error}'
    fs = r.data
    assert fs.status == '請假'
    assert fs.note == '出國'
    assert fs.surcharge == -50
    print(f'  ✅ #{fs.id} status={fs.status}, note={fs.note!r}, surcharge={fs.surcharge}')

    # ============================================================
    # T8: 已請假再 leave → 拒
    # ============================================================
    banner('T8: 已請假狀態再請假 → 應拒')
    r = apply_fixed_schedule_leave(
        session=session, schedule_id=99702, reason='測試',
    )
    assert not r.ok and '已是請假' in r.error
    print(f'  ✅ {r.error}')

    # ============================================================
    # T9: restore_fixed_schedule（清 status + note + surcharge）
    # ============================================================
    banner('T9: restore_fixed_schedule(99702) → 從請假恢復')
    # 確認 T7/T8 後 99702 是 status=請假, note=出國, surcharge=-50
    r = restore_fixed_schedule(
        session=session, schedule_id=99702,
        user_id='test', user_name='Linyan',
    )
    assert r.ok
    fs = r.data
    assert fs.status == '準備', f'status 應為 準備：{fs.status}'
    assert fs.note is None, f'note 應清：{fs.note!r}'
    assert fs.surcharge is None, (
        f'surcharge 應清為 NULL（fixed_schedule 是模板層，殘留會跟到 trips）：'
        f'{fs.surcharge}'
    )
    print(f'  ✅ #{fs.id} status={fs.status}, note 已清, surcharge 已清為 NULL')

    # ============================================================
    # T10: restore 已是準備 → 拒
    # ============================================================
    banner('T10: 已是準備狀態再 restore → 應拒')
    r = restore_fixed_schedule(session=session, schedule_id=99702)
    assert not r.ok and '已是準備' in r.error
    print(f'  ✅ {r.error}')

    # ============================================================
    # T11: schedule 不存在 → 各 mutation 都 fail
    # ============================================================
    banner('T11: schedule_id 不存在 → 各 mutation 都 fail')
    for fn_name, fn in [
        ('update', lambda: update_fixed_schedule(session=session, schedule_id=999999, base_fare=100)),
        ('leave', lambda: apply_fixed_schedule_leave(session=session, schedule_id=999999, reason='x')),
        ('restore', lambda: restore_fixed_schedule(session=session, schedule_id=999999)),
        ('get', lambda: get_fixed_schedule_by_id(999999, session=session)),
    ]:
        r = fn()
        assert not r.ok
        print(f'  ✅ {fn_name}: {r.error}')

    # ============================================================
    # T12: audit log 寫入
    # ============================================================
    banner('T12: audit_log 應有 update / leave / restore 三種 action')
    rows = session.execute(text("""
        SELECT action_type, COUNT(*) FROM audit_log
        WHERE target_table = 'fixed_schedules' AND target_id = ANY(:ids)
        GROUP BY action_type
    """), {'ids': fake_ids}).fetchall()
    seen = {r[0] for r in rows}
    print(f'  audit action_types: {seen}')
    assert 'update_fixed_schedule' in seen
    assert 'apply_fixed_schedule_leave' in seen
    assert 'restore_fixed_schedule' in seen
    print(f'  ✅ 3 種 action_type 都有 audit log')

    print('\n' + '=' * 60)
    print('✅ 全部 12 個 fixed_schedule 測試通過')
    print('=' * 60)
finally:
    session.rollback()   # 若中途有 aborted transaction，先清狀態才能跑清理
    for fid in fake_ids:
        try:
            session.execute(text("DELETE FROM fixed_schedules WHERE id = :id"), {'id': fid})
        except Exception:
            pass
    session.execute(text("""
        DELETE FROM audit_log
        WHERE target_table = 'fixed_schedules' AND target_id = ANY(:ids)
    """), {'ids': fake_ids})
    for sn in _fixture_customers:
        session.execute(text(
            "DELETE FROM customers WHERE short_name = :sn AND address = '測試地址'"
        ), {'sn': sn})
    session.commit()
    print(f'\n🧹 清理 fixed_schedules: {fake_ids} + audit_log + 測試客戶')
    session.close()
