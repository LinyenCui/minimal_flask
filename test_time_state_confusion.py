#!/usr/bin/env python3
"""
三時間態混亂問題診斷測試
測試AI系統對過去、現在、未來時間態的識別準確性
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from modules.services.smart_assistant import SmartAssistant
from modules.utils.taiwan_time import get_taiwan_date
from datetime import timedelta

def test_time_state_classification():
    """測試時間態分類準確性"""
    print("🔍 三時間態混亂問題診斷測試")
    print("=" * 50)
    
    assistant = SmartAssistant()
    today = get_taiwan_date()
    
    # 測試案例：明確的時間態語句
    test_cases = [
        {
            "query": "前天司機5386所有班次",
            "expected_time_state": "past",
            "expected_table": "completed_trips",
            "description": "前天 = 過去態"
        },
        {
            "query": "昨天的車資統計",
            "expected_time_state": "past", 
            "expected_table": "completed_trips",
            "description": "昨天 = 過去態"
        },
        {
            "query": "今天診所班次",
            "expected_time_state": "present",
            "expected_table": "trips",
            "description": "今天 = 現在態"
        },
        {
            "query": "明天要匯入固定班次",
            "expected_time_state": "future",
            "expected_table": "fixed_schedules",
            "description": "明天 = 未來態"
        },
        {
            "query": f"{today - timedelta(days=2)}司機123班次",
            "expected_time_state": "past",
            "expected_table": "completed_trips", 
            "description": f"具體過去日期{today - timedelta(days=2)} = 過去態"
        },
        {
            "query": f"{today}司機456班次",
            "expected_time_state": "present",
            "expected_table": "trips",
            "description": f"今天日期{today} = 現在態"
        }
    ]
    
    results = []
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n📋 測試案例 {i}: {case['description']}")
        print(f"   輸入: {case['query']}")
        print(f"   預期時間態: {case['expected_time_state']}")
        print(f"   預期表格: {case['expected_table']}")
        
        try:
            # 使用智能助手處理查詢
            result = assistant.process_user_message(case['query'], 'test_user')
            
            print(f"   🤖 AI處理結果:")
            print(f"      成功: {result.get('success', False)}")
            print(f"      命令: {result.get('parsed_command', 'N/A')}")
            print(f"      訊息: {result.get('message', 'N/A')[:100]}...")
            
            # 分析結果
            success = result.get('success', False)
            parsed_command = result.get('parsed_command', '')
            message = result.get('message', '')
            
            # 簡單的時間態判斷邏輯
            detected_time_state = "unknown"
            detected_table = "unknown"
            
            if '查已完成' in parsed_command or 'completed_trips' in message:
                detected_time_state = "past"
                detected_table = "completed_trips"
            elif '查詢班次' in parsed_command or 'trips' in message:
                detected_time_state = "present" 
                detected_table = "trips"
            elif '固定班次' in parsed_command or 'fixed_schedules' in message:
                detected_time_state = "future"
                detected_table = "fixed_schedules"
                
            print(f"      檢測到時間態: {detected_time_state}")
            print(f"      檢測到表格: {detected_table}")
            
            # 判斷準確性
            time_state_correct = detected_time_state == case['expected_time_state']
            table_correct = detected_table == case['expected_table']
            
            if time_state_correct and table_correct:
                print(f"   ✅ 分類正確")
            else:
                print(f"   ❌ 分類錯誤")
                if not time_state_correct:
                    print(f"      時間態錯誤: 期望{case['expected_time_state']}, 得到{detected_time_state}")
                if not table_correct:
                    print(f"      表格錯誤: 期望{case['expected_table']}, 得到{detected_table}")
            
            results.append({
                'case': case,
                'success': success,
                'time_state_correct': time_state_correct,
                'table_correct': table_correct,
                'detected_time_state': detected_time_state,
                'detected_table': detected_table,
                'result': result
            })
            
        except Exception as e:
            print(f"   ❌ 處理失敗: {str(e)}")
            results.append({
                'case': case,
                'success': False,
                'time_state_correct': False,
                'table_correct': False,
                'error': str(e)
            })
    
    # 統計結果
    print("\n" + "="*50)
    print("📊 測試結果統計")
    print("="*50)
    
    total_cases = len(results)
    successful_cases = sum(1 for r in results if r['success'])
    time_state_correct = sum(1 for r in results if r.get('time_state_correct', False))
    table_correct = sum(1 for r in results if r.get('table_correct', False))
    
    print(f"總測試案例: {total_cases}")
    print(f"成功處理: {successful_cases}/{total_cases} ({successful_cases/total_cases*100:.1f}%)")
    print(f"時間態識別正確: {time_state_correct}/{total_cases} ({time_state_correct/total_cases*100:.1f}%)")
    print(f"表格路由正確: {table_correct}/{total_cases} ({table_correct/total_cases*100:.1f}%)")
    
    # 列出問題案例
    problem_cases = [r for r in results if not (r.get('time_state_correct', False) and r.get('table_correct', False))]
    if problem_cases:
        print(f"\n🚨 發現 {len(problem_cases)} 個問題案例:")
        for i, case in enumerate(problem_cases, 1):
            print(f"   {i}. {case['case']['query']}")
            print(f"      問題: 期望{case['case']['expected_time_state']}/{case['case']['expected_table']}")
            print(f"            得到{case.get('detected_time_state', 'N/A')}/{case.get('detected_table', 'N/A')}")
    
    return results

def analyze_context_template():
    """分析智能助手的上下文模板"""
    print("\n🔍 智能助手上下文模板分析")
    print("="*50)
    
    assistant = SmartAssistant()
    context = assistant._build_ai_prompt("測試查詢", "test_user")
    
    # 檢查時間計算
    today = get_taiwan_date()
    yesterday = today - timedelta(days=1)
    day_before_yesterday = today - timedelta(days=2)
    
    print(f"✅ 當前日期: {today}")
    print(f"✅ 昨天: {yesterday}")
    print(f"✅ 前天: {day_before_yesterday}")
    
    # 檢查上下文中的日期
    context_lines = context.split('\n')
    date_lines = [line for line in context_lines if any(word in line for word in ['今天', '昨天', '前天', '明天', '後天'])]
    
    print(f"\n📋 上下文中的日期信息:")
    for line in date_lines:
        print(f"   {line.strip()}")
    
    # 檢查是否有硬編碼日期
    hardcoded_dates = [line for line in context_lines if '2025-07-' in line and line.count('-') >= 2]
    if hardcoded_dates:
        print(f"\n⚠️  發現硬編碼日期:")
        for line in hardcoded_dates:
            print(f"   {line.strip()}")
    else:
        print(f"\n✅ 未發現硬編碼日期，使用動態計算")

if __name__ == "__main__":
    print("開始三時間態混亂問題診斷...")
    
    # 分析上下文模板
    analyze_context_template()
    
    # 測試時間態分類
    results = test_time_state_classification()
    
    print("\n" + "="*50)
    print("🎯 診斷完成")
    print("="*50)