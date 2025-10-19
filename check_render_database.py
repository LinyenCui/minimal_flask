#!/usr/bin/env python3
"""
檢查 Render 生產環境資料庫的重複計價問題
1. 連接到 Render PostgreSQL
2. 檢查上一周的 completed_trips
3. 分析是否有重複記錄
"""
import os
import sys
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, timedelta

# Render PostgreSQL 連線資訊
RENDER_DB_CONFIG = {
    "host": "dpg-cvhb8fdrie7s73emf81g-a.singapore-postgres.render.com",
    "user": "dispatch_system_db_user",
    "dbname": "dispatch_system_db",
    "password": "rfmy454LJ5JTtPZjsq60KzzhFf0jsMlP",
    "port": 5432
}

def get_render_connection():
    """建立 Render 資料庫連線"""
    try:
        print("🔌 正在連接到 Render PostgreSQL...")
        conn = psycopg2.connect(**RENDER_DB_CONFIG)
        print("✅ 成功連接到 Render PostgreSQL")
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ 無法連接到 Render PostgreSQL: {e}", file=sys.stderr)
        return None

def get_last_week_dates():
    """獲取上一周的日期範圍"""
    today = datetime.now().date()
    # 計算上一周的開始和結束日期
    last_week_end = today - timedelta(days=today.weekday() + 1)  # 上週日
    last_week_start = last_week_end - timedelta(days=6)  # 上週一
    
    print(f"📅 上一周日期範圍: {last_week_start} 到 {last_week_end}")
    return last_week_start, last_week_end

def check_render_duplicates(conn, start_date, end_date):
    """檢查 Render 資料庫的重複記錄"""
    print("\n🔍 檢查 Render 資料庫重複記錄")
    print("-" * 50)
    
    try:
        with conn.cursor() as cur:
            # 1. 檢查相同日期、相同路線、相同司機的重複
            print("🔍 檢查相同日期+路線+司機的重複...")
            cur.execute("""
            SELECT date, start_point, via_point, end_point, driver_id, 
                   COUNT(*) as count, array_agg(id ORDER BY id) as ids
            FROM completed_trips 
            WHERE date >= %s AND date <= %s
            GROUP BY date, start_point, via_point, end_point, driver_id
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            """, (start_date, end_date))
            
            duplicates = cur.fetchall()
            if duplicates:
                print(f"❌ 發現 {len(duplicates)} 組重複記錄（相同日期+路線+司機）")
                for dup in duplicates:
                    date, start, via, end, driver, count, ids = dup
                    print(f"   {date}: {start}→{via}→{end} (司機{driver}) - {count}筆, IDs: {ids}")
            else:
                print("✅ 沒有發現重複記錄（相同日期+路線+司機）")
            
            # 2. 檢查 unique_code 重複
            print("\n🔍 檢查 unique_code 重複...")
            cur.execute("""
            SELECT unique_code, COUNT(*) as count, array_agg(id ORDER BY id) as ids
            FROM completed_trips 
            WHERE date >= %s AND date <= %s
            GROUP BY unique_code
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            """, (start_date, end_date))
            
            unique_duplicates = cur.fetchall()
            if unique_duplicates:
                print(f"❌ 發現 {len(unique_duplicates)} 個重複的 unique_code")
                for dup in unique_duplicates:
                    unique_code, count, ids = dup
                    print(f"   unique_code: {unique_code} - {count}筆, IDs: {ids}")
            else:
                print("✅ 沒有發現重複的 unique_code")
            
            # 3. 檢查小北路班次
            print("\n🚗 檢查小北路班次...")
            cur.execute("""
            SELECT id, date, start_point, via_point, end_point, 
                   unique_code, meter_fare, extra_fare, driver_id, created_at
            FROM completed_trips 
            WHERE date >= %s AND date <= %s
              AND start_point = '小北路' 
              AND via_point = '民德105' 
              AND end_point = '診所'
            ORDER BY date, id
            """, (start_date, end_date))
            
            xiaobei_trips = cur.fetchall()
            print(f"📊 小北路班次總數: {len(xiaobei_trips)}")
            
            for trip in xiaobei_trips:
                id, date, start, via, end, unique_code, meter, extra, driver, created = trip
                print(f"   ID: {id}, 日期: {date}")
                print(f"   unique_code: {unique_code}, 車資: {meter}+{extra}={meter+extra}")
                print(f"   司機: {driver}, 創建時間: {created}")
                print()
            
            # 4. 總體統計
            print("\n📊 上一周總體統計...")
            cur.execute("""
            SELECT COUNT(*) as total_trips,
                   COUNT(DISTINCT unique_code) as unique_trips,
                   SUM(meter_fare + extra_fare) as total_amount
            FROM completed_trips 
            WHERE date >= %s AND date <= %s
            """, (start_date, end_date))
            
            stats = cur.fetchone()
            total_trips, unique_trips, total_amount = stats
            print(f"   總班次數: {total_trips}")
            print(f"   唯一班次數: {unique_trips}")
            print(f"   總金額: {total_amount}")
            print(f"   重複率: {((total_trips - unique_trips) / total_trips * 100):.2f}%" if total_trips > 0 else "   重複率: 0%")
            
            return len(duplicates) == 0 and len(unique_duplicates) == 0
            
    except Exception as e:
        print(f"❌ 檢查 Render 資料庫時發生錯誤: {e}", file=sys.stderr)
        return False

