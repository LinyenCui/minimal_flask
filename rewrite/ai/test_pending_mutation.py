"""
測試 AI mutation 機制層確認（pending mutation）— 不打 Gemini API

涵蓋：
  T1 攔截分類：含 mutation 的 batch 攔下 vs 純唯讀 batch 放行、
     無 user_id 無 event_source（測試/repl）不攔、
     無 user_id 但有 event_source（真實事件）fail-closed 不執行
  T2 build_mutation_preview：預覽文案（動作名 + 目標資料 + 參數人話化）
  T3 resolve_tool：master skill 註冊表 resolve
  T4 execute_confirmed_calls：unknown tool fail / 真 tool 執行
     （auto_commit=False + session close → 不落地，真 DB 驗證）
  T5 pending 覆蓋語義：新的 AI mutation 預覽覆蓋既有 pending
  T6 pop_state：pop-before-execute 防雙擊重複、chat_id / type 不符不 pop
"""
import sys
import time as _time

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from sqlalchemy import text as _sql

from database import Session
from rewrite.ai.agent import (
    Agent,
    build_mutation_preview,
    execute_confirmed_calls,
    resolve_tool,
    stash_pending_mutations,
)
from rewrite.ai.client import ToolCall
from rewrite.ai.skills.master import build_master_skill
from rewrite.conversation_state import (
    clear_state,
    get_state,
    pop_state,
    set_state,
)
from rewrite.handlers.sandbox_handler import PENDING_MUTATION_STATE_TYPE

TEST_UID = 'Utest_pending_mutation'
MISSING_ID = 999999999  # 不存在的 id（preview fallback / tool validate fail 用）


def banner(label):
    print(f'\n{"=" * 60}\n# {label}\n{"=" * 60}')


# 動態取一筆現存 trip（不依賴固定 id — 本地 DB 會漂移）
_s = Session()
try:
    _row = _s.execute(_sql(
        "SELECT trip_id FROM trips ORDER BY trip_id DESC LIMIT 1"
    )).fetchone()
    SOME_TRIP_ID = _row[0] if _row else None
finally:
    _s.close()
print(f'動態測試 trip_id: {SOME_TRIP_ID}')


# ============================================================
# T1: _intercept_mutations 攔截分類
# ============================================================
banner('T1: _intercept_mutations 攔截分類')
clear_state(TEST_UID)
agent = Agent(llm=None, skill=build_master_skill())

# 純唯讀 batch → 不攔（回 None、不設 state）
msg = agent._intercept_mutations(
    [ToolCall('query_trips',
              {'date_from': '2026-07-10', 'date_to': '2026-07-10'})],
    TEST_UID, None,
)
assert msg is None, msg
assert get_state(TEST_UID) is None
print('✅ 純唯讀 batch 放行')

# 無 user_id 且無 event_source（測試 / repl 直呼）→ 不攔（照原流程直接執行）
msg = agent._intercept_mutations(
    [ToolCall('cancel_trip', {'trip_id': MISSING_ID})], None, None,
)
assert msg is None, msg
print('✅ 無 user_id 無 event_source（測試/repl）不攔')


# 無 user_id 但有 event_source（真實 webhook 事件 — 群組成員未加好友時
# source.user_id 可為 None）→ fail-closed：mutation 不執行、不設 pending、回提示
class _FakeGroupSource:
    type = 'group'
    group_id = 'Cgroup_test'
    user_id = None


msg = agent._intercept_mutations(
    [ToolCall('cancel_trip', {'trip_id': MISSING_ID})],
    None, _FakeGroupSource(),
)
assert msg is not None and msg['type'] == 'text', msg
assert '無法識別操作者身分' in msg['text'], msg
assert '未執行' in msg['text'], msg
print('✅ 無 user_id 但真實事件 → fail-closed 不執行')

# 同狀況純唯讀 batch → 照常放行（fail-closed 只擋 mutation）
msg = agent._intercept_mutations(
    [ToolCall('query_trips',
              {'date_from': '2026-07-10', 'date_to': '2026-07-10'})],
    None, _FakeGroupSource(),
)
assert msg is None, msg
print('✅ 無 user_id 真實事件的純唯讀 batch 照常放行')

