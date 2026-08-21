"""
測試司機車資的「已填」判定 + 週車資的收錄範圍

背景（2026-08-05 用戶回報）：
    同一個司機、同一週、同一類別，LIFF 顯示 7,600 元、AI 加總顯示 8,070 元，
    差 470。查下來是兩個獨立的問題疊在一起：

    1. 週列表把「請假班次」整批排除，理由寫「司機沒跑」——但那是誤解。
       三層障眼法的請假是「同車某位乘客沒來，車照跑」：
         乘客欄「（廖貴7:30）→寶珠7:40 →診所7:45」→ 廖貴住院，寶珠照載
         所以錶價 200 照跳、加成 −95 只扣廖貴那份，司機實拿 105。
       PROD 全部 151 筆請假班次錶價都 > 0（85~450），沒有任何一筆是 0。
       排除 = 少算司機的錢（533 上週少 525，全歷史少 12,315）。

    2. 「已填」有兩套標準：待補清單用 _MISSING_FARE（含「改車資」豁免），
       週列表只寫 meter != 0。導致衝帳那筆（錶價被人工改成 0、加成 −55）
       不在待補清單、卻在週列表被當成待補，而且 −55 被靜默排除在合計外。

這支測試不碰 DB（純函數），本地 Postgres 沒開也跑得動。
DB 層的整合驗證在 test_driver.py。
"""
import sys

sys.path.insert(0, '/Users/linyancui/minimal_flask')

import inspect

from rewrite.tools.driver import is_fare_filled, query_driver_week_fares


def ok(cond, label):
    print(f'  {"✅" if cond else "❌"} {label}')
    assert cond, label


print('=' * 60)
print('# T1: is_fare_filled —— 必須跟待補清單 _MISSING_FARE 同語意')
print('=' * 60)

CASES = [
    # (錶價, 加成, 修改備註), 期望, 說明
    ((200, -95, None), True,
     '請假班次（錶價 200、加成 −95）→ 車有跑，算已填'),
    ((0, -55, '[1] 改車資: 錶價 220→0 (這樣才對)'), True,
     '衝帳：錶價被人工改成 0、只留 −55 加成'),
    ((0, 0, '[1] 改車資: 錶價 220→0'), True,
     '衝帳：錶價加成都 0，但有「改車資」紀錄 → 不該再叫司機補'),
    ((220, -220, '[1] 改車資: 加成 0→-220 (住院請假)'), True,
     '淨額 0 但錶價非 0 → 已填（顯示 0 元是對的）'),
    ((385, 50, None), True, '正常填好'),
    ((None, None, None), False, '真的沒填'),
    ((0, 0, None), False, '真的沒填（都 0、沒動過）'),
    ((0, None, ''), False, '真的沒填（空字串備註）'),
    ((None, 0, '指派司機 5386'), False,
     '有備註但不是「改車資」→ 仍算沒填'),
]
for (m, e, r), want, note in CASES:
    ok(is_fare_filled(m, e, r) is want, f'{note}')

print()
print('=' * 60)
print('# T2: 週車資列表要收請假班次（司機確實跑了）')
print('=' * 60)

src = inspect.getsource(query_driver_week_fares)
ok('_NOT_LEAVE' not in src,
   '週查詢不再用 _NOT_LEAVE 排除請假班次')
ok('modification_reason' in src,
   'SELECT 有撈 modification_reason（判定「已填」要用）')
ok('is_fare_filled(' in src,
   '用共用的 is_fare_filled，不再自己寫一套 meter != 0')
ok(src.count('is_fare_filled(') == 1,
   '判定只有一處（避免又長出第二套標準）')

# 待補清單則相反：請假班次不該叫司機補（老闆已經填好錶價了）
from rewrite.tools.driver import query_driver_pending_fares
psrc = inspect.getsource(query_driver_pending_fares)
ok('_NOT_LEAVE' in psrc,
   '待補清單仍排除請假班次（錶價老闆已填，不必勞煩司機）')
ok('_MISSING_FARE' in psrc,
   '待補清單仍用 _MISSING_FARE（含「改車資」豁免）')

