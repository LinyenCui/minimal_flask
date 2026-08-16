"""
測試 rewrite/tools/leave_guard.py + 各入口的「請假但 0 元」閘門

背景：用戶回報連續數次「操作請假但金額沒扣除，或填成 -0（而 -0 是被允許的）」。
清查後確認請假有 9 條入口，漏一條就等於白做，所以這裡逐條斷言。

  T1  is_zero_surcharge 判定（None / 0 / -0 / 正數 / 負數 / 型別髒資料）
  T2  現在態 passenger_leave 閘門（擋 + 放行 + 留痕）
  T3  未來態 apply_fixed_schedule_leave 閘門
  T4  AI 確認卡：0 元/漏填要看得見警示；正常扣款不該有警示
  T5  匯入預覽會算出 zero_surcharge_leave
  T6  LIFF 通知不再因為 `if surcharge:` 把 0 元那行吃掉

DB 相關的測試全程 auto_commit=False + rollback，不污染生產資料。
"""
import sys

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from dotenv import load_dotenv
load_dotenv('/Users/linyancui/minimal_flask/.env')
load_dotenv('/Users/linyancui/minimal_flask/.env.dev', override=True)

from sqlalchemy import text

from database import Session
from rewrite.tools.leave_guard import (
    CONFIRMED_SUFFIX,
    NEEDS_CONFIRM_KEY,
    describe_surcharge,
    is_zero_surcharge,
    mark_confirmed,
)
from rewrite.tools.trip import TripView, passenger_leave
from rewrite.tools.fixed_schedule import apply_fixed_schedule_leave
from rewrite.tools.import_fixed import preview_import_fixed
from rewrite.ai.agent import build_mutation_preview
from rewrite.handlers.liff.trip import _trip_status_chat_text


def banner(label):
    print(f'\n{"=" * 60}\n# {label}\n{"=" * 60}')


def ok(cond, label):
    print(f'  {"✅" if cond else "❌"} {label}')
    assert cond, label


# ============================================================
banner('T1: is_zero_surcharge 判定')
# ============================================================
for v, expected, note in [
    (None, True, '未填'),
    (0, True, '0'),
    (-0, True, '-0（Python 裡就是 0）'),
    (int('-0'), True, "int('-0')"),
    (30, True, '正數（請假不該有正加成，一律當沒扣款）'),
    (-1, False, '-1'),
    (-30, False, '-30'),
    (-220, False, '-220'),
    ('abc', False, '型別髒資料交給原本的型別檢查'),
    (True, False, 'bool 不算數字'),
]:
    ok(is_zero_surcharge(v) is expected, f'is_zero_surcharge({v!r}) == {expected}（{note}）')

ok('未填' in describe_surcharge(None), 'describe：未填看得出來')
ok('0 元' in describe_surcharge(0), 'describe：0 看得出來')
ok('-30' in describe_surcharge(-30), 'describe：-30 正常顯示')
ok(describe_surcharge(None) != describe_surcharge(0), '「未填」與「填 0」訊息要分得出來')
ok(mark_confirmed('乘客請假: 化療').endswith(CONFIRMED_SUFFIX), 'mark_confirmed 會加標記')
ok(mark_confirmed(mark_confirmed('x')).count(CONFIRMED_SUFFIX) == 1, 'mark_confirmed 不重複疊加')


