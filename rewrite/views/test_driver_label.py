"""
測試列表裡的司機編號要完整顯示（不被截成「28…」）

背景（2026-09-20 用戶回報，附截圖）：
    /診所班次 與 /昨天司機28530班次 的 carousel，司機欄顯示成
    「🚗53…」「🚗28…」—— 編號被截掉。用戶原話：
    「想辦法把司機編號全部顯示出來，**但不可以動到金額顯示**，
      看可否將車子的圖標改成字元較少的，或者是犧牲一點行程的版面，
      或是字再小一號？」

三個選項裡只有前兩個可行：
    · 字再小一號 → **辦不到**，size 已經是 xxs（Flex 最小的關鍵字級）
    · 圖標換小 → 直接拿掉最省：🚗 約佔 2 個字寬，而且每列都一樣、不帶資訊
    · 犧牲行程版面 → 路線 flex 讓 1 格給司機欄
所以做法 = 拿掉 🚗 ＋ 路線讓一格。金額欄一個字都沒動。

    T1  driver_label：純數字、沒有 emoji
    T2  現在態列表：司機欄完整、路線讓一格、金額欄不存在（這張沒有金額）
    T3  過去態列表：司機欄完整，**金額欄的 flex/字級/粗體/對齊全部原封不動**
    T4  批次狀態列表：同一個 helper（全站一致）
    T5  列表層不可以再出現 🚗（詳情卡、分組統計卡不在此限）

純邏輯測試（自造 View 物件），不打 DB。
"""
import sys
from datetime import date, time as dt_time

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from rewrite.tools.trip import TripView
from rewrite.tools.completed_trip import CompletedTripView
from rewrite.views.trip_flex import driver_label, _trip_row
from rewrite.views.completed_trip_flex import _ct_row
from rewrite.views.trip_status_flex import _status_row


def banner(label):
    print(f'\n{"=" * 62}\n# {label}\n{"=" * 62}')


def ok(cond, label):
    print(f'  {"✅" if cond else "❌"} {label}')
    assert cond, label


# 生產實際存在的司機編號（最長 5 碼，就是被截掉的那些）
DRIVER_IDS = [533, 1117, 5386, 9999, 28530, 61153, 61353, 61367, 61379, 61553]


def cells(row: dict) -> list:
    """取一列裡所有 text 元件"""
    return [c for c in row['contents'] if c.get('type') == 'text']


# ============================================================
banner('T1: driver_label —— 純數字，沒有 emoji')
# ============================================================
for did in DRIVER_IDS:
    lab = driver_label(did)
    ok(lab == str(did), f'{did} → {lab!r}（原樣，沒有截斷）')
    ok('🚗' not in lab, f'{did} 不帶 🚗')
ok(driver_label(None) == '?', '沒司機 → ?')
ok(driver_label(0) == '?', '0 當成沒司機（既有語意）')


def mk_trip(driver_id):
    return TripView(
        trip_id=5010, date=date(2026, 9, 18), time=dt_time(11, 10),
        start_point='仁和路', end_point='診所',
        category='診所', status='準備', driver_id=driver_id,
        meter_fare=220, extra_fare=0,
        display_status='準備', status_emoji='🟢', is_locked=False,
    )


# ============================================================
banner('T2: 現在態列表（/診所班次）')
# ============================================================
row = _trip_row(mk_trip(28530))
texts = [c['text'] for c in cells(row)]
ok('28530' in texts, f'司機欄是完整的 28530（實際 {texts}）')
ok(not any('🚗' in t for t in texts), '整列沒有 🚗')

by_text = {c['text']: c for c in cells(row)}
ok(by_text['28530']['flex'] == 3, '司機欄 flex 2→3（多分到一格）')
route = [c for c in cells(row) if '→' in c['text']][0]
ok(route['flex'] == 4, '路線欄 flex 5→4（讓出來的那一格）')
ok(by_text['28530']['align'] == 'end' and by_text['28530']['size'] == 'xxs',
   '對齊與字級沒變（xxs 已是最小，不能再小）')

