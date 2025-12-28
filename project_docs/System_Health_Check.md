# System Health Check & AI Roadmap: Leveraging Gemini 2.5
# 系統健康檢查與 AI 路線圖：活用 Gemini 2.5

---

## 🇹🇼 繁體中文版 (Traditional Chinese)

**當前狀態**：系統已成功升級使用 `gemini-2.5-flash-001`。
**目標**：評估此升級是否能實現更「自然」的資料庫互動 (新增/刪除/修改)，並規劃下一步驟。

### 執行摘要
是的，切換到 `gemini-2.5-flash` 顯著提升了自然語言互動的潛力。然而，目前的系統架構透過嚴格的「功能定義 (Functions)」與「正則表達式護欄 (Regex-based Guardrails)」限制了 AI 的發揮。

為了真正解鎖「自然語言資料庫操作」（例如：「取消大衛下週所有的行程」或「把明天所有診所行程的車資改為 500 元」），我們需要適度放寬正則表達式的限制，在維持安全檢查的前提下，給予 AI 更多推理的信任。

### 1. 系統健康與能力分析

#### ✅ 優勢 (運作良好)
*   **安全第一**：系統極度安全。傾向於「澄清」而非「直接執行」，有效防止意外修改數據。
*   **上下文感知**：`IntentExecutor` 中的「三種時間狀態」(過去/現在/未來) 邏輯穩健。
*   **結構化意圖**：依靠 `UnifiedDateParser` 和精確的 Function Calling 定義，參數提取 (日期、地點、司機) 非常可靠。