session = Session()
try:
    # 自建 fixture，不依賴現成資料 —— 本地庫的班次會隨時間全部變成「已完成」，
    # 靠 SELECT 撈現成的「準備」班次會在某天突然找不到測資而整支紅掉
    # （2026-08-16 就發生過），跟程式對不對無關。
    from datetime import date as _d, time as _t, timedelta as _td
    _far = _d.today() + _td(days=30)
    tid = session.execute(text(
        "SELECT trip_id FROM trips WHERE status='準備' "
        "AND passenger_leave_reason IS NULL ORDER BY trip_id DESC LIMIT 1"
    )).scalar()
    _synthetic = not tid
    if _synthetic:
        tid = 99901
        _drv = session.execute(text('SELECT id FROM drivers ORDER BY id LIMIT 1')).scalar()

        def _ensure_fixture():
            exists = session.execute(text('SELECT 1 FROM trips WHERE trip_id=:i'),
                                     {'i': tid}).scalar()
            if not exists:
                session.execute(text("""
                    INSERT INTO trips (trip_id, date, time, start_point, end_point,
                                       category, driver_id, status, meter_fare,
                                       extra_fare, trip_type)
                    VALUES (:id, :d, :t, '測試起點', '測試終點', '臨時', :drv,
                            '準備', 0, 0, 'temp')
                """), {'id': tid, 'd': _far, 't': _t(9, 0), 'drv': _drv})
        _ensure_fixture()
    else:
        def _ensure_fixture():
            pass

    def _undo():
        """回滾這個 case。rollback 會連自建的 fixture 一起清掉，所以要補回來
        （fixture 跟測試案例在同一個交易裡，這是零污染測試的代價）。"""
        session.rollback()
        _ensure_fixture()

    sid = session.execute(text(
        "SELECT id FROM fixed_schedules WHERE status='準備' LIMIT 1"
    )).scalar()
    assert sid, '找不到「準備」狀態的固定班次模板'
    assert tid, '建不出測試班次'

    # ============================================================
    banner(f'T2: 現在態 passenger_leave 閘門（#{tid}）')
    # ============================================================
    def leave(**kw):
        r = passenger_leave(session=session, trip_id=tid, auto_commit=False, **kw)
        return r

    for label, kw in [('沒填加成', dict(reason='測')),
                      ('填 0', dict(reason='測', surcharge=0)),
                      ('填 -0', dict(reason='測', surcharge=-0)),
                      ('填正數 +30', dict(reason='測', surcharge=30))]:
        r = leave(**kw)
        ok(not r.ok and r.meta.get(NEEDS_CONFIRM_KEY) is True,
           f'{label} → 擋下且帶 {NEEDS_CONFIRM_KEY} 旗標')
        ok('不會扣款' in (r.error or '') or '沒有扣款' in (r.error or ''),
           f'{label} → 訊息講清楚沒扣款')
        _undo()

    r = leave(reason='測', surcharge=-30)
    ok(r.ok, '填 -30 → 正常放行（不該被閘門誤傷）')
    _undo()

    r = leave(reason='測', surcharge=0, confirm_zero_surcharge=True)
    ok(r.ok, '填 0 + 已確認 → 放行')
    mod = session.execute(text('SELECT modification_reason FROM trips WHERE trip_id=:t'),
                          {'t': tid}).scalar()
    ok(CONFIRMED_SUFFIX in (mod or ''), '放行的 0 元請假有留痕（事後對帳分得出來）')
    _undo()

    r = leave(reason='測', surcharge=-30, confirm_zero_surcharge=True)
    mod = session.execute(text('SELECT modification_reason FROM trips WHERE trip_id=:t'),
                          {'t': tid}).scalar()
    ok(CONFIRMED_SUFFIX not in (mod or ''), '正常扣款不該被加上「已確認」標記')
    _undo()

    # 閘門不可蓋掉更該講的錯
    ok(not passenger_leave(session=session, trip_id=999999, reason='測',
                           auto_commit=False).ok, '班次不存在 → 仍回原本的錯')
    ok('找不到' in (passenger_leave(session=session, trip_id=999999, reason='測',
                                    auto_commit=False).error or ''),
       '班次不存在的訊息不被 0 元警示蓋掉')
    _undo()
    r = passenger_leave(session=session, trip_id=tid, reason='  ',
                        surcharge=0, auto_commit=False)
    ok('原因' in (r.error or ''), '原因空白 → 仍先報原因錯（不是 0 元警示）')
    _undo()

    # ============================================================
    banner(f'T3: 未來態 apply_fixed_schedule_leave 閘門（#{sid}）')
    # ============================================================
    for label, kw in [('沒填加成', dict(reason='測')), ('填 0', dict(reason='測', surcharge=0))]:
        r = apply_fixed_schedule_leave(session=session, schedule_id=sid,
                                       auto_commit=False, **kw)
        ok(not r.ok and r.meta.get(NEEDS_CONFIRM_KEY) is True, f'{label} → 擋下')
        ok('每週匯入' in (r.error or ''), f'{label} → 有提醒「模板錯了會一直複製」')
        _undo()

    r = apply_fixed_schedule_leave(session=session, schedule_id=sid, reason='測',
                                   surcharge=-95, auto_commit=False)
    ok(r.ok, '填 -95 → 正常放行')
    _undo()
    r = apply_fixed_schedule_leave(session=session, schedule_id=sid, reason='測',
                                   surcharge=0, confirm_zero_surcharge=True,
                                   auto_commit=False)
    ok(r.ok, '填 0 + 已確認 → 放行')
    _undo()

    # 未填 + 已確認 → DB 要寫 0，不是 NULL
    # （final_surcharge 算了卻沒綁進 UPDATE 的話，這裡會抓到）
    r = apply_fixed_schedule_leave(session=session, schedule_id=sid, reason='測',
                                   confirm_zero_surcharge=True, auto_commit=False)
    ok(r.ok, '未填 + 已確認 → 放行')
    db_sc = session.execute(text('SELECT surcharge FROM fixed_schedules WHERE id=:i'),
                            {'i': sid}).scalar()
    ok(db_sc == 0, f'未填確認放行後 DB 寫 0 而非 NULL（實際 {db_sc!r}）')
    _undo()

    # ============================================================
    banner('T4: AI 確認卡')
    # ============================================================
    p_missing = build_mutation_preview([('passenger_leave', {'trip_id': tid, 'reason': '化療'})])
    p_zero = build_mutation_preview([('passenger_leave', {'trip_id': tid, 'reason': '化療',
                                                          'surcharge': 0})])
    p_ok = build_mutation_preview([('passenger_leave', {'trip_id': tid, 'reason': '化療',
                                                        'surcharge': -30})])
    ok('未填' in p_missing, '漏傳 surcharge → 卡片顯示「未填」（原本被 None 靜默 skip）')
    ok('不會扣款' in p_missing, '漏傳 surcharge → 卡片有警示')
    ok('不會扣款' in p_zero, '明確填 0 → 卡片有警示')
    ok('不會扣款' not in p_ok, '正常扣款 → 卡片乾淨，不吵')
    ok('-30' in p_ok, '正常扣款 → 金額有顯示')

    p_batch = build_mutation_preview([
        ('passenger_leave', {'trip_id': tid, 'reason': '化療', 'surcharge': 0}),
        ('passenger_leave', {'trip_id': tid, 'reason': '化療', 'surcharge': -30}),
    ])
    ok('其中 1 筆' in p_batch, '多筆時只數 0 元那幾筆')

    # ============================================================
    banner('T5: 匯入預覽算出 0 元請假筆數')
    # ============================================================
    r = preview_import_fixed(session=session, week_offset=1, category='診所')
    ok(r.ok, '預覽可執行')
    ok('zero_surcharge_leave' in r.data, '預覽回傳含 zero_surcharge_leave')
    ok(isinstance(r.data['zero_surcharge_leave'], int), 'zero_surcharge_leave 是整數')
    ok(r.data['zero_surcharge_leave'] <= r.data['leave_count'],
       '0 元請假筆數不可能超過請假總筆數')
    print(f"     （本週診所：請假 {r.data['leave_count']} 筆，"
          f"其中 0 元 {r.data['zero_surcharge_leave']} 筆）")

