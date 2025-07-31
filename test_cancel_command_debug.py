#!/usr/bin/env python3
"""
測試取消命令識別邏輯
"""

import sys
import os

# 添加模組路徑
sys.path.append('/Users/linyancui/ai_experiments/minimal_flask')

def test_cancel_command_logic():
    """測試取消命令識別邏輯"""
    print("🧪 測試取消命令識別邏輯")
    print("=" * 50)
    
    try:
        from modules.utils.conversation_context import conversation_manager
        
        # 模擬用戶ID
        test_user_id = "test_user"
        
        # 啟動passenger_leave對話
        conversation = conversation_manager.start_conversation(
            user_id=test_user_id,
            conversation_type='passenger_leave',
            current_step='waiting_reason_amount',
            context_data={'trip_id': 2408},
            prompt_message="測試對話"
        )
        
        print(f"✅ 啟動對話成功: {conversation.conversation_type}")
        print(f"📋 支援的取消命令: {conversation.cancel_commands}")
        
        # 測試各種取消命令
        test_messages = [
            "放棄",
            "放棄操作", 
            "取消",
            "取消請假",
            "退出",
            "不請假",
            "普通訊息"
        ]
        
        print("\n🔍 測試各種訊息:")
        for msg in test_messages:
            can_cancel = conversation_manager.can_user_cancel_with_message(test_user_id, msg)
            status = "✅ 可取消" if can_cancel else "❌ 不可取消"
            print(f"  '{msg}' -> {status}")
        
        # 清理
        conversation_manager.end_conversation(test_user_id)
        print("\n✅ 測試完成")
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_cancel_command_logic()