for did in DRIVER_IDS:
    t = [c['text'] for c in cells(_trip_row(mk_trip(did)))]
    ok(str(did) in t, f'司機 {did} 完整顯示')


def mk_ct(driver_id, *, meter=250, extra=0, mod=None):
    return CompletedTripView.from_row(type('R', (), {'_mapping': {
        'id': 4104, 'date': date(2026, 9, 17),
        'start_point': '東洋前門', 'end_point': '世平五街',
        'driver_id': driver_id, 'meter_fare': meter, 'extra_fare': extra,
        'category': '診所', 'passenger_leave_reason': None,
        'modification_reason': mod,
    }})())


# ============================================================
banner('T3: 過去態列表（/昨天司機28530班次）—— 金額欄不准動')
# ============================================================
row = _ct_row(mk_ct(28530))
texts = [c['text'] for c in cells(row)]
ok('28530' in texts, f'司機欄完整（實際 {texts}）')
ok(not any('🚗' in t for t in texts), '整列沒有 🚗')

drv = [c for c in cells(row) if c['text'] == '28530'][0]
route = [c for c in cells(row) if '→' in c['text']][0]
fare = [c for c in cells(row) if c['text'] == '250'][0]
ok(drv['flex'] == 3, '司機欄 flex 2→3')
ok(route['flex'] == 5, '路線欄 flex 6→5（寬度從路線來，不是從金額來）')

# ★ 用戶的硬條件：金額顯示一個字都不能動
ok(fare['flex'] == 2, '金額欄 flex 仍是 2')
ok(fare['size'] == 'xxs', '金額欄字級仍是 xxs')
ok(fare['weight'] == 'bold', '金額欄仍是粗體')
ok(fare['align'] == 'end', '金額欄仍靠右')
ok(fare['text'] == '250', '金額文字沒變（沒有「元」，維持 2026-08 的決定）')

# 沖帳（淨額 0 但填過）仍顯示 0 而不是「未記錄」—— 別被這次改動弄壞
z = _ct_row(mk_ct(61553, meter=140, extra=-140,
                  mod='[1] 改車資: 加成 0→-140 (遲到自己騎車回)'))
zt = [c['text'] for c in cells(z)]
ok('0' in zt and '未記錄' not in zt, f'沖帳列仍顯示 0（實際 {zt}）')
ok('61553' in zt, '沖帳列的司機編號也完整')

for did in DRIVER_IDS:
    t = [c['text'] for c in cells(_ct_row(mk_ct(did)))]
    ok(str(did) in t, f'司機 {did} 完整顯示')


# ============================================================
banner('T4: 批次狀態列表 —— 用同一個 helper')
# ============================================================
srow = _status_row(mk_trip(61379))
_flat = str(srow)
ok('61379' in _flat, '司機編號完整')
ok('🚗' not in _flat, '沒有 🚗（全站一致，不會兩種寫法）')


# ============================================================
banner('T5: 列表層不可以再長回 🚗')
# ============================================================
import inspect
import re

from rewrite.views import trip_flex as _tf
from rewrite.views import completed_trip_flex as _ctf
from rewrite.views import trip_status_flex as _tsf

for fn in (_tf._trip_row, _ctf._ct_row, _tsf._status_row):
    src = inspect.getsource(fn)
    ok('🚗' not in src, f'{fn.__name__} 原始碼沒有 🚗')
    ok('driver_label(' in src, f'{fn.__name__} 走共用 helper，不自己拼字串')

# 分組統計卡那種不擠的地方保留 🚗 是刻意的 —— 確認它還在，別被一起掃掉
ok('🚗' in inspect.getsource(_ctf.render_grouped_stat_card),
   '分組統計卡仍保留 🚗（那邊不擠，有圖示比較好認）')

print('\n' + '=' * 62)
print('✅ 全部通過 — 司機編號完整顯示，金額欄原封不動')
print('=' * 62)