finally:
    session.rollback()
    session.close()


# ============================================================
banner('T6: LIFF 通知不再吃掉 0 元那行')
# ============================================================
# 曾經寫 `if surcharge:` —— 0 是 falsy，害「請假 0 元」的通知連金額都不印，
# 操作者收到一則看起來完全正常的訊息（用戶回報的根因之一）。
_view = TripView(trip_id=1234, start_point='龍埔街', end_point='診所',
                 status='準備', passenger_leave_reason='化療')
t_zero = _trip_status_chat_text(_view, 'leave', '化療', 0)
t_none = _trip_status_chat_text(_view, 'leave', '化療', None)
t_neg = _trip_status_chat_text(_view, 'leave', '化療', -30)
ok('0 元' in t_zero, '0 元請假 → 通知有講金額')
ok('未扣款' in t_zero, '0 元請假 → 通知講明沒扣款')
ok('0 元' in t_none, '未填加成 → 通知有講金額')
ok('-30' in t_neg, '正常扣款 → 金額照舊顯示')

# ============================================================
banner('T7: 對抗性審查抓到的缺陷（回歸保護）')
# ============================================================
import inspect
import re as _re

from rewrite.handlers.liff.trip import _batch_status_text
import rewrite.router as _router
import rewrite.tools.leave as _leave_mod
import rewrite.tools.import_fixed as _imp

