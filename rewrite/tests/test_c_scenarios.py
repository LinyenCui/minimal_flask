"""
C 階段測試 - 在 dev_line_channel 測試端跑各種情境
"""
import os, json, logging, sys
from dotenv import load_dotenv
load_dotenv()

# 抑制大部分 INFO log
logging.getLogger().setLevel(logging.WARNING)
for noisy in ['apscheduler', 'modules.scheduler', 'sqlalchemy', 'modules.services.scheduler_service']:
    logging.getLogger(noisy).setLevel(logging.ERROR)

from app import app
from modules.models.base import db
from sqlalchemy import text

USER_ID = 'U6b520261e9199a21d25e6d20509eda3f'
TEST_TRIP = 1043

def banner(label):
    print(f'\n{"="*70}\n# {label}\n{"="*70}')

def show_trip(trip_id):
    row = db.session.execute(text("""
        SELECT trip_id, status, passenger_leave_reason, extra_fare, modification_reason
        FROM trips WHERE trip_id = :id
    """), {'id': trip_id}).fetchone()
    if row:
        print(f'  trip_id={row[0]} status={row[1]} leave_reason={row[2]} extra_fare={row[3]} mod={row[4]}')
    else:
        print(f'  trip_id={trip_id} 不存在')

with app.app_context():
    # ====================================================
    # C-1: 傳統 path 對 #1043 請假 → 還原
    # ====================================================
    banner(f'C-1: 傳統 path 對 #{TEST_TRIP} 請假 → 還原')
    from modules.handlers.passenger_leave_handler import process_passenger_leave
    from modules.handlers.trip_status_handler import handle_update_trip_status

    print('【before】')
    show_trip(TEST_TRIP)

    print('\n【執行請假 -50 原因="C1測試"】')
    r = process_passenger_leave(TEST_TRIP, -50, 'C1測試', USER_ID)
    print(f'回傳: {str(r)[:200]}')

    print('\n【after leave】')
    show_trip(TEST_TRIP)

    print('\n【還原 (改狀態回準備)】')
    r2 = handle_update_trip_status(f'修改狀態 {TEST_TRIP} 準備', USER_ID)
    print(f'回傳: {str(r2)[:200]}')

    print('\n【after restore】')
    show_trip(TEST_TRIP)

    # ====================================================
    # C-2: 沙盒 booking 完整流程 propose → execute → 清理
    # ====================================================
    banner('C-2: 沙盒 booking propose → execute → 清理')
    from modules.services.customers_ai_service import process_sandbox_message, execute_proposal

    text_input = '！明天14:00從測試街A到測試街B 乘客：C2測試客戶 金額500'
    print(f'輸入: {text_input}\n')
    proposal = process_sandbox_message(USER_ID, text_input)
    print(f'類型: {proposal.get("type")}')
    print(f'內容: {str(proposal.get("content"))[:300]}\n')

    if proposal.get('type') == 'proposal':
        # 取出 proposal 細節執行 (實際欄位是 func_name / func_args)
        content = proposal.get('content', {})
        func_name = content.get('func_name') if isinstance(content, dict) else None
        func_args = content.get('func_args') if isinstance(content, dict) else None
        print(f'func_name={func_name}')
        print(f'func_args={func_args}\n')

        if func_name == 'booking_create' and func_args:
            print('【執行 proposal】')
            exec_r = execute_proposal(func_name, func_args)
            print(f'執行結果: {str(exec_r)[:300]}')

            # 找出剛建立的 trip_id (查最新 + 簡稱「測試街A」)
            row = db.session.execute(text("""
                SELECT trip_id FROM trips
                WHERE start_point = '測試街A' OR start_point LIKE '%測試%'
                ORDER BY trip_id DESC LIMIT 1
            """)).fetchone()
            if row:
                new_id = row[0]
                print(f'\n【清理】 刪除測試 trip #{new_id}')
                db.session.execute(text("DELETE FROM trips WHERE trip_id = :id"), {'id': new_id})
                db.session.commit()
                print('已刪除')
    else:
        print('⚠️ 預期 proposal，實際拿到', proposal.get('type'))

    # ====================================================
    # C-3: 沙盒對不存在的 trip_id
    # ====================================================
    banner('C-3: 沙盒對 #99999 (不存在) trip_update')
    r = process_sandbox_message(USER_ID, '！把班次99999改時間到下午3點')
    print(f'類型: {r.get("type")}')
    print(f'內容: {str(r.get("content"))[:300]}')

    # ====================================================
    # C-4: 模糊代名詞 (沒有上下文)
    # ====================================================
    banner('C-4: 模糊代名詞「那一筆改時間」(無上下文)')
    r = process_sandbox_message(USER_ID, '！那一筆改時間到下午4點')
    print(f'類型: {r.get("type")}')
    print(f'內容: {str(r.get("content"))[:300]}')

    # ====================================================
    # C-5a: trip_delete 中等範圍 (僅看 propose, 不 execute)
    # ====================================================
    banner('C-5a: 沙盒對「取消 9999 到 10050」(50 筆, 不存在的 ID)')
    try:
        r = process_sandbox_message(USER_ID, '！取消 9999 到 10050 的班次')
        print(f'類型: {r.get("type")}')
        content = r.get('content')
        if isinstance(content, dict):
            func_name = content.get('func_name')
            func_args = content.get('func_args', {}) or {}
            print(f'func_name={func_name}')
            ids = func_args.get('trip_ids', [])
            print(f'AI 提議刪除 {len(ids)} 筆: {ids[:10]}{"..." if len(ids)>10 else ""}')
            print(f'⚠️ 不執行 (僅看 proposal)')
        else:
            print(f'內容: {str(content)[:300]}')
    except Exception as e:
        print(f'❌ Gemini 例外: {type(e).__name__}: {str(e)[:200]}')

    banner('C-5b: 沙盒對「取消 1 到 9999」(極大範圍, 預期掛掉)')
    try:
        r = process_sandbox_message(USER_ID, '！取消 1 到 9999 的班次')
        content = r.get('content')
        if isinstance(content, dict):
            func_args = content.get('func_args', {}) or {}
            ids = func_args.get('trip_ids', [])
            print(f'類型: {r.get("type")} | 提議 {len(ids)} 筆')
        else:
            print(f'類型: {r.get("type")} | 內容: {str(content)[:200]}')
    except Exception as e:
        print(f'❌ Gemini 例外: {type(e).__name__}: {str(e)[:300]}')

    # ====================================================
    # C-6: 跨界 - 在沙盒打非沙盒指令
    # ====================================================
    banner('C-6a: 沙盒接收「資料庫同步」(非沙盒指令)')
    r = process_sandbox_message(USER_ID, '！資料庫同步')
    print(f'類型: {r.get("type")}')
    print(f'內容: {str(r.get("content"))[:300]}')

    banner('C-6b: 沙盒接收「診所班次 今天」(非沙盒指令)')
    r = process_sandbox_message(USER_ID, '！診所班次 今天')
    print(f'類型: {r.get("type")}')
    print(f'內容: {str(r.get("content"))[:300]}')

    print('\n\n========== 全部測試完成 ==========')
