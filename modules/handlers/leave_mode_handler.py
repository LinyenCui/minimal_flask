"""
請假模式處理器
處理所有請假相關的邏輯，包括：
- 請假模式管理
- 簡單請假格式處理
- 乘客請假對話流程
"""
import logging
import re
from modules.utils.conversation_context import conversation_manager
from modules.utils.line_bot import reply_text

logger = logging.getLogger(__name__)


def handle_leave_mode_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    """
    處理請假模式相關命令
    返回 True 表示已處理，False 表示未處理
    """
    # 處理「放棄操作」命令（在請假模式中）
    if message_text.strip() == "放棄操作":
        if conversation_manager.is_in_leave_mode(user_id):
            conversation_manager.clear_leave_mode(user_id)
            reply_text(reply_token, "❌ 已取消請假操作")
            return True
        else:
            reply_text(reply_token, "❌ 目前沒有進行中的操作可以取消")
            return True
    
    # 檢查簡單請假格式（原因 加成）
    if conversation_manager.is_in_leave_mode(user_id):
        return check_and_handle_simple_leave_format(message_text, user_id, reply_token)
    
    return False


def check_and_handle_simple_leave_format(message_text: str, user_id: str, reply_token: str) -> bool:
    """
    檢查並處理簡單請假格式：[原因] [數字]
    返回 True 表示已處理，False 表示格式不符
    """
    # 嚴格的請假格式檢查：必須是 [原因] [數字] 格式
    parts = message_text.split()
    is_valid_format = False
    
    # 必須恰好2個部分：原因 + 數字
    if len(parts) == 2:
        try:
            # 第二部分必須是數字（加成）
            int(parts[1])
            is_valid_format = True
        except ValueError:
            pass
    
    if not is_valid_format:
        # 格式不符，自動取消請假模式
        logger.info(f"❌ 用戶 {user_id} 輸入格式不符，自動取消請假模式: {message_text}")
        conversation_manager.clear_leave_mode(user_id)
        reply_text(reply_token, 
            "❌ 請假格式不正確，已自動取消請假模式\n\n"
            "正確格式：[原因] [加成金額]\n"
            "例如：出國 300"
        )
        return True
    
    # 格式正確，執行請假
    reason = parts[0]
    extra_fare = int(parts[1])
    
    # 獲取請假模式上下文（使用 get_recent_trip_id 和 get_recent_fixed_schedule_id）
    recent_trip_id = conversation_manager.get_recent_trip_id(user_id)
    recent_fixed_schedule_id = conversation_manager.get_recent_fixed_schedule_id(user_id)
    
    if not recent_trip_id and not recent_fixed_schedule_id:
        conversation_manager.clear_leave_mode(user_id)
        reply_text(reply_token, "❌ 請假模式上下文遺失，請重新操作")
        return True
    
    # 執行請假
    try:
        if recent_fixed_schedule_id:
            # 固定班次請假
            from modules.handlers.fixed_schedule_leave_handler import handle_fixed_schedule_leave_command
            full_command = f"固定班次請假 {recent_fixed_schedule_id} {extra_fare} {reason}"
            result = handle_fixed_schedule_leave_command(full_command, user_id)
        elif recent_trip_id:
            # 一般班次請假
            from modules.handlers.passenger_leave_handler import handle_passenger_leave_command
            full_command = f"乘客請假 {recent_trip_id} {extra_fare} {reason}"
            result = handle_passenger_leave_command(full_command, user_id)
        
        # 清除請假模式
        conversation_manager.clear_leave_mode(user_id)
        
        reply_text(reply_token, result)
        return True
        
    except Exception as e:
        logger.error(f"執行請假時出錯: {e}")
        conversation_manager.clear_leave_mode(user_id)
        reply_text(reply_token, f"❌ 執行請假失敗：{str(e)}")
        return True


def handle_passenger_leave_conversation(conversation, message_text: str, user_id: str, reply_token: str):
    """
    處理乘客請假對話流程
    這個函數由 text_message_handler.py 在檢測到活躍的 passenger_leave 對話時調用
    """
    logger.info(f"🎯 處理乘客請假對話: 步驟={conversation.current_step}")
    
    # 嚴格的請假格式檢查：必須是 [原因] [數字] 格式
    parts = message_text.split()
    is_valid_format = False
    
    # 必須恰好2個部分：原因 + 數字
    if len(parts) == 2:
        try:
            # 第二部分必須是數字（加成）
            int(parts[1])
            is_valid_format = True
        except ValueError:
            pass
    
    if not is_valid_format:
        # 格式不符，結束對話
        logger.info(f"❌ 請假格式不符，結束對話: {message_text}")
        conversation_manager.end_conversation(user_id, "格式不符")
        reply_text(reply_token, 
            "❌ 請假格式不正確\n\n"
            "正確格式：[原因] [加成金額]\n"
            "例如：出國 300"
        )
        return
    
    # 格式正確，執行請假
    reason = parts[0]
    extra_fare = int(parts[1])
    
    # 獲取對話上下文
    context_data = conversation.context_data or {}
    trip_id = context_data.get('trip_id')
    
    if not trip_id:
        conversation_manager.end_conversation(user_id, "上下文遺失")
        reply_text(reply_token, "❌ 對話上下文遺失，請重新操作")
        return
    
    # 執行請假
    try:
        from modules.handlers.passenger_leave_handler import handle_passenger_leave_command
        result = handle_passenger_leave_command(f"乘客請假 {trip_id} {extra_fare} {reason}", user_id)
        
        # 結束對話
        conversation_manager.end_conversation(user_id, "請假完成")
        
        reply_text(reply_token, result)
        
    except Exception as e:
        logger.error(f"執行請假時出錯: {e}")
        conversation_manager.end_conversation(user_id, "執行失敗")
        reply_text(reply_token, f"❌ 執行請假失敗：{str(e)}")


def set_leave_mode_with_context(user_id: str, fixed_schedule_id: int = None, trip_id: int = None):
    """
    設置請假模式並保存上下文
    """
    context = {}
    
    if fixed_schedule_id:
        context['is_fixed_schedule'] = True
        context['fixed_schedule_id'] = fixed_schedule_id
        conversation_manager.set_leave_mode(user_id=user_id, fixed_schedule_id=fixed_schedule_id)
        logger.info(f"✅ 設置用戶 {user_id} 進入固定班次請假模式，固定班次 #{fixed_schedule_id}")
    elif trip_id:
        context['is_fixed_schedule'] = False
        context['trip_id'] = trip_id
        conversation_manager.set_leave_mode(user_id=user_id, trip_id=trip_id)
        logger.info(f"✅ 設置用戶 {user_id} 進入一般班次請假模式，班次 #{trip_id}")
    
    return context
