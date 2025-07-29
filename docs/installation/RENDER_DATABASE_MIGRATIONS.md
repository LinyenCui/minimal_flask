# Render 數據庫遷移記錄

此文件記錄所有需要在 Render 數據庫上執行的修改，以保持本地開發環境與生產環境同步。

## 待執行的遷移

目前無待執行的遷移。

## 歷史遷移記錄

### 已完成的遷移

#### 2025-06-08: 修復客戶ID函數
- **問題**：`get_next_available_id()` 函數錯誤查詢 `drivers` 表計算 `customers` 表ID
- **修復**：函數正確查詢 `customers` 表
- **狀態**：✅ 已在 Render 執行成功
- **影響**：解決客戶預約時的主鍵衝突問題

#### 2025-06-08: 清理 audit_logs 表
- **原因**：audit 系統已棄用，改用 modification tracking 欄位
- **本地操作**：刪除 `audit_logs` 表
- **Render狀態**：無此表（正確）
- **當前方案**：使用 `trips` 和 `completed_trips` 表中的 `modified_by`, `modification_reason`, `modification_time` 欄位

---

## 使用說明

1. 在推送代碼到 Render 之前，檢查此文件中的「待執行的遷移」
2. 登入 Render 數據庫控制台
3. 依序執行所有待執行的遷移腳本
4. 執行驗證命令確認遷移成功
5. 將已完成的遷移移至「歷史遷移記錄」部分 