# 含 mutation 的 batch → 攔：唯讀照常執行、mutation 收集、回預覽 quick_reply
msg = agent._intercept_mutations(
    [
        ToolCall('query_trips',
                 {'date_from': '2026-07-10', 'date_to': '2026-07-10'}),
        ToolCall('passenger_leave',
                 {'trip_id': MISSING_ID, 'reason': '化療', 'surcharge': -30}),
    ],
    TEST_UID, None,
)
assert msg is not None
assert msg['type'] == 'quick_reply', msg
btn_texts = [i['action']['text'] for i in msg['quick_reply']['items']]
assert btn_texts == ['確認執行', '取消操作'], btn_texts
assert '請假' in msg['text'] and f'#{MISSING_ID}' in msg['text'], msg['text']

st = get_state(TEST_UID)
assert st is not None and st['type'] == PENDING_MUTATION_STATE_TYPE, st
assert st['chat_id'] == TEST_UID  # 無 event_source → 私聊 fallback user_id
calls = st['payload']['calls']
assert len(calls) == 1, calls  # 只收 mutation，唯讀不進 pending
assert calls[0][0] == 'passenger_leave'
assert calls[0][1]['trip_id'] == MISSING_ID
assert st['payload']['preview'] == msg['text']
print('✅ mutation batch 攔截（唯讀不進 pending、state 設好）')
clear_state(TEST_UID)


# ============================================================
# T2: build_mutation_preview
# ============================================================
banner('T2: build_mutation_preview')

preview = build_mutation_preview([
    ('passenger_leave',
     {'trip_id': MISSING_ID, 'reason': '化療', 'surcharge': -30}),
    ('update_completed_trip_fare',
     {'completed_trip_id': MISSING_ID, 'meter_fare': 380}),
])
print(preview)
assert preview.startswith('📋 即將執行 2 筆修改，請確認：'), preview
assert f'① 請假 — #{MISSING_ID}' in preview, preview   # 撈不到 → 只列 #id + 參數
assert '原因：化療' in preview, preview                  # key 人話化
assert '加成：-30' in preview, preview
assert f'② 修改車資 — #{MISSING_ID}' in preview, preview
assert '錶跳車資：380' in preview, preview
assert preview.rstrip().endswith('確認後才會寫入。'), preview
print('✅ 預覽文案（fallback 只列參數）OK')

# 目標資料撈得到 → 帶日期 / 起→終 / 司機
if SOME_TRIP_ID:
    p2 = build_mutation_preview([
        ('cancel_trip', {'trip_id': SOME_TRIP_ID, 'reason': '測試'}),
    ])
    print(p2)
    assert f'① 註銷 — #{SOME_TRIP_ID}' in p2, p2
    assert '→' in p2, p2          # 起→終
    assert '原因：測試' in p2, p2
    print('✅ 預覽文案（目標資料 DB 撈取）OK')
else:
    print('⚠️ trips 表沒資料，跳過目標撈取 case')


# ============================================================
# T3: resolve_tool
# ============================================================
banner('T3: resolve_tool')

fn = resolve_tool('passenger_leave')
assert fn is not None and fn.__name__ == 'passenger_leave'
assert resolve_tool('void_ledger_entry').__name__ == 'void_ledger_entry'
assert resolve_tool('delete_customer').__name__ == 'delete_customer'
assert resolve_tool('no_such_tool') is None
print('✅ resolve_tool OK')


# ============================================================
# T4: execute_confirmed_calls
# ============================================================
banner('T4: execute_confirmed_calls')

# unknown tool → fail 不炸
results = execute_confirmed_calls([('no_such_tool', {'x': 1})], TEST_UID)
assert len(results) == 1
assert not results[0][2].ok and 'unknown tool' in (results[0][2].error or '')
print('✅ unknown tool → fail')

