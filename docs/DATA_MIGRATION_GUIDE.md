# 📊 資料搬移標準作業程序

## 🎯 目的
解決從Render匯出資料到本地時，PostgreSQL序列不同步導致的主鍵衝突問題。

## ⚠️ 問題根源
當執行 `TRUNCATE TABLE ... RESTART IDENTITY CASCADE;` 後匯入資料，序列值會停留在1，但資料表中已有較大的ID值，造成新插入記錄時主鍵衝突。

## 🔧 正確的資料搬移流程

### 步驟 1：清空目標表
```sql
TRUNCATE TABLE completed_trips RESTART IDENTITY CASCADE;
```

### 步驟 2：匯入資料
```sql
-- 執行您的INSERT語句
INSERT INTO completed_trips (...) VALUES (...);
```

### 步驟 3：🔑 **關鍵步驟 - 修復序列**
```sql
-- 自動設定序列為最大ID+1
SELECT setval('completed_trips_id_seq', COALESCE(MAX(id), 0) + 1, false) FROM completed_trips;
```

### 步驟 4：驗證修復結果
```sql
-- 檢查序列值
SELECT last_value FROM completed_trips_id_seq;

-- 檢查最大ID
SELECT MAX(id) FROM completed_trips;
```

## 🛠️ 自動化工具

### 方法1：命令行工具（推薦）
```bash
# 快速修復模式（資料搬移後使用）
python fix_sequence_after_import.py --quick

# 或使用互動模式
python fix_sequence_after_import.py
```

### 方法2：網頁管理介面（常態化）
訪問：`http://你的域名/admin/database-tools`

特點：
- 視覺化介面
- 即時狀態檢查
- 一鍵修復功能
- 詳細修復報告

## 📋 檢查清單

- [ ] 執行TRUNCATE
- [ ] 匯入資料完成
- [ ] **修復序列（必做！）**
- [ ] 驗證序列值 > 最大ID
- [ ] 測試插入新記錄

## 🚨 常見錯誤

### ❌ 錯誤做法
```
1. TRUNCATE table
2. 匯入資料
3. 結束 ← 忘記修復序列
```

### ✅ 正確做法  
```
1. TRUNCATE table
2. 匯入資料
3. 修復序列 ← 關鍵步驟
4. 驗證結果
```

## 📞 緊急修復

如果已經出現主鍵衝突：
```bash
python fix_sequence_after_import.py
```

## 🔍 其他相關表格

如果需要搬移其他表格，也要注意序列問題：
- `trips` → `trips_trip_id_seq`
- `fixed_trips` → `fixed_trips_id_seq`
- 等等...

使用腳本選項2可以一次檢查所有序列。 