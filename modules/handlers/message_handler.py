# 消息處理模塊 - 處理消息前綴和按鈕點擊檢測
# 定義命令前綴列表，用於群組聊天
prefixes = ["!", "#", "/"]

from modules.config import COMMAND_PREFIXES
import re
import logging
from modules.handlers.temp_booking_handler import temp_booking_states

logger = logging.getLogger(__name__)

# Known commands (exact match, case-insensitive)
KNOWN_COMMANDS = {
    "幫助", "幫助文字", 
    "預約叫車",      # This is our AI booking command
    "預約叫車幫助",  # Help for AI booking
    "查詢班次", "診所班次", "查已完成", "指派司機", "完成班次", "回報問題",
    "取消預約", "取消指派", "更新已完成班次"
}

# Commands that *can* take arguments
COMMANDS_WITH_ARGS = {
    "查詢班次", "診所班次", "查已完成", "班次詳情", "指派司機", "指派", 
    "記錄車資", "修改類別", "生成周報表", "生成週報表", "生成周報", "生成週報",
    "確認指派", "取消指派"
}

def is_from_button(message_text):
    """
    檢查消息是否來自按鈕點擊
    目前沒有明確的方法區分, 使用前綴作為近似判斷
    """
    # LINE按鈕點擊生成的消息通常會帶有前綴符號
    for prefix in prefixes:
        if message_text.startswith(prefix):
            return True
    return False

def should_process(message_text, source_type, user_id):
    logger.info(f"[should_process] Checking: '{message_text}' from {source_type}")

    if message_text == "@CANCEL_DRIVER_ASSIGN@":
        logger.info("[should_process] Internal cancel command detected, returning True")
        return True, message_text

    from modules.handlers.temp_booking_handler import temp_booking_states
    cancel_commands = ["取消", "取消預約", "cancel", "退出", "exit"]
    if user_id in temp_booking_states and not any(cmd in message_text.lower() for cmd in cancel_commands):
        if not any(message_text.startswith(f"{p}{cmd}") for p in ["!", "#", "/"] for cmd in cancel_commands):
             logger.info("[should_process] User in booking state, returning True")
             return True, message_text 

    prefix = None
    command_body = message_text 
    for p in ["!", "#", "/"]:
        if message_text.startswith(p):
            prefix = p
            command_body = message_text[len(prefix):].strip()
            logger.info(f"[should_process] Prefix '{prefix}' found, command body: '{command_body}'")
            if command_body: return True, command_body 
            else: 
                 logger.info("[should_process] Prefix found but command body is empty, ignoring.")
                 return False, message_text 

    logger.info(f"[should_process] No prefix or prefix stripped, evaluating: '{command_body}'")
    command_lower = command_body.strip().lower()
    
    # --- PRIORITY 1: Exact match for KNOWN_COMMANDS (case-insensitive) --- 
    matched_known_command = None
    for known_cmd_original_case in KNOWN_COMMANDS:
        if known_cmd_original_case.lower() == command_lower:
            matched_known_command = known_cmd_original_case 
            break
    if matched_known_command:
        logger.info(f"[should_process] Exact match for KNOWN command: '{matched_known_command}'")
        return True, matched_known_command
    # --- END KNOWN_COMMANDS CHECK --- 

    if source_type in ["group", "room"]:
        bot_names = ["機器人", "小黃", "小黄"]
        if command_body.strip() in bot_names or ("@" in command_body and any(f"@{name}" in command_body for name in bot_names)):
            logger.info("[should_process] Mention detected, treating as '幫助'")
            return True, "幫助"
            
        logger.info("[should_process] Group: Checking for commands with args pattern...")
        for cmd_arg_original_case in COMMANDS_WITH_ARGS:
             if command_body.startswith(f"{cmd_arg_original_case} "):
                  logger.info(f"[should_process] Group message starts with command+arg pattern: '{cmd_arg_original_case}'")
                  return True, command_body 
                  
        logger.info("[should_process] Group/Room: Not a KNOWN command (already checked), mention, or command+arg pattern, ignoring.")
        return False, command_body 

    if source_type == "user":
        logger.info("[should_process] Private chat and not a KNOWN command. Processing.")
        return True, command_body 

    logger.info("[should_process] Default: No processing rule matched, ignore.")
    return False, command_body 