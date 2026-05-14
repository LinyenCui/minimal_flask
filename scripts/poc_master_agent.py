"""
Master Agent PoC v2 — prompt 二輪迭代版

跑法:
  venv/bin/python scripts/poc_master_agent.py

比較:
  Mode A (現狀 baseline) = intent classify call + skill agent function calling call
  Mode B (master agent)  = 一個 call 帶全部 tools

對每個 case 印: 選 tool / latency / 一致性
最後 summary 兩種模式的 accuracy + 平均延遲
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, _REPO_ROOT)

from vertexai.generative_models import GenerativeModel, Tool

from modules.services.ai_service import init_vertexai, MODEL_ID
from rewrite.ai.client import GeminiClient
from rewrite.ai.intent import classify

from rewrite.ai.skills.trip_query import build_trip_query_skill
from rewrite.ai.skills.trip_mutation import build_trip_mutation_skill
from rewrite.ai.skills.completed_trip import build_completed_trip_skill
from rewrite.ai.skills.customer import build_customer_skill
from rewrite.ai.skills.fixed_schedule import build_fixed_schedule_skill


# ============================================================
# Ground truth cases - (text, acceptable_tools)
# ============================================================
CASES = [
    # trip_query
    ('明天龍埔街的狀態', {'query_trips'}),
    ('待派班次', {'query_pending_dispatch', 'query_trips'}),
    ('班次詳情 1077', {'query_trip_by_id'}),
    ('今天的診所班次', {'query_today_trips', 'query_trips'}),
    ('今天診所班次', {'query_today_trips', 'query_trips'}),

    # trip_mutation
    ('1077請假化療-30', {'passenger_leave'}),
    ('99502註銷,客戶取消', {'cancel_trip'}),
    ('指派司機533給1077', {'assign_driver'}),
    ('改回準備 99503', {'restore_to_ready'}),

    # customer
    ('查太子龍', {'query_customer_by_term'}),
    ('龍埔街是誰', {'query_customer_by_term'}),
    ('病歷層 15', {'query_customers_by_birthday_day'}),
    ('病歷層分布', {'query_birthday_day_summary'}),

    # fixed_schedule
    ('太子龍的固定班次', {'query_fixed_schedule'}),
    ('固定班次21修改時間到 10:15', {'update_fixed_schedule'}),
    ('固定班次14設為請假,出國,-50', {'apply_fixed_schedule_leave'}),
    ('恢復固定班次5', {'restore_fixed_schedule'}),

    # completed_trip
    ('查已完成 昨天', {'query_completed_trips'}),
    ('查看 820', {'query_completed_trip_by_id'}),
    ('上週司機533收入', {'aggregate_completed_trips', 'sun_week_info'}),
    ('4/26-5/2 東洋班次加總', {'aggregate_completed_trips'}),
    ('今天司機5386已完成班次', {'query_completed_trips'}),

    # 邊界 case (含 PoC v1 的 regression)
    ('今天龍埔街狀態', {'query_trips', 'query_today_trips'}),
    ('5386 今天已完成', {'query_completed_trips'}),
    ('昨天診所總計', {'aggregate_completed_trips'}),
    ('本週是哪一週', {'sun_week_info'}),
    ('從診所出發的班次', {'query_trips'}),  # v2: 預設現在態
    ('到龍埔街的班次', {'query_trips'}),
    ('今天 5386 載客賺多少', {'aggregate_completed_trips'}),
    ('1077 改成診所類別', {'update_completed_trip_category', 'update_trip_category'}),

    # v2 新增邊界 case
    ('現在態 1077 改類別東洋', {'update_trip_category'}),
    ('上週從診所出發', {'query_completed_trips', 'sun_week_info'}),
    ('明天 5386 排了什麼', {'query_trips'}),
    ('龍埔街今天的班次', {'query_trips', 'query_today_trips'}),
    ('1043 記錄車資 380', {'update_completed_trip_fare', 'record_fare_current'}),
]


# ============================================================
# 建 Master tools (去重) + master prompt
# ============================================================
def build_master_tools():
    skills = [
        build_trip_query_skill(),
        build_trip_mutation_skill(),
        build_completed_trip_skill(),
        build_customer_skill(),
        build_fixed_schedule_skill(),
    ]
    seen = set()
    tools = []
    for s in skills:
        for fn, schema in s.tools:
            if fn.__name__ in seen:
                continue
            seen.add(fn.__name__)
            tools.append((fn, schema))
    return tools


MASTER_PROMPT_V2 = """\
你是台南小黃調度系統的 AI 助手, 處理派班、客戶、班次查詢與統計。

[三時間態世界觀] (最重要的判別軸)
- 過去態 completed_trips: 已執行完的班次
  觸發詞: 已完成 / 查已完成 / 查看 N / 加總 / 統計 / 總和 / 收入 / 賺多少 / 賺了多少
  過去日期 + 班次 / 金額查詢
