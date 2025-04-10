import re
from datetime import datetime, timedelta, date, timezone

def parse_date_input(date_input):
    """解析各種格式的日期輸入"""
    # 嘗試解析完整日期格式 (YYYY-MM-DD)
    if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', date_input):
        return datetime.strptime(date_input, "%Y-%m-%d").date()
    
    # 嘗試解析簡短日期格式 (MM-DD)
    elif re.match(r'^\d{1,2}-\d{1,2}$', date_input):
        current_year = datetime.now().year
        return datetime.strptime(f"{current_year}-{date_input}", "%Y-%m-%d").date()
    
    # 嘗試解析中文日期格式 (MM月DD日)
    elif re.match(r'^\d{1,2}月\d{1,2}日$', date_input):
        month, day = re.findall(r'\d+', date_input)
        current_year = datetime.now().year
        return datetime.strptime(f"{current_year}-{month}-{day}", "%Y-%m-%d").date()
    
    # 嘗試解析數字日期格式 (MMDD)
    elif re.match(r'^\d{3,4}$', date_input):
        if len(date_input) == 3:  # 例如 "125" 表示 1月25日
            month = date_input[0]
            day = date_input[1:3]
        else:  # 例如 "0125" 表示 1月25日
            month = date_input[0:2]
            day = date_input[2:4]
        current_year = datetime.now().year
        return datetime.strptime(f"{current_year}-{month}-{day}", "%Y-%m-%d").date()
    
    # 無法識別的格式
    else:
        raise ValueError("無法識別的日期格式")

def parse_time_input(time_input):
    """解析各種格式的時間輸入"""
    # 嘗試解析時間格式 (HH:MM)
    if re.match(r'^\d{1,2}:\d{1,2}$', time_input):
        return datetime.strptime(time_input, "%H:%M").time()
    
    # 嘗試解析簡短時間格式 (HHMM)
    elif re.match(r'^\d{3,4}$', time_input):
        if len(time_input) == 3:  # 例如 "930" 表示 9:30
            hour = time_input[0]
            minute = time_input[1:3]
        else:  # 例如 "0930" 表示 9:30
            hour = time_input[0:2]
            minute = time_input[2:4]
        return datetime.strptime(f"{hour}:{minute}", "%H:%M").time()
    
    # 無法識別的格式
    else:
        raise ValueError("無法識別的時間格式")

# 台灣時區功能
def get_taiwan_time():
    """獲取台灣時間（UTC+8）"""
    taiwan_tz = timezone(timedelta(hours=8))
    return datetime.now(taiwan_tz)

def get_taiwan_date():
    """獲取台灣日期"""
    return get_taiwan_time().date()

def is_past_date(check_date):
    """檢查是否為過去的日期"""
    return check_date < get_taiwan_date()

def is_past_time(check_date, check_time):
    """檢查是否為過去的時間"""
    today = get_taiwan_date()
    now = get_taiwan_time().time()
    return check_date == today and check_time < now 