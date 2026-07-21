"""
測試 chat_text 協議：client_can_send=True → 回 chat_text 不 push；
False / 缺省 → 照舊 push（fallback，行為不變）。

不打 LINE API、不碰 DB：
  - notify_or_chat_text 分支：monkeypatch chat_notify.push_text
  - handler 層（booking batch_notify / trips batch_status_notify — 不碰 DB 的
    兩支收尾 endpoint）：Flask test client + mock 掉 auth 與 line_bot
  - 各 handler 的純文字 builder：SimpleNamespace 假 view
"""
import sys
from datetime import date, time
from types import SimpleNamespace

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')


def banner(label: str):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


# ============================================================
# T1: notify_or_chat_text 核心分支
# ============================================================
banner('T1: notify_or_chat_text — True 回 text 不 push / False 照舊 push')
from rewrite.handlers.liff import chat_notify  # noqa: E402

_push_calls = []
_orig_push_text = chat_notify.push_text
chat_notify.push_text = lambda target_id, text, label='liff': _push_calls.append(
    (target_id, text, label))

out = chat_notify.notify_or_chat_text(
    client_can_send=True, target_id='U' + 'a' * 32, text='結果文字', label='t1')
assert out == '結果文字', f'True 應回 text，got {out!r}'
assert _push_calls == [], 'True 不該 push'

out = chat_notify.notify_or_chat_text(
    client_can_send=False, target_id='U' + 'a' * 32, text='結果文字', label='t1')
assert out is None, 'False 應回 None'
assert _push_calls == [('U' + 'a' * 32, '結果文字', 't1')], 'False 應照舊 push'

chat_notify.push_text = _orig_push_text
print('  ok: 分支正確')

# ============================================================
# T2: handler 層 — booking /liff/booking/batch_notify
# ============================================================
banner('T2: booking batch_notify — True 回 chat_text 0 push / False 1 push')
from flask import Flask  # noqa: E402
from rewrite.handlers.liff import auth as liff_auth  # noqa: E402
from rewrite.handlers.liff import liff_bp  # noqa: E402
import modules.utils.line_bot as line_bot_mod  # noqa: E402

# auth：驗 token 一律過（不打 LINE verify）
liff_auth.verify_line_id_token = lambda tok: {'sub': 'U' + 'f' * 32, 'name': '測試'}

# line_bot：假 api 記 push 次數（不打 LINE push）
_pushed = []


class _FakeApi:
    def push_message(self, req):
        _pushed.append(req)


line_bot_mod.get_line_bot_api = lambda: _FakeApi()
line_bot_mod.push_notify_enabled = lambda: True

app = Flask(__name__)
app.register_blueprint(liff_bp)
client = app.test_client()

_HDR = {'Authorization': 'Bearer fake-token'}
_SRC = {'type': 'group', 'groupId': 'C' + 'a' * 32}
_BOOKINGS = [
    {'trip_id': 101, 'date': '2026-07-21', 'time': '08:30',
     'start_point': '龍埔街', 'end_point': '診所'},
    {'trip_id': 102, 'date': '2026-07-21', 'time': '09:00',
     'start_point': '東洋後門', 'end_point': ''},
]

# True → 回 chat_text，0 push
_pushed.clear()
resp = client.post('/liff/booking/batch_notify', headers=_HDR, json={
    'bookings': _BOOKINGS, 'source': _SRC, 'client_can_send': True,
})
data = resp.get_json()
assert data['ok'] is True
assert '已建立 2 筆預約' in data.get('chat_text', ''), f"chat_text 缺: {data}"
assert '#101' in data['chat_text'] and '7/21 08:30 龍埔街→診所' in data['chat_text']
assert len(_pushed) == 0, 'client_can_send=True 不該 push'
print(f"  ok True: chat_text={data['chat_text']!r}, pushes=0")

# False（缺省）→ 照舊 push 一則，無 chat_text
_pushed.clear()
resp = client.post('/liff/booking/batch_notify', headers=_HDR, json={
    'bookings': _BOOKINGS, 'source': _SRC,
})
data = resp.get_json()
assert data['ok'] is True
assert 'chat_text' not in data, f'False 不該回 chat_text: {data}'
assert len(_pushed) == 1, f'False 應照舊 push 一則, got {len(_pushed)}'
assert _pushed[0].to == 'C' + 'a' * 32
print('  ok False: 1 push, 無 chat_text')

