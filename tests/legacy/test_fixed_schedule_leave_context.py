#!/usr/bin/env python3
"""
測試固定班次請假上下文功能
模擬完整的用戶操作流程
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.utils.conversation_context import conversation_manager
import logging

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_fixed_schedule_leave_context():
    """測試固定班次請假上下文流程"""
    print("🧪 測試固定班次請假上下文功能")
    print("=" * 50)
    
    test_user_id = "test_user_123"
    test_schedule_id = 17
    
    # 步驟1：模擬用戶點擊「固定班次#17請假」按鈕
    print(f"\n1️⃣ 模擬點擊「固定班次#{test_schedule_id}請假」按鈕")
    try:
        # 設置固定班次ID到上下文
        conversation_manager.set_recent_fixed_schedule_id(test_user_id, test_schedule_id)
        print(f"✅ 設置 recent_fixed_schedule_id = {test_schedule_id}")
        
        # 設置請假模式
        conversation_manager.set_leave_mode(test_user_id, test_schedule_id)
        print(f"✅ 設置請假模式，trip_id = {test_schedule_id}")
        
    except Exception as e:
        print(f"❌ 設置失敗: {e}")
        return False
    
    # 步驟2：檢查狀態
    print(f"\n2️⃣ 檢查設置後的狀態")
    try:
        # 檢查固定班次ID
        retrieved_schedule_id = conversation_manager.get_recent_fixed_schedule_id(test_user_id)
        print(f"🔍 get_recent_fixed_schedule_id 返回: {retrieved_schedule_id}")
        
        # 檢查請假模式
        is_in_leave_mode = conversation_manager.is_in_leave_mode(test_user_id)
        print(f"🔍 is_in_leave_mode 返回: {is_in_leave_mode}")
        
        # 檢查最近班次ID（用於簡化請假）
        recent_trip_id = conversation_manager.get_recent_trip_id(test_user_id)
        print(f"🔍 get_recent_trip_id 返回: {recent_trip_id}")
        
        if retrieved_schedule_id != test_schedule_id:
            print(f"❌ 固定班次ID不匹配! 期望: {test_schedule_id}, 實際: {retrieved_schedule_id}")
            return False
            
        if not is_in_leave_mode:
            print(f"❌ 請假模式未設置!")
            return False
            
    except Exception as e:
        print(f"❌ 檢查狀態失敗: {e}")
        return False
    
    # 步驟3：模擬用戶輸入「測試 -0」
    print(f"\n3️⃣ 模擬用戶輸入簡化請假格式")
    user_input = "測試 -0"
    print(f"用戶輸入: '{user_input}'")
    
    # 模擬text_message_handler中的邏輯
    import re
    leave_pattern = r'^(.+?)\s+([-+]?\d+)$'
    match = re.match(leave_pattern, user_input.strip())
    
    if match:
        reason = match.group(1).strip()
        amount = match.group(2).strip()
        print(f"🔍 解析結果 - 原因: '{reason}', 加成: '{amount}'")
        
        # 檢查請假模式
        is_in_leave_mode = conversation_manager.is_in_leave_mode(test_user_id)
        recent_fixed_schedule_id = conversation_manager.get_recent_fixed_schedule_id(test_user_id)
        
        print(f"🔍 請假模式: {is_in_leave_mode}")
        print(f"🔍 固定班次ID: {recent_fixed_schedule_id}")
        
        if is_in_leave_mode and recent_fixed_schedule_id:
            # 構造完整命令
            full_command = f"固定班次請假 {recent_fixed_schedule_id} {amount} {reason}"
            print(f"✅ 構造完整命令: '{full_command}'")
            
            # 模擬處理
            print(f"✅ 系統應該處理: 固定班次#{recent_fixed_schedule_id} 請假，原因='{reason}', 加成={amount}")
            return True
        else:
            print(f"❌ 條件不滿足 - 請假模式: {is_in_leave_mode}, 固定班次ID: {recent_fixed_schedule_id}")
            return False
    else:
        print(f"❌ 無法解析請假格式: '{user_input}'")
        return False

def test_context_persistence():
    """測試上下文持久性"""
    print(f"\n4️⃣ 測試上下文持久性")
    test_user_id = "test_user_456"
    
    # 設置上下文
    conversation_manager.set_recent_fixed_schedule_id(test_user_id, 20)
    conversation_manager.set_leave_mode(test_user_id, 20)
    
    # 立即檢查
    immediate_check = conversation_manager.get_recent_fixed_schedule_id(test_user_id)
    immediate_leave_mode = conversation_manager.is_in_leave_mode(test_user_id)
    
    print(f"🔍 立即檢查 - 固定班次ID: {immediate_check}, 請假模式: {immediate_leave_mode}")
    
    # 模擬時間流逝（但在5分鐘內）
    import time
    print("⏰ 等待2秒...")
    time.sleep(2)
    
    # 再次檢查
    delayed_check = conversation_manager.get_recent_fixed_schedule_id(test_user_id)
    delayed_leave_mode = conversation_manager.is_in_leave_mode(test_user_id)
    
    print(f"🔍 延遲檢查 - 固定班次ID: {delayed_check}, 請假模式: {delayed_leave_mode}")
    
    return immediate_check == delayed_check and immediate_leave_mode == delayed_leave_mode

if __name__ == "__main__":
    print("🚀 開始測試固定班次請假上下文")
    
    success1 = test_fixed_schedule_leave_context()
    success2 = test_context_persistence()
    
    print(f"\n📊 測試結果:")
    print(f"基本流程測試: {'✅ 通過' if success1 else '❌ 失敗'}")
    print(f"持久性測試: {'✅ 通過' if success2 else '❌ 失敗'}")
    
    if success1 and success2:
        print(f"\n🎉 所有測試通過！固定班次請假上下文功能正常")
    else:
        print(f"\n⚠️ 測試失敗，需要進一步調試")