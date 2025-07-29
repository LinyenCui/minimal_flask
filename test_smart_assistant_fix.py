#!/usr/bin/env python3
"""
測試Smart Assistant修復後的車資修改解析功能
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.services.smart_assistant import process_with_smart_assistant

def test_fare_modification_parsing():
    """測試車資修改解析功能"""
    
    test_cases = [
        {
            "input": "修改#2111$1150+375",
            "expected_command": "修改車資 2111 1150 375",
            "description": "符號格式修改"
        },
        {
            "input": "修改班次#2111車資1150加成375", 
            "expected_command": "修改車資 2111 1150 375",
            "description": "中文格式修改"
        },
        {
            "input": "記錄車資 2014 280 -50",
            "expected_command": "記錄車資 2014 280 -50", 
            "description": "明確記錄命令"
        },
        {
            "input": "我想修改班次2014的車資",
            "expected_command": "修改車資 2014",
            "description": "自然語言修改請求"
        }
    ]
    
    print("🧪 測試Smart Assistant車資修改解析修復")
    print("=" * 60)
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n測試案例 {i}: {case['description']}")
        print(f"輸入: {case['input']}")
        print(f"期望: {case['expected_command']}")
        
        try:
            # 使用測試用戶ID
            result = process_with_smart_assistant(case["input"], "test_user_123")
            
            if result.get("type") == "execute_command":
                actual_command = result.get("command", "")
                print(f"實際: {actual_command}")
                
                if case["expected_command"] in actual_command:
                    print("✅ 通過")
                else:
                    print("❌ 失敗")
                    print(f"   AI推理: {result.get('ai_reasoning', 'N/A')}")
            else:
                print("❌ 未生成執行命令")
                print(f"   結果類型: {result.get('type')}")
                
        except Exception as e:
            print(f"❌ 錯誤: {e}")
    
    print("\n" + "=" * 60)
    print("測試完成")

if __name__ == "__main__":
    test_fare_modification_parsing()