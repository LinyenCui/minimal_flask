"""
通用工具函數模組
"""
import re
from modules.config import COMMAND_PREFIXES
from datetime import datetime, timedelta, date, timezone
from sqlalchemy import Row
import logging

logger = logging.getLogger(__name__)

# 台灣時區功能
def get_taiwan_time():
    """獲取台灣時間（UTC+8）"""
    taiwan_tz = timezone(timedelta(hours=8))
    return datetime.now(taiwan_tz)

def get_taiwan_date():
    """獲取台灣日期"""
    return get_taiwan_time().date()

# 用戶狀態字典，用於跟踪對話狀態
user_states = {}

# 預約狀態字典
booking_states = {}

def remove_prefix(text):
    """移除消息前綴"""
    for prefix in COMMAND_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix):]
    return text

def is_group_chat(source):
    """檢查是否為群組聊天"""
    return source.type == "group" or source.type == "room"

def get_user_id(source):
    """從source獲取用戶ID"""
    return source.user_id if hasattr(source, 'user_id') else None

def set_user_state(user_id, state, data=None):
    """設置用戶狀態"""
    if data is None:
        data = {}
    user_states[user_id] = {"state": state, "data": data}

def get_user_state(user_id):
    """獲取用戶狀態"""
    return user_states.get(user_id, {}).get("state", None)

def get_user_data(user_id):
    """獲取用戶數據"""
    return user_states.get(user_id, {}).get("data", {})

def clear_user_state(user_id):
    """清除用戶狀態"""
    if user_id in user_states:
        del user_states[user_id]

def extract_command_args(text):
    """從文本中提取命令和參數"""
    parts = text.strip().split()
    if not parts:
        return None, []
    command = parts[0]
    args = parts[1:] if len(parts) > 1 else []
    return command, args

def validate_date_format(date_str):
    """驗證日期格式 (YYYY-MM-DD)"""
    pattern = r"^\d{4}-\d{2}-\d{2}$"
    return bool(re.match(pattern, date_str))

def validate_time_format(time_str):
    """驗證時間格式 (HH:MM)"""
    pattern = r"^\d{1,2}:\d{2}$"
    return bool(re.match(pattern, time_str))

def get_weekday_name(date):
    """取得星期名稱（中文）"""
    weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
    return weekday_names[date.weekday()]

def format_date(date_obj):
    """格式化日期為 MM/DD (星期X)"""
    weekday = get_weekday_name(date_obj)
    return f"{date_obj.month}/{date_obj.day} (星期{weekday})"

def format_time(time_obj):
    """格式化時間為 HH:MM"""
    return time_obj.strftime("%H:%M")

