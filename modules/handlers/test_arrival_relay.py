"""
測試 到院通知接送群（arrival_relay_handler）

不打 LINE API — push / reply 全部 mock；Timer 不真跑，直接呼叫 _nag 驗狀態機。
DB 部分用本地 DB + 測試專用 chat_id，跑完清理。

跑法：source venv/bin/activate && python modules/handlers/test_arrival_relay.py
"""
import sys
import re
import time
import logging
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')

# 抑制大部分 INFO log
logging.getLogger().setLevel(logging.WARNING)
for noisy in ('apscheduler', 'sqlalchemy', 'modules', 'rewrite'):
    logging.getLogger(noisy).setLevel(logging.ERROR)

import modules.handlers.arrival_relay_handler as arh

# ============================================================
# mock LINE 出口（不打 API）
# ============================================================
SENT = []  # (kind, target_or_token, text)


def _fake_push(chat_id, text):
    SENT.append(('push', chat_id, text))


def _fake_reply_text(token, text):
    SENT.append(('reply', token, text))
    return True


def _fake_reply_message(token, messages):
    texts = [getattr(m, 'text', str(m)) for m in messages]
    SENT.append(('reply_msg', token, ' | '.join(texts)))
    return True


arh._push_to_relay = _fake_push
arh.reply_text = _fake_reply_text
arh.reply_message = _fake_reply_message
arh._schedule_nag = lambda chat_id: None  # 不開真 Timer；催促用 _nag 直呼驗證


# ============================================================
# 測試框架（極簡）
# ============================================================
FAILS = []


def banner(label):
    print(f'\n{"=" * 60}\n# {label}\n{"=" * 60}')


def check(label, cond):
    mark = '✅' if cond else '❌'
    print(f'  {mark} {label}')
    if not cond:
        FAILS.append(label)


def push_count():
    return len([s for s in SENT if s[0] == 'push'])


# ============================================================
# T1: 配對碼 生成 / 驗證 / 一次性 / TTL
# ============================================================
banner('T1: 配對碼生成 / 驗證 / TTL')
code = arh._gen_pair_code('W_TEST')
check('4 位數字碼', len(code) == 4 and code.isdigit())
check('驗碼取回工作群', arh._pop_valid_code(code) == 'W_TEST')
check('一次性（取走即失效）', arh._pop_valid_code(code) is None)
code2 = arh._gen_pair_code('W_TEST')
arh._PAIR_CODES[code2]['expires_at'] = time.time() - 1  # 模擬過期
check('TTL 過期 → None', arh._pop_valid_code(code2) is None)
check('亂碼 → None', arh._pop_valid_code('zzzz') is None)

# ============================================================
# T2: 事件節流（20 分鐘窗）
# ============================================================
banner('T2: 事件節流（20 分鐘窗）')
arh._EVENTS.clear()
check('第一次建立 → True', arh.start_arrival_event('R_TEST') is True)
check('窗內再建 → False（節流）', arh.start_arrival_event('R_TEST') is False)
arh._EVENTS['R_TEST']['started_at'] -= (arh.EVENT_THROTTLE_SEC + 1)  # 模擬窗過
check('窗過後可重建 → True', arh.start_arrival_event('R_TEST') is True)
check('不同接送群互不影響', arh.start_arrival_event('R_TEST2') is True)

# ============================================================
# T3: 催促狀態機（最多 2 次）
# ============================================================
banner('T3: 催促狀態機（最多 2 次）')
arh._EVENTS.clear()
SENT.clear()
arh.start_arrival_event('R_NAG')
arh._nag('R_NAG')
check('第 1 催有 push', push_count() == 1)
check('催促文案', arh.NAG_TEXT in SENT[-1][2])
arh._nag('R_NAG')
check('第 2 催有 push', push_count() == 2)
arh._nag('R_NAG')
check('第 3 次不催（上限 2）', push_count() == 2)
check('nag_count == 2', arh._EVENTS['R_NAG']['nag_count'] == 2)

# ============================================================
# T4: ack 停催
# ============================================================
banner('T4: ack 停催')
arh._EVENTS.clear()
SENT.clear()
arh.start_arrival_event('R_ACK')
check('「收到」被認得 → True', arh.handle_ack('tok', 'R_ACK', '收到') is True)
check('回覆「👌 已確認」', any(s[0] == 'reply' and '已確認' in s[2] for s in SENT))
check('acked=True', arh._EVENTS['R_ACK']['acked'] is True)
arh._nag('R_ACK')
check('ack 後催促不 push', push_count() == 0)

