#!/usr/bin/env python3
"""
調試AI查詢流程 - 模擬完整的查詢過程
找出第一頁和第二頁數據不一致的原因
"""
import os
import sys

# 添加項目根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from modules.models.base import db
from sqlalchemy import text

def debug_ai_query_flow():
    """調試AI查詢的完整流程"""
    with app.app_context():
        print("=" * 80)
        print("🔍 調試AI查詢流程：/7/14司機5386班次")
        print("=" * 80)
        
        # 步驟1: 模擬智能助手生成命令
        print("\n📍 1. 智能助手階段:")
        user_input = "/7/14司機5386班次"
        generated_command = "查已完成 7/14 司機5386"  # AI生成的命令
        print(f"   用戶輸入: {user_input}")
        print(f"   AI生成命令: {generated_command}")
        
        # 步驟2: 模擬AdvancedQueryProcessor解析條件
        print("\n📍 2. 條件解析階段:")
        from modules.services.advanced_query_processor import AdvancedQueryProcessor
        
        processor = AdvancedQueryProcessor()
        conditions = processor._parse_query_conditions(generated_command)
        print(f"   解析條件: {conditions}")
        
        # 步驟3: 模擬SQL構建
        print("\n📍 3. SQL構建階段:")
        if conditions.get('date'):
            date_condition, date_params = processor._build_date_condition(conditions['date'])
            print(f"   日期條件SQL: {date_condition}")
            print(f"   日期參數: {date_params}")
        else:
            print("   ❌ 沒有解析到日期條件！")
        
        # 步驟4: 執行完整的查詢流程
        print("\n📍 4. 完整查詢執行:")
        user_id = "test_user"
        result = processor.process_complex_query(generated_command, user_id)
        
        print(f"   查詢結果類型: {result.get('type')}")
        print(f"   結果數量: {result.get('count', 'N/A')}")
        print(f"   總金額: {result.get('total_amount', 'N/A')}")
        
        # 步驟5: 檢查保存的翻頁數據
        print("\n📍 5. 翻頁數據檢查:")
        from modules.utils.conversation_context import get_conversation_context
        
        context = get_conversation_context(user_id)
        saved_state = context.get_query_result()
        
        if saved_state:
            all_results = saved_state.get('all_results', [])
            print(f"   保存的結果數量: {len(all_results)}")
            
            if all_results:
                print("   前5個保存結果的日期:")
                for i, result in enumerate(all_results[:5]):
                    result_date = result.get('date', 'N/A')
                    result_id = result.get('id', 'N/A')
                    driver_id = result.get('driver_id', 'N/A')
                    print(f"     #{result_id} 司機{driver_id} {result_date}")
                    
                # 檢查是否有7/14的數據
                date_counts = {}
                for result in all_results:
                    result_date = str(result.get('date', 'N/A'))
                    date_counts[result_date] = date_counts.get(result_date, 0) + 1
                
                print(f"\n   📊 保存數據的日期分布:")
                for date, count in sorted(date_counts.items()):
                    print(f"     {date}: {count} 個班次")
                    
        else:
            print("   ❌ 沒有保存的翻頁數據！")
        
        # 步驟6: 直接驗證數據庫查詢
        print("\n📍 6. 直接數據庫驗證:")
        direct_query = """
        SELECT 
            id, date, start_point, end_point, category, driver_id,
            meter_fare, extra_fare, (meter_fare + extra_fare) as total_amount
        FROM completed_trips 
        WHERE date = '2025-07-14' AND driver_id = 5386
        ORDER BY id
        """
        
        direct_result = db.session.execute(text(direct_query))
        direct_trips = direct_result.fetchall()
        
        print(f"   直接查詢7/14司機5386: {len(direct_trips)} 個班次")
        if direct_trips:
            direct_total = sum(float(trip.total_amount or 0) for trip in direct_trips)
            print(f"   直接查詢總金額: {direct_total:.0f}元")
            
            print("   直接查詢結果明細:")
            for trip in direct_trips:
                print(f"     #{trip.id} {trip.start_point}→{trip.end_point} "
                      f"[{trip.category}] {trip.total_amount}元")
        
        # 步驟7: 檢查無日期限制的查詢
        print("\n📍 7. 無日期限制查詢檢查:")
        unlimited_query = """
        SELECT 
            id, date, start_point, end_point, category, driver_id,
            meter_fare, extra_fare, (meter_fare + extra_fare) as total_amount
        FROM completed_trips 
        WHERE driver_id = 5386
        ORDER BY date DESC, id DESC
        LIMIT 10
        """
        
        unlimited_result = db.session.execute(text(unlimited_query))
        unlimited_trips = unlimited_result.fetchall()
        
        print(f"   司機5386最近10個班次:")
        for trip in unlimited_trips:
            print(f"     #{trip.id} {trip.date} {trip.start_point}→{trip.end_point} "
                  f"[{trip.category}] {trip.total_amount}元")
        
        print("\n" + "=" * 80)
        print("🔍 調試完成")
        print("=" * 80)

if __name__ == "__main__":
    debug_ai_query_flow() 