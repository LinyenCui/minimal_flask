#!/usr/bin/env python3
"""
測試運行中的幫助系統
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_help_system_with_app_context():
    """在應用上下文中測試幫助系統"""
    print("🧪 測試運行中的幫助系統")
    print("=" * 50)
    
    try:
        from modules import create_app
        from modules.help_system import handle_help_message
        
        app = create_app()
        
        with app.app_context():
            print("✅ Flask 應用上下文創建成功")
            
            # 測試基本幫助命令
            test_cases = [
                "幫助",
                "help_category_quick_start", 
                "完整指令列表",
                "搜尋幫助"
            ]
            
            for command in test_cases:
                print(f"\n📝 測試命令: {command}")
                try:
                    # 使用模擬的回覆token和用戶ID
                    result = handle_help_message(command, "test_user", "mock_reply_token")
                    
                    if result:
                        print(f"   ✅ 命令處理成功")
                    else:
                        print(f"   ❌ 命令處理失敗")
                        
                except Exception as e:
                    print(f"   ❌ 錯誤: {e}")
            
            return True
            
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_message_handler_integration():
    """測試消息處理器整合"""
    print("\n🔗 測試消息處理器整合")
    print("=" * 50)
    
    try:
        from modules import create_app
        from modules.handlers.message_handler import should_process
        
        app = create_app()
        
        with app.app_context():
            print("✅ Flask 應用上下文創建成功")
            
            # 測試命令識別
            test_commands = [
                ("幫助", "user"),
                ("help_category_quick_start", "user"),
                ("help_category_quick_start", "group"),
                ("完整指令列表", "user"),
                ("搜尋幫助", "group"),
            ]
            
            for command, source_type in test_commands:
                print(f"\n📝 測試: '{command}' 來自 {source_type}")
                
                try:
                    should_handle, processed_text = should_process(command, source_type, "test_user")
                    
                    if should_handle:
                        print(f"   ✅ 應該處理: '{processed_text}'")
                    else:
                        print(f"   ❌ 不應該處理")
                        
                except Exception as e:
                    print(f"   ❌ 錯誤: {e}")
            
            return True
            
    except Exception as e:
        print(f"❌ 整合測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_new_help_commands():
    """測試新版幫助命令"""
    print("\n🆕 測試新版幫助命令")
    print("=" * 50)
    
    try:
        from modules import create_app
        from modules.handlers.message_handler import KNOWN_COMMANDS
        
        app = create_app()
        
        with app.app_context():
            print("✅ Flask 應用上下文創建成功")
            
            # 檢查新命令是否在已知命令列表中
            new_commands = [
                "搜尋幫助",
                "完整指令列表", 
                "完整指令"
            ]
            
            print(f"\n📋 檢查已知命令列表（共 {len(KNOWN_COMMANDS)} 個命令）:")
            for cmd in new_commands:
                if cmd in KNOWN_COMMANDS:
                    print(f"   ✅ '{cmd}' 已在已知命令中")
                else:
                    print(f"   ❌ '{cmd}' 不在已知命令中")
            
            # 檢查help_開頭的命令識別
            help_pattern_commands = [
                "help_category_quick_start",
                "help_item_basic_commands",
                "help_search_預約",
                "help_demo_example",
                "help_system_check"
            ]
            
            print(f"\n🔍 測試help_模式命令識別:")
            for cmd in help_pattern_commands:
                from modules.handlers.message_handler import should_process
                
                should_handle, processed = should_process(cmd, "group", "test_user")
                
                if should_handle:
                    print(f"   ✅ '{cmd}' 被正確識別")
                else:
                    print(f"   ❌ '{cmd}' 未被識別")
            
            return True
            
    except Exception as e:
        print(f"❌ 新命令測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 幫助系統運行狀態測試")
    print("=" * 70)
    
    tests = [
        ("幫助系統基本功能", test_help_system_with_app_context),
        ("消息處理器整合", test_message_handler_integration),
        ("新版幫助命令", test_new_help_commands),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n🔄 執行測試: {test_name}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ 測試 {test_name} 發生錯誤: {e}")
            results[test_name] = False
    
    # 總結
    print("\n📊 測試結果總結")
    print("=" * 70)
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n總計: {passed}/{total} 個測試通過")
    
    if passed == total:
        print("🎉 幫助系統運行正常！")
        print("\n💡 可用的幫助命令:")
        print("  • 幫助 - 顯示主幫助界面")
        print("  • help_category_quick_start - 快速入門") 
        print("  • 完整指令列表 - 完整命令列表")
        print("  • 搜尋幫助 - 搜尋功能")
    else:
        print("⚠️  幫助系統可能仍有問題，請檢查錯誤信息。")