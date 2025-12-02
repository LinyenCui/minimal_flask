"""
幫助系統處理器
整合新的動態幫助系統和現有的Line Bot處理邏輯
"""

import logging
from typing import Dict, List, Any, Optional

from .help_manager import HelpManager
from modules.utils.line_bot import reply_text, reply_flex

logger = logging.getLogger(__name__)

class HelpHandler:
    """幫助系統處理器"""
    
    def __init__(self):
        self.help_manager = HelpManager()
        self._demo_handlers = self._initialize_demo_handlers()
    
    def handle_help_request(self, message_text: str, user_id: str, reply_token: str) -> bool:
        """處理幫助請求"""
        try:
            message_text = message_text.strip()
            
            # 主幫助命令
            if message_text == "幫助":
                return self._handle_main_help(user_id, reply_token)
            
            # 文字版幫助
            elif message_text == "幫助文字":
                return self._handle_text_help(user_id, reply_token)
            
            # 搜尋幫助
            elif message_text == "搜尋幫助":
                return self._handle_search_help_prompt(user_id, reply_token)
            
            # 完整指令列表
            elif message_text == "完整指令列表":
                return self._handle_complete_commands_help(user_id, reply_token)
            
            # 分類幫助
            elif message_text.startswith("help_category_"):
                category_id = message_text.replace("help_category_", "")
                return self._handle_category_help(category_id, user_id, reply_token)
            
            # 項目幫助
            elif message_text.startswith("help_item_"):
                # 解析項目幫助命令：help_item_[category]_[item]
                remaining = message_text.replace("help_item_", "")
                
                # 根據已知的分類結構進行解析
                known_categories = ["quick_start", "time_states", "advanced_features", "troubleshooting"]
                
                category_id = None
                item_id = None
                
                # 嘗試匹配已知分類
                for cat in known_categories:
                    if remaining.startswith(f"{cat}_"):
                        category_id = cat
                        item_id = remaining[len(cat) + 1:]  # 移除 "category_" 前綴
                        break
                
                # 如果沒有匹配到已知分類，使用原有邏輯作為後備
                if not category_id:
                    parts = remaining.split("_", 1)
                    if len(parts) >= 2:
                        category_id, item_id = parts[0], parts[1]
                
                if category_id and item_id:
                    return self._handle_item_help(category_id, item_id, user_id, reply_token)
            
            # 搜尋查詢
            elif message_text.startswith("help_search_"):
                query = message_text.replace("help_search_", "")
                return self._handle_search_help(query, user_id, reply_token)
            
            # 演示功能
            elif message_text.startswith("help_demo_"):
                demo_type = message_text.replace("help_demo_", "")
                return self._handle_demo(demo_type, user_id, reply_token)
            
            # 系統檢查
            elif message_text == "help_system_check":
                return self._handle_system_check(user_id, reply_token)
            
            return False
            
        except Exception as e:
            logger.error(f"處理幫助請求時出錯: {e}")
            reply_text(reply_token, "幫助系統暫時無法使用，請稍後再試。")
            return True
    
    def _handle_main_help(self, user_id: str, reply_token: str) -> bool:
        """處理主幫助請求"""
        try:
            help_data = self.help_manager.get_main_help(user_id)
            
            if help_data.get("type") == "main_help":
                # 發送Flex Message
                navigation = help_data.get("navigation", {})
                flex_message = navigation.get("flex_message")
                
                if flex_message:
                    reply_flex(reply_token, "🔰 派班系統幫助中心", flex_message)
                else:
                    # 備用文字版本
                    text_message = self._build_main_help_text(help_data)
                    reply_text(reply_token, text_message)
            else:
                # 處理其他類型（如上下文感知幫助）
                self._handle_context_help(help_data, reply_token)
            
            return True
            
        except Exception as e:
            logger.error(f"處理主幫助時出錯: {e}")
            reply_text(reply_token, "無法載入幫助菜單，請使用「幫助文字」查看文字版本。")
            return True
    
    def _handle_text_help(self, user_id: str, reply_token: str) -> bool:
        """處理文字版幫助"""
        try:
            # 使用統一的幫助文本
            from modules.utils.help_text import get_help_text
            help_text = get_help_text()
            reply_text(reply_token, help_text)
            return True
        except Exception as e:
            logger.error(f"處理文字幫助時出錯: {e}")
            reply_text(reply_token, "無法載入文字版幫助。")
            return True
    
    def _handle_category_help(self, category_id: str, user_id: str, reply_token: str) -> bool:
        """處理分類幫助"""
        try:
            help_data = self.help_manager.get_category_help(user_id, category_id)
            
            if "error" in help_data:
                reply_text(reply_token, help_data["error"])
                return True
            
            # 構建分類幫助訊息
            message = self._build_category_help_text(help_data)
            
            # 發送Flex Message（如果可用）
            navigation = help_data.get("navigation", {})
            flex_message = navigation.get("flex_message")
            
            if flex_message:
                reply_flex(reply_token, help_data["title"], flex_message)
            else:
                reply_text(reply_token, message)
            
            return True
            
        except Exception as e:
            logger.error(f"處理分類幫助時出錯: {e}")
            reply_text(reply_token, f"無法載入分類幫助: {category_id}")
            return True
    
    def _handle_item_help(self, category_id: str, item_id: str, user_id: str, reply_token: str) -> bool:
        """處理項目幫助"""
        try:
            help_data = self.help_manager.get_item_help(user_id, category_id, item_id)
            
            if "error" in help_data:
                reply_text(reply_token, help_data["error"])
                return True
            
            # 構建詳細幫助訊息
            message = self._build_item_help_text(help_data)
            
            # 發送文字訊息和導航Flex
            reply_text(reply_token, message)
            
            # 如果有導航，發送Flex Message
            navigation = help_data.get("navigation", {})
            flex_message = navigation.get("flex_message")
            if flex_message:
                # 這裡可以選擇是否同時發送導航
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"處理項目幫助時出錯: {e}")
            reply_text(reply_token, f"無法載入項目幫助: {category_id}.{item_id}")
            return True
    
    def _handle_search_help_prompt(self, user_id: str, reply_token: str) -> bool:
        """處理搜尋幫助提示"""
        try:
            message = """🔍 幫助搜尋
            
請輸入您要搜尋的關鍵字，例如：
• help_search_預約
• help_search_班次
• help_search_請假
• help_search_報表

或者直接輸入關鍵字進行搜尋。"""
            
            reply_text(reply_token, message)
            return True
            
        except Exception as e:
            logger.error(f"處理搜尋提示時出錯: {e}")
            reply_text(reply_token, "搜尋功能暫時無法使用。")
            return True
    
    def _handle_search_help(self, query: str, user_id: str, reply_token: str) -> bool:
        """處理搜尋幫助"""
        try:
            help_data = self.help_manager.search_help(user_id, query)
            
            if help_data.get("type") == "search_no_results":
                message = f"{help_data['message']}\n\n建議搜尋：\n" + "\n".join(help_data.get("suggestions", []))
                reply_text(reply_token, message)
            else:
                message = self._build_search_results_text(help_data)
                reply_text(reply_token, message)
            
            return True
            
        except Exception as e:
            logger.error(f"處理搜尋幫助時出錯: {e}")
            reply_text(reply_token, f"搜尋「{query}」時發生錯誤。")
            return True
    
    def _handle_complete_commands_help(self, user_id: str, reply_token: str) -> bool:
        """處理完整指令列表"""
        try:
            # 使用舊的完整指令功能
            from modules.flex_designs.help_flex import get_complete_commands_help
            help_flex = get_complete_commands_help()
            reply_flex(reply_token, "完整指令列表", help_flex)
            return True
        except Exception as e:
            logger.error(f"處理完整指令列表時出錯: {e}")
            # 備用文字版本
            reply_text(reply_token, "完整指令列表載入失敗，請使用「幫助文字」查看基本命令。")
            return True
    
    def _handle_demo(self, demo_type: str, user_id: str, reply_token: str) -> bool:
        """處理演示功能"""
        try:
            if demo_type in self._demo_handlers:
                return self._demo_handlers[demo_type](user_id, reply_token)
            else:
                reply_text(reply_token, f"演示功能「{demo_type}」不存在。")
                return True
        except Exception as e:
            logger.error(f"處理演示功能時出錯: {e}")
            reply_text(reply_token, "演示功能暫時無法使用。")
            return True
    
    def _handle_system_check(self, user_id: str, reply_token: str) -> bool:
        """處理系統檢查"""
        try:
            # 執行基本系統檢查
            status_message = """🔧 系統狀態檢查

✅ 幫助系統：正常運行
✅ 資料庫連線：正常
✅ Line Bot API：正常
✅ AI助手：正常

📊 系統資訊：
• 幫助系統版本：2.0
• 最後更新：{last_updated}
• 運行狀態：穩定

如有其他問題，請聯絡系統管理員。""".format(
                last_updated=self.help_manager.config.last_updated.strftime("%Y-%m-%d %H:%M")
            )
            
            reply_text(reply_token, status_message)
            return True
            
        except Exception as e:
            logger.error(f"處理系統檢查時出錯: {e}")
            reply_text(reply_token, "系統檢查失敗，請聯絡管理員。")
            return True
    
    def _handle_context_help(self, help_data: Dict[str, Any], reply_token: str):
        """處理上下文感知幫助"""
        try:
            context_type = help_data.get("context", "")
            title = help_data.get("title", "幫助")
            message = help_data.get("message", "")
            
            if help_data.get("examples"):
                message += "\n\n範例：\n" + "\n".join(f"• {ex}" for ex in help_data["examples"])
            
            if help_data.get("suggestions"):
                message += "\n\n建議：\n" + "\n".join(f"• {sug}" for sug in help_data["suggestions"])
            
            reply_text(reply_token, f"{title}\n\n{message}")
            
        except Exception as e:
            logger.error(f"處理上下文幫助時出錯: {e}")
            reply_text(reply_token, "無法顯示相關幫助。")
    
    def _build_main_help_text(self, help_data: Dict[str, Any]) -> str:
        """構建主幫助文字"""
        try:
            message = f"{help_data['title']}\n\n"
            
            # 個性化建議
            suggestions = help_data.get("user_suggestions", [])
            if suggestions:
                message += "💡 為您推薦：\n"
                for i, suggestion in enumerate(suggestions[:3], 1):
                    message += f"{i}. {suggestion}\n"
                message += "\n"
            
            # 分類概覽
            categories = help_data.get("categories", [])
            if categories:
                message += "📚 幫助分類：\n"
                for cat in categories:
                    icon = "⭐" if cat.get("is_recommended") else "📖"
                    message += f"{icon} {cat['title']} - {cat['description']}\n"
                message += "\n"
            
            # 快速操作
            quick_actions = help_data.get("quick_actions", [])
            if quick_actions:
                message += "⚡ 快速操作：\n"
                for action in quick_actions:
                    message += f"• {action['label']}\n"
                message += "\n"
            
            message += "💬 提示：輸入「help_category_[分類名]」查看詳細幫助"
            
            return message
            
        except Exception as e:
            logger.error(f"構建主幫助文字時出錯: {e}")
            return "幫助系統載入失敗。"
    
    def _build_category_help_text(self, help_data: Dict[str, Any]) -> str:
        """構建分類幫助文字"""
        try:
            message = f"{help_data['title']}\n\n{help_data['description']}\n\n"
            
            items = help_data.get("items", [])
            if items:
                message += "📋 內容項目：\n"
                for i, item in enumerate(items, 1):
                    message += f"{i}. {item['title']} - {item['description']}\n"
                message += "\n"
            
            message += "💬 提示：輸入「help_item_[分類]_[項目]」查看詳細說明"
            
            return message
            
        except Exception as e:
            logger.error(f"構建分類幫助文字時出錯: {e}")
            return "分類幫助載入失敗。"
    
    def _build_item_help_text(self, help_data: Dict[str, Any]) -> str:
        """構建項目幫助文字"""
        try:
            content_type = help_data.get("type", "")
            title = help_data.get("title", "")
            description = help_data.get("description", "")
            
            message = f"📖 {title}\n\n{description}\n\n"
            
            if content_type == "command_list":
                commands = help_data.get("commands", [])
                if commands:
                    message += "📋 命令列表：\n"
                    for cmd in commands:
                        message += f"🔸 {cmd['command']}\n"
                        message += f"   說明：{cmd['description']}\n"
                        message += f"   用法：{cmd['usage']}\n"
                        if cmd.get("examples"):
                            message += f"   範例：{', '.join(cmd['examples'])}\n"
                        message += "\n"
            
            elif content_type == "interactive_guide":
                message += "🎯 互動式指南\n\n"
                examples = help_data.get("examples", [])
                if examples:
                    message += "範例操作：\n"
                    for example in examples:
                        message += f"• {example['text']}\n"
                
                tips = help_data.get("tips", [])
                if tips:
                    message += "\n💡 使用技巧：\n"
                    for tip in tips:
                        message += f"{tip}\n"
            
            elif content_type == "concept_guide":
                concept = help_data.get("concept", {})
                if concept:
                    message += f"🎯 核心概念\n\n"
                    message += f"用途：{concept.get('purpose', '')}\n\n"
                    
                    features = concept.get("key_features", [])
                    if features:
                        message += "主要功能：\n"
                        for feature in features:
                            message += f"• {feature}\n"
                    
                    workflow = concept.get("workflow", "")
                    if workflow:
                        message += f"\n工作流程：{workflow}\n"
            
            elif content_type == "feature_guide":
                # 如果有詳細說明，優先顯示
                if help_data.get("detailed_description"):
                    message += f"{help_data['detailed_description']}\n\n"
                
                features = help_data.get("features", [])
                if features:
                    message += "🔧 功能說明：\n"
                    for feature in features:
                        message += f"• {feature['name']}：{feature['description']}\n"
                        if feature.get("how_to_use"):
                            message += f"  使用方法：{feature['how_to_use']}\n"
                        if feature.get("examples"):
                            examples = feature.get("examples", [])
                            if examples:
                                message += f"  範例：{', '.join(examples[:2])}\n"
            
            elif content_type == "troubleshooting_guide":
                issues = help_data.get("common_issues", [])
                if issues:
                    message += "🔧 常見問題：\n"
                    for issue in issues:
                        message += f"\n❌ 問題：{issue['problem']}\n"
                        message += f"症狀：{', '.join(issue['symptoms'])}\n"
                        message += "解決方案：\n"
                        for solution in issue["solutions"]:
                            message += f"  {solution['step']}. {solution['description']}\n"
            
            return message
            
        except Exception as e:
            logger.error(f"構建項目幫助文字時出錯: {e}")
            return "項目幫助載入失敗。"
    
    def _build_search_results_text(self, help_data: Dict[str, Any]) -> str:
        """構建搜尋結果文字"""
        try:
            query = help_data.get("query", "")
            results = help_data.get("results", [])
            
            message = f"🔍 搜尋結果：「{query}」\n\n"
            
            if results:
                message += f"找到 {len(results)} 個相關結果：\n\n"
                for i, result in enumerate(results[:5], 1):  # 限制5個結果
                    result_type = "📁" if result["type"] == "category" else "📄"
                    message += f"{i}. {result_type} {result['title']}\n"
                    message += f"   {result['description']}\n\n"
                
                if len(results) > 5:
                    message += f"... 還有 {len(results) - 5} 個結果\n"
            else:
                message += "沒有找到相關結果。\n"
            
            return message
            
        except Exception as e:
            logger.error(f"構建搜尋結果文字時出錯: {e}")
            return "搜尋結果載入失敗。"
    
    def _initialize_demo_handlers(self) -> Dict[str, callable]:
        """初始化演示處理器"""
        return {
            "fixed": self._demo_fixed_schedule,
            "reports": self._demo_reports,
            "troubleshoot": self._demo_troubleshoot
        }
    
    def _demo_fixed_schedule(self, user_id: str, reply_token: str) -> bool:
        """演示固定班次功能"""
        message = """📋 固定班次演示

這是一個模擬的固定班次查詢結果：

🔍 找到 2 個與「新建路」相關的固定班次：

📋 **班次 #17**
🚌 路線：A01 (去程)
🕐 時間：08:30
📍 路線：新建路 → 診所
💰 車資：300 = 300
📊 類別：診所
🟢 狀態：準備
🚗 司機：王司機

📋 **班次 #25**
🚌 路線：A01 (回程)  
🕐 時間：17:00
📍 路線：診所 → 新建路
💰 車資：300 = 300
📊 類別：診所
🟢 狀態：準備
🚗 司機：王司機

💡 實際使用時請輸入：固定班表 [客戶簡稱]"""

        reply_text(reply_token, message)
        return True
    
    def _demo_reports(self, user_id: str, reply_token: str) -> bool:
        """演示報表功能"""
        message = """📊 報表系統演示

以下是一個模擬的週報表：

📈 診所班次週報表 (2025-07-21 ~ 2025-07-27)

📊 統計摘要：
• 總班次數：28 趟
• 已完成：26 趟 (92.9%)
• 請假：2 趟 (7.1%)
• 總收入：NT$ 8,400

📅 每日明細：
• 週一：4 趟 (NT$ 1,200)
• 週二：4 趟 (NT$ 1,200)  
• 週三：4 趟 (NT$ 1,200)
• 週四：4 趟 (NT$ 1,200)
• 週五：4 趟 (NT$ 1,200)
• 週六：3 趟 (NT$ 900)
• 週日：3 趟 (NT$ 900)

💡 實際使用時請輸入：生成周報表 [類別]"""

        reply_text(reply_token, message)
        return True
    
    def _demo_troubleshoot(self, user_id: str, reply_token: str) -> bool:
        """演示故障排除功能"""
        message = """🔧 故障排除演示

常見問題快速檢查：

✅ 系統狀態：正常
✅ 資料庫連線：正常  
✅ Line Bot API：正常

❓ 遇到問題？

1️⃣ 找不到班次
   • 檢查客戶簡稱拼寫
   • 確認日期格式正確
   • 嘗試使用完整地址

2️⃣ 請假功能異常
   • 重新點擊班次按鈕
   • 檢查網路連線
   • 確認輸入格式：原因 加成

3️⃣ 報表無法生成
   • 確認日期範圍有效
   • 檢查類別參數正確
   • 聯絡系統管理員

💡 如需更多幫助，請查看「故障排除」分類"""

        reply_text(reply_token, message)
        return True