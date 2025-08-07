#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試AI對對話取消操作的理解
"""

import sys
import os
sys.path.append('.')

def test_ai_cancel_understanding():
    """測試AI是否正確理解對話中的取消操作"""
    try:
        from modules.services.smart_assistant import SmartAssistant
        
        # 創建AI助手實例
        assistant = SmartAssistant()
        
        print("=== 測試AI對話取消理解修復 ===\n")
        
        # 測試案例1：模擬用戶在請假對話中說「取消」
        print("🧪 測試案例1：請假對話中的取消")
        print("模擬情境：用戶點擊了🔵請假按鈕，進入請假輸入模式，然後說「取消」")
        
        user_input = "取消"
        user_id = "test_user_123"
        
        # 設置請假模式上下文（模擬用戶剛點擊了請假按鈕）
        from modules.utils.conversation_context import conversation_manager
        conversation_manager.set_leave_mode(user_id=user_id, trip_id=112)
        
        try:
            result = assistant._analyze_with_ai(user_input, user_id)
            confidence = result.get('confidence', 'unknown')
            command = result.get('command', 'unknown')
            
            print(f"用戶輸入: '{user_input}'")
            print(f"AI信心度: {confidence}")
            print(f"生成命令: '{command}'")
            
            # 檢查結果
            if confidence == 'low' or (isinstance(confidence, (int, float)) and confidence < 0.3):
                print("✅ AI正確理解：信心度低，將由傳統對話取消機制處理")
            else:
                print("❌ AI仍然誤解：信心度過高，可能會生成錯誤命令")
                
        except Exception as e:
            print(f"❌ AI處理過程出現錯誤: {e}")
            
        print("\n" + "="*50 + "\n")
        
        # 測試案例2：對比測試 - 真正的狀態查詢
        print("🧪 測試案例2：真正的狀態查詢命令")
        print("模擬情境：用戶確實想查詢所有註銷狀態的班次")
        
        user_input2 = "取消班次"
        
        # 清除對話上下文（模擬正常查詢情境）
        conversation_manager.clear_leave_mode(user_id)
        
        try:
            result2 = assistant._analyze_with_ai(user_input2, user_id)
            confidence2 = result2.get('confidence', 'unknown')
            command2 = result2.get('command', 'unknown')
            
            print(f"用戶輸入: '{user_input2}'")
            print(f"AI信心度: {confidence2}")
            print(f"生成命令: '{command2}'")
            
            # 檢查結果
            if "查詢班次 狀態=註銷" in str(command2):
                print("✅ AI正確理解：這是狀態查詢命令")
            else:
                print("❌ AI理解錯誤：未正確生成狀態查詢命令")
                
        except Exception as e:
            print(f"❌ AI處理過程出現錯誤: {e}")
        
        print("\n=== 測試完成 ===")
        
    except ImportError as e:
        print(f"❌ 模組導入失敗: {e}")
        print("請確保在正確的環境中運行此測試")
    except Exception as e:
        print(f"❌ 測試過程中出現未預期的錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ai_cancel_understanding()