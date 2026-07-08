"""
測試 LIFF customer handler 的「多筆/單筆相容」payload 解析（純函數，不打 LINE API、不碰 DB）

涵蓋：
  - _extract_customer_items：新版 {customers:[...]} / 舊版單筆 body 相容 / 格式錯誤
  - _item_label：簡稱 → 姓名 → 第 N 位 fallback
  - _parse_payload：批次逐筆沿用同一個解析（空字串轉 None、birthday 轉 date）
"""
import sys
from datetime import date

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from rewrite.handlers.liff.customer import (  # noqa: E402
    _BATCH_MAX,
    _extract_customer_items,
    _item_label,
    _parse_payload,
)


def banner(label: str):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


# ============================================================
# T1: 新版多筆格式
# ============================================================
banner('T1: {customers: [...]} → is_batch=True，逐筆原樣')
body = {
    'customers': [
        {'name': '陳阿姨', 'short_name': '陳阿姨', 'address': '三峽'},
        {'name': '王伯伯', 'short_name': '王伯伯', 'address': '鶯歌'},
    ],
    'source': {'type': 'group', 'groupId': 'C' + 'a' * 32},
}
items, is_batch, err = _extract_customer_items(body)
assert err is None, f'unexpected err: {err}'
assert is_batch is True
assert len(items) == 2
assert items[0]['name'] == '陳阿姨'
assert items[1]['short_name'] == '王伯伯'
print(f'  ok: {len(items)} items, is_batch={is_batch}')

# ============================================================
# T2: 舊版單筆格式（LINE 快取頁）→ 包成 1 筆、is_batch=False
# ============================================================
banner('T2: 舊單筆 body → ([body], False, None)')
old_body = {'name': '太子龍', 'short_name': '太子龍', 'address': '三峽',
            'source': {'type': 'group', 'groupId': 'C' + 'b' * 32}}
items, is_batch, err = _extract_customer_items(old_body)
assert err is None
assert is_batch is False
assert len(items) == 1
assert items[0] is old_body  # 原樣傳回，單筆路徑行為不變
print('  ok: 舊格式走單筆路徑')

# ============================================================
# T3: customers 格式錯誤
# ============================================================
banner('T3: customers 非清單 / 空清單 / 含非物件 / 超過上限 → err')
for bad, why in [
    ({'customers': 'not-a-list'}, '非清單'),
    ({'customers': []}, '空清單'),
    ({'customers': None}, 'None'),
    ({'customers': [{'name': 'x'}, 'oops']}, '含非物件'),
    ({'customers': [{}] * (_BATCH_MAX + 1)}, '超過上限'),
]:
    items, is_batch, err = _extract_customer_items(bad)
    assert err is not None, f'{why} 應該要報錯'
    assert is_batch is True
    assert items == []
    print(f'  {why}: {err}')

# ============================================================
# T4: _item_label fallback 順序
# ============================================================
banner('T4: _item_label 簡稱 → 姓名 → 第 N 位')
assert _item_label({'short_name': '陳阿姨', 'name': '陳美麗'}, 0) == '陳阿姨'
assert _item_label({'short_name': '  ', 'name': '陳美麗'}, 0) == '陳美麗'
assert _item_label({'short_name': '', 'name': None}, 2) == '第 3 位'
assert _item_label({}, 0) == '第 1 位'
print('  ok: 4 cases')

# ============================================================
# T5: _parse_payload 批次逐筆沿用（空字串轉 None、birthday 轉 date、錯誤回訊息）
# ============================================================
banner('T5: _parse_payload 空字串→None、birthday→date、格式錯→err')
fields, err = _parse_payload({'name': ' 陳阿姨 ', 'short_name': '陳阿姨',
                              'address': '三峽', 'category': '',
                              'birthday': '1950-03-15', 'gender': ''})
assert err is None
assert fields['name'] == '陳阿姨'
assert fields['category'] is None
assert fields['gender'] is None
assert fields['birthday'] == date(1950, 3, 15)

fields, err = _parse_payload({'name': 'x', 'birthday': '03/15'})
assert err is not None and 'birthday' in err
print(f'  ok: birthday 格式錯 → {err}')

print(f'\n{"="*60}\n全部通過 ✅\n{"="*60}')