#### ⚠️ 限制 (瓶頸)
*   **嚴格的「守門員」**：`gemini_functions.py` 中的 `should_use_function_calling` 使用硬編碼的正則表達式 (例如：必須包含「請假」或「#」+「$」) 才允許 AI 嘗試修改。
    *   **結果**：使用者說「我想取消大衛明天的行程」可能會失敗，只因為沒有匹配到確切的關鍵字，即使 Gemini 2.5 完全聽得懂。
*   **「先找再問」模式**：`clarify_user_intent` 強制進入按鈕式互動流程。
    *   **結果**：雖然對簡單的歧義有效，但阻礙了「一步到位」的複雜指令 (例如：「找出並取消明天所有行程」變成了「找出 -> 顯示列表 -> 使用者必須點擊按鈕」)。
*   **動作詞彙有限**：系統目前只「認識」 `passenger_leave` (乘客請假)、`update_fare` (修改車資)、`update_trip_status` (修改狀態 - 部分)。缺乏通用的「搜尋並修改」能力。

### 2. 路線圖：解鎖 Gemini 2.5 潛能
為了邁向「自然語言資料庫操作」，建議採取以下分階段改進：

#### 第一階段：放寬護欄 (立即執行)
**目標**：讓 Gemini 處理路由，而非正則表達式。
**行動**：
*   簡化 `should_use_function_calling`。不再檢查特定的關鍵字 (如 ['已完成', '統計'])，而是允許 Gemini 對任何修改意圖進行分類。
*   相信 `gemini-2.5-flash` 能比 `gemini-1.5` 更準確地分辨「查詢」與「修改」。

#### 第二階段：增強「更新」功能 (短期)
**目標**：允許自然語言對應到更複雜的資料庫更新。
**行動**：
*   擴展 `update_trip_status` 以處理批量條件。
    *   **目前**：`update_trip_status(trip_id, status)`
    *   **建議**：`batch_update_trips(date_range, driver_id, location, new_status)`
    *   這允許：「取消明天所有行程」-> AI 呼叫 `batch_update_trips(date='tomorrow', new_status='cancelled')`。

#### 第三階段：對話式修改 (中期) 🔥 (已部分實現！)
**目標**：允許修改操作具有多輪對話上下文。
**行動**：
*   如果使用者說「把價格改成 500」，而畫面上顯示 3 個行程，允許使用者回答「第一個」。
*   目前上下文嚴重依賴按鈕。我們可以在 `SmartAssistant` 中實作「焦點上下文 (Focus Context)」，記住上一次查詢的列表。
*   **(註：我們剛完成的 Sandbox 對話記憶即為此階段的實踐之一)**

#### 第四階段：智慧「類 SQL」推理 (長期)
**目標**：複雜分析。
**行動**：
*   利用 `advanced_query_processor.py`。目前它是從正則提取的字典構建 SQL。
*   **升級**：將 Schema 傳給 Gemini，讓它直接生成 SQL WHERE 子句 (或安全的中間表示法)。
*   **範例**：「顯示車資大於 500 但小於 1000 的行程」對正則來說很難，但對 Gemini 來說輕而易舉。

### 3. 具體程式碼建議
1.  **重構 `gemini_functions.py`**
    *   將 Python 程式碼中詳細的「觸發條件」邏輯移除，移入 Gemini 的 System Prompt。
    *   **原因**：Gemini 2.5 遵循系統指令的能力更好。硬編碼的觸發器 (`should_use_function_calling`) 會讓系統變得脆弱。
2.  **升級 `IntentExecutor._handle_clarify_intent`**
    *   目前以 QuickReply 結束。
    *   **改進**：增加「自然語言追問」選項。如果使用者回覆文字而非點擊按鈕，將之前的 `trips` 上下文傳給 Gemini，讓它知道「改那一個」是指什麼。
3.  **擴展 `modules/services/smart_assistant.py` Prompt**
    *   在 System Prompt 中包含「Schema 摘要」，讓 AI 知道哪些欄位可查詢/修改 (例如：「你可以依 `category`, `driver_id`, `status` 篩選」)。

---

## 🇺🇸 Original English Version

**Current Status**: The system has been successfully updated to use `gemini-2.5-flash-001`.
**Objective**: Determine if this upgrade allows for more "natural" interaction with the database (add/delete/modify) and outline the next steps.

### Executive Summary
Yes, switching to `gemini-2.5-flash` significantly increases the potential for natural language interaction. However, the current system architecture limits this potential by constraining the AI to a very rigid set of "Functions" and "Regex-based Guardrails".

To truly unlock "natural language database operations" (e.g., "Cancel all of David's trips next week" or "Change all clinic trips tomorrow to $500"), we need to loosen the regex constraints and trust the AI's reasoning capabilities more, while maintaining safety checks.

### 1. System Health & Capability Analysis

#### ✅ Strengths (What works well)
*   **Safety First**: The system is extremely safe. It favors "clarification" over "execution" prevents accidental data data modification.
*   **Context Awareness**: The "Three Time States" (Past/Present/Future) logic in `IntentExecutor` is robust.
*   **Structured Intent**: The extraction of parameters (Date, Location, Driver) is reliable thanks to `UnifiedDateParser` and precise Function Calling definitions.

#### ⚠️ Limitations (Bottlenecks)
*   **Rigid "Gatekeeping"**: `should_use_function_calling` in `gemini_functions.py` uses hard-coded regex (e.g., must contain "請假" or "#" + "$") to even allow the AI to try a modification.
    *   **Result**: A user saying "I want to cancel the trip for David tomorrow" might fail if it doesn't match the exact keyword list, even if Gemini 2.5 understands it perfectly.
*   **"Find then Ask" Pattern**: `clarify_user_intent` forces a button-based interaction flow.
    *   **Result**: Efficient for simple ambiguity, but prevents "One-Shot" complex commands (e.g., "Find and cancel all trips for tomorrow" becomes "Find -> Show List -> User must click button").
*   **Limited Action Vocabulary**: The system only "knows" `passenger_leave`, `update_fare`, `update_trip_status` (partially). It lacks generic "search and modify" capabilities.

### 2. Roadmap: Unlocking Gemini 2.5 Capabilities
To move toward "Natural Language Database Operations", we recommend the following phased improvements:

#### Phase 1: Relaxing the Guardrails (Immediate)
**Objective**: Let Gemini handling routing, not Regex.
**Action**:
*   Simplify `should_use_function_calling`. Instead of checking for specific keywords like ['已完成', '統計'], allow Gemini to classify any modification intent.
*   Trust `gemini-2.5-flash` to distinguish between a "Query" and a "Modification" better than `gemini-1.5`.

#### Phase 2: Enhanced "Update" Functions (Short-term)
**Objective**: Allow natural language to map to more complex database updates.
**Action**:
*   Expand `update_trip_status` to handle batch criteria.
    *   **Current**: `update_trip_status(trip_id, status)`
    *   **Proposed**: `batch_update_trips(date_range, driver_id, location, new_status)`
    *   This allows: "Cancel all trips for tomorrow" -> AI calls `batch_update_trips(date='tomorrow', new_status='cancelled')`.

#### Phase 3: Conversational Modification (Medium-term)
**Objective**: Allow multi-turn context for modifications.
**Action**:
*   If a user says "Change the price to 500", and there are 3 trips, instead of just showing buttons, allow the user to reply "The first one".
*   Currently, context is heavily button-dependent. We can implement a "Focus Context" in `SmartAssistant` that remembers the last queried list.

#### Phase 4: Intelligent "SQL-like" Reasoning (Long-term)
**Objective**: Complex analytics.
**Action**:
*   Leverage `advanced_query_processor.py`. Currently, it builds SQL from regex-extracted dicts.
*   **Upgrade**: Pass the schema to Gemini and let it generate the SQL WHERE clauses (or a safe intermediate representation) directly.
*   **Example**: "Show me trips where the price is > 500 but < 1000" is hard for regex, but trivial for Gemini.

### 3. Specific Code Recommendations
1.  **Refactor `gemini_functions.py`**
    *   Remove the detailed "Trigger Conditions" logic from the Python code and move it into the System Prompt for Gemini.
    *   **Why**: Gemini 2.5 follows system instructions much better. Hard-coded triggers in Python (`should_use_function_calling`) make the system brittle.
2.  **Upgrade `IntentExecutor._handle_clarify_intent`**
    *   Currently, it ends with a QuickReply.
    *   **Improvement**: Add a "Natural Language Follow-up" options. If the user replies with text instead of clicking a button, pass the previous `trips` context to Gemini so it knows what "Change that one" means.
3.  **Expand `modules/services/smart_assistant.py` Prompt**
    *   Include a "Schema Summary" in the system prompt so the AI knows what fields are queryable/modifiable (e.g., "You can filter by `category`, `driver_id`, `status`").

### Conclusion
The model upgrade is a great first step. The next step is to remove the training wheels (heavy regex routing) and let the model drive the interaction, supported by safer, broader tools.
