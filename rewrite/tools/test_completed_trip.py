"""
測試 completed_trips 查詢工具（純函數，無 Flask）

對照 0013.txt log 的實機 demo 結果，驗證本地 DB 行為一致：
  /4/21司機5386班次          → 1 筆（trip_id=820, 東洋）
  /4/26-5/2東洋班次          → 10 筆 list
  /4/26-5/2東洋班次加總       → total=10, sum=8800
  /4/26-5/2診所班次加總       → total=86, sum=19215
  /4/26-5/2司機5386診所班次   → 12 筆
  /4/26-5/2司機533診所班次    → 36 筆

⚠️ 本地 sum 跟 production 可能不一致（用戶確認是同步腳本問題，不影響規格）。
"""
import sys
from datetime import date
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import Session
from rewrite.tools.completed_trip import (
    query_completed_trips,
    query_completed_trip_by_id,
    aggregate_completed_trips,
    CompletedTripView,
)


def banner(label):
    print(f'\n{"=" * 60}\n# {label}\n{"=" * 60}')


def _short(view: CompletedTripView) -> str:
    fare = f"{view.computed_total}元" if view.computed_total is not None else '未記錄'
    return (
        f'#{view.id} {view.date} {view.short_route()} '
        f'司機{view.driver_id or "?"} {view.category or "?"} {fare}'
    )


