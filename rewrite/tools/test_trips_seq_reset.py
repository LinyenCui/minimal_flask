"""
測試 trips 序號自動歸位的新條件 + 過去週殘留清理

背景（2026-09-20 用戶：「我不會讓現在態的 id 到 5 位數」）：
    匯入流程早就有自動歸位（門檻 5000），但條件是「trips 表清空」——
    那永遠不會成立（分類別匯入、預約叫車的未來班次、別的類別的屍體），
    所以序號到了 5190 也從沒歸位。

    改成：**所有活著的列 id 都 ≥ 門檻** 就歸 1（跟表清空一樣安全：
    歸 1 後有 ≥ 門檻個號碼的跑道 ≈ 30 週，那時舊列早清光）。
    配套：每次匯入把「過去週 且 已完成／註銷」的列**不分類別**清掉，
    不然 7/30 那兩筆臨時的已完成（id 4020）會永遠壓住 MIN。

    T1  trips_sequence_can_reset 純函數
    T2  _purge_stale_trips：只清過去週的已完成／註銷，本週與準備一律不碰
    T3  _trips_sequence_state 解析到**真正的** sequence（*_seq1，不是孤兒 *_seq）
    T4  手動「重置班次序號」：有活著的低 id → 拒絕，且序號沒被動
    T5  匯入流程真的接上新規則（inspect，不跑整段匯入）

DB 部分 auto_commit=False + rollback；setval 不受 rollback 保護，所以
只測「拒絕」那條路，成功路徑靠 T1 的純函數。
"""
import inspect
import sys
from datetime import date as _date, time as _time, timedelta

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from dotenv import load_dotenv
load_dotenv('/Users/linyancui/minimal_flask/.env')
load_dotenv('/Users/linyancui/minimal_flask/.env.dev', override=True)

from sqlalchemy import text

from database import Session
from modules.utils.week_utils import calculate_target_week
from rewrite.tools import import_fixed as _if
from rewrite.tools.import_fixed import (
    SEQ_RESET_THRESHOLD,
    _purge_stale_trips,
    _trips_sequence_state,
    reset_trips_sequence,
    trips_sequence_can_reset,
)


def banner(label):
    print(f'\n{"=" * 62}\n# {label}\n{"=" * 62}')


def ok(cond, label):
    print(f'  {"✅" if cond else "❌"} {label}')
    assert cond, label


T = SEQ_RESET_THRESHOLD

# ============================================================
banner('T1: trips_sequence_can_reset 純函數')
# ============================================================
ok(trips_sequence_can_reset(min_live_id=None, next_val=T) is True,
   '表空 + 序號到門檻 → 可歸（舊行為保留）')
ok(trips_sequence_can_reset(min_live_id=T, next_val=T + 190) is True,
   f'活著的最小 id = 門檻 → 可歸（歸 1 後有 {T} 個號碼的跑道）')
ok(trips_sequence_can_reset(min_live_id=T + 100, next_val=T + 500) is True,
   '活著的全在門檻之上 → 可歸')
ok(trips_sequence_can_reset(min_live_id=4020, next_val=5190) is False,
   '★ 今天的實況：MIN 4020 < 5000 → 不可歸（7/30 那兩筆臨時的殘留壓住了）')
ok(trips_sequence_can_reset(min_live_id=None, next_val=T - 1) is False,
   '序號還沒到門檻 → 沒必要歸')
ok(trips_sequence_can_reset(min_live_id=10, next_val=T + 1) is False,
   '有低 id 活著 → 不可歸（歸 1 會撞它）')
ok(trips_sequence_can_reset(min_live_id=None, next_val=None) is False,
   '序號讀不到 → 不可歸')


