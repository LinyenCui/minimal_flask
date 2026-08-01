"""
測試 rewrite/tools/driver.py — 司機管理 + 司機自助回報車資

涵蓋：
  D1  create_driver（指定編號）+ query_drivers
  D2  綁定 / 重複綁定被擋（兩個方向）/ 解綁 / 再綁
  D3  set_driver_active（停用不刪、停用中不可綁）
  D4  query_driver_pending_fares（現在態＋過去態混合、缺車資判定、days 視窗）
  D5  check_driver_owns_record（別人的班次不能動）
  D6  submit 逐筆寫入正確（呼叫既有 record_fare_current /
      update_completed_trip_fare，跟 LIFF endpoint 同一條路徑）

策略：auto_commit=False + 最後 session.rollback()，不留痕跡（比照 test_trip.py /
      test_completed_trip_mutations.py 慣例）。
⚠️ 唯一非交易性副作用：create_driver 的 setval(drivers_id_seq, MAX(id))。
   測試司機編號刻意選比現有 MAX(id) 小的號，setval 結果 = 現有 MAX，等於沒動。
"""
import sys
from datetime import time as _time, timedelta

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from sqlalchemy import text

from database import Session
from modules.utils.taiwan_time import get_taiwan_time
from rewrite.tools.completed_trip import update_completed_trip_fare
from rewrite.tools.driver import (
    bind_driver_line_user,
    check_driver_owns_record,
    create_driver,
    get_driver_by_line_user,
    query_driver_pending_fares,
    query_drivers,
    set_driver_active,
    unbind_driver,
)
from rewrite.tools.trip import record_fare_current


def banner(label):
    print(f'\n{"=" * 60}\n# {label}\n{"=" * 60}')


DRIVER_A = 60001        # 刻意 < 現有 MAX(drivers.id)，見檔頭說明
DRIVER_B = 60002
LUID_A = 'Utest_driver_aaaa0000000000000001'
LUID_B = 'Utest_driver_bbbb0000000000000002'

now = get_taiwan_time()
today = now.date()
yesterday = today - timedelta(days=1)
future_dt = now + timedelta(minutes=90)
HAS_FUTURE_SLOT = future_dt.date() == today   # 深夜跑測試時今天沒有「未來時段」

