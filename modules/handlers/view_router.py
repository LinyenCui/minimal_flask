"""
輕路由：班次詳情與已完成班次查看
行為維持不變，將主路由的分支委派至此。
"""
import logging
from modules.utils.line_bot import reply_text, reply_message, reply_flex
from modules.utils.conversation_context import conversation_manager

logger = logging.getLogger(__name__)


def handle_view_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    """處理『班次詳情 [ID]』與『查看 [已完成ID]』。
    回傳 True 表示已處理，False 表示非本路由命令。
    """
    try:
        # 班次詳情
        if message_text.startswith("班次詳情"):
            parts = message_text.split()
            if len(parts) >= 2:
                try:
                    trip_id = int(parts[1])
                    logger.info(f"[view_router] 處理班次詳情Flex Message: {trip_id}")
                    from modules.services.trip_detail_service import handle_trip_details_flex
                    result, error_message = handle_trip_details_flex(trip_id)
                    if result and 'flex_message' in result:
                        try:
                            from linebot.v3.messaging import FlexMessage, FlexContainer, QuickReply, QuickReplyItem, PostbackAction
                            if 'quick_reply' in result and result['quick_reply'] is not None:
                                quick_reply_items = []
                                for item in result['quick_reply']['items']:
                                    action = item['action']
                                    quick_reply_items.append(
                                        QuickReplyItem(
                                            action=PostbackAction(
                                                label=action['label'],
                                                text=action.get('text', action['displayText']),
                                                data=action['data']
                                            )
                                        )
                                    )
                                quick_reply = QuickReply(items=quick_reply_items)
                                flex_message = FlexMessage(
                                    alt_text=f"班次 #{trip_id} 詳細信息",
                                    contents=FlexContainer.from_dict(result['flex_message']),
                                    quick_reply=quick_reply
                                )
                            else:
                                flex_message = FlexMessage(
                                    alt_text=f"班次 #{trip_id} 詳細信息",
                                    contents=FlexContainer.from_dict(result['flex_message'])
                                )
                            reply_message(reply_token, [flex_message])
                            try:
                                conversation_manager.set_recent_trip_id(user_id, trip_id)
                            except Exception as context_error:
                                logger.error(f"[view_router] 記錄班次ID到上下文時出錯: {context_error}")
                        except Exception as flex_error:
                            logger.error(f"[view_router] 發送Flex Message失敗: {flex_error}")
                            from modules.handlers.trip_handler import handle_trip_details
                            text_result = handle_trip_details(trip_id)
                            reply_text(reply_token, text_result)
                    else:
                        reply_text(reply_token, error_message or f"找不到班次 #{trip_id}")
                except ValueError:
                    reply_text(reply_token, "班次ID必須是數字。")
                except Exception as e:
                    logger.error(f"[view_router] 處理班次詳情失敗: {e}")
                    reply_text(reply_token, f"班次查詢失敗: {str(e)}")
            else:
                reply_text(reply_token, "請提供班次ID，例如：班次詳情 123")
            return True

        # 查看已完成班次詳情
        if message_text.startswith("查看"):
            parts = message_text.split()
            if len(parts) >= 2:
                try:
                    completed_trip_id = int(parts[1])
                    logger.info(f"[view_router] 處理查看已完成班次詳情: {completed_trip_id}")
                    from modules.handlers.trip_handler import handle_completed_trip_details
                    result = handle_completed_trip_details(completed_trip_id)
                    reply_text(reply_token, result)
                except ValueError:
                    reply_text(reply_token, "班次ID必須是數字。")
                except Exception as e:
                    logger.error(f"[view_router] 處理查看已完成班次失敗: {e}")
                    reply_text(reply_token, f"查看班次失敗: {str(e)}")
            else:
                reply_text(reply_token, "請提供班次ID，例如：查看 2207")
            return True
        return False
    except Exception as e:
        logger.error(f"[view_router] 命令處理失敗: {e}", exc_info=True)
        reply_text(reply_token, f"處理請求時出錯: {str(e)}")
        return True
