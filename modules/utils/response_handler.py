"""
統一響應處理器
處理所有類型的響應格式，並統一發送給 LINE Bot API
"""
import logging
from typing import Dict, Any
from linebot.v3.messaging import TextMessage, FlexMessage, FlexContainer, ReplyMessageRequest
from modules.utils.line_bot import reply_text, reply_message, get_line_bot_api
from modules.utils.quick_reply_manager import QuickReplyManager

logger = logging.getLogger(__name__)

class ResponseHandler:
    """
    統一響應處理器
    負責將標準化的響應格式轉換為適當的 LINE 消息並發送
    """
    
    @staticmethod
    def send_response(reply_token: str, response: Dict[str, Any]) -> bool:
        """
        統一發送響應
        
        Args:
            reply_token: LINE Bot 回覆 token
            response: 標準化的響應字典
        
        Returns:
            是否發送成功
        """
        try:
            # 驗證響應格式
            if not QuickReplyManager.validate_response_format(response):
                logger.error("響應格式驗證失敗")
                return False
            
            response_type = response["type"]
            
            # 根據類型處理響應
            if response_type == QuickReplyManager.ResponseType.TEXT_ONLY:
                return ResponseHandler._send_text_only(reply_token, response)
            
            elif response_type == QuickReplyManager.ResponseType.TEXT_WITH_QUICK_REPLY:
                return ResponseHandler._send_text_with_quick_reply(reply_token, response)
            
            elif response_type == QuickReplyManager.ResponseType.FLEX_ONLY:
                return ResponseHandler._send_flex_only(reply_token, response)
            
            elif response_type == QuickReplyManager.ResponseType.FLEX_WITH_QUICK_REPLY:
                return ResponseHandler._send_flex_with_quick_reply(reply_token, response)
            
            else:
                logger.error(f"未知的響應類型: {response_type}")
                return False
                
        except Exception as e:
            logger.error(f"發送響應時出錯: {e}")
            return False
    
    @staticmethod
    def _send_text_only(reply_token: str, response: Dict[str, Any]) -> bool:
        """發送純文字消息"""
        try:
            reply_text(reply_token, response["text"])
            logger.info("✅ 純文字消息發送成功")
            return True
        except Exception as e:
            logger.error(f"發送純文字消息失敗: {e}")
            return False
    
    @staticmethod
    def _send_text_with_quick_reply(reply_token: str, response: Dict[str, Any]) -> bool:
        """發送帶 Quick Reply 的文字消息"""
        try:
            # 轉換為 LINE SDK 格式
            quick_reply_obj = QuickReplyManager.convert_to_line_sdk_object(response["quick_reply"])
            
            # 創建 TextMessage
            message = TextMessage(
                text=response["text"],
                quick_reply=quick_reply_obj
            )
            
            # 發送消息
            line_bot_api = get_line_bot_api()
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[message]
                )
            )
            
            logger.info("✅ 帶 Quick Reply 的文字消息發送成功")
            return True
            
        except Exception as e:
            logger.error(f"發送帶 Quick Reply 的文字消息失敗: {e}")
            return False
    
    @staticmethod
    def _send_flex_only(reply_token: str, response: Dict[str, Any]) -> bool:
        """發送純 Flex 消息"""
        try:
            # 創建 FlexMessage
            flex_message = FlexMessage(
                alt_text=response.get("alt_text", "Flex Message"),
                contents=FlexContainer.from_dict(response["flex_message"])
            )
            
            # 發送消息
            reply_message(reply_token, [flex_message])
            
            logger.info("✅ Flex 消息發送成功")
            return True
            
        except Exception as e:
            logger.error(f"發送 Flex 消息失敗: {e}")
            return False
    
    @staticmethod
    def _send_flex_with_quick_reply(reply_token: str, response: Dict[str, Any]) -> bool:
        """發送帶 Quick Reply 的 Flex 消息"""
        try:
            # 轉換為 LINE SDK 格式
            quick_reply_obj = QuickReplyManager.convert_to_line_sdk_object(response["quick_reply"])
            
            # 創建 FlexMessage
            flex_message = FlexMessage(
                alt_text=response.get("alt_text", "Flex Message"),
                contents=FlexContainer.from_dict(response["flex_message"]),
                quick_reply=quick_reply_obj
            )
            
            # 發送消息
            reply_message(reply_token, [flex_message])
            
            logger.info("✅ 帶 Quick Reply 的 Flex 消息發送成功")
            return True
            
        except Exception as e:
            logger.error(f"發送帶 Quick Reply 的 Flex 消息失敗: {e}")
            return False
    
    @staticmethod
    def handle_legacy_format(reply_token: str, result: Any) -> bool:
        """
        處理舊格式的響應（向後兼容）
        
        Args:
            reply_token: LINE Bot 回覆 token
            result: 舊格式的響應數據
        
        Returns:
            是否處理成功
        """
        try:
            # 如果已經是新格式，直接處理
            if isinstance(result, dict) and "type" in result:
                response_type = result["type"]
                
                # 檢查是否為新的標準格式
                if response_type in [
                    QuickReplyManager.ResponseType.TEXT_ONLY,
                    QuickReplyManager.ResponseType.TEXT_WITH_QUICK_REPLY,
                    QuickReplyManager.ResponseType.FLEX_ONLY,
                    QuickReplyManager.ResponseType.FLEX_WITH_QUICK_REPLY
                ]:
                    return ResponseHandler.send_response(reply_token, result)
                
                # 處理舊格式
                if response_type in ["text_with_quick_reply", "quick_reply"]:
                    # 轉換為新格式
                    text = result.get("message") or result.get("text", "")
                    quick_reply_data = result.get("quick_reply")
                    
                    if quick_reply_data:
                        new_response = {
                            "type": QuickReplyManager.ResponseType.TEXT_WITH_QUICK_REPLY,
                            "text": text,
                            "quick_reply": quick_reply_data
                        }
                    else:
                        new_response = {
                            "type": QuickReplyManager.ResponseType.TEXT_ONLY,
                            "text": text
                        }
                    
                    return ResponseHandler.send_response(reply_token, new_response)
                
                elif response_type == "flex_with_quick_reply":
                    # 轉換 Flex 格式
                    new_response = {
                        "type": QuickReplyManager.ResponseType.FLEX_WITH_QUICK_REPLY,
                        "flex_message": result.get("flex_message", {}),
                        "alt_text": result.get("alt_text", "Flex Message"),
                        "quick_reply": result.get("quick_reply", {})
                    }
                    
                    return ResponseHandler.send_response(reply_token, new_response)
                
                elif response_type == "text":
                    # 文字格式（可能帶 Quick Reply）
                    text = result.get("message") or result.get("text", "")
                    quick_reply_data = result.get("quick_reply")
                    
                    if quick_reply_data:
                        new_response = {
                            "type": QuickReplyManager.ResponseType.TEXT_WITH_QUICK_REPLY,
                            "text": text,
                            "quick_reply": quick_reply_data
                        }
                    else:
                        new_response = {
                            "type": QuickReplyManager.ResponseType.TEXT_ONLY,
                            "text": text
                        }
                    
                    return ResponseHandler.send_response(reply_token, new_response)
            
            # 如果是字符串，直接作為文字發送
            elif isinstance(result, str):
                new_response = {
                    "type": QuickReplyManager.ResponseType.TEXT_ONLY,
                    "text": result
                }
                return ResponseHandler.send_response(reply_token, new_response)
            
            # 處理 ai_fare_service 返回的格式
            elif isinstance(result, dict) and "flex_message" in result:
                # 這是來自 ai_fare_service 的 Flex 響應
                alt_text = result.get("alt_text", "AI查詢結果")
                quick_reply_data = result.get("quick_reply")
                
                if quick_reply_data:
                    new_response = {
                        "type": QuickReplyManager.ResponseType.FLEX_WITH_QUICK_REPLY,
                        "flex_message": result["flex_message"],
                        "alt_text": alt_text,
                        "quick_reply": quick_reply_data
                    }
                else:
                    new_response = {
                        "type": QuickReplyManager.ResponseType.FLEX_ONLY,
                        "flex_message": result["flex_message"],
                        "alt_text": alt_text
                    }
                
                return ResponseHandler.send_response(reply_token, new_response)
            
            else:
                logger.warning(f"無法處理的響應格式: {type(result)}")
                return False
                
        except Exception as e:
            logger.error(f"處理舊格式響應時出錯: {e}")
            return False

# 便利函數
def send_text_response(reply_token: str, text: str, quick_reply_buttons: list = None) -> bool:
    """
    便利函數：發送文字響應
    
    Args:
        reply_token: LINE Bot 回覆 token
        text: 文字內容
        quick_reply_buttons: Quick Reply 按鈕列表（可選）
    
    Returns:
        是否發送成功
    """
    response = QuickReplyManager.create_text_response(text, quick_reply_buttons)
    return ResponseHandler.send_response(reply_token, response)

def send_flex_response(reply_token: str, flex_content: dict, alt_text: str = "Flex Message", quick_reply_buttons: list = None) -> bool:
    """
    便利函數：發送 Flex 響應
    
    Args:
        reply_token: LINE Bot 回覆 token
        flex_content: Flex 內容字典
        alt_text: 替代文字
        quick_reply_buttons: Quick Reply 按鈕列表（可選）
    
    Returns:
        是否發送成功
    """
    response = QuickReplyManager.create_flex_response(flex_content, alt_text, quick_reply_buttons)
    return ResponseHandler.send_response(reply_token, response)