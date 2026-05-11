"""
車資試算 atomic tool 回歸測試。

跑法：
  venv/bin/python rewrite/tools/test_fare_calc.py
"""
import sys
import os
from dotenv import load_dotenv
load_dotenv()

# 從 rewrite/tools/test_fare_calc.py 算到 repo root（不寫死路徑，worktree 也能跑）
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, _REPO_ROOT)

from rewrite.tools.fare_calc import (
    calculate_fare,
    format_text,
    parse_command,
)


def banner(label: str):
    print(f'\n{"=" * 60}\n# {label}\n{"=" * 60}')


# ============================================================
# T1: 起跳距離內（1.0 km）→ 只收基礎
# ============================================================
banner('T1: 起跳距離內 distance=1.0 km')
r = calculate_fare(distance_km=1.0)
assert r.ok, r.error
d = r.data
assert d['breakdown']['base_fare'] == 85, d
assert d['breakdown']['distance_part'] == 0, d
assert d['breakdown']['waiting_part'] == 0, d
assert d['breakdown']['night_extra'] == 0, d
assert d['total'] == 85, d
print(f'  ✅ total={d["total"]} breakdown={d["breakdown"]}')


# ============================================================
# T2: 跨多跳 + 停等 + 日間
#   distance=10 km → extra 8.75 km → ceil(8750/200)=44 跳 → 220
#   waiting=5 分 → 300 秒 // 100 = 3 跳 → 15
#   subtotal = 85+220+15 = 320，4 捨 5 入到 5 元 → 320
# ============================================================
banner('T2: distance=10 km, waiting=5, 日間')
r = calculate_fare(distance_km=10, waiting_min=5, period='日間')
assert r.ok, r.error
d = r.data
assert d['breakdown']['base_fare'] == 85
assert d['breakdown']['distance_part'] == 220, d
assert d['breakdown']['waiting_part'] == 15, d
assert d['breakdown']['night_extra'] == 0
assert d['total'] == 320, d
print(f'  ✅ total={d["total"]} breakdown={d["breakdown"]}')


# ============================================================
# T3: 夜間 1.2 倍
#   同 T2 但夜間：subtotal=320 → night_extra=int(320*0.2)=64
#   running = 320+64 = 384 → 4 捨 5 入 → 385
# ============================================================
banner('T3: distance=10 km, waiting=5, 夜間')
r = calculate_fare(distance_km=10, waiting_min=5, period='夜間')
assert r.ok, r.error
d = r.data
assert d['breakdown']['night_extra'] == 64, d
assert d['total'] == 385, d
print(f'  ✅ total={d["total"]} night_extra={d["breakdown"]["night_extra"]}')


# ============================================================
# T4: str 參數 coerce（CLAUDE.md 規範）
# ============================================================
banner('T4: str 參數 coerce')
r = calculate_fare(distance_km='10', waiting_min='5', period='日間')
assert r.ok, r.error
assert r.data['total'] == 320, r.data
print(f'  ✅ str→numeric coerce OK total={r.data["total"]}')


# ============================================================
# T5: 負數 / 不合法
# ============================================================
banner('T5: 邊界 — 負數 / 不合法 period')
r = calculate_fare(distance_km=-1)
assert not r.ok and '負' in r.error, r
print(f'  ✅ distance_km<0 → fail: {r.error}')

r = calculate_fare(distance_km=5, waiting_min=-2)
assert not r.ok and '負' in r.error, r
print(f'  ✅ waiting_min<0 → fail: {r.error}')

r = calculate_fare(distance_km=5, period='中午')
assert not r.ok, r
print(f'  ✅ 不合法 period → fail: {r.error}')

r = calculate_fare(distance_km='abc')
assert not r.ok, r
print(f'  ✅ 非數字 distance → fail: {r.error}')


# ============================================================
# T6: parse_command — 含全形 / 前綴 / 大小寫
# ============================================================
banner('T6: parse_command 解析用戶輸入')

r = parse_command('車資試算 8.5')
assert r.ok and r.data == {'distance_km': 8.5, 'waiting_min': 0, 'period': '日間'}, r
print(f'  ✅ 「車資試算 8.5」→ {r.data}')

r = parse_command('車資試算 10 5 夜間')
assert r.ok and r.data['period'] == '夜間' and r.data['waiting_min'] == 5, r
print(f'  ✅ 「車資試算 10 5 夜間」→ {r.data}')

r = parse_command('/車資試算 ５ ３ 日間')  # 全形數字
assert r.ok and r.data == {'distance_km': 5.0, 'waiting_min': 3, 'period': '日間'}, r
print(f'  ✅ 全形數字 / 前綴 OK → {r.data}')

r = parse_command('#車資試算 １０．５')  # 全形小數點
assert r.ok and r.data['distance_km'] == 10.5, r
print(f'  ✅ 全形小數點 OK → {r.data}')

r = parse_command('車資試算')
assert not r.ok, r
print(f'  ✅ 沒給距離 → fail: {r.error}')

r = parse_command('車資試算 abc')
assert not r.ok, r
print(f'  ✅ 不合法輸入 → fail: {r.error}')


# ============================================================
# T7: format_text 渲染
# ============================================================
banner('T7: format_text')
r = calculate_fare(distance_km=10, waiting_min=5, period='夜間')
txt = format_text(r.data)
print(txt)
assert '台南車資試算' in txt
assert '385' in txt
assert '夜間' in txt
print(f'  ✅ format_text 含預期字串')


print('\n' + '=' * 60)
print('# ✅ All tests passed')
print('=' * 60)
