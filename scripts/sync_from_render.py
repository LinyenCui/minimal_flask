#!/usr/bin/env python3
"""
Render 資料庫同步到本地的自動化腳本
混合模式版本 (採用 minimal_flask_ai 穩定順序 + 時間戳錨點改進):
- 同步順序: 其他表先同步 → completed_trips 最後同步 (避免外鍵約束衝突)
- completed_trips: 使用時間戳作為錨點進行增量同步，保留本地歷史數據不受Render刪除影響
- 其他資料表: 完全覆蓋同步，與 Render 保持一致 (使用 TRUNCATE CASCADE)
- 內建序列自動校準，無需外部工具
"""
import os
import sys
import datetime
import time
import psycopg2
from psycopg2.extras import DictCursor, execute_batch
from dotenv import load_dotenv

# --- 設定 ---
load_dotenv()

# --- 時區設定：固定此腳本以台北時區執行，避免跨環境顯示差異 ---
os.environ['TZ'] = 'Asia/Taipei'
try:
    # macOS/Linux 提供 tzset，可立即生效
    time.tzset()
except AttributeError:
    # Windows 無 tzset，忽略即可，連線端仍會提供正確的帶時區時間
    pass

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

# 增量同步 (只添加新紀錄，保護本地歷史數據)
# completed_trips 使用專門的ID-based增量同步，確保本地歷史數據不受Render刪除影響
# INCREMENTAL_SYNC_TABLES = ["completed_trips"]

# 完全覆蓋同步 (清空本地，再從 Render 複製所有資料)
FULL_SYNC_TABLES = [
    "database_maintenance",  # 資料庫維護表，需要先同步
    "drivers",
    "customers", 
    "fixed_schedules",  # 移到trips之前，因為trips有外鍵參考
    "trips",
    # 🔥 新增：帳務處理流水帳與金流紀錄
    "account_ledger",
    "payments"
    # 移除 "users" 因為本地資料庫沒有這個表
    # ... 請根據您的需求，將其他需要完全同步的資料表加到這裡
]


# --- 核心邏輯 ---

def get_db_connection(config, db_type=""):
    """建立資料庫連線"""
    try:
        print(f"🔌 正在連接到 {db_type} 資料庫 ({config.get('host')})...")
        conn = psycopg2.connect(**config)
        # 統一連線會話時區，避免顯示早/晚 8 小時
        try:
            with conn.cursor() as cur:
                cur.execute("SET TIME ZONE 'Asia/Taipei';")
                cur.execute("SHOW TIMEZONE;")
                tz = cur.fetchone()[0]
            conn.commit()
            print(f"✅ 成功連接到 {db_type} 資料庫。🕒 會話時區: {tz}")
        except Exception as tz_err:
            # 不阻斷主流程，但提示可能的時區問題
            print(f"⚠️ 設定 {db_type} 連線時區失敗: {tz_err}")
            print("   將繼續以資料庫預設時區執行。")
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ 無法連接到 {db_type} 資料庫: {e}", file=sys.stderr)
        print("   請檢查您的 .env 設定以及資料庫服務是否正在運行。", file=sys.stderr)
        return None


