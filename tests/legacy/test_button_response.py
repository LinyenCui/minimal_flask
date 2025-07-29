#!/usr/bin/env python3
"""
測試新版幫助系統按鈕響應問題
"""
import sys
from pathlib import Path
import requests
import json

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_webhook_response():
    """測試webhook對新幫助命令的響應"""
    
    # 測試命令列表
    test_commands = [
        "幫助",
        "help_category_quick_start", 
        "help_category_time_states",
        "help_category_advanced_features",
        "help_category_troubleshooting",
        "搜尋幫助",
        "完整指令列表"
    ]
    
    webhook_url = "http://localhost:5000/callback"
    
    for command in test_commands:
        print(f"\n測試命令: {command}")
        print("-" * 40)
        
        # 構建Line Bot消息格式
        line_event = {
            "events": [
                {
                    "type": "message",
                    "message": {
                        "type": "text",
                        "text": command,
                        "id": "test_message_id"
                    },
                    "source": {
                        "type": "user",
                        "userId": "test_user_id"
                    },
                    "replyToken": "test_reply_token",
                    "timestamp": 1643723400000
                }
            ]
        }
        
        try:
            # 發送測試請求
            response = requests.post(
                webhook_url,
                headers={
                    "Content-Type": "application/json",
                    "X-Line-Signature": "test_signature"
                },
                data=json.dumps(line_event),
                timeout=10
            )
            
            print(f"狀態碼: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Webhook正常響應")
            else:
                print(f"❌ Webhook響應異常: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print("❌ 無法連接到本地服務器 - 應用可能未運行")
        except requests.exceptions.Timeout:
            print("⏰ 請求超時")
        except Exception as e:
            print(f"❌ 測試失敗: {e}")

def test_direct_import():
    """直接測試幫助系統導入"""
    print("\n🔍 測試幫助系統模組導入")
    print("=" * 50)
    
    try:
        # 測試模組導入
        from modules.help_system import handle_help_message, help_handler
        print("✅ 模組導入成功")
        
        # 測試處理器初始化
        print(f"✅ 幫助處理器類型: {type(help_handler)}")
        
        # 測試配置
        config = help_handler.help_manager.config
        print(f"✅ 配置版本: {config.version}")
        print(f"✅ 分類數量: {len(config.help_categories)}")
        
        # 測試命令識別
        test_messages = [
            "幫助",
            "help_category_quick_start",
            "搜尋幫助", 
            "不是幫助命令"
        ]
        
        for msg in test_messages:
            # 檢查是否為幫助命令
            is_help = (
                msg == '幫助' or msg == '幫助文字' or 
                msg.startswith('help_') or msg == '完整指令' or
                msg == '搜尋幫助' or msg == '完整指令列表'
            )
            status = "✅" if is_help else "⚠️"
            print(f"   {status} {msg}: {'幫助命令' if is_help else '非幫助命令'}")
        
        return True
        
    except Exception as e:
        print(f"❌ 導入測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_text_handler_integration():
    """測試與text_message_handler的整合"""
    print("\n🔗 測試text_message_handler整合")
    print("=" * 50)
    
    try:
        from modules.handlers.text_message_handler import handle_text_message
        print("✅ text_message_handler導入成功")
        
        # 檢查幫助處理邏輯是否存在
        import inspect
        source = inspect.getsource(handle_text_message)
        
        if "help_system" in source:
            print("✅ 發現新版幫助系統整合代碼")
        else:
            print("❌ 未發現新版幫助系統整合代碼")
            
        if "handle_help_message" in source:
            print("✅ 發現handle_help_message調用")
        else:
            print("❌ 未發現handle_help_message調用")
            
        return True
        
    except Exception as e:
        print(f"❌ 整合測試失敗: {e}")
        return False

if __name__ == "__main__":
    print("🧪 測試新版幫助系統按鈕響應問題")
    print("=" * 60)
    
    # 先測試直接導入
    import_ok = test_direct_import()
    
    # 測試整合
    integration_ok = test_text_handler_integration()
    
    # 如果導入和整合都正常，測試webhook
    if import_ok and integration_ok:
        test_webhook_response()
    else:
        print("\n❌ 基礎測試失敗，跳過webhook測試")
    
    print(f"\n📊 測試總結")
    print("=" * 60)
    print(f"模組導入: {'✅' if import_ok else '❌'}")
    print(f"整合測試: {'✅' if integration_ok else '❌'}")
    
    if import_ok and integration_ok:
        print("\n💡 建議檢查項目：")
        print("1. 確認應用已重啟並載入新代碼")
        print("2. 檢查Line Bot API調用是否正常")
        print("3. 查看服務器日誌中的錯誤信息")
    else:
        print("\n🔧 需要修復基礎問題後重新測試")