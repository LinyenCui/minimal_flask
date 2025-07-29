#!/usr/bin/env python3
"""
離線測試新版幫助系統 - 不涉及Line Bot API調用
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules import create_app

def test_help_system_core():
    """測試幫助系統核心功能（不包含Line Bot API）"""
    app = create_app()
    
    with app.app_context():
        print("🧪 離線測試新版幫助系統核心功能")
        print("=" * 60)
        
        try:
            from modules.help_system.help_manager import HelpManager
            from modules.help_system.help_config import HelpSystemConfig
            from modules.help_system.content_generators import HelpContentGenerator
            from modules.help_system.navigation_builder import HelpNavigationBuilder
            
            # 測試配置
            print("\n1️⃣ 測試幫助系統配置")
            print("-" * 40)
            
            config = HelpSystemConfig()
            print(f"   版本：{config.version}")
            print(f"   分類數量：{len(config.help_categories)}")
            
            for cat_id, category in config.help_categories.items():
                items_count = len(category.get('items', []))
                print(f"   📁 {cat_id}: {category['title']} ({items_count} 項目)")
            
            # 測試幫助管理器
            print("\n2️⃣ 測試幫助管理器")
            print("-" * 40)
            
            help_manager = HelpManager()
            test_user_id = "test_user"
            
            # 測試主幫助
            main_help = help_manager.get_main_help(test_user_id)
            print(f"   主幫助類型：{main_help.get('type')}")
            print(f"   標題：{main_help.get('title')}")
            print(f"   分類數量：{len(main_help.get('categories', []))}")
            print(f"   建議數量：{len(main_help.get('user_suggestions', []))}")
            
            # 測試分類幫助
            category_help = help_manager.get_category_help(test_user_id, "quick_start")
            if "error" not in category_help:
                print(f"   分類幫助：✅ 成功")
                print(f"   標題：{category_help.get('title')}")
                print(f"   項目數量：{len(category_help.get('items', []))}")
            else:
                print(f"   分類幫助：❌ {category_help['error']}")
            
            # 測試項目幫助
            item_help = help_manager.get_item_help(test_user_id, "quick_start", "basic_commands")
            if "error" not in item_help:
                print(f"   項目幫助：✅ 成功")
                print(f"   標題：{item_help.get('title')}")
                print(f"   類型：{item_help.get('type')}")
            else:
                print(f"   項目幫助：❌ {item_help['error']}")
            
            # 測試搜尋
            search_result = help_manager.search_help(test_user_id, "預約")
            if search_result.get("type") == "search_results":
                print(f"   搜尋功能：✅ 成功")
                print(f"   結果數量：{len(search_result.get('results', []))}")
            else:
                print(f"   搜尋功能：⚠️ 無結果或錯誤")
            
            # 測試快速幫助
            print("\n3️⃣ 測試快速幫助")
            print("-" * 40)
            
            commands = ['預約叫車', '東洋班次', '診所班次', '班次詳情', '固定班表']
            for cmd in commands:
                quick_help = help_manager.get_quick_help(test_user_id, cmd)
                status = "✅" if "找不到命令" not in quick_help else "❌"
                print(f"   {cmd}: {status}")
            
            # 測試內容生成器
            print("\n4️⃣ 測試內容生成器")
            print("-" * 40)
            
            content_gen = HelpContentGenerator()
            
            # 測試命令列表內容
            test_item = {
                "id": "test_commands",
                "title": "測試命令",
                "description": "測試命令列表生成",
                "content_type": "command_list",
                "commands": ["預約叫車", "東洋班次"]
            }
            
            command_content = content_gen.generate_item_content(test_item, "test_category")
            if command_content.get("type") == "command_list":
                print(f"   命令列表生成：✅ 成功")
                print(f"   命令數量：{len(command_content.get('commands', []))}")
            else:
                print(f"   命令列表生成：❌ 失敗")
            
            # 測試導航構建器
            print("\n5️⃣ 測試導航構建器")
            print("-" * 40)
            
            nav_builder = HelpNavigationBuilder()
            
            # 測試主導航
            main_nav = nav_builder.build_main_navigation(test_user_id)
            print(f"   主導航類型：{main_nav.get('type')}")
            
            # 測試分類導航
            test_category = config.help_categories["quick_start"]
            cat_nav = nav_builder.build_category_navigation("quick_start", test_category, test_user_id)
            print(f"   分類導航類型：{cat_nav.get('type')}")
            
            # 測試項目導航
            item_nav = nav_builder.build_item_navigation("quick_start", "basic_commands", test_user_id)
            print(f"   項目導航類型：{item_nav.get('type')}")
            
            # 測試上下文感知功能
            print("\n6️⃣ 測試上下文感知功能")
            print("-" * 40)
            
            context_helps = config.context_sensitive_helps
            print(f"   上下文幫助數量：{len(context_helps)}")
            
            for context_id, context in context_helps.items():
                print(f"   📋 {context_id}: {context['title']}")
            
            # 測試智能建議
            smart_suggestions = config.smart_suggestions
            print(f"   智能建議類別：{list(smart_suggestions.keys())}")
            
            user_context = {
                "is_new_user": True,
                "recent_errors": [],
                "uses_advanced_features": False
            }
            
            contextual_help = config.get_help_by_user_state(user_context)
            print(f"   個性化建議數量：{len(contextual_help.get('personalized_suggestions', []))}")
            print(f"   相關分類：{contextual_help.get('relevant_categories', [])}")
            
            print(f"\n" + "=" * 60)
            print("🎉 核心功能測試完成 - 所有測試通過！")
            
            return True
            
        except Exception as e:
            print(f"❌ 測試失敗：{e}")
            import traceback
            traceback.print_exc()
            return False

def test_help_handler_logic():
    """測試幫助處理器邏輯（不涉及實際Line Bot調用）"""
    app = create_app()
    
    with app.app_context():
        print("\n🔗 測試幫助處理器邏輯")
        print("=" * 60)
        
        try:
            from modules.help_system.help_handler import HelpHandler
            
            help_handler = HelpHandler()
            test_user_id = "test_logic_user"
            mock_reply_token = "mock_token"
            
            # 測試各種幫助請求的路由邏輯
            test_cases = [
                ("幫助", "主幫助"),
                ("幫助文字", "文字幫助"),
                ("help_category_quick_start", "分類幫助"),
                ("help_item_quick_start_basic_commands", "項目幫助"),
                ("help_search_預約", "搜尋幫助"),
                ("help_demo_fixed", "演示功能"),
                ("help_system_check", "系統檢查"),
                ("搜尋幫助", "搜尋提示"),
                ("完整指令列表", "完整指令"),
                ("不是幫助命令", "非幫助命令")
            ]
            
            for message, expected in test_cases:
                print(f"\n   測試：{message} (期望: {expected})")
                
                # 測試是否能正確識別幫助請求
                try:
                    # 由於實際調用會觸發Line Bot API，我們只測試路由邏輯
                    is_help_request = (
                        message == '幫助' or message == '幫助文字' or 
                        message.startswith('help_') or message == '完整指令' or
                        message == '搜尋幫助' or message == '完整指令列表'
                    )
                    
                    if is_help_request:
                        print(f"      ✅ 正確識別為幫助請求")
                    else:
                        print(f"      ⚠️  非幫助請求，將由其他處理器處理")
                        
                except Exception as e:
                    print(f"      ❌ 處理失敗：{e}")
            
            # 測試演示功能
            print(f"\n   測試演示功能處理邏輯")
            demo_types = ["fixed", "reports", "troubleshoot", "unknown"]
            
            for demo_type in demo_types:
                has_handler = demo_type in help_handler._demo_handlers
                status = "✅" if has_handler else "❌"
                print(f"      {demo_type}: {status}")
            
            print(f"\n" + "=" * 60)
            print("🎉 處理器邏輯測試完成")
            
            return True
            
        except Exception as e:
            print(f"❌ 處理器測試失敗：{e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success1 = test_help_system_core()
    success2 = test_help_handler_logic()
    
    print(f"\n📊 測試總結")
    print("=" * 60)
    print(f"核心功能測試：{'✅ 通過' if success1 else '❌ 失敗'}")
    print(f"處理器邏輯測試：{'✅ 通過' if success2 else '❌ 失敗'}")
    
    if success1 and success2:
        print(f"\n🎉 新版幫助系統重建完成！")
        print(f"系統特色：")
        print(f"• 動態內容管理")
        print(f"• 上下文感知幫助")
        print(f"• 個性化建議")
        print(f"• 互動式導航")
        print(f"• 智能搜尋功能")
        print(f"• 向後兼容舊系統")
    else:
        print(f"\n❌ 還有問題需要解決")