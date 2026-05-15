"""
日期計算 atomic tool 回歸測試。

跑法：
  venv/bin/python rewrite/tools/test_date_calc.py
"""
import sys
import os
from datetime import date, timedelta
from dotenv import load_dotenv
load_dotenv()

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, _REPO_ROOT)

from rewrite.tools.date_calc import (
    calculate,
    parse_command,
    is_date_calc_command,
    format_text,
    format_date_full,
    _cn_to_int,
    _normalize_input,
)


def banner(label: str):
    print(f'\n{"=" * 60}\n# {label}\n{"=" * 60}')


# ============================================================
# T1: parse_command — 半形括號
# ============================================================
banner('T1: parse_command 半形括號')
r = parse_command('(5/14)')
assert r.ok and r.data == {'date_str': '5/14'}, r
print(f'  ✅ (5/14) → {r.data}')

r = parse_command('  (5/14)  ')
assert r.ok and r.data['date_str'] == '5/14', r
print(f'  ✅ 兩端空白 OK')

r = parse_command('( 5/14 )')
assert r.ok and r.data['date_str'] == '5/14', r
print(f'  ✅ 括號內空白 OK → {r.data}')


# ============================================================
# T2: parse_command — 全形括號
# ============================================================
banner('T2: parse_command 全形括號')
r = parse_command('（5/14）')
assert r.ok and r.data['date_str'] == '5/14', r
print(f'  ✅ （5/14）→ {r.data}')

r = parse_command('（五月二十日）')
assert r.ok and r.data['date_str'] == '五月二十日', r
print(f'  ✅ （五月二十日）→ {r.data}')


# ============================================================
# T3: parse_command — 失敗
# ============================================================
banner('T3: parse_command 失敗')
for bad in ['abc', '5/14', '(5/14)abc', 'abc(5/14)', '()', '（）', '(  )']:
    r = parse_command(bad)
    assert not r.ok, f'{bad!r} should fail but got ok'
print(f'  ✅ 各種非法輸入都 fail')


# ============================================================
# T4: is_date_calc_command
# ============================================================
banner('T4: is_date_calc_command')
for good in ['(5/14)', '（5/14）', '(05-20)', '(2026-5-14)', '(五月二十日)', '  (5/14)  ']:
    assert is_date_calc_command(good), f'{good!r} should be True'
for bad in ['', '5/14', 'abc', '(abc', 'abc)', '()', '車資試算 10', '(這是)備註(也是)']:
    assert not is_date_calc_command(bad), f'{bad!r} should be False'
print(f'  ✅ regex 行為正確')


# ============================================================
# T5: 中文數字 _cn_to_int
# ============================================================
banner('T5: 中文數字 _cn_to_int')
cases = {
    '一': 1, '二': 2, '九': 9, '十': 10, '十一': 11, '十九': 19,
    '二十': 20, '二十一': 21, '三十': 30, '三十一': 31,
}
for cn, expected in cases.items():
    got = _cn_to_int(cn)
    assert got == expected, f'{cn} → {got}, expected {expected}'
assert _cn_to_int('甲') is None
assert _cn_to_int('') is None
assert _cn_to_int(None) is None
print(f'  ✅ 中文數字解析 OK（含 None / 非中文）')


# ============================================================
# T6: _normalize_input — 預處理規則
# ============================================================
banner('T6: _normalize_input 預處理')
assert _normalize_input('五月二十日') == '5/20'
assert _normalize_input('五月二十') == '5/20'        # 缺尾「日」
assert _normalize_input('五月二十號') == '5/20'      # 「號」也認
assert _normalize_input('十二月三十一日') == '12/31'
assert _normalize_input('2026/5/14') == '2026-5-14'  # 斜線含年 → 短橫線
assert _normalize_input('5/14') == '5/14'             # 不變
assert _normalize_input('2026-5-14') == '2026-5-14'   # 不變
assert _normalize_input('5月14日') == '5/14'          # 阿拉伯月日也統一吃 M/D
assert _normalize_input('5月14') == '5/14'            # 阿拉伯缺尾
assert _normalize_input('5月14號') == '5/14'          # 阿拉伯 + 「號」
print(f'  ✅ 預處理規則正確')


# ============================================================
# T7: calculate — MM/DD（短日期）
# ============================================================
banner('T7: calculate (5/14) → +7/+77/+84')
r = calculate(date_str='5/14')
assert r.ok, r.error
d = r.data
assert d['base'].month == 5 and d['base'].day == 14
assert d['next_week'] == d['base'] + timedelta(days=7)
assert d['week11'] == d['base'] + timedelta(days=77)
assert d['week12'] == d['base'] + timedelta(days=84)
print(f'  ✅ base={d["base"]} +7={d["next_week"]} +77={d["week11"]} +84={d["week12"]}')


# ============================================================
# T8: calculate — MM-DD（短橫線）
# ============================================================
banner('T8: calculate (05-20)')
r = calculate(date_str='05-20')
assert r.ok, r.error
assert r.data['base'].month == 5 and r.data['base'].day == 20
print(f'  ✅ 05-20 → base={r.data["base"]}')


