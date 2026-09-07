"""
測試週扣款「補記舊週」

背景（2026-09-07 用戶回報）：
    第 34 週（8/23〜8/29）的診所扣款要在第 35 週按「記錄上週扣款」，用戶忘了。
    等到第 36 週才發現時，表單只會記第 35 週 —— 因為 occurred_at 被寫死成
    _last_saturday_2359()，**沒有任何參數可以指定週次**，補不回來。
    那一次只能直接改 PROD 的 account_ledger（手動補了 #95 / 26,060）。

    所以加一個「要記哪一週」的選單。用戶原話：「1.好了」（選了加週次參數）。

    T1  resolve_week_end 純函數（預設上週、字串、非星期六、未來週）
    T2  補記舊週：occurred_at / memo 都落在指定那一週
    T3  不給 week_end → 行為完全沒變（記上週）
    T4  防重複是「按週」算的，不是全域
    T5  prefill 回最近 8 週，且金額與 aggregate_completed_trips 同源

全程 auto_commit=False + rollback，不污染生產資料。
"""
import sys
from datetime import date as _date, timedelta

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from dotenv import load_dotenv
load_dotenv('/Users/linyancui/minimal_flask/.env')
load_dotenv('/Users/linyancui/minimal_flask/.env.dev', override=True)

from sqlalchemy import text

from database import Session
from rewrite.tools.accounting import (
    WEEKLY_CHARGE_HISTORY_WEEKS,
    _last_saturday,
    record_weekly_charge,
    resolve_week_end,
    weekly_charge_prefill,
)
from rewrite.tools.completed_trip import aggregate_completed_trips


def banner(label):
    print(f'\n{"=" * 62}\n# {label}\n{"=" * 62}')


def ok(cond, label):
    print(f'  {"✅" if cond else "❌"} {label}')
    assert cond, label


LAST_SAT = _last_saturday()

# ============================================================
banner('T1: resolve_week_end 純函數')
# ============================================================
ok(LAST_SAT.weekday() == 5, f'_last_saturday() 回的是星期六（{LAST_SAT}）')
ok(resolve_week_end(None) == (LAST_SAT, None), '不給 → 預設上週六')
ok(resolve_week_end('') == (LAST_SAT, None), '空字串 → 也是預設（表單沒選）')

older = LAST_SAT - timedelta(weeks=2)
ok(resolve_week_end(older) == (older, None), f'給舊的星期六 → 照收（{older}）')
ok(resolve_week_end(older.isoformat()) == (older, None), '字串日期也收（表單傳的是字串）')

d, err = resolve_week_end(LAST_SAT - timedelta(days=1))
ok(d is None and '不是星期六' in (err or ''), f'星期五 → 擋：{err}')

d, err = resolve_week_end(LAST_SAT + timedelta(weeks=1))
ok(d is None and '還沒過完' in (err or ''), f'未來的週 → 擋：{err}')

d, err = resolve_week_end('亂打')
ok(d is None and '格式看不懂' in (err or ''), f'壞格式 → 擋：{err}')


