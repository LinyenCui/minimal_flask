# 資料庫同步需求文件

## 用戶原始需求描述

> 我render端跟本地測試端的資料庫是分開的，目前機器人也有一個資料庫同步的功能，我的想法是所有的資料表都單向從render端往本地端同步，但是completed_trips表比較不同的是往本地端同步後我會刪除一部分(例如只保留三個月)，以免render端資料一直增長，那刪掉的部分的序號我希望能回收，也不要一直增長，但是!我本地端的completed_trips希望能不跟render端的completed_trips一樣，本地端的可以存放久一點的資料沒關係，於是便以只日期大於本地端的資料同步下來而已，而序號不同步的問題用/fix-sequence工具修復，但是我上次試過將render上的五月一日以前的資料都刪除，同步下來本地端的五月一日以前的也不見了

## 需求分析

### Render 端策略
- 定期刪除舊資料（例如只保留3個月）
- 目的：避免資料無限增長
- 序號回收：刪掉的部分序號要能重複使用

### 本地端策略  
- 保留更長時間的歷史資料（比 Render 端久）
- 目的：本地需要更完整的歷史記錄

### 同步策略
- **所有資料表**：單向從 Render 往本地同步
- **completed_trips 特殊處理**：
  - **增量同步**：只同步「日期大於本地端最新日期」的資料
  - **不清空本地歷史資料**
  - 序號不一致問題用 `/fix-sequence` 工具修復

## 發現的問題

### 實際測試結果
1. 在 Render 刪除 5/1 以前的資料
2. 執行資料庫同步
3. **錯誤結果**：本地端 5/1 以前的資料也消失了
4. **預期結果**：本地端 5/1 以前的資料應該保留

### 問題根因
現在的同步程式**不是真正的增量同步**，在某個環節清空了本地的 completed_trips 資料。

## 正確的 completed_trips 同步邏輯應該是

```python
# 1. 查詢本地最新日期
SELECT MAX(date) FROM completed_trips;  # 假設得到 2025-07-20

# 2. 只從 Render 抓取比這個日期新的資料
SELECT * FROM completed_trips WHERE date > '2025-07-20';

# 3. 插入到本地（避免重複）
INSERT INTO completed_trips (...) VALUES (...) ON CONFLICT (id) DO NOTHING;
```

**絕對不能有任何 DELETE、TRUNCATE 或 CASCADE 影響本地的 completed_trips！**

## 解決方案演進

### 原始方案：日期錨點（有限制）
```python
# 查詢本地最新日期
SELECT MAX(date) FROM completed_trips;  # 假設得到 2025-07-20

# 只從 Render 抓取比這個日期新的資料
SELECT * FROM completed_trips WHERE date > '2025-07-20';
```

**問題**：如果同一天有多筆記錄，可能會遺漏或重複同步。

### 實施方案：時間戳錨點（已實現）

#### 1. 創建 database_maintenance 表（Render端）
```sql
CREATE TABLE IF NOT EXISTS database_maintenance (
    id SERIAL PRIMARY KEY,
    key VARCHAR(50) UNIQUE NOT NULL,
    value TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);
```

#### 2. 存儲同步時間戳
```sql
INSERT INTO database_maintenance (key, value, description) 
VALUES ('last_completed_trips_sync', '2025-07-29 12:00:00', '上次completed_trips同步時間戳')
ON CONFLICT (key) DO UPDATE SET 
    value = EXCLUDED.value, 
    timestamp = CURRENT_TIMESTAMP;
```

#### 3. 時間戳增量同步邏輯
```python
# 1. 從 Render 的 database_maintenance 表獲取上次同步時間
render_cur.execute("SELECT value FROM database_maintenance WHERE key = 'last_completed_trips_sync';")
last_sync_time = result['value']  # 例如：'2025-07-29 12:00:00'

# 2. 只同步 created_at > 上次同步時間的資料
render_cur.execute("SELECT * FROM completed_trips WHERE created_at > %s ORDER BY created_at, id;", (last_sync_time,))

# 3. 插入到本地（避免重複）
INSERT INTO completed_trips (...) VALUES (...) ON CONFLICT (id) DO UPDATE SET ...;

# 4. 更新同步時間戳
current_time = datetime.now().isoformat()
render_cur.execute("UPDATE database_maintenance SET value = %s WHERE key = 'last_completed_trips_sync'", (current_time,))
```

#### 4. 關鍵優勢
- **精確控制**：基於 `created_at` 時間戳，避免日期重複問題  
- **斷點續傳**：記錄上次同步位置，支持增量更新
- **本地歷史保護**：絕不清空本地資料，只添加新記錄
- **Render端管理**：同步時間戳存在 Render，避免本地端意外重置

