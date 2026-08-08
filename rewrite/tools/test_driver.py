"""
測試 rewrite/tools/driver.py — 司機管理 + 司機自助回報車資

涵蓋：
  D1  create_driver（指定編號）+ query_drivers
  D2  綁定 / 重複綁定被擋（兩個方向）/ 解綁 / 再綁
  D3  set_driver_active（停用不刪、停用中不可綁）
  D4  query_driver_pending_fares（現在態＋過去態混合、缺車資判定、days 視窗）
  D5  check_driver_owns_record（別人的班次不能動 + 管理司機代填豁免）
  D6  submit 逐筆寫入正確（呼叫既有 record_fare_current /
      update_completed_trip_fare，跟 LIFF endpoint 同一條路徑）
  D7  query_driver_week_fares（太陽週界、現在態＋過去態混合、合計只計已填）
  D8  管理司機清單（include_inactive 看得到停用的 9999）＋ get_driver_by_id
  D9  handler 層：非管理司機傳 driver_id 被忽略、管理司機切得過去
      （Flask test client + mock idToken 驗證）

策略：auto_commit=False + 最後 session.rollback()，不留痕跡（比照 test_trip.py /
      test_completed_trip_mutations.py 慣例）。
⚠️ 唯一非交易性副作用：create_driver 的 setval(drivers_id_seq, MAX(id))。
   測試司機編號刻意選比現有 MAX(id) 小的號，setval 結果 = 現有 MAX，等於沒動。
"""
import sys
from datetime import time as _time, timedelta

from dotenv import load_dotenv
# 跟其他測試一致：.env 打底、.env.dev 覆蓋（只載 .env 會拿到不同的 DATABASE_URL）
load_dotenv('/Users/linyancui/minimal_flask/.env')
load_dotenv('/Users/linyancui/minimal_flask/.env.dev', override=True)

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from sqlalchemy import text

from database import Session
from modules.utils.taiwan_time import get_taiwan_time
from rewrite.tools.completed_trip import update_completed_trip_fare
from rewrite.tools.driver import (
    bind_driver_line_user,
    check_driver_owns_record,
    create_driver,
    get_driver_by_id,
    get_driver_by_line_user,
    query_driver_pending_fares,
    query_driver_week_fares,
    query_drivers,
    set_driver_active,
    unbind_driver,
)
from rewrite.tools.trip import record_fare_current
from rewrite.utils.sun_week import sun_week_start


def banner(label):
    print(f'\n{"=" * 60}\n# {label}\n{"=" * 60}')


DRIVER_A = 60001        # 刻意 < 現有 MAX(drivers.id)，見檔頭說明
DRIVER_B = 60002
DRIVER_M = 60003        # 管理司機（模擬 5386 老闆／1117 春妃）
LUID_A = 'Utest_driver_aaaa0000000000000001'
LUID_B = 'Utest_driver_bbbb0000000000000002'
LUID_M = 'Utest_driver_mmmm0000000000000003'

now = get_taiwan_time()
today = now.date()
yesterday = today - timedelta(days=1)
future_dt = now + timedelta(minutes=90)
HAS_FUTURE_SLOT = future_dt.date() == today   # 深夜跑測試時今天沒有「未來時段」

