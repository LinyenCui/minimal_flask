#!/usr/bin/env python3
"""
檢查上一周 completed_trips 重複計價問題
1. 查詢上一周的所有班次
2. 檢查是否有重複的 unique_code
3. 分析重複原因和影響
4. 提供修復建議
"""
import os
import sys
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict

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

def get_last_week_dates():
    """獲取上一周的日期範圍"""
    today = datetime.now().date()
    # 計算上一周的開始和結束日期
    last_week_end = today - timedelta(days=today.weekday() + 1)  # 上週日
    last_week_start = last_week_end - timedelta(days=6)  # 上週一
    
    print(f"📅 上一周日期範圍: {last_week_start} 到 {last_week_end}")
    return last_week_start, last_week_end

def check_duplicate_unique_codes(conn, start_date, end_date):
    """檢查重複的 unique_code"""
    print("\n🔍 檢查重複的 unique_code")
    print("-" * 50)
    
    try:
        with conn.cursor() as cur:
            # 查詢上一周所有班次
            query = """
            SELECT unique_code, COUNT(*) as count, 
                   array_agg(id ORDER BY id) as ids,
                   array_agg(date ORDER BY id) as dates,
                   array_agg(start_point ORDER BY id) as start_points,
                   array_agg(via_point ORDER BY id) as via_points,
                   array_agg(end_point ORDER BY id) as end_points,
                   array_agg(meter_fare ORDER BY id) as meter_fares,
                   array_agg(extra_fare ORDER BY id) as extra_fares
            FROM completed_trips 
            WHERE date >= %s AND date <= %s
            GROUP BY unique_code
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            """
            
            cur.execute(query, (start_date, end_date))
            duplicates = cur.fetchall()
            
            if duplicates:
                print(f"❌ 發現 {len(duplicates)} 個重複的 unique_code")
                print("\n📊 重複詳情:")
                
                total_duplicate_records = 0
                for dup in duplicates:
                    unique_code, count, ids, dates, start_points, via_points, end_points, meter_fares, extra_fares = dup
                    total_duplicate_records += count - 1  # 減去1，因為只計算重複的部分
                    
                    print(f"\n🔴 unique_code: {unique_code}")
                    print(f"   重複次數: {count}")
                    print(f"   記錄ID: {ids}")
                    print(f"   日期: {dates}")
                    print(f"   路線: {start_points[0]} → {via_points[0]} → {end_points[0]}")
                    print(f"   車資: {meter_fares[0]} + {extra_fares[0]}")
                    
                    # 檢查是否為小北路班次
                    if start_points[0] == '小北路' and via_points[0] == '民德105' and end_points[0] == '診所':
                        print("   ⚠️  這是小北路經民德105到診所的班次！")
                
                print(f"\n📈 統計:")
                print(f"   重複的 unique_code 數量: {len(duplicates)}")
                print(f"   重複記錄總數: {total_duplicate_records}")
                
                return duplicates
            else:
                print("✅ 沒有發現重複的 unique_code")
                return []
                
    except Exception as e:
        print(f"❌ 檢查重複 unique_code 時發生錯誤: {e}", file=sys.stderr)
        return []

def check_duplicate_trip_details(conn, start_date, end_date):
    """檢查重複的班次詳情（即使 unique_code 不同）"""
    print("\n🔍 檢查重複的班次詳情")
    print("-" * 50)
    
    try:
        with conn.cursor() as cur:
            # 查詢重複的班次詳情
            query = """
            SELECT start_point, via_point, end_point, date, 
                   COUNT(*) as count,
                   array_agg(id ORDER BY id) as ids,
                   array_agg(unique_code ORDER BY id) as unique_codes,
                   array_agg(meter_fare ORDER BY id) as meter_fares,
                   array_agg(extra_fare ORDER BY id) as extra_fares
            FROM completed_trips 
            WHERE date >= %s AND date <= %s
            GROUP BY start_point, via_point, end_point, date
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            """
            
            cur.execute(query, (start_date, end_date))
            duplicates = cur.fetchall()
            
            if duplicates:
                print(f"❌ 發現 {len(duplicates)} 組重複的班次詳情")
                print("\n📊 重複班次詳情:")
                
                for dup in duplicates:
                    start_point, via_point, end_point, date, count, ids, unique_codes, meter_fares, extra_fares = dup
                    
                    print(f"\n🔴 班次: {start_point} → {via_point} → {end_point} ({date})")
                    print(f"   重複次數: {count}")
                    print(f"   記錄ID: {ids}")
                    print(f"   unique_codes: {unique_codes}")
                    print(f"   車資: {meter_fares}")
                    
                    # 檢查是否為小北路班次
                    if start_point == '小北路' and via_point == '民德105' and end_point == '診所':
                        print("   ⚠️  這是小北路經民德105到診所的班次！")
                        print("   💰 這會導致重複計價！")
                
                return duplicates
            else:
                print("✅ 沒有發現重複的班次詳情")
                return []
                
    except Exception as e:
        print(f"❌ 檢查重複班次詳情時發生錯誤: {e}", file=sys.stderr)
        return []

