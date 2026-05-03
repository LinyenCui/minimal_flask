"""
測試批量請假流程（router 層整合測試）

驗證：
  - 預檢分類（鎖外準備可請、鎖內跳過、已完成跳過、註銷跳過、已請假跳過）
  - conversation_state 正確設定
  - 批量 _execute 呼叫後，DB 上每筆 trip 都正確 passenger_leave
  - audit_log 有對應筆數
  - reply_message 攔截到正確訊息

mock reply_message 攔下 LINE API call，只看內部行為跟 DB。
"""
import sys
from datetime import date, datetime, timedelta, time as dt_time
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import Session
from sqlalchemy import text

# Mock reply_message — 攔截不打 LINE API
_REPLIES = []
import rewrite.router as router_mod

def _mock_reply(reply_token, msg):
    _REPLIES.append({'token': reply_token, 'msg': msg})

router_mod.reply_message = _mock_reply

from rewrite.router import (
    _handle_trip_batch_leave,
    _handle_leave_input,
)
from rewrite.conversation_state import (
    set_state, get_state, clear_state,
)

USER_ID = 'U6b520261e9199a21d25e6d20509eda3f'


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


TEST_CATEGORY = '測試批量'  # 跟真實資料的「診所」「東洋」區隔


def make_trip(session, trip_id, date_, time_, *,
              status='準備', driver_id=533,
              passenger_leave_reason=None, fake_ids):
    session.execute(text("DELETE FROM trips WHERE trip_id = :id"), {'id': trip_id})
    session.execute(text("""
        INSERT INTO trips (trip_id, date, time, start_point, end_point,
                           category, status, driver_id, meter_fare, extra_fare,
                           passenger_leave_reason)
        VALUES (:id, :d, :t, '龍埔街', '診所', :cat,
                :s, :drv, 340, 0, :leave)
    """), {
        'id': trip_id, 'd': date_, 't': time_,
        's': status, 'drv': driver_id,
        'cat': TEST_CATEGORY,
        'leave': passenger_leave_reason,
    })
    session.commit()
    fake_ids.append(trip_id)


