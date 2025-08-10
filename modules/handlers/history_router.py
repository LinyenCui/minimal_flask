"""
輕路由：過去態入口（完成記錄/查已完成）
行為維持不變，將主路由的分支委派至此。
"""
import logging
from modules.utils.line_bot import reply_text

logger = logging.getLogger(__name__)


def handle_history_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    try:
        # 傳統查已完成
        if message_text.startswith("查已完成"):
            from modules.services.ai_fare_service import handle_smart_fare_query
            result = handle_smart_fare_query(message_text, user_id, use_flex=True)
            # 使用統一處理（text_message_handler 中已有工具，但這裡直接簡化為文字回覆或錯誤）
            from modules.utils.response_handler import ResponseHandler
            if not ResponseHandler.handle_legacy_format(reply_token, result):
                reply_text(reply_token, "❌ 處理查已完成結果失敗")
            return True

        # 完成記錄 → 轉換為 查已完成
        if message_text.startswith("完成記錄"):
            from modules.services.trip_query_service import handle_query_completed_trips
            if message_text == "完成記錄":
                converted_query = "查已完成 今天"
            else:
                converted_query = message_text.replace("完成記錄", "查已完成", 1)
            logger.info(f"[history_router] 完成記錄命令轉換: '{message_text}' → '{converted_query}'")
            result = handle_query_completed_trips(converted_query)
            reply_text(reply_token, result or "📋 未找到符合條件的已完成班次")
            return True
        return False
    except Exception as e:
        logger.error(f"[history_router] 命令處理失敗: {e}", exc_info=True)
        reply_text(reply_token, f"❌ 查詢失敗: {str(e)}")
        return True