print()
print('=' * 60)
print('# T3: 合計文案要跟著週次走')
print('=' * 60)
html = open('/Users/linyancui/minimal_flask/templates/liff/driver_fare_form.html').read()
ok('`${wname}合計 ' in html,
   '合計用 ${wname}（看上週就寫「上週合計」，不再寫死「本週合計」）')
ok('`本週合計 ' not in html,
   '沒有殘留寫死的「本週合計」')

print()
print('=' * 60)
print('# T4: 同一條規則的四個使用者必須同源（2026-08-20 沖帳被判未記錄）')
print('=' * 60)
import inspect as _ins

from rewrite.tools import fare_rules as _fr
from rewrite.tools import completed_trip as _ct
from rewrite.tools import query_spec as _qs
from rewrite.views import completed_trip_flex as _flex
from rewrite.tools import driver as _drv

# 沖帳：錶價 140 / 加成 −140 → 淨額 0，但備註有「改車資」→ 已填
ok(is_fare_filled(140, -140, '[1] 改車資: 加成 0→-140 (遲到自己騎車回)'),
   '沖帳（140/−140，備註有改車資）算已填')
ok(is_fare_filled(0, 0, '[1] 改車資: 錶價 220→0'), '錶價被抵成 0 但動過 → 已填')
ok(not is_fare_filled(0, 0, None), '真的沒填才是沒填')
ok(not is_fare_filled(None, None, '指派司機 5386'), '備註不是「改車資」→ 仍沒填')

# View 的 has_fare 要用共用判定，不能自己算「總額 > 0」
_vsrc = _ins.getsource(_ct.CompletedTripView.from_row)
ok('is_fare_filled(' in _vsrc, 'CompletedTripView.has_fare 用共用判定')
ok('> 0' not in _vsrc.split('has_fare')[1][:80],
   'has_fare 不再用「總額 > 0」')

# 查詢過濾與受護欄查詢層都吃同一份 SQL
ok('FILLED_SQL' in _ins.getsource(_ct._build_filters), '查詢過濾用 FILLED_SQL')
ok('MISSING_SQL' in _ins.getsource(_ct._build_filters), '反向過濾用 MISSING_SQL')
ok(_qs.ALLOWED_COLUMNS['has_fare'].sql == _fr.FILLED_SQL,
   'query_spec 的 has_fare 欄 = FILLED_SQL')
ok(_drv._MISSING_FARE == _fr.MISSING_SQL, '司機待補清單 = MISSING_SQL')

# 顯示層：0 元不可以再落到「未記錄」
ok('if ct.has_fare:' in _ins.getsource(_flex._ct_row),
   '列表用 has_fare 判斷，不是 `if ct.computed_total`（0 是 falsy）')

# SQL 兩份必須是嚴格反面，不可能各自漂移
ok(_fr.MISSING_SQL == f'NOT {_fr.FILLED_SQL}', 'MISSING_SQL 是 FILLED_SQL 的反面')
ok('%%' in _fr.FILLED_SQL, "SQL 裡的 % 有寫成 %%（text() 帶參數時 psycopg2 會炸）")

# 端到端：假一筆沖帳的 View，列表那格要顯示 0
_v = _ct.CompletedTripView.from_row(type('R', (), {'_mapping': {
    'id': 3524, 'meter_fare': 140, 'extra_fare': -140,
    'modification_reason': '[1] 改車資: 加成 0→-140 (遲到自己騎車回)',
    'start_point': '診所', 'end_point': '怡平路', 'passenger_leave_reason': None,
}})())
ok(_v.has_fare is True and _v.computed_total == 0, '沖帳 View：has_fare=True、淨額 0')
_cell = [c.get('text') for c in _flex._ct_row(_v)['contents']][-1]
ok(_cell == '0', f'列表顯示 0 而不是「未記錄」（實際 {_cell!r}）')

print('\n' + '=' * 60)
print('✅ 全部通過 — 車資判定規則單一來源（四個使用者同源）')
print('=' * 60)