s = Session()
try:
    # 前置：測試編號不能已存在（避免撞到真司機）
    for did in (DRIVER_A, DRIVER_B):
        n = s.execute(text("SELECT COUNT(*) FROM drivers WHERE id = :i"), {'i': did}).scalar()
        assert n == 0, f'司機編號 {did} 已被使用，請換測試編號'

    # ============================================================
    # D1: create_driver + query_drivers
    # ============================================================
    banner('D1: create_driver（指定編號）+ query_drivers')
    r = create_driver(session=s, driver_id=DRIVER_A, name='測試司機甲',
                      plate_number='TEST-0001', via='test', auto_commit=False)
    assert r.ok, r.error
    assert r.data.id == DRIVER_A and r.data.name == '測試司機甲'
    assert r.data.display_name == '測試司機甲（TEST-0001）', r.data.display_name
    assert r.data.is_active and not r.data.is_bound
    print(f'  ✓ 新增 #{r.data.id} {r.data.display_name}')

    r = create_driver(session=s, driver_id=DRIVER_B, name='測試司機乙',
                      via='test', auto_commit=False)
    assert r.ok, r.error
    assert r.data.display_name == '測試司機乙', '沒車號時 display_name 不該有空括號'
    print(f'  ✓ 新增 #{r.data.id} {r.data.display_name}（無車號）')

    # 編號重複要擋
    r = create_driver(session=s, driver_id=DRIVER_A, name='撞號的',
                      via='test', auto_commit=False)
    assert not r.ok and '已存在' in r.error, r
    print(f'  ✓ 編號重複被擋：{r.error}')

    # 沒名字要擋
    assert not create_driver(session=s, name='  ', via='test', auto_commit=False).ok
    print('  ✓ 空姓名被擋')

    all_ids = [d.id for d in query_drivers(session=s, active_only=False).data]
    assert DRIVER_A in all_ids and DRIVER_B in all_ids
    print(f'  ✓ query_drivers(active_only=False) 共 {len(all_ids)} 位，含兩位測試司機')

    # ============================================================
    # D2: 綁定 / 重複綁定被擋 / 解綁 / 再綁
    # ============================================================
    banner('D2: 綁定 / 重複綁定被擋 / 解綁 / 再綁')
    assert get_driver_by_line_user(session=s, line_user_id=LUID_A).data is None
    print('  ✓ 未綁定時 get_driver_by_line_user 回 data=None（不是錯誤）')

    r = bind_driver_line_user(session=s, driver_id=DRIVER_A, line_user_id=LUID_A,
                              via='test', auto_commit=False)
    assert r.ok, r.error
    assert r.data.is_bound
    me = get_driver_by_line_user(session=s, line_user_id=LUID_A).data
    assert me is not None and me.id == DRIVER_A
    print(f'  ✓ #{DRIVER_A} 綁定 LUID_A → get_driver_by_line_user 認得')

    # 重複點同一位 → success（冪等），不報錯
    r = bind_driver_line_user(session=s, driver_id=DRIVER_A, line_user_id=LUID_A,
                              via='test', auto_commit=False)
    assert r.ok and r.meta.get('already_bound'), r
    print('  ✓ 重複綁同一組 → 冪等 success')

    # 方向一：同一個 LINE 帳號想綁第二位司機 → 擋
    r = bind_driver_line_user(session=s, driver_id=DRIVER_B, line_user_id=LUID_A,
                              via='test', auto_commit=False)
    assert not r.ok and '已經綁定司機' in r.error, r
    print(f'  ✓ 一個 LINE 帳號綁兩位司機被擋：{r.error.splitlines()[0]}')

    # 方向二：同一位司機想綁第二個 LINE 帳號 → 擋
    r = bind_driver_line_user(session=s, driver_id=DRIVER_A, line_user_id=LUID_B,
                              via='test', auto_commit=False)
    assert not r.ok and '已綁定其他 LINE 帳號' in r.error, r
    print(f'  ✓ 一位司機綁兩個帳號被擋：{r.error.splitlines()[0]}')

    # 解綁 → 再綁新帳號（換手機情境）
    r = unbind_driver(session=s, driver_id=DRIVER_A, via='test', auto_commit=False)
    assert r.ok and not r.data.is_bound, r
    assert get_driver_by_line_user(session=s, line_user_id=LUID_A).data is None
    r = unbind_driver(session=s, driver_id=DRIVER_A, via='test', auto_commit=False)
    assert not r.ok and '本來就沒有綁定' in r.error, r
    print('  ✓ 解綁成功；重複解綁回明確錯誤')

    r = bind_driver_line_user(session=s, driver_id=DRIVER_A, line_user_id=LUID_B,
                              via='test', auto_commit=False)
    assert r.ok, r.error
    print('  ✓ 解綁後可綁新的 LINE 帳號（換手機 OK）')

    # ============================================================
    # D3: set_driver_active
    # ============================================================
    banner('D3: set_driver_active（停用不刪、停用中不可綁）')
    r = set_driver_active(session=s, driver_id=DRIVER_B, active=False,
                          via='test', auto_commit=False)
    assert r.ok and r.data.is_active is False, r
    active_ids = [d.id for d in query_drivers(session=s, active_only=True).data]
    assert DRIVER_B not in active_ids, '停用後不該出現在 active 清單'
    assert DRIVER_A in active_ids
    assert DRIVER_B in [d.id for d in query_drivers(session=s, active_only=False).data], \
        '停用是 flag 不是刪除，active_only=False 要看得到'
    print('  ✓ 停用後：active 清單看不到、完整清單看得到（row 還在）')

    r = set_driver_active(session=s, driver_id=DRIVER_B, active=False,
                          via='test', auto_commit=False)
    assert not r.ok and '已經是' in r.error, r
    print(f'  ✓ 重複停用回明確錯誤：{r.error}')

    r = bind_driver_line_user(session=s, driver_id=DRIVER_B, line_user_id=LUID_A,
                              via='test', auto_commit=False)
    assert not r.ok and '已停用' in r.error, r
    print('  ✓ 停用中的司機不能被綁定')

    r = set_driver_active(session=s, driver_id=DRIVER_B, active=True,
                          via='test', auto_commit=False)
    assert r.ok and r.data.is_active is True, r
    print('  ✓ 可再啟用')

    # ============================================================
    # D4: query_driver_pending_fares — 現在態＋過去態混合
    # ============================================================
    banner('D4: query_driver_pending_fares（現在態＋過去態混合）')

    def mk_trip(*, tm, status='待派', meter=None, leave=None, driver=DRIVER_A, d=None):
        return s.execute(text("""
            INSERT INTO trips (date, time, start_point, end_point, category,
                               driver_id, status, meter_fare, extra_fare,
                               passenger_leave_reason, trip_type)
            VALUES (:d, :t, :sp, :ep, '臨時', :drv, :st, :mf, 0, :lv, 'fixed')
            RETURNING trip_id
        """), {'d': d or today, 't': tm, 'sp': '測試起點', 'ep': '測試終點',
               'drv': driver, 'st': status, 'mf': meter, 'lv': leave}).scalar()

    def mk_completed(*, meter=None, status=None, leave=None, driver=DRIVER_A,
                     d=None, code=None):
        return s.execute(text("""
            INSERT INTO completed_trips (date, start_point, end_point, category,
                                         driver_id, meter_fare, extra_fare,
                                         status, passenger_leave_reason, unique_code)
            VALUES (:d, :sp, :ep, '東洋', :drv, :mf, 0, :st, :lv, :code)
            RETURNING id
        """), {'d': d or today, 'sp': '測試起點C', 'ep': '測試終點C',
               'drv': driver, 'mf': meter, 'st': status, 'lv': leave,
               'code': code}).scalar()

    t_pending = mk_trip(tm=_time(0, 0), meter=None)             # ✅ 應列入（NULL）
    t_zero = mk_trip(tm=_time(0, 0), meter=0)                   # ✅ 應列入（0）
    t_has_fare = mk_trip(tm=_time(0, 0), meter=380)             # ❌ 已有車資
    t_done = mk_trip(tm=_time(0, 0), status='已完成', meter=0)   # ❌ 已入庫過去態，避免重複
    t_cancel = mk_trip(tm=_time(0, 0), status='註銷', meter=0)   # ❌ 註銷
    t_leave = mk_trip(tm=_time(0, 0), meter=0, leave='化療')      # ❌ 請假（老闆用加成處理）
    t_other = mk_trip(tm=_time(0, 0), meter=0, driver=DRIVER_B)  # ❌ 別人的班次
    t_future = mk_trip(tm=future_dt.time(), meter=0) if HAS_FUTURE_SLOT else None

    c_pending = mk_completed(meter=None, code='TESTDRV_C1')     # ✅ 應列入
    c_zero = mk_completed(meter=0, code='TESTDRV_C2')           # ✅ 應列入
    c_has_fare = mk_completed(meter=250, code='TESTDRV_C3')     # ❌ 已有車資
    c_cancel = mk_completed(meter=0, status='已取消', code='TESTDRV_C4')  # ❌ 已取消
    c_leave = mk_completed(meter=0, leave='住院', code='TESTDRV_C5')      # ❌ 請假
    c_yesterday = mk_completed(meter=0, d=yesterday, code='TESTDRV_C6')  # days=3 才看得到

    r = query_driver_pending_fares(session=s, driver_id=DRIVER_A, days=1)
    assert r.ok, r.error
    got = {(it['source'], it['id']) for it in r.data}
    expect_in = {('trip', t_pending), ('trip', t_zero),
                 ('completed', c_pending), ('completed', c_zero)}
    expect_out = {('trip', t_has_fare), ('trip', t_done), ('trip', t_cancel),
                  ('trip', t_leave), ('trip', t_other),
                  ('completed', c_has_fare), ('completed', c_cancel),
                  ('completed', c_leave), ('completed', c_yesterday)}
    if t_future:
        expect_out.add(('trip', t_future))
    assert expect_in <= got, f'該列入的漏了: {expect_in - got}'
    assert not (expect_out & got), f'不該列入的跑進來了: {expect_out & got}'
    print(f'  ✓ days=1 撈到 {len(r.data)} 筆，現在態＋過去態混合，'
          f'排除：已有車資／已完成／註銷／請假／別人的'
          f'{"／未來時段" if t_future else ""}')

    sample = next(it for it in r.data if it['id'] == t_pending)
    assert sample['route'] == '測試起點 → 測試終點', sample
    assert sample['time'] == '00:00' and sample['date'] == today.isoformat(), sample
    assert sample['category'] == '臨時'
    c_sample = next(it for it in r.data if it['id'] == c_pending)
    assert c_sample['time'] is None, '過去態沒有 time 欄位，應為 None'
    print(f'  ✓ 欄位格式：{sample["time"]} {sample["route"]}（{sample["category"]}）'
          f' / 過去態 time=None')

    keys = [(it['date'], it['time'] or '99:99', it['id']) for it in r.data]
    assert keys == sorted(keys), '應依日期→時間排序（過去態排同日最後）'
    print('  ✓ 排序：日期 → 時間（無時間的過去態排同日最後）')

    r3 = query_driver_pending_fares(session=s, driver_id=DRIVER_A, days=3)
    assert ('completed', c_yesterday) in {(i['source'], i['id']) for i in r3.data}, \
        'days=3 應包含昨天'
    assert r3.meta['date_from'] == (today - timedelta(days=2)).isoformat()
    print(f'  ✓ days=3 撈到 {len(r3.data)} 筆（含昨天），'
          f'區間 {r3.meta["date_from"]}~{r3.meta["date_to"]}')

    # ============================================================
    # D5: check_driver_owns_record（授權）
    # ============================================================
    banner('D5: check_driver_owns_record')
    assert check_driver_owns_record(session=s, driver_id=DRIVER_A,
                                    source='trip', record_id=t_pending).ok
    r = check_driver_owns_record(session=s, driver_id=DRIVER_A,
                                 source='trip', record_id=t_other)
    assert not r.ok and '不是你的班次' in r.error, r
    assert check_driver_owns_record(session=s, driver_id=DRIVER_A,
                                    source='completed', record_id=c_pending).ok
    r = check_driver_owns_record(session=s, driver_id=DRIVER_A,
                                 source='trip', record_id=99999999)
    assert not r.ok and '找不到' in r.error, r
    r = check_driver_owns_record(session=s, driver_id=DRIVER_A,
                                 source='亂寫', record_id=t_pending)
    assert not r.ok, r
    print('  ✓ 自己的班次放行；別人的／不存在／source 亂寫全部擋下')

    # ============================================================
    # D6: submit 逐筆寫入（走 LIFF endpoint 同一條既有工具路徑）
    # ============================================================
    banner('D6: submit 逐筆寫入（record_fare_current / update_completed_trip_fare）')
    r = record_fare_current(session=s, trip_id=t_pending, meter_fare=420,
                            extra_fare=50, user_id=LUID_B, user_name='測試司機甲',
                            via='liff_driver', auto_commit=False)
    assert r.ok, r.error
    row = s.execute(text(
        "SELECT meter_fare, extra_fare, modified_by FROM trips WHERE trip_id = :i"
    ), {'i': t_pending}).fetchone()
    assert row[0] == 420 and row[1] == 50, row
    assert row[2] == '測試司機甲', f'modified_by 應記司機姓名: {row[2]!r}'
    print(f'  ✓ 現在態 #{t_pending} → 錶價 420 / 加成 50，modified_by={row[2]}')

    r = update_completed_trip_fare(session=s, completed_trip_id=c_pending,
                                   meter_fare=300, extra_fare=0,
                                   reason='司機自助回報', user_id=LUID_B,
                                   user_name='測試司機甲', via='liff_driver',
                                   auto_commit=False)
    assert r.ok, r.error
    row = s.execute(text(
        "SELECT meter_fare, modification_reason, modified_by "
        "FROM completed_trips WHERE id = :i"
    ), {'i': c_pending}).fetchone()
    assert row[0] == 300, row
    assert '司機自助回報' in (row[1] or ''), row[1]
    print(f'  ✓ 過去態 #{c_pending} → 錶價 300，modification_reason={row[1]!r}')

    # 寫完就不該再出現在待補清單
    r = query_driver_pending_fares(session=s, driver_id=DRIVER_A, days=1)
    still = {(it['source'], it['id']) for it in r.data}
    assert ('trip', t_pending) not in still and ('completed', c_pending) not in still
    print('  ✓ 補完車資後兩筆都從待補清單消失')

    print('\n' + '=' * 60)
    print('✅ 全部測試通過（即將 rollback，不留痕跡）')
    print('=' * 60)
finally:
    s.rollback()
    s.close()