# (1) 群組裡「確認執行」按鈕不能是死鍵：webhook 群組閘門只放行 / 開頭，
#     而 router 自己的 'leave_input' state 不在放行白名單裡
_src = inspect.getsource(_router._handle_leave_input)
ok('f"/{MUTATION_CONFIRM_TEXT}"' in _src,
   'router 的確認 Quick Reply 帶 / 前綴（否則群組裡按了沒反應）')

# (2) chat_id 要從 state 頂層拿，不是 payload
ok("payload.get('chat_id')" not in _src,
   'chat_id 不從 payload 拿（payload 裡根本沒有這個 key）')

# (3) 「已確認」要綁在被警示的那組 (原因, 加成)，不能黏在 state 上
ok("pending_reason" in _src and "pending_surcharge" in _src and 'zero_ok' in _src,
   '確認旗標綁定在被警示的原因+加成上（避免同一輪之後全部放行）')

# (4) 批次彙總通知不能再被 falsy 0 吃掉金額
ok('0 元（未扣款）' in _batch_status_text('leave', [1, 2], 0, '化療', 0),
   '批次彙總：0 元有講明')
ok('0 元（未扣款）' in _batch_status_text('leave', [1], 0, '化療', None),
   '批次彙總：未填也有講明')
ok('-30' in _batch_status_text('leave', [1], 0, '化療', -30),
   '批次彙總：正常扣款照舊')

# (5) 匯入「執行」也要回 zero_surcharge_leave（否則廣播警示是死碼）
_esrc = inspect.getsource(_imp.import_fixed_to_trips)
ok("'zero_surcharge_leave': zero_surcharge_leave" in _esrc,
   '匯入執行的回傳含 zero_surcharge_leave')
ok('zero_surcharge_leave -= 1' in _esrc,
   '重複跳過時 zero_surcharge_leave 一起扣回（數字不虛高）')

# (6) 三個 LIFF 表單的前端門檻要對齊後端的 >= 0
for _f in ('trip_status_form', 'trip_batch_status_form', 'fixed_schedule_leave_form'):
    _h = open(f'/Users/linyancui/minimal_flask/templates/liff/{_f}.html').read()
    ok('if (sc < 0) return true;' in _h, f'{_f}：前端門檻對齊後端 >= 0')
    ok(_re.search(r'(>= 0\) (payload|basePayload)\.confirm_zero_surcharge|_sc >= 0\) payload)', _h)
       is not None, f'{_f}：>= 0 才帶確認旗標')

# (7) 第 10 條入口 apply_leave 要能透傳閘門參數
_sig = inspect.signature(_leave_mod.apply_leave)
ok('confirm_zero_surcharge' in _sig.parameters,
   'apply_leave 有 confirm_zero_surcharge 參數')
ok(_sig.parameters['surcharge'].default is None,
   'apply_leave 的 surcharge 預設對齊 passenger_leave（None 而非 0）')
ok('confirm_zero_surcharge=confirm_zero_surcharge' in inspect.getsource(_leave_mod.apply_leave),
   'apply_leave 真的把參數透傳下去')

print('\n' + '=' * 60)
print('✅ 全部通過 — 9 條請假入口的 0 元閘門 + 8 個審查缺陷')
print('=' * 60)
