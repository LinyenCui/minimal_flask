"""
幫助系統管理器 - 新一代動態幫助系統
提供上下文感知、個性化的幫助體驗
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from .help_config import HelpSystemConfig
from .content_generators import HelpContentGenerator
from .navigation_builder import HelpNavigationBuilder
from modules.utils.conversation_context import conversation_manager

logger = logging.getLogger(__name__)

class HelpManager:
    """幫助系統核心管理器"""
    
    def __init__(self):
        self.config = HelpSystemConfig()
        self.content_generator = HelpContentGenerator()
        self.navigation_builder = HelpNavigationBuilder()
        self._user_help_history = {}  # 記錄用戶幫助使用歷史
        
    def get_main_help(self, user_id: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """獲取主幫助界面"""
        try:
            logger.info(f"用戶 {user_id} 請求主幫助界面")
            
            # 獲取用戶上下文
            if not user_context:
                user_context = self._build_user_context(user_id)
            
            # 檢查是否需要上下文感知幫助
            context_help = self._get_context_sensitive_help(user_id, user_context)
            if context_help:
                return context_help
            
            # 構建個性化主幫助界面
            help_data = self._build_main_help_interface(user_id, user_context)
            
            # 記錄幫助使用
            self._record_help_usage(user_id, "main_help")
            
            return help_data
            
        except Exception as e:
            logger.error(f"獲取主幫助界面時出錯: {e}")
            return self._get_fallback_help()
    
    def get_category_help(self, user_id: str, category_id: str) -> Dict[str, Any]:
        """獲取特定分類的幫助"""
        try:
            logger.info(f"用戶 {user_id} 請求分類幫助: {category_id}")
            
            categories = self.config.help_categories
            if category_id not in categories:
                return {"error": f"找不到幫助分類: {category_id}"}
            
            category = categories[category_id]
            help_data = self.content_generator.generate_category_content(category)
            
            # 添加導航
            help_data["navigation"] = self.navigation_builder.build_category_navigation(
                category_id, category, user_id
            )
            
            # 記錄使用
            self._record_help_usage(user_id, f"category_{category_id}")
            
            return help_data
            
        except Exception as e:
            logger.error(f"獲取分類幫助時出錯: {e}")
            return self._get_fallback_help()
    
    def get_item_help(self, user_id: str, category_id: str, item_id: str) -> Dict[str, Any]:
        """獲取特定項目的詳細幫助"""
        try:
            logger.info(f"用戶 {user_id} 請求項目幫助: {category_id}.{item_id}")
            
            categories = self.config.help_categories
            if category_id not in categories:
                return {"error": f"找不到幫助分類: {category_id}"}
            
            category = categories[category_id]
            item = None
            
            for cat_item in category["items"]:
                if cat_item["id"] == item_id:
                    item = cat_item
                    break
            
            if not item:
                return {"error": f"找不到幫助項目: {item_id}"}
            
            # 生成詳細內容  
            help_data = self.content_generator.generate_item_content(item, category_id)
            
            # 添加導航
            help_data["navigation"] = self.navigation_builder.build_item_navigation(
                category_id, item_id, user_id
            )
            
            # 記錄使用
            self._record_help_usage(user_id, f"item_{category_id}_{item_id}")
            
            return help_data
            
        except Exception as e:
            logger.error(f"獲取項目幫助時出錯: {e}")
            return self._get_fallback_help()
    
    def search_help(self, user_id: str, query: str) -> Dict[str, Any]:
        """搜尋幫助內容"""
        try:
            logger.info(f"用戶 {user_id} 搜尋幫助: {query}")
            
            results = self._search_help_content(query)
            
            if not results:
                return {
                    "type": "search_no_results",
                    "message": f"找不到與「{query}」相關的幫助內容",
                    "suggestions": self._get_search_suggestions(query)
                }
            
            help_data = {
                "type": "search_results",
                "query": query,
                "results": results,
                "navigation": self.navigation_builder.build_search_navigation(user_id)
            }
            
            # 記錄搜尋
            self._record_help_usage(user_id, f"search_{query}")
            
            return help_data
            
        except Exception as e:
            logger.error(f"搜尋幫助時出錯: {e}")
            return self._get_fallback_help()
    
    def get_quick_help(self, user_id: str, command: str) -> str:
        """獲取命令的快速幫助"""
        try:
            quick_helps = {
                "預約叫車": "使用自然語言描述您的預約需求，例如：明天下午3點從台北車站到桃園機場",
                "東洋班次": "查詢東洋/臨時班次，點擊日期按鈕選擇查詢日期",
                "診所班次": "查詢診所班次，點擊日期按鈕選擇查詢日期", 
                "班次詳情": "格式：班次詳情 [ID]，例如：班次詳情 2320",
                "固定班表": "格式：固定班表 [客戶簡稱]，例如：固定班表 新建路",
                "查已完成": "格式：查已完成 [日期] [類別]，例如：查已完成 昨天 診所",
                "記錄車資": "格式：記錄車資 [ID] [錶價] [加成]，例如：記錄車資 2320 500 50",
                "生成周報表": "格式：生成周報表 [類別]，例如：生成周報表 診所",
                "生成月報表": "格式：生成月報表 [類別]，例如：生成月報表 全部"
            }
            
            help_text = quick_helps.get(command)
            if help_text:
                self._record_help_usage(user_id, f"quick_{command}")
                return help_text
            else:
                return f"找不到命令「{command}」的幫助。使用「幫助」查看完整命令列表。"
                
        except Exception as e:
            logger.error(f"獲取快速幫助時出錯: {e}")
            return "獲取幫助時出錯，請稍後再試。"
    
    def _build_user_context(self, user_id: str) -> Dict[str, Any]:
        """構建用戶上下文"""
        context = {
            "user_id": user_id,
            "timestamp": datetime.now(),
            "is_new_user": self._is_new_user(user_id),
            "recent_errors": self._get_recent_errors(user_id),
            "uses_advanced_features": self._uses_advanced_features(user_id),
            "needs_concept_understanding": self._needs_concept_understanding(user_id),
            "current_mode": self._get_current_mode(user_id),
            "help_usage_pattern": self._get_help_usage_pattern(user_id)
        }
        
        return context
    
    def _get_context_sensitive_help(self, user_id: str, user_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """獲取上下文感知幫助"""
        # 檢查用戶是否處於特殊模式
        current_mode = user_context.get("current_mode")
        
        if current_mode == "leave_mode":
            return self._build_leave_mode_help(user_id)
        elif current_mode == "booking_mode":
            return self._build_booking_mode_help(user_id)
        elif user_context.get("recent_errors"):
            return self._build_error_recovery_help(user_id, user_context["recent_errors"])
        
        return None
    
    def _build_main_help_interface(self, user_id: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """構建主幫助界面"""
        # 獲取個性化建議
        personalized = self.config.get_help_by_user_state(user_context)
        
        # 構建主界面
        help_data = {
            "type": "main_help",
            "title": "🔰 派班系統幫助中心",
            "version": self.config.version,
            "user_suggestions": personalized["personalized_suggestions"],
            "categories": self._build_category_overview(personalized["relevant_categories"]),
            "quick_actions": self._build_quick_actions(user_context),
            "navigation": self.navigation_builder.build_main_navigation(user_id),
            "footer": {
                "last_updated": self.config.last_updated.strftime("%Y-%m-%d"),
                "feedback": "如有問題請聯絡系統管理員"
            }
        }
        
        return help_data
    
    def _build_category_overview(self, relevant_categories: List[str]) -> List[Dict[str, Any]]:
        """構建分類概覽"""
        categories = []
        all_categories = self.config.help_categories
        
        # 先添加相關分類
        for cat_id in relevant_categories:
            if cat_id in all_categories:
                cat = all_categories[cat_id]
                categories.append({
                    "id": cat_id,
                    "title": cat["title"],
                    "icon": cat["icon"],
                    "description": cat["description"],
                    "priority": cat["priority"],
                    "is_recommended": True
                })
        
        # 再添加其他分類
        for cat_id, cat in all_categories.items():
            if cat_id not in relevant_categories:
                categories.append({
                    "id": cat_id,
                    "title": cat["title"],
                    "icon": cat["icon"],
                    "description": cat["description"],
                    "priority": cat["priority"],
                    "is_recommended": False
                })
        
        # 按優先級排序
        categories.sort(key=lambda x: (not x["is_recommended"], x["priority"]))
        
        return categories
    
    def _build_quick_actions(self, user_context: Dict[str, Any]) -> List[Dict[str, str]]:
        """構建快速操作"""
        actions = [
            {"id": "voice_booking", "label": "🎤 語音預約", "action": "預約叫車"},
            {"id": "today_schedule", "label": "📅 今日班次", "action": "東洋班次"},
            {"id": "search_help", "label": "🔍 搜尋幫助", "action": "search"},
        ]
        
        # 根據用戶狀態添加個性化操作
        if user_context.get("is_new_user"):
            actions.insert(0, {"id": "quick_start", "label": "🚀 快速入門", "action": "help_category_quick_start"})
        
        if user_context.get("recent_errors"):
            actions.append({"id": "troubleshooting", "label": "🔧 故障排除", "action": "help_category_troubleshooting"})
        
        return actions[:4]  # 限制4個快速操作
    
    def _search_help_content(self, query: str) -> List[Dict[str, Any]]:
        """搜尋幫助內容"""
        results = []
        query_lower = query.lower()
        
        # 搜尋所有分類和項目
        for cat_id, category in self.config.help_categories.items():
            # 搜尋分類標題和描述
            if (query_lower in category["title"].lower() or 
                query_lower in category["description"].lower()):
                results.append({
                    "type": "category",
                    "id": cat_id,
                    "title": category["title"],
                    "description": category["description"],
                    "relevance": self._calculate_relevance(query_lower, category["title"] + " " + category["description"])
                })
            
            # 搜尋項目
            for item in category["items"]:
                item_text = f"{item['title']} {item['description']}"
                if query_lower in item_text.lower():
                    results.append({
                        "type": "item", 
                        "category_id": cat_id,
                        "id": item["id"],
                        "title": item["title"],
                        "description": item["description"],
                        "relevance": self._calculate_relevance(query_lower, item_text)
                    })
        
        # 按相關性排序
        results.sort(key=lambda x: x["relevance"], reverse=True)
        
        return results[:10]  # 限制10個結果
    
    def _calculate_relevance(self, query: str, text: str) -> float:
        """計算搜尋相關性"""
        text_lower = text.lower()
        
        # 精確匹配得分最高
        if query == text_lower:
            return 1.0
        
        # 完整詞匹配
        if query in text_lower:
            return 0.8
        
        # 部分匹配
        words = query.split()
        matches = sum(1 for word in words if word in text_lower)
        
        return matches / len(words) * 0.6
    
    def _get_search_suggestions(self, query: str) -> List[str]:
        """獲取搜尋建議"""
        suggestions = [
            "預約", "班次", "請假", "報表", "司機", 
            "車資", "固定班表", "時間態", "AI", "故障排除"
        ]
        
        # 過濾掉與查詢相同的建議
        return [s for s in suggestions if s.lower() != query.lower()][:5]
    
    def _is_new_user(self, user_id: str) -> bool:
        """檢查是否為新用戶"""
        # 檢查用戶幫助使用歷史
        return user_id not in self._user_help_history
    
    def _get_recent_errors(self, user_id: str) -> List[str]:
        """獲取用戶最近的錯誤"""
        # 這裡應該與錯誤追蹤系統整合
        return []
    
    def _uses_advanced_features(self, user_id: str) -> bool:
        """檢查用戶是否使用進階功能"""
        # 檢查用戶的功能使用模式
        return False
    
    def _needs_concept_understanding(self, user_id: str) -> bool:
        """檢查用戶是否需要概念理解幫助"""
        # 基於用戶行為分析
        return True
    
    def _get_current_mode(self, user_id: str) -> Optional[str]:
        """獲取用戶當前模式"""
        # 檢查會話上下文
        if conversation_manager.is_in_leave_mode(user_id):
            return "leave_mode"
        # 可以添加更多模式檢查
        return None
    
    def _get_help_usage_pattern(self, user_id: str) -> Dict[str, Any]:
        """獲取用戶幫助使用模式"""
        history = self._user_help_history.get(user_id, [])
        return {
            "total_usage": len(history),
            "recent_usage": len([h for h in history if h["timestamp"] > datetime.now() - timedelta(days=7)]),
            "favorite_categories": self._get_favorite_categories(history)
        }
    
    def _get_favorite_categories(self, history: List[Dict[str, Any]]) -> List[str]:
        """獲取最常使用的分類"""
        category_counts = {}
        for entry in history:
            if entry["type"].startswith("category_"):
                cat = entry["type"].replace("category_", "")
                category_counts[cat] = category_counts.get(cat, 0) + 1
        
        return sorted(category_counts.keys(), key=lambda x: category_counts[x], reverse=True)[:3]
    
    def _record_help_usage(self, user_id: str, help_type: str):
        """記錄幫助使用情況"""
        if user_id not in self._user_help_history:
            self._user_help_history[user_id] = []
        
        self._user_help_history[user_id].append({
            "type": help_type,
            "timestamp": datetime.now()
        })
        
        # 保持歷史記錄在合理範圍內
        if len(self._user_help_history[user_id]) > 100:
            self._user_help_history[user_id] = self._user_help_history[user_id][-50:]
    
    def _build_leave_mode_help(self, user_id: str) -> Dict[str, Any]:
        """構建請假模式幫助"""
        return {
            "type": "context_help",
            "context": "leave_mode",
            "title": "🚫 請假模式",
            "message": "您正在設定請假。請輸入：【原因】【加成】",
            "examples": [
                "出國度假 -50",
                "住院治療 0", 
                "家庭事務 -20"
            ],
            "quick_actions": [
                {"label": "取消請假", "action": "取消操作"},
                {"label": "查看請假說明", "action": "help_item_advanced_features_fixed_schedules"}
            ]
        }
    
    def _build_booking_mode_help(self, user_id: str) -> Dict[str, Any]:
        """構建預約模式幫助"""
        return {
            "type": "context_help", 
            "context": "booking_mode",
            "title": "📅 預約模式",
            "message": "請用自然語言描述您的預約需求",
            "examples": [
                "明天下午2點從診所到火車站",
                "週五早上8點接送班次",
                "後天需要往返機場"
            ],
            "quick_actions": [
                {"label": "查看可用時段", "action": "東洋班次"},
                {"label": "取消預約", "action": "取消操作"}
            ]
        }
    
    def _build_error_recovery_help(self, user_id: str, errors: List[str]) -> Dict[str, Any]:
        """構建錯誤恢復幫助"""
        return {
            "type": "context_help",
            "context": "error_recovery", 
            "title": "⚠️ 錯誤恢復",
            "message": "偵測到最近有錯誤發生，以下是解決建議：",
            "suggestions": [
                "檢查輸入格式是否正確",
                "確認網路連線狀態",
                "嘗試重新執行命令",
                "查看故障排除指南"
            ],
            "quick_actions": [
                {"label": "故障排除", "action": "help_category_troubleshooting"},
                {"label": "重新開始", "action": "幫助"}
            ]
        }
    
    def _get_fallback_help(self) -> Dict[str, Any]:
        """獲取備用幫助"""
        return {
            "type": "fallback",
            "title": "幫助系統",
            "message": "系統繁忙，請稍後再試或使用以下快速命令：",
            "quick_commands": [
                "預約叫車 - 開始預約",
                "東洋班次 - 查看今日班次", 
                "幫助文字 - 查看文字版幫助"
            ]
        }