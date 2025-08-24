"""
Quick Reply 中央管理模組
統一管理所有 Quick Reply 相關邏輯，提供標準化的格式和處理方式
"""
import logging
from typing import Dict, List, Any, Union, Optional
from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction, PostbackAction

logger = logging.getLogger(__name__)

class QuickReplyManager:
    """
    Quick Reply 中央管理器
    負責統一處理所有 Quick Reply 相關邏輯
    """
    
    # 標準化的響應類型
    class ResponseType:
        TEXT_WITH_QUICK_REPLY = "text_with_quick_reply"
        FLEX_WITH_QUICK_REPLY = "flex_with_quick_reply" 
        TEXT_ONLY = "text_only"
        FLEX_ONLY = "flex_only"
    
    # 標準化的動作類型
    class ActionType:
        MESSAGE = "message"
        POSTBACK = "postback"
    
    @staticmethod
    def create_text_response(text: str, quick_reply_buttons: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        創建帶有 Quick Reply 的文字響應
        
        Args:
            text: 響應文字內容
            quick_reply_buttons: Quick Reply 按鈕列表
                格式: [{"label": "按鈕文字", "text": "發送內容", "type": "message"}]
        
        Returns:
            標準化的響應字典
        """
        response = {
            "type": QuickReplyManager.ResponseType.TEXT_ONLY,
            "text": text
        }
        
        if quick_reply_buttons:
            response["type"] = QuickReplyManager.ResponseType.TEXT_WITH_QUICK_REPLY
            response["quick_reply"] = QuickReplyManager._build_quick_reply_data(quick_reply_buttons)
        
        return response
    
    @staticmethod
    def create_flex_response(
        flex_content: Dict[str, Any], 
        alt_text: str = "Flex Message",
        quick_reply_buttons: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        創建帶有 Quick Reply 的 Flex 響應
        
        Args:
            flex_content: Flex Message 內容字典
            alt_text: Flex Message 的替代文字
            quick_reply_buttons: Quick Reply 按鈕列表
        
        Returns:
            標準化的響應字典
        """
        response = {
            "type": QuickReplyManager.ResponseType.FLEX_ONLY,
            "flex_message": flex_content,
            "alt_text": alt_text
        }
        
        if quick_reply_buttons:
            response["type"] = QuickReplyManager.ResponseType.FLEX_WITH_QUICK_REPLY
            response["quick_reply"] = QuickReplyManager._build_quick_reply_data(quick_reply_buttons)
        
        return response
    
    @staticmethod
    def _build_quick_reply_data(buttons: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        構建標準化的 Quick Reply 數據結構
        
        Args:
            buttons: 按鈕配置列表
        
        Returns:
            標準化的 Quick Reply 數據字典
        """
        items = []
        
        for button in buttons:
            action_type = button.get("type", QuickReplyManager.ActionType.MESSAGE)
            
            if action_type == QuickReplyManager.ActionType.MESSAGE:
                action = {
                    "type": "message",
                    "label": button["label"],
                    "text": button["text"]
                }
            elif action_type == QuickReplyManager.ActionType.POSTBACK:
                action = {
                    "type": "postback",
                    "label": button["label"],
                    "data": button["data"],
                    "text": button.get("text", button["label"])  # 顯示文字，默認為 label
                }
            else:
                logger.warning(f"未知的 Quick Reply 動作類型: {action_type}")
                continue
            
            items.append({
                "type": "action",
                "action": action
            })
        
        return {
            "items": items[:13]  # LINE 限制最多 13 個按鈕
        }
    
    @staticmethod
    def convert_to_line_sdk_object(quick_reply_data: Dict[str, Any]) -> QuickReply:
        """
        將標準化的 Quick Reply 數據轉換為 LINE SDK 對象
        
        Args:
            quick_reply_data: 標準化的 Quick Reply 數據字典
        
        Returns:
            LINE SDK QuickReply 對象
        """
        try:
            items = []
            
            for item_data in quick_reply_data.get("items", []):
                action_data = item_data.get("action", {})
                action_type = action_data.get("type")
                
                if action_type == "message":
                    action = MessageAction(
                        label=action_data["label"],
                        text=action_data["text"]
                    )
                elif action_type == "postback":
                    action = PostbackAction(
                        label=action_data["label"],
                        data=action_data["data"],
                        text=action_data.get("text")
                    )
                else:
                    logger.warning(f"未知的動作類型: {action_type}")
                    continue
                
                items.append(QuickReplyItem(action=action))
            
            return QuickReply(items=items)
            
        except Exception as e:
            logger.error(f"轉換 Quick Reply 為 LINE SDK 對象時出錯: {e}")
            return QuickReply(items=[])
    
    @staticmethod
    def create_common_buttons() -> Dict[str, List[Dict[str, str]]]:
        """
        創建常用的 Quick Reply 按鈕組合
        
        Returns:
            常用按鈕組合字典
        """
        return {
            "confirm_cancel": [
                {"label": "✅ 確認", "text": "確認", "type": "message"},
                {"label": "❌ 取消", "text": "取消", "type": "message"}
            ],
            "abandon_operation": [
                {"label": "🚫 放棄操作", "text": "放棄操作", "type": "message"}
            ],
            "abandon_ai_modification": [
                {"label": "❌ 放棄修改", "text": "放棄AI修改", "type": "message"}
            ],
            "confirm_abandon": [
                {"label": "✅ 確認", "text": "確認", "type": "message"},
                {"label": "🚫 放棄操作", "text": "放棄操作", "type": "message"}
            ],
            "booking_actions": [
                {"label": "重新預約", "text": "預約叫車", "type": "message"},
                {"label": "查詢班次", "text": "幫助", "type": "message"},
                {"label": "離開", "text": "謝謝", "type": "message"}
            ],
            "help_navigation": [
                {"label": "🏠 主選單", "text": "幫助", "type": "message"},
                {"label": "📞 客服", "text": "客服", "type": "message"}
            ]
        }
    
    @staticmethod
    def validate_response_format(response: Dict[str, Any]) -> bool:
        """
        驗證響應格式是否符合標準
        
        Args:
            response: 響應字典
        
        Returns:
            是否符合標準格式
        """
        required_fields = ["type"]
        
        # 檢查必要欄位
        for field in required_fields:
            if field not in response:
                logger.error(f"響應格式錯誤：缺少必要欄位 '{field}'")
                return False
        
        response_type = response["type"]
        
        # 根據類型檢查對應欄位
        if response_type in [QuickReplyManager.ResponseType.TEXT_WITH_QUICK_REPLY, QuickReplyManager.ResponseType.TEXT_ONLY]:
            if "text" not in response:
                logger.error("文字響應缺少 'text' 欄位")
                return False
        
        if response_type in [QuickReplyManager.ResponseType.FLEX_WITH_QUICK_REPLY, QuickReplyManager.ResponseType.FLEX_ONLY]:
            if "flex_message" not in response:
                logger.error("Flex 響應缺少 'flex_message' 欄位")
                return False
            if "alt_text" not in response:
                logger.error("Flex 響應缺少 'alt_text' 欄位")
                return False
        
        if response_type in [QuickReplyManager.ResponseType.TEXT_WITH_QUICK_REPLY, QuickReplyManager.ResponseType.FLEX_WITH_QUICK_REPLY]:
            if "quick_reply" not in response:
                logger.error("Quick Reply 響應缺少 'quick_reply' 欄位")
                return False
            
            # 驗證 quick_reply 結構
            quick_reply = response["quick_reply"]
            if not isinstance(quick_reply, dict) or "items" not in quick_reply:
                logger.error("Quick Reply 數據格式錯誤")
                return False
        
        return True

# 向後兼容的工具函數
def create_quick_reply_buttons(buttons: List[Dict[str, str]]) -> Dict[str, Any]:
    """向後兼容函數：創建 Quick Reply 按鈕"""
    return QuickReplyManager._build_quick_reply_data(buttons)

def create_text_with_quick_reply(text: str, buttons: List[Dict[str, str]]) -> Dict[str, Any]:
    """向後兼容函數：創建帶 Quick Reply 的文字響應"""
    return QuickReplyManager.create_text_response(text, buttons)