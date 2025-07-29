"""
幫助系統導航構建器
構建Flex Message和QuickReply導航界面
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class HelpNavigationBuilder:
    """幫助導航構建器"""
    
    def __init__(self):
        self.max_quick_reply_items = 13  # Line限制
        self.max_flex_actions = 12  # Flex Message限制
    
    def build_main_navigation(self, user_id: str) -> Dict[str, Any]:
        """構建主幫助導航"""
        try:
            return {
                "type": "flex_with_quick_reply",
                "flex_message": self._build_main_flex(user_id),
                "quick_reply": self._build_main_quick_reply(user_id)
            }
        except Exception as e:
            logger.error(f"構建主導航時出錯: {e}")
            return self._get_fallback_navigation()
    
    def build_category_navigation(self, category_id: str, category: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """構建分類導航"""
        try:
            return {
                "type": "flex_with_quick_reply",
                "flex_message": self._build_category_flex(category_id, category, user_id),
                "quick_reply": self._build_category_quick_reply(category_id, category, user_id)
            }
        except Exception as e:
            logger.error(f"構建分類導航時出錯: {e}")
            return self._get_fallback_navigation()
    
    def build_item_navigation(self, category_id: str, item_id: str, user_id: str) -> Dict[str, Any]:
        """構建項目導航"""
        try:
            return {
                "type": "flex_with_quick_reply", 
                "flex_message": self._build_item_flex(category_id, item_id, user_id),
                "quick_reply": self._build_item_quick_reply(category_id, item_id, user_id)
            }
        except Exception as e:
            logger.error(f"構建項目導航時出錯: {e}")
            return self._get_fallback_navigation()
    
    def build_search_navigation(self, user_id: str) -> Dict[str, Any]:
        """構建搜尋結果導航"""
        try:
            return {
                "type": "quick_reply_only",
                "quick_reply": {
                    "items": [
                        {
                            "type": "action",
                            "action": {
                                "type": "message",
                                "label": "🏠 回主選單",
                                "text": "幫助"
                            }
                        },
                        {
                            "type": "action",
                            "action": {
                                "type": "message",
                                "label": "🔍 新搜尋",
                                "text": "搜尋幫助"
                            }
                        }
                    ]
                }
            }
        except Exception as e:
            logger.error(f"構建搜尋導航時出錯: {e}")
            return self._get_fallback_navigation()
    
    def _build_main_flex(self, user_id: str) -> Dict[str, Any]:
        """構建主幫助Flex Message"""
        return {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "🔰 派班系統幫助中心",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#1DB446",
                        "align": "center"
                    },
                    {
                        "type": "text",
                        "text": "選擇您需要的幫助類型",
                        "size": "sm",
                        "color": "#666666",
                        "align": "center",
                        "margin": "sm"
                    }
                ],
                "paddingAll": "20px",
                "backgroundColor": "#F8F9FA"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            self._create_category_button("quick_start", "🚀 快速入門", "新手必看，5分鐘掌握基本操作"),
                            self._create_category_button("time_states", "⏰ 三時間態系統", "理解未來、現在、過去的派班邏輯"),
                            self._create_category_button("advanced_features", "🎯 進階功能", "提升效率的專業工具"),
                            self._create_category_button("troubleshooting", "🔧 故障排除", "常見問題快速解決")
                        ],
                        "spacing": "md"
                    }
                ],
                "paddingAll": "20px"
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "button",
                                "action": {
                                    "type": "message",
                                    "label": "🔍 搜尋幫助",
                                    "text": "搜尋幫助"
                                },
                                "style": "secondary",
                                "height": "sm",
                                "flex": 1
                            },
                            {
                                "type": "button",
                                "action": {
                                    "type": "message",
                                    "label": "📖 完整指令",
                                    "text": "完整指令列表"
                                },
                                "style": "secondary", 
                                "height": "sm",
                                "flex": 1,
                                "margin": "sm"
                            }
                        ]
                    }
                ],
                "paddingAll": "20px"
            }
        }
    
    def _build_main_quick_reply(self, user_id: str) -> Dict[str, Any]:
        """構建主幫助Quick Reply"""
        return {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "🎤 語音預約",
                        "text": "預約叫車"
                    }
                },
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "📅 今日班次",
                        "text": "東洋班次"
                    }
                },
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "🏥 診所班次",
                        "text": "診所班次"
                    }
                },
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "📋 固定班表",
                        "text": "help_demo_fixed"
                    }
                },
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "📊 查看報表",
                        "text": "help_demo_reports"
                    }
                }
            ]
        }
    
    def _build_category_flex(self, category_id: str, category: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """構建分類Flex Message"""
        items = category.get("items", [])
        
        return {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": category["title"],
                        "weight": "bold",
                        "size": "xl",
                        "color": "#1DB446",
                        "align": "center"
                    },
                    {
                        "type": "text",
                        "text": category["description"],
                        "size": "sm",
                        "color": "#666666",
                        "align": "center",
                        "margin": "sm",
                        "wrap": True
                    }
                ],
                "paddingAll": "20px",
                "backgroundColor": "#F8F9FA"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            self._create_item_button(category_id, item["id"], item["title"], item["description"])
                            for item in items[:self.max_flex_actions]
                        ],
                        "spacing": "md"
                    }
                ],
                "paddingAll": "20px"
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "message",
                            "label": "🏠 回主選單",
                            "text": "幫助"
                        },
                        "style": "secondary",
                        "height": "sm"
                    }
                ],
                "paddingAll": "20px"
            }
        }
    
    def _build_category_quick_reply(self, category_id: str, category: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """構建分類Quick Reply"""
        items = category.get("items", [])
        quick_items = []
        
        # 添加項目快捷按鈕
        for item in items[:self.max_quick_reply_items - 2]:  # 保留2個位置給導航
            quick_items.append({
                "type": "action",
                "action": {
                    "type": "message",
                    "label": f"📖 {item['title'][:8]}",
                    "text": f"help_item_{category_id}_{item['id']}"
                }
            })
        
        # 添加導航按鈕
        quick_items.extend([
            {
                "type": "action",
                "action": {
                    "type": "message",
                    "label": "🏠 主選單",
                    "text": "幫助"
                }
            },
            {
                "type": "action",
                "action": {
                    "type": "message",
                    "label": "🔍 搜尋",
                    "text": "搜尋幫助"
                }
            }
        ])
        
        return {"items": quick_items}
    
    def _build_item_flex(self, category_id: str, item_id: str, user_id: str) -> Dict[str, Any]:
        """構建項目Flex Message"""
        return {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📖 詳細說明",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#1DB446",
                        "align": "center"
                    }
                ],
                "paddingAll": "15px",
                "backgroundColor": "#F8F9FA"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "詳細內容請看上方訊息",
                        "size": "sm",
                        "color": "#666666",
                        "align": "center",
                        "wrap": True
                    }
                ],
                "paddingAll": "20px"
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "button",
                                "action": {
                                    "type": "message",
                                    "label": "◀️ 返回分類",
                                    "text": f"help_category_{category_id}"
                                },
                                "style": "secondary",
                                "height": "sm",
                                "flex": 1
                            },
                            {
                                "type": "button",
                                "action": {
                                    "type": "message",
                                    "label": "🏠 主選單",
                                    "text": "幫助"
                                },
                                "style": "secondary",
                                "height": "sm",
                                "flex": 1,
                                "margin": "sm"
                            }
                        ]
                    }
                ],
                "paddingAll": "20px"
            }
        }
    
    def _build_item_quick_reply(self, category_id: str, item_id: str, user_id: str) -> Dict[str, Any]:
        """構建項目Quick Reply"""
        return {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "🎯 立即試用",
                        "text": self._get_demo_action(category_id, item_id)
                    }
                },
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "📚 相關主題",
                        "text": f"help_category_{category_id}"
                    }
                },
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": "🏠 主選單",
                        "text": "幫助"
                    }
                }
            ]
        }
    
    def _create_category_button(self, category_id: str, title: str, description: str) -> Dict[str, Any]:
        """創建分類按鈕"""
        return {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": title,
                            "weight": "bold",
                            "size": "md",
                            "color": "#333333"
                        },
                        {
                            "type": "text",
                            "text": description,
                            "size": "sm",
                            "color": "#666666",
                            "wrap": True,
                            "margin": "xs"
                        }
                    ],
                    "flex": 4
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "action": {
                                "type": "message",
                                "label": "進入",
                                "text": f"help_category_{category_id}"
                            },
                            "style": "primary",
                            "height": "sm"
                        }
                    ],
                    "flex": 1,
                    "justifyContent": "center"
                }
            ],
            "paddingAll": "md",
            "backgroundColor": "#FFFFFF",
            "cornerRadius": "md",
            "action": {
                "type": "message",
                "text": f"help_category_{category_id}"
            }
        }
    
    def _create_item_button(self, category_id: str, item_id: str, title: str, description: str) -> Dict[str, Any]:
        """創建項目按鈕"""
        return {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": title,
                            "weight": "bold",
                            "size": "sm",
                            "color": "#333333"
                        },
                        {
                            "type": "text",
                            "text": description,
                            "size": "xs",
                            "color": "#666666",
                            "wrap": True,
                            "margin": "xs"
                        }
                    ],
                    "flex": 3
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "action": {
                                "type": "message",
                                "label": "查看",
                                "text": f"help_item_{category_id}_{item_id}"
                            },
                            "style": "secondary",
                            "height": "sm"
                        }
                    ],
                    "flex": 1,
                    "justifyContent": "center"
                }
            ],
            "paddingAll": "sm",
            "backgroundColor": "#F8F9FA",
            "cornerRadius": "sm",
            "action": {
                "type": "message",
                "text": f"help_item_{category_id}_{item_id}"
            }
        }
    
    def _get_demo_action(self, category_id: str, item_id: str) -> str:
        """獲取演示操作"""
        demo_actions = {
            "quick_start_basic_commands": "東洋班次",
            "quick_start_voice_booking": "預約叫車",
            "time_states_future_mode": "預約叫車 明天下午3點從台北到桃園",
            "time_states_present_mode": "東洋班次",
            "time_states_past_mode": "查已完成",
            "advanced_features_ai_assistant": "預約叫車",
            "advanced_features_fixed_schedules": "help_demo_fixed",
            "advanced_features_reporting_system": "生成周報表",
            "troubleshooting_common_errors": "help_demo_troubleshoot",
            "troubleshooting_system_status": "help_system_check"
        }
        
        demo_key = f"{category_id}_{item_id}"
        return demo_actions.get(demo_key, "幫助")
    
    def _get_fallback_navigation(self) -> Dict[str, Any]:
        """獲取備用導航"""
        return {
            "type": "quick_reply_only",
            "quick_reply": {
                "items": [
                    {
                        "type": "action",
                        "action": {
                            "type": "message",
                            "label": "🏠 主選單",
                            "text": "幫助"
                        }
                    },
                    {
                        "type": "action",
                        "action": {
                            "type": "message",
                            "label": "📖 文字版",
                            "text": "幫助文字"
                        }
                    }
                ]
            }
        }