def analyze_xiaobei_trips(conn, start_date, end_date):
    """專門分析小北路班次"""
    print("\n🚗 專門分析小北路班次")
    print("-" * 50)
    
    try:
        with conn.cursor() as cur:
            # 查詢小北路班次
            query = """
            SELECT id, date, start_point, via_point, end_point, 
                   unique_code, meter_fare, extra_fare, category, driver_id
            FROM completed_trips 
            WHERE date >= %s AND date <= %s
              AND start_point = '小北路' 
              AND via_point = '民德105' 
              AND end_point = '診所'
            ORDER BY date, id
            """
            
            cur.execute(query, (start_date, end_date))
            xiaobei_trips = cur.fetchall()
            
            if xiaobei_trips:
                print(f"📊 小北路班次總數: {len(xiaobei_trips)}")
                print("\n📋 小北路班次詳情:")
                
                for trip in xiaobei_trips:
                    id, date, start_point, via_point, end_point, unique_code, meter_fare, extra_fare, category, driver_id = trip
                    print(f"   ID: {id}, 日期: {date}, unique_code: {unique_code}")
                    print(f"   路線: {start_point} → {via_point} → {end_point}")
                    print(f"   車資: {meter_fare} + {extra_fare} = {meter_fare + extra_fare}")
                    print(f"   司機: {driver_id}, 類別: {category}")
                    print()
                
                # 檢查是否有重複
                unique_codes = [trip[5] for trip in xiaobei_trips]
                if len(unique_codes) != len(set(unique_codes)):
                    print("❌ 發現小北路班次有重複的 unique_code！")
                    return True
                else:
                    print("✅ 小北路班次沒有重複的 unique_code")
                    return False
            else:
                print("ℹ️  上一周沒有小北路班次")
                return False
                
    except Exception as e:
        print(f"❌ 分析小北路班次時發生錯誤: {e}", file=sys.stderr)
        return False

def calculate_financial_impact(duplicates):
    """計算財務影響"""
    print("\n💰 計算財務影響")
    print("-" * 50)
    
    if not duplicates:
        print("✅ 沒有重複記錄，財務影響為 0")
        return
    
    total_duplicate_amount = 0
    for dup in duplicates:
        unique_code, count, ids, dates, start_points, via_points, end_points, meter_fares, extra_fares = dup
        # 計算重複的金額（減去1，因為只計算重複的部分）
        duplicate_count = count - 1
        for i in range(duplicate_count):
            total_duplicate_amount += meter_fares[i] + extra_fares[i]
    
    print(f"💸 重複計價總金額: {total_duplicate_amount} 元")
    print(f"📊 重複記錄數: {sum(dup[1] - 1 for dup in duplicates)} 筆")
    
    if total_duplicate_amount > 0:
        print("⚠️  這會影響週報表的準確性！")

def provide_cleanup_suggestions(duplicates):
    """提供清理建議"""
    print("\n🔧 清理建議")
    print("-" * 50)
    
    if not duplicates:
        print("✅ 沒有需要清理的重複記錄")
        return
    
    print("📋 建議的清理步驟:")
    print("1. 備份 completed_trips 表")
    print("2. 對於每個重複的 unique_code，保留最新的記錄")
    print("3. 刪除重複的記錄")
    print("4. 驗證清理結果")
    
    print("\n💻 清理 SQL 範例:")
    for dup in duplicates:
        unique_code, count, ids, dates, start_points, via_points, end_points, meter_fares, extra_fares = dup
        print(f"-- 清理 unique_code: {unique_code}")
        print(f"DELETE FROM completed_trips WHERE id IN ({', '.join(map(str, ids[1:]))});")

def main():
    """主函數"""
    print("🔍 檢查上一周 completed_trips 重複計價問題")
    print("=" * 60)
    
    # 獲取上一周日期
    start_date, end_date = get_last_week_dates()
    
    # 連接資料庫
    local_conn = get_db_connection(LOCAL_DB_CONFIG, "Local")
    if not local_conn:
        return False
    
    try:
        # 檢查重複的 unique_code
        unique_code_duplicates = check_duplicate_unique_codes(local_conn, start_date, end_date)
        
        # 檢查重複的班次詳情
        trip_detail_duplicates = check_duplicate_trip_details(local_conn, start_date, end_date)
        
        # 專門分析小北路班次
        xiaobei_has_duplicates = analyze_xiaobei_trips(local_conn, start_date, end_date)
        
        # 計算財務影響
        calculate_financial_impact(unique_code_duplicates)
        
        # 提供清理建議
        provide_cleanup_suggestions(unique_code_duplicates)
        
        print("\n📊 檢查結果總結")
        print("=" * 60)
        print(f"✅ 重複的 unique_code: {len(unique_code_duplicates)} 個")
        print(f"✅ 重複的班次詳情: {len(trip_detail_duplicates)} 組")
        print(f"✅ 小北路班次重複: {'是' if xiaobei_has_duplicates else '否'}")
        
        if unique_code_duplicates or trip_detail_duplicates or xiaobei_has_duplicates:
            print("\n⚠️  發現重複計價問題！")
            print("💡 建議立即清理重複記錄，避免影響週報表")
            return False
        else:
            print("\n✅ 沒有發現重複計價問題")
            print("💡 可以安全生成週報表")
            return True
            
    except Exception as e:
        print(f"❌ 檢查過程中發生錯誤: {e}", file=sys.stderr)
        return False
    finally:
        if local_conn:
            local_conn.close()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)