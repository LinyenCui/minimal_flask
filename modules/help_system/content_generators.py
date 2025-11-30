"""
幫助內容生成器
根據配置動態生成不同類型的幫助內容
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class HelpContentGenerator:
    """幫助內容生成器"""
    
    def __init__(self):
        self.content_templates = self._initialize_templates()
    
    def generate_category_content(self, category: Dict[str, Any]) -> Dict[str, Any]:
        """生成分類幫助內容"""
        try:
            content = {
                "type": "category_help",
                "title": category["title"],
                "icon": category["icon"],
                "description": category["description"],
                "items": []
            }
            
            # 生成項目概覽
            for item in category["items"]:
                item_overview = {
                    "id": item["id"],
                    "title": item["title"],
                    "description": item["description"],
                    "content_type": item["content_type"]
                }
                content["items"].append(item_overview)
            
            return content
            
        except Exception as e:
            logger.error(f"生成分類內容時出錯: {e}")
            return self._get_error_content("分類內容生成失敗")
    
    def generate_item_content(self, item: Dict[str, Any], category_id: str) -> Dict[str, Any]:
        """生成項目詳細內容"""
        try:
            content_type = item["content_type"]
            
            if content_type == "command_list":
                return self._generate_command_list_content(item, category_id)
            elif content_type == "interactive_guide":
                return self._generate_interactive_guide_content(item, category_id)
            elif content_type == "concept_guide":
                return self._generate_concept_guide_content(item, category_id)
            elif content_type == "feature_guide":
                return self._generate_feature_guide_content(item, category_id)
            elif content_type == "troubleshooting_guide":
                return self._generate_troubleshooting_guide_content(item, category_id)
            elif content_type == "diagnostic_tools":
                return self._generate_diagnostic_tools_content(item, category_id)
            else:
                return self._generate_generic_content(item, category_id)
                
        except Exception as e:
            logger.error(f"生成項目內容時出錯: {e}")
            return self._get_error_content("項目內容生成失敗")
    
    def _generate_command_list_content(self, item: Dict[str, Any], category_id: str) -> Dict[str, Any]:
        """生成命令列表內容"""
        commands = item.get("commands", [])
        
        content = {
            "type": "command_list",
            "title": item["title"],
            "description": item["description"],
            "commands": []
        }
        
        # 為每個命令生成詳細說明
        command_details = {
            "幫助": {
                "description": "顯示主幫助菜單",
                "usage": "幫助",
                "examples": ["幫助"]
            },
            "預約叫車": {
                "description": "使用自然語言預約班次",
                "usage": "預約叫車 [描述]",
                "examples": ["預約叫車", "明天下午3點從台北車站到桃園機場"]
            },
            "東洋班次": {
                "description": "查詢東洋/臨時班次",
                "usage": "東洋班次 [日期]",
                "examples": ["東洋班次", "東洋班次 明天", "東洋班次 2025-07-28"]
            },
            "診所班次": {
                "description": "查詢診所班次",
                "usage": "診所班次 [日期]",
                "examples": ["診所班次", "診所班次 今天", "診所班次 昨天"]
            },
            "班次詳情": {
                "description": "查看班次詳細信息",
                "usage": "班次詳情 [ID]",
                "examples": ["班次詳情 2320", "班次詳情 1234"]
            },
            "查已完成": {
                "description": "查詢已完成的班次",
                "usage": "查已完成 [日期] [類別]",
                "examples": ["查已完成", "查已完成 昨天", "查已完成 2025-07-25 診所"]
            },
            "固定班表": {
                "description": "查詢固定班次並管理",
                "usage": "固定班表 [客戶簡稱]",
                "examples": ["固定班表 新建路", "固定班表 診所"]
            }
        }
        
        for cmd in commands:
            if cmd in command_details:
                content["commands"].append({
                    "command": cmd,
                    **command_details[cmd]
                })
            else:
                content["commands"].append({
                    "command": cmd,
                    "description": f"{cmd}命令",
                    "usage": cmd,
                    "examples": [cmd]
                })
        
        return content
    
    def _generate_interactive_guide_content(self, item: Dict[str, Any], category_id: str) -> Dict[str, Any]:
        """生成互動式指南內容"""
        return {
            "type": "interactive_guide",
            "title": item["title"],
            "description": item["description"],
            "introduction": "以下是一些使用範例，您可以直接點擊試用：",
            "examples": [
                {
                    "text": example,
                    "action": f"預約叫車 {example}",
                    "explanation": f"這會啟動預約流程：{example}"
                }
                for example in item.get("examples", [])
            ],
            "tips": [
                "💡 使用自然語言描述，系統會自動理解",
                "🕐 包含時間信息會提高預約準確度",
                "📍 提供具體地點名稱或地址",
                "🔄 可以隨時修改或取消預約"
            ],
            "next_steps": [
                {"label": "開始預約", "action": "預約叫車"},
                {"label": "查看班次", "action": "東洋班次"},
                {"label": "了解更多", "action": "help_category_advanced_features"}
            ]
        }
    
    def _generate_concept_guide_content(self, item: Dict[str, Any], category_id: str) -> Dict[str, Any]:
        """生成概念指南內容"""
        concepts = item.get("concepts", {})
        
        return {
            "type": "concept_guide",
            "title": item["title"],
            "description": item["description"],
            "concept": {
                "purpose": concepts.get("purpose", ""),
                "key_features": concepts.get("key_features", []),
                "workflow": concepts.get("workflow", ""),
                "visual_diagram": self._generate_workflow_diagram(item["id"])
            },
            "practical_examples": self._get_practical_examples(item["id"]),
            "related_commands": self._get_related_commands(item["id"]),
            "best_practices": self._get_best_practices(item["id"])
        }
    
    def _generate_feature_guide_content(self, item: Dict[str, Any], category_id: str) -> Dict[str, Any]:
        """生成功能指南內容"""
        features = item.get("features", {})
        
        content = {
            "type": "feature_guide",
            "title": item["title"],
            "description": item["description"],
            "features": [
                {
                    "name": name,
                    "description": desc,
                    "how_to_use": self._get_feature_usage(name),
                    "examples": self._get_feature_examples(name)
                }
                for name, desc in features.items()
            ],
            "getting_started": self._get_getting_started_guide(item["id"]),
            "advanced_usage": self._get_advanced_usage_guide(item["id"])
        }
        
        # 如果有詳細說明，添加到內容中
        if "detailed_description" in item:
            content["detailed_description"] = item["detailed_description"]
        
        return content
    
    def _generate_troubleshooting_guide_content(self, item: Dict[str, Any], category_id: str) -> Dict[str, Any]:
        """生成故障排除指南內容"""
        issues = item.get("issues", [])
        
        return {
            "type": "troubleshooting_guide",
            "title": item["title"],
            "description": item["description"],
            "common_issues": [
                {
                    "problem": issue["problem"],
                    "symptoms": issue["symptoms"],
                    "solutions": [
                        {
                            "step": i + 1,
                            "description": solution,
                            "action": self._get_solution_action(solution)
                        }
                        for i, solution in enumerate(issue["solutions"])
                    ],
                    "prevention": self._get_prevention_tips(issue["problem"])
                }
                for issue in issues
            ],
            "escalation": {
                "when_to_escalate": "如果以上解決方案都無效",
                "contact_info": "請聯絡系統管理員",
                "what_to_include": [
                    "詳細描述問題症狀",
                    "已嘗試的解決步驟", 
                    "錯誤訊息截圖",
                    "發生時間和頻率"
                ]
            }
        }
    
    def _generate_diagnostic_tools_content(self, item: Dict[str, Any], category_id: str) -> Dict[str, Any]:
        """生成診斷工具內容"""
        return {
            "type": "diagnostic_tools",
            "title": item["title"],
            "description": item["description"],
            "tools": [
                {
                    "name": "系統狀態檢查",
                    "description": "檢查系統各組件運行狀態",
                    "action": "system_health_check",
                    "expected_result": "顯示各模組健康狀態"
                },
                {
                    "name": "連線測試",
                    "description": "測試與Line Bot平台的連線",
                    "action": "connection_test",
                    "expected_result": "確認API連線正常"
                },
                {
                    "name": "資料庫檢查",
                    "description": "驗證資料庫連線和數據完整性",
                    "action": "database_check",
                    "expected_result": "確認資料庫狀態正常"
                }
            ],
            "automated_diagnostics": {
                "description": "一鍵診斷所有系統組件",
                "action": "run_full_diagnostics",
                "warning": "診斷過程可能需要幾分鐘時間"
            }
        }
    
    def _generate_generic_content(self, item: Dict[str, Any], category_id: str) -> Dict[str, Any]:
        """生成通用內容"""
        return {
            "type": "generic_content",
            "title": item["title"],
            "description": item["description"],
            "content": "詳細內容開發中...",
            "placeholder": True
        }
    
    def _generate_workflow_diagram(self, item_id: str) -> Dict[str, Any]:
        """生成工作流程圖"""
        diagrams = {
            "future_mode": {
                "steps": [
                    {"id": 1, "label": "預約需求", "description": "用戶提出預約需求"},
                    {"id": 2, "label": "AI解析", "description": "智能助手解析需求"},
                    {"id": 3, "label": "時間規劃", "description": "安排到未來時間點"},
                    {"id": 4, "label": "確認預約", "description": "確認預約詳情"},
                    {"id": 5, "label": "等待執行", "description": "等待時間到達"}
                ],
                "connections": ["1→2", "2→3", "3→4", "4→5"]
            },
            "present_mode": {
                "steps": [
                    {"id": 1, "label": "班次開始", "description": "從未來態轉入"},
                    {"id": 2, "label": "司機指派", "description": "分配執行司機"},
                    {"id": 3, "label": "執行中", "description": "班次進行中"},
                    {"id": 4, "label": "狀態更新", "description": "即時狀態同步"},
                    {"id": 5, "label": "完成", "description": "轉入過去態"}
                ],
                "connections": ["1→2", "2→3", "3→4", "4→5"]
            },
            "past_mode": {
                "steps": [
                    {"id": 1, "label": "班次完成", "description": "從現在態轉入"},
                    {"id": 2, "label": "記錄車資", "description": "登記費用信息"},
                    {"id": 3, "label": "分類歸檔", "description": "按類別整理"},
                    {"id": 4, "label": "數據分析", "description": "統計分析處理"},
                    {"id": 5, "label": "報表生成", "description": "產生各類報表"}
                ],
                "connections": ["1→2", "2→3", "3→4", "4→5"]
            }
        }
        
        return diagrams.get(item_id, {"steps": [], "connections": []})
    
    def _get_practical_examples(self, item_id: str) -> List[Dict[str, str]]:
        """獲取實用範例"""
        examples = {
            "future_mode": [
                {
                    "scenario": "定期診所接送",
                    "command": "固定班表 診所",
                    "explanation": "查看和管理定期的診所接送班次"
                },
                {
                    "scenario": "臨時預約",
                    "command": "預約叫車 明天下午3點從台北車站到桃園機場",
                    "explanation": "使用自然語言描述預約需求"
                }
            ],
            "present_mode": [
                {
                    "scenario": "查看今日班次",
                    "command": "東洋班次",
                    "explanation": "查看今天所有進行中的班次"
                },
                {
                    "scenario": "指派司機",
                    "command": "指派司機 2320",
                    "explanation": "為班次ID 2320指派執行司機"
                }
            ],
            "past_mode": [
                {
                    "scenario": "記錄車資",
                    "command": "記錄車資 2320 500 50",
                    "explanation": "為班次2320記錄錶價500、加成50"
                },
                {
                    "scenario": "生成報表",
                    "command": "生成周報表 診所",
                    "explanation": "生成診所類別的週報表"
                }
            ]
        }
        
        return examples.get(item_id, [])
    
    def _get_related_commands(self, item_id: str) -> List[str]:
        """獲取相關命令"""
        related = {
            "future_mode": ["預約叫車", "固定班表", "匯入固定班次"],
            "present_mode": ["東洋班次", "診所班次", "班次詳情", "指派司機"],
            "past_mode": ["查已完成", "記錄車資", "生成周報表", "生成月報表"]
        }
        
        return related.get(item_id, [])
    
    def _get_best_practices(self, item_id: str) -> List[str]:
        """獲取最佳實踐"""
        practices = {
            "future_mode": [
                "提前規劃長期班次，使用固定班表功能",
                "預約時提供詳細的時間和地點信息",
                "定期檢查未來班次安排，確保無衝突"
            ],
            "present_mode": [
                "及時更新班次狀態，確保資訊同步",
                "優先處理進行中的班次",
                "保持與司機的即時溝通"
            ],
            "past_mode": [
                "完成班次後立即記錄車資",
                "定期生成報表進行業務分析",
                "保持歷史資料的準確性和完整性"
            ]
        }
        
        return practices.get(item_id, [])
    
    def _get_feature_usage(self, feature_name: str) -> str:
        """獲取功能使用方法"""
        usage_guide = {
            "voice_booking": "直接說出或輸入您的預約需求，系統會自動解析",
            "smart_search": "輸入關鍵字或自然語言描述來搜尋班次",
            "context_aware": "系統會記住對話上下文，提供相關建議",
            "auto_completion": "開始輸入命令，系統會提供補全選項",
            "long_term_leave": "點擊固定班次按鈕，然後輸入請假原因和加成",
            "bulk_import": "使用「匯入固定班次」命令批量導入班次",
            "schedule_recovery": "使用「固定班次恢復」命令恢復請假班次",
            "cross_time_management": "系統自動處理跨時間態的班次轉換",
            # === 群組地點與到院提醒：簡明使用方法（給一般用戶） ===
            "set_place": "設定地點 名稱 緯度 經度\n例：設定地點 診所 22.9983,120.2002 或 設定地點 東洋 (22.9983, 120.2002)",
            "set_name": "設定地點名稱 名稱\n例：設定地點名稱 診所",
            "set_template": "設定到院訊息 模板\n可用變數：{name}/{distance_km}/{eta_min}/{provider}/{speed}",
            "view_meta": "查看到院設定（顯示名稱與是否有自訂模板）",
            "reset_template": "恢復預設到院訊息（清除自訂模板）",
            # === 批量加成功能 ===
            "batch_allowance": "輸入「批量加成」，系統會引導您逐步設定日期範圍、金額和原因",
            "interactive_mode": "問答式互動，系統會詢問日期範圍、加成金額和原因",
            "special_occasions": "適用於春節、颱風假等需要為多個班次統一加成的特殊情況",
            # === 清理Trips功能 ===
            "cleanup_completed": "清理trips 已完成 - 清理所有已完成狀態的班次",
            "cleanup_past": "清理trips 過去 - 清理所有過去日期的班次（不管狀態）",
            "cleanup_all": "清理trips 全部 - 與「過去」功能相同",
            # === 序號管理功能 ===
            "line_bot_fix": "在LINE Bot中輸入「/fix-sequence」或「修復序號」，系統會自動檢查並修復序列問題",
            "reset_render": "執行 python reset_render_sequences.py，會重置Render資料庫的序號為1（需確認）",
            "fix_after_import": "執行 python scripts/fix_sequence_after_import.py，修復資料搬移後的序列同步問題",
            "web_admin": "訪問網頁管理介面 /admin/database-tools，進行視覺化的序列檢查和修復"
        }
        
        return usage_guide.get(feature_name, "使用方法待補充")
    
    def _get_feature_examples(self, feature_name: str) -> List[str]:
        """獲取功能範例"""
        examples = {
            "voice_booking": [
                "明天早上8點從家裡到醫院",
                "週五下午需要接送服務",
                "下週二往返機場班次"
            ],
            "smart_search": [
                "搜尋：台北車站",
                "搜尋：昨天的診所班次",
                "搜尋：王先生的預約"
            ],
            "long_term_leave": [
                "出國度假 -50",
                "住院治療 0",
                "家庭事務 -20"
            ],
            # === 群組地點與到院提醒：範例 ===
            "set_place": [
                "設定地點 診所 22.9983,120.2002",
                "設定地點 東洋 (22.9983, 120.2002)"
            ],
            "set_name": [
                "設定地點名稱 診所"
            ],
            "set_template": [
                "設定到院訊息 🧑‍🦽 請準備輪椅\n距離：{distance_km} 公里，約 {eta_min} 分鐘（{provider}）"
            ],
            "view_meta": [
                "查看到院設定"
            ],
            "reset_template": [
                "恢復預設到院訊息"
            ],
            # === 批量加成功能：範例 ===
            "batch_allowance": [
                "批量加成（然後依序輸入：1/20-1/29、100、春節加成）"
            ],
            "interactive_mode": [
                "輸入「批量加成」後，系統會逐步詢問日期範圍、金額和原因"
            ],
            "special_occasions": [
                "春節期間：批量加成 → 1/20-1/29 → 100 → 春節加成",
                "颱風假：批量加成 → 7/28-7/29 → 50 → 颱風補償"
            ],
            # === 清理Trips功能：範例 ===
            "cleanup_completed": [
                "清理trips 已完成"
            ],
            "cleanup_past": [
                "清理trips 過去"
            ],
            "cleanup_all": [
                "清理trips 全部"
            ],
            # === 序號管理功能：範例 ===
            "line_bot_fix": [
                "/fix-sequence",
                "修復序號"
            ],
            "reset_render": [
                "python reset_render_sequences.py"
            ],
            "fix_after_import": [
                "python scripts/fix_sequence_after_import.py",
                "python scripts/fix_sequence_after_import.py --quick"
            ],
            "web_admin": [
                "訪問 http://your-domain/admin/database-tools"
            ]
        }
        
        return examples.get(feature_name, [])
    
    def _get_getting_started_guide(self, item_id: str) -> Dict[str, Any]:
        """獲取入門指南"""
        guides = {
            "ai_assistant": {
                "step1": "嘗試自然語言預約：預約叫車",
                "step2": "觀察AI如何理解您的需求",
                "step3": "根據建議完善預約信息"
            },
            "fixed_schedules": {
                "step1": "查看現有固定班次：固定班表 [客戶名]",
                "step2": "了解班次詳情和狀態",
                "step3": "嘗試設定請假或恢復班次"
            },
            "reporting_system": {
                "step1": "查看已完成班次：查已完成",
                "step2": "記錄車資信息：記錄車資 [ID] [金額]",
                "step3": "生成第一份報表：生成周報表"
            }
        }
        
        return guides.get(item_id, {})
    
    def _get_advanced_usage_guide(self, item_id: str) -> List[Dict[str, str]]:
        """獲取進階使用指南"""
        return [
            {
                "title": "批量操作",
                "description": "學習如何一次處理多個項目"
            },
            {
                "title": "自訂規則",
                "description": "設定個人化的自動化規則"
            },
            {
                "title": "數據整合",
                "description": "與其他系統進行數據交換"
            }
        ]
    
    def _get_solution_action(self, solution: str) -> Optional[str]:
        """獲取解決方案對應的操作"""
        action_mapping = {
            "檢查輸入格式是否正確": "show_format_guide",
            "確認客戶簡稱拼寫": "show_customer_list",
            "嘗試使用完整地址": "address_guide",
            "重新點擊班次按鈕": "refresh_schedule",
            "檢查網路連線": "connection_test",
            "聯絡系統管理員": "contact_admin"
        }
        
        return action_mapping.get(solution)
    
    def _get_prevention_tips(self, problem: str) -> List[str]:
        """獲取預防建議"""
        tips = {
            "找不到班次": [
                "保持客戶簡稱的一致性",
                "定期更新地址資料",
                "使用標準化的命令格式"
            ],
            "請假失敗": [
                "確保網路連線穩定",
                "避免同時進行多個操作",
                "定期更新應用程式"
            ]
        }
        
        return tips.get(problem, [])
    
    def _get_error_content(self, message: str) -> Dict[str, Any]:
        """獲取錯誤內容"""
        return {
            "type": "error",
            "title": "內容載入失敗",
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
    
    def _initialize_templates(self) -> Dict[str, str]:
        """初始化內容模板"""
        return {
            "command_help": "命令：{command}\n描述：{description}\n用法：{usage}\n範例：{examples}",
            "feature_help": "功能：{feature}\n說明：{description}\n使用方法：{usage}",
            "concept_help": "概念：{concept}\n用途：{purpose}\n關鍵特性：{features}"
        }