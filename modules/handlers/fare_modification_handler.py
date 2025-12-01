"""
車資修改處理器
處理所有車資修改相關的邏輯，包括：
- 記錄車資命令
- AI車資修改確認
- 車資修改對話流程
"""
import logging
from modules.utils.conversation_context import conversation_manager
from modules.utils.line_bot import reply_text
from modules.utils.response_handler import ResponseHandler

logger = logging.getLogger(__name__)


def handle_fare_modification_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    """
    處理車資修改相關命令
    返回 True 表示已處理，False 表示未處理
    """
    # 處理 "記錄車資" 命令
    if message_text.startswith("記錄車資"):
        return _handle_record_fare_command(message_text, user_id, reply_token)
    
    # 處理 "確認AI修改" 命令
    elif message_text.startswith("確認AI修改"):
        return _handle_ai_modification_confirm(message_text, user_id, reply_token)
    
    # 處理取消命令
    elif message_text in ["取消AI修改", "放棄AI修改"]:
        return _handle_ai_modification_cancel(user_id, reply_token)
    
    return False


def _handle_record_fare_command(message_text: str, user_id: str, reply_token: str) -> bool:
    """處理記錄車資命令"""
    try:
        parts = message_text.split()
        
        # 檢查基本參數（至少需要：記錄車資 ID 錶價）
        if len(parts) < 3:
            reply_text(reply_token, "❌ 參數不足\n\n正確格式：\n記錄車資 [班次ID] [錶價] [加成] [原因]")
            return True
        
        # 解析參數
        try:
            completed_trip_id = int(parts[1])
            meter_fare = int(parts[2])
            extra_fare = int(parts[3]) if len(parts) > 3 else 0
            reason = " ".join(parts[4:]) if len(parts) > 4 else ""
        except ValueError:
            reply_text(reply_token, "❌ 參數格式錯誤\n\n班次ID和金額必須是數字")
            return True
        
        # 執行記錄車資
        from modules.services.trip_service import record_fare
        result = record_fare(completed_trip_id, meter_fare, extra_fare, reason)
        
        reply_text(reply_token, result)
        return True
        
    except Exception as e:
        logger.error(f"處理記錄車資命令時出錯: {e}")
        reply_text(reply_token, f"❌ 處理記錄車資命令時出錯：{str(e)}")
        return True


def _handle_ai_modification_confirm(message_text: str, user_id: str, reply_token: str) -> bool:
    """處理確認AI修改命令"""
    try:
        # 獲取待處理的修改
        pending_modification = conversation_manager.get_pending_modification(user_id)
        
        if not pending_modification:
            reply_text(reply_token, "❌ 沒有待確認的修改")
            return True
        
        # 執行修改
        completed_trip_id = pending_modification.get('completed_trip_id')
        meter_fare = pending_modification.get('meter_fare')
        extra_fare = pending_modification.get('extra_fare')
        reason = pending_modification.get('reason', '')
        
        from modules.services.trip_service import record_fare
        result = record_fare(completed_trip_id, meter_fare, extra_fare, reason)
        
        # 清除待處理修改
        conversation_manager.clear_pending_modification(user_id)
        
        reply_text(reply_token, result)
        return True
        
    except Exception as e:
        logger.error(f"確認AI修改時出錯: {e}")
        reply_text(reply_token, f"❌ 確認修改時出錯：{str(e)}")
        return True


def _handle_ai_modification_cancel(user_id: str, reply_token: str) -> bool:
    """處理取消AI修改命令"""
    conversation_manager.clear_pending_modification(user_id)
    reply_text(reply_token, "✅ 已放棄AI修改")
    return True


def handle_fare_modification_conversation(conversation, message_text: str, user_id: str, reply_token: str):
    """
    處理車資修改對話流程
    這個函數由 text_message_handler.py 在檢測到活躍的 fare_modification 對話時調用
    """
    logger.info(f"🎯 處理車資修改對話: 步驟={conversation.current_step}")
    
    # 這裡可以根據對話步驟進行不同的處理
    # 目前大部分邏輯由 ai_fare_service.py 處理
    # 這個函數主要是作為擴展點
    
    # 檢查是否是取消命令
    if message_text.strip() in ["取消", "放棄", "放棄操作"]:
        conversation_manager.end_conversation(user_id, "用戶取消")
        reply_text(reply_token, "❌ 已取消車資修改")
        return
    
    # 其他情況交給 AI fare service 處理
    try:
        from modules.services.ai_fare_service import handle_smart_fare_query
        result = handle_smart_fare_query(message_text, user_id, use_flex=True)
        
        # 使用統一的響應處理器
        ResponseHandler.handle_legacy_format(reply_token, result)
        
    except Exception as e:
        logger.error(f"車資修改對話處理失敗: {e}")
        reply_text(reply_token, f"❌ 處理失敗：{str(e)}")
        conversation_manager.end_conversation(user_id, "處理失敗")
