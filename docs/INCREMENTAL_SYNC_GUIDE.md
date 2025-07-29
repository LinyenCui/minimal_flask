# 🔄 增量資料庫同步系統使用指南

## 概述

全新的智能增量同步系統，解決了原有同步過程中本地數據丟失的問題，提供安全、高效的資料庫同步方案。

## ✨ 主要功能

### 🛡️ 保護性同步
- **保留本地數據**: 不會覆蓋或刪除本地獨有的數據
- **智能增量**: 只同步新增和更新的記錄
- **生成欄位過濾**: 自動處理PostgreSQL生成欄位問題
- **序列自動校準**: 同步後自動修復序列值

### 🔧 技術特性
- **UPSERT策略**: 使用ON CONFLICT處理重複記錄
- **批量處理**: 高效的批量數據插入
- **錯誤恢復**: 遇到錯誤時自動回滾
- **詳細日誌**: 完整的操作記錄和統計

## 🚀 使用方法

### 1. 透過Line Bot （推薦）

在Line群組中輸入以下任一命令：

```
資料庫同步       # 執行保護性增量同步（預設）
增量同步         # 執行標準增量同步  
保護同步         # 執行保護性同步
同步狀態         # 查看當前同步狀態
```

系統會回應Flex訊息顯示同步狀態，完成後會發送通知。

### 2. 命令行工具

```bash
# 執行保護性同步（預設）
python scripts/smart_sync.py

# 執行標準增量同步
python scripts/smart_sync.py --mode incremental

# 保護更多天數的本地數據
python scripts/smart_sync.py --preserve-days 10

# 只同步特定表
python scripts/smart_sync.py --tables trips drivers

# 查看幫助
python scripts/smart_sync.py --help
```

### 3. 程式碼整合

```python
from modules.services.incremental_sync_service import IncrementalSyncService

# 初始化服務
sync_service = IncrementalSyncService()

# 執行保護性同步
results = sync_service.preserve_local_data_sync()

# 執行標準增量同步
results = sync_service.full_incremental_sync()

# 檢查結果
if results['success']:
    print(f"同步成功: {results['total_new_records']} 筆新記錄")
else:
    print(f"同步失敗: {results['errors']}")
```

## 📊 同步策略

### 支援的表格

| 表名 | 同步方式 | 生成欄位過濾 | 序列同步 |
|------|----------|--------------|----------|
| `trips` | 增量UPSERT | ✅ actual_fare, total_fare | ✅ |
| `completed_trips` | 增量UPSERT | ✅ actual_fare, total_fare | ✅ |
| `drivers` | 增量UPSERT | ❌ | ✅ |
| `customers` | 增量UPSERT | ❌ | ✅ |
| `fixed_schedules` | 增量UPSERT | ❌ | ✅ |

### 數據保護機制

1. **重疊同步**: 預設往前推3天，確保不遺漏數據
2. **衝突處理**: 使用ON CONFLICT UPDATE策略
3. **本地優先**: 保留本地獨有的數據記錄
4. **原子操作**: 失敗時自動回滾，保證數據一致性

## 🔍 監控和診斷

### 查看同步日誌

```bash
# 查看詳細日誌
tail -f logs/sync.log

# 查看最近的同步結果
cat last_sync_result.txt
```

### 測試同步功能

```bash
# 測試同步服務
python test_incremental_sync.py

# 測試資料庫連接
python -c "
from modules.services.incremental_sync_service import IncrementalSyncService
service = IncrementalSyncService()
print('Local:', service.get_connection(service.local_config, 'Local') is not None)
print('Render:', service.get_connection(service.render_config, 'Render') is not None)
"
```

## ⚠️ 注意事項

### 環境變數配置

確保以下環境變數已正確設定：

```bash
# Render資料庫
RENDER_DB_HOST=dpg-xxxxx.singapore-postgres.render.com
RENDER_DB_USER=your_user
RENDER_DB_NAME=your_db
RENDER_DB_PASSWORD=your_password

# 本地資料庫
LOCAL_DB_HOST=localhost
LOCAL_DB_USER=your_user
LOCAL_DB_NAME=dispatch_db
LOCAL_DB_PASSWORD=your_password
```

### 安全建議

1. **備份重要數據**: 同步前建議備份關鍵數據
2. **測試環境先試**: 在生產環境前先在測試環境驗證
3. **監控同步頻率**: 避免過於頻繁的同步操作
4. **檢查網路狀況**: 確保與Render的穩定連接

## 🚨 故障排除

### 常見問題

1. **連接失敗**
   ```
   ❌ 連接 Render 資料庫失敗
   ```
   - 檢查網路連接
   - 驗證環境變數配置
   - 確認Render服務狀態

2. **生成欄位錯誤**
   ```
   ❌ 無法插入生成欄位
   ```
   - 系統會自動過濾，如持續發生請檢查表結構

3. **序列不同步**
   ```
   ❌ 序列值錯誤
   ```
   - 系統會自動修復，可手動執行序列同步

### 手動恢復

```bash
# 如果同步失敗，可以手動執行恢復
python scripts/smart_sync.py --mode preserve --preserve-days 1

# 或使用原有腳本作為備選
python scripts/sync_from_render.py
```

## 📈 性能優化

- **批量處理**: 使用execute_batch提高插入效率
- **索引優化**: 基於日期和ID欄位的查詢優化
- **連接池**: 自動管理資料庫連接
- **內存管理**: 分批處理大量數據避免內存溢出

## 🔮 未來擴展

- [ ] 支援雙向同步
- [ ] 衝突解決策略配置
- [ ] 實時增量同步
- [ ] 詳細的數據差異報告
- [ ] 自動化定時同步

---

*最後更新: 2025-07-27*  
*版本: v1.0*