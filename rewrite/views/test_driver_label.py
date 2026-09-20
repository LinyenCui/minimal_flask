"""
測試列表裡的司機編號要完整顯示（不被截成「28…」），且圖示留著

背景（2026-09-20 用戶回報，附截圖）：
    /診所班次 與 /昨天司機28530班次 的 carousel，司機欄顯示成
    「🚗53…」「🚗28…」—— 編號被截掉。用戶原話：
    「想辦法把司機編號全部顯示出來，**但不可以動到金額顯示**，
      看可否將車子的圖標改成字元較少的，或者是犧牲一點行程的版面，
      或是字再小一號？」

三條路只有兩條能走：
    · 字再小一號 → **辦不到**，size 已經是 xxs（Flex 最小的關鍵字級）
    · 圖標換小 / 拿掉 → 可行
    · 犧牲行程版面 → 路線 flex 讓一格給司機欄

⚠️ 第一版兩個一起做了 —— **做過頭**。光是讓一格司機欄就有 52px，
   帶圖示只需要 42px。用戶追問「看能否把車子圖示弄回來」才發現。
   所以現在是：路線讓一格（保留）＋ 圖示留著，並換成 🚕（小黃，同寬但黃色）。

金額欄從頭到尾一個字都沒動。

    T1  driver_label：圖示 + 完整編號，不截斷
    T2  版面預算：司機欄「配到的寬」要大於「需要的寬」，10 個真實編號逐一驗
    T3  現在態列表：司機欄完整、路線讓一格
    T4  過去態列表：司機欄完整，**金額欄的 flex/字級/粗體/對齊原封不動**
    T5  三個列表共用同一個 helper，圖示只有一種

純邏輯測試（自造 View 物件），不打 DB。
"""
import sys
from datetime import date, time as dt_time

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from rewrite.tools.trip import TripView
from rewrite.tools.completed_trip import CompletedTripView
from rewrite.views.trip_flex import driver_label, DRIVER_ICON, _trip_row
from rewrite.views.completed_trip_flex import _ct_row
from rewrite.views.trip_status_flex import _status_row


def banner(label):
    print(f'\n{"=" * 62}\n# {label}\n{"=" * 62}')


def ok(cond, label):
    print(f'  {"✅" if cond else "❌"} {label}')
    assert cond, label


# 生產實際存在的司機編號（最長 5 碼，就是被截掉的那些）
DRIVER_IDS = [533, 1117, 5386, 9999, 28530, 61153, 61353, 61367, 61379, 61553]

# ---- 版面預算模型（估算，用來擋「又把欄位改窄」的回歸）----
# carousel 的 bubble 是 kilo = 260px，body 預設左右 padding 各約 20px
BUBBLE_USABLE = 260 - 40
SPACING_XS = 4          # spacing:"xs" 每個間隙
W_DIGIT = 5.8           # xxs（約 11px 字）下一個數字的寬
W_CJK = 11.0            # 中文字約等於字級
W_EMOJI = 13.0          # emoji 約 2 個字寬


def text_width(s: str) -> float:
    total = 0.0
    for ch in s:
        if ord(ch) > 0x2500 and not ch.isdigit():
            total += W_EMOJI if ord(ch) > 0x1F000 else W_CJK
        else:
            total += W_DIGIT
    return total


def column_widths(row: dict) -> list:
    """回 [(text, 配到的寬)]，依 flex 比例分配（flex 0 = 依內容）"""
    cells = [c for c in row['contents'] if c.get('type') == 'text']
    fixed = sum(text_width(c['text']) for c in cells if c.get('flex') == 0)
    pool = BUBBLE_USABLE - fixed - SPACING_XS * (len(cells) - 1)
    total_flex = sum(c.get('flex', 1) for c in cells if c.get('flex') != 0)
    out = []
    for c in cells:
        f = c.get('flex', 1)
        out.append((c['text'],
                    text_width(c['text']) if f == 0 else pool * f / total_flex))
    return out


def cells(row: dict) -> list:
    return [c for c in row['contents'] if c.get('type') == 'text']


# ============================================================
banner('T1: driver_label —— 圖示 + 完整編號')
# ============================================================
ok(DRIVER_ICON == '🚕', f'圖示是計程車（小黃），不是轎車 → {DRIVER_ICON}')
for did in DRIVER_IDS:
    lab = driver_label(did)
    ok(lab == f'{DRIVER_ICON}{did}', f'{did} → {lab}')
ok(driver_label(None) == f'{DRIVER_ICON}?', '沒司機 → 圖示 + ?')
ok(driver_label(0) == f'{DRIVER_ICON}?', '0 當成沒司機（既有語意）')