session = Session()
try:
    # ============================================================
    # T1: 單筆查詢（對應 legacy「查看 820」）
    # ============================================================
    banner('T1: query_completed_trip_by_id(820)')
    r = query_completed_trip_by_id(820, session=session)
    if r.ok:
        t = r.data
        print(f'  {_short(t)}')
        print(f'  meter={t.meter_fare} extra={t.extra_fare} actual={t.actual_fare}')
        print(f'  computed_total={t.computed_total} has_fare={t.has_fare}')
        print(f'  trip_type={t.trip_type} unique_code={t.unique_code}')
        print(f'  modification_reason={t.modification_reason!r}')
    else:
        print(f'  ❌ {r.error}')

    # ============================================================
    # T2: 不存在 ID
    # ============================================================
    banner('T2: query_completed_trip_by_id(99999999) — 應失敗')
    r = query_completed_trip_by_id(99999999, session=session)
    print(f'  ok={r.ok} error={r.error!r}')
    assert not r.ok

    # ============================================================
    # T3: 範圍 + driver_id（對應 /4/21司機5386班次）
    # ============================================================
    banner('T3: query_completed_trips(4/21, driver=5386)')
    r = query_completed_trips(
        session=session,
        date_from=date(2026, 4, 21),
        date_to=date(2026, 4, 21),
        driver_id=5386,
    )
    if r.ok:
        print(f'  {len(r.data)} 筆 (預期 1 筆 from log)')
        for t in r.data:
            print(f'    {_short(t)}')
    else:
        print(f'  ❌ {r.error}')

    # ============================================================
    # T4: 範圍 + category（對應 /4/26-5/2東洋班次）
    # ============================================================
    banner('T4: query_completed_trips(4/26-5/2, category=東洋)')
    r = query_completed_trips(
        session=session,
        date_from=date(2026, 4, 26),
        date_to=date(2026, 5, 2),
        category='東洋',
    )
    if r.ok:
        print(f'  {len(r.data)} 筆 (log demo: 10 筆)')
        # 列前 3
        for t in r.data[:3]:
            print(f'    {_short(t)}')
    else:
        print(f'  ❌ {r.error}')

    # ============================================================
    # T5: 範圍 + driver + category（對應 /4/26-5/2司機5386診所班次）
    # ============================================================
    banner('T5: query_completed_trips(4/26-5/2, driver=5386, category=診所)')
    r = query_completed_trips(
        session=session,
        date_from=date(2026, 4, 26),
        date_to=date(2026, 5, 2),
        driver_id=5386,
        category='診所',
    )
    if r.ok:
        print(f'  {len(r.data)} 筆 (log demo: 12 筆)')
    else:
        print(f'  ❌ {r.error}')

    # ============================================================
    # T6: aggregate 東洋（對應 /4/26-5/2東洋班次加總）
    # ============================================================
    banner('T6: aggregate_completed_trips(4/26-5/2, category=東洋)')
    r = aggregate_completed_trips(
        session=session,
        date_from=date(2026, 4, 26),
        date_to=date(2026, 5, 2),
        category='東洋',
    )
    if r.ok:
        d = r.data
        print(f"  total={d['total_count']} filled={d['filled_count']} "
              f"unfilled={d['unfilled_count']} sum={d['sum_amount']}")
        print(f"  (log demo: total=10 filled=10 sum=8800)")
    else:
        print(f'  ❌ {r.error}')

    # ============================================================
    # T7: aggregate 診所（對應 /4/26-5/2診所班次加總）
    # ============================================================
    banner('T7: aggregate_completed_trips(4/26-5/2, category=診所)')
    r = aggregate_completed_trips(
        session=session,
        date_from=date(2026, 4, 26),
        date_to=date(2026, 5, 2),
        category='診所',
    )
    if r.ok:
        d = r.data
        print(f"  total={d['total_count']} filled={d['filled_count']} "
              f"unfilled={d['unfilled_count']} sum={d['sum_amount']}")
        print(f"  (log demo: total=86 filled=86 sum=19215)")

    # ============================================================
    # T8: location ILIKE
    # ============================================================
    banner('T8: query_completed_trips(4/26-5/2, location=東洋) — ILIKE')
    r = query_completed_trips(
        session=session,
        date_from=date(2026, 4, 26),
        date_to=date(2026, 5, 2),
        location='東洋',
    )
    if r.ok:
        print(f'  {len(r.data)} 筆（ILIKE 比對 start/via/end）')
        # 抓前 2 看是否含「東洋」
        for t in r.data[:2]:
            print(f'    {_short(t)}')

    # ============================================================
    # T9: has_fare=False（找未記錄車資）
    # ============================================================
    banner('T9: query_completed_trips(2026-01-01..今天, has_fare=False)')
    r = query_completed_trips(
        session=session,
        date_from=date(2026, 1, 1),
        date_to=date.today(),
        has_fare=False,
        limit=20,
    )
    if r.ok:
        print(f'  {len(r.data)} 筆未記錄車資')
        for t in r.data[:5]:
            print(f'    {_short(t)}')
    else:
        print(f'  ✅ {r.error}（沒未記錄是好事）')

    # ============================================================
    # T10: View / 渲染煙霧測試
    # ============================================================
    banner('T10: render flex (smoke)')
    from rewrite.views.completed_trip_flex import (
        render_completed_trip_detail,
        render_completed_trip_list_carousel,
        render_aggregate_card,
    )

    r = query_completed_trip_by_id(820, session=session)
    if r.ok:
        b = render_completed_trip_detail(r.data)
        print(f'  detail bubble keys: {list(b.keys())}')
        assert b['type'] == 'bubble'

    r = query_completed_trips(
        session=session,
        date_from=date(2026, 4, 26), date_to=date(2026, 5, 2),
        category='東洋',
    )
    if r.ok:
        c = render_completed_trip_list_carousel(r.data)
        print(f'  list type: {c["type"]}')

    r = aggregate_completed_trips(
        session=session,
        date_from=date(2026, 4, 26), date_to=date(2026, 5, 2),
        category='東洋',
    )
    if r.ok:
        b = render_aggregate_card(r.data, filters_text='4/26~5/2 · 東洋')
        print(f'  aggregate bubble keys: {list(b.keys())}')

    # ============================================================
    # T11: query_reconciliation_text 對帳單格式
    # tx 內 seed 假資料（遠未來日期，避開真資料）→ 驗格式 → rollback
    # ============================================================
    banner('T11: query_reconciliation_text 對帳單格式（tx 內 seed + rollback）')
    from sqlalchemy import text as _sqltext
    from rewrite.tools.completed_trip import (
        query_reconciliation_text,
        ReconciliationTextView,
    )

    T11_FROM, T11_TO = date(2035, 1, 5), date(2035, 1, 11)
    # 前置：確認該範圍沒真資料（有的話 seed 斷言會失真）
    r = query_reconciliation_text(
        session=session, date_from=T11_FROM, date_to=T11_TO,
    )
    assert not r.ok, f'2035/1/5-1/11 不該有真資料（有 {r.meta.get("count")} 筆）'

    def _seed(d, sp, ep, mf, ef, cat, drv, leave, code):
        return session.execute(_sqltext("""
            INSERT INTO completed_trips
            (date, start_point, via_point, end_point, meter_fare, extra_fare,
             category, driver_id, unique_code, trip_type, passenger_leave_reason)
            VALUES (:d, :sp, NULL, :ep, :mf, :ef, :cat, :drv, :code, 'temp', :leave)
            RETURNING id
        """), {'d': d, 'sp': sp, 'ep': ep, 'mf': mf, 'ef': ef,
               'cat': cat, 'drv': drv, 'code': code, 'leave': leave}).fetchone()[0]

    id1 = _seed(date(2035, 1, 8), '萬年七街', '太子龍', 330, 0,
                '東洋', 28530, None, 'test_recon_1')
    id2 = _seed(date(2035, 1, 8), '健康三街', '建平七街', 0, -30,
                '東洋', 28530, '住院', 'test_recon_2')
    id3 = _seed(date(2035, 1, 10), '超過十個字的超長起點地名截斷', '太子龍', 500, 50,
                '東洋', 28530, None, 'test_recon_3')
    id4 = _seed(date(2035, 1, 9), '診所', '馬鎮宮', 999, 0,
                '診所', 533, None, 'test_recon_4')  # 不同司機+類別 → 應被 filter 掉

    # date coerce：字串日期也要吃（AI 傳 'YYYY-MM-DD'）
    r = query_reconciliation_text(
        session=session, date_from='2035-01-05', date_to='2035-01-11',
        driver_id='28530',  # int coerce
        category='東洋',
    )
    assert r.ok, r.error
    view = r.data
    assert isinstance(view, ReconciliationTextView)
    txt = view.text
    print(txt)
    assert '📋 對帳單 2035/1/5～1/11' in txt
    assert '司機 28530｜東洋' in txt
    assert '──────────' in txt
    assert '1/8（一）' in txt and '1/10（三）' in txt   # 按日期分段 + 星期
    assert f'#{id1} 萬年七街→太子龍 330' in txt
    assert f'#{id2} 健康三街→建平七街 請假 -30' in txt  # 請假標記 + 金額照列
    assert '…' in txt                                    # 超長地點截斷
    assert f'#{id4}' not in txt                          # 司機/類別 filter 生效
    assert '共 3 筆' in txt
    assert '合計 850 元' in txt                           # 330 + (-30) + 550
    assert view.count == 3 and view.total_amount == 850
    # to_dict（給 LLM 的摘要）不含全文
    d = view.to_dict()
    assert d['count'] == 3 and d['total_amount'] == 850
    assert len(d['preview']) <= 200

    # 無 filter（撈全部 4 筆，無第二行 header）
    r = query_reconciliation_text(
        session=session, date_from=T11_FROM, date_to=T11_TO,
    )
    assert r.ok and r.data.count == 4
    assert f'#{id4} 診所→馬鎮宮 999' in r.data.text

    # 無效類別 → fail
    r = query_reconciliation_text(
        session=session, date_from=T11_FROM, date_to=T11_TO, category='飛機',
    )
    assert not r.ok and '無效' in r.error

    # 缺日期 → fail
    r = query_reconciliation_text(session=session, date_from=None, date_to=None)
    assert not r.ok

    session.rollback()  # T11 seed 全部還原
    print('  ✅ T11 pass（seed 已 rollback）')

    # ============================================================
    # T12: split_text_for_line 5000 字切分（純函數）
    # ============================================================
    banner('T12: split_text_for_line 切分邏輯（純函數）')
    from rewrite.tools.completed_trip import split_text_for_line

    # 短文 → 1 則
    chunks, overflow = split_text_for_line('hello\nworld')
    assert chunks == ['hello\nworld'] and not overflow

    # 多行長文 → 多則、各 ≤4900、在換行處切（每則第一行是完整一列）
    line = '#1234 萬年七街→太子龍 330'
    big = '\n'.join(f'{line} {i}' for i in range(400))
    chunks, overflow = split_text_for_line(big)
    print(f'  {len(big)} 字 → {len(chunks)} 則, overflow={overflow}')
    assert not overflow and len(chunks) >= 2
    assert all(len(c) <= 4900 for c in chunks)
    assert '\n'.join(chunks) == big          # 內容不掉字
    for c in chunks:
        assert c.split('\n')[0].startswith('#1234')  # 不把一筆切兩半

    # 單行超長 → hard-split，內容不掉字
    mono = 'x' * 10000
    chunks, overflow = split_text_for_line(mono)
    assert not overflow and len(chunks) == 3  # 4900 + 4900 + 200
    assert ''.join(chunks) == mono

    # 超過 5 則塞不下 → overflow=True，只回前 5 則
    huge = '\n'.join(f'{line} {i}' for i in range(2000))
    chunks, overflow = split_text_for_line(huge)
    print(f'  {len(huge)} 字 → {len(chunks)} 則, overflow={overflow}')
    assert overflow and len(chunks) == 5
    assert all(len(c) <= 4900 for c in chunks)
    print('  ✅ T12 pass')

    print('\n✅ 全部 pass')
finally:
    session.close()
