#!/usr/bin/env python3
"""
範圍搜尋金額加總測試
測試 '7/1-7/31診所班次金額加總' 功能，檢查日期計算和金額加總是否正確
"""

import sys
import os
import logging
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.services.date_range_query_service import (
    parse_date_range, 
    query_completed_trips_range,
    format_completed_trips_range_result,
    handle_query_completed_trips_range
)
from modules.utils.unified_date_parser import UnifiedDateParser
from modules.utils.taiwan_time import get_taiwan_date

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_date_parsing_beyond_30_days():
    """
    測試超過30天的日期計算問題
    用戶提到的問題：三十天以後的日就算去年還是明年的麻煩改長一點
    """
    print("=" * 60)
    print("🔍 測試日期解析 - 超過30天的日期計算")
    print("=" * 60)
    
    today = get_taiwan_date()
    current_year = today.year
    
    test_cases = [
        # 測試7月1日的解析（8月6日測試）
        ("7/1", "7月1日解析測試"),
        ("7/31", "7月31日解析測試"),
        ("1/1", "1月1日解析測試（跨年）"),
        ("12/31", "12月31日解析測試"),
        ("3/1", "3月1日解析測試"),
        ("6/15", "6月15日解析測試"),
        ("9/15", "9月15日解析測試"),
        ("11/30", "11月30日解析測試"),
    ]
    
    for date_str, description in test_cases:
        try:
            parsed_date = UnifiedDateParser.parse(date_str)
            days_diff = (parsed_date - today).days
            
            print(f"📅 {description}")
            print(f"   輸入: {date_str}")
            print(f"   今天: {today.strftime('%Y-%m-%d')} ({today.strftime('%m/%d')})")
            print(f"   解析: {parsed_date.strftime('%Y-%m-%d')} ({parsed_date.strftime('%m/%d')})")
            print(f"   天數差: {days_diff} 天 ({'未來' if days_diff > 0 else '過去'})")
            print(f"   年份: {parsed_date.year} ({'明年' if parsed_date.year > current_year else '今年' if parsed_date.year == current_year else '去年'})")
            
            # 檢查超過30天的邏輯
            if abs(days_diff) > 30:
                if days_diff < 0:  # 過去的日期
                    print(f"   ⚠️  警告：過去 {abs(days_diff)} 天，應該考慮是否應該被歸類為明年？")
                else:  # 未來的日期
                    print(f"   ✅ 未來 {days_diff} 天，正常")
            else:
                print(f"   ✅ 30天內，正常")
            
            print()
            
        except Exception as e:
            print(f"❌ {description} 解析失敗: {e}")
            print()

def test_date_range_parsing():
    """測試日期範圍解析功能"""
    print("=" * 60)
    print("🔍 測試日期範圍解析")
    print("=" * 60)
    
    test_ranges = [
        "7/1-7/31",
        "1/1-1/31", 
        "12/1-12/31",
        "6/1-8/31",
        "2024-07-01-2024-07-31",
        "昨天-今天",
        "7/1到7/31",
        "7/1至7/31"
    ]
    
    for range_str in test_ranges:
        try:
            start_date, end_date = parse_date_range(range_str)
            if start_date and end_date:
                days_span = (end_date - start_date).days + 1
                print(f"📅 範圍: {range_str}")
                print(f"   開始: {start_date.strftime('%Y-%m-%d')}")
                print(f"   結束: {end_date.strftime('%Y-%m-%d')}")
                print(f"   天數: {days_span} 天")
                print(f"   ✅ 解析成功")
            else:
                print(f"❌ 範圍: {range_str} - 解析失敗")
            print()
        except Exception as e:
            print(f"❌ 範圍: {range_str} - 解析異常: {e}")
            print()

def create_mock_completed_trips_data():
    """創建模擬的已完成班次數據"""
    today = get_taiwan_date()
    
    # 模擬7月份診所班次數據
    mock_trips = [
        # (id, date, start_point, end_point, category, meter_fare, extra_fare, total_fare, driver_id, modification_reason, trip_type)
        (1, "2025-07-01", "診所A", "病患家", "診所", 150, 50, 200, 5386, None, "regular"),
        (2, "2025-07-01", "診所B", "病患家", "診所", 200, 0, 200, 5387, None, "regular"),
        (3, "2025-07-02", "診所C", "病患家", "診所", 180, 20, 200, 5386, None, "regular"),
        (4, "2025-07-05", "診所A", "病患家", "診所", 300, 100, 400, 5388, None, "regular"),
        (5, "2025-07-10", "診所D", "病患家", "診所", 250, 50, 300, 5386, None, "regular"),
        (6, "2025-07-15", "診所A", "病患家", "診所", 160, 40, 200, 5387, None, "regular"),
        (7, "2025-07-20", "診所B", "病患家", "診所", 220, 80, 300, 5388, None, "regular"),
        (8, "2025-07-25", "診所C", "病患家", "診所", 190, 10, 200, 5386, None, "regular"),
        (9, "2025-07-30", "診所D", "病患家", "診所", 280, 120, 400, 5387, None, "regular"),
        (10, "2025-07-31", "診所A", "病患家", "診所", 170, 30, 200, 5388, None, "regular"),
        
        # 一些非診所班次（應該被過濾掉）
        (11, "2025-07-15", "市區A", "市區B", "東洋", 500, 0, 500, 5386, None, "regular"),
        (12, "2025-07-20", "車站", "機場", "臨時", 800, 200, 1000, 5387, None, "regular"),
    ]
    
    return mock_trips

