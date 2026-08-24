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
    # 🔥 2026-05-08: customers 加回同步（兩邊 schema 已對齊 + 已透過
    # reverse_sync_customers.py 把本地累積資料推到 Render；以後可正常同步）
    "customers",
    "fixed_schedules",  # 移到trips之前，因為trips有外鍵參考
    "trips",
    # 🔥 新增：帳務處理流水帳與金流紀錄
    "account_ledger",
    "payments"
    # 移除 "users" 因為本地資料庫沒有這個表
    # ... 請根據您的需求，將其他需要完全同步的資料表加到這裡
]

# 暫時跳過同步的表（保護 dev 上特殊狀態的資料）
# Key: 表名，Value: 跳過原因（會印在每次同步開頭，提醒用戶）
SKIP_TABLES = {
    # 目前沒有需要跳過的表
    # （customers 之前因 schema 不一致 + 本地資料較多被擋；現已對齊解除）
}


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

def classify_local_completed_row(*, row_date, unique_code, row_id,
                                 render_min_date, render_codes, render_ids):
    """本地這一列該怎麼處理：'archive'（保護）/ 'delete'（清掉）/ 'keep'（已同步）。

    抽成純函數是因為這條規則同時要滿足兩個看似互斥的需求（見
    purge_local_only_completed 的說明），錯一邊就是「刪掉真實歷史」或
    「本地永遠比 Render 多」，所以要能被單獨測到。
    """
    # 窗口外（比 Render 現存最早日期還舊）→ 那是 Render 瘦身掉的歷史，只剩本地有
    if row_date is not None and render_min_date is not None and row_date < render_min_date:
        return 'archive'
    if unique_code:
        return 'keep' if unique_code in render_codes else 'delete'
    return 'keep' if row_id in render_ids else 'delete'


def purge_local_only_completed(local_conn, render_conn):
    """清掉本地獨有的 completed_trips —— **但只在 Render 還涵蓋的日期範圍內**。

    這裡要同時滿足兩件看似互斥的事（2026-08-24 用戶提出）：
      (a) 本地是拿來測試的 → 在 Render 還有資料的那段期間，本地就該等於 Render，
          本地排程自己產生的測試殘留要清掉，否則兩邊數字對不起來。
      (b) 用戶打算定期把 Render 三～六個月前的資料刪掉幫 Render 瘦身
          → 那些歷史只剩本地有，**絕對不能因為「Render 沒有」就被當成垃圾刪掉**。

    解法是用「時間」把兩者切開，不需要任何設定：

        鏡射窗口 = Render 現存資料的最早日期（MIN(date)）之後
          · 窗口內：Render 是唯一真相，本地獨有的一律刪
          · 窗口外（更舊）：本地的歷史保存庫，一律不動

    好處是它會自己維護：等 Render 把 3 月前的資料清掉，MIN(date) 自動往前移，
    本地那批舊資料就自動落到窗口外受保護，不必記得去改任何參數。

    防呆：Render 的 completed_trips 空的、或算不出 MIN(date) → 整個跳過不刪。
    """
    with render_conn.cursor() as rcur, local_conn.cursor() as lcur:
        rcur.execute("SELECT COUNT(*), MIN(date) FROM completed_trips")
        render_n, render_min_date = rcur.fetchone()
        if not render_n or render_min_date is None:
            print("   - ⚠️ Render completed_trips 為空或無日期，跳過清理（防誤刪）")
            return 0

        rcur.execute("SELECT id FROM completed_trips")
        render_ids = {r[0] for r in rcur.fetchall()}
        rcur.execute(
            "SELECT unique_code FROM completed_trips WHERE unique_code IS NOT NULL")
        render_codes = {r[0] for r in rcur.fetchall()}

        print(f"   - 鏡射窗口：{render_min_date} 之後（Render 現存最早日期）；"
              f"更舊的是本地歷史保存庫，不動")

        lcur.execute("SELECT id, unique_code, date FROM completed_trips")
        to_delete, archived = [], 0
        for rid, code, d in lcur.fetchall():
            verdict = classify_local_completed_row(
                row_date=d, unique_code=code, row_id=rid,
                render_min_date=render_min_date,
                render_codes=render_codes, render_ids=render_ids)
            if verdict == 'archive':
                archived += 1
            elif verdict == 'delete':
                to_delete.append(rid)

        if archived:
            print(f"   - 🗄️ 保護 {archived} 筆窗口外的歷史紀錄（Render 已瘦身掉的期間）")
        if to_delete:
            lcur.execute(
                "DELETE FROM completed_trips WHERE id = ANY(%s)", (to_delete,))
            local_conn.commit()
            print(f"   - 🧹 清掉窗口內本地獨有的 {len(to_delete)} 筆（Render 為準）")
        else:
            print("   - ✅ 窗口內沒有本地獨有的紀錄")
        return len(to_delete)


