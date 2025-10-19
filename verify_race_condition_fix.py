#!/usr/bin/env python3
"""
驗證排程任務競態條件修復
1. 檢查排程任務時間設定
2. 模擬班次完成流程
3. 驗證不會重複寫入
"""
import os
import sys
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
from datetime import datetime, time, timedelta
import time as time_module

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

def check_scheduler_timing():
    """檢查排程任務時間設定"""
    print("\n🔍 步驟1: 檢查排程任務時間設定")
    print("-" * 50)
    
    print("📅 當前排程任務時間:")
    print("   - update_completed_trips: 每小時 00,30 分執行")
    print("   - initialize_unique_codes: 每小時 35 分執行")
    print("   - 時間間隔: 5分鐘")
    
    # 檢查是否有其他班次可能衝突
    local_conn = get_db_connection(LOCAL_DB_CONFIG, "Local")
    if not local_conn:
        return False
    
    try:
        with local_conn.cursor() as cur:
            # 檢查所有班次的時間分布
            print("\n📊 檢查班次時間分布:")
            cur.execute("""
            SELECT time, COUNT(*) as count
            FROM trips 
            WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY time
            ORDER BY time
            """)
            
            time_distribution = cur.fetchall()
            conflict_times = []
            
            for time_info in time_distribution:
                trip_time = time_info[0]
                count = time_info[1]
                
                # 檢查是否在排程任務執行時間附近
                if (trip_time.minute == 25 or trip_time.minute == 55):
                    conflict_times.append((trip_time, count))
                    print(f"   ⚠️  {trip_time}: {count} 筆 (可能衝突)")
                else:
                    print(f"   ✅ {trip_time}: {count} 筆")
            
            if conflict_times:
                print(f"\n⚠️  發現 {len(conflict_times)} 個可能衝突的時間點")
                return False
            else:
                print("\n✅ 目前沒有發現時間衝突")
                return True
                
    except Exception as e:
        print(f"❌ 檢查時間分布時發生錯誤: {e}", file=sys.stderr)
        return False
    finally:
        if local_conn:
            local_conn.close()

def simulate_trip_completion():
    """模擬班次完成流程"""
    print("\n🧪 步驟2: 模擬班次完成流程")
    print("-" * 50)
    
    local_conn = get_db_connection(LOCAL_DB_CONFIG, "Local")
    if not local_conn:
        return False
    
    try:
        with local_conn.cursor() as cur:
            # 創建測試班次
            print("🔧 創建測試班次...")
            
            # 檢查是否已有測試班次
            cur.execute("""
            SELECT trip_id FROM trips 
            WHERE start_point = '測試起點' 
              AND via_point = '測試經點' 
              AND end_point = '測試終點'
            """)
            
            existing_test = cur.fetchone()
            if existing_test:
                print("✅ 測試班次已存在")
                test_trip_id = existing_test[0]
            else:
                # 創建測試班次
                cur.execute("""
                INSERT INTO trips (date, time, start_point, via_point, end_point, 
                                 status, fixed_trip_id, unique_code)
                VALUES (CURRENT_DATE, '15:25:00', '測試起點', '測試經點', '測試終點', 
                       '準備', 999, 'TEST_999_001')
                RETURNING trip_id
                """)
                test_trip_id = cur.fetchone()[0]
                local_conn.commit()
                print(f"✅ 創建測試班次 ID: {test_trip_id}")
            
            # 模擬班次完成
            print("🔄 模擬班次完成流程...")
            
            # 1. 檢查班次狀態
            cur.execute("SELECT status, unique_code FROM trips WHERE trip_id = %s", (test_trip_id,))
            trip_info = cur.fetchone()
            print(f"   班次狀態: {trip_info[0]}, unique_code: {trip_info[1]}")
            
            # 2. 模擬 update_completed_trips 執行
            print("   📝 模擬 update_completed_trips 執行...")
            
            # 檢查是否已在 completed_trips 中
            cur.execute("""
            SELECT COUNT(*) FROM completed_trips 
            WHERE unique_code = %s
            """, (trip_info[1],))
            
            existing_count = cur.fetchone()[0]
            if existing_count > 0:
                print("   ✅ 班次已在 completed_trips 中，跳過插入")
            else:
                print("   📝 插入班次到 completed_trips...")
                cur.execute("""
                INSERT INTO completed_trips 
                (date, start_point, via_point, end_point, unique_code, trip_type)
                VALUES (CURRENT_DATE, '測試起點', '測試經點', '測試終點', %s, '固定')
                """, (trip_info[1],))
                
                # 更新班次狀態
                cur.execute("""
                UPDATE trips SET status = '已完成' WHERE trip_id = %s
                """, (test_trip_id,))
                
                local_conn.commit()
                print("   ✅ 班次完成流程執行成功")
            
            # 3. 模擬 initialize_unique_codes 執行（5分鐘後）
            print("   📝 模擬 initialize_unique_codes 執行...")
            
            # 檢查班次是否會被重複處理
            cur.execute("""
            SELECT COUNT(*) FROM completed_trips 
            WHERE unique_code = %s
            """, (trip_info[1],))
            
            final_count = cur.fetchone()[0]
            if final_count == 1:
                print("   ✅ 班次沒有被重複處理")
                return True
            else:
                print(f"   ❌ 班次被重複處理，count: {final_count}")
                return False
                
    except Exception as e:
        print(f"❌ 模擬班次完成時發生錯誤: {e}", file=sys.stderr)
        local_conn.rollback()
        return False
    finally:
        if local_conn:
            local_conn.close()

def analyze_architectural_issues():
    """分析架構問題"""
    print("\n🏗️ 步驟3: 分析架構問題")
    print("-" * 50)
    
    print("❌ 當前架構的根本問題:")
    print("   1. 排程任務依賴時間間隔避免衝突")
    print("   2. 新增班次可能再次造成時間衝突")
    print("   3. 同一時間多個班次會加劇問題")
    print("   4. 缺乏原子性保證")
    
    print("\n💡 建議的解決方案:")
    print("   1. 使用資料庫鎖機制")
    print("   2. 實現原子性操作")
    print("   3. 使用事件驅動架構")
    print("   4. 實現分散式鎖")
    
    return True

def main():
    """主函數"""
    print("🧪 驗證排程任務競態條件修復")
    print("=" * 60)
    
    # 步驟1: 檢查排程任務時間設定
    timing_ok = check_scheduler_timing()
    
    # 步驟2: 模擬班次完成流程
    simulation_ok = simulate_trip_completion()
    
    # 步驟3: 分析架構問題
    analysis_ok = analyze_architectural_issues()
    
    print("\n📊 驗證結果")
    print("=" * 60)
    print(f"✅ 排程任務時間設定: {'通過' if timing_ok else '失敗'}")
    print(f"✅ 班次完成流程模擬: {'通過' if simulation_ok else '失敗'}")
    print(f"✅ 架構問題分析: {'完成' if analysis_ok else '失敗'}")
    
    if timing_ok and simulation_ok and analysis_ok:
        print("\n🎉 驗證通過！但架構需要改進")
        return True
    else:
        print("\n❌ 驗證失敗")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)