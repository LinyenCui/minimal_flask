# 消息處理模塊 - 處理消息前綴和按鈕點擊檢測
# 定義命令前綴列表，用於群組聊天
prefixes = ["!", "#", "/"]

from modules.config import COMMAND_PREFIXES
import re
import logging

logger = logging.getLogger(__name__)

def is_from_button(message_text):
    """
    檢查消息是否來自按鈕點擊
    目前沒有明確的方法區分，使用前綴作為近似判斷
    """
    # LINE按鈕點擊生成的消息通常會帶有前綴符號
    for prefix in prefixes:
        if message_text.startswith(prefix):
            return True
    return False

def should_process_message(message_text, source_type, user_id=None):
    logger.info(f"[should_process] Checking: '{message_text}' from {source_type}")
    
    # 0. Check if user is in booking state
    if user_id is not None:
        from modules.handlers.temp_booking_handler import temp_booking_states
        if user_id in temp_booking_states:
            logger.info("[should_process] User in booking state, returning True")
            # For booking state, we need the original message text
            return True, message_text
             
    # 1. Handle User messages directly
    if source_type == 'user':
        logger.info("[should_process] User source, returning True")
        return True, message_text
        
    # 2. Handle Group/Room messages
    if source_type in ['group', 'room']:
        logger.info("[should_process] Group/Room source")
        
        # 2a. Check mentions first (Optional: keep or remove based on preference)
        # Example: Check if mentioning the bot should trigger 'help'
        # if message_text.strip() == "機器人" or ("@" in message_text and any(bot_name in message_text for bot_name in ["機器人", "小黃", "小黄"])):
        #     logger.info("[should_process] Mention detected, returning True (Help)")
        #     return True, "幫助" # Trigger help on mention
        
        # 2b. Check for prefix
        processed_text = message_text
        for prefix in ["!", "#", "/"]:
            if message_text.startswith(prefix):
                processed_text = message_text[len(prefix):].strip() # Use len(prefix) for multi-char prefixes
                if processed_text:
                    logger.info(f"[should_process] Prefix '{prefix}' detected, returning True with '{processed_text}'")
                    return True, processed_text
                else:
                    # Handle case where only prefix is sent (e.g., "!")
                    logger.info(f"[should_process] Only prefix '{prefix}' found, returning False")
                    return False, message_text # Ignore message with only prefix
        
        # 2c. If NO prefix, check known commands (likely from Quick Replies)
        logger.info("[should_process] No prefix found, checking known commands...")
        # List of commands often triggered by buttons/quick replies that should work without prefix
        known_commands = [
            "查詢班次", "診所班次", "查已完成",
            # "預約", "東洋預約", # Might be too general? Consider triggering these with prefix?
            # "生成周報表", # Usually requires prefix
            "班次詳情", "幫助", "幫助文字",
            "臨時預約", "臨時預約幫助", # "取消預約" might be too general
            "取消", # Allow generic cancel from Quick Reply
            # "指派司機", "選擇司機", "確認指派", "取消指派", # Usually require arguments or prefix
            "記錄車資", "修改類別"
        ]
        # Add commands that START with known patterns, e.g., "班次詳情 123"
        known_command_patterns = [
             "班次詳情 ", # Note the space
             "查詢班次 ", # Note the space
             "診所班次 ", # Note the space
             "查已完成 ", # Note the space
             "修改狀態 ", # Note the space
             "記錄車資 ", # Note the space
             "確認取消 ", # Note the space
             "確認請假 ", # Note the space
             "確認衝突 ", # Note the space
             "修改類別 ", # Note the space
             # Driver related commands usually triggered by postback or have prefix,
             # but check if needed based on your Quick Reply design
             # "指派司機 ", "選擇司機 ", "確認指派 ", "取消指派 "
        ]

        exact_match = message_text in known_commands
        starts_with_match = any(message_text.startswith(pattern) for pattern in known_command_patterns)

        if exact_match or starts_with_match:
             logger.info(f"[should_process] Known command without prefix detected ('{message_text}'), returning True")
             # For these commands, the handler expects the full original text
             return True, message_text

        # 2d. If NO prefix and NOT a known command, DO NOT process
        logger.info("[should_process] No prefix and not a known command in Group/Room, returning False")
        return False, message_text # Ignore other non-prefixed messages
        
    # Default: should not happen, but return False just in case
    logger.warning(f"[should_process] Unknown source type or condition: {source_type}")
    return False, message_text 