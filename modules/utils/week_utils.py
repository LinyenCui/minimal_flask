"""
太陽周次計算工具模組
提供以周日為開始的周次計算功能
"""
from datetime import date, timedelta
from typing import Tuple, List
import logging

logger = logging.getLogger(__name__)

def get_sunday_week_start(target_date: date) -> date:
    """
    獲取指定日期所在太陽周的開始日期（周日）
    
    Args:
        target_date: 目標日期
        
    Returns:
        該周的周日日期
    """
    # Python weekday(): Monday=0, Sunday=6
    # 我們需要計算到周日的天數
    days_since_sunday = target_date.weekday() + 1 if target_date.weekday() < 6 else 0
    week_start = target_date - timedelta(days=days_since_sunday)
    return week_start

def get_week_dates(week_start: date) -> List[date]:
    """
    獲取從周日開始的一周七天日期
    
    Args:
        week_start: 周日日期
        
    Returns:
        周日到周六的日期列表
    """
    return [week_start + timedelta(days=i) for i in range(7)]

def get_week_info(target_date: date) -> Tuple[date, List[date], str]:
    """
    獲取指定日期的周次信息
    
    Args:
        target_date: 目標日期
        
    Returns:
        (周日日期, 周日到周六日期列表, 周次描述)
    """
    week_start = get_sunday_week_start(target_date)
    dates = get_week_dates(week_start)
    week_end = dates[6]  # 周六
    
    # 格式化周次描述
    week_desc = f"{week_start.month}/{week_start.day}-{week_end.month}/{week_end.day}"
    
    return week_start, dates, week_desc

def calculate_target_week(base_date: date, week_offset: int) -> Tuple[date, List[date], str]:
    """
    計算目標周次
    
    Args:
        base_date: 基準日期（通常是今天）
        week_offset: 周次偏移（0=本周, 1=下周, -1=上周）
        
    Returns:
        (周日日期, 周日到周六日期列表, 周次描述)
    """
    base_week_start = get_sunday_week_start(base_date)
    target_week_start = base_week_start + timedelta(weeks=week_offset)
    
    dates = get_week_dates(target_week_start)
    week_end = dates[6]
    
    # 格式化周次描述
    week_desc = f"{target_week_start.month}/{target_week_start.day}-{week_end.month}/{week_end.day}"
    
    return target_week_start, dates, week_desc

def parse_week_parameter(week_param: str) -> Tuple[int, str]:
    """
    解析周次參數
    
    Args:
        week_param: 周次參數字符串
        
    Returns:
        (周次偏移, 周次名稱)
        
    Raises:
        ValueError: 不支持的周次參數
    """
    week_param = week_param.strip()
    
    week_mappings = {
        "本週": (0, "本周"),
        "這週": (0, "本周"), 
        "本周": (0, "本周"),
        "這周": (0, "本周"),
        "下週": (1, "下周"),
        "下周": (1, "下周"),
        "下一週": (1, "下周"),
        "下一周": (1, "下周"),
        "下個週": (1, "下周"),
        "下個周": (1, "下周"),
        "下星期": (1, "下周"),
        "下個星期": (1, "下周"),
    }
    
    if week_param in week_mappings:
        return week_mappings[week_param]
    
    # 檢查是否為過去時間態（禁止）
    past_week_keywords = ["上週", "上周", "上一週", "上一周", "上個週", "上個周", "上星期", "上個星期", "前週", "前周"]
    if week_param in past_week_keywords:
        raise ValueError(f"不允許匯入過去時間態：{week_param}")
    
    # 未知參數
    raise ValueError(f"不支持的周次參數：{week_param}")

def is_week_in_past(week_dates: List[date], reference_date: date = None) -> bool:
    """
    檢查周次是否為過去時間態
    
    Args:
        week_dates: 周次日期列表
        reference_date: 參考日期（默認為今天）
        
    Returns:
        True如果整周都已過去
    """
    if reference_date is None:
        reference_date = date.today()
    
    # 檢查周六（最後一天）是否已過去
    week_end = week_dates[6]
    return week_end < reference_date

def get_available_weeks() -> List[Tuple[int, str, str]]:
    """
    獲取可用的周次選項
    
    Returns:
        [(偏移值, 周次名稱, 周次描述), ...]
    """
    today = date.today()
    available_weeks = []
    
    # 本周
    offset, name = 0, "本周"
    _, _, desc = calculate_target_week(today, offset)
    available_weeks.append((offset, name, desc))
    
    # 下周
    offset, name = 1, "下周"
    _, _, desc = calculate_target_week(today, offset)
    available_weeks.append((offset, name, desc))
    
    # 下下周（可選，提供更多靈活性）
    offset, name = 2, "下下周"
    _, _, desc = calculate_target_week(today, offset)
    available_weeks.append((offset, name, desc))
    
    return available_weeks 