# 消息處理模塊 - 處理消息前綴和按鈕點擊檢測
# 定義命令前綴列表，用於群組聊天
prefixes = ["!", "#", "/"]

from modules.config import COMMAND_PREFIXES
import re
import logging

logger = logging.getLogger(__name__)

# Known commands (exact match, case-insensitive)
KNOWN_COMMANDS = {
    "幫助", 
    "幫助文字", 
    # "臨時預約", # Removed
    # "臨時預約幫助", # Removed
    "AI叫車",     # Added
    # "Bot叫車",    # We'll use the step-by-step fallback from AI for now
    # "AI叫車幫助", 
    # "Bot叫車幫助",
    "查詢班次",     
    "診所班次",     
    "查已完成",     
    "指派司機",     
    "完成班次",
    "回報問題",
    "取消預約",     
    "取消指派",     
    "更新已完成班次"
}

# Commands that *can* take arguments
COMMANDS_WITH_ARGS = {
    "查詢班次",
    "診所班次",
    "查已完成",
    "班次詳情",
    "指派司機", 
    "指派",     
    "記錄車資",
    "修改類別",
    "生成周報表", 
    "生成週報表", 
    "生成周報",   
    "生成週報",
    "確認指派", 
    "取消指派"  
}

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
            return True, message_text
             
    # 1. Handle User messages directly
    if source_type == 'user':
        logger.info("[should_process] User source, returning True")
        return True, message_text
        
    # 2. Handle Group/Room messages
    if source_type in ['group', 'room']:
        logger.info("[should_process] Group/Room source")
        
        # 2a. Check mentions first
        if message_text.strip() == "機器人" or ("@" in message_text and any(bot_name in message_text for bot_name in ["機器人", "小黃", "小黄"])):
            logger.info("[should_process] Mention detected, returning True (Help)")
            return True, "幫助"
        
        # 2b. Check for prefix
        processed_text = message_text
        for prefix in ["!", "#", "/"]:
            if message_text.startswith(prefix):
                processed_text = message_text[1:].strip()
                if processed_text: 
                    logger.info(f"[should_process] Prefix '{prefix}' detected, returning True with '{processed_text}'")
                    return True, processed_text 
                else:
                    logger.info(f"[should_process] Only prefix '{prefix}' found, returning False")
                    return False, message_text
        
        # 2c. If NO prefix, check known button/text commands
        logger.info("[should_process] No prefix found, checking known commands...")
        button_commands = [
            "查詢班次", "診所班次", "查已完成",
            "預約", "東洋預約", 
            "生成周報表",
            "班次詳情", "幫助", "幫助文字",
            "取消預約",
            "指派司機", "選擇司機", "確認指派", "取消指派",
            "記錄車資", "修改類別"
        ]
        for cmd in button_commands:
            match = False
            if message_text == cmd:
                match = True
                logger.info(f"[should_process] Exact match for command: '{cmd}'")
            elif message_text.startswith(f"{cmd} "):
                 match = True
                 logger.info(f"[should_process] Starts with command: '{cmd} '")
                 
            if match:
                 # For commands, return the original text, let handler parse args
                 logger.info(f"[should_process] Command match, returning True with original text '{message_text}'")
                 return True, message_text
                 
        # 2d. If NO prefix and NOT a known command, THEN check for booking input patterns
        logger.info("[should_process] Not a known command, checking booking patterns...")
        # ... (Define date_pattern, time_pattern, location_keywords etc. as before) ...
        date_pattern = r'^\d{4}-\d{2}-\d{2}$' 
        time_pattern = r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$'
        shorthand_time_pattern = r'^\d{3,4}$' 
        special_date_inputs = ["今天", "明天", "後天"]
        confirm_inputs = ["確認", "confirm", "yes", "是", "確定", "ok"]
        cancel_inputs = ["取消", "取消預約", "cancel", "退出", "exit"]
        location_keywords = ["路", "街", "巷", "弄", "號", "樓", "台", "臺", "区", "區", "鎮", "鄉", "村", "大樓", "大廈", "社區", "小區", "廣場", "公園", "站", "市場", "中心", "學校", "醫院", "飯店", "酒店", "賓館", "捷運", "公司", "車站", "南", "北", "東", "西"]
        driver_assign_pattern = r'^指派司機\s+\d+$'
        driver_select_pattern = r'^指派司機\s+\d+\s+\d+$'
        driver_confirm_pattern = r'^確認指派\s+\d+\s+\d+$'
        driver_cancel_pattern = r'^取消指派\s+\d+$'
        simplified_assign_pattern = r'^指派\s+\d+$'
        is_booking_input = (
            re.match(date_pattern, message_text) or 
            re.match(time_pattern, message_text) or
            re.match(shorthand_time_pattern, message_text) or
            message_text in special_date_inputs or
            message_text in confirm_inputs or
            message_text in cancel_inputs or
            message_text == "無(略過)" or
            any(keyword in message_text for keyword in location_keywords) or
            re.match(driver_assign_pattern, message_text) or # Keep driver assign checks here or move to known commands?
            re.match(driver_select_pattern, message_text) or
            re.match(driver_confirm_pattern, message_text) or
            re.match(driver_cancel_pattern, message_text) or
            re.match(simplified_assign_pattern, message_text)
        )
        if is_booking_input:
             logger.info("[should_process] Booking input pattern detected, returning True")
             return True, message_text # Return original text for booking handler
             
        # 5. If none of the above, skip
        logger.info("[should_process] No match found, returning False")
        return False, message_text
                
    logger.info("[should_process] Default return False (source type unknown?)")
    return False, message_text 