def calibrate_sequence(conn, table_name, id_column='id'):
    """
    校準指定資料表的序列計數器

    用 pg_get_serial_sequence 動態查實際 sequence 名稱，避免 schema 變動
    導致序列名稱不符標準格式（如 trips_trip_id_seq1 而非 trips_trip_id_seq）
    時跳過校準的 bug — 這個 bug 之前讓 trips / completed_trips 的 sequence
    永遠落後於 max(id)，造成 INSERT 撞 PK 而 trips 卡在「準備」狀態無法
    流轉到 completed_trips。
    """
    with conn.cursor() as cur:
        try:
            cur.execute(
                "SELECT pg_get_serial_sequence(%s, %s)",
                (table_name, id_column),
            )
            sequence_name = cur.fetchone()[0]
            if not sequence_name:
                print(f"   - ⚠️ {table_name}.{id_column} 沒有對應 sequence，跳過")
                return
            print(f"   - 正在校準序列 '{sequence_name}'...")
            cur.execute(
                f"SELECT setval('{sequence_name}', "
                f"COALESCE((SELECT MAX({id_column}) FROM {table_name}), 1))"
            )
            conn.commit()
            print(f"   - ✅ 序列 '{sequence_name}' 已校準")
        except Exception as e:
            print(f"❌ 校準 {table_name}.{id_column} 序列時發生錯誤: {e}", file=sys.stderr)
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
            
            # 🔥 安全處理：避免 CASCADE 影響到 incremental sync 的表（如 completed_trips）
            print(f"   - 使用安全清空方式，避免 CASCADE 波及其他資料表...")
            # 暫時禁用外鍵約束
            local_cur.execute("SET session_replication_role = replica;")
            local_cur.execute(f"DELETE FROM {table_name};")
            # 恢復外鍵約束  
            local_cur.execute("SET session_replication_role = DEFAULT;")

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


# 兩邊 schema 一致（2026-08-24 實測），排除 id 與生成欄後可逐欄刷新
_REFRESH_COLS = [
    'date', 'start_point', 'via_point', 'end_point',
    'meter_fare', 'extra_fare', 'category', 'driver_id',
    'remarks', 'created_at', 'status', 'modified_by',
    'modification_reason', 'modification_time',
    'passenger_name', 'passenger_leave_reason', 'trip_type',
]


def refresh_existing_completed_from_render(local_conn, render_conn):
    """把本地已有的 completed_trips 用 Render 的內容刷新（以 unique_code 對齊）。

    為什麼需要（2026-08-24 用戶回報「同步後兩邊數字不同」）：
        原本的增量同步是**只增不改** —— 路徑 2 只挑 unique_code 不在本地的補進來，
        本地已有的一律不碰（`code not in local_codes`），所以 3.1 那段「預先刪除
        以便覆蓋」形同虛設：能被撈出來的本來就不存在於本地。
        當初的理由是「本地是累積版，要保留 Render 已手動清掉的歷史」。

        實測那個理由已經不成立：兩邊日期範圍完全一樣（2026-03-02 ~ 08-24），
        本地保有、Render 已清掉的歷史 **0 筆**。代價卻是 **120 筆分岔** ——
        在 Render 上改了司機/加成之後，本地永遠停在舊值，同一個查詢兩邊數字不同
        （用戶因此一度以為是程式改壞了）。

    用戶定調（2026-08-24，選項 A）：本地是拿來測試的，就該等於 Render。
    Render 是唯一真相。

    用 UPDATE 而不是 DELETE+INSERT：保持本地 id 穩定，也避免序列每次同步都
    暴衝 —— 那會讓「本地 max_id > 遠端」這個假衝突越來越誇張。
    """
    print("--- 刷新本地既有 completed_trips（以 Render 為準）---")
    cols = ', '.join(_REFRESH_COLS)
    with render_conn.cursor() as rcur, local_conn.cursor() as lcur:
        rcur.execute(
            f"SELECT unique_code, {cols} FROM completed_trips "
            f"WHERE unique_code IS NOT NULL")
        remote = {r[0]: r[1:] for r in rcur.fetchall()}
        lcur.execute(
            f"SELECT unique_code, {cols} FROM completed_trips "
            f"WHERE unique_code IS NOT NULL")
        local = {r[0]: r[1:] for r in lcur.fetchall()}

        stale = [(code, remote[code]) for code in (set(remote) & set(local))
                 if remote[code] != local[code]]
        print(f"   - Render {len(remote)} 筆 / 本地 {len(local)} 筆，"
              f"內容不一致 {len(stale)} 筆")
        if not stale:
            print("   - ✅ 本地既有紀錄已與 Render 一致")
            return 0

        set_clause = ', '.join(f"{c} = %s" for c in _REFRESH_COLS)
        lcur.executemany(
            f"UPDATE completed_trips SET {set_clause} WHERE unique_code = %s",
            [(*vals, code) for code, vals in stale],
        )
        print(f"   - ✅ 已用 Render 內容刷新 {len(stale)} 筆")
        return len(stale)


