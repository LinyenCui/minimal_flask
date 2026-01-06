"""
統一查詢路由器 - 所有查詢的統一入口

設計原則（2026-01-06 重構）：
1. 標準命令格式直接處理（東洋班次、診所班次、查已完成範圍等）
2. 自然語言查詢統一解析後調用 date_range_query_service
3. 狀態篩選查詢（待派班次、請假班次）單獨處理
4. 聚合查詢（金額加總、統計）統一處理

統一執行層：date_range_query_service.handle_query_trips_range
"""
import logging
import re
from modules.utils.line_bot import reply_text, reply_message, reply_flex, reply_message_with_quick_reply
from linebot.v3.messaging import TextMessage

logger = logging.getLogger(__name__)


def handle_query_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    """
    統一查詢命令入口

    Returns:
        bool: True 如果已處理，False 如果未匹配
    """
    try:
        # === 1. 標準命令格式（精確匹配）===

        # 東洋班次
        if message_text.startswith("東洋班次"):
            return _handle_toyo_trips(message_text, user_id, reply_token)

        # 診所班次
        if message_text.startswith("診所班次"):
            return _handle_clinic_trips(message_text, user_id, reply_token)

        # 查詢班次（複雜條件 - trips 表）
        if message_text.startswith("查詢班次"):
            return _handle_query_trips(message_text, user_id, reply_token)

        # 查已完成範圍
        if message_text.startswith("查已完成範圍"):
            return _handle_completed_range(message_text, user_id, reply_token)

        # 查班次範圍
        if message_text.startswith("查班次範圍"):
            return _handle_current_range(message_text, user_id, reply_token)

        # 查已完成（單筆或條件）
        if message_text.startswith("查已完成"):
            return _handle_completed_query(message_text, user_id, reply_token)

        # === 2. 狀態篩選查詢 ===
        from modules.core.query_classifier import is_status_filter_query
        if is_status_filter_query(message_text):
            return _handle_status_filter_query(message_text, user_id, reply_token)

        # === 3. 自然語言日期查詢（有日期的查詢）===
        from modules.core.query_classifier import is_simple_direct_query
        if is_simple_direct_query(message_text):
            return _handle_natural_query(message_text, user_id, reply_token)

        return False

    except Exception as e:
        logger.error(f"查詢命令處理失敗: {e}", exc_info=True)
        reply_text(reply_token, f"查詢處理失敗: {str(e)}")
        return True


# === 標準命令處理 ===

def _handle_toyo_trips(message_text: str, user_id: str, reply_token: str) -> bool:
    """處理東洋班次命令"""
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


def _handle_clinic_trips(message_text: str, user_id: str, reply_token: str) -> bool:
    """處理診所班次命令"""
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


def _handle_query_trips(message_text: str, user_id: str, reply_token: str) -> bool:
    """處理查詢班次命令（trips 表複雜條件）"""
    from modules.services.advanced_query_processor import AdvancedQueryProcessor
    processor = AdvancedQueryProcessor()
    result = processor.process_complex_query(message_text, user_id)

    if result.get('type') == 'success':
        reply_text(reply_token, result['message'])
    elif result.get('type') == 'success_with_pagination':
        reply_message_with_quick_reply(reply_token, result['message'], result['quick_reply'])
    elif result.get('type') == 'no_results':
        reply_text(reply_token, result['message'])
    else:
        reply_text(reply_token, result.get('message', '查詢完成'))
    return True


def _handle_completed_range(message_text: str, user_id: str, reply_token: str) -> bool:
    """處理查已完成範圍命令"""
    from modules.services.date_range_query_service import handle_query_completed_trips_range
    result = handle_query_completed_trips_range(message_text, user_id)

    if isinstance(result, dict):
        text_msg = TextMessage(text=result['message'], quick_reply=result.get('quick_reply'))
        reply_message(reply_token, [text_msg])
    else:
        reply_text(reply_token, result)
    return True


def _handle_current_range(message_text: str, user_id: str, reply_token: str) -> bool:
    """處理查班次範圍命令"""
    from modules.services.date_range_query_service import handle_query_current_trips_range
    result = handle_query_current_trips_range(message_text, user_id)

    if isinstance(result, dict):
        text_msg = TextMessage(text=result['message'], quick_reply=result.get('quick_reply'))
        reply_message(reply_token, [text_msg])
    else:
        reply_text(reply_token, result)
    return True


def _handle_completed_query(message_text: str, user_id: str, reply_token: str) -> bool:
    """處理查已完成命令（非範圍格式）"""
    from modules.services.advanced_query_processor import AdvancedQueryProcessor
    processor = AdvancedQueryProcessor()
    result = processor.process_complex_query(message_text, user_id)

    if result.get('type') in ('success', 'success_with_pagination', 'no_results'):
        if result.get('quick_reply'):
            reply_message_with_quick_reply(reply_token, result['message'], result['quick_reply'])
        else:
            reply_text(reply_token, result['message'])
    else:
        reply_text(reply_token, result.get('message', '查詢完成'))
    return True


