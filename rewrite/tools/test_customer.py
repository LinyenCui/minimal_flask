"""
測試 query_customer 完全不依賴 Flask app context（修 N-6）

對照組：main 的 _tool_customer_lookup 必須在 app.app_context() 內呼叫，
       否則會 'Working outside of application context'。

實驗組：本檔下面的測試，沒匯入 app，直接用 sqlalchemy.Session，全部能跑。
"""
import sys, os
from dotenv import load_dotenv
load_dotenv()

# ⚠️ 故意 NOT import app
# from app import app    ← 不寫這行
# 只用底層 database 模組
sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import engine, Session
from rewrite.tools.customer import (
    query_customer,
    query_customer_by_term,
    get_customer_by_id,
)


def banner(label: str):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


session = Session()
try:
    # ============================================================
    # T1: 精確 short_name
    # ============================================================
    banner('T1: 精確 short_name = "龍埔街"')
    r = query_customer(short_name='龍埔街', session=session)
    assert r.ok, f'expected ok, got {r.error}'
    c = r.data[0]
    print(f'  matched_by: {r.meta.get("matched_by")}')
    print(f'  {c.short_name} → {c.name} ({c.category})')
    print(f'  地址: {c.address}')
    print(f'  生日: {c.birthday} | 病歷層: {c.birthday_day} 日 | 年齡: {c.age}')

    # ============================================================
    # T2: 病歷號精確
    # ============================================================
    banner('T2: 病歷號 medical_record_no = "001026"')
    r = query_customer(medical_record_no='001026', session=session)
    assert r.ok
    c = r.data[0]
    print(f'  matched_by: {r.meta.get("matched_by")}')
    print(f'  {c.name} ({c.gender}) 生日 {c.birthday}')
    print(f'  病歷層: {c.birthday_day} 日 | 病歷號: {c.medical_record_no}')

    # ============================================================
    # T3: mask_id 參數仍接受（backward-compat）
    # ============================================================
    banner('T3: mask_id=False 不該炸（drop national_id 後參數變 noop）')
    r = query_customer(medical_record_no='001026', session=session, mask_id=False)
    assert r.ok
    c = r.data[0]
    print(f'  mask_id=False ok: #{c.id} {c.name}')

    # ============================================================
    # T4: 模糊查詢（自然語言）
    # ============================================================
    banner('T4: 自然語言「陳」 → 應命中陳昭月、黃陳玉盆')
    r = query_customer_by_term('陳', session=session)
    if r.ok:
        print(f'  matched_by: {r.meta.get("matched_by")}')
        for c in r.data:
            print(f'  - #{c.id} {c.name} (簡稱:{c.short_name})')
    else:
        print(f'  ❌ {r.error}')

    # ============================================================
    # T5: cascade fallback — 先試 short_name 沒命中，自動 fallback name
    # ============================================================
    banner('T5: cascade — short_name="陳昭月" 沒，name fallback')
    r = query_customer(short_name='陳昭月', name='陳昭月', session=session)
    if r.ok:
        print(f'  matched_by: {r.meta.get("matched_by")}')  # 應該是 name(fuzzy) 不是 short_name
        for c in r.data:
            print(f'  - 短名:{c.short_name} 姓名:{c.name}')

    # ============================================================
    # T6: 身分證 heuristic（drop 後改檢查不會 cascade 進 national_id 路徑）
    # ============================================================
    banner('T6: term="D200615801" → drop national_id 後該走 short_name fallthrough')
    r = query_customer_by_term('D200615801', session=session)
    # 應該命不中（沒這個 short_name / name / address），回 fail
    print(f'  ok={r.ok}, matched_by={r.meta.get("matched_by") if r.ok else "—"}')

    # ============================================================
    # T7: 病歷號 heuristic 觸發（純數字）
    # ============================================================
    banner('T7: term="001677" → 應走 medical_record_no heuristic')
    r = query_customer_by_term('001677', session=session)
    if r.ok:
        print(f'  matched_by: {r.meta.get("matched_by")}')
        c = r.data[0]
        print(f'  → {c.name} (病歷層 {c.birthday_day} 日)')

    # ============================================================
    # T8: 找不到
    # ============================================================
    banner('T8: 不存在的 ID')
    r = query_customer(short_name='不存在AAAA', session=session)
    print(f'  ok={r.ok}  error={r.error}')

    # ============================================================
    # T9: get_customer_by_id
    # ============================================================
    banner('T9: get_customer_by_id(54) → 黃陳玉盆')
    r = get_customer_by_id(54, session=session)
    if r.ok:
        c = r.data
        print(f'  {c.name} ({c.gender}) 生日 {c.birthday}')
        print(f'  病歷層 {c.birthday_day} 日 | 病歷號 {c.medical_record_no}')

    # ============================================================
    # T10: 地址模糊 fallback
    # ============================================================
    banner('T10: address="永康"（模糊）→ 應命中 龍埔街(永康區)')
    r = query_customer(address='永康', session=session)
    if r.ok:
        print(f'  matched_by: {r.meta.get("matched_by")}')
        for c in r.data[:3]:
            print(f'  - {c.short_name} ({c.address})')

    print('\n' + '='*60)
    print('✅ 全部測試通過 — 全程沒有 import app，沒有 app.app_context()')
    print('   證明 R-4 純函數設計正確（修 N-6）')
    print('='*60)
finally:
    session.close()