def incremental_sync_completed_trips(local_conn, render_conn):
    """補齊 completed_trips —— 把「Render 有、本地沒有的」插進來。

    （內容不同的由步驟 2b refresh_existing_completed_from_render 負責刷新，
      本地獨有的由 purge_local_only_completed 依鏡射窗口處理。）

    設計理由（**保留 incremental 精神**，by design）：
      - 本地是「累積版」要保留 Render 已手動清掉的歷史
      - 用 created_at > last_sync_time 抓「Render 新增的」即可
      - 不要全抓 — 會把 Render NULL 的舊 row 用 Render 內容覆蓋本地修改

    ⚠️ Bug 修正（2026-05-08）：Render 上 60%+ 的 completed_trips
    `created_at IS NULL`（schema 升級舊資料）。舊邏輯只用
    `WHERE created_at > last_sync_time` → NULL 全部過濾掉 →
    本地永遠缺這些 row（4/26-5/2 28 筆漏失就是這個）。

    新邏輯雙路徑：
      路徑 1: created_at > last_sync_time → 抓 Render 新加的（標準 incremental）
      路徑 2: 缺 id 補漏 — Render 有、本地沒有的 id 一律補回
              （2026-07-15 由「只補 NULL created_at」擴成全 id 比對；
               本地已有這個 id 的不抓，避免覆蓋本地修改）
    """
    table_name = "completed_trips"
    print(f"--- 補齊資料表: {table_name}（比對 unique_code 補缺） ---")

    with local_conn.cursor() as local_cur, render_conn.cursor(cursor_factory=DictCursor) as render_cur:
        try:
            # ----- 路徑 1（時間錨點）已移除 -----
            # 2026-08-25：路徑 2（比對 unique_code 補缺）＋ 步驟 2b
            # （refresh_existing_completed_from_render 刷新既有紀錄）合起來，
            # 已經完全覆蓋路徑 1 能做的事：
            #   · Render 有、本地沒有的 → 路徑 2 補
            #   · 兩邊都有但內容不同的 → 步驟 2b 刷新
            # 而路徑 1 還有兩個缺點：
            #   · 靠 created_at，但 Render 上有 2896 筆 created_at 是 NULL
            #     （schema 升級遺留），本來就抓不到
            #   · 它要回寫 Render 的 database_maintenance 錨點 ——
            #     同步是「從 Render 拉資料」，不該對生產庫寫東西
            # 移除後同步對 Render 變成**唯讀**。
            records_by_time = []

            # ----- 路徑 2: 補本地沒的 NULL row -----
            # Render 上 NULL row 是 schema 升級遺留，數量固定（不會新增）
            # 本地已有的一律不抓 → 維持「不洗本地修改、只增不減」。
            # ⚠️ 比對鍵用 unique_code（業務唯一鍵）而非 id：本地 Flask 排程也會
            # 把班次掉進 completed_trips，同一趟在兩邊拿到不同流水號
            # （2026-07-27 實測：20_196_29 本地 #2795 / Render #2791）→
            # 用 id 比對會誤判成「缺 24 筆」而重複插入同一批班次。
            # unique_code 為 NULL 的舊資料退回 id 比對。
            print("   - [路徑2] 比對 unique_code，補 Render 有、本地沒有的紀錄...")
            render_cur.execute(f"SELECT id, unique_code FROM {table_name} ORDER BY id;")
            render_rows = [(r['id'], r['unique_code']) for r in render_cur.fetchall()]
            local_cur.execute(f"SELECT id, unique_code FROM {table_name}")
            local_rows = local_cur.fetchall()
            local_ids = {r[0] for r in local_rows}
            local_codes = {r[1] for r in local_rows if r[1]}
            time_ids = {r['id'] for r in records_by_time}  # 路徑1 已抓的不重複抓
            missing_ids = [
                rid for rid, code in render_rows
                if rid not in time_ids
                and (code not in local_codes if code else rid not in local_ids)
            ]
            print(f"   - [路徑2] Render {len(render_rows)} 筆, 本地 {len(local_rows)} 筆, "
                  f"待補 {len(missing_ids)} 筆")

            if missing_ids:
                render_cur.execute(
                    f"SELECT * FROM {table_name} WHERE id = ANY(%s) ORDER BY id",
                    (missing_ids,),
                )
                records_missing = list(render_cur.fetchall())
                description_full = render_cur.description  # SELECT * 重新 cache
            else:
                records_missing = []

            # ----- 合併 -----
            new_records = records_by_time + records_missing
            if not new_records:
                print("   - ✅ 沒有需要同步的新紀錄")
                return
            print(f"   - 總共需補 {len(new_records)} 筆")

            # 3. 過濾生成欄位（用 cached description，避免被 path 2 的 SELECT id 覆寫）
            all_cols = [desc[0] for desc in description_full]
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

            # 3.1 若 unique_code 已存在於本地，預先刪除舊資料以便遠端覆蓋
            unique_code_idx = filtered_cols.index('unique_code') if 'unique_code' in filtered_cols else None
            duplicates_removed = 0
            if unique_code_idx is not None:
                candidate_codes = {record[unique_code_idx] for record in filtered_records if record[unique_code_idx]}
                if candidate_codes:
                    local_cur.execute(
                        "SELECT unique_code FROM completed_trips WHERE unique_code = ANY(%s)",
                        (list(candidate_codes),)
                    )
                    duplicate_codes = [row[0] for row in local_cur.fetchall()]
                    if duplicate_codes:
                        print(f"   - ⚠️ 偵測到 {len(duplicate_codes)} 個 unique_code 已存在於本地，將以 Render 資料覆蓋")
                        local_cur.execute(
                            "DELETE FROM completed_trips WHERE unique_code = ANY(%s)",
                            (duplicate_codes,)
                        )
                        duplicates_removed = local_cur.rowcount
                        print(f"   - ✅ 已預先移除 {duplicates_removed} 筆衝突記錄，避免 unique_completed_trip_code 衝突")
                else:
                    print("   - ℹ️ 新紀錄中沒有 unique_code，跳過衝突檢查")
            else:
                print("   - ⚠️ 找不到 unique_code 欄位，無法自動處理重複序號")

            # 3.2 補漏不沿用 Render 的 id — id 只是流水號，unique_code 才是身份。
            # 本地 Flask 排程也會產生 completed_trips，同一趟兩邊 id 不同；沿用
            # Render id 會撞本地既有紀錄的主鍵，同批內還會連鎖佔位互踩
            # （2026-07-27 實測：21 筆只進 7 筆、殘留 4 筆怎麼補都補不進）。
            # 讓本地序列自己編號，衝突只可能發生在 unique_code（上面已預刪）。
            if 'id' in filtered_cols:
                _id_pos = filtered_cols.index('id')
                filtered_cols = [c for c in filtered_cols if c != 'id']
                filtered_records = [
                    tuple(v for i, v in enumerate(rec) if i != _id_pos)
                    for rec in filtered_records
                ]
                print("   - 🆔 補漏改用本地新 id（unique_code 為身份鍵，避免主鍵連鎖衝突）")

            # 4. 使用 ON CONFLICT DO UPDATE 覆蓋本地資料
            print(f"   - 正在將新紀錄寫入本地，覆蓋已存在的記錄...")
            placeholders = "%s, " * len(filtered_cols)
            
            # 構建 UPDATE SET 子句（排除衝突鍵 unique_code）
            update_cols = [col for col in filtered_cols if col != 'unique_code']
            update_set = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_cols])

            insert_sql = f"""INSERT INTO {table_name} ({', '.join(filtered_cols)}) 
                            VALUES ({placeholders.strip(', ')}) 
                            ON CONFLICT (unique_code) DO UPDATE SET {update_set}"""
            
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
            
            # 5.（已移除）不再回寫 Render 的同步時間戳 ——
            #    路徑 1 沒了就不需要錨點，同步也因此對 Render 保持唯讀。

        except Exception as e:
            local_conn.rollback()
            print(f"❌ 增量同步 '{table_name}' 時發生錯誤: {e}", file=sys.stderr)
            raise

