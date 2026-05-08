"""
測試 trip_mutation_skill — AI 自然語言觸發 mutation

⚠️ 此測試會：
  - 打 Gemini API
  - 在 dev DB 造假 trip（99501-99504）跑 mutation 後清理
  - 寫 audit_log 後清理
"""
import sys
from datetime import date, datetime, timedelta, time as dt_time
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import Session
from sqlalchemy import text

from rewrite.ai.client import GeminiClient
from rewrite.ai.agent import Agent
from rewrite.ai.skills.trip_mutation import build_trip_mutation_skill


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


def show_msg(msg):
    t = msg.get('type')
    if t == 'text':
        print(f'  [text] {msg["text"][:200]}')
    elif t == 'flex':
        c = msg.get('contents', {})
        if c.get('type') == 'bubble':
            h = c.get('header', {}).get('contents', [{}])[0].get('text', '')
            print(f'  [flex bubble] {h}')


# ============================================================
# 準備：建 4 個假 trips
# ============================================================
session = Session()
fake_ids = [99501, 99502, 99503, 99504]
try:
    now = datetime.now()
    target_time = (now + timedelta(minutes=120)).time().replace(microsecond=0)
    today = now.date()

    for tid in fake_ids:
        session.execute(text("DELETE FROM trips WHERE trip_id = :id"), {'id': tid})
    session.execute(text("""
        INSERT INTO trips (trip_id, date, time, start_point, end_point,
                           category, status, driver_id, meter_fare, extra_fare,
                           passenger_name)
        VALUES
        (99501, :d, :t, '龍埔街', '診所', '診所', '準備', 533, 340, 0, '甲患者'),
        (99502, :d, :t, '龍埔街', '診所', '診所', '準備', 533, 340, 0, NULL),
        (99503, :d, :t, '龍埔街', '診所', '診所', '註銷', 533, 340, 0, NULL),
        (99504, :d, :t, '龍埔街', '診所', '診所', '待派', NULL, 340, 0, NULL)
    """), {'d': today, 't': target_time})
    session.commit()
    print(f'✅ 建好 4 個假 trips (#{fake_ids})')
finally:
    session.close()


# 全域 agent
agent = Agent(
    llm=GeminiClient(),
    skill=build_trip_mutation_skill(),
)
print(f'✅ Agent 初始化；skill={agent.skill.name}, tools={len(agent.skill.tools)}')

session = Session()
try:
    # ============================================================
    # T1: 完整一句請假
    # ============================================================
    banner('T1: 「班次 99501 請假，化療，加成 -30」')
    msg = agent.process('班次 99501 請假，化療，加成 -30')
    show_msg(msg)
    # 驗證 DB
    row = session.execute(text("""
        SELECT status, passenger_leave_reason, extra_fare
        FROM trips WHERE trip_id = 99501
    """)).fetchone()
    print(f'  DB: status={row[0]}, leave={row[1]!r}, extra={row[2]}')
    assert row[0] == '準備' and row[1] == '化療' and row[2] == -30, '請假未生效'
    print('  ✅ DB 驗證：三層障眼法生效')

    # ============================================================
    # T2: 註銷
    # ============================================================
    banner('T2: 「班次 99502 註銷，客戶取消」')
    msg = agent.process('班次 99502 註銷，客戶取消')
    show_msg(msg)
    row = session.execute(text("SELECT status FROM trips WHERE trip_id = 99502")).fetchone()
    print(f'  DB: status={row[0]}')
    assert row[0] == '註銷'
    print('  ✅ DB 驗證：註銷生效')

    # ============================================================
    # T3: 改回準備
    # ============================================================
    banner('T3: 「把 99503 改回準備」')
    msg = agent.process('把 99503 改回準備')
    show_msg(msg)
    row = session.execute(text("SELECT status FROM trips WHERE trip_id = 99503")).fetchone()
    print(f'  DB: status={row[0]}')
    assert row[0] == '準備'
    print('  ✅ DB 驗證：改回準備生效')

    # ============================================================
    # T4: 指派司機（待派 → 準備）
    # ============================================================
    banner('T4: 「99504 指派司機 5386」')
    msg = agent.process('99504 指派司機 5386')
    show_msg(msg)
    row = session.execute(text("SELECT status, driver_id FROM trips WHERE trip_id = 99504")).fetchone()
    print(f'  DB: status={row[0]}, driver_id={row[1]}')
    assert row[0] == '準備' and row[1] == 5386
    print('  ✅ DB 驗證：指派 + 升級為準備')

    # ============================================================
    # T5: 改乘客名
    # ============================================================
    banner('T5: 「把 99501 的乘客改成 王小明」')
    msg = agent.process('把 99501 的乘客改成 王小明')
    show_msg(msg)
    row = session.execute(text("SELECT passenger_name FROM trips WHERE trip_id = 99501")).fetchone()
    print(f'  DB: passenger_name={row[0]!r}')
    assert row[0] == '王小明'
    print('  ✅ DB 驗證：改名生效')

    # ============================================================
    # T6: 缺資訊（請假沒給數字）— AI 應該要問，不該亂呼叫
    # ============================================================
    banner('T6: 「99502 請假化療」（缺 surcharge → AI 應回問或不執行）')
    # 先把 99502 從註銷改回準備（T2 改了）
    session.execute(text("""
        UPDATE trips SET status='準備', passenger_leave_reason=NULL, extra_fare=0
        WHERE trip_id = 99502
    """))
    session.commit()

    msg = agent.process('99502 請假化療')
    show_msg(msg)
    # 驗證：99502 不應該被改成請假狀態（因為 AI 沒拿到 surcharge）
    row = session.execute(text("""
        SELECT status, passenger_leave_reason FROM trips WHERE trip_id = 99502
    """)).fetchone()
    print(f'  DB: status={row[0]}, leave={row[1]!r}')
    if row[1] is None:
        print('  ✅ AI 沒亂執行（preferred）')
    else:
        # 若 AI 假設 surcharge=0 也算合理（passenger_leave 接受 0）
        print('  ⚠️ AI 帶了 surcharge=0 執行了（可接受但 prompt 可加強）')

    print('\n' + '=' * 60)
    print('✅ trip_mutation_skill 5/6 個 case 通過驗證 DB 變化')
    print('   T6 視 AI 行為決定是否合理（缺參數的處理）')
    print('=' * 60)
finally:
    # 清理
    for fid in fake_ids:
        try:
            session.execute(text("DELETE FROM trips WHERE trip_id = :id"), {'id': fid})
        except Exception:
            pass
    session.execute(text("""
        DELETE FROM audit_log
        WHERE target_table = 'trips' AND target_id = ANY(:ids)
    """), {'ids': fake_ids})
    session.commit()
    print(f'\n🧹 清理 trips: {fake_ids} + 對應 audit_log')
    session.close()
