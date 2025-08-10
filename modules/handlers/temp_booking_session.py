"""
外觀層：為「預約叫車/臨時預約」提供穩定的 API，
隱藏內部的 temp_booking_states，降低跨模組耦合。

注意：此階段只做轉送，不改變任何現有行為。
"""
from typing import Optional, Dict, Any

# 可選：鏡射到統一對話管理（不改變現有行為，只做增強與觀測）
def _mirror_start_conversation(user_id: str):
    """在啟動預約時，於 conversation_manager 建立一個 temp_booking 活躍對話。
    僅在內部 temp_booking_states 成功建立後呼叫。
    不影響既有行為（外部仍以 temp_booking_states 為準）。
    """
    try:
        from modules.utils.conversation_context import conversation_manager
        conversation_manager.start_conversation(
            user_id=user_id,
            conversation_type='temp_booking',
            current_step='waiting_info',
            context_data={},
            prompt_message='請提供預約資訊（日期、時間、出發地等）',
            duration_minutes=10,
        )
    except Exception:
        # 靜默失敗以避免影響主流程
        pass

def _mirror_end_conversation(user_id: str):
    """在取消或結束預約時，結束 conversation_manager 對話。"""
    try:
        from modules.utils.conversation_context import conversation_manager
        conversation_manager.end_conversation(user_id, "預約流程結束")
    except Exception:
        pass

# 僅在函式內部導入，避免頂層循環相依與副作用

def is_booking_active(user_id: str) -> bool:
    """檢查使用者是否在預約叫車流程中（封裝 temp_booking_states）。"""
    from modules.handlers.temp_booking_handler import temp_booking_states  # lazy import
    return user_id in temp_booking_states


def start_booking(user_id: str, category: str = "東洋") -> Dict[str, Any]:
    """啟動預約叫車流程（封裝 handle_temp_booking_start）。"""
    from modules.handlers.temp_booking_handler import handle_temp_booking_start  # lazy import
    response = handle_temp_booking_start(user_id, category)
    # 鏡射：啟動活躍對話（不影響原本狀態機制）
    _mirror_start_conversation(user_id)
    return response


def handle_booking_message(user_id: str, message_text: str) -> Optional[Dict[str, Any]]:
    """處理預約叫車流程中的訊息（封裝 handle_temp_booking_message）。"""
    from modules.handlers.temp_booking_handler import handle_temp_booking_message  # lazy import
    result = handle_temp_booking_message(user_id, message_text)
    # 若流程內部回傳取消/完成語意，則鏡射結束會話（不精確比對，盡量保守）
    try:
        if isinstance(result, dict) and isinstance(result.get('text'), str):
            txt = result['text']
            success_markers = ["預約成功", "臨時預約成功", "✅ 臨時預約成功", "✅ 預約成功"]
            cancel_markers = ["已取消", "取消預約", "放棄", "結束"]
            if any(k in txt for k in cancel_markers + success_markers):
                _mirror_end_conversation(user_id)
    except Exception:
        pass
    return result


def cancel_booking(user_id: str) -> bool:
    """取消並清除使用者的預約叫車狀態（封裝 temp_booking_states）。"""
    from modules.handlers.temp_booking_handler import temp_booking_states  # lazy import
    if user_id in temp_booking_states:
        try:
            del temp_booking_states[user_id]
            _mirror_end_conversation(user_id)
            return True
        except Exception:
            return False
    return False
