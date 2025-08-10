"""
輕路由：查詢相關命令（診所班次、東洋班次、查詢班次/範圍）
行為維持不變，僅包裝主路由分支。
"""
import logging
from modules.utils.line_bot import reply_text, reply_message, reply_flex

logger = logging.getLogger(__name__)

def handle_query_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    try:
        # 東洋班次（東洋/臨時）
        if message_text.startswith("東洋班次"):
            parts = message_text.split()
            if len(parts) > 1:
                logger.info(f"處理東洋班次命令 (帶日期): {message_text}")
                from modules.services.trip_query_service import handle_query_trips_flex
                flex_content, result_message = handle_query_trips_flex(message_text)
                if flex_content:
                    reply_flex(reply_token, "班次查詢結果", flex_content)
                elif result_message:
                    reply_text(reply_token, result_message)
                else:
                    reply_text(reply_token, "查詢完成，但沒有找到任何信息。")
            else:
                logger.info(f"處理東洋班次命令 (觸發日期選擇): {message_text}")
                from modules.services.trip_query_service import request_toyo_temp_trip_date_selection
                reply_msg, error_message = request_toyo_temp_trip_date_selection()
                if reply_msg and error_message is None:
                    reply_message(reply_token, [reply_msg])
                else:
                    reply_text(reply_token, error_message or "無法生成日期選擇")
            return True
        # 診所班次
        if message_text.startswith("診所班次"):
            parts = message_text.split()
            if len(parts) > 1:
                logger.info(f"處理診所班次命令 (帶日期): {message_text}")
                from modules.services.trip_query_service import handle_query_clinic_trips_flex
                flex_content, message = handle_query_clinic_trips_flex(message_text)
                if flex_content:
                    reply_flex(reply_token, "診所班次查詢結果", flex_content)
                else:
                    reply_text(reply_token, message or "查詢診所班次時發生未知錯誤。")
            else:
                logger.info(f"處理診所班次命令 (觸發日期選擇): {message_text}")
                from modules.services.trip_query_service import request_clinic_trip_date_selection
                reply_msg, error_message = request_clinic_trip_date_selection()
                if reply_msg and error_message is None:
                    reply_message(reply_token, [reply_msg])
                else:
                    reply_text(reply_token, error_message or "無法生成日期選擇")
            return True
        # 查詢班次（複雜條件）
        if message_text.startswith("查詢班次"):
            from modules.services.advanced_query_processor import AdvancedQueryProcessor
            processor = AdvancedQueryProcessor()
            result = processor.process_complex_query(message_text, user_id)
            from modules.utils.line_bot import reply_message_with_quick_reply
            if result.get('type') == 'success':
                reply_text(reply_token, result['message'])
            elif result.get('type') == 'success_with_pagination':
                reply_message_with_quick_reply(reply_token, result['message'], result['quick_reply'])
            elif result.get('type') == 'no_results':
                reply_text(reply_token, result['message'])
            else:
                reply_text(reply_token, result.get('message', '查詢完成'))
            return True
        # 範圍查詢
        if message_text.startswith("查已完成範圍"):
            from modules.services.date_range_query_service import handle_query_completed_trips_range
            result = handle_query_completed_trips_range(message_text)
            reply_text(reply_token, result)
            return True
        if message_text.startswith("查班次範圍"):
            from modules.services.date_range_query_service import handle_query_current_trips_range
            result = handle_query_current_trips_range(message_text)
            reply_text(reply_token, result)
            return True
        return False
    except Exception as e:
        logger.error(f"查詢命令處理失敗: {e}", exc_info=True)
        reply_text(reply_token, f"查詢處理失敗: {str(e)}")
        return True