s = Session()
try:
    def balance():
        return int(s.execute(text(
            'SELECT COALESCE(SUM(amount_in),0) - COALESCE(SUM(amount_out),0) '
            'FROM account_ledger')).scalar() or 0)

    def ledger(lid):
        # ⚠️ 不要斷言 occurred_at 的絕對時刻：occurred_at 是 timestamptz，
        #    而工具寫入的是 naive 的「該週六 23:59」，落成哪個 UTC instant
        #    取決於 session 時區 —— 本地（+08）與 Render 差 8 小時。
        #    系統自己的判準是「AT TIME ZONE 'UTC' 之後的日期」（見
        #    find_weekly_charge_for_week），兩邊都落在同一天，所以測這個。
        return s.execute(text(
            "SELECT (occurred_at AT TIME ZONE 'UTC')::date AS week_end, "
            'amount_out, memo, type FROM account_ledger WHERE id = :i'),
            {'i': lid}).fetchone()

    # 挑一個「目前還沒記過扣款」的舊週當標的，避免撞到真資料的防重複
    target = None
    for i in range(1, WEEKLY_CHARGE_HISTORY_WEEKS + 4):
        cand = LAST_SAT - timedelta(weeks=i)
        n = s.execute(text(
            "SELECT COUNT(*) FROM account_ledger WHERE type='weekly_charge' "
            "AND (occurred_at AT TIME ZONE 'UTC')::date = :d"), {'d': cand}).scalar()
        if not n:
            target = cand
            break
    assert target, '找不到還沒記過扣款的舊週可以測'

    # ========================================================
    banner(f'T2: 補記舊週（{target}）')
    # ========================================================
    before_balance = balance()
    r = record_weekly_charge(session=s, amount=12345, week_end=target,
                            user_name='test', via='test', auto_commit=False)
    ok(r.ok, f'補記成功{"" if r.ok else "：" + (r.error or "")}')
    lid = r.data['ledger_id']
    row = ledger(lid)
    ok(row[0] == target,
       f'系統判準（AT TIME ZONE UTC 的日期）落在該週六 → {row[0]}')
    ok(r.data['occurred_at'] == f'{target.isoformat()}T23:59:00',
       f'鎖定時間是該週六 23:59 → {r.data["occurred_at"]}')
    ok(r.data['week_end_date'] == target.isoformat(), f'回傳的 week_end_date = {target}')
    ok(row[2] == f'週末 {target.isoformat()} 扣款',
       f'memo 與原本的格式一致 → {row[2]!r}')
    ok(row[3] == 'weekly_charge' and row[1] == 12345, 'type / 金額正確')
    ok(balance() == before_balance - 12345, '餘額扣掉了')

    # 字串形式（表單實際傳的）
    r_str = record_weekly_charge(session=s, amount=1, week_end=target.isoformat(),
                                 allow_duplicate=True, user_name='test', via='test',
                                 auto_commit=False)
    ok(r_str.ok and r_str.data['week_end_date'] == target.isoformat(),
       '字串型的 week_end 也走同一條路')

    # ========================================================
    banner('T3: 不給 week_end → 行為完全沒變（記上週）')
    # ========================================================
    existing_last = s.execute(text(
        "SELECT COUNT(*) FROM account_ledger WHERE type='weekly_charge' "
        "AND (occurred_at AT TIME ZONE 'UTC')::date = :d"), {'d': LAST_SAT}).scalar()
    r = record_weekly_charge(session=s, amount=999, allow_duplicate=True,
                            user_name='test', via='test', auto_commit=False)
    ok(r.ok, '不帶參數照樣可以記')
    ok(r.data['week_end_date'] == LAST_SAT.isoformat(),
       f'預設仍然是上週六 {LAST_SAT}（向後相容）')

    # ========================================================
    banner('T4: 防重複是「按週」算的')
    # ========================================================
    r = record_weekly_charge(session=s, amount=500, week_end=target,
                            user_name='test', via='test', auto_commit=False)
    ok(not r.ok and '已記過扣款' in (r.error or ''),
       f'同一週再記 → 擋：{(r.error or "")[:40]}')

    other = target - timedelta(weeks=1)
    n_other = s.execute(text(
        "SELECT COUNT(*) FROM account_ledger WHERE type='weekly_charge' "
        "AND (occurred_at AT TIME ZONE 'UTC')::date = :d"), {'d': other}).scalar()
    if not n_other:
        r = record_weekly_charge(session=s, amount=500, week_end=other,
                                user_name='test', via='test', auto_commit=False)
        ok(r.ok, f'換一週（{other}）→ 不受影響，照樣可記')

    r = record_weekly_charge(session=s, amount=0, week_end=target,
                            user_name='test', via='test', auto_commit=False)
    ok(not r.ok, '金額 0 照樣擋（沒被新參數繞過）')

    # ========================================================
    banner('T5: prefill 回最近 8 週，金額與 aggregate 同源')
    # ========================================================
    r = weekly_charge_prefill(session=s)
    ok(r.ok, 'prefill 成功')
    d = r.data
    ok(len(d['weeks']) == WEEKLY_CHARGE_HISTORY_WEEKS,
       f'回 {WEEKLY_CHARGE_HISTORY_WEEKS} 週（實際 {len(d["weeks"])}）')
    ok(d['weeks'][0]['week_end'] == LAST_SAT.isoformat(), '第一筆是上週（新到舊）')
    ok(all(_date.fromisoformat(w['week_end']).weekday() == 5 for w in d['weeks']),
       '每一筆的 week_end 都是星期六')
    ok(all(_date.fromisoformat(w['week_end']) - _date.fromisoformat(w['week_start'])
           == timedelta(days=6) for w in d['weeks']), '每週都是 7 天（日～六）')
    ends = [w['week_end'] for w in d['weeks']]
    ok(ends == sorted(ends, reverse=True) and len(set(ends)) == len(ends),
       '由新到舊、不重複')
    ok(d['week_end'] == d['weeks'][0]['week_end'],
       '沒指定週次 → 選定的就是最新那週（相容原本的欄位）')

    # 金額必須跟 aggregate_completed_trips 一致 —— 不可以另外寫一套 SQL
    # （fare_rules 那條規則就是因為多份實作出過兩次錯）
    for w in d['weeks'][:3]:
        agg = aggregate_completed_trips(
            session=s,
            date_from=_date.fromisoformat(w['week_start']),
            date_to=_date.fromisoformat(w['week_end']),
            category='診所')
        want = int(agg.data.get('sum_amount') or 0) if agg.ok else 0
        ok(w['total_amount'] == want,
           f"{w['week_end']} 金額 {w['total_amount']:,} = aggregate {want:,}")

    # 指定週次
    r2 = weekly_charge_prefill(session=s, week_end=target.isoformat())
    ok(r2.ok and r2.data['week_end'] == target.isoformat(),
       f'指定週次 → 選定 {target}')
    ok(len(r2.data['weeks']) == WEEKLY_CHARGE_HISTORY_WEEKS,
       '指定週次時清單照樣完整（切換不必再打 API）')
    ok(r2.data['existing_charge'] is not None,
       'T2 記過之後，該週的 existing_charge 撈得到（表單會標「已記」）')

    r3 = weekly_charge_prefill(session=s, week_end=LAST_SAT + timedelta(weeks=1))
    ok(not r3.ok and '還沒過完' in (r3.error or ''), 'prefill 也擋未來的週')

finally:
    s.rollback()
    s.close()

print('\n' + '=' * 62)
print('✅ 全部通過 — 週扣款可以補記舊週，預設行為不變')
print('=' * 62)
