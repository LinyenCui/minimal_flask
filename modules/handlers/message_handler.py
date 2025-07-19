# 消息處理模塊 - 處理消息前綴和按鈕點擊檢測
# 定義命令前綴列表，用於群組聊天
prefixes = ["!", "#", "/"]

from modules.config import COMMAND_PREFIXES
import re
import logging
from modules.handlers.temp_booking_handler import temp_booking_states
from modules.handlers.batch_allowance_handler import batch_allowance_states
from modules.utils.conversation_context import conversation_manager

logger = logging.getLogger(__name__)

# Known commands (exact match, case-insensitive)
KNOWN_COMMANDS = {
    "幫助", "幫助文字", 
    "預約叫車",      # This is our AI booking command
    "預約叫車幫助",  # Help for AI booking
    "東洋班次", "診所班次", "查已完成", "指派司機", "完成班次", "回報問題",
    "取消預約", "取消指派", "更新已完成班次", "取消AI修改",
    "確認修改", "取消修改",  # 🔥 新增：車資修改確認框回覆
    "fix-sequence",   # Database sequence repair command
    "批量加成", "batch-allowance",   # Batch allowance command
    "資料庫同步", "確認同步", "取消",   # Database sync and maintenance commands
    # 🔥 新增：分頁相關命令
    "更多", "下一頁", "更多結果", "next", "more"
}

# Commands that *can* take arguments
COMMANDS_WITH_ARGS = {
    "東洋班次", "診所班次", "查已完成", "班次詳情", "指派司機", "指派", 
    "記錄車資", "修改類別", "生成周報表", "生成週報表", "生成周報", "生成週報",
    "確認指派", "取消指派", "確認AI修改", "取消AI修改", "查看", "修改班次",
    "固定班次請假", "固定班次恢復",  # 固定班次請假相關命令
    "固定班表"  # 新增固定班表查詢命令（去掉前綴，因為前綴會被預處理掉）
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

    cancel_commands = ["取消", "取消預約", "cancel", "退出", "exit"]
    if user_id in temp_booking_states and not any(cmd in message_text.lower() for cmd in cancel_commands):
        if not any(message_text.startswith(f"{p}{cmd}") for p in ["!", "#", "/"] for cmd in cancel_commands):
            logger.info("[should_process] User in booking state, returning True")
            return True, message_text
    
    # 檢查用戶是否在批量加成狀態中
    if user_id in batch_allowance_states and not any(cmd in message_text.lower() for cmd in cancel_commands):
        if not any(message_text.startswith(f"{p}{cmd}") for p in ["!", "#", "/"] for cmd in cancel_commands):
            logger.info("[should_process] User in batch allowance state, returning True")
            return True, message_text
    
    # 🔥 新增：檢查用戶是否在活躍對話狀態中（如車資修改、請假等）
    if user_id in conversation_manager.active_conversations:
        active_conv = conversation_manager.active_conversations[user_id]
        if not active_conv.is_expired() and not active_conv.can_cancel_with(message_text):
            logger.info(f"[should_process] User in active conversation ({active_conv.conversation_type}), returning True")
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
             # 特殊處理「修改班次」指令，支持「修改班次#數字」格式
             if cmd_arg_original_case == "修改班次":
                  if command_body.startswith("修改班次#") or command_body.startswith("修改班次 "):
                       logger.info(f"[should_process] Group message matches '修改班次' pattern")
                       return True, command_body
             elif command_body.startswith(f"{cmd_arg_original_case} "):
                  logger.info(f"[should_process] Group message starts with command+arg pattern: '{cmd_arg_original_case}'")
                  return True, command_body
        
        # 特殊處理「固定班次#ID請假」格式
        if re.match(r"固定班次#\d+請假", command_body):
            logger.info(f"[should_process] Group message matches '固定班次#ID請假' pattern")
            return True, command_body 
                  
        logger.info("[should_process] Group/Room: Not a KNOWN command (already checked), mention, or command+arg pattern, ignoring.")
        return False, command_body 

    if source_type == "user":
        # 特殊處理「固定班次#ID請假」格式
        if re.match(r"固定班次#\d+請假", command_body):
            logger.info(f"[should_process] Private chat matches '固定班次#ID請假' pattern")
            return True, command_body
        
        logger.info("[should_process] Private chat and not a KNOWN command. Processing.")
        return True, command_body 
                
    logger.info("[should_process] Default: No processing rule matched, ignore.")
    return False, command_body 