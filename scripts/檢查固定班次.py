#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
檢查固定班次資料
用於確認固定班次表中的內容
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 設置資料庫連接
DATABASE_URL = "postgresql://postgres:0720@localhost:5432/dispatch_db"
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

def check_fixed_schedules():
    """檢查固定班次表"""
    session = Session()
    
    try:
        # 查詢所有固定班次
        query = """
        SELECT 
            id, route_number, departure_time, start_point, via_point, end_point,
            base_fare, surcharge, total_fare, category, driver_id, direction,
            status, note
        FROM fixed_schedules
        ORDER BY id DESC
        LIMIT 10
        """
        
        results = session.execute(text(query)).fetchall()
        
        print("📋 最新的 10 筆固定班次：")
        print("=" * 80)
        
        for row in results:
            print(f"ID: {row[0]:3d} | route_number: {row[1]:10s} | time: {row[2]} | {row[3]} → {row[5]}")
            print(f"       fare: {row[6]} | category: {row[9]} | driver: {row[10]} | status: {row[12]}")
            print("-" * 80)
        
        # 特別查詢 ID=54
        print("\n🔍 查詢 ID=54：")
        specific_query = "SELECT * FROM fixed_schedules WHERE id = 54"
        specific_result = session.execute(text(specific_query)).fetchone()
        
        if specific_result:
            print("✅ 找到 ID=54:")
            print(f"   {specific_result}")
        else:
            print("❌ 沒有找到 ID=54")
        
        # 查詢 route_number 包含 246 的記錄
        print("\n🔍 查詢 route_number 包含 '246' 的記錄：")
        route_query = "SELECT id, route_number, departure_time, start_point, end_point FROM fixed_schedules WHERE route_number LIKE '%246%'"
        route_results = session.execute(text(route_query)).fetchall()
        
        if route_results:
            print("✅ 找到 route_number 包含 '246' 的記錄:")
            for row in route_results:
                print(f"   ID: {row[0]} | route_number: {row[1]} | time: {row[2]} | {row[3]} → {row[4]}")
        else:
            print("❌ 沒有找到 route_number 包含 '246' 的記錄")
            
    except Exception as e:
        print(f"❌ 查詢錯誤: {e}")
    
    finally:
        session.close()

if __name__ == "__main__":
    check_fixed_schedules() 