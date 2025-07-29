"""
動態幫助系統配置文件
集中管理所有幫助內容和結構
"""

from typing import Dict, List, Any
from datetime import datetime

class HelpSystemConfig:
    """幫助系統配置管理"""
    
    def __init__(self):
        self.version = "2.0"
        self.last_updated = datetime.now()
        
    @property
    def help_categories(self) -> Dict[str, Dict[str, Any]]:
        """幫助分類結構"""
        return {
            "quick_start": {
                "title": "🚀 快速入門",
                "icon": "🚀",
                "description": "新手必看，5分鐘掌握基本操作",
                "priority": 1,
                "items": [
                    {
                        "id": "basic_commands",
                        "title": "基本命令",
                        "description": "最常用的10個命令",
                        "content_type": "command_list",
                        "commands": [
                            "幫助", "預約叫車", "東洋班次", "診所班次", 
                            "班次詳情", "查已完成", "固定班表"
                        ]
                    },
                    {
                        "id": "voice_booking",
                        "title": "語音預約",
                        "description": "用自然語言描述需求",
                        "content_type": "interactive_guide",
                        "examples": [
                            "明天下午3點從台北車站到桃園機場",
                            "後天早上看診班次安排",
                            "週五需要請假"
                        ]
                    }
                ]
            },
            
            "time_states": {
                "title": "⏰ 三時間態系統",
                "icon": "⏰", 
                "description": "理解未來、現在、過去的派班邏輯",
                "priority": 2,
                "items": [
                    {
                        "id": "future_mode",
                        "title": "🔮 未來時間態",
                        "description": "規劃與預約功能",
                        "content_type": "concept_guide",
                        "concepts": {
                            "purpose": "處理尚未發生的班次預約和安排",
                            "key_features": ["預約叫車", "固定班次匯入", "長期請假設定"],
                            "workflow": "預約 → 確認 → 排程 → 轉入現在態"
                        }
                    },
                    {
                        "id": "present_mode", 
                        "title": "⚡ 現在時間態",
                        "description": "進行中班次管理",
                        "content_type": "concept_guide",
                        "concepts": {
                            "purpose": "管理正在進行或即將開始的班次",
                            "key_features": ["司機指派", "狀態更新", "即時調度"],
                            "workflow": "開始 → 進行中 → 完成 → 轉入過去態"
                        }
                    },
                    {
                        "id": "past_mode",
                        "title": "📚 過去時間態", 
                        "description": "歷史記錄與報表",
                        "content_type": "concept_guide",
                        "concepts": {
                            "purpose": "記錄已完成班次的詳細資訊",
                            "key_features": ["車資記錄", "類別分類", "報表生成"],
                            "workflow": "完成 → 記錄 → 統計 → 歸檔"
                        }
                    }
                ]
            },
            
            "advanced_features": {
                "title": "🎯 進階功能",
                "icon": "🎯",
                "description": "提升效率的專業工具", 
                "priority": 3,
                "items": [
                    {
                        "id": "ai_assistant",
                        "title": "🤖 智能助手",
                        "description": "AI驅動的自然語言處理",
                        "content_type": "feature_guide",
                        "features": {
                            "voice_booking": "語音預約叫車",
                            "smart_search": "智能班次搜尋",
                            "context_aware": "上下文感知對話",
                            "auto_completion": "自動補全指令"
                        }
                    },
                    {
                        "id": "fixed_schedules",
                        "title": "📋 固定班次系統",
                        "description": "長期班次管理與請假",
                        "content_type": "feature_guide", 
                        "features": {
                            "long_term_leave": "長期請假設定",
                            "bulk_import": "批量匯入班次",
                            "schedule_recovery": "班次恢復機制",
                            "cross_time_management": "跨時間態管理"
                        }
                    },
                    {
                        "id": "reporting_system",
                        "title": "📊 報表系統",
                        "description": "數據分析與業務洞察",
                        "content_type": "feature_guide",
                        "features": {
                            "weekly_reports": "週報表生成",
                            "monthly_analysis": "月度分析",
                            "custom_filters": "自訂篩選條件",
                            "export_formats": "多格式匯出"
                        }
                    }
                ]
            },
            
            "troubleshooting": {
                "title": "🔧 故障排除",
                "icon": "🔧",
                "description": "常見問題快速解決",
                "priority": 4,
                "items": [
                    {
                        "id": "common_errors",
                        "title": "常見錯誤",
                        "description": "最常遇到的問題及解決方案",
                        "content_type": "troubleshooting_guide",
                        "issues": [
                            {
                                "problem": "找不到班次",
                                "symptoms": ["查詢結果為空", "顯示「找不到相關班次」"],
                                "solutions": [
                                    "檢查日期格式是否正確",
                                    "確認客戶簡稱拼寫",
                                    "嘗試使用完整地址"
                                ]
                            },
                            {
                                "problem": "請假失敗",
                                "symptoms": ["顯示「正在處理...」後無回應", "請假狀態未更新"],
                                "solutions": [
                                    "重新點擊班次按鈕",
                                    "檢查網路連線",
                                    "聯絡系統管理員"
                                ]
                            }
                        ]
                    },
                    {
                        "id": "system_status",
                        "title": "系統狀態檢查",
                        "description": "診斷工具與健康檢查",
                        "content_type": "diagnostic_tools"
                    }
                ]
            }
        }
    
    @property
    def context_sensitive_helps(self) -> Dict[str, Dict[str, Any]]:
        """上下文感知幫助"""
        return {
            "in_leave_mode": {
                "title": "請假模式幫助",
                "content": "您正在設定請假。請輸入：【原因】【加成】\n例如：出國度假 -50",
                "quick_actions": ["取消請假", "查看班次詳情"]
            },
            "in_booking_mode": {
                "title": "預約模式幫助", 
                "content": "請描述您的預約需求，例如：\n明天下午2點從診所到火車站",
                "quick_actions": ["查看可用時段", "取消預約"]
            },
            "after_error": {
                "title": "錯誤後幫助",
                "content": "遇到問題？嘗試以下解決方案：",
                "quick_actions": ["重新執行", "查看故障排除", "聯絡支援"]
            }
        }
    
    @property
    def smart_suggestions(self) -> Dict[str, List[str]]:
        """智能建議"""
        return {
            "morning": [
                "查看今日班次安排", 
                "檢查司機指派狀態",
                "匯入固定班次"
            ],
            "afternoon": [
                "更新班次狀態",
                "記錄車資", 
                "處理臨時預約"
            ],
            "evening": [
                "完成今日班次",
                "生成日報表",
                "準備明日班次"
            ],
            "new_user": [
                "觀看快速入門教學",
                "了解三時間態系統",
                "嘗試語音預約"
            ],
            "experienced_user": [
                "使用進階篩選功能",
                "設定自動化規則",
                "查看業務分析報表"
            ]
        }
    
    def get_help_by_user_state(self, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """根據用戶狀態提供相關幫助"""
        suggestions = []
        
        # 根據時間提供建議
        current_hour = datetime.now().hour
        if 6 <= current_hour < 12:
            suggestions.extend(self.smart_suggestions["morning"])
        elif 12 <= current_hour < 18:
            suggestions.extend(self.smart_suggestions["afternoon"])
        else:
            suggestions.extend(self.smart_suggestions["evening"])
        
        # 根據用戶經驗提供建議
        if user_context.get("is_new_user", False):
            suggestions.extend(self.smart_suggestions["new_user"])
        else:
            suggestions.extend(self.smart_suggestions["experienced_user"])
        
        return {
            "personalized_suggestions": suggestions[:5],  # 限制5個建議
            "relevant_categories": self._get_relevant_categories(user_context)
        }
    
    def _get_relevant_categories(self, user_context: Dict[str, Any]) -> List[str]:
        """獲取相關的幫助分類"""
        relevant = ["quick_start"]  # 總是包含快速入門
        
        if user_context.get("recent_errors"):
            relevant.append("troubleshooting")
        
        if user_context.get("uses_advanced_features"):
            relevant.append("advanced_features")
        
        if user_context.get("needs_concept_understanding"):
            relevant.append("time_states")
        
        return relevant