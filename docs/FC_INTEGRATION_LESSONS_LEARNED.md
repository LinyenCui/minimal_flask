# FC（Function Calling）整合心路歷程與教訓

> **日期**：2025-12-20  
> **案例**：修改車資功能的 FC 整合  
> **結果**：成功，但走了很多彎路

---

## 🎯 核心教訓：AI 要成為決策者，必須先了解現有系統

根據 [AI智能化改進建議報告](/Users/linyancui/Downloads/G3pro-AI智能化改進建議報告.md) 的願景：

**我們的目標是讓 AI 從「翻譯官」進化為「決策者」。**

但是，**AI 要成為決策者，前提是必須完整了解現有系統的能力：**

1. 現有系統能做什麼？（有哪些功能、哪些服務）
2. 這些功能的實現邏輯在哪裡？（程式碼位置、參數格式）
3. AI 應該如何調用這些功能來滿足用戶需求？

**這次的教訓就是：我們急著讓 AI 做決策，卻沒有先讓 AI（或開發者）了解現有系統已經具備的能力。**

---

## 🎯 AI 決策者的正確思路

**AI 作為決策者，應該這樣工作：**

```
用戶請求：「幫我修改 #5297 車資 140+60」
    ↓
AI 決策者思考：
    1. 用戶想做什麼？→ 修改車資
    2. 系統有這個功能嗎？→ 有，在 ai_fare_service.py
    3. 這個功能需要什麼參數？→ trip_id, meter_fare, extra_fare, reason
    4. 用戶有提供原因嗎？→ 沒有
    5. 系統對「沒有原因」的處理是什麼？→ 會追問
    6. 我應該怎麼做？→ 調用現有的追問流程
    ↓
AI 執行：調用 ai_fare_service.py 的追問邏輯
    ↓
結果：完整的用戶體驗（追問 → 確認 → 執行）
```

**而不是：**

```
用戶請求：「幫我修改 #5297 車資 140+60」
    ↓
AI 決策者（不了解系統）：
    1. 用戶想修改車資
    2. 我自己寫一個修改邏輯吧！
    ↓
結果：重複造輪子，功能不完整
```

---

## ❌ 這次犯的錯誤

### 問題 1：沒有先了解現有系統的能力

在修改 `intent_executor.py` 的 `_handle_update_fare` 函數時，我們：
- 沒有先查看 `ai_fare_service.py` 已經有完整的車資修改流程
- 沒有先查看 `trip_handler.py` 已經有正確的修改原因疊加邏輯
- 直接在 FC 層面寫了一套新的邏輯

結果：
- 重複造輪子
- 新邏輯不完整（缺少追問原因、缺少疊加編號）
- 程式碼變得臃腫

### 問題 2：盲目新增功能，而不是複用

當發現問題時，我們的第一反應是「新增」：
- 新增 `is_default_reason` 檢查
- 新增對話類型 `fare_modification_reason`
- 新增確認框生成邏輯

但其實：
- `ai_fare_service.py` 第 561 行已經有 `is_default_reason` 檢查
- `ai_modification_reason` 對話類型已經存在
- `execute_fare_modification()` 已經有完整的確認框生成

### 問題 3：不了解系統的對話狀態管理

我們不知道：
- `text_message_handler.py` 有「自動清除舊對話狀態」的機制
- `end_conversation()` 會自動清除 `pending_modification`
- 「確認AI修改」需要被列為「對話流程命令」才不會被清除

---

## ✅ 正確的做法：AI 決策者的修改流程

### 第一步：盤點現有系統的能力

在修改任何功能之前，AI 決策者（或開發者）必須回答以下問題：

```
🔍 系統能力盤點清單

1. 這個功能原本是怎麼實現的？
   - 用戶輸入什麼格式？
   - 哪個 handler/service 處理？
   - 對話流程是怎樣的？
   - 確認框是怎麼生成的？

2. 現有的邏輯在哪裡？
   - 哪個函數負責核心業務？
   - 有哪些輔助函數可以複用？
   - 有哪些驗證邏輯已經寫好了？

3. AI 決策者應該如何「指揮」這些功能？
   - AI 負責理解用戶意圖、提取參數
   - AI 負責判斷應該調用哪個現有功能
   - 業務邏輯由現有函數執行（不要重寫）
```

### 第二步：AI 決策者「指揮」現有功能

AI 決策者的角色是「指揮官」，而不是「工兵」：

```python
# ✅ 正確：AI 決策後，調用現有功能
def _handle_update_fare(self, params, user_id, reply_token):
    # AI 已經識別出用戶意圖和參數
    trip_id = params.get("trip_id")
    reason = params.get("reason", "")
    
    # AI 判斷：用戶沒有提供原因，需要追問
    # → 調用現有的追問對話系統（不要自己重寫）
    if is_default_reason(reason):
        start_conversation(user_id, "ai_modification_reason", ...)
        return
    
    # AI 判斷：用戶提供了原因，可以執行
    # → 調用現有的確認流程（不要自己重寫）
    from ai_fare_service import execute_fare_modification
    result = execute_fare_modification(trip, modification_intent, user_id)
    return result
```