# ============================================================
# T5: 靜默白名單判定
# ============================================================
banner('T5: 靜默白名單判定')
check('其他文字 → False（靜默跳過）', arh.handle_ack('tok', 'R_ACK', '大家好') is False)
check('空字串 → False', arh.handle_ack('tok', 'R_ACK', '') is False)
check('「/收到」（斜線前綴）也認', arh.handle_ack('tok', 'R_ACK', '/收到') is True)
check('無事件時「收到」也回確認不炸',
      arh.handle_ack('tok', 'R_NOEVENT', '收到') is True)

# ============================================================
# T6: notify（reply / push 兩觸發點）過節流才發
# ============================================================
banner('T6: notify 觸發點 + 節流')
arh._EVENTS.clear()
SENT.clear()
arh.notify_relay_by_reply('tok1', 'R_N', '🚗 注意：來程車輛接近「診所」')
check('(a) 接送群位置釘 → reply 通知', any(s[0] == 'reply_msg' for s in SENT))
SENT.clear()
arh.notify_relay_by_reply('tok2', 'R_N', '🚗 注意：來程車輛接近「診所」')
check('(a) 節流中 → 不重發通知', len(SENT) == 0)
arh._EVENTS.clear()
SENT.clear()
arh.notify_relay_by_push('R_P', '🚗 注意：來程車輛接近「診所」')
check('(b) 工作群位置釘 → push 到接送群', push_count() == 1)
SENT.clear()
arh.notify_relay_by_push('R_P', '🚗 注意：來程車輛接近「診所」')
check('(b) 節流中 → 不重 push', push_count() == 0)

# ============================================================
# T7 / T8: DB 往返（本地 DB + 測試 chat_id，跑完清理）
# ============================================================
from app import app  # noqa: E402
from modules.models.base import db  # noqa: E402
from modules.models.group_location_meta import GroupLocationMeta  # noqa: E402
from modules.services.group_location_meta_service import (  # noqa: E402
    set_relay, clear_relay, get_relay_of, find_work_by_relay,
)

W = 'TESTWORK_arrival_relay'
R = 'TESTRELAY_arrival_relay'


def _cleanup():
    GroupLocationMeta.query.filter(
        GroupLocationMeta.chat_id.in_([W, R])
    ).delete(synchronize_session=False)
    db.session.commit()


with app.app_context():
    try:
        banner('T7: set_relay / find_work_by_relay 往返')
        set_relay(W, R)
        check('get_relay_of(工作群) == 接送群', get_relay_of(W) == R)
        check('find_work_by_relay(接送群) == 工作群', find_work_by_relay(R) == W)
        check('無綁定 chat → None', find_work_by_relay('TESTNOBODY_arrival') is None)
        check('get_relay_of 無紀錄 → None', get_relay_of('TESTNOBODY_arrival') is None)
        clear_relay(W)
        check('clear 後 get_relay_of → None', get_relay_of(W) is None)
        check('clear 後 find_work_by_relay → None', find_work_by_relay(R) is None)

        banner('T8: 綁定指令全流程')
        resp = arh.handle_relay_commands('設定到院轉發', W)
        m = re.search(r'配對碼：(\d{4})', resp or '')
        check('工作群拿到 4 位配對碼', bool(m))
        pair = m.group(1) if m else ''
        resp2 = arh.handle_relay_commands(f'綁定到院通知 {pair}', R)
        check('接送群綁定完成文案', bool(resp2) and '綁定完成' in resp2)
        check('DB 已綁定', find_work_by_relay(R) == W)
        resp3 = arh.handle_relay_commands('查看到院轉發', W)
        check('工作群查看 → 已綁定', bool(resp3) and '已綁定接送群' in resp3)
        resp3b = arh.handle_relay_commands('查看到院轉發', R)
        check('接送群查看 → 本群是接送群', bool(resp3b) and '本群是接送群' in resp3b)
        resp3c = arh.handle_relay_commands('設定到院轉發', R)
        check('接送群打「設定到院轉發」被擋', bool(resp3c) and resp3c.startswith('❌'))
        respx = arh.handle_relay_commands(f'綁定到院通知 {pair}', R)
        check('配對碼一次性（重用被拒）', bool(respx) and '錯誤或已過期' in respx)
        resp4 = arh.handle_relay_commands('取消到院轉發', W)
        check('工作群取消', bool(resp4) and '已取消' in resp4)
        check('取消後 find_work_by_relay → None', find_work_by_relay(R) is None)
        resp5 = arh.handle_relay_commands('取消到院轉發', W)
        check('沒綁定時取消 → 提示', bool(resp5) and '沒有綁定' in resp5)
        check('非指令 → None', arh.handle_relay_commands('大家好', W) is None)
    finally:
        _cleanup()

# ============================================================
# 總結
# ============================================================
print(f'\n{"=" * 60}')
if FAILS:
    print(f'❌ {len(FAILS)} 項失敗:')
    for f in FAILS:
        print(f'   - {f}')
    sys.exit(1)
print('✅ 全部通過')
sys.exit(0)
