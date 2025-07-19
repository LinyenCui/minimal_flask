#!/usr/bin/env python3
"""
Render 資料庫同步到本地的自動化腳本
混合模式版本 (最終版):
- completed_trips: 使用日期作為錨點進行增量同步，保留本地歷史。
- 其他資料表: 完全覆蓋，與 Render 保持一致。
- 內建序列自動校準，無需外部工具。
"""
import os
import sys
import datetime
import psycopg2
from psycopg2.extras import DictCursor, execute_batch
from dotenv import load_dotenv

# --- 設定 ---
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

# --- 要同步的資料表 ---

# 增量同步 (只添加新紀錄)
# 這個列表目前是硬編碼為 completed_trips，由專門的函式處理
# INCREMENTAL_SYNC_TABLES = ["completed_trips"]

# 完全覆蓋同步 (清空本地，再從 Render 複製所有資料)
FULL_SYNC_TABLES = [
    "drivers",
    "customers",
    "fixed_schedules",
    "trips",
    "users"
    # ... 請根據您的需求，將其他需要完全同步的資料表加到這裡
]


# --- 核心邏輯 ---

def get_db_connection(config, db_type=""):
    """建立資料庫連線"""
    try:
        print(f"🔌 正在連接到 {db_type} 資料庫 ({config.get('host')})...")
        conn = psycopg2.connect(**config)
        print(f"✅ 成功連接到 {db_type} 資料庫。")
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ 無法連接到 {db_type} 資料庫: {e}", file=sys.stderr)
        print("   請檢查您的 .env 設定以及資料庫服務是否正在運行。", file=sys.stderr)
        return None

def calibrate_sequence(conn, table_name, id_column='id'):
    """校準指定資料表的序列計數器"""
    sequence_name = f"{table_name}_{id_column}_seq"
    with conn.cursor() as cur:
        try:
            print(f"   - 正在校準序列 '{sequence_name}'...")
            # 使用 COALESCE 處理空表的情況，如果沒有最大ID，就設為1
            cur.execute(f"SELECT setval('{sequence_name}', COALESCE((SELECT MAX({id_column}) FROM {table_name}), 1));")
            conn.commit()
            print(f"   - ✅ 序列 '{sequence_name}' 已校準。")
        except psycopg2.errors.UndefinedTable:
             print(f"   - ⚠️ 找不到序列 '{sequence_name}'，跳過校準。可能是因為資料表沒有使用標準序列。")
             conn.rollback()
        except Exception as e:
            print(f"❌ 校準序列 '{sequence_name}' 時發生錯誤: {e}", file=sys.stderr)
            conn.rollback()
            raise

def truncate_and_copy(local_conn, render_conn, table_name):
    """清空本地資料表，並從 Render 完整複製資料"""
    print(f"--- 開始完全同步資料表: {table_name} ---")
    
    with local_conn.cursor() as local_cur, render_conn.cursor(cursor_factory=DictCursor) as render_cur:
        try:
            print(f"   - 正在從 Render 讀取 '{table_name}'...")
            render_cur.execute(f"SELECT * FROM {table_name};")
            records = render_cur.fetchall()
            
            print(f"   - 正在清空本地 '{table_name}'...")
            local_cur.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE;")

            if not records:
                print(f"   - '{table_name}' 在 Render 上沒有資料，本地資料表已清空。")
                local_conn.commit()
                return

            print(f"   - 從 Render 讀取了 {len(records)} 筆紀錄，正在寫入本地...")
            cols = [desc[0] for desc in render_cur.description]
            placeholders = "%s, " * len(cols)
            insert_sql = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders.strip(', ')})"
            
            execute_batch(local_cur, insert_sql, [tuple(rec) for rec in records])
            local_conn.commit()
            print(f"   ✅ 資料表 '{table_name}' 完全同步成功。")

        except Exception as e:
            local_conn.rollback()
            print(f"❌ 同步資料表 '{table_name}' 時發生錯誤: {e}", file=sys.stderr)
            raise

