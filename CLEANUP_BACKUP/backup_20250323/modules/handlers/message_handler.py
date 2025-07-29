# 消息處理模塊 - 處理消息前綴和按鈕點擊檢測
# 定義命令前綴列表，用於群組聊天
prefixes = ["!", "#", "/"]

from modules.config import COMMAND_PREFIXES

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

def should_process_message(message_text, source_type):
    """
    檢查是否應該處理這條消息
    
    params:
        message_text: 消息文本
        source_type: 消息來源類型 ('user', 'group', 'room')
    
    returns:
        (should_process, processed_text): 是否處理, 處理後的文本
    """
    # 私聊消息，總是處理
    if source_type == 'user':
        return True, message_text
        
    # 群組消息，需要前綴
    if source_type in ['group', 'room']:
        # 檢查是否是常見命令格式，這些通常是由按鈕觸發的
        button_commands = [
            "查詢班次", "預約", "東洋預約", "查詢固定班次", 
            "生成週報", "修改狀態", "班次詳情", "幫助", "幫助文字"
        ]
        
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