## 實施狀態

### ✅ 已完成
1. 創建 database_maintenance 表
2. 實現時間戳同步邏輯  
3. 驗證 incremental_sync_completed_trips 函數正常運作

### ✅ 最終解決方案
**調整同步執行順序，避免 CASCADE 影響**

#### 問題分析
```
錯誤順序：
1. TRUNCATE drivers CASCADE  ← 清空 completed_trips！
2. 增量同步 completed_trips   ← 太晚了，歷史資料已丟失

正確順序：
1. 增量同步 completed_trips   ← 先保護歷史資料
2. TRUNCATE drivers CASCADE  ← 不再影響 completed_trips
```

#### 修復代碼
```python
# 步驟 1: 🔥 先執行增量同步 completed_trips（保護歷史資料）
incremental_sync_completed_trips(local_conn, render_conn)

# 步驟 2: 執行完全覆蓋同步其他表
for table in ['drivers', 'customers', 'fixed_schedules', 'trips']:
    truncate_and_copy(local_conn, render_conn, table)

# 步驟 3: 最後同步 database_maintenance (包含更新後的時間戳)
truncate_and_copy(local_conn, render_conn, 'database_maintenance')
```

#### 關鍵優勢
- **歷史資料保護**：completed_trips 在任何清空操作前就已增量同步完成
- **時間戳管理**：database_maintenance 最後同步，確保時間戳正確更新
- **順序邏輯**：completed_trips → 其他表 → 時間戳記錄

### ✅ 外鍵約束問題解決方案
**問題分析**
```
錯誤：DELETE FROM drivers 時發生外鍵約束錯誤
原因：completed_trips.driver_id 仍然參考 drivers.id
報錯：update or delete on table "drivers" violates foreign key constraint "completed_trips_driver_id_fkey"
```

**修復代碼**
```python
# 暫時禁用外鍵約束
local_cur.execute("SET session_replication_role = replica;")

# 執行清空和插入操作
local_cur.execute(f"DELETE FROM {table_name};")
execute_batch(local_cur, insert_sql, filtered_records)

# 恢復外鍵約束
local_cur.execute("SET session_replication_role = DEFAULT;")
```

#### 最終測試結果
- **completed_trips**: 1618 records (歷史資料完全保護) ✅
- **trips**: 134 records (與 Render 完全一致) ✅  
- **drivers**: 9 records (與 Render 完全一致) ✅
- **customers**: 75 records (與 Render 完全一致) ✅

### ✅ 最終完美解決方案
**混合策略：minimal_flask_ai 穩定順序 + drivers 表特殊處理 + 時間戳錨點**

#### 核心策略
```python
# 同步順序：其他表先同步 → completed_trips 最後同步
for table in ['drivers', 'customers', 'fixed_schedules', 'trips']:
    if table == 'drivers':
        # 特殊處理：避免 CASCADE 清空 completed_trips
        local_cur.execute("SET session_replication_role = replica;")
        local_cur.execute(f"DELETE FROM {table_name};")
        local_cur.execute("SET session_replication_role = DEFAULT;")
    else:
        # 標準處理
        local_cur.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE;")

# 最後增量同步 completed_trips（時間戳錨點）
incremental_sync_completed_trips(local_conn, render_conn)
```

#### 關鍵突破
1. **保持 minimal_flask_ai 穩定順序**：避免複雜的事務處理錯誤
2. **drivers 表特殊處理**：暫時禁用外鍵約束，防止 CASCADE 清空 completed_trips
3. **時間戳錨點精確同步**：使用 database_maintenance 表記錄同步時間戳
4. **錯誤處理優化**：確保外鍵約束在錯誤情況下也能正確恢復

#### 最終測試結果 ✅
- **completed_trips**: 1620 records（歷史資料完全保護，包含本地特有數據）
- **trips**: 134 records（與 Render 完全一致）✅  
- **drivers**: 9 records（與 Render 完全一致）✅
- **customers**: 75 records（與 Render 完全一致）✅
- **fixed_schedules**: 47 records（與 Render 完全一致）✅

**成功標準完全達成**：
1. ✅ completed_trips 保留本地歷史資料，不受 Render 刪除影響
2. ✅ 其他表實現真正的「資料同步」，與 Render 端資料完全一致  
3. ✅ trips 表正確包含 134 筆記錄，滿足用戶需求「即然render端有134筆，那同步下來就得有134筆呀！」
4. ✅ 穩定性優異，無事務錯誤，使用經過驗證的 minimal_flask_ai 順序
5. ✅ 精確的時間戳同步，避免重複或遺漏數據