def get_column_types(conn, table_name: str, columns: list[str]) -> dict:
    """回傳指定資料表欄位型別（例如 timestamp with time zone）"""
    types: dict[str, str] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = ANY(%s)
            """,
            (table_name, columns),
        )
        for name, typ in cur.fetchall():
            types[name] = typ
    return types


def ensure_account_ledger_timestamptz(local_conn) -> None:
    """確保本地 account_ledger 的時間欄位為 timestamptz。

    若為 timestamp without time zone，轉換為 timestamptz，
    並以 Asia/Taipei 解讀原始值，避免產生 8 小時位移。
    """
    table = "account_ledger"
    time_columns = ["occurred_at", "created_at"]
    types = get_column_types(local_conn, table, time_columns)

    to_fix: list[str] = [col for col in time_columns if types.get(col) == "timestamp without time zone"]
    if not to_fix:
        print("🔎 account_ledger 欄位型別檢查：OK (timestamptz)")
        return

    print(f"🛠️ 偵測到本地 {table} 欄位型別需修正: {to_fix}")
    with local_conn.cursor() as cur:
        for col in to_fix:
            print(f"   - 正在轉換 {col} 為 TIMESTAMP WITH TIME ZONE（以 Asia/Taipei 解讀現有值）…")
            cur.execute(
                f"""
                ALTER TABLE {table}
                ALTER COLUMN {col}
                TYPE TIMESTAMP WITH TIME ZONE
                USING ({col} AT TIME ZONE 'Asia/Taipei');
                """
            )
    local_conn.commit()
    print("   ✅ 欄位型別轉換完成。")

def get_sequence_info(conn, table_name, id_column='id'):
    """獲取序列的當前信息"""
    sequence_name = f"{table_name}_{id_column}_seq"
    with conn.cursor() as cur:
        try:
            # 使用 last_value 替代 currval，避免序列未使用時的錯誤
            cur.execute(f"SELECT last_value, is_called FROM {sequence_name};")
            result = cur.fetchone()
            if result:
                last_value, is_called = result
                # 如果序列從未被調用過，實際可用值是 last_value
                # 如果已被調用過，下一個值是 last_value + 1
                current_val = last_value if not is_called else last_value
            else:
                current_val = 1
            
            # 獲取表中最大ID
            cur.execute(f"SELECT COALESCE(MAX({id_column}), 0) FROM {table_name};")
            max_id = cur.fetchone()[0]
            
            return {
                'sequence_name': sequence_name,
                'current_val': current_val,
                'max_id': max_id,
                'table_name': table_name,
                'id_column': id_column,
                'is_called': is_called if result else False
            }
        except psycopg2.errors.UndefinedTable:
            return None
        except Exception as e:
            print(f"   - ⚠️ 獲取序列 {sequence_name} 信息時出錯: {e}")
            return None

def detect_sequence_conflicts(local_conn, render_conn):
    """檢測序號衝突"""
    conflicts = []
    tables_to_check = [
        ('trips', 'trip_id'),
        ('completed_trips', 'id')
    ]
    
    print("🔍 正在檢查序號衝突...")
    
    for table_name, id_column in tables_to_check:
        print(f"   - 檢查 {table_name} 表的序號...")
        
        # 獲取遠端序號信息
        remote_info = get_sequence_info(render_conn, table_name, id_column)
        if not remote_info:
            print(f"   - ⚠️ 遠端 {table_name} 表沒有序列，跳過檢查")
            continue
            
        # 獲取本地序號信息
        local_info = get_sequence_info(local_conn, table_name, id_column)
        if not local_info:
            print(f"   - ⚠️ 本地 {table_name} 表沒有序列，跳過檢查")
            continue
            
        # 檢測衝突條件：
        # 1. 遠端序號小於本地序號
        # 2. 遠端最大ID小於本地最大ID
        has_conflict = False
        conflict_reasons = []
        
        if remote_info['current_val'] < local_info['current_val']:
            has_conflict = True
            conflict_reasons.append(f"遠端序號({remote_info['current_val']}) < 本地序號({local_info['current_val']})")
            
        if remote_info['max_id'] < local_info['max_id']:
            has_conflict = True
            conflict_reasons.append(f"遠端最大ID({remote_info['max_id']}) < 本地最大ID({local_info['max_id']})")
            
        if has_conflict:
            conflict_info = {
                'table_name': table_name,
                'id_column': id_column,
                'local_info': local_info,
                'remote_info': remote_info,
                'reasons': conflict_reasons
            }
            conflicts.append(conflict_info)
            print(f"   - ⚠️ 發現衝突: {', '.join(conflict_reasons)}")
        else:
            print(f"   - ✅ {table_name} 序號無衝突")
    
    return conflicts

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
            
            # 🔥 特殊處理：drivers 表需要避免 CASCADE 影響 completed_trips
            if table_name == 'drivers':
                print(f"   - 檢測到 drivers 表，使用安全清空方式避免影響 completed_trips...")
                # 暫時禁用外鍵約束
                local_cur.execute("SET session_replication_role = replica;")
                local_cur.execute(f"DELETE FROM {table_name};")
                # drivers 表沒有序列，跳過序列重置
                print(f"   - drivers 表沒有使用序列，跳過序列重置")
                # 恢復外鍵約束  
                local_cur.execute("SET session_replication_role = DEFAULT;")
            else:
                # 其他表使用標準 TRUNCATE CASCADE
                local_cur.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE;")

            if not records:
                print(f"   - '{table_name}' 在 Render 上沒有資料，本地資料表已清空。")
                local_conn.commit()
                return

            print(f"   - 從 Render 讀取了 {len(records)} 筆紀錄，正在寫入本地...")
            
            # 獲取所有欄位
            all_cols = [desc[0] for desc in render_cur.description]
            
            # 過濾掉自動生成的欄位
            generated_columns = ['actual_fare', 'total_fare']  # 已知的自動生成欄位
            filtered_cols = [col for col in all_cols if col not in generated_columns]
            
            # 獲取對應的資料索引
            col_indices = [all_cols.index(col) for col in filtered_cols]
            
            # 準備插入語句
            placeholders = "%s, " * len(filtered_cols)
            insert_sql = f"INSERT INTO {table_name} ({', '.join(filtered_cols)}) VALUES ({placeholders.strip(', ')})"
            
            # 過濾記錄資料，只包含非生成欄位  
            filtered_records = [[rec[i] for i in col_indices] for rec in records]
            
            execute_batch(local_cur, insert_sql, filtered_records)
            local_conn.commit()
            print(f"   ✅ 資料表 '{table_name}' 完全同步成功。")

        except Exception as e:
            # 確保外鍵約束在錯誤情況下也能恢復
            try:
                local_cur.execute("SET session_replication_role = DEFAULT;")
            except:
                pass
            local_conn.rollback()
            print(f"❌ 同步資料表 '{table_name}' 時發生錯誤: {e}", file=sys.stderr)
            raise

def incremental_sync_completed_trips(local_conn, render_conn):
    """增量同步 completed_trips 資料表，使用時間戳保護本地歷史數據"""
    table_name = "completed_trips"
    print(f"--- 開始增量同步資料表: {table_name} (基於時間戳保護本地歷史數據) ---")

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
                return

            print(f"   - 從 Render 找到 {len(new_records)} 筆新紀錄需要同步。")

            # 3. 過濾生成欄位和本地特有欄位，避免插入錯誤
            all_cols = [desc[0] for desc in render_cur.description]
            # completed_trips: 過濾生成欄位和本地特有欄位
            if table_name == 'completed_trips':
                excluded_columns = ['actual_fare', 'total_fare', 'original_trip_id']
            else:
                excluded_columns = ['actual_fare', 'total_fare']
            filtered_cols = [col for col in all_cols if col not in excluded_columns]
            
            print(f"   - 原始欄位: {len(all_cols)} 個，過濾後: {len(filtered_cols)} 個")
            
            # 獲取對應的資料索引
            col_indices = [all_cols.index(col) for col in filtered_cols]
            
            # 過濾記錄資料，只包含非生成欄位
            filtered_records = [[rec[i] for i in col_indices] for rec in new_records]

            # 4. 使用 ON CONFLICT DO UPDATE 覆蓋本地資料
            print(f"   - 正在將新紀錄寫入本地，覆蓋已存在的記錄...")
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
                # 先嘗試插入前5筆記錄進行測試
                test_records = filtered_records[:5]
                print(f"   - 調試：測試插入前5筆記錄...")
                
                success_count = 0
                for i, record in enumerate(test_records):
                    try:
                        local_cur.execute(insert_sql, record)
                        success_count += 1
                        print(f"     測試記錄 {i+1}: 成功")
                    except Exception as single_error:
                        print(f"     測試記錄 {i+1}: 失敗 - {single_error}")
                        # 顯示問題記錄的部分數據
                        print(f"     問題記錄前3個欄位: {record[:3]}")
                        local_conn.rollback()
                        if i == 0:  # 如果第一筆就失敗，停止測試
                            raise single_error
                
                local_conn.commit()
                print(f"   - 測試結果：{success_count}/5 筆記錄成功插入")
                
                if success_count == 5:
                    # 測試成功，執行批量插入
                    print(f"   - 測試通過，執行完整批量插入...")
                    execute_batch(local_cur, insert_sql, filtered_records)
                    affected_count = local_cur.rowcount
                    local_conn.commit()
                    print(f"   - ✅ 批量插入完成，處理 {len(filtered_records)} 筆紀錄。")
                else:
                    print(f"   - ⚠️ 測試未完全通過，請檢查數據格式")
                    
            except Exception as insert_error:
                print(f"   - ❌ 插入錯誤: {insert_error}")
                local_conn.rollback()
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

        except Exception as e:
            local_conn.rollback()
            print(f"❌ 增量同步 '{table_name}' 時發生錯誤: {e}", file=sys.stderr)
            raise

def main(check_only=False, force_sync=False):
    """主函數"""
    if check_only:
        print("🔍 執行序號衝突檢查模式")
    else:
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

        # 檢測序號衝突
        conflicts = detect_sequence_conflicts(local_conn, render_conn)
        
        if conflicts:
            print(f"\n⚠️ 發現 {len(conflicts)} 個序號衝突:")
            for conflict in conflicts:
                print(f"\n📋 表名: {conflict['table_name']}")
                print(f"   本地序號: {conflict['local_info']['current_val']} (最大ID: {conflict['local_info']['max_id']})")
                print(f"   遠端序號: {conflict['remote_info']['current_val']} (最大ID: {conflict['remote_info']['max_id']})")
                print(f"   衝突原因: {', '.join(conflict['reasons'])}")
            
            if check_only:
                print("\n🔍 檢查完成，發現序號衝突。")
                return {"status": "conflicts", "conflicts": conflicts}
            
            if not force_sync:
                print("\n❌ 由於序號衝突，同步已停止。")
                print("💡 解決方案:")
                print("   1. 在 LINE Bot 中輸入「確認序號覆蓋」來強制以遠端序號為主")
                print("   2. 或手動解決衝突後再重新同步")
                return {"status": "conflicts", "conflicts": conflicts}
            else:
                print("\n⚡ 強制同步模式: 將以遠端序號為主覆蓋本地序號")
        else:
            print("\n✅ 未發現序號衝突，可安全進行同步")
            
        if check_only:
            print("\n🔍 檢查完成，無序號衝突。")
            return {"status": "no_conflicts"}

        # 確保本地 account_ledger 的時間欄位型別正確，避免 8 小時位移
        try:
            ensure_account_ledger_timestamptz(local_conn)
        except Exception as fix_err:
            print(f"⚠️ 檢查/修正 account_ledger 欄位型別時出錯：{fix_err}")

        # 🔥 採用 minimal_flask_ai 的穩定順序：其他表先同步，completed_trips 最後同步
        
        # 步驟 1: 執行完全覆蓋同步其他表 (不包含 database_maintenance)
        sync_tables = [table for table in FULL_SYNC_TABLES if table != 'database_maintenance']
        for table in sync_tables:
            truncate_and_copy(local_conn, render_conn, table)
        
        # 步驟 2: 執行增量同步 completed_trips（保護歷史資料，使用時間戳錨點）
        incremental_sync_completed_trips(local_conn, render_conn)
        
        # 步驟 3: 最後同步 database_maintenance (包含更新後的時間戳)
        truncate_and_copy(local_conn, render_conn, 'database_maintenance')

        # 步驟 3: 校準所有相關資料表的序列
        print("--- 開始校準本地資料庫序列 ---")
        for table in FULL_SYNC_TABLES:
            # trips 表的 ID 欄位名是 trip_id
            id_column = 'trip_id' if table == 'trips' else 'id'
            calibrate_sequence(local_conn, table, id_column)
        
        calibrate_sequence(local_conn, "completed_trips")

        print("\n🎉 同步成功完成！")
        print("   - ✅ 採用 minimal_flask_ai 穩定順序：其他表先同步，completed_trips 最後同步")
        print("   - ✅ 其他指定資料表已與 Render 完全同步（使用 TRUNCATE CASCADE）")
        print("   - ✅ completed_trips 已使用時間戳錨點增量更新，本地歷史數據完全保護")
        print("   - ✅ database_maintenance 表已同步，包含最新同步時間戳")
        print("   - ✅ 所有本地資料庫序列已自動校準")
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
    import argparse
    
    parser = argparse.ArgumentParser(description='Render 資料庫同步工具')
    parser.add_argument('--check-only', action='store_true', help='只檢查序號衝突，不執行同步')
    parser.add_argument('--force', action='store_true', help='強制同步，忽略序號衝突')
    
    args = parser.parse_args()
    
    result = main(check_only=args.check_only, force_sync=args.force)
    
    # 如果是檢查模式，返回檢查結果
    if args.check_only:
        if isinstance(result, dict):
            if result["status"] == "conflicts":
                print("\n❌ 檢查結果：發現序號衝突")
                exit(1)
            else:
                print("\n✅ 檢查結果：無序號衝突")
                exit(0)
    
    # 正常同步模式
    if isinstance(result, dict) and result["status"] == "conflicts":
        exit(2)  # 特殊返回碼表示序號衝突
    
    success = result if isinstance(result, bool) else False
    exit(0 if success else 1)
