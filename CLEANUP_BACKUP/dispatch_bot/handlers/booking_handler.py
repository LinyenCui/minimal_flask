from linebot.v3.messaging import TextMessage, ReplyMessageRequest
from datetime import datetime, date

from ..utils.date_utils import parse_date_input, parse_time_input, is_past_date, is_past_time
from ..utils.db_utils import execute_query, commit

# 用戶狀態字典，用於跟踪對話狀態
user_states = {}

def start_booking(user_id, messaging_api, reply_token):
    """開始預約流程"""
    # 初始化預約狀態
    user_states[user_id] = {
        'state': 'booking',
        'step': 'date',
        'data': {
            'category': '東洋'  # 預設類別為"東洋"
        }
    }
    
    reply_text = "請輸入預約日期（格式：MM-DD 或 MM月DD日）："
    
    reply_message_request = ReplyMessageRequest(
        reply_token=reply_token,
        messages=[TextMessage(text=reply_text)]
    )
    
    messaging_api.reply_message(reply_message_request)

def handle_booking_conversation(event, user_id, message_text, messaging_api):
    """處理預約對話流程"""
    reply_token = event.reply_token
    current_step = user_states[user_id]['step']
    
    try:
        # 根據當前步驟處理用戶輸入
        if current_step == 'date':
            handle_date_step(user_id, message_text, messaging_api, reply_token)
        elif current_step == 'time':
            handle_time_step(user_id, message_text, messaging_api, reply_token)
        elif current_step == 'start_point':
            handle_start_point_step(user_id, message_text, messaging_api, reply_token)
        elif current_step == 'via_point':
            handle_via_point_step(user_id, message_text, messaging_api, reply_token)
        elif current_step == 'end_point':
            handle_end_point_step(user_id, message_text, messaging_api, reply_token)
        elif current_step == 'confirm':
            handle_confirm_step(user_id, message_text, messaging_api, reply_token)
    
    except Exception as e:
        # 發生錯誤，清除用戶狀態並發送錯誤消息
        del user_states[user_id]
        
        error_text = f"預約過程中發生錯誤: {str(e)}\n請重新開始預約流程。"
        
        reply_message_request = ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=error_text)]
        )
        
        messaging_api.reply_message(reply_message_request)

def handle_date_step(user_id, message_text, messaging_api, reply_token):
    """處理日期輸入步驟"""
    try:
        # 嘗試解析各種日期格式
        input_date = parse_date_input(message_text)
        
        # 檢查是否為過去的日期
        if is_past_date(input_date):
            # 如果是過去的日期，嘗試使用明年的同一天
            today = date.today()
            if input_date.replace(year=today.year + 1) > today:
                input_date = input_date.replace(year=today.year + 1)
            else:
                raise ValueError("不能預約過去的日期")
        
        user_states[user_id]['data']['date'] = input_date
        user_states[user_id]['step'] = 'time'
        reply_text = "請輸入預約時間（格式：HH:MM 或 HHMM）："
    except ValueError as e:
        reply_text = f"日期格式不正確或日期無效: {str(e)}\n請使用以下格式之一：\n- MM-DD（例如：03-15）\n- MM月DD日（例如：3月15日）\n- MMDD（例如：0315）"
    
    reply_message_request = ReplyMessageRequest(
        reply_token=reply_token,
        messages=[TextMessage(text=reply_text)]
    )
    
    messaging_api.reply_message(reply_message_request)

# ... 其他步驟處理函數 ... 