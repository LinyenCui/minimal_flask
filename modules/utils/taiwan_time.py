"""
台灣時區工具模組 - 提供台灣時區相關的功能
"""
from datetime import datetime, timezone, timedelta, date

# 台灣時區功能
def get_taiwan_time():
    """獲取台灣時間（UTC+8）"""
    taiwan_tz = timezone(timedelta(hours=8))
    return datetime.now(taiwan_tz)

def get_taiwan_date():
    """獲取台灣日期"""
    return get_taiwan_time().date() 