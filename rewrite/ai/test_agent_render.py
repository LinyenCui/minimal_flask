"""
測試 agent.py 純函數層 — 不打 Gemini API、不寫 DB

涵蓋：
  - humanize_tool_error（A4：fail 文案人話化）
  - _is_readonly_tool（A3：唯讀 vs mutation 判定）
  - _render_mutation_summary（A3：多筆 mutation 文字彙總）
  - _inject_context_args（A2：audit context 注入）
  - _is_timeout_error（A5：逾時例外偵測）
"""
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from rewrite.ai.agent import (
    Agent,
    humanize_tool_error,
    _is_readonly_tool,
    _is_timeout_error,
    _inject_context_args,
)
from rewrite.tools.base import ToolResult


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


# ============================================================
# T1: humanize_tool_error
# ============================================================
banner('T1: humanize_tool_error')

# 欄位名 → 業務用語
assert humanize_tool_error('trip_id 必填') == '班次編號 必填'
assert humanize_tool_error('meter_fare 跟 extra_fare 至少給一個') == '錶跳車資 跟 加成 至少給一個'
assert humanize_tool_error('找不到 customer_id=5') == '找不到 客戶編號=5'
assert humanize_tool_error('deposit_date 格式錯誤') == '入金日期 格式錯誤'
assert humanize_tool_error('reason 必填') == '原因 必填'
# 長 key 先換：completed_trip_id 不能被 trip_id 半路攔截
assert humanize_tool_error('completed_trip_id 不存在') == '班次編號 不存在'
# 工程詞殘留 → 補「幫助」提示
out = humanize_tool_error('surcharge 必須是 int')
assert '（輸入格式可打「幫助」查看）' in out, out
out = humanize_tool_error('無法解析 JSON')
assert out.endswith('（輸入格式可打「幫助」查看）'), out
# point / string 不誤中 int / str
out = humanize_tool_error('start_point 不可為空')
assert '幫助' not in out, out
# 沒工程詞就不加提示
assert '幫助' not in humanize_tool_error('班次不存在')
# 空值防呆
assert humanize_tool_error(None) == '發生未知錯誤，請再試一次'
assert humanize_tool_error('') == '發生未知錯誤，請再試一次'
print('✅ humanize_tool_error OK')


# ============================================================
# T2: _is_readonly_tool
# ============================================================
banner('T2: _is_readonly_tool')

for name in ('query_trips', 'query_trip_by_id', 'aggregate_completed_trips',
             'get_customer_by_id', 'get_fixed_schedule_by_id', 'sun_week_info'):
    assert _is_readonly_tool(name), name

for name in ('passenger_leave', 'cancel_trip', 'assign_driver',
             'update_completed_trip_fare', 'create_customer', 'delete_customer',
             'apply_fixed_schedule_leave', 'restore_fixed_schedule',
             'record_fare_current'):
    assert not _is_readonly_tool(name), name

assert not _is_readonly_tool('')  # 防呆
print('✅ _is_readonly_tool OK')


# ============================================================
# T3: _render_mutation_summary
# ============================================================
banner('T3: _render_mutation_summary')

results = [
    ('passenger_leave', {'trip_id': 1234, 'reason': '化療', 'surcharge': -30},
     ToolResult.success(data=None)),
    ('passenger_leave', {'trip_id': 1235, 'reason': '化療', 'surcharge': -30},
     ToolResult.success(data=None)),
    ('cancel_trip', {'trip_id': 1236},
     ToolResult.fail('⏰ 班次 #1236 距執行時間還有 12 分鐘，30 分鐘內不可修改狀態。')),
]
msg = Agent._render_mutation_summary(results)
assert msg['type'] == 'text'
t = msg['text']
assert '共執行 3 筆' in t, t
assert '✅ 成功 2 筆' in t, t
assert '❌ 失敗 1 筆' in t, t
assert '#1234 請假 完成' in t, t
assert '#1235 請假 完成' in t, t
assert '#1236 註銷：' in t, t
print(t)

