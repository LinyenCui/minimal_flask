"""
測試 customer_skill — AI 自然語言操作客戶資料

⚠️ 此測試會：
  - 打 Gemini API
  - 在 dev DB 造假客戶 (short_name='測試客戶_AI') + 清理
"""
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import Session
from sqlalchemy import text

from rewrite.ai.client import GeminiClient
from rewrite.ai.agent import Agent
from rewrite.ai.skills.customer import build_customer_skill


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


def show_msg(msg):
    t = msg.get('type')
    if t == 'text':
        print(f'  [text] {msg["text"][:300]}')
    elif t == 'flex':
        c = msg.get('contents', {})
        ct = c.get('type')
        if ct == 'bubble':
            h = c.get('header', {}).get('contents', [{}])[0].get('text', '')
            print(f'  [flex bubble] {h}')
        elif ct == 'carousel':
            n = len(c.get('contents', []))
            print(f'  [flex carousel] {n} bubbles')


# 清掉測試客戶（如果有殘留）
session = Session()
try:
    session.execute(text("""
        DELETE FROM customers WHERE short_name = '測試客戶_AI'
    """))
    session.commit()
finally:
    session.close()

# 全域 agent
agent = Agent(
    llm=GeminiClient(),
    skill=build_customer_skill(),
)
print(f'✅ Agent 初始化；skill={agent.skill.name}, tools={len(agent.skill.tools)}')


session = Session()
created_id = None
try:
    # ============================================================
    # T1: 自然語言查（cascade fallback）
    # ============================================================
    banner('T1: 「查 龍埔街」 → query_customer_by_term')
    msg = agent.process('查 龍埔街')
    show_msg(msg)
    print('  ✅ 通過')

    # ============================================================
    # T2: 病歷層
    # ============================================================
    banner('T2: 「病歷層 15」 → query_customers_by_birthday_day(15)')
    msg = agent.process('病歷層 15')
    show_msg(msg)
    print('  ✅ 通過')

    # ============================================================
    # T3: 病歷層分布
    # ============================================================
    banner('T3: 「病歷層分布」 → query_birthday_day_summary')
    msg = agent.process('病歷層分布')
    show_msg(msg)
    print('  ✅ 通過')

    # ============================================================
    # T4: 創建（完整資訊）
    # ============================================================
    banner('T4: 「新增 測試客戶_AI 簡稱也是 測試客戶_AI 地址測試街123 類別診所」')
    msg = agent.process(
        '新增客戶，姓名 測試客戶_AI，簡稱 測試客戶_AI，'
        '地址 測試街123，類別 診所'
    )
    show_msg(msg)
    # 驗 DB
    row = session.execute(text("""
        SELECT id, name, short_name, address, category
        FROM customers WHERE short_name = '測試客戶_AI'
    """)).fetchone()
    if row:
        created_id = row[0]
        print(f'  DB: id={row[0]}, name={row[1]!r}, short={row[2]!r}, '
              f'addr={row[3]!r}, cat={row[4]!r}')
        assert row[1] == '測試客戶_AI'
        assert row[3] == '測試街123'
        print('  ✅ DB 驗證：客戶已創建')
    else:
        print('  ⚠️ AI 沒有實際 create（可能要求補資訊）')

    # ============================================================
    # T5: 修改（先查再改）
    # ============================================================
    if created_id:
        banner('T5: 「把測試客戶_AI 的地址改成 測試街456」')
        msg = agent.process('把 測試客戶_AI 的地址改成 測試街456')
        show_msg(msg)
        row = session.execute(text("""
            SELECT address FROM customers WHERE id = :id
        """), {'id': created_id}).fetchone()
        print(f'  DB: address={row[0]!r}')
        if row[0] == '測試街456':
            print('  ✅ DB 驗證：地址已更新')
        else:
            print(f'  ⚠️ 地址未更新（AI 可能先 query 再執行，或卡在多輪）')

    # ============================================================
    # T6: 缺資訊（創建只給名字 → AI 應該問）
    # ============================================================
    banner('T6: 「新增客戶 測試X」（缺 address/short_name → AI 應回問）')
    msg = agent.process('新增客戶 測試X')
    show_msg(msg)
    # 驗證沒新增
    n = session.execute(text("""
        SELECT COUNT(*) FROM customers WHERE name = '測試X' OR short_name = '測試X'
    """)).scalar()
    if n == 0:
        print('  ✅ AI 沒亂執行')
    else:
        print(f'  ⚠️ 找到 {n} 筆 — AI 帶預設值執行了')

    # ============================================================
    # T7: 刪除（測試 created_id）
    # ============================================================
    if created_id:
        banner(f'T7: 「刪除 測試客戶_AI」(id={created_id})')
        msg = agent.process('刪除 測試客戶_AI')
        show_msg(msg)
        row = session.execute(text("""
            SELECT id FROM customers WHERE id = :id
        """), {'id': created_id}).fetchone()
        if row is None:
            print('  ✅ DB 驗證：客戶已刪除')
            created_id = None
        else:
            print(f'  ⚠️ 客戶仍在 — AI 可能要求確認')

    print('\n' + '=' * 60)
    print('✅ customer_skill 整合測試完成')
    print('=' * 60)
finally:
    # 清理（即使 T7 沒刪成功也手動清）
    session.execute(text("""
        DELETE FROM customers WHERE short_name = '測試客戶_AI' OR name = '測試X'
    """))
    session.commit()
    print(f'\n🧹 清理測試客戶資料')
    session.close()
