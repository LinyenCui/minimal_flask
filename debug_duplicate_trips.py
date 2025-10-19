#!/usr/bin/env python3
"""
調試重複班次問題 - 檢查「小北路經民德105到診所」的重複記錄
"""
import os
import sys
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

load_dotenv()

# 本地資料庫連線資訊
LOCAL_DB_CONFIG = {
    "host": os.getenv('LOCAL_DB_HOST', 'localhost'),
    "user": os.getenv('LOCAL_DB_USER', ''),
    "dbname": os.getenv('LOCAL_DB_NAME', 'dispatch_db'),
    "password": os.getenv('LOCAL_DB_PASSWORD', '')
}

def get_db_connection(config, db_type=""):
    """建立資料庫連線"""
    try:
        print(f"🔌 正在連接到 {db_type} 資料庫...")
        conn = psycopg2.connect(**config)
        print(f"✅ 成功連接到 {db_type} 資料庫。")
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ 無法連接到 {db_type} 資料庫: {e}", file=sys.stderr)
        return None

def check_duplicate_trips():
    """檢查重複班次問題"""
    print("🚀 開始檢查重複班次問題")
    print("=" * 60)
    
    local_conn = get_db_connection(LOCAL_DB_CONFIG, "Local")
    if not local_conn:
        return False
    
    try:
        with local_conn.cursor(cursor_factory=DictCursor) as cur:
            # 1. 檢查 completed_trips 表中的重複記錄
            print("\n📋 1. 檢查 completed_trips 表中的「小北路經民德105到診所」記錄:")
            print("-" * 50)
            
            query = """
            SELECT id, date, start_point, via_point, end_point, unique_code, trip_type, 
                   passenger_name, passenger_leave_reason, modification_reason, created_at
            FROM completed_trips 
            WHERE start_point LIKE '%小北路%' 
              AND via_point LIKE '%民德105%' 
              AND end_point LIKE '%診所%'
            ORDER BY id
            """
            
            cur.execute(query)
            trips = cur.fetchall()
            
            print(f"找到 {len(trips)} 筆記錄:")
            for i, trip in enumerate(trips, 1):
                print(f"  {i}. ID: {trip['id']}, 日期: {trip['date']}")
                print(f"     起點: {trip['start_point']}, 途經: {trip['via_point']}, 終點: {trip['end_point']}")
                print(f"     unique_code: {trip['unique_code']}, trip_type: {trip['trip_type']}")
                print(f"     passenger_name: {trip['passenger_name']}")
                print(f"     leave_reason: {trip['passenger_leave_reason']}")
                print(f"     mod_reason: {trip['modification_reason']}")
                print(f"     created_at: {trip['created_at']}")
                print()
            
            # 2. 檢查是否有相同的 unique_code
            if len(trips) > 1:
                print("🔍 2. 檢查 unique_code 重複情況:")
                print("-" * 50)
                
                unique_codes = [trip['unique_code'] for trip in trips]
                unique_codes_set = set(unique_codes)
                
                if len(unique_codes) != len(unique_codes_set):
                    print("❌ 發現重複的 unique_code!")
                    for code in unique_codes_set:
                        count = unique_codes.count(code)
                        if count > 1:
                            print(f"   unique_code '{code}' 出現 {count} 次")
                else:
                    print("✅ 所有 unique_code 都是唯一的")
            
            # 3. 檢查 trips 表中是否還有相關記錄
            print("\n📋 3. 檢查 trips 表中是否還有相關記錄:")
            print("-" * 50)
            
            trips_query = """
            SELECT trip_id, date, start_point, via_point, end_point, status, unique_code, 
                   fixed_trip_id, passenger_leave_reason
            FROM trips 
            WHERE start_point LIKE '%小北路%' 
              AND via_point LIKE '%民德105%' 
              AND end_point LIKE '%診所%'
            ORDER BY trip_id
            """
            
            cur.execute(trips_query)
            active_trips = cur.fetchall()
            
            print(f"找到 {len(active_trips)} 筆活躍記錄:")
            for trip in active_trips:
                print(f"  trip_id: {trip['trip_id']}, 日期: {trip['date']}, 狀態: {trip['status']}")
                print(f"  unique_code: {trip['unique_code']}, fixed_trip_id: {trip['fixed_trip_id']}")
                print(f"  leave_reason: {trip['passenger_leave_reason']}")
                print()
            
            # 4. 檢查 fixed_schedules 表中的原始記錄
            print("\n📋 4. 檢查 fixed_schedules 表中的原始記錄:")
            print("-" * 50)
            
            fixed_query = """
            SELECT id, route_number, departure_time, start_point, via_point, end_point, 
                   status, note, surcharge
            FROM fixed_schedules 
            WHERE start_point LIKE '%小北路%' 
              AND via_point LIKE '%民德105%' 
              AND end_point LIKE '%診所%'
            ORDER BY id
            """
            
            cur.execute(fixed_query)
            fixed_schedules = cur.fetchall()
            
            print(f"找到 {len(fixed_schedules)} 筆固定班次記錄:")
            for schedule in fixed_schedules:
                print(f"  ID: {schedule['id']}, 路線: {schedule['route_number']}")
                print(f"  時間: {schedule['departure_time']}")
                print(f"  起點: {schedule['start_point']}, 途經: {schedule['via_point']}, 終點: {schedule['end_point']}")
                print(f"  狀態: {schedule['status']}, 說明: {schedule['note']}")
                print(f"  加成: {schedule['surcharge']}")
                print()
            
            # 5. 分析問題
            print("\n🔍 5. 問題分析:")
            print("-" * 50)
            
            if len(trips) > 1:
                print("❌ 發現重複記錄問題!")
                print("   可能的原因:")
                print("   1. unique_code 生成邏輯有問題")
                print("   2. 去重檢查機制失效")
                print("   3. 並發執行導致競態條件")
                print("   4. 資料庫事務問題")
            else:
                print("✅ 沒有發現重複記錄")
            
            return True
            
    except Exception as e:
        print(f"❌ 檢查過程中發生錯誤: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False
    finally:
        if local_conn:
            local_conn.close()
        print("🔌 資料庫連線已關閉。")

if __name__ == "__main__":
    success = check_duplicate_trips()
    exit(0 if success else 1)