s = Session()
try:
    # 前置：測試編號不能已存在（避免撞到真司機）
    for did in (DRIVER_A, DRIVER_B, DRIVER_M):
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
    # 2026-08-02 用戶定調：display_name 以司機編號為主（有些司機不知姓名）
    assert r.data.display_name == f'{r.data.id}　測試司機甲', r.data.display_name
    assert r.data.is_active and not r.data.is_bound
    print(f'  ✓ 新增 #{r.data.id} {r.data.display_name}')

    r = create_driver(session=s, driver_id=DRIVER_B, name='測試司機乙',
                      via='test', auto_commit=False)
    assert r.ok, r.error
    assert r.data.display_name == f'{r.data.id}　測試司機乙', r.data.display_name
    print(f'  ✓ 新增 #{r.data.id} {r.data.display_name}')

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

    def mk_trip(*, tm, status='待派', meter=None, leave=None, driver=DRIVER_A, d=None,
                extra=0):
        return s.execute(text("""
            INSERT INTO trips (date, time, start_point, end_point, category,
                               driver_id, status, meter_fare, extra_fare,
                               passenger_leave_reason, trip_type)
            VALUES (:d, :t, :sp, :ep, '臨時', :drv, :st, :mf, :ex, :lv, 'fixed')
            RETURNING trip_id
        """), {'d': d or today, 't': tm, 'sp': '測試起點', 'ep': '測試終點',
               'drv': driver, 'st': status, 'mf': meter, 'lv': leave,
               'ex': extra}).scalar()

    def mk_completed(*, meter=None, status=None, leave=None, driver=DRIVER_A,
                     d=None, code=None, extra=0):
        return s.execute(text("""
            INSERT INTO completed_trips (date, start_point, end_point, category,
                                         driver_id, meter_fare, extra_fare,
                                         status, passenger_leave_reason, unique_code)
            VALUES (:d, :sp, :ep, '東洋', :drv, :mf, :ex, :st, :lv, :code)
            RETURNING id
        """), {'d': d or today, 'sp': '測試起點C', 'ep': '測試終點C',
               'drv': driver, 'mf': meter, 'st': status, 'lv': leave, 'ex': extra,
               'code': code}).scalar()

    t_pending = mk_trip(tm=_time(0, 0), meter=None)             # ✅ 應列入（NULL）
    t_zero = mk_trip(tm=_time(0, 0), meter=0)                   # ✅ 應列入（0）
    t_has_fare = mk_trip(tm=_time(0, 0), meter=380)             # ❌ 已有車資
    t_done = mk_trip(tm=_time(0, 0), status='已完成', meter=0)   # ❌ 已入庫過去態，避免重複
    t_cancel = mk_trip(tm=_time(0, 0), status='註銷', meter=0)   # ❌ 註銷
    # 請假的兩種樣態：
    #   t_leave      錶價 0 —— 待補清單要排除（不叫司機補）
    #   t_leave_paid 錶價 200 / 加成 −95 —— PROD 真實長相（同車某位乘客沒來、
    #                車照跑），司機實拿 105，週車資列表必須收，待補清單仍排除
    t_leave = mk_trip(tm=_time(0, 0), meter=0, leave='化療')
    t_leave_paid = mk_trip(tm=_time(0, 0), meter=200, extra=-95, leave='中華北路住院')
    t_other = mk_trip(tm=_time(0, 0), meter=0, driver=DRIVER_B)  # ❌ 別人的班次
    t_future = mk_trip(tm=future_dt.time(), meter=0) if HAS_FUTURE_SLOT else None

    c_pending = mk_completed(meter=None, code='TESTDRV_C1')     # ✅ 應列入
    c_zero = mk_completed(meter=0, code='TESTDRV_C2')           # ✅ 應列入
    c_has_fare = mk_completed(meter=250, code='TESTDRV_C3')     # ❌ 已有車資
    c_cancel = mk_completed(meter=0, status='已取消', code='TESTDRV_C4')  # ❌ 已取消
    c_leave = mk_completed(meter=0, leave='住院', code='TESTDRV_C5')
    c_leave_paid = mk_completed(meter=200, extra=-95, leave='住院',
                                code='TESTDRV_C5B')
    c_yesterday = mk_completed(meter=0, d=yesterday, code='TESTDRV_C6')  # days=3 才看得到

    r = query_driver_pending_fares(session=s, driver_id=DRIVER_A, days=1)
    assert r.ok, r.error
    got = {(it['source'], it['id']) for it in r.data}
    expect_in = {('trip', t_pending), ('trip', t_zero),
                 ('completed', c_pending), ('completed', c_zero)}
    expect_out = {('trip', t_has_fare), ('trip', t_done), ('trip', t_cancel),
                  ('trip', t_leave), ('trip', t_leave_paid), ('trip', t_other),
                  ('completed', c_has_fare), ('completed', c_cancel),
                  ('completed', c_leave), ('completed', c_leave_paid),
                  ('completed', c_yesterday)}
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

    # ---- 管理司機代填豁免 ----
    r = create_driver(session=s, driver_id=DRIVER_M, name='測試管理司機',
                      via='test', auto_commit=False)
    assert r.ok, r.error
    s.execute(text("UPDATE drivers SET is_manager = TRUE WHERE id = :i"), {'i': DRIVER_M})
    mgr = get_driver_by_id(session=s, driver_id=DRIVER_M).data
    assert mgr.is_manager is True, 'is_manager 應該一路透到 DriverView'
    normal_b = get_driver_by_id(session=s, driver_id=DRIVER_B).data
    assert normal_b.is_manager is False

    # 管理司機代 A 填 A 的班次 → 放行
    r = check_driver_owns_record(session=s, driver_id=DRIVER_A, source='trip',
                                 record_id=t_pending, acting_driver=mgr)
    assert r.ok, r.error
    r = check_driver_owns_record(session=s, driver_id=DRIVER_A, source='completed',
                                 record_id=c_pending, acting_driver=mgr)
    assert r.ok, r.error
    print('  ✓ 管理司機代填：檢視 A 時可寫 A 的現在態／過去態班次')

    # 管理司機檢視 A，卻送 B 的班次 → 仍要擋（避免手殘寫到第三人）
    r = check_driver_owns_record(session=s, driver_id=DRIVER_A, source='trip',
                                 record_id=t_other, acting_driver=mgr)
    assert not r.ok and '不是這位司機的班次' in r.error, r
    print(f'  ✓ 管理司機不是無條件放行：{r.error}')

    # 一般司機想代別人填 → 擋
    r = check_driver_owns_record(session=s, driver_id=DRIVER_A, source='trip',
                                 record_id=t_pending, acting_driver=normal_b)
    assert not r.ok and '只能填自己的班次車資' in r.error, r
    print(f'  ✓ 一般司機代填被擋：{r.error}')

    # 自己填自己（acting = 本人）→ 跟不帶 acting_driver 行為一致
    me_a = get_driver_by_id(session=s, driver_id=DRIVER_A).data
    assert check_driver_owns_record(session=s, driver_id=DRIVER_A, source='trip',
                                    record_id=t_pending, acting_driver=me_a).ok
    r = check_driver_owns_record(session=s, driver_id=DRIVER_A, source='trip',
                                 record_id=t_other, acting_driver=me_a)
    assert not r.ok and '不是你的班次' in r.error, r
    print('  ✓ 帶 acting_driver=本人 時行為與舊版一致')

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

    # ============================================================
    # D7: query_driver_week_fares — 太陽週界 + 混合 + 合計只計已填
    # ============================================================
    banner('D7: query_driver_week_fares（本太陽週 = 星期日 ~ 今天）')

    week_start = sun_week_start(today)          # ← 對照組用 helper 算，不自己推
    before_week = week_start - timedelta(days=1)
    c_in_week = mk_completed(meter=100, d=week_start, code='TESTDRV_W1')   # 週日當天要含
    c_before = mk_completed(meter=999, d=before_week, code='TESTDRV_W0')   # 上一週，要排除

    r = query_driver_week_fares(session=s, driver_id=DRIVER_A)
    assert r.ok, r.error

    # 週界：起點必為星期日，且距今天的天數 = (weekday+1)%7（太陽週定義）
    assert week_start.weekday() == 6, '太陽週起點必須是星期日'
    assert r.meta['week_start'] == week_start.isoformat(), r.meta
    assert r.meta['week_end'] == today.isoformat(), '截止到今天（這星期到目前）'
    assert (today - week_start).days == (today.weekday() + 1) % 7
    print(f'  ✓ 週界 {r.meta["week_start"]}（日）~ {r.meta["week_end"]}（今天）'
          f'，與 sun_week_start 一致')

    in_week_yesterday = yesterday >= week_start   # 今天是星期日的話昨天屬上一週
    got = {(it['source'], it['id']) for it in r.data}
    expect_in = {
        ('trip', t_pending),        # 已填 420+50
        ('trip', t_zero),           # 未填
        ('trip', t_has_fare),       # 已填 380
        ('completed', c_pending),   # 已填 300
        ('completed', c_zero),      # 未填
        ('completed', c_has_fare),  # 已填 250
        ('completed', c_in_week),   # 已填 100（週日當天）
        # 請假班次要收 —— 車照跑，司機賺的錢不能漏算（2026-08-05 修正）
        ('trip', t_leave),          # 錶價 0 → 收進來但算未填
        ('trip', t_leave_paid),     # 錶價 200 / 加成 −95 → 已填，計 105
        ('completed', c_leave),     # 錶價 0 → 收進來但算未填
        ('completed', c_leave_paid),  # 已填，計 105
    }
    expect_out = {
        ('trip', t_done), ('trip', t_cancel), ('trip', t_other),
        ('completed', c_cancel), ('completed', c_before),
    }
    if t_future:
        expect_out.add(('trip', t_future))
    if in_week_yesterday:
        expect_in.add(('completed', c_yesterday))   # 未填
    else:
        expect_out.add(('completed', c_yesterday))
    # DRIVER_A 是全新測試司機 → 整週清單就只會有這些
    assert got == expect_in, f'漏: {expect_in - got} / 多: {got - expect_in}'
    assert not (expect_out & got), f'不該列入的跑進來了: {expect_out & got}'
    print(f'  ✓ 收錄 {len(got)} 筆（現在態＋過去態混合）；'
          f'含請假（車照跑）；排除：已完成／註銷／衝突／別人的／上一週'
          f'{"／未來時段" if t_future else ""}')

    by_id = {(it['source'], it['id']): it for it in r.data}
    filled = by_id[('trip', t_pending)]
    assert filled['has_fare'] is True and filled['total'] == 470, filled
    todo = by_id[('trip', t_zero)]
    assert todo['has_fare'] is False and todo['total'] == 0, todo
    assert by_id[('completed', c_in_week)]['date'] == week_start.isoformat()
    assert by_id[('completed', c_pending)]['time'] is None, '過去態沒有 time'
    print(f'  ✓ 每筆欄位：已填 {filled["route"]} total={filled["total"]}、'
          f'未填 has_fare=False total=0')

    # 合計只計已填。請假但錶價照跳的兩筆（200−95=105）必須計入 ——
    # 以前被整批排除，導致司機的車資被少算（用戶回報的 470 元差額主因）
    expect_filled = 7
    expect_sum = 470 + 380 + 300 + 250 + 100 + 105 + 105
    assert r.meta['count'] == len(expect_in), r.meta
    assert r.meta['filled_count'] == expect_filled, r.meta
    assert r.meta['sum_amount'] == expect_sum, r.meta
    assert sum(1 for it in r.data if not it['has_fare']) == len(expect_in) - expect_filled
    print(f'  ✓ 合計 {r.meta["sum_amount"]} 元'
          f'（已填 {r.meta["filled_count"]}／共 {r.meta["count"]} 筆），未填不計入')

    keys = [(it['date'], it['time'] or '99:99', it['id']) for it in r.data]
    assert keys == sorted(keys), '應依日期→時間排序'
    print('  ✓ 排序：日期 → 時間')

    # 沒班次的司機 → 空清單、合計 0（不是錯誤）
    r_empty = query_driver_week_fares(session=s, driver_id=DRIVER_M)
    assert r_empty.ok and r_empty.data == [] and r_empty.meta['sum_amount'] == 0, r_empty
    print('  ✓ 沒班次的司機回空清單 + 合計 0')

    # ============================================================
    # D8: 管理司機看得到停用的司機（切換選單）
    # ============================================================
    banner('D8: query_drivers(include_inactive) + get_driver_by_id')
    r = set_driver_active(session=s, driver_id=DRIVER_B, active=False,
                          via='test', auto_commit=False)
    assert r.ok, r.error
    active_ids = [d.id for d in query_drivers(session=s).data]
    all_ids = [d.id for d in query_drivers(session=s, include_inactive=True).data]
    assert DRIVER_B not in active_ids, '預設清單不該有停用的'
    assert DRIVER_B in all_ids, '管理司機的切換選單要看得到停用的'
    assert DRIVER_A in active_ids and DRIVER_A in all_ids
    print(f'  ✓ include_inactive=True 多撈到停用司機（{len(active_ids)} → {len(all_ids)} 位）')

    # 停用的排後面（選單不會被 9999 卡在中間）
    views = query_drivers(session=s, include_inactive=True).data
    flags = [v.is_active for v in views]
    assert flags == sorted(flags, key=lambda a: not a), '停用的應排在啟用的後面'
    real_9999 = s.execute(text("SELECT id FROM drivers WHERE id = 9999")).scalar()
    if real_9999:
        assert 9999 in all_ids, '停用的 9999「其他」也要出現在管理司機的選單'
        print('  ✓ 停用的 9999「其他」有出現在完整清單（舊班次還掛在它名下）')

    r = get_driver_by_id(session=s, driver_id=DRIVER_B)
    assert r.ok and r.data.is_active is False, '停用的司機 get_driver_by_id 也要撈得到'
    assert not get_driver_by_id(session=s, driver_id=99999999).ok
    print('  ✓ get_driver_by_id：停用的撈得到、不存在的回錯誤')
    set_driver_active(session=s, driver_id=DRIVER_B, active=True,
                      via='test', auto_commit=False)

    # ============================================================
    # D9: handler 層 —— 非管理司機傳 driver_id 要被忽略
    # ============================================================
    banner('D9: /liff/driver/fare/state 的 driver_id 權限（Flask test client）')

    import rewrite.handlers.liff.auth as liff_auth
    import rewrite.handlers.liff.driver_fare as dfare
    from flask import Flask

    from rewrite.handlers.liff import liff_bp

    # 1) mock idToken 驗證：Bearer <line_user_id> 直接當成該使用者
    _orig_verify = liff_auth.verify_line_id_token
    liff_auth.verify_line_id_token = lambda tok: {'sub': tok, 'name': 'test'}

    # 2) handler 開自己的 Session → 換成本測試這條（未 commit 的資料才看得見）；
    #    close/commit/rollback 全部吃掉，避免把測試交易收掉
    class _SessionProxy:
        def __init__(self, real):
            object.__setattr__(self, '_real', real)

        def __getattr__(self, k):
            return getattr(object.__getattribute__(self, '_real'), k)

        def close(self):
            pass

        def commit(self):
            pass

        def rollback(self):
            pass

    _orig_session = dfare.Session
    dfare.Session = lambda: _SessionProxy(s)

    try:
        # 管理司機也要綁 LINE 帳號才進得了表單
        rb = bind_driver_line_user(session=s, driver_id=DRIVER_M, line_user_id=LUID_M,
                                   via='test', auto_commit=False)
        assert rb.ok, rb.error

        app = Flask(__name__)
        app.register_blueprint(liff_bp)
        client = app.test_client()

        def get_state(luid, driver_id=None):
            url = '/liff/driver/fare/state?days=1'
            if driver_id is not None:
                url += f'&driver_id={driver_id}'
            resp = client.get(url, headers={'Authorization': f'Bearer {luid}'})
            assert resp.status_code == 200, (resp.status_code, resp.get_data(as_text=True))
            return resp.get_json()

        # 一般司機（DRIVER_A，綁 LUID_B）想看別人的 → 忽略，回自己的
        st = get_state(LUID_B, DRIVER_B)
        assert st['ok'] and st['bound']
        assert st['me']['id'] == DRIVER_A and st['me']['is_manager'] is False
        assert st['viewing']['id'] == DRIVER_A, f"非管理員的 driver_id 應被忽略: {st['viewing']}"
        assert st['drivers_all'] == [], '一般司機不該拿到司機清單（前端也就 render 不出切換列）'
        print('  ✓ 一般司機傳 driver_id → 忽略，viewing 仍是自己、drivers_all 為空')

        # 一般司機的本週車資是自己的
        assert st['week']['start'] == week_start.isoformat()
        assert st['week']['sum_amount'] == expect_sum, st['week']
        print(f'  ✓ state 帶本週車資：{st["week"]["start"]}~{st["week"]["end"]}'
              f' 合計 {st["week"]["sum_amount"]} 元')

        # 管理司機（DRIVER_M，綁 LUID_M）切去看 DRIVER_A
        st = get_state(LUID_M, DRIVER_A)
        assert st['me']['id'] == DRIVER_M and st['me']['is_manager'] is True
        assert st['viewing']['id'] == DRIVER_A, '管理司機應該切得過去'
        assert st['week']['sum_amount'] == expect_sum, '看到的是 A 的本週車資'
        ids_all = [d['id'] for d in st['drivers_all']]
        assert DRIVER_A in ids_all and DRIVER_M in ids_all
        if real_9999:
            assert 9999 in ids_all, '管理司機的切換選單要含停用的 9999'
        print(f'  ✓ 管理司機切到 #{DRIVER_A}：viewing 換人、合計換成對方的、'
              f'drivers_all {len(ids_all)} 位（含停用）')

        # 管理司機不指定 → 預設看自己
        st = get_state(LUID_M)
        assert st['viewing']['id'] == DRIVER_M and st['week']['sum_amount'] == 0
        print('  ✓ 管理司機不指定 driver_id → 預設看自己')

        # 管理司機指定不存在的司機 → 退回自己（不當機）
        st = get_state(LUID_M, 99999999)
        assert st['viewing']['id'] == DRIVER_M
        print('  ✓ 指定不存在的司機 → 安全退回自己')
    finally:
        liff_auth.verify_line_id_token = _orig_verify
        dfare.Session = _orig_session

    print('\n' + '=' * 60)
    print('✅ 全部測試通過（即將 rollback，不留痕跡）')
    print('=' * 60)
finally:
    s.rollback()
    s.close()
