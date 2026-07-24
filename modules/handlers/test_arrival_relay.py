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


def _fake_push(chat_id, text, warn=None):
    SENT.append(('push', chat_id, f'{text}|{warn}' if warn else text))


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
arh._schedule_nag = lambda key: None  # 不開真 Timer；催促用 _nag 直呼驗證


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
banner('T1: 配對碼生成 / 驗證 / TTL（DB 版 — database_maintenance）')
from app import app as _app_t1
from modules.models.base import db as _db_t1
from sqlalchemy import text as _sql_t1
with _app_t1.app_context():
    code = arh._gen_pair_code('W_TEST')
    check('4 位數字碼', len(code) == 4 and code.isdigit())
    check('驗碼取回工作群', arh._pop_valid_code(code) == 'W_TEST')
    check('一次性（取走即失效）', arh._pop_valid_code(code) is None)
    code2 = arh._gen_pair_code('W_TEST')
    # 模擬過期：把 DB 時間戳往回撥 11 分鐘
    _db_t1.session.execute(_sql_t1(
        "UPDATE database_maintenance SET timestamp = NOW() - INTERVAL '11 minutes' "
        "WHERE key = :k"), {'k': f'relay_pair_{code2}'})
    _db_t1.session.commit()
    check('TTL 過期 → None', arh._pop_valid_code(code2) is None)
    check('亂碼 → None', arh._pop_valid_code('zzzz') is None)
    # 清理測試殘留
    _db_t1.session.execute(_sql_t1(
        "DELETE FROM database_maintenance WHERE key LIKE 'relay_pair_%'"))
    _db_t1.session.commit()

# ============================================================
# T2: 事件節流（20 分鐘窗）
# ============================================================
banner('T2: 事件節流（20 分鐘窗）')
arh._EVENTS.clear()
check('第一次建立 → True', arh.start_arrival_event('R_TEST', 'D1') is True)
check('同司機窗內再建 → False（節流）', arh.start_arrival_event('R_TEST', 'D1') is False)
check('不同司機 → True（多車各自通知）', arh.start_arrival_event('R_TEST', 'D2') is True)
check('第三位司機 → True', arh.start_arrival_event('R_TEST', 'D3') is True)
arh._EVENTS[('R_TEST', 'D1')]['started_at'] -= (arh.EVENT_THROTTLE_SEC + 1)  # 模擬窗過
check('同司機窗過後可重建 → True', arh.start_arrival_event('R_TEST', 'D1') is True)
check('不同接送群互不影響', arh.start_arrival_event('R_TEST2', 'D1') is True)
check('未帶司機 → unknown bucket', arh.start_arrival_event('R_TEST3') is True)
check('unknown bucket 同窗節流', arh.start_arrival_event('R_TEST3') is False)

# ============================================================
# T3: 催促狀態機（最多 2 次）
# ============================================================
banner('T3: 催促狀態機（最多 2 次）')
arh._EVENTS.clear()
SENT.clear()
arh.start_arrival_event('R_NAG', 'D1')
arh._nag(('R_NAG', 'D1'))
check('第 1 催有 push', push_count() == 1)
check('催促文案', arh.NAG_TEXT in SENT[-1][2])
arh._nag(('R_NAG', 'D1'))
check('第 2 催有 push', push_count() == 2)
arh._nag(('R_NAG', 'D1'))
check('第 3 次不催（上限 2）', push_count() == 2)
check('nag_count == 2', arh._EVENTS[('R_NAG', 'D1')]['nag_count'] == 2)

# ============================================================
# T4: ack 停催
# ============================================================
banner('T4: ack 停催')
arh._EVENTS.clear()
SENT.clear()
arh.start_arrival_event('R_ACK', 'D1')
arh.start_arrival_event('R_ACK', 'D2')   # 第二台車進行中
check('「收到」被認得 → True', arh.handle_ack('tok', 'R_ACK', '收到') is True)
check('回覆「👌 已確認」', any(s[0] == 'reply' and '已確認' in s[2] for s in SENT))
check('D1 acked', arh._EVENTS[('R_ACK', 'D1')]['acked'] is True)
check('D2 也一鍵全確認', arh._EVENTS[('R_ACK', 'D2')]['acked'] is True)
arh._nag(('R_ACK', 'D1'))
arh._nag(('R_ACK', 'D2'))
check('ack 後兩台車的催促都不 push', push_count() == 0)

