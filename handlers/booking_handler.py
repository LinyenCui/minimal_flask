import re
from datetime import datetime, date, time
from linebot.v3.messaging import ReplyMessageRequest, TextMessage
from models import db
from sqlalchemy import text as sql_text

def handle_booking_conversation(event, user_id, message_text, user_states, messaging_api):
    """處理預約對話流程"""
    reply_token = event.reply_token
    current_step = user_states[user_id]['step']
    
    try:
        # 簡化版本，不進行實際處理
        reply_text = "這是預約功能的測試回覆。實際功能尚未完全實現。"
        
        # 清除用戶狀態
        if user_id in user_states:
            del user_states[user_id]
        
        # 發送回覆
        reply_message_request = ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=reply_text)]
        )
        messaging_api.reply_message(reply_message_request)
    
    except Exception as e:
        # 處理錯誤
        error_message = f"處理預約時發生錯誤: {str(e)}"
        reply_message_request = ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=error_message)]
        )
        messaging_api.reply_message(reply_message_request)
        
        # 清除用戶狀態
        if user_id in user_states:
            del user_states[user_id]

def parse_date(date_str):
    """解析各種日期格式"""
    date_str = date_str.strip()
    
    # 嘗試解析 YYYY-MM-DD 格式
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        pass
    
    # 嘗試解析 MM-DD 格式（假設當前年份）
    try:
        current_year = date.today().year
        parsed_date = datetime.strptime(date_str, "%m-%d").date()
        return parsed_date.replace(year=current_year)
    except ValueError:
        pass
    
    # 嘗試解析 MMDD 格式（假設當前年份）
    try:
        if len(date_str) == 4 and date_str.isdigit():
            month = int(date_str[:2])
            day = int(date_str[2:])
            current_year = date.today().year
            return date(current_year, month, day)
    except ValueError:
        pass
    
    # 如果所有格式都失敗，拋出異常
    raise ValueError("無法解析日期，請使用 YYYY-MM-DD 或 MM-DD 格式")

def parse_time(time_str):
    """解析各種時間格式"""
    time_str = time_str.strip()
    
    # 嘗試解析 HH:MM 格式
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        pass
    
    # 嘗試解析 HHMM 格式
    try:
        if len(time_str) == 4 and time_str.isdigit():
            hour = int(time_str[:2])
            minute = int(time_str[2:])
            return time(hour, minute)
    except ValueError:
        pass
    
    # 如果所有格式都失敗，拋出異常
    raise ValueError("無法解析時間，請使用 HH:MM 或 HHMM 格式") 