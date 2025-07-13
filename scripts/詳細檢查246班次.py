#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
詳細檢查 246 班次
確認是否有班次缺失需要補充
"""

import os
from datetime import date, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 設置資料庫連接
DATABASE_URL = "postgresql://postgres:0720@localhost:5432/dispatch_db"
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

def check_246_trips():
    """檢查 246 班次的詳細情況"""
    session = Session()
    
    try:
        print("🔍 詳細檢查 route_number=246 的所有班次：")
        print("=" * 100)
        
        # 查詢所有 route_number=246 的班次
        query = """
        SELECT 
            id, route_number, departure_time, start_point, via_point, end_point,
            base_fare, surcharge, total_fare, category, driver_id, direction,
            status, note
        FROM fixed_schedules
        WHERE route_number LIKE '%246%'
        ORDER BY departure_time
        """
        
        results = session.execute(text(query)).fetchall()
        
        for row in results:
            id, route_number, departure_time, start_point, via_point, end_point = row[:6]
            base_fare, surcharge, total_fare, category, driver_id, direction = row[6:12]
            status, note = row[12:14]
            
            print(f"ID: {id:2d} | {departure_time} | {start_point:12s} → {end_point:12s} | {base_fare}元 | 司機:{driver_id}")
            if via_point:
                print(f"       途經: {via_point}")
            print("-" * 100)
        
        print(f"\n📊 總共找到 {len(results)} 筆 route_number=246 的班次")
        
        # 計算本週的日期（星期二、四、六）
        today = date.today()
        days_since_sunday = today.weekday() + 1 if today.weekday() < 6 else 0
        week_start = today - timedelta(days=days_since_sunday)
        
        # 246 對應星期二(2)、四(4)、六(6)
        weekdays = [2, 4, 6]  # 星期二、四、六
        target_dates = []
        
        for weekday in weekdays:
            target_date = week_start + timedelta(days=weekday)
            target_dates.append(target_date)
        
        print(f"\n📅 本週 246 班次對應的日期：")
        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
        for target_date in target_dates:
            weekday = weekday_names[target_date.weekday()]
            print(f"   {target_date} (星期{weekday})")
        
        # 檢查 trips 表中已匯入的 246 班次
        print(f"\n🔍 檢查 trips 表中本週已匯入的 246 班次：")
        print("=" * 100)
        
        trips_query = """
        SELECT 
            t.trip_id, t.fixed_trip_id, t.date, t.time, 
            t.start_point, t.end_point, t.driver_id, t.status,
            fs.route_number
        FROM trips t
        LEFT JOIN fixed_schedules fs ON t.fixed_trip_id = fs.id
        WHERE t.date >= %s AND t.date <= %s
        AND fs.route_number LIKE '%%246%%'
        ORDER BY t.date, t.time
        """
        
        trips_results = session.execute(text(trips_query), (target_dates[0], target_dates[-1])).fetchall()
        
        if trips_results:
            for row in trips_results:
                trip_id, fixed_trip_id, trip_date, trip_time = row[:4]
                start_point, end_point, driver_id, status, route_number = row[4:9]
                weekday = weekday_names[trip_date.weekday()]
                print(f"班次 #{trip_id} | 固定班次ID:{fixed_trip_id} | {trip_date} (星期{weekday}) | {trip_time}")
                print(f"        {start_point} → {end_point} | 司機:{driver_id} | 狀態:{status}")
                print("-" * 100)
        else:
            print("❌ trips 表中沒有找到本週的 246 班次")
        
        # 分析可能缺失的班次
        print(f"\n📋 分析：")
        fixed_count = len(results)
        imported_count = len(trips_results)
        expected_count = fixed_count * len(target_dates)  # 每個固定班次 × 3天
        
        print(f"   固定班次表中的 246 班次數量: {fixed_count}")
        print(f"   本週應該匯入的班次數量: {expected_count} ({fixed_count} × {len(target_dates)}天)")
        print(f"   trips表中已匯入的 246 班次數量: {imported_count}")
        
        if imported_count < expected_count:
            print(f"   ⚠️  可能缺失 {expected_count - imported_count} 筆班次")
        else:
            print(f"   ✅ 班次數量正常")
            
    except Exception as e:
        print(f"❌ 查詢錯誤: {e}")
    
    finally:
        session.close()

if __name__ == "__main__":
    check_246_trips() 