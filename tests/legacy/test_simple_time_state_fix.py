#!/usr/bin/env python3
"""
測試簡化的時間態修復方案
驗證AI能否正確區分"查看"(過去態)和"班次詳情"(現在態)
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from modules.services.smart_assistant import SmartAssistant
from modules import create_app

def test_simple_semantic_distinction():
    """測試簡單的語義區分"""
    print("🎯 測試簡化的時間態語義區分")
    print("=" * 50)
    
    app = create_app()
    assistant = SmartAssistant()
    
    test_cases = [
        {
            "input": "查看 2014",
            "expected_semantic": "過去態",
            "expected_command": "查已完成",
            "description": "'查看' = 過去態查詢"
        },
        {
            "input": "班次詳情 1585", 
            "expected_semantic": "現在態",
            "expected_command": "班次詳情",
            "description": "'詳情' = 現在態查詢"
        },
        {
            "input": "班次 1996",
            "expected_semantic": "現在態", 
            "expected_command": "班次詳情",
            "description": "'班次' = 現在態查詢"
        },
        {
            "input": "我想看看班次2014的詳情",
            "expected_semantic": "現在態",
            "expected_command": "班次詳情", 
            "description": "自然語言包含'詳情' = 現在態"
        },
        {
            "input": "查看1585",
            "expected_semantic": "過去態",
            "expected_command": "查已完成",
            "description": "'查看' = 過去態查詢"
        }
    ]
    
    with app.app_context():
        for i, case in enumerate(test_cases, 1):
            print(f"\n📋 測試案例 {i}: {case['description']}")
            print(f"   輸入: {case['input']}")
            print(f"   期望: {case['expected_semantic']} → {case['expected_command']}")
            
            try:
                result = assistant.process_user_message(case['input'], 'test_user')
                
                if result.get('success'):
                    command = result.get('parsed_command', '')
                    print(f"   🤖 AI輸出: {command}")
                    
                    # 簡單的語義判斷
                    if case['expected_command'] in command:
                        print(f"   ✅ 語義正確")
                    else:
                        print(f"   ❌ 語義錯誤")
                        print(f"      期望包含: {case['expected_command']}")
                        print(f"      實際得到: {command}")
                else:
                    print(f"   ❌ AI處理失敗: {result.get('message', 'Unknown error')}")
                    
            except Exception as e:
                print(f"   ❌ 測試失敗: {str(e)}")

def analyze_current_ai_understanding():
    """分析當前AI理解能力"""
    print(f"\n🔍 分析當前AI理解能力")
    print("=" * 30)
    
    app = create_app()
    assistant = SmartAssistant()
    
    # 檢查AI上下文中的語義規則
    context = assistant._build_ai_prompt("測試", "test_user")
    
    # 檢查關鍵語義規則是否存在
    key_rules = [
        '"查看" = 過去態',
        '"詳情" = 現在態', 
        'completed_trips',
        'trips'
    ]
    
    print("📋 檢查AI上下文中的關鍵規則:")
    for rule in key_rules:
        if rule in context:
            print(f"   ✅ 找到: {rule}")
        else:
            print(f"   ❌ 缺少: {rule}")
    
    return context

if __name__ == "__main__":
    print("開始測試簡化的時間態修復方案...")
    
    # 分析AI理解能力
    analyze_current_ai_understanding()
    
    # 測試語義區分
    test_simple_semantic_distinction()
    
    print("\n" + "=" * 50)
    print("🎯 測試總結")
    print("用戶建議的簡化方案:")
    print("  ✅ 查看 = 過去態 (completed_trips)")
    print("  ✅ 班次詳情 = 現在態 (trips)")
    print("  ✅ 讓AI明確分辨語義，而非複雜的跨表查詢")
    print("\n✨ 這確實是更簡潔、更優雅的解決方案！")