def check_render_schema(conn):
    """檢查 Render 資料庫的 schema"""
    print("\n🔍 檢查 Render 資料庫 schema")
    print("-" * 50)
    
    try:
        with conn.cursor() as cur:
            # 檢查 completed_trips 表結構
            cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'completed_trips' 
            ORDER BY ordinal_position
            """)
            
            columns = cur.fetchall()
            print("completed_trips 表欄位:")
            for col_name, col_type in columns:
                print(f"   {col_name}: {col_type}")
            
            # 檢查是否有 unique_code 唯一約束
            cur.execute("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints 
            WHERE table_name = 'completed_trips' 
              AND constraint_type = 'UNIQUE'
            """)
            
            constraints = cur.fetchall()
            if constraints:
                print(f"\n✅ 找到 {len(constraints)} 個唯一約束:")
                for constraint_name, constraint_type in constraints:
                    print(f"   {constraint_name}: {constraint_type}")
            else:
                print("\n❌ 沒有找到唯一約束")
            
            return True
            
    except Exception as e:
        print(f"❌ 檢查 schema 時發生錯誤: {e}", file=sys.stderr)
        return False

def main():
    """主函數"""
    print("🔍 檢查 Render 生產環境資料庫")
    print("=" * 60)
    
    # 獲取上一周日期
    start_date, end_date = get_last_week_dates()
    
    # 連接 Render 資料庫
    conn = get_render_connection()
    if not conn:
        return False
    
    try:
        # 檢查 schema
        schema_ok = check_render_schema(conn)
        
        # 檢查重複記錄
        no_duplicates = check_render_duplicates(conn, start_date, end_date)
        
        print("\n📊 檢查結果總結")
        print("=" * 60)
        print(f"✅ Schema 檢查: {'通過' if schema_ok else '失敗'}")
        print(f"✅ 重複記錄檢查: {'通過' if no_duplicates else '失敗'}")
        
        if schema_ok and no_duplicates:
            print("\n🎉 Render 資料庫檢查通過！")
            print("✅ 沒有發現重複計價問題")
            print("💡 可以安全生成週報表")
            return True
        else:
            print("\n⚠️  Render 資料庫檢查發現問題！")
            print("💡 建議進一步調查")
            return False
            
    except Exception as e:
        print(f"❌ 檢查過程中發生錯誤: {e}", file=sys.stderr)
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)