#!/usr/bin/env python3
"""
測試完整的固定班次請假流程（模擬Line Bot）
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules import create_app
from modules.utils.conversation_context import conversation_manager
from modules.services.smart_assistant import process_with_smart_assistant
from modules.handlers.fixed_schedule_leave_handler import handle_fixed_schedule_leave_command

def test_complete_flow():
    """測試完整的固定班次請假流程"""
    app = create_app()
    
    with app.app_context():
        print("🧪 測試完整固定班次請假流程")
        print("=" * 60)
        
        test_user_id = "test_complete_flow"
        fixed_schedule_id = 17
        
        # 步驟1：模擬點擊「固定班次#17請假」按鈕
        print(f"1️⃣ 模擬點擊「固定班次#{fixed_schedule_id}請假」按鈕")
        print("-" * 50)
        
        try:
            # 設置上下文（這是按鈕點擊時發生的）
            conversation_manager.set_recent_fixed_schedule_id(test_user_id, fixed_schedule_id)
            conversation_manager.set_leave_mode(user_id=test_user_id, trip_id=fixed_schedule_id)
            
            print(f"   ✅ 上下文已設置：固定班次ID={fixed_schedule_id}")
            
        except Exception as e:
            print(f"   ❌ 設置上下文失敗: {e}")
            return
        
        # 步驟2：模擬用戶輸入「測試 -0」
        print(f"\n2️⃣ 模擬用戶輸入「測試 -0」")
        print("-" * 50)
        
        user_input = "測試 -0"
        print(f"   用戶輸入: '{user_input}'")
        
        try:
            # 智能助手處理
            smart_result = process_with_smart_assistant(user_input, test_user_id)
            
            print(f"   智能助手結果類型: {smart_result.get('type')}")
            
            if smart_result.get('type') == 'execute_command':
                generated_command = smart_result.get('command')
                print(f"   ✅ 生成命令: '{generated_command}'")
                
                # 步驟3：模擬執行生成的命令
                print(f"\n3️⃣ 執行生成的命令")
                print("-" * 50)
                
                if generated_command.startswith("固定班次請假"):
                    result = handle_fixed_schedule_leave_command(generated_command, test_user_id)
                    
                    # 清除請假模式
                    conversation_manager.clear_leave_mode(test_user_id)
                    
                    print(f"   執行結果:")
                    print(f"   {result}")
                    
                    # 檢查是否成功
                    if "請假設置完成" in result:
                        print(f"\n   ✅ 固定班次請假執行成功！")
                    elif "已經處於請假狀態" in result:
                        print(f"\n   ⚠️  班次已在請假狀態")
                    else:
                        print(f"\n   ❌ 固定班次請假執行失敗")
                else:
                    print(f"   ❌ 生成的命令格式錯誤: {generated_command}")
            else:
                print(f"   ❌ 智能助手返回錯誤類型: {smart_result.get('type')}")
                
        except Exception as e:
            print(f"   ❌ 智能助手處理失敗: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n" + "=" * 60)
        print("🎉 完整流程測試完成")

def test_direct_command():
    """直接測試固定班次請假命令處理"""
    app = create_app()
    
    with app.app_context():
        print("\n🧪 直接測試固定班次請假命令處理")
        print("=" * 60)
        
        test_user_id = "test_direct_command"
        command = "固定班次請假 17 -0 測試"
        
        print(f"直接執行命令: '{command}'")
        print("-" * 40)
        
        try:
            result = handle_fixed_schedule_leave_command(command, test_user_id)
            print(f"執行結果:")
            print(f"{result}")
            
            if "請假設置完成" in result:
                print(f"\n✅ 命令執行成功")
            elif "已經處於請假狀態" in result:
                print(f"\n⚠️  班次已在請假狀態")
            else:
                print(f"\n❌ 命令執行失敗") 
                
        except Exception as e:
            print(f"❌ 命令執行異常: {e}")

if __name__ == "__main__":
    test_complete_flow()
    test_direct_command()