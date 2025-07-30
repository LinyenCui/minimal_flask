#!/usr/bin/env python3
"""
單獨測試 incremental_sync_completed_trips 函數
"""
import os
import sys
import psycopg2
from psycopg2.extras import DictCursor, execute_batch
from dotenv import load_dotenv
import datetime

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

def check_completed_trips_count(conn, label):
    """檢查 completed_trips 記錄數"""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM completed_trips;")
        count = cur.fetchone()[0]
        print(f"🔍 {label}: completed_trips 有 {count} 筆記錄")
        return count

def incremental_sync_completed_trips(local_conn, render_conn):
    """增量同步 completed_trips 資料表，使用時間戳保護本地歷史數據"""
    table_name = "completed_trips"
    print(f"--- 開始增量同步資料表: {table_name} (基於時間戳保護本地歷史數據) ---")
    
    # 同步前檢查
    check_completed_trips_count(local_conn, "同步前")

    with local_conn.cursor() as local_cur, render_conn.cursor(cursor_factory=DictCursor) as render_cur:
        try:
            # 1. 從 Render 的 database_maintenance 表獲取上次同步時間
            render_cur.execute("SELECT value FROM database_maintenance WHERE key = 'last_completed_trips_sync';")
            last_sync_result = render_cur.fetchone()
            
            if last_sync_result:
                last_sync_time = last_sync_result['value']
                print(f"   - 上次同步時間: {last_sync_time}")
            else:
                # 如果沒有記錄，設定一個很早的時間
                last_sync_time = '2000-01-01 00:00:00'
                print("   - 沒有找到上次同步記錄，將同步所有數據")

            # 2. 從 Render 讀取所有 created_at > 上次同步時間的資料
            print(f"   - 正在從 Render 讀取 created_at > '{last_sync_time}' 的新紀錄...")
            render_cur.execute(f"SELECT * FROM {table_name} WHERE created_at > %s ORDER BY created_at, id;", (last_sync_time,))
            new_records = render_cur.fetchall()

            if not new_records:
                print("   - ✅ 在 Render 上沒有找到需要同步的新紀錄。")
                # 檢查同步後狀態
                check_completed_trips_count(local_conn, "無新記錄，同步後")
                return

            print(f"   - 從 Render 找到 {len(new_records)} 筆新紀錄需要同步。")
            
            # 檢查找到新記錄後的狀態
            check_completed_trips_count(local_conn, "找到新記錄後")

            # 3. 過濾生成欄位和本地特有欄位，避免插入錯誤
            all_cols = [desc[0] for desc in render_cur.description]
            # completed_trips: 過濾生成欄位和本地特有欄位
            if table_name == 'completed_trips':
                excluded_columns = ['actual_fare', 'total_fare', 'original_trip_id']
            else:
                excluded_columns = ['actual_fare', 'total_fare']
            filtered_cols = [col for col in all_cols if col not in excluded_columns]
            
            print(f"   - 原始欄位: {len(all_cols)} 個，過濾後: {len(filtered_cols)} 個")
            
            # 檢查欄位過濾後的狀態
            check_completed_trips_count(local_conn, "欄位過濾後")
            
            # 獲取對應的資料索引
            col_indices = [all_cols.index(col) for col in filtered_cols]
            
            # 過濾記錄資料，只包含非生成欄位
            filtered_records = [[rec[i] for i in col_indices] for rec in new_records]

            # 4. 使用 ON CONFLICT DO UPDATE 覆蓋本地資料
            print(f"   - 正在將新紀錄寫入本地，覆蓋已存在的記錄...")
            
            # 檢查準備插入前的狀態
            check_completed_trips_count(local_conn, "準備插入前")
            
            placeholders = "%s, " * len(filtered_cols)
            
            # 構建 UPDATE SET 子句（排除 id 欄位）
            update_cols = [col for col in filtered_cols if col != 'id']
            update_set = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_cols])
            
            insert_sql = f"""INSERT INTO {table_name} ({', '.join(filtered_cols)}) 
                            VALUES ({placeholders.strip(', ')}) 
                            ON CONFLICT (id) DO UPDATE SET {update_set}"""
            
            print(f"   - 調試：SQL語句前50字符: {insert_sql[:50]}...")
            print(f"   - 調試：準備插入 {len(filtered_records)} 筆記錄")
            print(f"   - 調試：欄位列表: {filtered_cols}")
            
            try:
                # 執行批量插入
                execute_batch(local_cur, insert_sql, filtered_records)
                
                # 檢查插入後但提交前的狀態
                check_completed_trips_count(local_conn, "插入後，提交前")
                
                # 提交事務
                local_conn.commit()
                print(f"   - ✅ 批量插入完成，處理 {len(filtered_records)} 筆紀錄。")
                
                # 檢查提交後的狀態
                check_completed_trips_count(local_conn, "提交後")
                    
            except Exception as insert_error:
                print(f"   - ❌ 插入錯誤: {insert_error}")
                local_conn.rollback()
                check_completed_trips_count(local_conn, "插入錯誤，回滾後")
                raise
            
            # 5. 更新 Render 的同步時間戳
            current_time = datetime.datetime.now().isoformat()
            render_cur.execute("""
                UPDATE database_maintenance 
                SET value = %s, timestamp = CURRENT_TIMESTAMP 
                WHERE key = 'last_completed_trips_sync'
            """, (current_time,))
            render_conn.commit()
            print(f"   - ✅ 已更新同步時間戳: {current_time}")
            
            # 最終檢查
            check_completed_trips_count(local_conn, "最終狀態")

        except Exception as e:
            local_conn.rollback()
            print(f"❌ 增量同步 '{table_name}' 時發生錯誤: {e}", file=sys.stderr)
            check_completed_trips_count(local_conn, "異常後，回滾後")
            raise

def main():
    """主函數"""
    print("🚀 測試 incremental_sync_completed_trips 函數")
    print("=" * 60)

    render_conn = None
    local_conn = None
    
    try:
        render_conn = psycopg2.connect(**RENDER_DB_CONFIG)
        local_conn = psycopg2.connect(**LOCAL_DB_CONFIG)
        
        print("✅ 資料庫連線成功")
        
        # 執行增量同步測試
        incremental_sync_completed_trips(local_conn, render_conn)
        
        return True

    except Exception as e:
        print(f"\\n❌ 測試失敗: {e}", file=sys.stderr)
        return False
    finally:
        if render_conn:
            render_conn.close()
        if local_conn:
            local_conn.close()
        print("🔌 資料庫連線已關閉。")

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)