# 全成功 → 沒有失敗區塊
msg2 = Agent._render_mutation_summary([
    ('assign_driver', {'trip_id': 1190, 'driver_id': 28530}, ToolResult.success()),
    ('assign_driver', {'trip_id': 1191, 'driver_id': 28530}, ToolResult.success()),
])
assert '❌' not in msg2['text'], msg2['text']
assert '#1190 指派司機 完成' in msg2['text']

# completed_trip_id / schedule_id 也抓得到 target
msg3 = Agent._render_mutation_summary([
    ('update_completed_trip_fare', {'completed_trip_id': 820, 'reason': 'x'},
     ToolResult.success()),
    ('apply_fixed_schedule_leave', {'schedule_id': 21, 'reason': '出國', 'surcharge': -50},
     ToolResult.fail('reason 必填')),
])
assert '#820 修改車資 完成' in msg3['text'], msg3['text']
assert '#21 固定班次請假：原因 必填' in msg3['text'], msg3['text']
print('✅ _render_mutation_summary OK')


# ============================================================
# T4: _inject_context_args
# ============================================================
banner('T4: _inject_context_args')


def fake_tool(*, session, trip_id: int, user_id=None, user_name=None,
              via: str = 'unknown'):
    ...


def fake_tool_no_ctx(*, session, term: str, limit: int = 20):
    ...


def fake_tool_kwargs(*, session, customer_id: int, **fields):
    ...


# 接受 user_id / via → 注入
out = _inject_context_args(fake_tool, {'trip_id': 1}, user_id='U123')
assert out == {'trip_id': 1, 'user_id': 'U123', 'via': 'ai_agent'}, out
# user_name 沒值 → 不注入 None
assert 'user_name' not in out
# AI 已明確傳同名參數 → 不覆蓋
out = _inject_context_args(fake_tool, {'trip_id': 1, 'via': 'liff'}, user_id='U123')
assert out['via'] == 'liff', out
# 工具不收 context 參數 → 原樣
out = _inject_context_args(fake_tool_no_ctx, {'term': '太子龍'}, user_id='U123')
assert out == {'term': '太子龍'}, out
# **kwargs 型工具（update_customer 的 **fields）→ 不注入，避免 user_id 被當業務欄位
out = _inject_context_args(fake_tool_kwargs, {'customer_id': 5, 'name': '王'}, user_id='U123')
assert out == {'customer_id': 5, 'name': '王'}, out
# 真實 atomic tool（有 @require_modifiable_window decorator，@wraps 保簽名）
from rewrite.tools.trip import passenger_leave
out = _inject_context_args(passenger_leave,
                           {'trip_id': 1, 'reason': '化療', 'surcharge': -30},
                           user_id='U123')
assert out.get('user_id') == 'U123' and out.get('via') == 'ai_agent', out
# 真實 **fields 工具 update_customer → 不注入
from rewrite.tools.customer import update_customer
out = _inject_context_args(update_customer, {'customer_id': 5, 'name': '王'},
                           user_id='U123')
assert 'user_id' not in out and 'via' not in out, out
print('✅ _inject_context_args OK')


# ============================================================
# T5: _is_timeout_error
# ============================================================
banner('T5: _is_timeout_error')

import httpx
assert _is_timeout_error(httpx.ReadTimeout('read timed out'))
assert _is_timeout_error(httpx.ConnectTimeout('connect timeout'))
assert _is_timeout_error(RuntimeError('Deadline Exceeded'))
assert _is_timeout_error(Exception('request timed out after 40s'))
assert not _is_timeout_error(Exception('429 resource exhausted'))
assert not _is_timeout_error(ValueError('bad value'))
print('✅ _is_timeout_error OK')

print('\n🎉 全部通過（不打 Gemini API、不寫 DB）')
