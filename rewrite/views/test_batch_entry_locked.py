"""
測試批次狀態管理的入口按鈕要帶上 30 分鐘鎖內的班次

背景（2026-09-24 用戶回報，附截圖）：
    11:11 打「/今天診所班次」列出 17 筆，其中 #5139（11:30 診所→土城）
    點「⚙️ 對這批做狀態管理」後 LIFF 裡沒有 —— 同樣消失的還有 #5142、#5144（11:20）。

    原因：build_trip_list_batch_quick_reply 組 trip_ids 時把 30 分鐘鎖內的篩掉了。
    那條是批次表單「只能改狀態」時代寫的；後來加了**指派／撤銷指派**
    （allow_in_lock=True —— 快到點了才更需要派車），LIFF 端也已經會處理鎖內的列，
    只有入口沒跟著改，鎖內的班次連看都看不到。

    T1  批次入口：鎖內的「準備」要帶進去，已完成照樣不帶
    T2  全部都在鎖內 → 按鈕仍要出現（還能派車）
    T3  單筆入口仍篩鎖內（那張表單只有狀態類動作，鎖內全不能做）—— 兩邊別被改反
    T4  LIFF 端確實會安全處理鎖內的列（可勾但預設不勾、狀態類動作跳過、指派不看鎖）

純邏輯測試，不打 DB。
"""
import pathlib
import sys
from datetime import date, time as dt_time
from urllib.parse import parse_qs, urlparse, unquote

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from dotenv import load_dotenv
load_dotenv('/Users/linyancui/minimal_flask/.env')
load_dotenv('/Users/linyancui/minimal_flask/.env.dev', override=True)

from rewrite.tools.trip import TripView
from rewrite.views.trip_flex import (
    build_trip_list_batch_quick_reply, build_trip_quick_reply,
)


def banner(label):
    print(f'\n{"=" * 62}\n# {label}\n{"=" * 62}')


def ok(cond, label):
    print(f'  {"✅" if cond else "❌"} {label}')
    assert cond, label


def mk(tid, hhmm, *, status='準備', locked=False):
    h, m = map(int, hhmm.split(':'))
    return TripView(
        trip_id=tid, date=date(2026, 9, 24), time=dt_time(h, m),
        start_point='診所', end_point='土城', category='診所',
        status=status, driver_id=533, meter_fare=220, extra_fare=0,
        display_status=status, status_emoji='🟢', is_locked=locked,
    )


def ids_in(qr) -> list:
    """從 quick reply 的 LIFF uri 拆出 trip_ids"""
    uri = qr['items'][0]['action']['uri']
    q = parse_qs(urlparse(uri).query)
    raw = (q.get('trip_ids') or [''])[0]
    if not raw:                                    # liff.state 包一層的情況
        inner = unquote((q.get('liff.state') or [''])[0])
        raw = (parse_qs(urlparse(inner).query).get('trip_ids') or [''])[0]
    return [int(x) for x in unquote(raw).split(',') if x]


# 重現截圖：現在 11:11，鎖到 11:41
TRIPS = [
    mk(5138, '06:30', status='已完成'),
    mk(5145, '10:55', status='已完成'),
    mk(5142, '11:20', locked=True),
    mk(5144, '11:20', locked=True),
    mk(5139, '11:30', locked=True),     # ★ 用戶劃紅線的那筆
    mk(5135, '11:50'),
    mk(5136, '12:00'),
]

# ============================================================
banner('T1: 批次入口 —— 鎖內的準備要帶進去')
# ============================================================
qr = build_trip_list_batch_quick_reply(TRIPS)
ok(qr is not None, '有按鈕')
got = ids_in(qr)
print(f'    trip_ids = {got}')
ok(5139 in got, '★ #5139（11:30，鎖內）有帶進去')
ok(5142 in got and 5144 in got, '#5142 / #5144（11:20，鎖內）也有')
ok(5135 in got and 5136 in got, '鎖外的照樣有')
ok(5138 not in got and 5145 not in got, '已完成的仍然不帶（沒有任何動作能做）')

# ============================================================
banner('T2: 全部都在鎖內 → 按鈕仍要出現')
# ============================================================
qr2 = build_trip_list_batch_quick_reply([mk(1, '11:20', locked=True),
                                         mk(2, '11:30', locked=True)])
ok(qr2 is not None, '全鎖內仍有按鈕（快到點了才更需要派車）')
ok(ids_in(qr2) == [1, 2], f'兩筆都在 → {ids_in(qr2)}')
ok(build_trip_list_batch_quick_reply([mk(9, '06:30', status='已完成')]) is None,
   '全部已完成 → 沒按鈕')

# ============================================================
banner('T3: 單筆入口仍篩鎖內（兩邊別被改反）')
# ============================================================
ok(build_trip_quick_reply(mk(5139, '11:30', locked=True)) is None,
   '單筆「⚙️ 狀態管理」：鎖內不給（那張表單只有請假／註銷／衝突／改回準備）')
ok(build_trip_quick_reply(mk(5135, '11:50')) is not None,
   '單筆：鎖外照給')
single_form = pathlib.Path('/Users/linyancui/minimal_flask/templates/liff/'
                           'trip_status_form.html').read_text(encoding='utf-8')
ok('assign' not in single_form.split('const ACTION_LABEL')[1].split('};')[0],
   '單筆表單確實沒有指派選項 —— 哪天加了，單筆入口也要跟著放寬')

# ============================================================
banner('T4: LIFF 端安全處理鎖內的列')
# ============================================================
tpl = pathlib.Path('/Users/linyancui/minimal_flask/templates/liff/'
                   'trip_batch_status_form.html').read_text(encoding='utf-8')
ok("t.is_locked ? '' : 'checked'" in tpl,
   '鎖內的列可以勾、但預設不勾（不會被誤帶進狀態類動作）')
ok("t.is_locked ? '⏰' : ''" in tpl, '鎖內的列打 ⏰ 標記')
ok("t.display_status === '準備' && !t.is_locked" in tpl,
   '請假／註銷／衝突的筆數計算排除鎖內')
ok('刻意不看 is_locked' in tpl, '指派／撤銷的筆數計算不看鎖')
ok('locked && lockBlocks' in tpl, '送出時：狀態類動作遇鎖跳過，指派照送')

print('\n' + '=' * 62)
print('✅ 全部通過 — 批次入口帶上鎖內班次，LIFF 端會安全處理')
print('=' * 62)
