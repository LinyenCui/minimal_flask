"""
測試 trip_flex carousel 拆頁邏輯（修同日 16 筆只顯示 13 + 「⋯ 還 3 筆」的 bug）

純邏輯測試（mock TripView），不打 DB。
"""
import sys
from datetime import date, time as dt_time

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from rewrite.tools.trip import TripView
from rewrite.views.trip_flex import (
    render_trip_list_carousel,
    PER_BUBBLE,
    MAX_BUBBLES,
)


def make_trip(trip_id: int, d: date, t: dt_time = dt_time(9, 0)) -> TripView:
    """造一個最小可用的 TripView"""
    return TripView(
        trip_id=trip_id, date=d, time=t,
        start_point='龍埔街', end_point='診所',
        category='診所', status='準備', driver_id=533,
        meter_fare=340, extra_fare=0,
        display_status='準備', status_emoji='🟢',
        is_locked=False,
    )


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


def assert_bubbles(carousel_or_bubble, expected_count):
    """從 result 取出 bubble 數，給 single bubble 也能驗"""
    if carousel_or_bubble.get('type') == 'carousel':
        return len(carousel_or_bubble['contents'])
    elif carousel_or_bubble.get('type') == 'bubble':
        return 1
    raise AssertionError(f'unexpected type: {carousel_or_bubble.get("type")}')


# ============================================================
# T1: 同日 13 筆 → 1 bubble（剛好滿頁，不拆）
# ============================================================
banner('T1: 同日 13 筆 → 1 bubble')
d1 = date(2026, 5, 2)
trips = [make_trip(i, d1) for i in range(1, 14)]
result = render_trip_list_carousel(trips)
n = assert_bubbles(result, 1)
assert n == 1, f'expected 1 bubble, got {n}'
# 1 bubble 的話 result 直接是 bubble 結構（不用 carousel 包）
assert result['type'] == 'bubble'
header_subtext = result['header']['contents'][1]['text']
assert header_subtext == '13 筆', f'header sub: {header_subtext!r}'
print(f'  ✅ 1 bubble，header sub = {header_subtext!r}')

# ============================================================
# T2: 同日 14 筆 → 2 bubbles（13 + 1，標頁數）
# ============================================================
banner('T2: 同日 14 筆 → 2 bubbles（page_info 1/2 + 2/2）')
trips = [make_trip(i, d1) for i in range(1, 15)]
result = render_trip_list_carousel(trips)
n = assert_bubbles(result, 2)
assert n == 2, f'expected 2 bubbles, got {n}'
b1, b2 = result['contents']
assert b1['header']['contents'][1]['text'] == '第 1/2 頁（共 14 筆）', \
    f'b1 sub: {b1["header"]["contents"][1]["text"]!r}'
assert b2['header']['contents'][1]['text'] == '第 2/2 頁（共 14 筆）'
# 第 1 張裝 13、第 2 張裝 1
assert len(b1['body']['contents']) == 13
assert len(b2['body']['contents']) == 1
print(f'  ✅ 2 bubbles, b1=13筆 b2=1筆, header 標頁數正確')

# ============================================================
# T3: 同日 16 筆 → 2 bubbles（13 + 3）— 用戶踩到的 bug
# ============================================================
banner('T3: 同日 16 筆 → 2 bubbles（13 + 3）— 修 LINE 上「⋯ 還 3 筆」bug')
trips = [make_trip(i, d1) for i in range(1, 17)]
result = render_trip_list_carousel(trips)
n = assert_bubbles(result, 2)
assert n == 2
b1, b2 = result['contents']
assert len(b1['body']['contents']) == 13
assert len(b2['body']['contents']) == 3
assert '第 1/2' in b1['header']['contents'][1]['text']
assert '第 2/2' in b2['header']['contents'][1]['text']
print(f'  ✅ 2 bubbles 取代「⋯ 還 3 筆」文字')

# ============================================================
# T4: 同日 27 筆 → 3 bubbles（13 + 13 + 1）
# ============================================================
banner('T4: 同日 27 筆 → 3 bubbles（13 + 13 + 1）')
trips = [make_trip(i, d1) for i in range(1, 28)]
result = render_trip_list_carousel(trips)
n = assert_bubbles(result, 3)
assert n == 3
b1, b2, b3 = result['contents']
assert len(b1['body']['contents']) == 13
assert len(b2['body']['contents']) == 13
assert len(b3['body']['contents']) == 1
for i, b in enumerate(result['contents'], 1):
    assert f'第 {i}/3' in b['header']['contents'][1]['text']
