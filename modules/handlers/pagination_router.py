"""
輕路由：分頁命令（更多/下一頁/更多結果）
行為維持不變，從主路由移出。
"""
import logging
from modules.utils.line_bot import reply_text, reply_message

logger = logging.getLogger(__name__)

PAGINATION_COMMANDS = {"更多", "下一頁", "更多結果", "next", "more"}

def handle_pagination_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    if message_text not in PAGINATION_COMMANDS:
        return False
    try:
        logger.info(f"[pagination_router] 處理翻頁命令: {message_text}")
        from modules.utils.conversation_context import get_conversation_context
        context = get_conversation_context(user_id)
        query_state = context.get_query_result()
        if not query_state:
            reply_text(reply_token, "💡 沒有可用的查詢結果或會話已過期\n\n請重新執行查詢命令")
            return True
        current_page = query_state.get('current_page', 0)
        page_result = context.get_page_results(current_page + 1)
        if page_result and page_result.get('type') == 'success':
            result_message = page_result.get('message')
            quick_reply = page_result.get('quick_reply')
            if quick_reply:
                from linebot.v3.messaging import TextMessage
                text_msg = TextMessage(text=result_message, quick_reply=quick_reply)
                reply_message(reply_token, [text_msg])
                logger.info("[pagination_router] 發送帶Quick Reply的翻頁結果")
            else:
                reply_text(reply_token, result_message)
                logger.info("[pagination_router] 發送純文本翻頁結果")
        else:
            reply_text(reply_token, "💡 沒有更多結果或會話已過期\n\n請重新執行查詢命令")
        return True
    except Exception as e:
        logger.error(f"[pagination_router] 處理翻頁命令時出錯: {e}")
        reply_text(reply_token, "翻頁功能暫時不可用，請重新查詢")
        return True
