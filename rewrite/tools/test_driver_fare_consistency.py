"""
測試司機回報車資的兩張清單必須講同一件事

背景（2026-09-30 用戶回報，附截圖）：
    司機 28530 的「回報車資」LIFF，本週車資列表顯示
    「9/29 東洋後門 → 南紡購物中心　待補」，上面的待補清單卻說
    「沒有需要補車資的班次」—— 司機看得到待補、卻沒地方補。

    原因：query_driver_week_fares 用 modification_reason 判斷「填過沒」
    （改車資 豁免），但 SELECT 根本沒撈這一欄，d.get() 永遠是 None。
    待補清單走 SQL（MISSING_SQL）有撈，於是兩邊對 #4344
    （錶價 0 / 加成 0 / 「改車資: 錶價 360→0」）判定相反。

    舊測試只檢查 'modification_reason' in 原始碼 —— 被 d.get(...) 那個字騙過。
    這支改驗**不變量本身**：對每一筆非請假班次，
        週列表的 has_fare  ==  「不在待補清單裡」
    不管將來是漏欄位、改規則、還是加新條件造成分歧，都會在這裡紅。

    （請假班次刻意排除：待補清單本來就不收請假 —— 錶價由老闆填，不勞司機。）

全程 auto_commit=False + rollback，fixture 用今天日期 + 高位 id。
"""
import sys
from datetime import time as _time

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from dotenv import load_dotenv
load_dotenv('/Users/linyancui/minimal_flask/.env')
load_dotenv('/Users/linyancui/minimal_flask/.env.dev', override=True)

from sqlalchemy import text

from database import Session
from modules.utils.taiwan_time import get_taiwan_time
from rewrite.tools.driver import query_driver_pending_fares, query_driver_week_fares


def banner(label):
    print(f'\n{"=" * 62}\n# {label}\n{"=" * 62}')


def ok(cond, label):
    print(f'  {"✅" if cond else "❌"} {label}')
    assert cond, label


# 各種車資狀態（錶價, 加成, 修改紀錄, 說明）—— 全都是非請假
CASES = [
    (None, None, None,                                 '完全沒填'),
    (0,    0,    None,                                 '錶價加成都 0、沒動過'),
    (200,  0,    None,                                 '正常填好'),
    (0,    -55,  '[1] 改車資: 錶價 220→0 (這樣才對)',   '衝帳（錶價 0、加成非 0）'),
    (140,  -140, '[1] 改車資: 加成 0→-140 (遲到自己騎車回)', '沖帳（淨額 0）'),
    (0,    0,    '[1] 改路線: 終點 久保田家→南紡購物中心 (修改); [2] 改車資: 錶價 360→0',
                                                        '★ #4344：改路線後把錶價清成 0'),
]

today = get_taiwan_time().date()
s = Session()
try:
    drv = s.execute(text('SELECT id FROM drivers ORDER BY id LIMIT 1')).scalar()
    assert drv, '需要至少一位司機'

    fixture = {}      # (source, id) → 說明

    # ---- 過去態 completed_trips ----
    for i, (m, e, mod, note) in enumerate(CASES):
        cid = s.execute(text("""
            INSERT INTO completed_trips
                (date, start_point, end_point, meter_fare, extra_fare, category,
                 driver_id, unique_code, trip_type, passenger_leave_reason,
                 modification_reason)
            VALUES (:d, '測試起', '測試迄', :m, :e, '東洋', :drv, :code, 'temp',
                    NULL, :mod)
            RETURNING id
        """), {'d': today, 'm': m, 'e': e, 'drv': drv,
               'code': f'test_cons_c{i}', 'mod': mod}).scalar()
        fixture[('completed', cid)] = f'過去態 {note}'

    # ---- 現在態 trips（時間已過、還沒被排程掃成已完成）----
    for i, (m, e, mod, note) in enumerate(CASES):
        tid = 99870 + i
        s.execute(text("""
            INSERT INTO trips (trip_id, date, time, start_point, end_point, category,
                               driver_id, status, meter_fare, extra_fare,
                               trip_type, unique_code, week_number, fixed_trip_id,
                               modification_reason, passenger_leave_reason)
            VALUES (:id, :d, :t, '測試起', '測試迄', '東洋', :drv, '準備', :m, :e,
                    'temp', :code, :wk, NULL, :mod, NULL)
        """), {'id': tid, 'd': today, 't': _time(0, 1), 'drv': drv, 'm': m, 'e': e,
               'code': f'T_{tid}_{today.strftime("%Y%m%d")}',
               'wk': today.isocalendar()[1], 'mod': mod})
        fixture[('trip', tid)] = f'現在態 {note}'

    week = query_driver_week_fares(session=s, driver_id=drv, week_offset=0)
    pend = query_driver_pending_fares(session=s, driver_id=drv, days=1)
    ok(week.ok and pend.ok, '兩支查詢都成功')

    week_has = {(it['source'], it['id']): it['has_fare'] for it in week.data}
    pend_ids = {(it['source'], it['id']) for it in pend.data}

    # ========================================================
    banner('不變量：週列表的「已填」== 不在待補清單')
    # ========================================================
    for key, note in fixture.items():
        ok(key in week_has, f'{note}：有出現在週列表')
        filled = week_has[key]
        pending = key in pend_ids
        ok(filled != pending,
           f'{note}：週列表{"已填" if filled else "待補"}／'
           f'待補清單{"有" if pending else "沒有"} → '
           f'{"一致" if filled != pending else "★ 矛盾：看得到待補卻沒地方補"}')

    # ========================================================
    banner('#4344 那一種：兩邊講的是同一個答案')
    # ========================================================
    k4344 = [k for k, n in fixture.items() if '#4344' in n]
    answers = {(week_has[k], k in pend_ids) for k in k4344}
    ok(len(answers) == 1,
       f'現在態與過去態對這種班次的判定一致 → {answers}')

finally:
    s.rollback()
    s.close()

print('\n' + '=' * 62)
print('✅ 全部通過 — 週列表與待補清單對每一筆的判定一致')
print('=' * 62)
