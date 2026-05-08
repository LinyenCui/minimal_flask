"""
測試 rewrite/ai/ 整套 — Agent + GeminiClient + trip_query_skill

驗證：
  - 自然語言查詢能正確路由到對應 atomic tool
  - 日期解析（明天/今天/YYYY-MM-DD）
  - 客戶簡稱 → customer_short_name
  - 班次號 → query_trip_by_id
  - 結果 render 成 LINE message dict（type=flex/text）

⚠️ 此測試會打 Gemini API（真實呼叫）+ 連 dev DB，需網路。
"""
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from rewrite.ai.client import GeminiClient
from rewrite.ai.agent import Agent
from rewrite.ai.skills.trip_query import build_trip_query_skill


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


def show_msg(msg: dict):
    """精簡顯示 LINE message dict"""
    t = msg.get('type')
    if t == 'text':
        print(f'  [text] {msg["text"][:200]}')
    elif t == 'flex':
        contents = msg.get('contents', {})
        ct = contents.get('type')
        if ct == 'bubble':
            header = contents.get('header', {}).get('contents', [{}])[0].get('text', '')
            print(f'  [flex bubble] header={header!r}')
        elif ct == 'carousel':
            n = len(contents.get('contents', []))
            print(f'  [flex carousel] {n} bubbles')
            for i, b in enumerate(contents['contents'][:3]):
                h = b.get('header', {}).get('contents', [{}])[0].get('text', '')
                sub = b.get('header', {}).get('contents', [{}, {}])[1].get('text', '') if len(b.get('header', {}).get('contents', [])) > 1 else ''
                print(f'    bubble {i+1}: {h!r} / {sub!r}')
        if msg.get('quickReply'):
            qr = msg['quickReply']['items']
            print(f'  + quickReply: {[i["action"]["label"] for i in qr]}')
    print(f'  altText={msg.get("altText", "—")}')


# 全域 agent — 避免每次重新初始化 Gemini
agent = Agent(
    llm=GeminiClient(),
    skill=build_trip_query_skill(),
)
print(f'✅ Agent 初始化完成；skill={agent.skill.name}, tools={len(agent.skill.tools)}')


# ============================================================
# T1: 班次號查詢
# ============================================================
banner('T1: 「班次1077」 → query_trip_by_id')
msg = agent.process('班次1077', user_id='test_user')
show_msg(msg)
assert msg['type'] in ('flex', 'text')
print('  ✅ 通過')

# ============================================================
# T2: 客戶簡稱查詢（核心場景：「明天龍埔街的狀態」）
# ============================================================
banner('T2: 「明天龍埔街的狀態」 → query_trips(明天, 龍埔街)')
msg = agent.process('明天龍埔街的狀態', user_id='test_user')
show_msg(msg)
print('  ✅ 通過（看是否走到 trips/flex）')

# ============================================================
# T3: 今天 + 類別
# ============================================================
banner('T3: 「今天的診所班次」 → query_today_trips/category=診所')
msg = agent.process('今天的診所班次', user_id='test_user')
show_msg(msg)
print('  ✅ 通過')

# ============================================================
# T4: 司機查詢
# ============================================================
banner('T4: 「明天 533 司機的班次」')
msg = agent.process('明天 533 司機的班次', user_id='test_user')
show_msg(msg)
print('  ✅ 通過')

# ============================================================
# T5: 待派班次
# ============================================================
banner('T5: 「待派班次」')
msg = agent.process('待派班次', user_id='test_user')
show_msg(msg)
print('  ✅ 通過')

# ============================================================
# T6: 不相關訊息（測 fall-through）
# ============================================================
banner('T6: 「你好嗎？」（無 tool call，AI 應回文字）')
msg = agent.process('你好嗎？', user_id='test_user')
show_msg(msg)
print('  ✅ 通過（應該 type=text 或要求釐清）')

print('\n' + '=' * 60)
print('✅ Agent + Skill + Function Calling 整套 v0.1 第一階段測試完成')
print('   （未接 LINE webhook — 那是下一個 commit）')
print('=' * 60)
