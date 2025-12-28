# 客戶 AI 沙盒開發任務清單

- [x] **客戶查詢 (Sandbox Read)**
    - [x] 設置基本路由 (`webhook.py` -> `CustomersAIService`)
    - [x] 建立 `CustomerSandbox` 模型 (對應 `customers` 表)
    - [x] 實現 `_tool_customer_lookup` 工具
    - [x] 實現 `process_sandbox_message` 處理查詢意圖
    - [x] [使用者審查] 驗證查詢功能 (fuzzy search, partial match)

- [x] **客戶新增 (Sandbox Create)**
    - [x] 實現 `_tool_customer_create` 工具
    - [x] 更新 `process_sandbox_message` 支援新增意圖
    - [x] **[安全]** 實作「變更確認」流程 (Propose -> Confirm -> Execute)
    - [x] [使用者審查] 驗證新增功能與確認流程
    - [x] **[修復]** 解決 `Duplicate key value` 錯誤 (同步 `customers_id_seq1`)

- [x] **客戶修改與刪除 (Sandbox Update/Delete)**
    - [x] 實現 `_tool_customer_update` 工具
    - [x] 實現 `_tool_customer_delete` 工具
    - [x] 更新 `process_sandbox_message` 支援修改與刪除
    - [x] **[安全]** 更新確認流程以支援修改與刪除報告
    - [x] [使用者審查] 驗證修改與刪除功能

- [x] **模糊匹配與歧義處理 (Ambiguity Handling)**
    - [x] 在 `customers_ai_service.py` 實作模糊匹配預驗證
    - [x] 更新相關文件

- [x] **安全性與強健性 (Safety & Robustness)**
    - [x] 為寫入操作增加「您確定嗎？」確認步驟
    - [x] 限制上下文窗口或使用摘要以防止 token 溢出
    - [x] 實作 API 失敗的強健錯誤處理
    - [x] 增加輸入驗證 (電話正則表達式, 長度檢查)
    - [x] 實作歧義處理 (例如有多個「王」姓客戶時)
    - [x] **強制必填欄位**：將 `簡稱` 和 `類別` 設為必填
    - [x] **修復序號問題**：通過同步 `customers_id_seq1` 解決 `duplicate key` 錯誤
    - [x] **統一對話記憶 (短期記憶)**
        - [x] 更新 `conversation_context.py` 中的 `ConversationManager` 以支援 `customer_sandbox`
        - [x] 更新 `CustomersAIService` 以回傳 `missing_info` 結構
        - [x] 更新 `CustomersAIHandler` 以透過 `ConversationManager` 管理狀態
