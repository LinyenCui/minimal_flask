#!/usr/bin/env python3
"""
測試日期解析修復效果
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.utils.helpers import parse_date_input, get_taiwan_date

def test_date_parsing():
    """測試日期解析功能"""
    print("🧪 測試日期解析修復效果")
    print("=" * 50)
    
    today = get_taiwan_date()
    print(f"今天日期：{today}")
    print()
    
    test_cases = [
        ("前天", "應該是 " + str(today - timedelta(days=2))),
        ("昨天", "應該是 " + str(today - timedelta(days=1))),
        ("今天", "應該是 " + str(today)),
        ("明天", "應該是 " + str(today + timedelta(days=1))),
        ("後天", "應該是 " + str(today + timedelta(days=2))),
        ("7/25", "應該是 2025-07-25"),
        ("7/24", "應該是 2025-07-24"),
    ]
    
    from datetime import timedelta
    
    print("測試結果：")
    for date_input, expected in test_cases:
        try:
            result = parse_date_input(date_input)
            status = "✅" if result else "❌"
            print(f"{status} '{date_input}' → {result} ({expected})")
        except Exception as e:
            print(f"❌ '{date_input}' → Error: {str(e)} ({expected})")
    
    print()
    print("🎯 修復驗證：")
    try:
        yesterday = parse_date_input("昨天")
        absolute_725 = parse_date_input("7/25")
        
        if str(yesterday) == "2025-07-25" and str(absolute_725) == "2025-07-25":
            print("✅ '昨天'和'7/25'解析為相同日期 → 修復成功！")
        else:
            print(f"⚠️ '昨天'={yesterday}, '7/25'={absolute_725} → 結果不一致")
    except Exception as e:
        print(f"❌ 測試失敗：{str(e)}")

if __name__ == "__main__":
    test_date_parsing() 