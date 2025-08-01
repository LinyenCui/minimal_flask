#!/usr/bin/env python3
"""
測試跨日期範圍查詢功能
"""

import sys
import os

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.services.date_range_query_service import (
    parse_date_range,
    handle_query_completed_trips_range,
    handle_query_current_trips_range
)
from modules.utils.unified_date_parser import UnifiedDateParser

def test_date_range_parsing():
    """測試日期範圍解析"""
    print("=== 測試日期範圍解析 ===")
    
    test_cases = [
        "7/28-7/30",
        "7/28到7/30", 
        "2025-07-28-2025-07-30",
        "昨天到今天",
        "7/25~7/31",
        "invalid-range"
    ]
    
    for case in test_cases:
        start_date, end_date = parse_date_range(case)
        if start_date and end_date:
            print(f"✅ '{case}' → {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
        else:
            print(f"❌ '{case}' → 解析失敗")
    
    print()

def test_completed_trips_range_query():
    """測試已完成班次範圍查詢"""
    print("=== 測試已完成班次範圍查詢 ===")
    
    test_commands = [
        "查已完成範圍 7/28-7/30",
        "查已完成範圍 7/28-7/30 5386",
        "查已完成範圍 7/28-7/30 診所",
        "查已完成範圍 7/28-7/30 5386 診所",
        "查已完成範圍 invalid-date",
        "查已完成範圍"  # 缺少參數
    ]
    
    for cmd in test_commands:
        print(f"🔍 命令: {cmd}")
        try:
            result = handle_query_completed_trips_range(cmd)
            print(f"結果: {result[:200]}...")  # 只顯示前200字符
        except Exception as e:
            print(f"❌ 錯誤: {e}")
        print("-" * 50)
    
    print()

def test_current_trips_range_query():
    """測試進行中班次範圍查詢"""
    print("=== 測試進行中班次範圍查詢 ===")
    
    test_commands = [
        "查班次範圍 8/1-8/5",
        "查班次範圍 8/1-8/5 5386",
        "查班次範圍 8/1-8/5 東洋",
        "查班次範圍 8/1-8/5 5386 東洋",
        "查班次範圍 invalid-date",
        "查班次範圍"  # 缺少參數
    ]
    
    for cmd in test_commands:
        print(f"🔍 命令: {cmd}")
        try:
            result = handle_query_current_trips_range(cmd)
            print(f"結果: {result[:200]}...")  # 只顯示前200字符
        except Exception as e:
            print(f"❌ 錯誤: {e}")
        print("-" * 50)
    
    print()

def test_ai_tool_registry():
    """測試AI工具註冊表"""
    print("=== 測試AI工具註冊表 ===")
    
    try:
        from modules.ai_agent.tool_registry import tool_registry
        
        # 檢查新工具是否註冊成功
        range_tools = [
            "query_completed_trips_range",
            "query_current_trips_range"
        ]
        
        for tool_name in range_tools:
            tool = tool_registry.get_tool(tool_name)
            if tool:
                print(f"✅ {tool_name} 已註冊")
                print(f"   描述: {tool.description}")
                print(f"   參數: {[p.name for p in tool.parameters]}")
                print(f"   範例: {tool.examples[0] if tool.examples else '無'}")
            else:
                print(f"❌ {tool_name} 未註冊")
            print()
    
    except Exception as e:
        print(f"❌ 工具註冊表測試失敗: {e}")

def test_unified_date_parser():
    """測試統一日期解析器"""
    print("=== 測試統一日期解析器 ===")
    
    test_dates = [
        "7/28",
        "7/30", 
        "2025-07-28",
        "昨天",
        "今天",
        "明天"
    ]
    
    for date_str in test_dates:
        try:
            parsed_date = UnifiedDateParser.parse(date_str)
            print(f"✅ '{date_str}' → {parsed_date.strftime('%Y-%m-%d')}")
        except Exception as e:
            print(f"❌ '{date_str}' → {e}")
    
    print()

if __name__ == "__main__":
    print("🧪 跨日期範圍查詢功能測試")
    print("=" * 60)
    
    # 測試各個組件
    test_date_range_parsing()
    test_unified_date_parser()
    test_ai_tool_registry()
    test_completed_trips_range_query()
    test_current_trips_range_query()
    
    print("✅ 測試完成")