- 現在態 trips: 生產線上的班次 (含今天 + 未來已匯入)
  觸發詞: 明天 / 下週 / 待派 / 班次詳情 N、今天 (除非明示已完成)
  修改類: 請假 / 註銷 / 衝突 / 指派司機 / 改乘客名 / 改類別 + trip_id
- 未來態 fixed_schedules: 模板 (每週重複)
  觸發詞: 固定班次 / X 的固定班次 / 長期請假

[時間] 今天 2026-05-15 (星期五)。日期類問題自己算 YYYY-MM-DD。
[太陽週] Sunday-first 非 ISO 8601。本週 / 上週 / +N週 / 第N週 / W{N} 必先 call sun_week_info。

[Tool prefix 分組]
  - trips 領域: query_trips / query_trip_by_id / query_today_trips / query_pending_dispatch /
    passenger_leave / cancel_trip / mark_conflict / restore_to_ready / assign_driver /
    unassign_driver / record_fare_current / update_passenger_name / update_trip_category
  - completed_trips 領域: query_completed_trips / query_completed_trip_by_id /
    aggregate_completed_trips / update_completed_trip_fare /
    update_completed_trip_category / update_completed_trip_driver
  - customer 領域: query_customer_by_term / get_customer_by_id /
    query_customers_by_birthday_day / query_birthday_day_summary /
    create_customer / update_customer / delete_customer
  - fixed_schedule 領域: query_fixed_schedule / create_fixed_schedule /
    update_fixed_schedule / apply_fixed_schedule_leave / restore_fixed_schedule
  - sun_week_info: 跨領域, 任何週次計算先 call

