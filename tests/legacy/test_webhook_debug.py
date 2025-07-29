#!/usr/bin/env python3
"""
調試webhook和幫助系統響應問題
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules import create_app
from modules.handlers.text_message_handler import process_text_message

class MockEvent:
    def __init__(self, text, user_id="test_user"):
        self.message = MockMessage(text)
        self.source = MockSource(user_id)
        self.reply_token = "mock_reply_token"

class MockMessage:
    def __init__(self, text):
        self.text = text
        self.type = "text"

class MockSource:
    def __init__(self, user_id):
        self.user_id = user_id
        self.type = "user"

def test_help_system_direct():
    """直接測試幫助系統處理"""
    app = create_app()
    
    with app.app_context():
        print("🧪 直接測試幫助系統處理")
        print("=" * 60)
        
        test_commands = [
            "幫助",
            "help_category_quick_start",
            "help_category_time_states", 
            "help_category_advanced_features",
            "help_category_troubleshooting",
            "搜尋幫助",
            "完整指令列表"
        ]
        
        for command in test_commands:
            print(f"\n測試命令: {command}")
            print("-" * 40)
            
            try:
                # 創建模擬事件
                event = MockEvent(command)
                
                # 捕獲所有輸出
                import io
                import contextlib
                from unittest.mock import patch
                
                # 模擬reply_text和reply_flex函數
                reply_calls = []
                
                def mock_reply_text(token, text):
                    reply_calls.append(("text", text))
                    print(f"   📝 回覆文字: {text[:100]}...")
                
                def mock_reply_flex(token, title, flex):
                    reply_calls.append(("flex", title, flex))
                    print(f"   🎨 回覆Flex: {title}")
                
                # 使用mock來攔截回覆
                with patch('modules.utils.line_bot.reply_text', mock_reply_text), \
                     patch('modules.utils.line_bot.reply_flex', mock_reply_flex):
                    
                    # 調用處理函數
                    process_text_message(event)
                    
                    if reply_calls:
                        print(f"   ✅ 成功處理，回覆 {len(reply_calls)} 個消息")
                        for call_type, *args in reply_calls:
                            if call_type == "text":
                                print(f"      📝 文字回覆")
                            elif call_type == "flex":
                                print(f"      🎨 Flex回覆: {args[0]}")
                    else:
                        print(f"   ⚠️  沒有回覆")
                
            except Exception as e:
                print(f"   ❌ 處理失敗: {e}")
                import traceback
                traceback.print_exc()

def test_help_system_routing():
    """測試幫助系統路由邏輯"""
    app = create_app()
    
    with app.app_context():
        print(f"\n🔍 測試幫助系統路由邏輯")
        print("=" * 60)
        
        try:
            from modules.help_system import handle_help_message
            
            test_cases = [
                ("幫助", True),
                ("help_category_quick_start", True),
                ("搜尋幫助", True),
                ("完整指令列表", True),
                ("東洋班次", False),
                ("預約叫車", False)
            ]
            
            for message, should_handle in test_cases:
                print(f"\n   測試: {message}")
                
                # 檢查路由條件
                is_help_command = (
                    message == '幫助' or message == '幫助文字' or 
                    message.startswith('help_') or message == '完整指令' or
                    message == '搜尋幫助' or message == '完整指令列表'
                )
                
                route_status = "✅" if is_help_command == should_handle else "❌"
                print(f"      路由判斷: {route_status} {'會處理' if is_help_command else '不會處理'}")
                
                if is_help_command:
                    try:
                        # 模擬處理
                        from unittest.mock import patch
                        reply_calls = []
                        
                        def mock_reply(token, text):
                            reply_calls.append(text)
                        
                        with patch('modules.utils.line_bot.reply_text', mock_reply), \
                             patch('modules.utils.line_bot.reply_flex', lambda t, title, flex: reply_calls.append(f"Flex: {title}")):
                            
                            handled = handle_help_message(message, "test_user", "mock_token")
                            
                            if handled and reply_calls:
                                print(f"      處理結果: ✅ 成功處理")
                            elif handled:
                                print(f"      處理結果: ⚠️  處理但無回覆")
                            else:
                                print(f"      處理結果: ❌ 未處理")
                                
                    except Exception as e:
                        print(f"      處理結果: ❌ 錯誤 - {e}")
        
        except Exception as e:
            print(f"❌ 路由測試失敗: {e}")

def test_text_handler_flow():
    """測試完整的文字處理流程"""
    app = create_app()
    
    with app.app_context():
        print(f"\n🔄 測試完整文字處理流程")
        print("=" * 60)
        
        test_message = "help_category_quick_start"
        
        try:
            # 檢查text_message_handler中的條件
            print(f"   測試消息: {test_message}")
            
            # 檢查幫助條件
            help_conditions = [
                test_message == '幫助',
                test_message == '幫助文字',
                test_message.startswith('help_'),
                test_message == '完整指令',
                test_message == '搜尋幫助',
                test_message == '完整指令列表'
            ]
            
            matches_help = any(help_conditions)
            print(f"   符合幫助條件: {'✅' if matches_help else '❌'}")
            
            if matches_help:
                print(f"   幫助條件詳情:")
                conditions = ['幫助', '幫助文字', 'help_*', '完整指令', '搜尋幫助', '完整指令列表']
                for i, (cond, result) in enumerate(zip(conditions, help_conditions)):
                    print(f"      {cond}: {'✅' if result else '❌'}")
            
            # 模擬完整處理流程
            from unittest.mock import patch
            processed = False
            
            def mock_handle_help(msg, user, token):
                nonlocal processed
                processed = True
                print(f"   新版幫助系統被調用: ✅")
                return True
            
            with patch('modules.help_system.handle_help_message', mock_handle_help):
                event = MockEvent(test_message)
                process_text_message(event)
                
                if processed:
                    print(f"   流程結果: ✅ 新版幫助系統成功處理")
                else:
                    print(f"   流程結果: ❌ 新版幫助系統未被調用")
        
        except Exception as e:
            print(f"   ❌ 流程測試失敗: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_help_system_direct()
    test_help_system_routing()
    test_text_handler_flow()