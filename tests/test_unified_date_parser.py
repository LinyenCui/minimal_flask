#!/usr/bin/env python3
"""
統一日期解析器測試
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, date

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.utils.unified_date_parser import UnifiedDateParser

class TestUnifiedDateParser:
    """統一日期解析器測試類"""
    
    def test_relative_date_parsing(self):
        """測試相對日期解析"""
        parser = UnifiedDateParser()
        
        # 相對日期測試
        yesterday_result = parser.parse("昨天")
        assert yesterday_result is not None
        assert isinstance(yesterday_result, date)
        
        today_result = parser.parse("今天")
        assert today_result is not None
        assert isinstance(today_result, date)
        
        tomorrow_result = parser.parse("明天")
        assert tomorrow_result is not None
        assert isinstance(tomorrow_result, date)
    
    def test_absolute_date_parsing(self):
        """測試絕對日期解析"""
        parser = UnifiedDateParser()
        
        # 數字日期測試
        date_result = parser.parse("7/25")
        assert date_result is not None
        assert isinstance(date_result, date)
        assert date_result.month == 7
        assert date_result.day == 25
        
        # 完整日期測試
        full_date_result = parser.parse("2025/7/25")
        assert full_date_result is not None
        assert full_date_result.year == 2025
        assert full_date_result.month == 7
        assert full_date_result.day == 25
    
    def test_chinese_date_parsing(self):
        """測試中文日期解析"""
        parser = UnifiedDateParser()
        
        # 數字中文日期測試 (7月25日)
        chinese_result = parser.parse("7月25日")
        assert chinese_result is not None
        assert chinese_result.month == 7
        assert chinese_result.day == 25
    
    def test_edge_cases(self):
        """測試邊界情況"""
        parser = UnifiedDateParser()
        
        # 無效輸入應該拋出異常
        with pytest.raises(ValueError):
            parser.parse("無效日期")
        
        # 空字串應該拋出異常
        with pytest.raises(ValueError):
            parser.parse("")
        
        # None輸入應該拋出異常
        with pytest.raises(ValueError):
            parser.parse(None)
    
    def test_environment_consistency(self):
        """測試環境一致性（核心測試）"""
        parser = UnifiedDateParser()
        
        # 關鍵：確保昨天解析結果一致
        test_cases = ["昨天", "今天", "明天", "7/25", "2025/7/25"]
        
        for test_case in test_cases:
            result1 = parser.parse(test_case)
            result2 = parser.parse(test_case)
            
            # 相同輸入應該產生相同結果
            assert result1 == result2, f"解析不一致: {test_case}"
    
    def test_hospital_schedule_query(self):
        """測試診所班次查詢場景"""
        parser = UnifiedDateParser()
        
        # 模擬實際使用情境
        yesterday_query = "昨天診所班次"
        yesterday_date = parser.parse("昨天")
        
        assert yesterday_date is not None
        print(f"昨天日期解析結果: {yesterday_date}")
        
        # 確保日期合理
        today = date.today()
        expected_yesterday = date.fromordinal(today.toordinal() - 1)
        assert yesterday_date == expected_yesterday

if __name__ == "__main__":
    pytest.main([__file__, "-v"])