# 不存在的 trip → tool 自己 validate fail（resolve → inject → 執行路徑通）
results = execute_confirmed_calls(
    [('cancel_trip',
      {'trip_id': MISSING_ID, 'reason': '測試', 'auto_commit': False})],
    TEST_UID,
)
name, args, r = results[0]
assert name == 'cancel_trip' and not r.ok, (name, r.error)
assert args.get('via') == 'ai_agent', args        # _inject_context_args 有注入
assert args.get('user_id') == TEST_UID, args
print('✅ resolve → inject context → 執行 → 收集 ToolResult')

# 真 tool 成功路徑：auto_commit=False + session close → 不落地
if SOME_TRIP_ID:
    test_name = f'測試乘客{int(_time.time())}'
    results = execute_confirmed_calls(
        [('update_passenger_name',
          {'trip_id': SOME_TRIP_ID, 'passenger_name': test_name,
           'auto_commit': False})],
        TEST_UID,
    )
    name, args, r = results[0]
    assert r.ok, r.error
    _s = Session()
    try:
        cur = _s.execute(
            _sql("SELECT passenger_name FROM trips WHERE trip_id = :i"),
            {'i': SOME_TRIP_ID},
        ).scalar()
    finally:
        _s.close()
    assert cur != test_name, '不該落地！（auto_commit=False 應被 rollback）'
    print('✅ 真 tool 執行成功且 rollback 不污染')
else:
    print('⚠️ trips 表沒資料，跳過真 tool 成功 case')


# ============================================================
# T5: pending 覆蓋語義
# ============================================================
banner('T5: pending 覆蓋語義')
clear_state(TEST_UID)

stash_pending_mutations([('cancel_trip', {'trip_id': 111})], TEST_UID)
stash_pending_mutations(
    [('passenger_leave', {'trip_id': 222, 'reason': 'x', 'surcharge': -30})],
    TEST_UID,
)
st = get_state(TEST_UID)
assert st['type'] == PENDING_MUTATION_STATE_TYPE
calls = st['payload']['calls']
assert len(calls) == 1 and calls[0][0] == 'passenger_leave', calls
assert calls[0][1]['trip_id'] == 222, calls
print('✅ 新預覽覆蓋既有 pending')
clear_state(TEST_UID)


# ============================================================
# T6: pop_state — 防雙擊 + chat_id / type 條件
# ============================================================
banner('T6: pop_state 防雙擊 / chat_id 不符不執行')
clear_state(TEST_UID)
set_state(TEST_UID, PENDING_MUTATION_STATE_TYPE,
          {'calls': [('cancel_trip', {'trip_id': 333})]},
          ttl_minutes=5.0, chat_id='Cchat_A')

# chat_id 不符 → 不 pop、state 保留（跨對話不執行、也不誤清）
assert pop_state(TEST_UID, state_type=PENDING_MUTATION_STATE_TYPE,
                 chat_id='Cchat_B') is None
assert get_state(TEST_UID) is not None
print('✅ chat_id 不符 → 不執行、pending 保留')

# type 不符 → 不 pop
assert pop_state(TEST_UID, state_type='other_type', chat_id='Cchat_A') is None
assert get_state(TEST_UID) is not None
print('✅ type 不符 → 不 pop')

# 都符 → pop 成功；第二次 pop → None（先 pop 再執行 → 雙擊不重複執行）
st = pop_state(TEST_UID, state_type=PENDING_MUTATION_STATE_TYPE,
               chat_id='Cchat_A')
assert st is not None and st['type'] == PENDING_MUTATION_STATE_TYPE
assert st['payload']['calls'][0][1]['trip_id'] == 333
assert pop_state(TEST_UID, state_type=PENDING_MUTATION_STATE_TYPE,
                 chat_id='Cchat_A') is None
assert get_state(TEST_UID) is None
print('✅ pop-before-execute：第二次 pop 拿 None，防雙擊重複執行')

clear_state(TEST_UID)
print('\n🎉 全部通過（不打 Gemini API、mutation 不落地）')
