#!/usr/bin/env python3
"""
測試固定班次請假功能
"""
import sys
from pathlib import Path

# 添加項目根目錄到路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules import create_app
from modules.utils.conversation_context import conversation_manager
from modules.handlers.fixed_schedule_leave_handler import process_fixed_schedule_leave

def test_fixed_schedule_leave():
    """測試固定班次請假完整流程"""
    app = create_app()
    
    with app.app_context():
        print("🧪 測試固定班次請假功能")
        print("=" * 50)
        
        test_user_id = "test_user_123"
        fixed_schedule_id = 17
        
        print(f"1. 設置用戶上下文 (固定班次 #{fixed_schedule_id})")
        try:
            conversation_manager.set_recent_fixed_schedule_id(test_user_id, fixed_schedule_id)
            conversation_manager.set_leave_mode(user_id=test_user_id, trip_id=fixed_schedule_id)
            
            # 驗證上下文設置
            stored_id = conversation_manager.get_recent_fixed_schedule_id(test_user_id)
            is_in_leave_mode = conversation_manager.is_in_leave_mode(test_user_id)
            
            print(f"   ✅ 固定班次ID已設置: {stored_id}")
            print(f"   ✅ 請假模式已啟用: {is_in_leave_mode}")
            
        except Exception as e:
            print(f"   ❌ 設置上下文失敗: {e}")
            return
        
        print(f"\n2. 測試固定班次請假處理")
        try:
            # 直接測試處理函數
            result = process_fixed_schedule_leave(
                fixed_schedule_id=fixed_schedule_id,
                surcharge=-0,  # 對應用戶輸入的 "-0"
                reason="測試",  # 對應用戶輸入的 "測試"
                user_id=test_user_id
            )
            
            print(f"   處理結果: {result}")
            
            if "已經處於請假狀態" in result:
                print("   ✅ 班次已是請假狀態")
            elif "請假設置完成" in result:
                print("   ✅ 請假設置成功")
            elif "找不到ID為" in result:
                print("   ❌ 找不到指定班次")
            else:
                print("   ⚠️  未預期的結果")
                
        except Exception as e:
            print(f"   ❌ 處理失敗: {e}")
        
        print(f"\n3. 清理上下文")
        try:
            conversation_manager.clear_leave_mode(test_user_id)
            print("   ✅ 上下文已清理")
        except Exception as e:
            print(f"   ❌ 清理失敗: {e}")
        
        print("\n" + "=" * 50)
        print("🎉 測試完成")

if __name__ == "__main__":
    test_fixed_schedule_leave()