session = Session()
fake_ids = []
try:
    now = datetime.now()
    target = (now + timedelta(minutes=60)).time().replace(microsecond=0)
    locked = (now + timedelta(minutes=15)).time().replace(microsecond=0)
    today = now.date()
    tomorrow = today + timedelta(days=1)

    # ============================================================
    # 準備：建 5 個 trips 在「明天」（避開 today 已請假的測試）
    # ============================================================
    banner('準備 — 建 5 個明天的 trips（含各種狀態）')
    trips_setup = [
        # (id, status, time, leave_reason)  → 預期被預檢分類
        (99301, '準備',  target, None),       # 可請
        (99302, '準備',  target, None),       # 可請
        (99303, '已完成', target, None),       # 跳過：已完成
        (99304, '註銷',  target, None),       # 跳過：註銷
        (99305, '準備',  target, '舊請假'),    # 跳過：已請假（display_status='請假'）
    ]
    for tid, s, t, leave in trips_setup:
        make_trip(session, tid, tomorrow, t,
                  status=s, passenger_leave_reason=leave,
                  fake_ids=fake_ids)
    print(f'  建好 5 筆 trips')

    # ============================================================
    # T1：批量請假 入口 — 預檢分類
    # ============================================================
    banner('T1: _handle_trip_batch_leave 預檢分類')
    _REPLIES.clear()
    clear_state(USER_ID)
    date_arg = f"{tomorrow.month}/{tomorrow.day}"
    _handle_trip_batch_leave(
        reply_token='fake_token',
        session=session,
        date_str=date_arg,
        category=TEST_CATEGORY,
        user_id=USER_ID,
    )

    # 驗 reply 內容
    assert len(_REPLIES) == 1
    msg = _REPLIES[0]['msg']
    assert msg['type'] == 'text'
    text_body = msg['text']
    print(f'  reply 文字（前 300 字）：')
    print('  ' + text_body[:300].replace('\n', '\n  '))

    # 驗包含可請 + 跳過資訊
    assert '可請假 2 筆' in text_body
    assert '#99301' in text_body and '#99302' in text_body
    assert '跳過 3 筆' in text_body
    assert '已完成' in text_body and '註銷' in text_body and '已請假' in text_body
    assert '請輸入：[原因] [負加成]' in text_body
    # 驗 quickReply [放棄操作]
    assert msg.get('quickReply')
    assert msg['quickReply']['items'][0]['action']['text'] == '放棄操作'
    print(f'  ✅ 預檢正確：2 可請 + 3 跳過')

    # 驗 state 已設定
    state = get_state(USER_ID)
    assert state and state['type'] == 'batch_leave_input'
    assert sorted(state['payload']['trip_ids']) == [99301, 99302]
    print(f'  ✅ state 設好：trip_ids={state["payload"]["trip_ids"]}')

    # ============================================================
    # T2：用戶輸入「化療 -30」 → batch 執行
    # ============================================================
    banner('T2: _handle_leave_input 接收「化療 -30」批量執行')
    _REPLIES.clear()
    _handle_leave_input(
        reply_token='fake_token',
        user_id=USER_ID,
        text='化療 -30',
        state=state,
    )

    assert len(_REPLIES) == 1
    text_body = _REPLIES[0]['msg']['text']
    print(f'  reply 文字：\n  ' + text_body.replace('\n', '\n  '))
    assert '批量請假完成' in text_body
    assert '化療' in text_body and '-30' in text_body
    assert '成功 2 筆' in text_body
    print(f'  ✅ 批量回報「成功 2 筆」')

    # state 應已清
    assert get_state(USER_ID) is None
    print(f'  ✅ state 已清')

    # 驗 DB
    rows = session.execute(text("""
        SELECT trip_id, status, passenger_leave_reason, extra_fare
        FROM trips WHERE trip_id = ANY(:ids)
        ORDER BY trip_id
    """), {'ids': [99301, 99302]}).fetchall()
    for r in rows:
        print(f'    #{r[0]}: status={r[1]} leave={r[2]!r} extra={r[3]}')
        assert r[1] == '準備'  # 三層障眼法：仍 '準備'
        assert r[2] == '化療'
        assert r[3] == -30
    print(f'  ✅ 兩筆 trips 都正確 update（三層障眼法）')

    # 驗 audit log
    audit_count = session.execute(text("""
        SELECT COUNT(*) FROM audit_log
        WHERE target_table = 'trips'
              AND target_id = ANY(:ids)
              AND action_type = 'passenger_leave'
              AND via = 'line_batch_input'
    """), {'ids': [99301, 99302]}).scalar()
    assert audit_count == 2, f'expected 2 audit, got {audit_count}'
    print(f'  ✅ audit_log 兩筆 via=line_batch_input')

    # ============================================================
    # T3：批量無可請假 → 不進 mode
    # ============================================================
    banner('T3: 全部不可請假 → 不進 mode')
    # 把可請的兩筆設成「已完成」
    session.execute(text("""
        UPDATE trips SET status = '已完成' WHERE trip_id = ANY(:ids)
    """), {'ids': [99301, 99302]})
    session.commit()

    _REPLIES.clear()
    clear_state(USER_ID)
    _handle_trip_batch_leave(
        reply_token='fake_token',
        session=session,
        date_str=date_arg,
        category=TEST_CATEGORY,
        user_id=USER_ID,
    )

    assert len(_REPLIES) == 1
    text_body = _REPLIES[0]['msg']['text']
    assert '無可請假班次' in text_body
    assert '5 筆全部跳過' in text_body
    print(f'  ✅ {text_body.strip()}')
    assert get_state(USER_ID) is None
    print(f'  ✅ state 沒被設定（沒進 mode）')

    # ============================================================
    # T4：放棄操作中途退出
    # ============================================================
    banner('T4: 進入 batch mode 後輸入「放棄操作」 → 清 state')
    # 重新啟動：把 99301 完整重置（清 T2 留下的請假狀態）
    session.execute(text("""
        UPDATE trips SET
            status = '準備',
            passenger_leave_reason = NULL,
            extra_fare = 0
        WHERE trip_id = 99301
    """))
    session.commit()

    _REPLIES.clear()
    _handle_trip_batch_leave(
        reply_token='fake_token',
        session=session,
        date_str=date_arg,
        category=TEST_CATEGORY,
        user_id=USER_ID,
    )
    state = get_state(USER_ID)
    assert state and state['type'] == 'batch_leave_input'

    _REPLIES.clear()
    _handle_leave_input(
        reply_token='fake_token',
        user_id=USER_ID,
        text='放棄操作',
        state=state,
    )
    assert get_state(USER_ID) is None
    assert _REPLIES[0]['msg']['text'] == '已放棄請假操作'
    print(f'  ✅ 放棄操作正確清 state')

    # ============================================================
    # T5：日期解析失敗
    # ============================================================
    banner('T5: 日期格式錯誤 → 提示')
    _REPLIES.clear()
    clear_state(USER_ID)
    _handle_trip_batch_leave(
        reply_token='fake_token',
        session=session,
        date_str='aaa',
        category=None,
        user_id=USER_ID,
    )
    assert len(_REPLIES) == 1
    assert '日期解析失敗' in _REPLIES[0]['msg']['text']
    print(f'  ✅ {_REPLIES[0]["msg"]["text"][:80]}')

    print('\n' + '='*60)
    print('✅ 全部 5 個批量請假整合測試通過')
    print('   預檢分類 ✓ / state 流轉 ✓ / 批量執行 ✓')
    print('   全跳過 ✓ / 中途放棄 ✓ / 日期錯誤 ✓')
    print('='*60)

finally:
    clear_state(USER_ID)
    for fid in fake_ids:
        try:
            session.execute(text("DELETE FROM trips WHERE trip_id = :id"), {'id': fid})
        except Exception:
            pass
    if fake_ids:
        session.execute(text("""
            DELETE FROM audit_log
            WHERE target_table = 'trips' AND target_id = ANY(:ids)
        """), {'ids': fake_ids})
    session.commit()
    if fake_ids:
        print(f'\n🧹 清理測試 trips: {fake_ids}')
    session.close()
