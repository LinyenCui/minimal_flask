"""
測試 conversation_state 的過期 grace 期 + peek_recently_expired
（純 in-memory，無 DB / Flask；用縮小的 TTL / _GRACE 操縱時間）
"""
import sys
import time
from datetime import timedelta

sys.path.insert(0, '/Users/linyancui/minimal_flask')
import rewrite.conversation_state as cs


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


PASS = 0

def check(label, cond):
    global PASS
    assert cond, f'FAIL: {label}'
    PASS += 1
    print(f'  ✅ {label}')


# 縮小 grace 讓測試可等（原值 3 分鐘）
_ORIG_GRACE = cs._GRACE
cs._GRACE = timedelta(seconds=0.2)

TTL_TINY = 0.05 / 60  # 0.05 秒（ttl_minutes 單位）

try:
    # ============================================================
    # T1: 未過期 — get 有值、peek False
    # ============================================================
    banner('T1: active state')
    cs.set_state('U_alive', 'leave_input', {'trip_id': 1}, chat_id='G1')
    st = cs.get_state('U_alive')
    check('get_state 回 state', st is not None and st['type'] == 'leave_input')
    check('peek_recently_expired False（未過期）',
          cs.peek_recently_expired('U_alive', chat_id='G1') is False)
    cs.clear_state('U_alive')

    # ============================================================
    # T2: 過期在 grace 內 — get 回 None（語義不變）但 peek True
    # ============================================================
    banner('T2: expired within grace')
    cs.set_state('U_exp', 'sandbox_active', {}, ttl_minutes=TTL_TINY, chat_id='G1')
    time.sleep(0.08)  # 過 TTL，還在 grace（0.2s）內
    check('get_state 回 None（過期）', cs.get_state('U_exp') is None)
    check('get 後條目仍在（grace 內不刪）', 'U_exp' in cs._STATES)
    check('peek True（grace 內）', cs.peek_recently_expired('U_exp', chat_id='G1') is True)
    check('peek 不刪條目（純 peek）', 'U_exp' in cs._STATES)
    check('再 get 仍回 None', cs.get_state('U_exp') is None)

    # chat_id 比對
    check('peek False（不同 chat）',
          cs.peek_recently_expired('U_exp', chat_id='G2') is False)
    check('peek True（不給 chat_id 只看時間窗）',
          cs.peek_recently_expired('U_exp') is True)

    # webhook 提示後 clear_state 清標記 → 之後不再提示
    cs.clear_state('U_exp')
    check('clear 後 peek False（只提示一次）',
          cs.peek_recently_expired('U_exp', chat_id='G1') is False)

    # ============================================================
    # T3: 過 grace — peek False，get 真正清除
    # ============================================================
    banner('T3: past grace')
    cs.set_state('U_old', 'sandbox_active', {}, ttl_minutes=TTL_TINY, chat_id='G1')
    time.sleep(0.3)  # 過 TTL + grace
    check('peek False（超過 grace）',
          cs.peek_recently_expired('U_old', chat_id='G1') is False)
    check('get_state 回 None', cs.get_state('U_old') is None)
    check('get 後條目真正被清除', 'U_old' not in cs._STATES)

    # ============================================================
    # T4: sweep_expired — grace 內不掃，過 grace 才掃
    # ============================================================
    banner('T4: sweep respects grace')
    cs.set_state('U_sw', 'sandbox_active', {}, ttl_minutes=TTL_TINY, chat_id='G1')
    time.sleep(0.08)  # 過 TTL，grace 內
    cs.sweep_expired()
    check('sweep 不清 grace 內條目', 'U_sw' in cs._STATES)
    check('sweep 後 peek 仍 True', cs.peek_recently_expired('U_sw', chat_id='G1') is True)
    time.sleep(0.25)  # 過 grace
    cleaned = cs.sweep_expired()
    check('sweep 清掉過 grace 條目', 'U_sw' not in cs._STATES and cleaned >= 1)

    # ============================================================
    # T5: 沒有 state 的 user — peek False
    # ============================================================
    banner('T5: no state')
    check('peek False（無 state）', cs.peek_recently_expired('U_none') is False)

    print(f'\n全部通過：{PASS} 項檢查 ✅')
finally:
    cs._GRACE = _ORIG_GRACE
    for uid in ('U_alive', 'U_exp', 'U_old', 'U_sw'):
        cs.clear_state(uid)
