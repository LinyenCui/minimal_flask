"""
測試批量加成「遇零不加」

背景（2026-08-27 診所回報）：
    2026-08-24 豪雨停班停課批量 +50（診所類），打到一筆**整趟取消**的班次：
      診所→長溪路（珠發，單一乘客）錶 210，請假「住院」加成 −210 → 淨 0
      批量 +50 → 加成 −160、淨 50
    病患住院沒搭車，診所卻被收了 50 元。謝佩伶回報「煩請更正此費用」。

規則就一條：**車資 0 元的班次，批量加成不加。**
不是「請假就跳過」—— 請假不等於沒跑（見交接檔 3.1）：
    · 部分請假：2026-06-26 中華北路 錶200 / 加−95 / 淨105，
      廖貴住院但寶珠照搭，車在豪雨裡跑了 → +50 變 155 是**對的**
    · 整趟取消：加成把錶價抵成 0 → 淨額 0 → 不加
看的是加成前的淨額，不是請假欄。

    T1  ZERO_FARE_SQL 就是「淨額 = 0」，沒有別的條件
    T2  真實案例重演：整趟取消不加、部分請假照加
    T3  preview 與 execute 的筆數必須一致（預覽說幾筆就改幾筆）
    T4  全部都是 0 元班次時 → fail 且說明原因

全程 auto_commit=False + rollback，用 2035 年的假日期，不碰真資料。
"""
import sys
from datetime import date as _date

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from dotenv import load_dotenv
load_dotenv('/Users/linyancui/minimal_flask/.env')
load_dotenv('/Users/linyancui/minimal_flask/.env.dev', override=True)

from sqlalchemy import text

from database import Session
from rewrite.tools.batch_allowance import (
    ZERO_FARE_SQL, preview_batch_allowance, execute_batch_allowance,
)


def banner(label):
    print(f'\n{"=" * 62}\n# {label}\n{"=" * 62}')


def ok(cond, label):
    print(f'  {"✅" if cond else "❌"} {label}')
    assert cond, label


# ============================================================
banner('T1: 排除條件就是「淨額 = 0」，沒有別的')
# ============================================================
ok(ZERO_FARE_SQL == "COALESCE(meter_fare, 0) + COALESCE(extra_fare, 0) = 0",
   f'ZERO_FARE_SQL = 淨額 0（實際 {ZERO_FARE_SQL!r}）')
ok('%' not in ZERO_FARE_SQL,
   "沒有 %（有的話進 text() 帶參數會被 psycopg2 當佔位符）")