print(f'  ✅ 3 bubbles 拆頁正確')

# ============================================================
# T5: 跨 3 日各 5 筆 → 3 bubbles（按日分，不拆頁）
# ============================================================
banner('T5: 跨 3 日各 5 筆 → 3 bubbles')
trips = []
for delta in range(3):
    d = date(2026, 5, 2 + delta)
    trips.extend(make_trip(100 + delta * 10 + i, d) for i in range(5))
result = render_trip_list_carousel(trips)
n = assert_bubbles(result, 3)
assert n == 3
for b in result['contents']:
    sub = b['header']['contents'][1]['text']
    assert sub == '5 筆', f'sub={sub!r}'
print(f'  ✅ 3 bubbles 各 5 筆，無頁數標記（單頁）')

# ============================================================
# T6: 跨日 + 同日多筆混合（5/2 16筆 + 5/3 5筆 → 3 bubbles）
# ============================================================
banner('T6: 5/2 16 筆 + 5/3 5 筆 → 3 bubbles（13+3+5）')
trips = (
    [make_trip(i, date(2026, 5, 2)) for i in range(1, 17)] +
    [make_trip(i + 100, date(2026, 5, 3)) for i in range(1, 6)]
)
result = render_trip_list_carousel(trips)
n = assert_bubbles(result, 3)
assert n == 3
b1, b2, b3 = result['contents']
assert len(b1['body']['contents']) == 13
assert len(b2['body']['contents']) == 3
assert len(b3['body']['contents']) == 5
assert '第 1/2' in b1['header']['contents'][1]['text']
assert '第 2/2' in b2['header']['contents'][1]['text']
assert b3['header']['contents'][1]['text'] == '5 筆'  # 5/3 沒拆
print(f'  ✅ 5/2 拆 2 頁 + 5/3 單頁，共 3 bubbles')

# ============================================================
# T7: 超過 carousel 上限（14 天各 5 筆 = 14 bubbles → 截 11 + more_indicator）
# ============================================================
banner('T7: 超過 carousel 上限 → 截 11 + more_indicator')
trips = []
for delta in range(14):
    d = date(2026, 5, 1 + delta)
    trips.extend(make_trip(delta * 10 + i, d) for i in range(5))
result = render_trip_list_carousel(trips)
n = assert_bubbles(result, MAX_BUBBLES)
assert n == MAX_BUBBLES
# 最後一張是 more_indicator
last = result['contents'][-1]
last_text = last['body']['contents'][0]['text']
assert '還有' in last_text and '頁' in last_text, f'last bubble: {last_text!r}'
print(f'  ✅ 截 11 + more_indicator 訊息：{last_text!r}')

# ============================================================
# T8: 1 筆 → 直接詳情卡（不走 carousel）
# ============================================================
banner('T8: 1 筆 → 直接詳情卡')
trips = [make_trip(1, d1)]
result = render_trip_list_carousel(trips)
assert result['type'] == 'bubble'
# detail 卡有 header 標題 "🚖 班次 #1 詳情"
assert '詳情' in result['header']['contents'][0]['text']
print(f'  ✅ 1 筆走詳情卡')

# ============================================================
# 驗證所有 row 字體都是 xxs（除了 status_emoji 是 xs）
# ============================================================
banner('T9: row 字體驗證（xxs，除 emoji 是 xs）')
trips = [make_trip(1, d1)]
result = render_trip_list_carousel([trips[0], make_trip(2, d1)])
# carousel/bubble case 取 row
b = result['contents'][0] if result['type'] == 'carousel' else result
row = b['body']['contents'][0]
sizes = [c.get('size') for c in row['contents']]
print(f'  row 字體 sizes: {sizes}')
# emoji 是 xs，其餘是 xxs
assert sizes[0] == 'xs', f'emoji size: {sizes[0]}'
assert all(s == 'xxs' for s in sizes[1:]), f'其餘字體: {sizes[1:]}'
print(f'  ✅ 字體 xs/xxs 配置正確')

print('\n' + '='*60)
print('✅ 全部 9 個拆頁/字體測試通過')
print(f'   PER_BUBBLE={PER_BUBBLE}, MAX_BUBBLES={MAX_BUBBLES}')
print(f'   行字體：emoji=xs, 其餘=xxs（用戶要求縮小）')
print('='*60)
