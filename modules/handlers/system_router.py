"""
系統維護路由器
處理系統維護相關命令：
- fix-sequence: 序列修復
- batch-allowance: 批量加成
- 清理trips: 清理過期數據
- 更新已完成班次: 手動觸發自動化任務
"""

import logging
from modules.utils.line_bot import reply_text
from modules.utils.response_handler import ResponseHandler

logger = logging.getLogger(__name__)


def handle_system_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    """
    處理系統維護相關命令
    
    Args:
        message_text: 用戶輸入
        user_id: 用戶ID
        reply_token: LINE回覆token
    
    Returns:
        bool: True表示已處理，False表示未處理
    """
    
    # 序列修復命令
    if message_text.startswith("fix-sequence"):
        return _handle_sequence_fix(user_id, reply_token)
    
    # 批量加成命令
    elif message_text.startswith("batch-allowance") or message_text.startswith("批量加成"):
        return _handle_batch_allowance(user_id, reply_token)
    
    # 清理trips命令
    elif message_text.startswith("清理trips"):
        return _handle_cleanup_trips(message_text, reply_token)
    
    # 更新已完成班次
    elif message_text == "更新已完成班次":
        return _handle_update_completed(reply_token)
    
    return False


def _handle_sequence_fix(user_id: str, reply_token: str) -> bool:
    """處理序列修復命令"""
    logger.info(f"用戶 {user_id} 請求序列修復")
    
    try:
        from modules.handlers.sequence_fix_handler import handle_sequence_fix_start
        response = handle_sequence_fix_start(user_id)
        
        if response:
            # 使用統一響應處理器
            success = ResponseHandler.handle_legacy_format(reply_token, response)
            if not success:
                reply_text(reply_token, "❌ 處理序列修復響應時出錯")
        else:
            reply_text(reply_token, "❌ 無法獲取序列狀態")
        
        return True
        
    except Exception as e:
        logger.error(f"序列修復命令處理失敗: {e}")
        reply_text(reply_token, f"❌ 序列修復檢查失敗: {str(e)}")
        return True


def _handle_batch_allowance(user_id: str, reply_token: str) -> bool:
    """處理批量加成命令"""
    logger.info(f"用戶 {user_id} 請求批量加成")
    
    try:
        from modules.handlers.batch_allowance_handler import handle_batch_allowance_start
        response = handle_batch_allowance_start(user_id)
        
        if response:
            reply_text(reply_token, response.get("text", "啟動批量加成中..."))
        else:
            reply_text(reply_token, "❌ 啟動批量加成失敗")
        
        return True
        
    except Exception as e:
        logger.error(f"批量加成命令處理失敗: {e}")
        reply_text(reply_token, f"❌ 批量加成啟動失敗: {str(e)}")
        return True


def _handle_cleanup_trips(message_text: str, reply_token: str) -> bool:
    """處理清理trips命令"""
    logger.info(f"處理清理trips命令: {message_text}")
    
    try:
        from modules.handlers.cleanup_handler import handle_cleanup_trips
        result_text = handle_cleanup_trips(message_text)
        reply_text(reply_token, result_text)
        return True
        
    except Exception as e:
        logger.error(f"清理trips命令處理失敗: {e}")
        reply_text(reply_token, f"❌ 清理trips失敗: {str(e)}")
        return True


def _handle_update_completed(reply_token: str) -> bool:
    """處理手動更新已完成班次命令"""
    logger.info("手動觸發更新已完成班次")
    
    try:
        from modules.services.scheduler_service import update_completed_trips
        result_text = update_completed_trips()
        reply_text(reply_token, result_text)
        return True
        
    except Exception as e:
        logger.error(f"更新已完成班次失敗: {e}")
        reply_text(reply_token, f"❌ 更新已完成班次失敗: {str(e)}")
        return True
