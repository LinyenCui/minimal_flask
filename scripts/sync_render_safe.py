#!/usr/bin/env python3
"""
Render 資料庫安全同步腳本
核心原則：completed_trips 完全獨立，不受其他表同步影響
- completed_trips: 使用日期錨點進行增量同步，永不清空
- 其他資料表: 完全覆蓋同步，但不影響 completed_trips
"""
import os
import sys
import datetime
import psycopg2
from psycopg2.extras import DictCursor, execute_batch
from dotenv import load_dotenv

load_dotenv()

# 資料庫連線設定
RENDER_DB_CONFIG = {
    "host": os.getenv('RENDER_DB_HOST'),
    "user": os.getenv('RENDER_DB_USER'),
    "dbname": os.getenv('RENDER_DB_NAME'),
    "password": os.getenv('RENDER_DB_PASSWORD'),
    "sslmode": 'require'
}

LOCAL_DB_CONFIG = {
    "host": os.getenv('LOCAL_DB_HOST', 'localhost'),
    "user": os.getenv('LOCAL_DB_USER', ''),
    "dbname": os.getenv('LOCAL_DB_NAME', 'dispatch_db'),
    "password": os.getenv('LOCAL_DB_PASSWORD', '')
}

# 需要完全同步的表（不包含 completed_trips）
SYNC_TABLES = [
    "drivers",
    "customers", 
    "fixed_schedules",
    "trips"
]

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

def safe_sync_table(local_conn, render_conn, table_name):
    """安全地同步單個表，不影響 completed_trips"""
    print(f"--- 同步表: {table_name} ---")
    
    with local_conn.cursor() as local_cur, render_conn.cursor(cursor_factory=DictCursor) as render_cur:
        try:
            # 從 Render 讀取資料
            render_cur.execute(f"SELECT * FROM {table_name};")
            records = render_cur.fetchall()
            print(f"   - 從 Render 讀取 {len(records)} 筆記錄")
            
            if not records:
                print(f"   - {table_name} 沒有資料")
                return
            
            # 暫時禁用外鍵約束
            local_cur.execute("SET session_replication_role = replica;")
            
            # 清空表
            local_cur.execute(f"DELETE FROM {table_name};")
            
            # 重置序列
            try:
                if table_name == 'trips':
                    local_cur.execute(f"ALTER SEQUENCE {table_name}_trip_id_seq RESTART WITH 1;")
                else:
                    local_cur.execute(f"ALTER SEQUENCE {table_name}_id_seq RESTART WITH 1;")
            except Exception:
                pass
            
            # 準備插入
            all_cols = [desc[0] for desc in render_cur.description]
            generated_columns = ['actual_fare', 'total_fare']
            filtered_cols = [col for col in all_cols if col not in generated_columns]
            col_indices = [all_cols.index(col) for col in filtered_cols]
            filtered_records = [[rec[i] for i in col_indices] for rec in records]
            
            # 插入資料
            placeholders = "%s, " * len(filtered_cols)
            insert_sql = f"INSERT INTO {table_name} ({', '.join(filtered_cols)}) VALUES ({placeholders.strip(', ')})"
            execute_batch(local_cur, insert_sql, filtered_records)
            
            # 恢復外鍵約束
            local_cur.execute("SET session_replication_role = DEFAULT;")
            
            local_conn.commit()
            print(f"   ✅ {table_name} 同步完成")
            
        except Exception as e:
            local_conn.rollback()
            print(f"❌ 同步 {table_name} 失敗: {e}", file=sys.stderr)
            raise

def incremental_sync_completed_trips(local_conn, render_conn):
    """增量同步 completed_trips，基於日期錨點"""
    print("--- 增量同步 completed_trips ---")
    
    with local_conn.cursor() as local_cur, render_conn.cursor(cursor_factory=DictCursor) as render_cur:
        try:
            # 檢查本地最新日期
            local_cur.execute("SELECT MAX(date) FROM completed_trips;")
            last_local_date = local_cur.fetchone()[0]
            
            if last_local_date is None:
                last_local_date = datetime.date(2000, 1, 1)
            
            print(f"   - 本地最新日期: {last_local_date}")
            
            # 從 Render 讀取新資料
            render_cur.execute("SELECT * FROM completed_trips WHERE date >= %s ORDER BY date, id;", (last_local_date,))
            new_records = render_cur.fetchall()
            
            if not new_records:
                print("   - 沒有新資料需要同步")
                return
            
            print(f"   - 找到 {len(new_records)} 筆可能的新記錄")
            
            # 過濾欄位
            all_cols = [desc[0] for desc in render_cur.description]
            generated_columns = ['actual_fare', 'total_fare']
            filtered_cols = [col for col in all_cols if col not in generated_columns]
            col_indices = [all_cols.index(col) for col in filtered_cols]
            filtered_records = [[rec[i] for i in col_indices] for rec in new_records]
            
            # 插入新資料（跳過重複）
            placeholders = "%s, " * len(filtered_cols)
            insert_sql = f"INSERT INTO completed_trips ({', '.join(filtered_cols)}) VALUES ({placeholders.strip(', ')}) ON CONFLICT (id) DO NOTHING"
            
            execute_batch(local_cur, insert_sql, filtered_records)
            inserted_count = local_cur.rowcount
            local_conn.commit()
            
            print(f"   ✅ completed_trips 同步完成，新增 {inserted_count} 筆記錄")
            
        except Exception as e:
            local_conn.rollback()
            print(f"❌ completed_trips 同步失敗: {e}", file=sys.stderr)
            raise

def calibrate_sequences(local_conn):
    """校準序列"""
    print("--- 校準序列 ---")
    
    with local_conn.cursor() as cur:
        for table in SYNC_TABLES + ["completed_trips"]:
            try:
                if table == 'trips':
                    seq_name = f"{table}_trip_id_seq"
                    col_name = "trip_id"
                else:
                    seq_name = f"{table}_id_seq"
                    col_name = "id"
                
                cur.execute(f"SELECT setval('{seq_name}', COALESCE((SELECT MAX({col_name}) FROM {table}), 1));")
                print(f"   ✅ {seq_name} 已校準")
            except Exception as e:
                print(f"   ⚠️ {table} 序列校準跳過: {e}")
        
        local_conn.commit()

def main():
    """主函數"""
    print("🚀 開始安全資料庫同步")
    print("=" * 50)
    
    if not all(RENDER_DB_CONFIG.values()):
        print("❌ 請設定 Render 資料庫連線資訊")
        return False
    
    render_conn = None
    local_conn = None
    
    try:
        render_conn = get_db_connection(RENDER_DB_CONFIG, "Render")
        local_conn = get_db_connection(LOCAL_DB_CONFIG, "Local")
        
        if not render_conn or not local_conn:
            return False
        
        # 先同步其他表
        for table in SYNC_TABLES:
            safe_sync_table(local_conn, render_conn, table)
        
        # 再增量同步 completed_trips
        incremental_sync_completed_trips(local_conn, render_conn)
        
        # 校準序列
        calibrate_sequences(local_conn)
        
        print("\n🎉 同步成功完成！")
        print("   - completed_trips 已增量更新，歷史資料完整保留")
        print("   - 其他表已完全同步")
        return True
        
    except Exception as e:
        print(f"\n❌ 同步失敗: {e}", file=sys.stderr)
        return False
    finally:
        if render_conn:
            render_conn.close()
        if local_conn:
            local_conn.close()
        print("🔌 資料庫連線已關閉")

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)