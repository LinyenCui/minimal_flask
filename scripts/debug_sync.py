#!/usr/bin/env python3
"""
調試同步腳本 - 在各個階段檢查 completed_trips 記錄數
"""
import os
import sys
import psycopg2
from psycopg2.extras import DictCursor, execute_batch
from dotenv import load_dotenv

load_dotenv()

# 本地資料庫連線資訊
LOCAL_DB_CONFIG = {
    "host": os.getenv('LOCAL_DB_HOST', 'localhost'),
    "user": os.getenv('LOCAL_DB_USER', ''),
    "dbname": os.getenv('LOCAL_DB_NAME', 'dispatch_db'),
    "password": os.getenv('LOCAL_DB_PASSWORD', '')
}

# Render 資料庫連線資訊
RENDER_DB_CONFIG = {
    "host": os.getenv('RENDER_DB_HOST'),
    "user": os.getenv('RENDER_DB_USER'),
    "dbname": os.getenv('RENDER_DB_NAME'),
    "password": os.getenv('RENDER_DB_PASSWORD'),
    "sslmode": 'require'
}

def check_completed_trips_count(conn, label):
    """檢查 completed_trips 記錄數"""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM completed_trips;")
        count = cur.fetchone()[0]
        print(f"🔍 {label}: completed_trips 有 {count} 筆記錄")
        return count

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

def debug_sync_process():
    """調試同步過程"""
    print("🚀 開始調試同步過程")
    print("=" * 50)
    
    # 先恢復資料
    print("📥 恢復 completed_trips 資料...")
    os.system("python3 scripts/restore_completed_trips.py")
    
    local_conn = get_db_connection(LOCAL_DB_CONFIG, "Local")
    render_conn = get_db_connection(RENDER_DB_CONFIG, "Render")
    
    if not local_conn or not render_conn:
        return False
    
    try:
        # 檢查初始狀態
        initial_count = check_completed_trips_count(local_conn, "初始狀態")
        
        # 模擬同步過程的每一步
        print("\n--- 步驟 1: 完全同步其他表 ---")
        
        # 模擬 drivers 同步
        print("同步 drivers...")
        check_completed_trips_count(local_conn, "drivers 同步後")
        
        # 模擬 customers 同步
        print("同步 customers...")
        check_completed_trips_count(local_conn, "customers 同步後")
        
        # 模擬 fixed_schedules 同步
        print("同步 fixed_schedules...")
        check_completed_trips_count(local_conn, "fixed_schedules 同步後")
        
        # 模擬 trips 同步
        print("同步 trips...")
        check_completed_trips_count(local_conn, "trips 同步後")
        
        print("\n--- 步驟 2: completed_trips 增量同步 ---")
        
        # 檢查 Render 上的同步時間戳
        with render_conn.cursor() as render_cur:
            render_cur.execute("SELECT value FROM database_maintenance WHERE key = 'last_completed_trips_sync';")
            result = render_cur.fetchone()
            if result:
                last_sync_time = result[0]
                print(f"Render 上次同步時間: {last_sync_time}")
                
                # 查詢是否有新記錄
                render_cur.execute("SELECT COUNT(*) FROM completed_trips WHERE created_at > %s;", (last_sync_time,))
                new_count = render_cur.fetchone()[0]
                print(f"Render 上有 {new_count} 筆新記錄")
        
        check_completed_trips_count(local_conn, "completed_trips 同步後")
        
        print("\n--- 步驟 3: database_maintenance 同步 ---")
        print("同步 database_maintenance...")
        check_completed_trips_count(local_conn, "database_maintenance 同步後")
        
        print("\n--- 步驟 4: 序列校準 ---")
        
        # 校準 completed_trips 序列
        print("校準 completed_trips 序列...")
        with local_conn.cursor() as local_cur:
            try:
                local_cur.execute("SELECT setval('completed_trips_id_seq', COALESCE((SELECT MAX(id) FROM completed_trips), 1));")
                local_conn.commit()
                print("序列校準完成")
            except Exception as e:
                print(f"序列校準錯誤: {e}")
                local_conn.rollback()
        
        final_count = check_completed_trips_count(local_conn, "序列校準後")
        
        print(f"\n📊 總結:")
        print(f"   初始記錄數: {initial_count}")
        print(f"   最終記錄數: {final_count}")
        print(f"   記錄變化: {final_count - initial_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ 調試過程中發生錯誤: {e}", file=sys.stderr)
        return False
    finally:
        if render_conn:
            render_conn.close()
        if local_conn:
            local_conn.close()
        print("🔌 資料庫連線已關閉。")

if __name__ == "__main__":
    success = debug_sync_process()
    exit(0 if success else 1)