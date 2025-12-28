# Customers AI Sandbox Walkthrough

I have implemented the "Customers AI Sandbox" which allows performing natural language operations on the `customers` database table using Gemini 2.5 (accessed via Vertex AI).

## Feature Overview

### 1. Natural Language Query
Users can ask questions like `cu 查 Test` or `客 找 地址在台北的`.
- **Mechanism**:
  1. Trigger detected in `webhook.py`.
  2. `customers_ai_handler` receives message.
  3. `customers_ai_service` calls Gemini with `customer_lookup` tool.
  4. Result returned to user.

### 2. Safe Write Operations (Create/Update/Delete)
Users can request changes like `cu 新增客戶 測試店...`.
- **Mechanism**:
  1. Gemini identifies intent and calls `customer_create`.
  2. **Interception**: `customers_ai_service` detects a write operation and returns a "Proposal" instead of executing.
  3. **Confirmation**: `customers_ai_handler` saves the proposal in session state and asks user to confirm.
  4. **Execution**: User replies "確認", handler executes the actual tool.

## Files Created/Modified

### New Files
- [customers_ai_service.py](file:///Users/linyancui/minimal_flask/modules/services/customers_ai_service.py): Core logic, `CustomerSandbox` model, and Gemini Tool definitions. **Updated**: Added pre-validation to handle fuzzy matching for Update/Delete.
- [customers_ai_handler.py](file:///Users/linyancui/minimal_flask/modules/handlers/customers_ai_handler.py): Handles routing, user state, and confirmation flow.

### Modified Files
- [webhook.py](file:///Users/linyancui/minimal_flask/modules/routes/webhook.py): Injected routing logic to intercept messages starting with `cu` / `客`.

## Verification Results

I verified the feature using a script `verify_customers_sandbox.py` that simulated the message flow and Vertex AI interaction.

### Test Case 1: Query
**Input**: `cu 查 TestUser`
**Output**:
```
{'type': 'text_response', 'content': '找到了名為 TestUser 的客戶...'}
```
Gemini successfully called `customer_lookup` and summarized the result.

### Test Case 2: Create Proposal
**Input**: `cu 新增客戶 測試店 地址是台北市 電話 02-22223333`
**Output**:
```
# 客戶 AI 沙盒 (Customers AI Sandbox) 功能導覽

## 🌟 功能概覽
**客戶 AI 沙盒** 是一個讓您能使用自然語言查詢、新增、修改與刪除客戶資料的智慧功能。它具有以下特點：
*   **自然語言操作**：直接說「幫我查文賢路上的診所」或「新增客戶...」。
*   **安全沙盒**：所有寫入操作（新增、修改、刪除）都需要您的**二次確認**才會執行。
*   **智慧模糊搜尋**：即使名字只記得一半（例如「肯德基」），也能找到正確的客戶。
*   **短期記憶**：若新增資料時缺少必要欄位，系統會貼心提醒並記住您已輸入的內容，不用重頭來過。

## 🛠️ 如何使用

### 1. 查詢客戶 (Lookup)
想找客戶資料？直接問！
> **使用者**：「查一下文賢路有沒有診所」
> **AI**：(列出符合條件的客戶列表)

### 2. 新增客戶 (Create)
新增客戶時，系統會自動檢查必填欄位。
> **使用者**：「新增客戶 王小明 住台南市安平區」
> **AI**：「請提供『簡稱、類別』...」
> **使用者**：「簡稱 小明，類別 住家」
> **AI**：(顯示完整資料並請求確認)

### 3. 修改資料 (Update)
資料有誤？隨時修正。
> **使用者**：「把 小明 的電話改成 0912345678」
> **AI**：(確認將「王小明」的電話更新為「0912345678」)

### 4. 刪除客戶 (Delete)
清理舊資料。
> **使用者**：「刪除 小明 這筆資料」
> **AI**：(嚴重警告：即將刪除「王小明」，請確認)

## 🏗️ 技術亮點
*   **模糊匹配**：同時搜尋 `name` 和 `short_name`，解決「全名 vs 簡稱」的困擾。
*   **嚴格驗證**：強制要求 `short_name` 和 `category`，確保後續派班功能正常運作。
*   **對話記憶**：整合系統級 `ConversationManager`，實現流暢的多輪對話補填資料體驗。
*   **智慧路由**：WebHook 層級自動識別活躍的沙盒對話，讓您在補填資料時無需重複輸入指令前綴 (例如 `/客`)。

## 🛡️ 安全措施
*   **前綴觸發**：嚴格限制只有特定前綴指令 (`/客` 或 `cu`) 才會觸發沙盒 (除非正在進行持續對話)。
*   **讀取限制**：Sandbox 只能「選取 (`SELECT`)」資料，無法直接修改 (`UPDATE/DELETE`) 原始資料庫。
*   **獨立模型**：使用 `CustomerSandbox` 模型，避免影響主程式運作。
- **Fuzzy Matching**: Before proposing a change, the system searches for the customer. If exact match fails but a unique partial match exists, it auto-corrects the target. If ambiguous, it asks the user to clarify.