s = Session()
try:
    drv = s.execute(text('SELECT id FROM drivers ORDER BY id LIMIT 1')).scalar()
    assert drv, '需要至少一位司機當 FK'
    today = _date.today()
    this_week_start, _, _ = calculate_target_week(today, 0)
    last_week = this_week_start - timedelta(days=1)        # 上週六（過去週）
    next_week = this_week_start + timedelta(days=8)

    def mk(tid, *, d, status, cat='診所'):
        s.execute(text("""
            INSERT INTO trips (trip_id, date, time, start_point, end_point, category,
                               driver_id, status, meter_fare, extra_fare,
                               trip_type, unique_code, week_number, fixed_trip_id)
            VALUES (:id, :d, :t, '測試起點', '測試終點', :cat, :drv, :st, 0, 0,
                    'temp', :code, :wk, NULL)
        """), {'id': tid, 'd': d, 't': _time(9, 0), 'cat': cat, 'drv': drv,
               'st': status, 'code': f"T_{tid}_{d.strftime('%Y%m%d')}",
               'wk': d.isocalendar()[1]})
        return tid

    def alive(tid):
        return s.execute(text('SELECT COUNT(*) FROM trips WHERE trip_id=:i'),
                         {'i': tid}).scalar() == 1

    # ========================================================
    banner('T2: _purge_stale_trips — 只清過去週的已完成／註銷')
    # ========================================================
    dead_done = mk(99801, d=last_week, status='已完成', cat='診所')
    dead_cancel = mk(99802, d=last_week, status='註銷', cat='東洋')
    stuck_ready = mk(99803, d=last_week, status='準備', cat='臨時')   # 不是本清理的事
    this_done = mk(99804, d=this_week_start, status='已完成')          # 本週：不碰
    future_ready = mk(99805, d=next_week, status='準備')

    n = _purge_stale_trips(session=s, before=this_week_start)
    ok(n >= 2, f'至少清掉 fixture 的兩筆（實際 {n}，含本地真實殘留）')
    ok(not alive(dead_done), '過去週 已完成（診所）→ 清掉')
    ok(not alive(dead_cancel), '過去週 註銷（東洋）→ 清掉（不分類別）')
    ok(alive(stuck_ready), '過去週 準備 → 不碰（那是 purge_past 的事，不是殘留清理）')
    ok(alive(this_done), '★ 本週的已完成 → 不碰（界線是本週週日，匯下週也不會誤刪）')
    ok(alive(future_ready), '未來的準備 → 不碰')

    real_left = s.execute(text(
        "SELECT COUNT(*) FROM trips WHERE date < :b AND status IN ('已完成','註銷')"),
        {'b': this_week_start}).scalar()
    ok(real_left == 0, '清完之後過去週沒有任何已完成／註銷殘留')

    # ========================================================
    banner('T3: _trips_sequence_state 解析到真正的 sequence')
    # ========================================================
    seq_name, next_val, min_id, cnt = _trips_sequence_state(s)
    ok(seq_name and seq_name.endswith('trips_trip_id_seq1'),
       f'pg_get_serial_sequence → {seq_name}（不是寫死的孤兒 trips_trip_id_seq）')
    ok(isinstance(next_val, int) and next_val > 0, f'序號值 {next_val}')
    ok(min_id is not None and min_id <= 99803, f'MIN(trip_id) 含 fixture → {min_id}')
    ok(cnt >= 3, f'COUNT 含 fixture → {cnt}')

    # ========================================================
    banner('T4: 手動重置 — 有活著的低 id → 拒絕，序號不動')
    # ========================================================
    low = mk(10, d=next_week, status='準備')     # 一筆 id=10 活著（低於門檻）
    before_seq = s.execute(text(f'SELECT last_value FROM {seq_name}')).scalar()
    r = reset_trips_sequence(session=s)
    ok(not r.ok, f'拒絕：{(r.error or "")[:60]}')
    ok('最小 id #10' in (r.error or '') or '門檻' in (r.error or ''),
       '訊息講清楚是哪筆低 id 擋住、以及門檻')
    after_seq = s.execute(text(f'SELECT last_value FROM {seq_name}')).scalar()
    ok(before_seq == after_seq, f'序號沒被動（{before_seq} → {after_seq}）')

    # ========================================================
    banner('T5: 匯入流程真的接上新規則')
    # ========================================================
    src = inspect.getsource(_if.import_fixed_to_trips)
    ok('_purge_stale_trips(' in src, '匯入會呼叫殘留清理')
    ok('trips_sequence_can_reset(' in src, '匯入的歸位用共用規則')
    ok('remaining == 0' not in src, '舊的「表清空」條件已移除')
    ok('calculate_target_week(today, 0)' in src,
       '殘留清理的界線是本週（不是匯入目標週）')
    rsrc = inspect.getsource(reset_trips_sequence)
    ok('trips_sequence_can_reset(' in rsrc, '手動指令用同一條規則')
    ok('COUNT(*) FROM trips")).scalar()\n    if count' not in rsrc,
       '手動指令不再要求表清空')

finally:
    s.rollback()
    s.close()

print('\n' + '=' * 62)
print('✅ 全部通過 — 序號歸位條件改為「活著的都過門檻」，殘留會被清')
print('=' * 62)