def mk_trip(driver_id):
    return TripView(
        trip_id=5010, date=date(2026, 9, 18), time=dt_time(11, 10),
        start_point='仁和路', end_point='診所',
        category='診所', status='準備', driver_id=driver_id,
        meter_fare=220, extra_fare=0,
        display_status='準備', status_emoji='🟢', is_locked=False,
    )


def mk_ct(driver_id, *, meter=250, extra=0, mod=None):
    return CompletedTripView.from_row(type('R', (), {'_mapping': {
        'id': 4104, 'date': date(2026, 9, 17),
        'start_point': '東洋前門', 'end_point': '世平五街',
        'driver_id': driver_id, 'meter_fare': meter, 'extra_fare': extra,
        'category': '診所', 'passenger_leave_reason': None,
        'modification_reason': mod,
    }})())


# ============================================================
banner('T2: 版面預算 —— 司機欄放得下「圖示 + 5 碼編號」')
# ============================================================
# 這是本次修正的核心：欄位配到的寬必須 > 內容需要的寬。
# 改前司機欄 35px / 需要 42px → 差 7px，就是截圖裡被截掉的原因。
for label, builder, mk in [('現在態', _trip_row, mk_trip),
                           ('過去態', _ct_row, mk_ct)]:
    worst = None
    for did in DRIVER_IDS:
        row = builder(mk(did))
        got = dict(column_widths(row))[driver_label(did)]
        need = text_width(driver_label(did))
        if worst is None or got - need < worst[1]:
            worst = (did, got - need, got, need)
        ok(need <= got,
           f'{label} 司機 {did}：配到 {got:.0f}px ≥ 需要 {need:.0f}px')
    print(f'    → {label} 最吃緊的是 {worst[0]}，餘 {worst[1]:.0f}px'
          f'（{worst[2]:.0f} vs {worst[3]:.0f}）')
    ok(worst[1] >= 5, f'{label} 最小餘裕 ≥ 5px（模型有誤差，不能貼著邊）')


# ============================================================
banner('T3: 現在態列表（/診所班次）')
# ============================================================
row = _trip_row(mk_trip(28530))
texts = [c['text'] for c in cells(row)]
ok(f'{DRIVER_ICON}28530' in texts, f'司機欄 = 圖示 + 完整編號（實際 {texts}）')

by_text = {c['text']: c for c in cells(row)}
drv = by_text[f'{DRIVER_ICON}28530']
ok(drv['flex'] == 3, '司機欄 flex 2→3（多分到一格，這才是真正的修正）')
route = [c for c in cells(row) if '→' in c['text']][0]
ok(route['flex'] == 4, '路線欄 flex 5→4（讓出來的那一格）')
ok(drv['align'] == 'end' and drv['size'] == 'xxs',
   '對齊與字級沒變（xxs 已是最小，不能再小）')

# 編號欄的 # 目前還留著 —— 放得下就不動
idc = [c for c in cells(row) if c['text'].startswith('#')][0]
got = dict(column_widths(row))[idc['text']]
ok(text_width(idc['text']) <= got,
   f'編號「{idc["text"]}」放得下（需 {text_width(idc["text"]):.0f}px / '
   f'配到 {got:.0f}px）→ 還不必拿掉 #')


# ============================================================
banner('T4: 過去態列表 —— 金額欄不准動')
# ============================================================
row = _ct_row(mk_ct(28530))
texts = [c['text'] for c in cells(row)]
ok(f'{DRIVER_ICON}28530' in texts, f'司機欄完整（實際 {texts}）')

drv = [c for c in cells(row) if c['text'].startswith(DRIVER_ICON)][0]
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


# ============================================================
banner('T5: 三個列表共用 helper，圖示只有一種')
# ============================================================
import inspect

from rewrite.views import trip_flex as _tf
from rewrite.views import completed_trip_flex as _ctf
from rewrite.views import trip_status_flex as _tsf

for fn in (_tf._trip_row, _ctf._ct_row, _tsf._status_row):
    src = inspect.getsource(fn)
    ok('driver_label(' in src, f'{fn.__name__} 走共用 helper')
    ok('🚗' not in src and '🚕' not in src,
       f'{fn.__name__} 不自己拼圖示（圖示只能來自 DRIVER_ICON）')

ok(f'🚕' in _status_row(mk_trip(61379)).__str__(),
   '批次狀態列表也帶圖示（全站一致）')

# 分組統計卡不擠，但圖示要跟列表同一個常數（不要兩種車）
gsrc = inspect.getsource(_ctf.render_grouped_stat_card)
ok('DRIVER_ICON' in gsrc, '分組統計卡用 DRIVER_ICON 常數')
ok('🚗' not in gsrc, '分組統計卡沒有殘留的舊轎車圖示')

print('\n' + '=' * 62)
print('✅ 全部通過 — 圖示留著（小黃）、編號完整、金額欄原封不動')
print('=' * 62)