def upsert_drivers(local_conn, render_conn):
    """UPSERT drivers（保留本地升級欄位：line_user_id / is_active / is_manager）

    Render 端可能還沒補這三個欄位；即使補了，綁定也可能只存在其中一邊。
    做法與 upsert_customers 相同：INSERT/UPDATE 只碰「Render 實際有的欄位」，
    本地獨有欄位自然不被 update → 綁定與管理員標記完整保留。
    """
    table = 'drivers'
    print(f"--- UPSERT 資料表: {table}（保留綁定 / 管理員 / 停用欄位） ---")
    with render_conn.cursor(cursor_factory=DictCursor) as rcur, local_conn.cursor() as lcur:
        rcur.execute(f"SELECT * FROM {table}")
        rows = rcur.fetchall()
        if not rows:
            print("   - ⚠️ Render drivers 為空，跳過")
            return
        cols = [d[0] for d in rcur.description]
        col_list = ', '.join(cols)
        placeholders = ', '.join(['%s'] * len(cols))
        update_set = ', '.join(f"{c} = EXCLUDED.{c}" for c in cols if c != 'id')
        sql = (f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
               f"ON CONFLICT (id) DO UPDATE SET {update_set}")
        execute_batch(lcur, sql, [tuple(r) for r in rows])
        local_conn.commit()
        # 本地獨有的司機（Render 沒有）不刪 — 可能是本地測試或還沒推上去的新司機
        rids = [r['id'] for r in rows]
        lcur.execute(f"SELECT COUNT(*) FROM {table} WHERE NOT (id = ANY(%s))", (rids,))
        extra = lcur.fetchone()[0]
    print(f"   ✅ {table} UPSERT 完成（Render {len(rows)} 筆；本地獨有 {extra} 筆保留）")
    print(f"   - 本地欄位 line_user_id / is_active / is_manager 未被覆蓋")