def test_amount_summation():
    """測試金額加總功能"""
    print("=" * 60)
    print("🔍 測試診所班次金額加總 (7/1-7/31)")
    print("=" * 60)
    
    # 模擬數據
    mock_trips = create_mock_completed_trips_data()
    
    # 使用mock測試query_completed_trips_range函數
    with patch('modules.services.date_range_query_service.db') as mock_db:
        # 模擬數據庫查詢返回診所班次
        mock_result = Mock()
        mock_result.fetchall.return_value = [trip for trip in mock_trips if trip[4] == "診所"]  # 只返回診所班次
        mock_db.session.execute.return_value = mock_result
        
        try:
            # 測試日期範圍解析
            start_date, end_date = parse_date_range("7/1-7/31")
            print(f"📅 測試日期範圍:")
            print(f"   開始日期: {start_date}")
            print(f"   結束日期: {end_date}")
            print()
            
            # 查詢診所班次
            trips = query_completed_trips_range(start_date, end_date, category="診所")
            
            if trips:
                print(f"📊 查詢到 {len(trips)} 筆診所班次:")
                total_amount = 0
                daily_totals = {}
                
                for trip in trips:
                    trip_id, date_str, start_point, end_point, category = trip[:5]
                    meter_fare, extra_fare, total_fare = trip[5:8]
                    driver_id = trip[8]
                    
                    print(f"   #{trip_id} {date_str} 司機{driver_id} {start_point}→{end_point} ${total_fare}")
                    total_amount += total_fare
                    
                    # 按日統計
                    if date_str not in daily_totals:
                        daily_totals[date_str] = 0
                    daily_totals[date_str] += total_fare
                
                print()
                print(f"💰 7月份診所班次金額統計:")
                print(f"   總筆數: {len(trips)} 筆")
                print(f"   總金額: ${total_amount:,} 元")
                print(f"   平均每筆: ${total_amount/len(trips):,.0f} 元")
                
                print()
                print(f"📈 每日金額統計:")
                for date_str in sorted(daily_totals.keys()):
                    print(f"   {date_str}: ${daily_totals[date_str]:,} 元")
                
                # 驗證金額計算
                expected_total = sum(trip[7] for trip in mock_trips if trip[4] == "診所")  # 只計算診所班次
                if total_amount == expected_total:
                    print(f"\n✅ 金額計算正確！")
                else:
                    print(f"\n❌ 金額計算錯誤！")
                    print(f"   預期: ${expected_total}")
                    print(f"   實際: ${total_amount}")
            else:
                print("❌ 未查詢到診所班次數據")
                
        except Exception as e:
            print(f"❌ 測試過程中發生錯誤: {e}")
            import traceback
            print(f"詳細錯誤: {traceback.format_exc()}")

def test_complete_query_flow():
    """測試完整的查詢流程"""
    print("=" * 60)
    print("🔍 測試完整查詢流程")
    print("=" * 60)
    
    # 模擬完整的命令處理
    test_commands = [
        "查已完成範圍 7/1-7/31 診所",
        "查已完成範圍 7/1-7/31",
        "查已完成範圍 1/1-1/31 診所",  # 測試跨年日期
        "查已完成範圍 12/1-12/31 診所"  # 測試年底日期
    ]
    
    mock_trips = create_mock_completed_trips_data()
    
    for command in test_commands:
        print(f"🔍 測試命令: '{command}'")
        
        with patch('modules.services.date_range_query_service.db') as mock_db:
            # 根據命令決定返回的數據
            if "診所" in command:
                filtered_trips = [trip for trip in mock_trips if trip[4] == "診所"]
            else:
                filtered_trips = mock_trips
                
            mock_result = Mock()
            mock_result.fetchall.return_value = filtered_trips
            mock_db.session.execute.return_value = mock_result
            
            try:
                result = handle_query_completed_trips_range(command)
                print("結果預覽:")
                print(result[:300] + ("..." if len(result) > 300 else ""))
                print("✅ 命令處理成功")
            except Exception as e:
                print(f"❌ 命令處理失敗: {e}")
        
        print("-" * 40)

def main():
    """主測試函數"""
    print("🚀 開始範圍搜尋金額加總測試")
    print(f"測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"當前日期: {get_taiwan_date()}")
    print()
    
    # 1. 測試日期解析（特別是超過30天的情況）
    test_date_parsing_beyond_30_days()
    
    # 2. 測試日期範圍解析
    test_date_range_parsing()
    
    # 3. 測試金額加總
    test_amount_summation()
    
    # 4. 測試完整查詢流程
    test_complete_query_flow()
    
    print("=" * 60)
    print("🏁 測試完成")
    print("=" * 60)
    
    print("\n💡 根據測試結果的建議:")
    print("1. 檢查日期解析邏輯中的30天限制是否合理")
    print("2. 確認金額加總計算是否正確")
    print("3. 驗證診所班次篩選是否準確")
    print("4. 檢查跨年日期處理是否符合預期")

if __name__ == "__main__":
    main()