D = _date(2035, 3, 14)          # 假日期，遠離真資料
s = Session()
try:
    n_real = s.execute(text('SELECT COUNT(*) FROM completed_trips WHERE date = :d'),
                       {'d': D}).scalar()
    assert n_real == 0, f'{D} 不該有真班次（有 {n_real} 筆）'

    def seed(code, *, meter, extra, cat='診所', leave=None, mod=None):
        return s.execute(text("""
            INSERT INTO completed_trips
                (date, start_point, end_point, meter_fare, extra_fare, category,
                 driver_id, unique_code, trip_type, passenger_leave_reason,
                 modification_reason)
            VALUES (:d, '起', '迄', :m, :e, :c, NULL, :code, 'temp', :lv, :mod)
            RETURNING id
        """), {'d': D, 'm': meter, 'e': extra, 'c': cat, 'code': code,
               'lv': leave, 'mod': mod}).scalar()

    # 真實案例重演
    id_cancel = seed('t_zero_cancel', meter=210, extra=-210, leave='住院',
                     mod='[1] 乘客請假: 住院')            # 8/24 長溪路：整趟取消
    id_partial = seed('t_zero_partial', meter=200, extra=-95, leave='中華北路住院')
    #                                                      # 6/26 中華北路：部分請假
    id_normal = seed('t_zero_normal', meter=330, extra=0)  # 一般班次
    id_unfilled = seed('t_zero_unfilled', meter=None, extra=0)  # 司機還沒回報
    id_offset = seed('t_zero_offset', meter=140, extra=-140,
                     mod='[1] 改車資: 加成 0→-140 (遲到自己騎車回)')   # 沖帳

    # ========================================================
    banner('T2: 真實案例重演 — 誰該被加成')
    # ========================================================
    r = preview_batch_allowance(session=s, date_from=D, date_to=D, category='診所')
    ok(r.ok, f'preview 成功{"" if r.ok else "：" + (r.error or "")}')
    got = {t['id'] for t in r.data['preview']}
    ok(id_cancel not in got, '整趟取消（錶210/加−210/淨0）→ 不加 ★本次回報的案例')
    ok(id_offset not in got, '沖帳（140/−140/淨0）→ 不加')
    ok(id_unfilled not in got, '錶價還沒填（淨額也是 0）→ 不加（之後補加成再說）')
    ok(id_partial in got, '部分請假（錶200/加−95/淨105，車照跑）→ 照加成')
    ok(id_normal in got, '一般班次 → 照加成')
    ok(r.data['count'] == 2, f'會被加成 2 筆（實際 {r.data["count"]}）')
    ok(r.data['skipped_zero'] == 3, f'略過 3 筆（實際 {r.data["skipped_zero"]}）')
    ok(len(r.data['skipped_zero_preview']) == 3, '略過清單要給操作者看')
    ok(any('住院' in x for x in r.data['skipped_zero_preview']),
       f'清單帶得出請假原因：{r.data["skipped_zero_preview"]}')

    # ========================================================
    banner('T3: preview 說幾筆，execute 就改幾筆')
    # ========================================================
    before = {i: s.execute(text('SELECT extra_fare FROM completed_trips WHERE id=:i'),
                           {'i': i}).scalar()
              for i in (id_cancel, id_partial, id_normal, id_unfilled, id_offset)}

    r2 = execute_batch_allowance(session=s, date_from=D, date_to=D, category='診所',
                                 amount=50, reason='豪雨停班停課（測試）',
                                 user_name='test', auto_commit=False)
    ok(r2.ok, f'execute 成功{"" if r2.ok else "：" + (r2.error or "")}')
    ok(r2.data['updated_count'] == r.data['count'],
       f'執行筆數 {r2.data["updated_count"]} = 預覽筆數 {r.data["count"]}')
    ok(r2.data['skipped_zero'] == r.data['skipped_zero'],
       '略過筆數兩邊一致')

    after = {i: s.execute(text('SELECT extra_fare FROM completed_trips WHERE id=:i'),
                          {'i': i}).scalar()
             for i in before}
    ok(after[id_cancel] == before[id_cancel] == -210,
       f'整趟取消那筆一動也沒動（仍 {after[id_cancel]}，不是 −160）★回報案例已修')
    ok(after[id_offset] == before[id_offset] == -140, '沖帳那筆沒動')
    ok(after[id_unfilled] == before[id_unfilled] == 0, '錶價還沒填的那筆沒動')
    ok(after[id_partial] == -45, f'部分請假 −95 → {after[id_partial]}（+50，車有跑）')
    ok(after[id_normal] == 50, f'一般班次 0 → {after[id_normal]}')

    _mod = s.execute(text('SELECT modification_reason FROM completed_trips WHERE id=:i'),
                     {'i': id_cancel}).scalar()
    ok('豪雨' not in (_mod or ''),
       f'被略過的班次連 modification_reason 都不該被寫（{_mod!r}）')

    # ========================================================
    banner('T4: 整批都是 0 元班次 → fail 並說明')
    # ========================================================
    s.execute(text("DELETE FROM completed_trips WHERE date=:d AND id <> :keep"),
              {'d': D, 'keep': id_cancel})
    r3 = execute_batch_allowance(session=s, date_from=D, date_to=D, category='診所',
                                 amount=50, reason='測試', user_name='test',
                                 auto_commit=False)
    ok(not r3.ok, '沒有可加成的班次 → fail')
    ok('車資 0 元' in (r3.error or ''),
       f'錯誤訊息要說明為什麼是 0 筆：{r3.error!r}')

finally:
    s.rollback()
    s.close()

print('\n' + '=' * 62)
print('✅ 全部通過 — 遇零不加：車資 0 元的班次，批量加成不加')
print('=' * 62)