def upsert_customers(local_conn, render_conn):
    """UPSERT customers（保留本地升級欄位不被覆蓋）

    本地 schema 升級了 birthday / gender / medical_record_no / latitude /
    longitude / created_at / updated_at 等欄位，Render 上沒有。
    直接 truncate_and_copy 會洗掉本地補的這些欄位。

    ⚠️ 2026-05-08: drop national_id / insurance_type 已從 customers schema
       移除，本地與 Render schema 對齊後可考慮 enable customers sync。

    解法：UPSERT
      - INSERT 用 Render 既有欄位（升級欄位走本地 schema default 為 NULL）
      - ON CONFLICT (id) DO UPDATE 只更新「Render 既有欄位」（render_cols 自然
        不含本地升級欄位 → 升級欄位不會被 update → 自動保留）
      - 本地獨有 id（seed 5 筆 + 手動加）→ Render 沒這 id → 不會被刪/動
      - short_name 衝突（Render id=10 short_name='李四'，本地 id=999 short_name='李四'）
        → savepoint per-row，violation 跳過 + log

    必須在 trips / fixed_schedules 同步**之前**執行（兩者 FK 指 customers.short_name）。
    """
    table = 'customers'
    print(f"--- UPSERT 資料表: {table}（保留本地升級欄位） ---")

    with local_conn.cursor() as local_cur, render_conn.cursor(cursor_factory=DictCursor) as render_cur:
        try:
            # 從 Render 抓所有 customers（48 筆左右，無增量必要）
            render_cur.execute(f"SELECT * FROM {table} ORDER BY id;")
            records = render_cur.fetchall()
            if not records:
                print(f"   - Render 上沒 {table}，跳過")
                return

            render_cols = [d[0] for d in render_cur.description]
            print(f"   - 從 Render 抓到 {len(records)} 筆，欄位: {render_cols}")

            # 自動生成欄位排除（即使 Render 有此欄也不寫）
            generated = {'actual_fare', 'total_fare'}
            insert_cols = [c for c in render_cols if c not in generated]
            col_indices = [render_cols.index(c) for c in insert_cols]

            # ON CONFLICT 只 update Render 有的欄位（自然不含本地升級欄位）
            update_cols = [c for c in insert_cols if c != 'id']
            update_set = ', '.join(f'{c} = EXCLUDED.{c}' for c in update_cols)
            placeholders = ', '.join(['%s'] * len(insert_cols))
            insert_sql = (
                f"INSERT INTO {table} ({', '.join(insert_cols)}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT (id) DO UPDATE SET {update_set}"
            )

            inserted = updated = skipped_unique = 0
            sn_idx = insert_cols.index('short_name') if 'short_name' in insert_cols else None
            id_idx = insert_cols.index('id')

            # savepoint per-row 處理 short_name unique violation
            for rec in records:
                row = [rec[i] for i in col_indices]
                # 用 SAVEPOINT 隔離 unique 衝突（不會 abort 整個 transaction）
                local_cur.execute("SAVEPOINT row_save")
                try:
                    local_cur.execute(insert_sql, row)
                    # rowcount: INSERT new = 1, UPDATE existing = 1（PG 對 ON CONFLICT 都是 1）
                    # 用 SELECT xmax 區分太繁，直接判斷本地 id 在/不在
                    local_cur.execute("RELEASE SAVEPOINT row_save")
                    inserted += 1  # 計總改動，不細分 INSERT vs UPDATE
                except psycopg2.errors.UniqueViolation as e:
                    local_cur.execute("ROLLBACK TO SAVEPOINT row_save")
                    sn = row[sn_idx] if sn_idx is not None else '?'
                    rid = row[id_idx]
                    print(f"   - ⚠️ 跳過 id={rid} short_name={sn!r}: 本地有同 short_name 不同 id "
                          f"（保留本地版）")
                    skipped_unique += 1

            local_conn.commit()
            print(f"   - ✅ UPSERT 完成: 同步 {inserted} 筆，short_name 衝突跳過 {skipped_unique} 筆")
            print(f"   - ℹ️ 本地獨有的 customer id（seed/手動加）保留不動")

        except Exception as e:
            local_conn.rollback()
            print(f"❌ UPSERT '{table}' 失敗: {e}", file=sys.stderr)
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
            
            # 用戶定調（2026-07-27）：Render 是唯一真相，本地 completed_trips
            # 的「多出來的 id」都是本地排程測試產物 → 自動清掉、不中止同步。
            # （舊行為：直接 return 中止，連 completed_trips 補漏都沒跑到，
            #   造成本地缺 24 筆卻回報「同步成功」的假象）
            purged = purge_local_only_completed(local_conn, render_conn)
            if purged:
                print(f"   - 🧹 已清除本地獨有的測試資料 {purged} 筆（Render 為準）")
            if not force_sync:
                print("\n⚡ 序號衝突已自動處理（清本地測試資料 + 稍後校準序號），繼續同步")
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

        # 列出本次跳過的表（rewrite dev 保護機制）
        if SKIP_TABLES:
            print("\n⏭️  以下資料表【跳過】同步：")
            for tbl, reason in SKIP_TABLES.items():
                print(f"   - {tbl}：{reason}")
            print()

        # 步驟 1: 執行完全覆蓋同步其他表 (不包含 database_maintenance 和 SKIP_TABLES)
        sync_tables = [
            table for table in FULL_SYNC_TABLES
            if table != 'database_maintenance' and table not in SKIP_TABLES
        ]
        for table in sync_tables:
            if table == 'drivers':
                # drivers 不能 truncate：本地有 Render 沒有的升級欄位
                # （line_user_id 綁定 / is_active / is_manager），
                # truncate 重灌會把司機的 LINE 綁定與管理員標記整包洗掉。
                upsert_drivers(local_conn, render_conn)
                continue
            truncate_and_copy(local_conn, render_conn, table)
        
        # 步驟 2: 增量同步 completed_trips —— 先補「Render 有、本地沒有的」
        incremental_sync_completed_trips(local_conn, render_conn)

        # 步驟 2b: 再把本地既有的用 Render 內容刷新（2026-08-24 用戶定調選項 A）。
        # 少了這一步，同步就只是「只增不改」：在 Render 上改過的班次
        # （換司機、改加成…）永遠傳不到本地，兩邊會越積越多分岔。
        refresh_existing_completed_from_render(local_conn, render_conn)
        
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
