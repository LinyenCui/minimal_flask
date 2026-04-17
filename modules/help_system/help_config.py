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
            # 新增：帳務處理分類（僅作為幫助入口，按鈕直接觸發文字命令）
            "accounting": {
                "title": "💰 帳務處理",
                "icon": "💼",
                "description": "查餘額、記錄入金與週扣款",
                "priority": 2,
                "items": [
                    {
                        "id": "balance",
                        "title": "查看帳戶餘額",
                        "description": "點擊主項或輸入『帳務處理』",
                        "content_type": "feature_guide",
                        "features": {
                            "balance": "顯示目前帳戶餘額，附快速操作按鈕"
                        }
                    },
                    {
                        "id": "deposit",
                        "title": "記錄入金",
                        "description": "依序輸入日期、金額、銀行、末4碼",
                        "content_type": "interactive_guide",
                        "examples": ["➕ 記錄入金"]
                    },
                    {
                        "id": "weekly_charge",
                        "title": "記錄上週扣款",
                        "description": "輸入金額，系統自動設為最近週日23:59",
                        "content_type": "interactive_guide",
                        "examples": ["💵 記錄上週扣款"]
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
                        "id": "group_location_arrival",
                        "title": "📍 群組地點與到院提醒",
                        "description": "以群組固定地點計算距離與ETA（支援括號座標）",
                        "content_type": "feature_guide",
                        "features": {
                            "set_place": "設定地點 名稱 緯度 經度 或 名稱 (緯度, 經度)",
                            "set_name": "設定地點名稱 名稱",
                            "set_template": "設定到院訊息 模板（支援 {name}/{distance_km}/{eta_min}/{provider}/{speed}）",
                            "view_meta": "查看到院設定（僅顯示名稱與模板長度）",
                            "reset_template": "恢復預設到院訊息"
                        },
                        "detailed_description": """群組地點與到院提醒功能讓您可以設定群組的固定地點，當群組成員傳送位置訊息時，系統會自動計算距離與預估到達時間。

📋 主要功能：
• 設定群組固定地點（支援多種座標格式）
• 自訂到院提醒訊息模板
• 自動計算距離與ETA
• 支援Google地圖路線計算（需設定API金鑰）

💡 使用場景：
• 診所接送：設定診所位置，司機傳位置時自動提醒
• 固定接送點：設定常用接送地點，方便計算距離
• 到院提醒：自訂提醒訊息，包含距離、時間等資訊

⚠️ 注意事項：
• 座標格式支援：22.9983,120.2002 或 (22.9983, 120.2002)
• 模板變數：{name}、{distance_km}、{eta_min}、{provider}、{speed}
• 需要設定GOOGLE_MAPS_API_KEY才能使用Google路線計算"""
                    },
                    {
                        "id": "batch_allowance",
                        "title": "💰 批量加成",
                        "description": "問答式批量加成功能（春節/颱風假期等特殊情況）",
                        "content_type": "feature_guide",
                        "features": {
                            "batch_allowance": "批量加成 - 為多個班次一次性設定加成金額",
                            "interactive_mode": "問答式互動，逐步確認日期範圍和金額",
                            "special_occasions": "適用於春節、颱風假等特殊情況"
                        },
                        "detailed_description": """批量加成功能讓您可以為多個班次一次性設定加成金額，特別適用於特殊節日或情況。

📋 使用流程：
1. 輸入「批量加成」啟動功能
2. 系統會詢問日期範圍（例如：1/20-1/29）
3. 輸入加成金額（例如：100 或 -50）
4. 輸入原因（例如：春節加成）
5. 系統顯示符合條件的班次數量
6. 確認後批量更新

💡 適用場景：
• 春節期間：為所有班次統一加成
• 颱風假：為受影響班次設定補償
• 特殊活動：為特定日期範圍的班次加成

⚠️ 注意事項：
• 只會影響符合日期範圍的班次
• 可以設定正數（加成）或負數（減成）
• 建議先查看受影響的班次數量再確認"""
                    },
                    {
                        "id": "cleanup_trips",
                        "title": "🗑️ 清理Trips資料",
                        "description": "清理trips表中的過去資料，保持資料庫整潔",
                        "content_type": "feature_guide",
                        "features": {
                            "cleanup_completed": "清理trips 已完成 - 清理所有已完成狀態的班次",
                            "cleanup_past": "清理trips 過去 - 清理所有過去日期的班次",
                            "cleanup_all": "清理trips 全部 - 清理所有過去日期的班次"
                        },
                        "detailed_description": """清理功能專門用於清理trips表中的過去資料，幫助保持資料庫的整潔和效能。

📋 可用選項：
• 清理trips 已完成：清理所有狀態為「已完成」的班次
• 清理trips 過去：清理所有過去日期的班次（不管狀態）
• 清理trips 全部：與「過去」功能相同

🔒 安全機制：
• 不影響今天：今天的班次不會被清理
• 不影響未來：未來的班次完全不會被清理
• 只清理過去：所有清理選項都只作用於過去的資料

💡 使用建議：
• 每週清理：使用「清理trips 已完成」清理已執行完成的班次
• 月度清理：使用「清理trips 過去」清理所有過去日期的班次
• 定期維護：保持資料庫整潔，提升查詢效能

⚠️ 注意事項：
• 清理操作不可恢復，請謹慎使用
• 建議先備份資料再進行大規模清理
• 清理已完成：只清理已完成狀態，保留其他狀態
• 清理過去/全部：清理所有過去日期，但保留當前和未來

🔧 清理後的序號處理：
清理資料後，序號不會自動重置。如果需要重置序號，請使用「序號管理」功能。"""
                    },
                    {
                        "id": "sequence_management",
                        "title": "🔢 序號管理與重置",
                        "description": "管理資料庫序號，重置和修復序列值",
                        "content_type": "feature_guide",
                        "features": {
                            "line_bot_fix": "LINE Bot修復：輸入「/fix-sequence」或「修復序號」檢查並修復序列",
                            "reset_render": "重置Render序號：python reset_render_sequences.py（命令行工具）",
                            "fix_after_import": "匯入後修復：python scripts/fix_sequence_after_import.py（命令行工具）"
                        },
                        "detailed_description": """序號管理功能用於處理資料庫序列（Sequence）的同步和重置問題。

📋 使用場景：
• 清理資料後需要重置序號
• 資料搬移後序列不同步
• 主鍵衝突問題修復
• 序號過大需要回收

🛠️ 可用工具：

1️⃣ LINE Bot修復（最方便）
• 命令：/fix-sequence 或 修復序號
• 功能：自動檢查所有序列狀態，發現問題時提供修復選項
• 適用：日常維護和快速檢查
• 支援：trips 和 completed_trips 表

2️⃣ 重置Render序號（命令行）
• 檔案：reset_render_sequences.py
• 命令：python reset_render_sequences.py
• 功能：重置Render資料庫的序號為1（需確認）
• 適用：清理資料後需要從頭開始編號
• 注意：會重置 trips_trip_id_seq 和 completed_trips_id_seq

3️⃣ 匯入後修復（命令行）
• 檔案：scripts/fix_sequence_after_import.py
• 命令：python scripts/fix_sequence_after_import.py
• 快速模式：python scripts/fix_sequence_after_import.py --quick
• 功能：修復資料搬移後的序列同步問題
• 適用：TRUNCATE + 匯入資料後使用
• 選項：可選擇只修復 completed_trips 或檢查所有序列

💡 使用建議：
• 日常檢查：使用 LINE Bot 的 /fix-sequence 命令
• 清理後重置：使用 reset_render_sequences.py
• 資料搬移後：使用 fix_sequence_after_import.py --quick

⚠️ 重要提醒：
• 重置序號前請確認資料表狀態
• 序號重置後不可恢復，請謹慎操作
• 資料搬移後務必修復序列，避免主鍵衝突
• Render端序號建議每週或每月重置一次（視使用頻率）"""
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