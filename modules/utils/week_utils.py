"""
太陽週次計算工具模組
提供以週日為開始的週次計算功能
"""
from datetime import date, timedelta
from typing import Tuple, List
import logging

logger = logging.getLogger(__name__)

def get_sunday_week_start(target_date: date) -> date:
    """
    獲取指定日期所在太陽週的開始日期（週日）
    
    Args:
        target_date: 目標日期
        
    Returns:
        該週的週日日期
    """
    # Python weekday(): Monday=0, Sunday=6
    # 我們需要計算到週日的天數
    days_since_sunday = target_date.weekday() + 1 if target_date.weekday() < 6 else 0
    week_start = target_date - timedelta(days=days_since_sunday)
    return week_start

def get_week_dates(week_start: date) -> List[date]:
    """
    獲取從週日開始的一週七天日期
    
    Args:
        week_start: 週日日期
        
    Returns:
        週日到週六的日期列表
    """
    return [week_start + timedelta(days=i) for i in range(7)]

def get_week_info(target_date: date) -> Tuple[date, List[date], str]:
    """
    獲取指定日期的週次信息
    
    Args:
        target_date: 目標日期
        
    Returns:
        (週日日期, 週日到週六日期列表, 週次描述)
    """
    week_start = get_sunday_week_start(target_date)
    dates = get_week_dates(week_start)
    week_end = dates[6]  # 週六
    
    # 格式化週次描述
    week_desc = f"{week_start.month}/{week_start.day}-{week_end.month}/{week_end.day}"
    
    return week_start, dates, week_desc

def calculate_target_week(base_date: date, week_offset: int) -> Tuple[date, List[date], str]:
    """
    計算目標週次
    
    Args:
        base_date: 基準日期（通常是今天）
        week_offset: 週次偏移（0=本週, 1=下週, -1=上週）
        
    Returns:
        (週日日期, 週日到週六日期列表, 週次描述)
    """
    base_week_start = get_sunday_week_start(base_date)
    target_week_start = base_week_start + timedelta(weeks=week_offset)
    
    dates = get_week_dates(target_week_start)
    week_end = dates[6]
    
    # 格式化週次描述
    week_desc = f"{target_week_start.month}/{target_week_start.day}-{week_end.month}/{week_end.day}"
    
    return target_week_start, dates, week_desc

def parse_week_parameter(week_param: str) -> Tuple[int, str]:
    """
    解析週次參數
    
    Args:
        week_param: 週次參數字符串
        
    Returns:
        (週次偏移, 週次名稱)
        
    Raises:
        ValueError: 不支持的週次參數
    """
    week_param = week_param.strip()
    
    week_mappings = {
        "本週": (0, "本週"),
        "這週": (0, "本週"), 
        "本周": (0, "本週"),
        "這周": (0, "本週"),
        "下週": (1, "下週"),
        "下周": (1, "下週"),
        "下一週": (1, "下週"),
        "下一周": (1, "下週"),
        "下個週": (1, "下週"),
        "下個周": (1, "下週"),
        "下星期": (1, "下週"),
        "下個星期": (1, "下週"),
    }
    
    if week_param in week_mappings:
        return week_mappings[week_param]
    
    # 檢查是否為過去時間態（禁止）
    past_week_keywords = ["上週", "上周", "上一週", "上一周", "上個週", "上個周", "上星期", "上個星期", "前週", "前周"]
    if week_param in past_week_keywords:
        raise ValueError(f"不允許匯入過去時間態：{week_param}")
    
    # 未知參數
    raise ValueError(f"不支持的週次參數：{week_param}")

def is_week_in_past(week_dates: List[date], reference_date: date = None) -> bool:
    """
    檢查週次是否為過去時間態
    
    Args:
        week_dates: 週次日期列表
        reference_date: 參考日期（默認為今天）
        
    Returns:
        True如果整週都已過去
    """
    if reference_date is None:
        reference_date = date.today()
    
    # 檢查週六（最後一天）是否已過去
    week_end = week_dates[6]
    return week_end < reference_date

def get_available_weeks() -> List[Tuple[int, str, str]]:
    """
    獲取可用的週次選項
    
    Returns:
        [(偏移值, 週次名稱, 週次描述), ...]
    """
    today = date.today()
    available_weeks = []
    
    # 本週
    offset, name = 0, "本週"
    _, _, desc = calculate_target_week(today, offset)
    available_weeks.append((offset, name, desc))
    
    # 下週
    offset, name = 1, "下週"
    _, _, desc = calculate_target_week(today, offset)
    available_weeks.append((offset, name, desc))
    
    # 下下週（可選，提供更多靈活性）
    offset, name = 2, "下下週"
    _, _, desc = calculate_target_week(today, offset)
    available_weeks.append((offset, name, desc))
    
    return available_weeks 