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

    print('\n✅ 全部 pass')
finally:
    session.close()
