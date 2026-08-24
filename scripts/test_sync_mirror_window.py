"""
測試同步的「鏡射窗口」規則 — 本地既要等於 Render，又要留住 Render 瘦身掉的歷史

背景（2026-08-24 用戶提出的兩難）：
  (a) 本地是拿來測試的 → Render 還有資料的那段期間，本地就該等於 Render，
      本地排程自己產生的測試殘留要清掉，不然兩邊數字對不起來
      （實際發生過：同一個查詢 PROD 42 筆、本地 40 筆）
  (b) 用戶打算定期把 Render 三～六個月前的資料刪掉幫 Render 瘦身
      → 那些歷史只剩本地有，**絕對不能因為「Render 沒有」就被當垃圾刪掉**

用戶原話：「完全鏡射好像又變得不可以了，很傷腦筋。」

解法是用時間切開，不需要任何設定：
    鏡射窗口 = Render 現存資料的最早日期（MIN(date)）之後
      · 窗口內：Render 是唯一真相 → 本地獨有的刪掉
      · 窗口外（更舊）：本地的歷史保存庫 → 一律不動
而且它會自己維護 —— Render 一瘦身，MIN(date) 往前移，本地那批舊資料
就自動落到窗口外受保護，不必記得改任何參數。

這支測純函數，不碰資料庫。
"""
import sys
from datetime import date

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from scripts.sync_from_render import classify_local_completed_row


def ok(cond, label):
    print(f'  {"✅" if cond else "❌"} {label}')
    assert cond, label


RENDER_MIN = date(2026, 3, 2)          # Render 現存最早日期
RENDER_CODES = {'20_217_32', '15_198_29'}
RENDER_IDS = {100, 200}


def verdict(**kw):
    base = dict(render_min_date=RENDER_MIN, render_codes=RENDER_CODES,
                render_ids=RENDER_IDS)
    base.update(kw)
    return classify_local_completed_row(**base)


print('=' * 62)
print('# T1: 窗口外（Render 已瘦身掉的期間）→ 一律保護')
print('=' * 62)
ok(verdict(row_date=date(2026, 1, 15), unique_code='99_1_1', row_id=999) == 'archive',
   'Render 沒見過的舊 code → archive（這就是瘦身後留在本地的歷史）')
ok(verdict(row_date=date(2026, 3, 1), unique_code=None, row_id=999) == 'archive',
   '早一天也算窗口外')
ok(verdict(row_date=date(2025, 12, 1), unique_code='20_217_32', row_id=1) == 'archive',
   '窗口外一律不動，連 code 對得上的也不碰')

print()
print('=' * 62)
print('# T2: 窗口內 → Render 是唯一真相')
print('=' * 62)
ok(verdict(row_date=RENDER_MIN, unique_code='20_217_32', row_id=1) == 'keep',
   '窗口起始日、code 在 Render → keep（同一趟，兩邊 id 不同也算已同步）')
ok(verdict(row_date=date(2026, 8, 7), unique_code='4_219_32', row_id=3455) == 'delete',
   'Render 沒見過的 code → delete（本地排程的測試殘留）')
ok(verdict(row_date=date(2026, 8, 7), unique_code=None, row_id=100) == 'keep',
   '無 code 但 id 在 Render → keep')
ok(verdict(row_date=date(2026, 8, 7), unique_code=None, row_id=99999) == 'delete',
   '無 code 且 id 不在 Render → delete')

print()
print('=' * 62)
print('# T3: 邊界與防呆')
print('=' * 62)
ok(verdict(row_date=None, unique_code='20_217_32', row_id=1) == 'keep',
   'date 是 NULL → 不當成窗口外（無法判斷就走一般規則）')
ok(verdict(row_date=None, unique_code='沒見過', row_id=1) == 'delete',
   'date NULL 且 code 沒見過 → 仍照一般規則刪')
ok(classify_local_completed_row(
       row_date=date(2020, 1, 1), unique_code='沒見過', row_id=1,
       render_min_date=None, render_codes=RENDER_CODES,
       render_ids=RENDER_IDS) == 'delete',
   'render_min_date 算不出來時不會誤判成 archive（呼叫端另有「Render 空就整個跳過」的防呆）')

print()
print('=' * 62)
print('# T4: 情境模擬 —— Render 瘦身之後，本地的歷史要活下來')
print('=' * 62)
# 現況：Render 2026-03-02 起；本地有 2026-01 的舊資料
before = verdict(row_date=date(2026, 1, 10), unique_code='old_1', row_id=50)
ok(before == 'archive', '瘦身前：本地 1 月的資料在窗口外 → 保護')
# 用戶把 Render 的 6 月前資料也刪掉 → MIN(date) 前移到 2026-06-01
after = classify_local_completed_row(
    row_date=date(2026, 4, 15), unique_code='apr_1', row_id=51,
    render_min_date=date(2026, 6, 1), render_codes=RENDER_CODES, render_ids=RENDER_IDS)
ok(after == 'archive',
   '瘦身後：4 月的資料自動落到窗口外 → 也受保護（不必改任何設定）')
still = classify_local_completed_row(
    row_date=date(2026, 8, 7), unique_code='沒見過', row_id=52,
    render_min_date=date(2026, 6, 1), render_codes=RENDER_CODES, render_ids=RENDER_IDS)
ok(still == 'delete', '瘦身後：窗口內的測試殘留照樣清掉')

print('\n' + '=' * 62)
print('✅ 全部通過 — 鏡射窗口：窗口內等於 Render，窗口外留住歷史')
print('=' * 62)