```python
# ❌ 錯誤：AI 自己當工兵，重新實現
def _handle_update_fare(self, params, user_id, reply_token):
    # 自己查數據庫（現有函數已經有）
    # 自己計算車資（現有函數已經有）
    # 自己生成確認訊息（現有函數已經有）
    # 自己處理對話狀態（現有函數已經有）
    # ... 幾十行重複的代碼
```

### 第三步：擴展 AI 的決策能力

當現有系統能力不足時，才考慮新增功能。例如：

- 用戶說「上上個月的報表」→ 現有系統無法解析「上上個月」→ 新增日期解析能力
- 用戶說「這週哪天生意最好」→ 現有系統沒有分析功能 → 新增 `analyze_data` 功能

**這才是 AI 決策者的價值：理解用戶需求，並擴展系統能力來滿足。**

### 第三步：檢查對話狀態管理

修改任何涉及對話的功能時，必須檢查：

1. **對話類型是否在分發列表中？**
   - `text_message_handler.py` 的對話類型列表
   - `conversation_dispatcher.py` 的 handlers 映射

2. **確認/取消命令是否在「對話流程命令」列表中？**
   - `text_message_handler.py` 的 `conversation_flow_commands`
   - `is_conversation_cmd` 判斷邏輯

3. **`end_conversation()` 是否會清除需要的狀態？**
   - 注意 `end_conversation()` 會自動調用 `clear_pending_modification()`
   - 如果需要保留狀態，要在結束對話後重新設定

---

## 📋 修改功能前的檢查清單

### 在寫任何代碼之前：

- [ ] 1. 搜尋現有實現：`grep -r "功能關鍵字" modules/`
- [ ] 2. 閱讀相關的 handler 和 service
- [ ] 3. 理解現有的對話類型和狀態管理
- [ ] 4. 確認有哪些現成函數可以調用
- [ ] 5. 如果有不清楚的地方，**先問**，不要猜測

### 在修改代碼時：

- [ ] 1. 優先調用現有函數，而不是重新實現
- [ ] 2. 如果必須新增邏輯，確認不會與現有邏輯衝突
- [ ] 3. 新的對話類型要加到分發列表中
- [ ] 4. 新的確認/取消命令要加到「對話流程命令」列表中
- [ ] 5. 測試完整的用戶流程，包括追問、確認、取消

### 在測試時：

- [ ] 1. 測試正常流程（有原因/無原因）
- [ ] 2. 測試確認和取消按鈕
- [ ] 3. 測試對話超時的情況
- [ ] 4. 檢查日誌是否有「清除對話狀態」的警告

---

## 🔍 這次修改的關鍵代碼位置

### 1. 現有的車資修改流程（不要重寫這些）

```
modules/services/ai_fare_service.py
├── is_default_reason 檢查（第 561 行）
├── 追問原因的對話系統（第 581-610 行）
├── execute_fare_modification()（第 1263 行）
└── create_ai_modification_confirm_flex()（調用 flex_designs）

modules/handlers/trip_handler.py
├── handle_record_fare()（第 365 行）
└── build_modification_update_dict()（疊加編號邏輯）

modules/flex_designs/ai_fare_query_flex.py
└── create_ai_modification_confirm_flex()（確認框 UI）
```

### 2. 對話狀態管理（修改前要檢查）

```
modules/handlers/text_message_handler.py
├── 對話類型分發列表（第 161 行）
├── conversation_flow_commands（第 180 行）
└── is_conversation_cmd 判斷（第 195 行）

modules/handlers/conversation_dispatcher.py
├── handlers 映射（第 30 行）
└── handle_ai_modification_reason_conversation()（第 257 行）

modules/utils/conversation_context.py
├── start_conversation()
├── end_conversation()（會清除 pending_modification！）
└── set/get/clear_pending_modification()
```

### 3. FC 接入點（這裡做最小修改）

```
modules/core/intent_executor.py
└── _handle_update_fare()（接入現有流程，不重寫）
```

---

## 💡 總結：AI 決策者的修改守則

### 核心理念

**AI 要成為決策者，必須先成為「系統能力的專家」。**

只有完整了解現有系統能做什麼，AI 才能：
1. 正確地將用戶請求對應到現有功能
2. 判斷何時需要擴展新功能
3. 給用戶最好的回應和體驗

### 修改功能的黃金法則

1. **先盤點，後動手** 
   - 用戶要的功能，系統現在能做嗎？
   - 如果能，邏輯在哪裡？直接調用
   - 如果不能，才考慮新增

2. **AI 是指揮官，不是工兵**
   - AI 負責理解意圖、做決策
   - 業務邏輯由現有服務執行
   - 不要在 AI 層重複實現業務邏輯

3. **擴展而非取代**
   - 新功能應該是「擴展」現有能力
   - 不是「取代」或「重寫」現有邏輯
   - 保持系統的穩定性和一致性

4. **檢查對話狀態**
   - 新的確認/取消命令要加到白名單
   - 理解 `end_conversation()` 的副作用
   - 確保對話流程完整

### 最終目標

讓 AI 真正成為「決策者」：
- 用戶說自然語言 → AI 理解意圖
- AI 判斷應該用哪個功能 → 調用現有服務
- 現有功能不足 → AI 建議或執行擴展
- 用戶獲得滿意的結果

**這才是「從翻譯官進化為決策者」的真正含義。**
