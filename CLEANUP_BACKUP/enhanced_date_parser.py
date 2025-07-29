"""
增強日期解析器
支持多種日期格式和自然語言日期表達
"""

import re
from datetime import datetime, date, timedelta
from typing import Tuple, Optional
from modules.utils.taiwan_time import get_taiwan_date

def parse_date_enhanced(date_string: str, context: str = 'general') -> Tuple[Optional[date], str]:
    """
    增強日期解析函數
    
    Args:
        date_string: 輸入的日期字符串
        context: 解析上下文 ('general', 'fare_query', 'schedule')
    
    Returns:
        (parsed_date, confidence) - 解析的日期和信心度 ('high', 'medium', 'low')
    """
    if not date_string:
        return None, 'low'
    
    date_string = str(date_string).strip()
    today = get_taiwan_date()
    
    # 相對日期 - 高信心度
    relative_patterns = {
        '今天': (today, 'high'),
        '今日': (today, 'high'),
        '昨天': (today - timedelta(days=1), 'high'),
        '昨日': (today - timedelta(days=1), 'high'),
        '前天': (today - timedelta(days=2), 'high'),
        '明天': (today + timedelta(days=1), 'high'),
        '明日': (today + timedelta(days=1), 'high'),
        '後天': (today + timedelta(days=2), 'high'),
        '大後天': (today + timedelta(days=3), 'high')
    }
    
    for pattern, (target_date, confidence) in relative_patterns.items():
        if pattern in date_string:
            return target_date, confidence
    
    # 星期幾 - 中等信心度
    weekday_patterns = {
        '星期一': 0, '周一': 0, '一': 0,
        '星期二': 1, '周二': 1, '二': 1,
        '星期三': 2, '周三': 2, '三': 2,
        '星期四': 3, '周四': 3, '四': 3,
        '星期五': 4, '周五': 4, '五': 4,
        '星期六': 5, '周六': 5, '六': 5,
        '星期日': 6, '周日': 6, '日': 6
    }
    
    for pattern, target_weekday in weekday_patterns.items():
        if pattern in date_string:
            days_ahead = target_weekday - today.weekday()
            if days_ahead <= 0:  # 如果是過去的星期幾，指向下周
                days_ahead += 7
            target_date = today + timedelta(days=days_ahead)
            return target_date, 'medium'
    
    # 具體日期格式
    date_patterns = [
        # YYYY-MM-DD 格式 - 高信心度
        (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', 'high', lambda m: date(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
        
        # MM-DD 格式 - 高信心度
        (r'(\d{1,2})[-/](\d{1,2})', 'high', lambda m: date(today.year, int(m.group(1)), int(m.group(2)))),
        
        # 中文日期格式 - 高信心度
        (r'(\d{1,2})月(\d{1,2})日?', 'high', lambda m: date(today.year, int(m.group(1)), int(m.group(2)))),
        
        # MMDD 格式 (4位數字) - 中等信心度
        (r'^(\d{2})(\d{2})$', 'medium', lambda m: date(today.year, int(m.group(1)), int(m.group(2)))),
        
        # MDD 格式 (3位數字) - 低信心度
        (r'^(\d{1})(\d{2})$', 'low', lambda m: date(today.year, int(m.group(1)), int(m.group(2))))
    ]
    
    for pattern, confidence, date_func in date_patterns:
        match = re.match(pattern, date_string)
        if match:
            try:
                parsed_date = date_func(match)
                # 檢查日期是否合理
                if parsed_date.year < 2020 or parsed_date.year > 2030:
                    continue
                return parsed_date, confidence
            except (ValueError, IndexError):
                continue
    
    # 純數字日期 (當天) - 針對特殊情況
    if date_string.isdigit():
        num = int(date_string)
        
        # 如果是1-31的數字，可能是當月的某一天
        if 1 <= num <= 31:
            try:
                target_date = date(today.year, today.month, num)
                return target_date, 'low'
            except ValueError:
                pass
        
        # 如果是4位數，嘗試MMDD格式
        if 100 <= num <= 1231:
            month = num // 100
            day = num % 100
            if 1 <= month <= 12 and 1 <= day <= 31:
                try:
                    target_date = date(today.year, month, day)
                    return target_date, 'medium'
                except ValueError:
                    pass
    
    # 解析失敗
    return None, 'low'

def parse_time_enhanced(time_string: str) -> Optional[tuple]:
    """
    增強時間解析函數
    
    Returns:
        (hour, minute) 或 None
    """
    if not time_string:
        return None
    
    time_string = str(time_string).strip()
    
    # 標準時間格式
    time_patterns = [
        r'(\d{1,2}):(\d{2})',  # HH:MM
        r'(\d{1,2})點(\d{1,2})分?',  # X點Y分
        r'(\d{1,2})時(\d{1,2})分?',  # X時Y分
        r'(\d{1,2})[點時]',  # X點/X時
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, time_string)
        if match:
            try:
                if len(match.groups()) == 2:
                    hour = int(match.group(1))
                    minute = int(match.group(2))
                else:
                    hour = int(match.group(1))
                    minute = 0
                
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return (hour, minute)
            except (ValueError, IndexError):
                continue
    
    return None

def get_date_range_enhanced(query: str) -> Tuple[Optional[date], Optional[date]]:
    """
    從查詢中提取日期範圍
    
    Returns:
        (start_date, end_date) 或 (None, None)
    """
    range_patterns = [
        r'(\S+)到(\S+)',
        r'(\S+)至(\S+)',
        r'(\S+)-(\S+)',
        r'從(\S+)到(\S+)'
    ]
    
    for pattern in range_patterns:
        match = re.search(pattern, query)
        if match:
            start_str = match.group(1)
            end_str = match.group(2)
            
            start_date, _ = parse_date_enhanced(start_str)
            end_date, _ = parse_date_enhanced(end_str)
            
            if start_date and end_date:
                return start_date, end_date
    
    return None, None 