# === 狀態篩選查詢 ===

def _handle_status_filter_query(message_text: str, user_id: str, reply_token: str) -> bool:
    """處理狀態篩選查詢（待派班次、請假班次等）"""
    try:
        from modules.services.advanced_query_processor import AdvancedQueryProcessor
        from modules.core.query_classifier import determine_query_table

        processor = AdvancedQueryProcessor()
        table = determine_query_table(message_text)

        if table == 'completed_trips':
            cmd = f"查已完成 {message_text}"
        else:
            cmd = f"查詢班次 {message_text}"

        logger.info(f"📊 狀態篩選查詢: {cmd}")
        result = processor.process_complex_query(cmd, user_id)

        if result.get('type') in ('success', 'success_with_pagination', 'no_results'):
            if result.get('quick_reply'):
                reply_message_with_quick_reply(reply_token, result['message'], result['quick_reply'])
            else:
                reply_text(reply_token, result['message'])
            return True

        return False

    except Exception as e:
        logger.error(f"狀態篩選查詢處理失敗: {e}")
        return False


# === 自然語言查詢 ===

def _handle_natural_query(message_text: str, user_id: str, reply_token: str) -> bool:
    """
    處理自然語言查詢（有日期的查詢）
    統一使用 date_range_query_service.handle_query_trips_range
    """
    try:
        from modules.core.query_classifier import parse_direct_query, determine_query_table, _has_location_pattern
        from modules.services.date_range_query_service import handle_query_trips_range

        query_params = parse_direct_query(message_text)

        if not query_params or not query_params.get('start_date'):
            return False

        start = query_params['start_date']
        end = query_params.get('end_date') or start
        driver_id = query_params.get('driver_id')
        category = query_params.get('category')
        location = query_params.get('location')

        # 檢測聚合關鍵字
        aggregation_keywords = ['金額加總', '加總', '合計', '總額', '總和', '總計', '統計金額', '統計']
        is_aggregation = any(kw in message_text for kw in aggregation_keywords)

        # 檢測「已完成」關鍵字
        has_completed_keyword = '已完成' in message_text

        # 判斷目標表
        table = determine_query_table(message_text)
        force_completed = (table == 'completed_trips') or has_completed_keyword

        logger.info(f"📊 自然語言查詢: start={start}, end={end}, driver={driver_id}, "
                   f"category={category}, location={location}, mode={'aggregate' if is_aggregation else 'list'}, "
                   f"force_completed={force_completed}")

        # 有地點的查詢暫時還是走 advanced_query_processor（它有更好的地點處理）
        if location and not is_aggregation:
            return _handle_location_query(message_text, user_id, reply_token, table)

        # 統一使用 handle_query_trips_range
        result = handle_query_trips_range(
            start_date=start,
            end_date=end,
            driver_id=driver_id,
            category=category,
            location=location,
            user_id=user_id,
            force_completed=force_completed,
            mode="aggregate" if is_aggregation else "list"
        )

        if result:
            text_payload = result.get('text', '')
            quick_reply = result.get('quick_reply')

            logger.info(f"📱 自然語言查詢結果: text長度={len(text_payload)}, quick_reply={'有' if quick_reply else '無'}")

            if quick_reply:
                text_msg = TextMessage(text=text_payload, quick_reply=quick_reply)
                reply_message(reply_token, [text_msg])
            else:
                reply_text(reply_token, text_payload)
            return True

        return False

    except Exception as e:
        logger.error(f"自然語言查詢處理失敗: {e}", exc_info=True)
        return False


def _handle_location_query(message_text: str, user_id: str, reply_token: str, table: str) -> bool:
    """處理有地點的查詢（暫時使用 advanced_query_processor）"""
    try:
        from modules.services.advanced_query_processor import AdvancedQueryProcessor
        processor = AdvancedQueryProcessor()

        if table == 'completed_trips':
            cmd = f"查已完成 {message_text}"
        else:
            cmd = f"查詢班次 {message_text}"

        logger.info(f"📊 地點查詢: {cmd}")
        result = processor.process_complex_query(cmd, user_id)

        if result.get('type') in ('success', 'success_with_pagination', 'no_results'):
            if result.get('quick_reply'):
                reply_message_with_quick_reply(reply_token, result['message'], result['quick_reply'])
            else:
                reply_text(reply_token, result['message'])
            return True

        return False

    except Exception as e:
        logger.error(f"地點查詢處理失敗: {e}")
        return False