# ============================================================
# T3: handler 層 — trip /liff/trips/batch_status_notify
# ============================================================
banner('T3: trips batch_status_notify — True 回 chat_text 0 push / False 1 push')
_payload = {
    'action': 'leave',
    'results': [{'trip_id': 11, 'ok': True}, {'trip_id': 12, 'ok': False}],
    'reason': '出國',
    'surcharge': -30,
    'source': _SRC,
}

_pushed.clear()
resp = client.post('/liff/trips/batch_status_notify', headers=_HDR,
                   json={**_payload, 'client_can_send': True})
data = resp.get_json()
assert data['ok'] is True
ct = data.get('chat_text', '')
assert '🏷️ 已請假 共 1 筆' in ct and '#11' in ct and '出國' in ct, f'chat_text 缺: {data}'
assert '1 筆未成功' in ct
assert len(_pushed) == 0, 'client_can_send=True 不該 push'
print(f'  ok True: chat_text={ct!r}, pushes=0')

_pushed.clear()
resp = client.post('/liff/trips/batch_status_notify', headers=_HDR, json=_payload)
data = resp.get_json()
assert data['ok'] is True
assert 'chat_text' not in data
assert len(_pushed) == 1, f'False 應照舊 push 一則, got {len(_pushed)}'
print('  ok False: 1 push, 無 chat_text')

# ============================================================
# T4: 各 handler 純文字 builder
# ============================================================
banner('T4: 文字 builder — customer / fixed_schedule / trip / booking')
from rewrite.handlers.liff.customer import (  # noqa: E402
    _customer_batch_chat_text,
    _customer_chat_text,
)
from rewrite.handlers.liff.fixed_schedule import (  # noqa: E402
    _schedule_chat_text,
    _schedule_leave_chat_text,
)
from rewrite.handlers.liff.trip import _trip_status_chat_text  # noqa: E402
from rewrite.handlers.liff.booking import _booking_chat_text  # noqa: E402

cust = SimpleNamespace(id=5, short_name='太子龍', name='陳先生',
                       address='三峽', category='診所', contact_phone='0912')
t = _customer_chat_text(cust, '新增')
assert t.startswith('✅ 已新增客戶 #5 太子龍')
assert '姓名：陳先生' in t and '地址：三峽' in t and '類別：診所' in t
t = _customer_batch_chat_text([cust], [('王伯伯', '簡稱重複')])
assert '已新增 1 位客戶' in t and '#5 太子龍' in t and '王伯伯：簡稱重複' in t
assert _customer_batch_chat_text([], [('x', 'err')]) is None, '無成功應回 None'

sched = SimpleNamespace(id=14, route_number='135', departure_time=time(8, 30),
                        start_point='龍埔街', end_point='診所', category='診所')
t = _schedule_chat_text(sched, '建立')
assert '✅ 已建立固定班次 #14' in t and '每週一三五 08:30' in t
assert '龍埔街 → 診所' in t
t = _schedule_leave_chat_text(sched, '化療', -30)
assert '🏷️ 已將固定班次 #14 設為請假' in t
assert '原因：化療' in t and '加成：-30 元' in t

trip_view = SimpleNamespace(
    trip_id=2534, date=date(2026, 7, 21), time=time(8, 30),
    display_route=lambda: ('龍埔街', None, '診所'),
    category='診所', driver_id=5386,
)
t = _trip_status_chat_text(trip_view, 'leave', '出國', -100)
assert '🏷️ 已請假 班次 #2534' in t
assert '📅 7/21(二) 08:30' in t and '📝 出國' in t and '💰 -100 元' in t
t = _trip_status_chat_text(trip_view, 'cancel', '', 0)
assert '🚫 已註銷 班次 #2534' in t and '↩️ 可用「改回準備」還原' in t

t = _booking_chat_text(trip_view)
assert '✅ 已建立預約 #2534' in t and '📍 龍埔街 → 診所' in t
assert '類別：診所' in t and '🚕 司機 5386' in t
print('  ok: builders 文案正確')

print(f'\n{"="*60}\n全部通過 ✅\n{"="*60}')
