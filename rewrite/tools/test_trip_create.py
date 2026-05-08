"""
測試 create_trip — 第 3 批 mutation：trips 增

驗證：
  - 起終點 FK 校驗 + 「臨時地點」fallback（雙寫）
  - 司機驗證（給 → 準備、沒給 → 待派、不存在 → 拒）
  - unique_code 格式 T_{trip_id}_{YYYYMMDD}
  - week_number 自動計算
  - 必填驗證
  - R-6 audit log（before=None, after=完整 snapshot）
"""
import sys
from datetime import date, datetime, timedelta, time as dt_time
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import Session
from sqlalchemy import text
from rewrite.tools.trip import create_trip, query_trip_by_id

USER_ID = 'U6b520261e9199a21d25e6d20509eda3f'


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


session = Session()
created_ids = []
try:
    today = date.today()
    base_time = dt_time(10, 30)

    # ============================================================
    # T1: FK 校驗成功 — 起終點都在 customers（雙寫）
    # ============================================================
    banner('T1: FK 起終點都在 customers → 雙寫 start_point + custom_start_point')
    r = create_trip(
        session=session,
        trip_date=today + timedelta(days=2),
        trip_time=base_time,
        start_point='龍埔街',
        end_point='診所',
        category='診所',
        passenger_name='測試病患A',
        meter_fare=340,
        user_id=USER_ID, user_name='Linyan',
        via='quick_command',
    )
    assert r.ok, f'create failed: {r.error}'
    t = r.data
    created_ids.append(t.trip_id)
    print(f'  ✅ trip_id={t.trip_id} status={t.status}')
    # 確認雙寫
    row = session.execute(text("""
        SELECT start_point, custom_start_point, end_point, custom_end_point
        FROM trips WHERE trip_id = :id
    """), {'id': t.trip_id}).fetchone()
    print(f'  start: fk={row[0]!r} custom={row[1]!r} | end: fk={row[2]!r} custom={row[3]!r}')
    assert row[0] == '龍埔街' and row[1] == '龍埔街', 'start_point 應雙寫'
    assert row[2] == '診所' and row[3] == '診所', 'end_point 應雙寫'
    print(f'  ✅ FK 起終點雙寫一致')

    # ============================================================
    # T2: 起點不在 customers → fallback '臨時地點'
    # ============================================================
    banner('T2: 起點 "陽明山某某住家" 不在 customers → fallback 臨時地點')
    r = create_trip(
        session=session,
        trip_date=today + timedelta(days=2),
        trip_time=dt_time(11, 0),
        start_point='陽明山某某住家',
        end_point='診所',  # 終點在 customers
        category='臨時',
        user_id=USER_ID, user_name='Linyan',
    )
    assert r.ok, f'create failed: {r.error}'
    t = r.data
    created_ids.append(t.trip_id)
    row = session.execute(text("""
        SELECT start_point, custom_start_point, end_point, custom_end_point
        FROM trips WHERE trip_id = :id
    """), {'id': t.trip_id}).fetchone()
    print(f'  start: fk={row[0]!r} custom={row[1]!r}')
    print(f'  end:   fk={row[2]!r} custom={row[3]!r}')
    assert row[0] == '臨時地點', f'起點 fk 應為 臨時地點，實際 {row[0]!r}'
    assert row[1] == '陽明山某某住家', f'custom 應保留實際值'
    assert row[2] == '診所' and row[3] == '診所', '終點 FK 一致'
    print(f'  ✅ FK fallback 正確：起點走 臨時地點，custom 留實際值')

    # ============================================================
    # T3: 終點為空 → end_point=None
    # ============================================================
    banner('T3: end_point=None → 都為 NULL（單程班次）')
    r = create_trip(
        session=session,
        trip_date=today + timedelta(days=2),
        trip_time=dt_time(11, 30),
        start_point='龍埔街',
        end_point=None,
        user_id=USER_ID,
    )
    assert r.ok, f'create failed: {r.error}'
    t = r.data
    created_ids.append(t.trip_id)
    row = session.execute(text("""
        SELECT end_point, custom_end_point FROM trips WHERE trip_id = :id
    """), {'id': t.trip_id}).fetchone()
    assert row[0] is None and row[1] is None, f'end 應為 NULL，實際 {row}'
    print(f'  ✅ 終點 NULL（end_point={row[0]}, custom={row[1]}）')

    # ============================================================
    # T4: 給司機 → status='準備'，driver_id 設置
    # ============================================================
    banner('T4: 帶 driver_id=533 → status 應為 準備')
    r = create_trip(
        session=session,
        trip_date=today + timedelta(days=3),
        trip_time=base_time,
        start_point='龍埔街',
        end_point='診所',
        driver_id=533,
        user_id=USER_ID, user_name='Linyan',
    )
    assert r.ok
    t = r.data
    created_ids.append(t.trip_id)
    assert t.status == '準備', f'有司機應為 準備，實際 {t.status}'
    assert t.driver_id == 533
    print(f'  ✅ status={t.status} driver_id={t.driver_id}')

    # ============================================================
    # T5: 沒給司機 → status='待派'
    # ============================================================
    banner('T5: 不帶 driver_id → status 應為 待派')
    r = create_trip(
        session=session,
        trip_date=today + timedelta(days=3),
        trip_time=dt_time(13, 0),
        start_point='龍埔街',
        end_point='診所',
        user_id=USER_ID,
    )
    assert r.ok
    t = r.data
    created_ids.append(t.trip_id)
    assert t.status == '待派', f'無司機應為 待派，實際 {t.status}'
    assert t.driver_id is None
    print(f'  ✅ status={t.status} driver_id={t.driver_id}')

    # ============================================================
    # T6: 司機不存在 → 拒
    # ============================================================
    banner('T6: driver_id=88888 不存在 → 應拒')
    r = create_trip(
        session=session,
        trip_date=today + timedelta(days=3),
        trip_time=dt_time(14, 0),
        start_point='龍埔街',
        end_point='診所',
        driver_id=88888,
        user_id=USER_ID,
    )
    assert not r.ok
    assert '司機' in r.error
    print(f'  ✅ {r.error}')

    # ============================================================
    # T7: start_point 必填
    # ============================================================
    banner('T7: start_point="" → 應拒')
    r = create_trip(
        session=session,
        trip_date=today + timedelta(days=3),
        trip_time=dt_time(15, 0),
        start_point='   ',  # 全空白
        user_id=USER_ID,
    )
    assert not r.ok
    print(f'  ✅ {r.error}')

    # ============================================================
    # T8: unique_code 格式 T_{trip_id}_{YYYYMMDD}
    # ============================================================
    banner('T8: unique_code 格式驗證')
    target_date = today + timedelta(days=5)
    r = create_trip(
        session=session,
        trip_date=target_date,
        trip_time=dt_time(9, 0),
        start_point='龍埔街',
        end_point='診所',
        user_id=USER_ID,
    )
    assert r.ok
    t = r.data
    created_ids.append(t.trip_id)
    expected_code = f"T_{t.trip_id}_{target_date.strftime('%Y%m%d')}"
    assert t.unique_code == expected_code, f'expected {expected_code}, got {t.unique_code}'
    print(f'  ✅ unique_code = {t.unique_code}')

    # ============================================================
    # T9: week_number 自動計算
    # ============================================================
    banner('T9: week_number 自動計算（ISO 週次）')
    _, expected_week, _ = target_date.isocalendar()
    assert t.week_number == expected_week, f'expected week {expected_week}, got {t.week_number}'
    print(f'  ✅ {target_date} ISO 週次 = {t.week_number}（預期 {expected_week}）')

    # ============================================================
    # T10: audit log 寫入
    # ============================================================
    banner('T10: audit_log 應有 create_trip 紀錄（before=None, after 完整）')
    audit_count = session.execute(text("""
        SELECT COUNT(*) FROM audit_log
        WHERE target_table = 'trips' AND target_id = ANY(:ids)
              AND action_type = 'create_trip'
    """), {'ids': created_ids}).scalar()
    print(f'  共 {audit_count} 筆 create_trip audit')
    assert audit_count == len(created_ids), \
        f'audit 數量不對：{audit_count} vs {len(created_ids)}'

    # 抽一筆看內容
    row = session.execute(text("""
        SELECT before_state, after_state, extra
        FROM audit_log
        WHERE target_table = 'trips' AND target_id = :id
              AND action_type = 'create_trip'
        ORDER BY created_at LIMIT 1
    """), {'id': created_ids[0]}).fetchone()
    print(f'  before_state = {row[0]}')
    print(f'  after_state keys = {list(row[1].keys()) if row[1] else None}')
    print(f'  extra = {row[2]}')
    assert row[0] is None, 'before_state 應為 NULL'
    assert row[1] is not None and 'trip_id' in row[1], 'after_state 應有 trip_id'
    assert row[2] and 'fk_resolved' in row[2], 'extra 應有 fk_resolved'
    print(f'  ✅ audit log 結構正確')

    # ============================================================
    # T11: via_point 雙寫到 custom_via_point
    # ============================================================
    banner('T11: via_point 雙寫（給 scheduler 看 custom_*）')
    r = create_trip(
        session=session,
        trip_date=today + timedelta(days=6),
        trip_time=dt_time(10, 0),
        start_point='龍埔街',
        via_point='順路便利商店',
        end_point='診所',
        user_id=USER_ID,
    )
    assert r.ok
    t = r.data
    created_ids.append(t.trip_id)
    row = session.execute(text("""
        SELECT via_point, custom_via_point FROM trips WHERE trip_id = :id
    """), {'id': t.trip_id}).fetchone()
    assert row[0] == '順路便利商店' and row[1] == '順路便利商店'
    print(f'  ✅ via 雙寫：via_point={row[0]!r} custom_via_point={row[1]!r}')

    # ============================================================
    # T12: extra_fare 非整數 → 拒
    # ============================================================
    banner('T12: extra_fare="abc" → 應拒')
    r = create_trip(
        session=session,
        trip_date=today + timedelta(days=6),
        trip_time=dt_time(11, 0),
        start_point='龍埔街',
        extra_fare='abc',
        user_id=USER_ID,
    )
    assert not r.ok
    print(f'  ✅ {r.error}')

    print('\n' + '='*60)
    print(f'✅ 全部 12 個 create_trip 測試通過')
    print(f'   FK 校驗 ✓ / fallback ✓ / 雙寫 ✓ / unique_code ✓ /')
    print(f'   司機驗證 ✓ / R-6 audit ✓')
    print(f'   建立 trip_ids: {created_ids}')
    print('='*60)

finally:
    # 清理
    for fid in created_ids:
        try:
            session.execute(text("DELETE FROM trips WHERE trip_id = :id"), {'id': fid})
        except Exception:
            pass
    if created_ids:
        session.execute(text("""
            DELETE FROM audit_log
            WHERE target_table = 'trips' AND target_id = ANY(:ids)
        """), {'ids': created_ids})
    session.commit()
    if created_ids:
        print(f'\n🧹 清理測試 trips: {created_ids} + 對應 audit_log')
    session.close()
