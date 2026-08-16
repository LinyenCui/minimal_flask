"""
測試「改班次日期」— update_trip_date（現在態）/ update_completed_trip_date（過去態）

為什麼這兩支要特別測：
    日期被編在 unique_code 裡，而 unique_code 是
      · scheduler 把班次掉進 completed_trips 的去重鍵（ON CONFLICT DO NOTHING）
      · Render ↔ 本地同步的比對主鍵（ON CONFLICT DO UPDATE）
    只改 date 不改 code，最糟會靜默掉一筆已完成記錄（車資消失、沒有錯誤訊息）。
    所以重點不是「date 有沒有被改到」，是**連動的兩個欄位有沒有一起對**，
    以及**撞號時有沒有擋下來**。

    T1  recompute_unique_code 純函數（兩種格式 + 看不懂的要回 None）
    T2  現在態：temp / fixed 改日期，三個欄位一起變
    T3  現在態：撞號要擋（trips 沒有唯一索引，撞了不會報錯）
    T4  現在態：狀態/同日期/看不懂的格式要擋
    T5  過去態：改日期 + 原因寫 remarks（不進報表欄）+ 撞號要擋

全程 auto_commit=False + rollback，測試資料用 99xxx 高位 id，不污染生產資料。
"""
import sys
from datetime import date as _date, time as _time, timedelta

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from dotenv import load_dotenv
load_dotenv('/Users/linyancui/minimal_flask/.env')
load_dotenv('/Users/linyancui/minimal_flask/.env.dev', override=True)

from sqlalchemy import text

from database import Session
from rewrite.tools.trip import update_trip_date
from rewrite.tools.completed_trip import update_completed_trip_date
from rewrite.tools.trip_identity import iso_week_number, recompute_unique_code


def banner(label):
    print(f'\n{"=" * 60}\n# {label}\n{"=" * 60}')


def ok(cond, label):
    print(f'  {"✅" if cond else "❌"} {label}')
    assert cond, label


# ============================================================
banner('T1: recompute_unique_code 純函數')
# ============================================================
D = _date(2026, 8, 11)          # day_of_year=223, ISO week=33
ok(iso_week_number(D) == 33, f'2026-08-11 的 ISO 週 = 33（實際 {iso_week_number(D)}）')
ok(D.timetuple().tm_yday == 223, '2026-08-11 是第 223 天')

code, kind = recompute_unique_code('T_4178_20260810', D)
ok((code, kind) == ('T_4178_20260811', 'temp'), f'預約：只換日期段，trip_id 保留 → {code}')

code, kind = recompute_unique_code('51_222_33', D)
ok((code, kind) == ('51_223_33', 'fixed'), f'固定：換天序+週次，模板 id 保留 → {code}')

code, kind = recompute_unique_code('51_222_33', _date(2026, 1, 5))
ok(code == '51_5_2', f'跨年也對：2026-01-05 → {code}')

ok(recompute_unique_code(None, D) == (None, 'none'), '本來就沒 code → 不用維護')
ok(recompute_unique_code('', D) == (None, 'none'), '空字串同上')
for bad in ('亂七八糟', 'T_abc_20260811', '51_222', 'X_1_2_3'):
    ok(recompute_unique_code(bad, D) == (None, None), f'看不懂的格式 {bad!r} → 回 None 讓呼叫端擋')