# T4b: 「誰按的」— mock 名字解析，驗證帶名文案
SENT.clear()
arh._EVENTS.clear()
arh.start_arrival_event('R_WHO', 'D1')
_orig_resolve = arh._resolve_member_name
arh._resolve_member_name = lambda chat_id, uid: '春妃' if uid == 'U_TEST' else None
check('帶 user_id 的收到 → True', arh.handle_ack('tok', 'R_WHO', '收到', user_id='U_TEST') is True)
check('回覆帶名字「👌 春妃 已確認」', any(s[0] == 'reply' and '春妃 已確認' in s[2] for s in SENT))
SENT.clear()
arh.start_arrival_event('R_WHO2', 'D1')
check('名字查不到 → 仍確認', arh.handle_ack('tok', 'R_WHO2', '收到', user_id='U_UNKNOWN') is True)
check('文案退回無名版', any(s[0] == 'reply' and s[2] == '👌 已確認' for s in SENT))
arh._resolve_member_name = _orig_resolve

# ============================================================
# T5: 靜默白名單判定
# ============================================================
banner('T5: 靜默白名單判定')
check('其他文字 → False（靜默跳過）', arh.handle_ack('tok', 'R_ACK', '大家好') is False)
check('空字串 → False', arh.handle_ack('tok', 'R_ACK', '') is False)
check('「/收到」（斜線前綴）也認', arh.handle_ack('tok', 'R_ACK', '/收到') is True)
check('「確定」也是確認詞（手錶罐頭回覆）', arh.handle_ack('tok', 'R_ACK', '確定') is True)
check('無事件時「收到」也回確認不炸',
      arh.handle_ack('tok', 'R_NOEVENT', '收到') is True)

# ============================================================
# T6: notify（reply / push 兩觸發點）過節流才發
# ============================================================
banner('T6: notify 觸發點 + 節流')
arh._EVENTS.clear()
SENT.clear()
arh.notify_relay_by_reply('tok1', 'R_N', '🚗 注意：來程車輛接近「診所」', driver_key='D1')
check('(a) 接送群位置釘 → reply 通知', any(s[0] == 'reply_msg' for s in SENT))
SENT.clear()
arh.notify_relay_by_reply('tok2', 'R_N', '🚗 注意：來程車輛接近「診所」', driver_key='D1')
check('(a) 同司機節流中 → 不重發通知', len(SENT) == 0)
arh.notify_relay_by_reply('tok3', 'R_N', '🚗 注意：來程車輛接近「診所」', driver_key='D2')
check('(a) 不同司機 → 照發（多車各自通知）', any(s[0] == 'reply_msg' for s in SENT))
arh._EVENTS.clear()
SENT.clear()
arh.notify_relay_by_push('R_P', '🚗 注意：來程車輛接近「診所」', driver_key='D1')
check('(b) 工作群位置釘 → push 到接送群', push_count() == 1)
SENT.clear()
arh.notify_relay_by_push('R_P', '🚗 注意：來程車輛接近「診所」', driver_key='D1')
check('(b) 同司機節流中 → 不重 push', push_count() == 0)
arh.notify_relay_by_push('R_P', '🚗 注意：來程車輛接近「診所」', driver_key='D2')
check('(b) 不同司機 → 照 push', push_count() == 1)

# T6b: 多車在途註記
arh._EVENTS.clear(); SENT.clear()
arh.notify_relay_by_reply('t1', 'R_M', '🚗 通知A', driver_key='DA')
first = [s for s in SENT if s[0] == 'reply_msg']
check('第 1 台：無多車註記', first and '在途共' not in str(first[-1][2]))
SENT.clear()
arh.notify_relay_by_reply('t2', 'R_M', '🚗 通知B', driver_key='DB')
second = [s for s in SENT if s[0] == 'reply_msg']
check('第 2 台：帶「在途共 2 趟」紅字警示（Flex）', second and '在途共 2 趟' in str(second[-1][2]) and '#D32F2F' in str(second[-1][2]))
SENT.clear()
arh.handle_ack('t3', 'R_M', '收到')          # 全確認
arh.notify_relay_by_reply('t4', 'R_M', '🚗 通知C', driver_key='DC')
third = [s for s in SENT if s[0] == 'reply_msg']
check('確認後新來一台：回到無註記', third and '在途共' not in str(third[-1][2]))

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
