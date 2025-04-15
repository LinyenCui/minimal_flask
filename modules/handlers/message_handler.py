# 消息處理模塊 - 處理消息前綴和按鈕點擊檢測
# 定義命令前綴列表，用於群組聊天
prefixes = ["!", "#", "/"]

from modules.config import COMMAND_PREFIXES
import re

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
    """
    檢查是否應該處理這條消息
    
    params:
        message_text: 消息文本
        source_type: 消息來源類型 ('user', 'group', 'room')
        user_id: 用戶ID，用於檢查是否在臨時預約流程中
    
    returns:
        (should_process, processed_text): 是否處理, 處理後的文本
    """
    # 如果有提供用戶ID，檢查是否在臨時預約流程中
    if user_id is not None:
        from modules.handlers.temp_booking_handler import temp_booking_states
        if user_id in temp_booking_states:
            # 用戶在臨時預約流程中，直接處理
            return True, message_text
    
    # 私聊消息，總是處理
    if source_type == 'user':
        return True, message_text
        
    # 群組消息，需要前綴
    if source_type in ['group', 'room']:
        # 檢查是否是用戶提及機器人
        if message_text.strip() == "機器人":
            # 返回特殊命令「幫助」，使機器人顯示幫助菜單
            return True, "幫助"
        # 檢查是否有人@機器人 (通常會包含像 @機器人 或 @小黃機器人 這樣的文本)
        if "@" in message_text and any(bot_name in message_text for bot_name in ["機器人", "小黃", "小黄"]):
            return True, "幫助"
            
        # 檢查是否是常見命令格式，這些通常是由按鈕觸發的
        button_commands = [
            "查詢班次", "預約", "東洋預約", "查詢固定班次", 
            "生成週報", "修改狀態", "班次詳情", "幫助", "幫助文字",
            "臨時預約", "臨時預約幫助", "取消預約",
            "指派司機", "選擇司機", "確認指派", "取消指派"
        ]
        
        # 檢查是否是臨時預約流程中的常用輸入格式
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'  # 如 2025-04-16
        time_pattern = r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$'  # 如 09:30
        shorthand_time_pattern = r'^\d{3,4}$'  # 如 930 或 1430
        special_date_inputs = ["今天", "明天", "後天"]
        confirm_inputs = ["確認", "confirm", "yes", "是", "確定", "ok"]
        cancel_inputs = ["取消", "取消預約", "cancel", "退出", "exit"]
        
        # 檢查司機指派相關輸入格式
        driver_assign_pattern = r'^指派司機\s+\d+$'  # 如 "指派司機 2307"
        driver_select_pattern = r'^指派司機\s+\d+\s+\d+$'  # 如 "指派司機 2307 123"
        driver_confirm_pattern = r'^確認指派\s+\d+\s+\d+$'  # 如 "確認指派 2307 123"
        driver_cancel_pattern = r'^取消指派\s+\d+$'  # 如 "取消指派 2307"
        
        # 簡化的班次指派指令
        simplified_assign_pattern = r'^指派\s+\d+$'  # 如 "指派 2307" 或 "指派司機"
        
        # 添加位置相關文本識別（這是一個啟發式方法）
        # 這些是可能的位置關鍵詞，任何包含這些關鍵詞的文本都可能是位置輸入
        location_keywords = [
            "路", "街", "巷", "弄", "號", "樓", "台", "臺", "区", "區", "鎮", "鄉", "村", 
            "大樓", "大廈", "社區", "小區", "廣場", "公園", "站", "市場", "中心", "學校", 
            "醫院", "飯店", "酒店", "賓館", "捷運", "公司", "車站", "南", "北", "東", "西"
        ]
        
        # 檢查是否是日期、時間、確認等臨時預約流程中的輸入
        is_booking_input = (
            re.match(date_pattern, message_text) or 
            re.match(time_pattern, message_text) or
            re.match(shorthand_time_pattern, message_text) or
            message_text in special_date_inputs or
            message_text in confirm_inputs or
            message_text in cancel_inputs or
            message_text == "無(略過)" or
            # 檢查是否包含位置關鍵詞
            any(keyword in message_text for keyword in location_keywords) or
            # 檢查司機指派相關命令
            re.match(driver_assign_pattern, message_text) or
            re.match(driver_select_pattern, message_text) or
            re.match(driver_confirm_pattern, message_text) or
            re.match(driver_cancel_pattern, message_text) or
            re.match(simplified_assign_pattern, message_text)
        )
        
        # 如果是臨時預約相關輸入，直接處理
        if is_booking_input:
            return True, message_text
        
        # 檢查前綴
        has_prefix = False
        processed_text = message_text
        
        for prefix in ["!", "#", "/"]:
            if message_text.startswith(prefix):
                processed_text = message_text[1:].strip()
                if processed_text:  # 確保不是空消息
                    has_prefix = True
                    break
        
        # 檢查是否是按鈕命令
        is_button_command = False
        for cmd in button_commands:
            if processed_text == cmd or processed_text.startswith(f"{cmd} "):
                is_button_command = True
                break
        
        # 在群組中，必須要么有前綴，要么是常見按鈕命令
        if has_prefix and is_button_command:
            return True, processed_text
        elif has_prefix:
            # 有前綴但不是按鈕命令，也可以處理
            return True, processed_text
        elif is_button_command and not has_prefix:
            # 是按鈕命令但没有前綴，這裡要判斷是否確實來自按鈕點擊
            # 簡單的判斷方式：檢查消息是否完全匹配某個按鈕命令
            # 對於"班次詳情 123"這樣的命令，允許處理
            return True, processed_text
                
    # 默認不處理
    return False, message_text 