# ============================================================
# T9: calculate — 含年 YYYY-M-D
# ============================================================
banner('T9: calculate (2026-5-14)')
r = calculate(date_str='2026-5-14')
assert r.ok
assert r.data['base'] == date(2026, 5, 14)
assert r.data['week11'] == date(2026, 7, 30)
assert r.data['week12'] == date(2026, 8, 6)
print(f'  ✅ 2026-5-14 → 11週=7/30 12週=8/6')


# ============================================================
# T10: calculate — 含年 YYYY/M/D（預處理）
# ============================================================
banner('T10: calculate (2026/5/14) 預處理')
r = calculate(date_str='2026/5/14')
assert r.ok, r.error
assert r.data['base'] == date(2026, 5, 14)
print(f'  ✅ 2026/5/14 normalize OK')


# ============================================================
# T11: calculate — 中文格式
# ============================================================
banner('T11: calculate 中文 (五月二十日)')
r = calculate(date_str='五月二十日')
assert r.ok, r.error
assert r.data['base'].month == 5 and r.data['base'].day == 20
print(f'  ✅ 五月二十日 → {r.data["base"]}')

r = calculate(date_str='十二月三十一')  # 缺尾
assert r.ok, r.error
assert r.data['base'].month == 12 and r.data['base'].day == 31
print(f'  ✅ 十二月三十一（缺尾）→ {r.data["base"]}')

r = calculate(date_str='十一月一日')
assert r.ok, r.error
assert r.data['base'].month == 11 and r.data['base'].day == 1
print(f'  ✅ 十一月一日 → {r.data["base"]}')


# ============================================================
# T12: calculate — 跨年（+77/+84 推進到次年）
# ============================================================
banner('T12: calculate 跨年 (2025-12-15)')
r = calculate(date_str='2025-12-15')
assert r.ok
base = r.data['base']
assert base == date(2025, 12, 15)
assert r.data['week11'] == base + timedelta(days=77)
assert r.data['week11'].year == 2026
print(f'  ✅ 2025-12-15 +77 = {r.data["week11"]}')


# ============================================================
# T13: calculate — 閏年 2028-2-29
# ============================================================
banner('T13: calculate 閏年 (2028-2-29)')
r = calculate(date_str='2028-2-29')
assert r.ok, r.error
assert r.data['base'] == date(2028, 2, 29)
print(f'  ✅ 閏年 2028-2-29 OK')


# ============================================================
# T14: calculate — 失敗 case
# ============================================================
banner('T14: calculate 失敗')
for bad in ['abc', '', '13/40', '0/0', '五月卅日']:  # 「卅」不支援
    r = calculate(date_str=bad)
    assert not r.ok, f'{bad!r} should fail'
    print(f'  ✅ {bad!r} → fail: {r.error[:50]}')


# ============================================================
# T15: format_text + format_date_full
# ============================================================
banner('T15: format_text + format_date_full')
r = calculate(date_str='2026-5-14')
txt = format_text(r.data)
print(txt)
assert '2026 年 05 月 14 日' in txt
assert '星期' in txt
assert '抽血' in txt
assert '回診' in txt

# format_date_full 直接驗
d = date(2026, 5, 14)  # 星期四
s = format_date_full(d)
assert s == '2026 年 05 月 14 日 星期四', s
print(f'  ✅ format_date_full({d}) = {s!r}')


# ============================================================
# T16: parse_command + calculate 端到端
# ============================================================
banner('T16: 端到端 (五月二十日)')
p = parse_command('(五月二十日)')
assert p.ok, p.error
r = calculate(**p.data)
assert r.ok, r.error
assert r.data['base'].month == 5 and r.data['base'].day == 20
print(f'  ✅ (五月二十日) → base={r.data["base"]} +77={r.data["week11"]}')


# ============================================================
# T17: 短日期強制當年（醫療回診語境）
#   parser 的「>180 天往前推 1 年」邏輯對日期計算外掛不對。
#   12/30 在 5/15 打時 parser 推 2025/12/30，但用戶語意是今年。
# ============================================================
banner('T17: 短日期強制當年')
from modules.utils.taiwan_time import get_taiwan_date
this_year = get_taiwan_date().year

for inp in ['12/30', '12-30', '十二月三十日', '12月30日', '12月30']:
    r = calculate(date_str=inp)
    assert r.ok, r.error
    assert r.data['base'].year == this_year, \
        f'{inp!r} expected year={this_year} got {r.data["base"]}'
    assert r.data['base'].month == 12 and r.data['base'].day == 30
    print(f'  ✅ {inp!r} → {r.data["base"]}（強制當年）')

# 含年明示 — 不受強制當年影響
r = calculate(date_str='2025-12-30')
assert r.ok and r.data['base'] == date(2025, 12, 30)
print(f'  ✅ 含年明示 2025-12-30 → {r.data["base"]}（保持原年）')

r = calculate(date_str='2027-3-15')
assert r.ok and r.data['base'] == date(2027, 3, 15)
print(f'  ✅ 含年明示 2027-3-15 → {r.data["base"]}（保持原年）')


print('\n' + '=' * 60)
print('# ✅ All tests passed')
print('=' * 60)
