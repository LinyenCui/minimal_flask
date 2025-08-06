"""
統一日期解析器
整合所有日期解析邏輯，取代重複實現
"""

import re
from datetime import datetime, timedelta, date
from .taiwan_time import get_taiwan_date, get_taiwan_time

class UnifiedDateParser:
    """統一日期解析器 - 單一責任，唯一來源"""
    
    @staticmethod
    def parse(date_input: str) -> date:
        """
        統一日期解析入口
        支援所有格式：絕對日期、相對日期、中文日期等
        """
        if not date_input or not isinstance(date_input, str):
            raise ValueError("日期輸入不能為空")
        
        date_input = date_input.strip()
        today = get_taiwan_date()
        current_year = today.year
        
        # 1. 相對日期（最常用，優先處理）
        relative_dates = {
            '前天': today - timedelta(days=2),
            '昨天': today - timedelta(days=1), 
            '今天': today,
            '明天': today + timedelta(days=1),
            '後天': today + timedelta(days=2),
        }
        
        if date_input in relative_dates:
            return relative_dates[date_input]
        
        # 2. 完整日期格式 (YYYY-MM-DD)
        if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', date_input):
            return datetime.strptime(date_input, "%Y-%m-%d").date()
        
        # 3. 斜線日期格式 (MM/DD) - 最常用的絕對日期
        if re.match(r'^\d{1,2}/\d{1,2}$', date_input):
            month, day = map(int, date_input.split('/'))
            return UnifiedDateParser._handle_short_date(month, day, today, current_year)
        
        # 4. 短橫線日期格式 (MM-DD)
        elif re.match(r'^\d{1,2}-\d{1,2}$', date_input):
            month, day = map(int, date_input.split('-'))
            return UnifiedDateParser._handle_short_date(month, day, today, current_year)
        
        # 5. 中文日期格式 (MM月DD日)
        elif re.match(r'^\d{1,2}月\d{1,2}日$', date_input):
            month, day = map(int, re.findall(r'\d+', date_input))
            return UnifiedDateParser._handle_short_date(month, day, today, current_year)
        
        # 6. 數字日期格式 (MMDD)
        elif re.match(r'^\d{3,4}$', date_input):
            if len(date_input) == 3:  # 例如 "125" 表示 1月25日
                month = int(date_input[0])
                day = int(date_input[1:3])
            else:  # 例如 "0125" 表示 1月25日
                month = int(date_input[0:2])
                day = int(date_input[2:4])
            return UnifiedDateParser._handle_short_date(month, day, today, current_year)
        
        # 7. 星期幾 (一, 二, 三, 四, 五, 六, 日)
        elif date_input in ['一', '二', '三', '四', '五', '六', '日']:
            weekday_map = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6}
            target_weekday = weekday_map[date_input]
            current_weekday = today.weekday()
            
            # 計算到目標星期幾的天數
            days_ahead = (target_weekday - current_weekday) % 7
            if days_ahead == 0:
                days_ahead = 7  # 如果是同一天，則取下一周的同一天
            
            return today + timedelta(days=days_ahead)
        
        # 無法識別的格式
        else:
            raise ValueError(f"無法識別的日期格式: {date_input}")
    
    @staticmethod
    def _handle_short_date(month: int, day: int, today: date, current_year: int) -> date:
        """處理短日期格式的年份推斷邏輯"""
        try:
            parsed_date = date(current_year, month, day)
            
            # 改進的年份推斷邏輯
            days_difference = (today - parsed_date).days
            
            # 如果日期已過去超過180天（約6個月），假設是明年的日期
            # 如果日期在未來超過180天，假設是去年的日期
            if days_difference > 180:
                # 過去超過180天，推斷為明年
                parsed_date = date(current_year + 1, month, day)
            elif days_difference < -180:
                # 未來超過180天，推斷為去年
                parsed_date = date(current_year - 1, month, day)
            
            return parsed_date
        except ValueError as e:
            raise ValueError(f"無效的日期: {month:02d}/{day:02d}")
    
    @staticmethod 
    def get_relative_date_type(date_input: str) -> str:
        """
        獲取相對日期類型（用於資料庫查詢）
        兼容 advanced_query_processor 的需求
        """
        mapping = {
            '前天': 'day_before_yesterday',
            '昨天': 'yesterday', 
            '今天': 'today',
            '明天': 'tomorrow',
            '後天': 'day_after_tomorrow'
        }
        return mapping.get(date_input)

# 向後兼容的全局函數
def parse_date_input(date_input: str) -> date:
    """向後兼容的日期解析函數"""
    return UnifiedDateParser.parse(date_input) 