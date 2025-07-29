#!/usr/bin/env python3
"""
測試預約叫車系統
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.handlers.temp_booking_handler import (
    handle_temp_booking_start,
    handle_temp_booking_message,
    temp_booking_states
)

def test_booking_flow():
    """測試預約流程"""
    print("🧪 測試預約叫車系統")
    print("=" * 50)
    
    # 清除所有狀態
    temp_booking_states.clear()
    
    test_user_id = "test_user_123"
    
    # 1. 開始預約
    print("\n1️⃣ 開始預約")
    result = handle_temp_booking_start(test_user_id)
    print(f"回應: {result.get('text', 'No text')}")
    print(f"狀態: {temp_booking_states.get(test_user_id, 'No state')}")
    
    # 2. 測試複雜輸入
    print("\n2️⃣ 測試複雜輸入: '昨天晚上07:00 從馬來西亞到新加坡 診所班次 乘客梁峻榮'")
    result = handle_temp_booking_message(test_user_id, "昨天晚上07:00 從馬來西亞到新加坡 診所班次 乘客梁峻榮")
    if result:
        print(f"回應: {result.get('text', 'No text')}")
        print(f"狀態: {temp_booking_states.get(test_user_id, 'No state')}")
    else:
        print("❌ 無回應")
    
    # 3. 測試簡單時間輸入
    print("\n3️⃣ 測試簡單時間: '今天19:00'")
    result = handle_temp_booking_message(test_user_id, "今天19:00")
    if result:
        print(f"回應: {result.get('text', 'No text')}")
        print(f"狀態: {temp_booking_states.get(test_user_id, 'No state')}")
    else:
        print("❌ 無回應")
    
    # 4. 測試另一個簡單時間
    print("\n4️⃣ 測試簡單時間: '晚上七點'")
    result = handle_temp_booking_message(test_user_id, "晚上七點")
    if result:
        print(f"回應: {result.get('text', 'No text')}")
        print(f"狀態: {temp_booking_states.get(test_user_id, 'No state')}")
    else:
        print("❌ 無回應")
    
    # 5. 測試時間格式
    print("\n5️⃣ 測試時間格式: '19:30'")
    result = handle_temp_booking_message(test_user_id, "19:30")
    if result:
        print(f"回應: {result.get('text', 'No text')}")
        print(f"狀態: {temp_booking_states.get(test_user_id, 'No state')}")
    else:
        print("❌ 無回應")

def test_fallback_parsing():
    """測試 fallback 解析邏輯"""
    print("\n🔧 測試 fallback 解析")
    print("=" * 30)
    
    from modules.handlers.temp_booking_handler import _simple_time_parsing
    
    test_cases = [
        "今天19:00",
        "今天晚上七點",
        "明天18:30",
        "7/28 19:00",
        "晚上七點半",
        "19:30",
    ]
    
    for case in test_cases:
        print(f"\n測試: '{case}'")
        try:
            result = _simple_time_parsing(case)
            print(f"結果: {result}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

if __name__ == "__main__":
    try:
        test_booking_flow()
        test_fallback_parsing()
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()