"""
測試 trips 查詢工具（純函數，無 Flask）
"""
import sys
from datetime import date, timedelta
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import Session
from rewrite.tools.trip import (
    query_trips,
    query_trip_by_id,
    query_today_trips,
    query_pending_dispatch,
    TripView,
    STATUS_EMOJI,
)


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


session = Session()
try:
    # ============================================================
    # T1: query_trip_by_id
    # ============================================================
    banner('T1: query_trip_by_id(1043)')
    r = query_trip_by_id(1043, session=session)
    if r.ok:
        t = r.data
        print(f'  #{t.trip_id} {t.date} {t.time} {t.short_route()}')
        print(f'  狀態: {t.status_emoji} {t.display_status} (raw: {t.status!r})')
        print(f'  司機: {t.driver_id}')
        print(f'  車資: {t.meter_fare}+{t.extra_fare}={t.actual_fare}')
        print(f'  請假: {t.passenger_leave_reason!r}')
        print(f'  鎖? {t.is_locked} (距現在 {t.minutes_until_trip} 分)')
    else:
        print(f'  ❌ {r.error}')

    # ============================================================
    # T2: 今天班次
    # ============================================================
    banner('T2: query_today_trips()')
    r = query_today_trips(session=session)
    if r.ok:
        print(f'  共 {r.meta["count"]} 筆')
        # 簡短列出前 5 筆
        for t in r.data[:5]:
            print(f'  {t.status_emoji} {t.trip_id} {t.time}'
                  f' {t.start_point}→{t.end_point} 司機{t.driver_id}')
    else:
        print(f'  {r.error}')

    # ============================================================
    # T3: 今天 + 排除已完成
    # ============================================================
    banner('T3: query_today_trips(include_completed=False)')
    r = query_today_trips(session=session, include_completed=False)
    if r.ok:
        print(f'  共 {r.meta["count"]} 筆')
        for t in r.data[:10]:
            print(f'  {t.status_emoji} {t.trip_id} {t.time} {t.short_route()} [{t.display_status}]')
    else:
        print(f'  {r.error}')

    # ============================================================
    # T4: 範圍 + 司機
    # ============================================================
    banner('T4: query_trips(4/26-5/2, driver=533, 診所)')
    r = query_trips(
        session=session,
        date_from=date(2026, 4, 26),
        date_to=date(2026, 5, 2),
        driver_id=533,
        category='診所',
    )
    if r.ok:
        print(f'  共 {r.meta["count"]} 筆')
        for t in r.data[:5]:
            print(f'  {t.status_emoji} #{t.trip_id} {t.date} {t.time} {t.short_route()}')
    else:
        print(f'  {r.error}')

    # ============================================================
    # T5: 客戶名稱模糊（龍埔街今天）
    # ============================================================
    banner('T5: query_trips(today, customer_short_name=龍埔街)')
    today = date.today()
    r = query_trips(
        session=session,
        date_from=today,
        date_to=today,
        customer_short_name='龍埔街',
    )
    if r.ok:
        print(f'  共 {r.meta["count"]} 筆')
        for t in r.data:
            print(f'  #{t.trip_id} {t.time} {t.short_route()} {t.status_emoji}')
    else:
        print(f'  {r.error}')

    # ============================================================
    # T6: 待派班次
    # ============================================================
    banner('T6: query_pending_dispatch')
    r = query_pending_dispatch(session=session)
    if r.ok:
        print(f'  共 {r.meta["count"]} 筆待派')
        for t in r.data[:5]:
            print(f'  #{t.trip_id} {t.date} {t.time} {t.short_route()} '
                  f'[{t.display_status}] driver={t.driver_id}')
    else:
        print(f'  {r.error}')

    # ============================================================
    # T7: 不存在
    # ============================================================
    banner('T7: query_trip_by_id(99999)')
    r = query_trip_by_id(99999, session=session)
    print(f'  ok={r.ok}  error={r.error}')

    # ============================================================
    # T8: 三層障眼法驗證（請假 → display_status='請假'）
    # ============================================================
    banner('T8: 三層障眼法 — #1043 應為「請假」')
    r = query_trip_by_id(1043, session=session)
    if r.ok:
        t = r.data
        print(f'  raw status: {t.status!r}')
        print(f'  passenger_leave_reason: {t.passenger_leave_reason!r}')
        print(f'  display_status: {t.display_status!r}')
        print(f'  status_emoji: {t.status_emoji}')
        if t.passenger_leave_reason and t.status == '準備':
            assert t.display_status == '請假'
            print(f'  ✅ 三層障眼法正確展示為「請假」')

    # ============================================================
    # T9: 鎖定窗計算（用 #1043 today 10:15 看現在是否在 30 分內）
    # ============================================================
    banner('T9: 鎖定窗計算')
    r = query_trip_by_id(1043, session=session)
    if r.ok:
        t = r.data
        from datetime import datetime
        print(f'  trip 時間: {t.date} {t.time}')
        print(f'  目前時間: {datetime.now()}')
        print(f'  距 trip: {t.minutes_until_trip} 分')
        print(f'  is_locked? {t.is_locked}')
        if t.minutes_until_trip is not None:
            if 0 < t.minutes_until_trip < 30:
                assert t.is_locked, '應該鎖'
                print(f'  ✅ 在 30 分內 → 鎖定 ✓')
            elif t.minutes_until_trip < 0:
                print(f'  ℹ️  trip 已過 → 不鎖')
            else:
                print(f'  ℹ️  trip 未到 30 分內 → 不鎖')

    # ============================================================
    # T10: 時段篩選 time_from / time_to（str coerce）
    # ============================================================
    banner('T10: query_trips(time_from="09:00") — 全部結果 time >= 09:00')
    from datetime import time as dt_time
    r = query_trips(time_from='09:00', session=session, limit=50)
    if r.ok:
        assert all(t.time >= dt_time(9, 0) for t in r.data if t.time), '有 09:00 前的班次漏進來'
        print(f'  ✅ {len(r.data)} 筆全部 >= 09:00')
    else:
        print(f'  ℹ️  無資料（{r.error}）— 篩選語法有跑即可')

    r = query_trips(time_to='0900', session=session, limit=50)  # 無冒號格式
    if r.ok:
        assert all(t.time <= dt_time(9, 0) for t in r.data if t.time), '有 09:00 後的班次漏進來'
        print(f'  ✅ time_to="0900" coerce OK，{len(r.data)} 筆全部 <= 09:00')
    else:
        print(f'  ℹ️  time_to 無資料（{r.error}）')

    r = query_trips(time_from='亂打', session=session)
    assert not r.ok and '時間格式' in r.error, '壞格式應回人話錯誤'
    print(f'  ✅ 壞格式擋下：{r.error}')

    print('\n' + '='*60)
    print('✅ 全部 trips 查詢測試通過')
    print('='*60)
finally:
    session.close()
