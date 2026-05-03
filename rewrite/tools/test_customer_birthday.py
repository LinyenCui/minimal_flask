"""
測試生日層查詢（病歷層）

業務情境：
  門診人員需要找某客戶的病歷時，知道生日的「日」就能快速定位病歷層級。
  此工具反向查詢：給定一個日，列出該層所有客戶。
"""
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import Session
from rewrite.tools.customer import (
    query_customers_by_birthday_day,
    query_birthday_day_summary,
)


def banner(label: str):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


session = Session()
try:
    # ============================================================
    # T1: 病歷層總覽
    # ============================================================
    banner('T1: 病歷層總覽（哪幾層有人）')
    r = query_birthday_day_summary(session=session)
    assert r.ok
    print(f'  共 {r.meta["total_layers"]} 層、{r.meta["total_customers_with_birthday"]} 個有生日的客戶')
    print(f'  分布：')
    for day, cnt in r.data:
        bar = '█' * cnt
        print(f'    {day:2d} 日: {bar} ({cnt})')

    # ============================================================
    # T2: 用戶提的查詢「生日是 18 號的客戶」
    # ============================================================
    banner('T2: 查 day=18（用戶提的範例）')
    r = query_customers_by_birthday_day(day=18, session=session)
    if r.ok:
        print(f'  共 {len(r.data)} 筆')
        for c in r.data:
            print(f'    #{c.id} {c.name} 生日 {c.birthday}')
    else:
        print(f'  {r.error}')

    # ============================================================
    # T3: 已知有資料的層（5 個範例患者）
    # ============================================================
    print('\n' + '='*60)
    print('# T3: 我們現有 5 個範例患者各自所在的層')
    print('='*60)
    for day in [23, 26, 1, 17, 13]:
        r = query_customers_by_birthday_day(day=day, session=session)
        if r.ok:
            for c in r.data:
                print(f'  day={day:2d} → #{c.id} {c.name} ({c.gender}) 生日 {c.birthday}'
                      f'  病歷號 {c.medical_record_no}')
        else:
            print(f'  day={day:2d} → {r.error}')

    # ============================================================
    # T4: 邊界值測試
    # ============================================================
    banner('T4: 邊界值')
    for day in [0, 32, -1, 'abc']:
        r = query_customers_by_birthday_day(day=day, session=session)
        assert not r.ok
        print(f'  day={day!r} → 拒絕：{r.error}')

    # ============================================================
    # T5: 邊界值（合法但無資料）
    # ============================================================
    banner('T5: 完全沒人在的層 (e.g. day=31)')
    r = query_customers_by_birthday_day(day=31, session=session)
    print(f'  day=31 → ok={r.ok} {r.error if not r.ok else r.data}')

    print('\n' + '='*60)
    print('✅ 病歷層查詢工具運作正常')
    print('='*60)
finally:
    session.close()
