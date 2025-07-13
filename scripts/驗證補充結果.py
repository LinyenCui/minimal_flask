#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
驗證補充結果
確認 ID=54 的班次是否成功補充到 trips 表
"""

import os
from datetime import date, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 設置資料庫連接
DATABASE_URL = "postgresql://postgres:0720@localhost:5432/dispatch_db"
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

def verify_added_trips():
    """驗證補充結果"""
    session = Session()
    
    try:
        print("🔍 驗證 ID=54 班次的補充結果：")
        print("=" * 80)
        
        # 查詢 trips 表中 fixed_trip_id=54 的記錄
        query = """
        SELECT 
            t.trip_id, t.fixed_trip_id, t.date, t.time, 
            t.start_point, t.end_point, t.driver_id, t.status
        FROM trips t
        WHERE t.fixed_trip_id = 54
        ORDER BY t.date, t.time
        """
        
        results = session.execute(text(query)).fetchall()
        
        if results:
            print(f"✅ 找到 {len(results)} 筆 ID=54 的班次：")
            print()
            weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
            
            for row in results:
                trip_id, fixed_trip_id, trip_date, trip_time = row[:4]
                start_point, end_point, driver_id, status = row[4:8]
                weekday = weekday_names[trip_date.weekday()]
                
                print(f"  班次 #{trip_id} | {trip_date} (星期{weekday}) | {trip_time}")
                print(f"          {start_point} → {end_point} | 司機:{driver_id} | 狀態:{status}")
                print("-" * 80)
        else:
            print("❌ 沒有找到 fixed_trip_id=54 的班次")
        
        # 檢查本週所有 246 相關的班次數量
        print("\n📊 本週 246 班次統計：")
        
        # 計算本週日期範圍
        today = date.today()
        days_since_sunday = today.weekday() + 1 if today.weekday() < 6 else 0
        week_start = today - timedelta(days=days_since_sunday)
        week_end = week_start + timedelta(days=6)
        
        count_query = """
        SELECT COUNT(*)
        FROM trips t
        LEFT JOIN fixed_schedules fs ON t.fixed_trip_id = fs.id
        WHERE t.date >= :week_start AND t.date <= :week_end
        AND fs.route_number LIKE '%246%'
        """
        
        total_count = session.execute(text(count_query), {
            "week_start": week_start,
            "week_end": week_end
        }).fetchone()[0]
        
        print(f"   本週 246 班次總數: {total_count}")
        print(f"   週期範圍: {week_start} 至 {week_end}")
        
    except Exception as e:
        print(f"❌ 驗證錯誤: {e}")
    
    finally:
        session.close()

if __name__ == "__main__":
    verify_added_trips() 