def parse_date(date_str):
    """解析日期字符串（YYYY-MM-DD）"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None

def parse_time_input(time_str):
    """解析各種格式的時間輸入 (HH:MM, HHMM) 並返回 time 對象"""
    time_str = time_str.strip()
    
    # 嘗試 HH:MM 格式
    if re.match(r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$", time_str):
        try:
            return datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            pass # 繼續嘗試其他格式
            
    # 嘗試 HHMM 格式
    elif re.match(r'^\d{3,4}$', time_str):
        if len(time_str) == 3: # 補零，例如 930 -> 09:30
             formatted_time = f"0{time_str[0]}:{time_str[1:3]}"
        else: # 1405 -> 14:05
             formatted_time = f"{time_str[0:2]}:{time_str[2:4]}"
        try:
            return datetime.strptime(formatted_time, "%H:%M").time()
        except ValueError:
            pass # 繼續嘗試其他格式

    # (可選) 處理 早上/下午 等模糊時間？ 暫不處理
    # elif time_str == "早上":
    #     return datetime.strptime("09:00", "%H:%M").time() # Example
    # elif time_str == "下午":
    #     return datetime.strptime("14:00", "%H:%M").time() # Example
            
    # 無法識別的格式
    raise ValueError(f"無法識別的時間格式: {time_str}")

def generate_unique_code(trip_id, date_obj, fixed_trip_id=None):
    """生成班次的唯一識別碼，使用一年中的第幾天和第幾周"""
    # 計算一年中的第幾天（1-366）
    day_of_year = date_obj.timetuple().tm_yday
    
    # 計算一年中的第幾周
    _, week_number, _ = date_obj.isocalendar()
    
    if fixed_trip_id:
        # 固定班次：固定班次ID_太陽日_周數
        return f"{fixed_trip_id}_{day_of_year}_{week_number}"
    else:
        # 臨時班次：T_班次ID
        return f"T_{trip_id}"

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
        # 檢查前綴
        for prefix in COMMAND_PREFIXES:
            if message_text.startswith(prefix):
                # 去除前綴
                processed_text = message_text[len(prefix):].strip()
                if processed_text:  # 確保消息不僅僅是前綴
                    return True, processed_text
                
    # 默認不處理
    return False, message_text 

def parse_date_input(date_input):
    """解析各種格式的日期輸入"""
    
    today = get_taiwan_date()
    current_year = today.year
    
    # 嘗試解析完整日期格式 (YYYY-MM-DD)
    if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', date_input):
        return datetime.strptime(date_input, "%Y-%m-%d").date()
    
    # 嘗試解析簡短日期格式 (MM-DD)
    elif re.match(r'^\d{1,2}-\d{1,2}$', date_input):
        month, day = map(int, date_input.split('-'))
        try:
            parsed_date = date(current_year, month, day)
            # 如果日期已過去超過30天，假設是明年的日期
            days_difference = (today - parsed_date).days
            if days_difference > 30:
                parsed_date = date(current_year + 1, month, day)
            return parsed_date
        except ValueError as e:
            raise ValueError(f"无效的日期: {month}-{day}")
    
    # 嘗試解析斜線日期格式 (MM/DD)
    elif re.match(r'^\d{1,2}/\d{1,2}$', date_input):
        month, day = map(int, date_input.split('/'))
        try:
            parsed_date = date(current_year, month, day)
            # 如果日期已過去超過30天，假設是明年的日期
            days_difference = (today - parsed_date).days
            if days_difference > 30:
                parsed_date = date(current_year + 1, month, day)
            return parsed_date
        except ValueError as e:
            raise ValueError(f"无效的日期: {month}/{day}")
    
    # 嘗試解析中文日期格式 (MM月DD日)
    elif re.match(r'^\d{1,2}月\d{1,2}日$', date_input):
        month, day = map(int, re.findall(r'\d+', date_input))
        try:
            parsed_date = date(current_year, month, day)
            # 如果日期已過去超過30天，假設是明年的日期
            days_difference = (today - parsed_date).days
            if days_difference > 30:
                parsed_date = date(current_year + 1, month, day)
            return parsed_date
        except ValueError as e:
            raise ValueError(f"无效的日期: {month}月{day}日")
    
    # 嘗試解析數字日期格式 (MMDD)
    elif re.match(r'^\d{3,4}$', date_input):
        if len(date_input) == 3:  # 例如 "125" 表示 1月25日
            month = int(date_input[0])
            day = int(date_input[1:3])
        else:  # 例如 "0125" 表示 1月25日
            month = int(date_input[0:2])
            day = int(date_input[2:4])
        try:
            parsed_date = date(current_year, month, day)
            # 如果日期已過去超過30天，假設是明年的日期
            days_difference = (today - parsed_date).days
            if days_difference > 30:
                parsed_date = date(current_year + 1, month, day)
            return parsed_date
        except ValueError as e:
            raise ValueError(f"无效的日期: {month:02d}{day:02d}")
    
    # 嘗試解析星期幾 (一, 二, 三, 四, 五, 六, 日)
    elif date_input in ['一', '二', '三', '四', '五', '六', '日']:
        weekday_map = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6}
        target_weekday = weekday_map[date_input]
        current_weekday = today.weekday()
        
        # 計算到目標星期幾的天數
        days_ahead = (target_weekday - current_weekday) % 7
        if days_ahead == 0:
            days_ahead = 7  # 如果是同一天，則取下一周的同一天
        
        return today + timedelta(days=days_ahead)
    
    # 嘗試解析相對日期 ("今天", "明天", "後天")
    elif date_input == "今天":
        return today
    elif date_input == "明天":
        return today + timedelta(days=1)
    elif date_input == "後天":
        return today + timedelta(days=2)
    
    # 無法識別的格式
    else:
        raise ValueError("無法識別的日期格式") 

# Helper function to convert Row to dict
def row_to_dict(row: Row) -> dict | None:
    """將 SQLAlchemy Row 對象轉換為字典，處理可能的 None。"""
    if row is None:
        return None
    # SQLAlchemy 1.4+ 使用 ._mapping
    if hasattr(row, '_mapping'):
        return dict(row._mapping)
    else:
        # 嘗試直接轉換，適用於某些情況
        try: 
           return dict(row)
        except TypeError:
           logger.error(f"Could not convert row to dict: {row}")
           return None 
