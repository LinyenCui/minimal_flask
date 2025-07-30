#!/usr/bin/env python3
"""
直接從 Render 恢復 completed_trips 資料的腳本
用於在本地資料遺失時快速恢復，不依賴同步邏輯
"""
import os
import sys
import psycopg2
from psycopg2.extras import DictCursor, execute_batch
from dotenv import load_dotenv

load_dotenv()

# Render 資料庫連線資訊
RENDER_DB_CONFIG = {
    "host": os.getenv('RENDER_DB_HOST'),
    "user": os.getenv('RENDER_DB_USER'),
    "dbname": os.getenv('RENDER_DB_NAME'),
    "password": os.getenv('RENDER_DB_PASSWORD'),
    "sslmode": 'require'
}

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

def restore_completed_trips():
    """直接從 Render 恢復 completed_trips 資料"""
    print("🚀 開始直接恢復 completed_trips 資料")
    print("=" * 50)
    
    render_conn = None
    local_conn = None
    
    try:
        render_conn = get_db_connection(RENDER_DB_CONFIG, "Render")
        local_conn = get_db_connection(LOCAL_DB_CONFIG, "Local")
        
        if not render_conn or not local_conn:
            return False
        
        with local_conn.cursor() as local_cur, render_conn.cursor(cursor_factory=DictCursor) as render_cur:
            # 1. 檢查本地 completed_trips 目前狀況
            local_cur.execute("SELECT COUNT(*) FROM completed_trips;")
            local_count = local_cur.fetchone()[0]
            print(f"📊 本地 completed_trips 目前有 {local_count} 筆記錄")
            
            # 2. 從 Render 讀取所有 completed_trips 資料
            print("📥 正在從 Render 讀取所有 completed_trips 資料...")
            render_cur.execute("SELECT * FROM completed_trips ORDER BY created_at, id;")
            all_records = render_cur.fetchall()
            print(f"📊 從 Render 讀取到 {len(all_records)} 筆記錄")
            
            if not all_records:
                print("⚠️ Render 上沒有 completed_trips 資料")
                return True
            
            # 3. 清空本地 completed_trips 表
            print("🗑️ 正在清空本地 completed_trips 表...")
            local_cur.execute("TRUNCATE TABLE completed_trips RESTART IDENTITY CASCADE;")
            
            # 4. 過濾欄位（排除生成欄位和本地特有欄位）
            all_cols = [desc[0] for desc in render_cur.description]
            excluded_columns = ['actual_fare', 'total_fare', 'original_trip_id']
            filtered_cols = [col for col in all_cols if col not in excluded_columns]
            
            print(f"📋 原始欄位: {len(all_cols)} 個，過濾後: {len(filtered_cols)} 個")
            print(f"📋 過濾後欄位: {filtered_cols}")
            
            # 5. 準備插入資料
            col_indices = [all_cols.index(col) for col in filtered_cols]
            filtered_records = [[rec[i] for i in col_indices] for rec in all_records]
            
            # 6. 批量插入資料
            placeholders = "%s, " * len(filtered_cols)
            insert_sql = f"INSERT INTO completed_trips ({', '.join(filtered_cols)}) VALUES ({placeholders.strip(', ')})"
            
            print(f"💾 正在插入 {len(filtered_records)} 筆記錄到本地資料庫...")
            execute_batch(local_cur, insert_sql, filtered_records)
            
            # 7. 提交變更
            local_conn.commit()
            
            # 8. 驗證結果
            local_cur.execute("SELECT COUNT(*) FROM completed_trips;")
            final_count = local_cur.fetchone()[0]
            print(f"✅ 恢復完成！本地 completed_trips 現在有 {final_count} 筆記錄")
            
            # 9. 顯示最新幾筆記錄樣本
            local_cur.execute("SELECT id, date, start_point, end_point, driver_id, created_at FROM completed_trips ORDER BY created_at DESC LIMIT 3;")
            samples = local_cur.fetchall()
            print("\n📋 最新記錄樣本:")
            for sample in samples:
                print(f"   ID: {sample[0]}, 日期: {sample[1]}, {sample[2]} → {sample[3]}, 司機: {sample[4]}")
            
            return True
            
    except Exception as e:
        print(f"❌ 恢復過程中發生錯誤: {e}", file=sys.stderr)
        if local_conn:
            local_conn.rollback()
        return False
    finally:
        if render_conn:
            render_conn.close()
        if local_conn:
            local_conn.close()
        print("🔌 資料庫連線已關閉。")

if __name__ == "__main__":
    success = restore_completed_trips()
    exit(0 if success else 1)