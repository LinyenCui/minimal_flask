"""
測試 MultiSkillAgent — intent classifier 把訊息正確路由到對應 skill

⚠️ 此測試會：
  - 多次打 Gemini API（每個 case 至少 1 次 classify + 1 次 skill）
  - 不寫 DB（純測 routing 邏輯，DB write 在各 skill 自己的測試）
"""
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from rewrite.ai.intent import classify
from rewrite.ai.client import GeminiClient
from rewrite.ai.multi_skill_agent import build_default_multi_skill_agent


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


# ============================================================
# Part A: 純測 classifier 路由準確度
# ============================================================
banner('Part A: classify() 路由準確度')
llm = GeminiClient()
cases = [
    ('明天龍埔街的狀態', 'trip_query'),
    ('待派班次', 'trip_query'),
    ('班次詳情 1077', 'trip_query'),
    ('今天的診所班次', 'trip_query'),
    ('1077請假化療-30', 'trip_mutation'),
    ('99502註銷，客戶取消', 'trip_mutation'),
    ('指派司機533給1077', 'trip_mutation'),
    ('改回準備 99503', 'trip_mutation'),
    ('查太子龍', 'customer'),
    ('龍埔街是誰', 'customer'),
    ('新增客戶 王小明 龍哥 龍埔街', 'customer'),
    ('病歷層 15', 'customer'),
    ('病歷層分布', 'customer'),
    ('刪除客戶測試', 'customer'),
    ('匯入固定班次 本週', 'unknown'),
    ('預約明天下午兩點', 'unknown'),
    ('生成週報表', 'unknown'),
    ('你好嗎', 'unknown'),
]

correct = 0
for text, expected in cases:
    actual = classify(llm, text)
    ok = actual == expected
    correct += int(ok)
    mark = '✅' if ok else '❌'
    print(f'  {mark} {text!r:30} → {actual:<15} (預期 {expected})')

acc = correct / len(cases) * 100
print(f'\n準確率：{correct}/{len(cases)} ({acc:.0f}%)')

# ============================================================
# Part B: MultiSkillAgent 端到端
# ============================================================
banner('Part B: MultiSkillAgent 端到端 (3 個代表 case)')
agent = build_default_multi_skill_agent(llm=llm)

for text in ['今天診所班次', '查 龍埔街', '不認識的訊息']:
    print(f'\n→ 用戶說：{text!r}')
    msg = agent.process(text)
    t = msg.get('type')
    if t == 'text':
        print(f'  [text] {msg["text"][:200]}')
    elif t == 'flex':
        c = msg.get('contents', {})
        ct = c.get('type')
        if ct == 'bubble':
            h = c.get('header', {}).get('contents', [{}])[0].get('text', '')
            print(f'  [flex bubble] {h}')
        elif ct == 'carousel':
            n = len(c.get('contents', []))
            print(f'  [flex carousel] {n} bubbles')

print('\n' + '=' * 60)
print(f'✅ 測試完成；classifier 準確率 {acc:.0f}%')
print('=' * 60)