s = Session()
made = []
try:
    drv = s.execute(text('SELECT id FROM drivers ORDER BY id LIMIT 1')).scalar()
    fsid = s.execute(text('SELECT id FROM fixed_schedules ORDER BY id LIMIT 1')).scalar()
    assert drv and fsid, '需要至少一位司機與一張模板當 FK'
    far = _date.today() + timedelta(days=30)      # 遠離 30 分鐘鎖
    tgt = far + timedelta(days=1)

    def mk_trip(tid, *, d, code, ttype, fixed_id=None, status='準備'):
        s.execute(text("""
            INSERT INTO trips (trip_id, date, time, start_point, end_point, category,
                               driver_id, status, meter_fare, extra_fare,
                               trip_type, unique_code, week_number, fixed_trip_id)
            VALUES (:id, :d, :t, '測試起點', '測試終點', '臨時', :drv, :st, 0, 0,
                    :tt, :code, :wk, :fid)
        """), {'id': tid, 'd': d, 't': _time(9, 0), 'drv': drv, 'st': status,
               'tt': ttype, 'code': code, 'wk': iso_week_number(d), 'fid': fixed_id})
        made.append(('trips', tid))
        return tid

    def trip_row(tid):
        return s.execute(text(
            'SELECT date, week_number, unique_code, modification_reason '
            'FROM trips WHERE trip_id=:i'), {'i': tid}).fetchone()

    # ========================================================
    banner('T2: 現在態改日期 — 三個欄位一起變')
    # ========================================================
    t_temp = mk_trip(99801, d=far, code=f"T_99801_{far.strftime('%Y%m%d')}", ttype='temp')
    r = update_trip_date(session=s, trip_id=t_temp, new_date=tgt,
                         reason='客戶改期', auto_commit=False)
    ok(r.ok, f'預約班次改日期成功{"" if r.ok else "：" + (r.error or "")}')
    d2, w2, c2, mod = trip_row(t_temp)
    ok(d2 == tgt, f'date → {d2}')
    ok(w2 == iso_week_number(tgt), f'week_number 跟著改 → {w2}')
    ok(c2 == f"T_99801_{tgt.strftime('%Y%m%d')}", f'unique_code 跟著改 → {c2}')
    # 原因政策：改日期不影響金額 → 不寫 modification_reason（那欄會被 scheduler
    # 複製進 completed_trips 而進請款報表）。軌跡在 audit_log。
    ok('改日期' not in (mod or ''),
       '現在態不寫 modification_reason（不污染報表說明欄）')
    _aud = s.execute(text(
        "SELECT action_type FROM audit_log WHERE target_table='trips' "
        "AND target_id=:i ORDER BY id DESC LIMIT 1"), {'i': t_temp}).scalar()
    ok(_aud == 'update_trip_date', f'軌跡記在 audit_log → {_aud}')

    t_fixed = mk_trip(99802, d=far, code=f"{fsid}_{far.timetuple().tm_yday}_{iso_week_number(far)}",
                      ttype='fixed', fixed_id=fsid)
    r = update_trip_date(session=s, trip_id=t_fixed, new_date=tgt,
                         reason='調班', auto_commit=False)
    ok(r.ok, f'固定班次改日期成功{"" if r.ok else "：" + (r.error or "")}')
    d3, w3, c3, _ = trip_row(t_fixed)
    ok(c3 == f"{fsid}_{tgt.timetuple().tm_yday}_{iso_week_number(tgt)}",
       f'固定班次的 code 換天序+週次 → {c3}')

    # 字串日期走 unified_date_parser
    r = update_trip_date(session=s, trip_id=t_temp, new_date=tgt.strftime('%-m/%-d'),
                         reason='測試', auto_commit=False)
    ok(not r.ok and '無需修改' in (r.error or ''),
       '字串日期解析得出來（已是該日期 → 回「無需修改」而不是格式錯）')

    # ========================================================
    banner('T3: 撞號要擋 — trips 沒有唯一索引，撞了不會報錯')
    # ========================================================
    # 已經有一筆佔用了 tgt 那天的 code
    occupied = f"T_99803_{tgt.strftime('%Y%m%d')}"
    mk_trip(99803, d=tgt, code=occupied, ttype='temp')
    t_clash = mk_trip(99804, d=far, code=occupied.replace(tgt.strftime('%Y%m%d'),
                                                          far.strftime('%Y%m%d')), ttype='temp')
    r = update_trip_date(session=s, trip_id=t_clash, new_date=tgt,
                         reason='測試', auto_commit=False)
    ok(not r.ok and '已經用了識別碼' in (r.error or ''),
       f'撞到 trips 既有 code → 擋下：{(r.error or "")[:40]}')

    # 撞到 completed_trips 也要擋（班次遲早會掉進去）
    done_code = s.execute(text(
        'SELECT unique_code FROM completed_trips WHERE unique_code IS NOT NULL LIMIT 1')).scalar()
    if done_code:
        newc, kind = recompute_unique_code(done_code, tgt)
        if kind in ('temp', 'fixed'):
            # 造一筆「改到 tgt 之後就會撞上那個已完成 code」的班次
            base = recompute_unique_code(done_code, far)[0]
            t_clash2 = mk_trip(99805, d=far, code=base, ttype='temp' if kind == 'temp' else 'fixed',
                               fixed_id=fsid if kind == 'fixed' else None)
            s.execute(text('UPDATE completed_trips SET unique_code=:c WHERE unique_code=:o'),
                      {'c': newc, 'o': done_code})
            r = update_trip_date(session=s, trip_id=t_clash2, new_date=tgt,
                                 reason='測試', auto_commit=False)
            ok(not r.ok and '已完成班次' in (r.error or ''),
               f'撞到 completed_trips 既有 code → 也擋下')
            s.execute(text('UPDATE completed_trips SET unique_code=:o WHERE unique_code=:c'),
                      {'c': newc, 'o': done_code})

    # ========================================================
    banner('T4: 該擋的都要擋')
    # ========================================================
    r = update_trip_date(session=s, trip_id=t_temp, new_date=tgt, reason='x', auto_commit=False)
    ok(not r.ok and '無需修改' in (r.error or ''), '同一個日期 → 擋')

    r = update_trip_date(session=s, trip_id=999999, new_date=tgt, reason='x', auto_commit=False)
    ok(not r.ok and '找不到' in (r.error or ''), '班次不存在 → 擋')

    r = update_trip_date(session=s, trip_id=t_temp, new_date='亂七八糟',
                         reason='x', auto_commit=False)
    ok(not r.ok and '看不懂' in (r.error or ''), '日期看不懂 → 擋')

    t_cancel = mk_trip(99806, d=far, code=f"T_99806_{far.strftime('%Y%m%d')}",
                       ttype='temp', status='註銷')
    r = update_trip_date(session=s, trip_id=t_cancel, new_date=tgt, reason='x', auto_commit=False)
    ok(not r.ok and '註銷' in (r.error or ''), '註銷的班次 → 擋')

    t_done = mk_trip(99807, d=far, code=f"T_99807_{far.strftime('%Y%m%d')}",
                     ttype='temp', status='已完成')
    r = update_trip_date(session=s, trip_id=t_done, new_date=tgt, reason='x', auto_commit=False)
    ok(not r.ok and '已完成' in (r.error or ''), '已完成的班次 → 擋（要走過去態那支）')

    t_weird = mk_trip(99808, d=far, code='這不是合法格式', ttype='temp')
    r = update_trip_date(session=s, trip_id=t_weird, new_date=tgt, reason='x', auto_commit=False)
    ok(not r.ok and '識別碼格式看不懂' in (r.error or ''),
       'code 格式看不懂 → 拒絕（寧可不改，也不要寫出半殘的身分證）')

    # ========================================================
    banner('T5: 過去態改日期')
    # ========================================================
    def mk_done(cid, *, d, code):
        s.execute(text("""
            INSERT INTO completed_trips (id, date, start_point, end_point, category,
                                         driver_id, meter_fare, extra_fare,
                                         trip_type, unique_code)
            VALUES (:id, :d, '測試起點', '測試終點', '東洋', :drv, 100, 0, 'temp', :code)
        """), {'id': cid, 'd': d, 'drv': drv, 'code': code})
        made.append(('completed_trips', cid))
        return cid

    c1 = mk_done(99811, d=far, code=f"T_99811_{far.strftime('%Y%m%d')}")
    r = update_completed_trip_date(session=s, completed_trip_id=c1, new_date=tgt,
                                   reason='客戶記錯日期', auto_commit=False)
    ok(r.ok, f'過去態改日期成功{"" if r.ok else "：" + (r.error or "")}')
    row = s.execute(text(
        'SELECT date, unique_code, remarks, modification_reason '
        'FROM completed_trips WHERE id=:i'), {'i': c1}).fetchone()
    ok(row[0] == tgt, f'date → {row[0]}')
    ok(row[1] == f"T_99811_{tgt.strftime('%Y%m%d')}", f'unique_code 跟著改 → {row[1]}')
    ok('改日期' in (row[2] or '') and '客戶記錯日期' in (row[2] or ''),
       f'原因寫進 remarks → {row[2]!r}')
    # 請款報表讀 modification_reason / passenger_leave_reason，不讀 remarks
    ok('改日期' not in (row[3] or ''),
       '不寫 modification_reason（那一欄會進請款報表）')

    # 原因是選填的（改日期不影響金額，確認卡就是防呆）
    r = update_completed_trip_date(session=s, completed_trip_id=c1,
                                   new_date=tgt + timedelta(days=1), reason='',
                                   auto_commit=False)
    ok(r.ok, f'過去態不給原因也能改（不影響金額）{"" if r.ok else "：" + (r.error or "")}')
    _rm = s.execute(text('SELECT remarks FROM completed_trips WHERE id=:i'),
                    {'i': c1}).scalar()
    ok('改日期' in (_rm or ''), '沒給原因時 remarks 仍記下日期變動')

    c2 = mk_done(99812, d=far, code=f"T_99812_{far.strftime('%Y%m%d')}")
    s.execute(text('UPDATE completed_trips SET unique_code=:c WHERE id=:i'),
              {'c': f"T_99812_{tgt.strftime('%Y%m%d')}", 'i': 99811})
    r = update_completed_trip_date(session=s, completed_trip_id=c2, new_date=tgt,
                                   reason='測試', auto_commit=False)
    ok(not r.ok and '已經用了識別碼' in (r.error or ''), '過去態撞號 → 擋（給看得懂的訊息）')

    print('\n' + '=' * 60)
    print('✅ 全部通過 — 改日期會連動 week_number + unique_code，撞號擋得住')
    print('=' * 60)
finally:
    s.rollback()
    s.close()
