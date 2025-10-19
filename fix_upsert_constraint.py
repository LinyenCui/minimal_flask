#!/usr/bin/env python3
"""
修復 UPSERT 約束問題
1. 重新添加 unique_code 唯一約束
2. 確保 UPSERT 能正常工作
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

def add_unique_constraint():
    """添加 unique_code 唯一約束"""
    print("🔧 添加 unique_code 唯一約束")
    print("-" * 50)
    
    local_conn = get_db_connection(LOCAL_DB_CONFIG, "Local")
    if not local_conn:
        return False
    
    try:
        with local_conn.cursor() as cur:
            # 檢查約束是否已存在
            check_constraint_query = """
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'completed_trips' 
              AND constraint_type = 'UNIQUE'
              AND constraint_name = 'unique_completed_trip_code'
            """
            
            cur.execute(check_constraint_query)
            existing_constraints = cur.fetchall()
            
            if existing_constraints:
                print("✅ unique_code 唯一約束已存在")
                return True
            
            # 添加唯一約束
            print("🔧 添加 unique_code 唯一約束...")
            add_constraint_query = """
            ALTER TABLE completed_trips 
            ADD CONSTRAINT unique_completed_trip_code 
            UNIQUE (unique_code)
            """
            
            cur.execute(add_constraint_query)
            local_conn.commit()
            print("✅ 成功添加 unique_code 唯一約束")
            
            return True
            
    except Exception as e:
        print(f"❌ 添加唯一約束時發生錯誤: {e}", file=sys.stderr)
        local_conn.rollback()
        return False
    finally:
        if local_conn:
            local_conn.close()

def verify_constraint():
    """驗證約束是否生效"""
    print("\n✅ 驗證約束是否生效")
    print("-" * 50)
    
    local_conn = get_db_connection(LOCAL_DB_CONFIG, "Local")
    if not local_conn:
        return False
    
    try:
        with local_conn.cursor() as cur:
            # 檢查約束是否存在
            check_constraint_query = """
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'completed_trips' 
              AND constraint_type = 'UNIQUE'
              AND constraint_name = 'unique_completed_trip_code'
            """
            
            cur.execute(check_constraint_query)
            existing_constraints = cur.fetchall()
            
            if existing_constraints:
                print("✅ unique_code 唯一約束已生效")
                return True
            else:
                print("❌ unique_code 唯一約束未生效")
                return False
                
    except Exception as e:
        print(f"❌ 驗證約束時發生錯誤: {e}", file=sys.stderr)
        return False
    finally:
        if local_conn:
            local_conn.close()

def test_upsert_with_constraint():
    """測試 UPSERT 與約束的配合"""
    print("\n🧪 測試 UPSERT 與約束的配合")
    print("-" * 50)
    
    local_conn = get_db_connection(LOCAL_DB_CONFIG, "Local")
    if not local_conn:
        return False
    
    try:
        with local_conn.cursor() as cur:
            # 清理測試資料
            cur.execute("DELETE FROM completed_trips WHERE unique_code = 'TEST_UPSERT_001'")
            local_conn.commit()
            
            # 測試資料
            test_data = {
                'unique_code': 'TEST_UPSERT_001',
                'date': '2025-10-19',
                'start_point': '測試起點',
                'via_point': '測試經點',
                'end_point': '測試終點',
                'meter_fare': 100,
                'extra_fare': 0,
                'category': '測試',
                'driver_id': 999,
                'trip_type': '測試',
                'passenger_name': '測試乘客',
                'passenger_leave_reason': None,
                'modification_reason': None
            }
            
            # 第一次插入
            print("🔄 第一次插入...")
            insert_query = """
            INSERT INTO completed_trips
            (date, start_point, via_point, end_point,
             meter_fare, extra_fare, category, driver_id,
             unique_code, trip_type, passenger_name,
             passenger_leave_reason, modification_reason)
            VALUES
            (%(date)s, %(start_point)s, %(via_point)s, %(end_point)s,
             %(meter_fare)s, %(extra_fare)s, %(category)s, %(driver_id)s,
             %(unique_code)s, %(trip_type)s, %(passenger_name)s,
             %(passenger_leave_reason)s, %(modification_reason)s)
            ON CONFLICT (unique_code) DO UPDATE SET
                date = EXCLUDED.date,
                start_point = EXCLUDED.start_point,
                via_point = EXCLUDED.via_point,
                end_point = EXCLUDED.end_point,
                meter_fare = EXCLUDED.meter_fare,
                extra_fare = EXCLUDED.extra_fare,
                category = EXCLUDED.category,
                driver_id = EXCLUDED.driver_id,
                trip_type = EXCLUDED.trip_type,
                passenger_name = EXCLUDED.passenger_name,
                passenger_leave_reason = EXCLUDED.passenger_leave_reason,
                modification_reason = EXCLUDED.modification_reason
            """
            
            cur.execute(insert_query, test_data)
            local_conn.commit()
            print("✅ 第一次插入成功")
            
            # 檢查記錄數
            cur.execute("SELECT COUNT(*) FROM completed_trips WHERE unique_code = %s", (test_data['unique_code'],))
            count_after_first = cur.fetchone()[0]
            print(f"   插入後記錄數: {count_after_first}")
            
            # 第二次插入（模擬重複）
            print("🔄 第二次插入（模擬重複）...")
            test_data['meter_fare'] = 200  # 修改數據
            cur.execute(insert_query, test_data)
            local_conn.commit()
            print("✅ 第二次插入成功")
            
            # 檢查最終結果
            cur.execute("SELECT COUNT(*) FROM completed_trips WHERE unique_code = %s", (test_data['unique_code'],))
            count_after_second = cur.fetchone()[0]
            print(f"   重複插入後記錄數: {count_after_second}")
            
            # 檢查數據是否被更新
            cur.execute("SELECT meter_fare FROM completed_trips WHERE unique_code = %s", (test_data['unique_code'],))
            updated_fare = cur.fetchone()[0]
            print(f"   更新後的車資: {updated_fare}")
            
            if count_after_second == 1 and updated_fare == 200:
                print("✅ UPSERT 測試通過！記錄被正確更新")
                return True
            else:
                print(f"❌ UPSERT 測試失敗！記錄數: {count_after_second}, 車資: {updated_fare}")
                return False
                
    except Exception as e:
        print(f"❌ 測試 UPSERT 時發生錯誤: {e}", file=sys.stderr)
        local_conn.rollback()
        return False
    finally:
        if local_conn:
            local_conn.close()

def main():
    """主函數"""
    print("🔧 修復 UPSERT 約束問題")
    print("=" * 60)
    
    # 步驟1: 添加唯一約束
    if not add_unique_constraint():
        print("❌ 添加唯一約束失敗")
        return False
    
    # 步驟2: 驗證約束
    if not verify_constraint():
        print("❌ 驗證約束失敗")
        return False
    
    # 步驟3: 測試 UPSERT
    if not test_upsert_with_constraint():
        print("❌ 測試 UPSERT 失敗")
        return False
    
    print("\n🎉 UPSERT 約束修復完成！")
    print("=" * 60)
    print("✅ 已添加 unique_code 唯一約束")
    print("✅ UPSERT 操作正常工作")
    print("✅ 重複插入問題已解決")
    
    print("\n💡 修復說明:")
    print("   1. 重新添加了 unique_code 唯一約束")
    print("   2. UPSERT 操作現在可以正常工作")
    print("   3. 重複插入會被自動更新而不是重複")
    print("   4. 這才是真正的原子性解決方案")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)