[工具選擇要點]
- 「班次」+ 數字 = trips (query_trip_by_id 或 mutation)
- 「固定班次」+ 數字 = fixed_schedule
- 「狀態」+ 客戶名 -> query_trips (列該客戶當天班次)
- 客戶 CRUD: query_customer_by_term / create_customer / update_customer / delete_customer
- 病歷層: query_customers_by_birthday_day (單日) / query_birthday_day_summary (分布)
- 過去態: query_completed_trips (列表) / query_completed_trip_by_id (「查看 N」「#N」) /
  aggregate_completed_trips (加總 / 統計 / 收入 / 賺多少)
- 「修改 #N 金額」「記錄車資 N」 -> update_completed_trip_fare
- 「#N 司機改成 M」「換 #N 司機 M」 -> update_completed_trip_driver

[地點 query 規則] (重要)
- 純粹「從 X 出發」「到 X」「經過 X」 沒指定時間態 -> 預設**現在態** query_trips
  (講的是目前在線上的班次, 不是已完成的歷史)
- 加「已完成」「上週」「昨天」等過去語境 -> query_completed_trips
- 例:
  * 「從診所出發的班次」 -> query_trips(start_location='診所')
  * 「到龍埔街的班次」 -> query_trips(end_location='龍埔街')
  * 「上週從診所出發」 -> 先 sun_week_info 拿日期 -> query_completed_trips(start_location='診所', ...)

[改類別 / mutation + trip_id 的判別]
- 「改類別 + 數字」沒指明過去 / 現在態 -> 預設**過去態** update_completed_trip_category
  (「改類別」最常出現在「車已開完後發現分類錯誤」)
- 用戶明說「現在態 N」「未完成 N」「生產線 N」+ 改類別 -> update_trip_category
- 例:
  * 「1077 改成診所類別」 -> update_completed_trip_category
  * 「現在態 1077 改類別東洋」 -> update_trip_category
- 「N 記錄車資 X」沒指明 -> 預設過去態 update_completed_trip_fare

[category vs location]
- 「X 班次 / X 加總」中 X 是診所 / 東洋 / 臨時 -> category 參數
- 「從 X 出發」「到 X」「經過 X」 -> start_location / end_location / location

[規則]
- mutation 必須給 reason; 用戶沒給就回文字問用戶補充
- 完成動作直接回報, 不主動追問下一步
- 不確定就 call 最像的 query tool — **永遠別只回純文字不 call tool** (除非閒聊)

用戶訊息:
"""


def run_baseline(llm, text: str, skills: dict) -> Tuple[Optional[str], float, dict]:
    t0 = time.time()
    intent = classify(llm, text)
    t1 = time.time()
    intent_latency = t1 - t0
    if intent == 'unknown' or intent not in skills:
        return None, time.time() - t0, {
            'intent': intent, 'intent_latency': intent_latency,
            'skill_latency': 0, 'note': 'unknown_intent',
        }
    skill = skills[intent]
    init_vertexai()
    gemini_tools = [Tool(function_declarations=skill.function_declarations())]
    model = GenerativeModel(MODEL_ID, tools=gemini_tools)
    chat = model.start_chat()
    full_prompt = f"{skill.system_prompt}\n\n用戶訊息: {text}"
    response = chat.send_message(full_prompt)
    t2 = time.time()
    tool_name = _extract_first_function_name(response)
    return tool_name, t2 - t0, {
        'intent': intent, 'intent_latency': intent_latency,
        'skill_latency': t2 - t1,
    }


def run_master(text: str, master_tools) -> Tuple[Optional[str], float, dict]:
    t0 = time.time()
    init_vertexai()
    from rewrite.ai.skill import Skill
    fake_skill = Skill(name='master', system_prompt=MASTER_PROMPT_V2, tools=master_tools)
    gemini_tools = [Tool(function_declarations=fake_skill.function_declarations())]
    model = GenerativeModel(MODEL_ID, tools=gemini_tools)
    chat = model.start_chat()
    response = chat.send_message(f"{MASTER_PROMPT_V2}{text}")
    t1 = time.time()
    tool_name = _extract_first_function_name(response)
    return tool_name, t1 - t0, {'n_tools': len(master_tools)}


def _extract_first_function_name(response) -> Optional[str]:
    try:
        candidates = getattr(response, 'candidates', None) or []
        if not candidates:
            return None
        content = candidates[0].content
        parts = getattr(content, 'parts', None) or []
        for p in parts:
            fc = getattr(p, 'function_call', None)
            if fc and getattr(fc, 'name', None):
                return fc.name
        return None
    except Exception as e:
        print(f'  warn extract_fn_name: {e}')
        return None


def main():
    print('Initializing Gemini...')
    init_vertexai()
    llm = GeminiClient()

    skills = {
        'trip_query': build_trip_query_skill(),
        'trip_mutation': build_trip_mutation_skill(),
        'completed_trip': build_completed_trip_skill(),
        'customer': build_customer_skill(),
        'fixed_schedule': build_fixed_schedule_skill(),
    }
    master_tools = build_master_tools()
    print(f'Master tools: {len(master_tools)}')
    print(f'Model: {MODEL_ID}')
    print(f'Cases: {len(CASES)}\n')

    results = []
    for i, (text, acceptable) in enumerate(CASES, 1):
        print(f'[{i:>2}/{len(CASES)}] {text!r}')
        try:
            b_tool, b_lat, b_info = run_baseline(llm, text, skills)
        except Exception as e:
            b_tool, b_lat, b_info = None, 0, {'error': str(e)[:100]}
        try:
            m_tool, m_lat, m_info = run_master(text, master_tools)
        except Exception as e:
            m_tool, m_lat, m_info = None, 0, {'error': str(e)[:100]}

        b_ok = b_tool in acceptable if b_tool else False
        m_ok = m_tool in acceptable if m_tool else False
        b_mark = '[v]' if b_ok else ('[~]' if b_tool else '[X]')
        m_mark = '[v]' if m_ok else ('[~]' if m_tool else '[X]')
        print(f'    baseline  {b_mark} tool={b_tool or "-":<35} {b_lat:.2f}s '
              f'(intent={b_info.get("intent")})')
        print(f'    master    {m_mark} tool={m_tool or "-":<35} {m_lat:.2f}s')
        results.append({
            'text': text, 'acceptable': acceptable,
            'b_tool': b_tool, 'b_ok': b_ok, 'b_lat': b_lat,
            'm_tool': m_tool, 'm_ok': m_ok, 'm_lat': m_lat,
        })

    n = len(results)
    b_pass = sum(1 for r in results if r['b_ok'])
    m_pass = sum(1 for r in results if r['m_ok'])
    b_avg = sum(r['b_lat'] for r in results) / n
    m_avg = sum(r['m_lat'] for r in results) / n
    agree = sum(1 for r in results if r['b_tool'] == r['m_tool'])

    print('\n' + '=' * 70)
    print('Summary')
    print('=' * 70)
    print(f'  Baseline (2 calls): pass={b_pass}/{n} ({b_pass/n*100:.0f}%)  avg={b_avg:.2f}s')
    print(f'  Master   (1 call) : pass={m_pass}/{n} ({m_pass/n*100:.0f}%)  avg={m_avg:.2f}s')
    print(f'  Speedup           : {b_avg/m_avg:.2f}x  (delta {b_avg - m_avg:.2f}s 每訊息)')
    print(f'  Tool 選擇一致     : {agree}/{n}')

    disagreed = [r for r in results if r['b_tool'] != r['m_tool']]
    if disagreed:
        print('\n  -- 不一致 case --')
        for r in disagreed:
            print(f'    {r["text"]!r}')
            print(f'      baseline={r["b_tool"]}  master={r["m_tool"]}  acceptable={sorted(r["acceptable"])}')

    master_regression = [r for r in results if r['b_ok'] and not r['m_ok']]
    if master_regression:
        print(f'\n  ## Master regression: {len(master_regression)} case')
        for r in master_regression:
            print(f'    {r["text"]!r}  baseline={r["b_tool"]} -> master={r["m_tool"]}')

    baseline_only_fail = [r for r in results if not r['b_ok'] and r['m_ok']]
    if baseline_only_fail:
        print(f'\n  ## Baseline 錯 master 對: {len(baseline_only_fail)} case (master 撿回的)')
        for r in baseline_only_fail:
            print(f'    {r["text"]!r}  baseline={r["b_tool"]} -> master={r["m_tool"]}')


if __name__ == '__main__':
    main()
