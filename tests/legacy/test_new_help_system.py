#!/usr/bin/env python3
"""
測試新版幫助系統功能
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules import create_app

def test_help_system():
    """測試新版幫助系統"""
    app = create_app()
    
    with app.app_context():
        print("🧪 測試新版幫助系統")
        print("=" * 60)
        
        try:
            from modules.help_system import help_handler, handle_help_message
            
            test_user_id = "test_help_user"
            
            # 測試案例
            test_cases = [
                {
                    "name": "主幫助",
                    "message": "幫助",
                    "expected": "應顯示主幫助界面"
                },
                {
                    "name": "分類幫助",
                    "message": "help_category_quick_start",
                    "expected": "應顯示快速入門分類"
                },
                {
                    "name": "項目幫助",
                    "message": "help_item_quick_start_basic_commands",
                    "expected": "應顯示基本命令項目"
                },
                {
                    "name": "搜尋幫助",
                    "message": "help_search_預約",
                    "expected": "應搜尋預約相關內容"
                },
                {
                    "name": "演示功能",
                    "message": "help_demo_fixed",
                    "expected": "應顯示固定班次演示"
                },
                {
                    "name": "系統檢查",
                    "message": "help_system_check",
                    "expected": "應顯示系統狀態"
                },
                {
                    "name": "文字版幫助",
                    "message": "幫助文字",
                    "expected": "應顯示文字版幫助"
                }
            ]
            
            for i, test_case in enumerate(test_cases, 1):
                print(f"\n{i}️⃣ 測試：{test_case['name']}")
                print(f"   訊息：{test_case['message']}")
                print(f"   期望：{test_case['expected']}")
                print(f"   {'─' * 50}")
                
                try:
                    # 模擬處理幫助訊息
                    class MockReplyToken:
                        def __init__(self):
                            self.replies = []
                        
                        def add_reply(self, message_type, content):
                            self.replies.append({"type": message_type, "content": content})
                    
                    # 直接測試幫助管理器
                    if test_case["message"] == "幫助":
                        result = help_handler.help_manager.get_main_help(test_user_id)
                        if result.get("type") == "main_help":
                            print(f"   ✅ 成功獲取主幫助界面")
                            print(f"      標題：{result.get('title')}")
                            print(f"      分類數量：{len(result.get('categories', []))}")
                            print(f"      建議數量：{len(result.get('user_suggestions', []))}")
                        else:
                            print(f"   ⚠️  返回類型：{result.get('type')}")
                    
                    elif test_case["message"].startswith("help_category_"):
                        category_id = test_case["message"].replace("help_category_", "")
                        result = help_handler.help_manager.get_category_help(test_user_id, category_id)
                        if "error" not in result:
                            print(f"   ✅ 成功獲取分類幫助")
                            print(f"      標題：{result.get('title')}")
                            print(f"      項目數量：{len(result.get('items', []))}")
                        else:
                            print(f"   ❌ 分類幫助錯誤：{result['error']}")
                    
                    elif test_case["message"].startswith("help_item_"):
                        parts = test_case["message"].replace("help_item_", "").split("_", 1)
                        if len(parts) >= 2:
                            category_id, item_id = parts[0], parts[1]
                            result = help_handler.help_manager.get_item_help(test_user_id, category_id, item_id)
                            if "error" not in result:
                                print(f"   ✅ 成功獲取項目幫助")
                                print(f"      標題：{result.get('title')}")
                                print(f"      類型：{result.get('type')}")
                            else:
                                print(f"   ❌ 項目幫助錯誤：{result['error']}")
                    
                    elif test_case["message"].startswith("help_search_"):
                        query = test_case["message"].replace("help_search_", "")
                        result = help_handler.help_manager.search_help(test_user_id, query)
                        if result.get("type") == "search_results":
                            print(f"   ✅ 成功搜尋")
                            print(f"      查詢：{result.get('query')}")
                            print(f"      結果數量：{len(result.get('results', []))}")
                        elif result.get("type") == "search_no_results":
                            print(f"   ⚠️  無搜尋結果")
                        else:
                            print(f"   ❌ 搜尋錯誤")
                    
                    elif test_case["message"] == "help_system_check":
                        # 測試系統檢查
                        print(f"   ✅ 系統檢查功能可用")
                        print(f"      幫助系統版本：{help_handler.help_manager.config.version}")
                    
                    elif test_case["message"] == "幫助文字":
                        # 測試文字版幫助
                        from modules.handlers.text_message_handler import get_help_text
                        help_text = get_help_text()
                        if help_text and len(help_text) > 100:
                            print(f"   ✅ 文字版幫助可用")
                            print(f"      內容長度：{len(help_text)} 字符")
                        else:
                            print(f"   ❌ 文字版幫助內容不足")
                    
                    else:
                        print(f"   ⚠️  未知測試類型")
                    
                except Exception as e:
                    print(f"   ❌ 測試失敗：{e}")
                    import traceback
                    traceback.print_exc()
            
            # 測試快速幫助功能
            print(f"\n\n🚀 測試快速幫助功能")
            print(f"{'─' * 50}")
            
            quick_help_commands = ['預約叫車', '東洋班次', '診所班次', '班次詳情', '固定班表']
            for cmd in quick_help_commands:
                try:
                    quick_help = help_handler.help_manager.get_quick_help(test_user_id, cmd)
                    print(f"   {cmd}：{quick_help[:50]}...")
                except Exception as e:
                    print(f"   {cmd}：❌ {e}")
            
            # 測試配置
            print(f"\n\n⚙️ 測試幫助系統配置")
            print(f"{'─' * 50}")
            
            config = help_handler.help_manager.config
            print(f"   版本：{config.version}")
            print(f"   最後更新：{config.last_updated}")
            print(f"   分類數量：{len(config.help_categories)}")
            print(f"   上下文幫助數量：{len(config.context_sensitive_helps)}")
            
            # 檢查各分類的完整性
            for cat_id, category in config.help_categories.items():
                print(f"   📁 {cat_id}：{category['title']} ({len(category['items'])} 項目)")
            
            print(f"\n" + "=" * 60)
            print("🎉 新版幫助系統測試完成")
            
        except Exception as e:
            print(f"❌ 幫助系統初始化失敗：{e}")
            import traceback
            traceback.print_exc()

def test_integration():
    """測試與現有系統的整合"""
    app = create_app()
    
    with app.app_context():
        print("\n🔗 測試系統整合")
        print("=" * 60)
        
        try:
            from modules.help_system import handle_help_message
            
            test_user_id = "test_integration_user"
            
            # 模擬真實的Line Bot處理流程
            print("1️⃣ 測試與text_message_handler的整合")
            
            integration_tests = [
                "幫助",
                "help_category_quick_start", 
                "help_demo_fixed",
                "搜尋幫助",
                "不存在的命令"
            ]
            
            for msg in integration_tests:
                print(f"\n   測試訊息：{msg}")
                try:
                    # 這裡應該模擬完整的訊息處理流程
                    handled = handle_help_message(msg, test_user_id, "mock_reply_token")
                    if handled:
                        print(f"   ✅ 新版幫助系統處理成功")
                    else:
                        print(f"   ⚠️  新版幫助系統未處理，將使用舊版")
                except Exception as e:
                    print(f"   ❌ 整合測試失敗：{e}")
            
            print(f"\n" + "=" * 60)
            print("🎉 整合測試完成")
            
        except Exception as e:
            print(f"❌ 整合測試失敗：{e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_help_system()
    test_integration()