def incremental_sync_completed_trips(local_conn, render_conn):
    """使用日期作為錨點，增量同步 completed_trips 資料表"""
    table_name = "completed_trips"
    print(f"--- 開始增量同步資料表: {table_name} ---")

    with local_conn.cursor() as local_cur, render_conn.cursor(cursor_factory=DictCursor) as render_cur:
        try:
            # 1. 獲取本地最新的紀錄日期
            local_cur.execute(f"SELECT MAX(date) FROM {table_name};")
            last_local_date = local_cur.fetchone()[0]
            
            if last_local_date is None:
                # 如果本地沒有任何紀錄，就從一個很早的日期開始
                last_local_date = datetime.date(2000, 1, 1)
            print(f"   - 本地最新的 '{table_name}' 日期: {last_local_date}")

            # 2. 從 Render 讀取所有日期大於等於本地最新日期的資料
            print(f"   - 正在從 Render 讀取 date >= '{last_local_date}' 的新紀錄...")
            render_cur.execute(f"SELECT * FROM {table_name} WHERE date >= %s ORDER BY date, id;", (last_local_date,))
            new_records = render_cur.fetchall()

            if not new_records:
                print("   - ✅ 在 Render 上沒有找到需要同步的新紀錄。")
                return

            print(f"   - 從 Render 找到 {len(new_records)} 筆可能需要同步的紀錄。")

            # 3. 使用 ON CONFLICT DO NOTHING 將新資料優雅地寫入本地
            print(f"   - 正在將新紀錄寫入本地，並自動跳過已存在的紀錄...")
            cols = [desc[0] for desc in render_cur.description]
            placeholders = "%s, " * len(cols)
            # 關鍵：ON CONFLICT (id) DO NOTHING
            insert_sql = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders.strip(', ')}) ON CONFLICT (id) DO NOTHING"
            
            execute_batch(local_cur, insert_sql, [tuple(rec) for rec in new_records])
            inserted_count = local_cur.rowcount
            local_conn.commit()
            print(f"   - ✅ 成功插入 {inserted_count} 筆新紀錄。({len(new_records) - inserted_count} 筆已存在)")

        except Exception as e:
            local_conn.rollback()
            print(f"❌ 增量同步 '{table_name}' 時發生錯誤: {e}", file=sys.stderr)
            raise

def main():
    """主函數"""
    print("🚀 開始 Render 資料庫混合模式同步流程")
    print("=" * 60)

    if not all(RENDER_DB_CONFIG.values()):
        print("❌ 請在 .env 文件中設定所有 Render 資料庫連線資訊。", file=sys.stderr)
        return False

    render_conn = None
    local_conn = None
    
    try:
        render_conn = get_db_connection(RENDER_DB_CONFIG, "Render")
        local_conn = get_db_connection(LOCAL_DB_CONFIG, "Local")

        if not render_conn or not local_conn:
            return False

        # 步驟 1: 執行完全覆蓋同步
        for table in FULL_SYNC_TABLES:
            truncate_and_copy(local_conn, render_conn, table)
        
        # 步驟 2: 執行增量同步
        incremental_sync_completed_trips(local_conn, render_conn)

        # 步驟 3: 校準所有相關資料表的序列
        print("--- 開始校準本地資料庫序列 ---")
        for table in FULL_SYNC_TABLES:
            # trips 表的 ID 欄位名是 trip_id
            id_column = 'trip_id' if table == 'trips' else 'id'
            calibrate_sequence(local_conn, table, id_column)
        
        calibrate_sequence(local_conn, "completed_trips")

        print("\n🎉 同步成功完成！")
        print("   - `completed_trips` 已基於日期增量更新。")
        print("   - 其他指定資料表已與 Render 完全同步。")
        print("   - 所有本地資料庫序列已自動校準。")
        return True

    except Exception as e:
        print(f"\n❌ 同步流程因嚴重錯誤而中止: {e}", file=sys.stderr)
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
