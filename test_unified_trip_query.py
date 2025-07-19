#!/usr/bin/env python3
"""
統一班次查詢服務測試
驗證跨時間態智能搜索功能
"""
import sys
import os

# 添加項目根目錄到路徑
sys.path.insert(0, os.path.abspath('.'))

from modules.services.unified_trip_query_service import unified_trip_query_service

def test_unified_trip_query():
    """測試統一班次查詢功能"""
    
    print("🧪 統一班次查詢服務測試開始\n")
    
    # 測試用例1：查詢一個可能在trips表的ID
    print("=== 測試1：查詢較大ID（可能在trips表）===")
    user_context_1 = {
        'original_query': '班次詳情 1585',
        'user_id': 'test_user',
        'command_type': 'trip_details'
    }
    
    result_1 = unified_trip_query_service.query_trip_details(1585, user_context_1)
    print(f"查詢結果：{result_1['success']}")
    print(f"來源表：{result_1.get('source_table')}")
    print(f"時間態：{result_1.get('time_perspective')}")
    print(f"智能提示：{result_1.get('smart_hint')}")
    print(f"結果內容：")
    print(result_1['message'])
    print("\n" + "="*50 + "\n")
    
    # 測試用例2：查詢一個可能在completed_trips表的ID
    print("=== 測試2：查詢較小ID（可能在completed_trips表）===")
    user_context_2 = {
        'original_query': '查看 50',
        'user_id': 'test_user',
        'command_type': 'view_trip'
    }
    
    result_2 = unified_trip_query_service.query_trip_details(50, user_context_2)
    print(f"查詢結果：{result_2['success']}")
    print(f"來源表：{result_2.get('source_table')}")
    print(f"時間態：{result_2.get('time_perspective')}")
    print(f"智能提示：{result_2.get('smart_hint')}")
    print(f"結果內容：")
    print(result_2['message'])
    print("\n" + "="*50 + "\n")
    
    # 測試用例3：查詢一個不存在的ID
    print("=== 測試3：查詢不存在的ID ===")
    user_context_3 = {
        'original_query': '班次詳情 99999',
        'user_id': 'test_user',
        'command_type': 'trip_details'
    }
    
    result_3 = unified_trip_query_service.query_trip_details(99999, user_context_3)
    print(f"查詢結果：{result_3['success']}")
    print(f"來源表：{result_3.get('source_table')}")
    print(f"智能提示：{result_3.get('smart_hint')}")
    print(f"結果內容：")
    print(result_3['message'])
    print("\n" + "="*50 + "\n")
    
    # 測試用例4：包含車資關鍵字的查詢（偏向過去態）
    print("=== 測試4：包含車資關鍵字的查詢 ===")
    user_context_4 = {
        'original_query': '查看班次1585的車資',
        'user_id': 'test_user',
        'command_type': 'fare_query'
    }
    
    result_4 = unified_trip_query_service.query_trip_details(1585, user_context_4)
    print(f"查詢結果：{result_4['success']}")
    print(f"來源表：{result_4.get('source_table')}")
    print(f"時間態：{result_4.get('time_perspective')}")
    print(f"智能提示：{result_4.get('smart_hint')}")
    print(f"結果內容：")
    print(result_4['message'])
    
    print("\n🎉 統一班次查詢服務測試完成！")

def test_strategy_determination():
    """測試搜索策略判斷邏輯"""
    
    print("\n🧪 測試搜索策略判斷邏輯\n")
    
    test_cases = [
        {
            'trip_id': 1585,
            'context': {'original_query': '班次詳情 1585'},
            'expected': 'present_first',
            'reason': '大ID默認現在態優先'
        },
        {
            'trip_id': 50,
            'context': {'original_query': '查看 50'},
            'expected': 'past_first',
            'reason': '小ID默認過去態優先'
        },
        {
            'trip_id': 1585,
            'context': {'original_query': '查看班次1585的車資'},
            'expected': 'past_first',
            'reason': '包含車資關鍵字優先過去態'
        },
        {
            'trip_id': 100,
            'context': {'original_query': '今天班次100狀態'},
            'expected': 'present_first',
            'reason': '包含今天關鍵字優先現在態'
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        strategy = unified_trip_query_service._determine_search_strategy(
            case['trip_id'], case['context']
        )
        
        status = "✅" if strategy == case['expected'] else "❌"
        print(f"測試 {i}: {status}")
        print(f"  輸入: ID={case['trip_id']}, 查詢='{case['context']['original_query']}'")
        print(f"  預期: {case['expected']}")
        print(f"  實際: {strategy}")
        print(f"  原因: {case['reason']}\n")

if __name__ == "__main__":
    # 設置測試環境
    print("🚀 開始測試統一班次查詢服務")
    print("="*60)
    
    try:
        # 測試核心查詢功能
        test_unified_trip_query()
        
        # 測試策略判斷邏輯
        test_strategy_determination()
        
    except Exception as e:
        print(f"❌ 測試過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("🏁 測試完成") 