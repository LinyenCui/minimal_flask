# 自然語言操作資料庫 - 發展計劃

> **建立日期**：2026-01-12
> **目標**：讓沙盒的 Function Calling 架構逐步取代主系統，實現更人性化的資料庫操作

---

## 一、現狀分析

### 1.1 兩套系統的對比

| 面向 | 主系統 (text_message_handler) | 沙盒 (customers_ai_handler) |
|-----|------------------------------|----------------------------|
| **架構** | 命令解析 → AI 翻譯 → 再解析 → 執行 | AI Function Calling → 直接執行 |
| **用戶體驗** | 需要記命令格式 | 自然語言 |
| **缺失處理** | 報錯 | 追問補充 |
| **危險操作** | 部分有確認 | 統一確認機制 |
| **多輪對話** | 有限支援 | 完整支援 |
| **程式碼量** | ~1,500 行 (smart_assistant) | ~630 行 |

### 1.2 主系統的問題

```
用戶: "昨天5386診所班次"
       ↓
smart_assistant 解析 (1,500行)
       ↓
生成命令 "查已完成 昨天 司機5386 診所"
       ↓
text_message_handler 再解析 (1,027行)
       ↓
執行查詢
```

**問題**：
1. 兩次解析，浪費效能
2. 命令格式是系統內部概念，不應暴露給用戶
3. AI 翻譯可能出錯，但用戶看不到
4. 維護兩套解析邏輯

### 1.3 沙盒的優勢

```
用戶: "預約明天下午兩點從高鐵站到東洋"
       ↓
Gemini Function Calling
       ↓
booking_create(date="明天", time="14:00", start_point="高鐵站", end_point="東洋")
       ↓
確認 → 執行
```

**優勢**：
1. 一次解析，直接調用函數
2. 缺失信息時追問（"請問要幾點？"）
3. 危險操作統一確認
4. 支援實體連結（"改那一班"）

---

## 二、功能差距分析

### 2.1 沙盒已實現的 Functions

| Function | 說明 | 是否需確認 |
|----------|------|-----------|
| `customer_lookup` | 查詢客戶 | 否 |
| `customer_create` | 新增客戶 | 是 |
| `customer_update` | 修改客戶 | 是 |
| `customer_delete` | 刪除客戶 | 是 |
| `booking_create` | 預約叫車 | 是 |
| `trip_update` | 修改行程 | 是 |
| `trip_delete` | 取消行程 | 是 |

### 2.2 主系統有但沙盒缺少的功能

| 功能 | 主系統命令 | 優先級 | 備註 |
|-----|-----------|--------|------|
| **班次查詢** | `查班次`, `診所班次` | P0 | 最常用功能 |
| **已完成查詢** | `查已完成` | P0 | 最常用功能 |
| **乘客請假** | `乘客請假 [ID] [加成] [原因]` | P0 | 核心業務 |
| **車資記錄** | `記錄車資 [ID] [錶價] [加成]` | P0 | 核心業務 |
| **統計金額** | `統計金額 [條件]` | P1 | 報表相關 |
| **指派司機** | `指派司機 [ID] [司機]` | P1 | 班次管理 |
| **匯入班次** | `匯入固定班次 [週次]` | P1 | 週期操作 |
| **修改狀態** | `修改狀態 [ID] [狀態]` | P2 | 較少用 |
| **報表生成** | `生成周報表`, `生成月報表` | P2 | 週期操作 |

### 2.3 沙盒需要強化的能力

| 能力 | 現狀 | 需強化 |
|-----|------|--------|
| 三時間態判斷 | 無 | 根據日期自動判斷查 trips 或 completed_trips |
| 分頁支援 | 無 | 查詢結果超過 N 筆時分頁 |
| 日期範圍 | 有限 | 支援 "12/1-12/6"、"本週"、"上週" |
| 上下文記憶 | 基礎 | 記住最近操作的班次，支援 "那一班"、"第三班" |

---

## 三、新 Function 設計

### 3.1 P0：核心查詢與操作

```python
# 1. 班次查詢（統一入口，自動判斷時間態）
trip_query = FunctionDeclaration(
    name="trip_query",
    description="""
    查詢班次信息。系統會自動根據日期判斷查詢 trips 或 completed_trips。

    使用場景：
    - "今天診所班次"
    - "昨天5386已完成班次"
    - "12/1-12/6 東洋班次"
    - "明天有哪些班次"
    """,
    parameters={
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "日期（今天、昨天、12/15）"},
            "date_range": {"type": "string", "description": "日期範圍（12/1-12/6）"},
            "driver_id": {"type": "integer", "description": "司機編號"},
            "category": {"type": "string", "description": "類別：診所、東洋、臨時"},
            "location": {"type": "string", "description": "地點關鍵字"},
            "status": {"type": "string", "description": "狀態：準備、請假、待派"},
            "force_completed": {"type": "boolean", "description": "強制查已完成表"}
        }
    }
)

# 2. 乘客請假
passenger_leave = FunctionDeclaration(
    name="passenger_leave",
    description="""
    處理乘客請假。使用三層障眼法：狀態保持「準備」，記錄請假原因。

    使用場景：
    - "明天公園南路的病患請假"
    - "班次 658 乘客請假，出國"
    - "今天5386診所的客人不來了"
    """,
    parameters={
        "type": "object",
        "properties": {
            "trip_id": {"type": "integer", "description": "班次編號（優先）"},
            "date": {"type": "string", "description": "日期"},
            "location": {"type": "string", "description": "地點"},
            "driver_id": {"type": "integer", "description": "司機編號"},
            "reason": {"type": "string", "description": "請假原因"},
            "allowance": {"type": "integer", "description": "加成調整（通常負數）", "default": 0}
        }
    }
)

# 3. 車資記錄/修改
fare_update = FunctionDeclaration(
    name="fare_update",
    description="""
    記錄或修改已完成班次的車資。

    使用場景：
    - "班次 4996 車資 90"
    - "把 4914 的車資改成 500"
    - "#2014 錶價 280 加成 -50"
    """,
    parameters={
        "type": "object",
        "properties": {
            "trip_id": {"type": "integer", "description": "班次編號"},
            "meter_fare": {"type": "integer", "description": "錶價"},
            "extra_fare": {"type": "integer", "description": "加成"},
            "reason": {"type": "string", "description": "修改原因"}
        },
        "required": ["trip_id"]
    }
)

# 4. 金額統計
fare_statistics = FunctionDeclaration(
    name="fare_statistics",
    description="""
    統計已完成班次的金額。

    使用場景：
    - "昨天5386診所金額"
    - "本週東洋統計"
    - "12/1-12/6 金額加總"
    """,
    parameters={
        "type": "object",
        "properties": {
            "date": {"type": "string"},
            "date_range": {"type": "string"},
            "driver_id": {"type": "integer"},
            "category": {"type": "string"}
        }
    }
)
```

### 3.2 P1：班次管理

```python
# 5. 指派司機
assign_driver = FunctionDeclaration(
    name="assign_driver",
    description="為班次指派司機",
    parameters={
        "type": "object",
        "properties": {
            "trip_id": {"type": "integer"},
            "driver_id": {"type": "integer"},
            "date": {"type": "string", "description": "用於批次指派"},
            "category": {"type": "string"}
        }
    }
)

# 6. 匯入固定班次
import_fixed_schedules = FunctionDeclaration(
    name="import_fixed_schedules",
    description="匯入固定班次到生產線",
    parameters={
        "type": "object",
        "properties": {
            "week": {"type": "string", "description": "本週、下週、W3"},
            "overwrite": {"type": "boolean", "description": "是否覆蓋"}
        }
    }
)

# 7. 修改班次狀態
update_trip_status = FunctionDeclaration(
    name="update_trip_status",
    description="修改班次狀態",
    parameters={
        "type": "object",
        "properties": {
            "trip_id": {"type": "integer"},
            "status": {"type": "string", "description": "準備、待派、註銷、衝突"}
        },
        "required": ["trip_id", "status"]
    }
)
```

### 3.3 上下文增強

```python
# 支援 "那一班"、"第三班" 的實體連結
# 在 prompt 中加入最近操作的班次信息

Context Example:
"""
Recent Context:
- Last query returned 5 trips: #1666, #1583, #1659, #1663, #1585
- Last modified trip: #1659
- User is in conversation about 1/15 診所班次

Entity Linking Rules:
- "那一班" → #1659 (last modified)
- "第三班" → #1659 (3rd in list)
- "5386的那班" → filter by driver then match
"""
```

---

## 四、遷移路徑

### Phase 1：擴展沙盒功能（2-3 週）

**目標**：讓沙盒能處理所有查詢和常用操作

| 任務 | 優先級 | 預估工作量 |
|-----|--------|-----------|
| 實現 `trip_query` | P0 | 2 天 |
| 整合三時間態判斷邏輯 | P0 | 1 天 |
| 實現 `passenger_leave` | P0 | 1 天 |
| 實現 `fare_update` | P0 | 1 天 |
| 實現 `fare_statistics` | P1 | 1 天 |
| 加入分頁支援 | P1 | 1 天 |
| 強化上下文記憶 | P1 | 2 天 |

### Phase 2：雙軌並行測試（2 週）

**目標**：沙盒和主系統並行，驗證穩定性

```python
# 在 webhook.py 中加入 A/B 測試
if user_id in SANDBOX_BETA_USERS:
    # 所有消息都走沙盒
    handle_customers_ai_message(event)
else:
    # 繼續使用主系統
    process_text_message(event)
```

| 任務 | 說明 |
|-----|------|
| 建立 Beta 用戶群組 | 內部測試 |
| 監控錯誤率 | 對比兩套系統 |
| 收集用戶反饋 | 自然語言理解準確度 |
| 調整 prompt | 根據錯誤案例優化 |

### Phase 3：逐步切換（2 週）

**目標**：沙盒成為預設，主系統成為備用

```python
# 新的路由邏輯
def route_message(event):
    try:
        # 預設走沙盒
        result = handle_sandbox_message(event)
        if result.get('fallback_to_legacy'):
            # 沙盒無法處理時降級
            return handle_legacy_message(event)
        return result
    except Exception as e:
        # 錯誤時降級
        logger.error(f"Sandbox error: {e}")
        return handle_legacy_message(event)
```

| 任務 | 說明 |
|-----|------|
| 修改預設路由 | 沙盒優先 |
| 保留傳統命令 | `查已完成`、`記錄車資` 等仍可用 |
| 監控降級率 | 目標 < 5% |

### Phase 4：清理與優化（持續）

**目標**：移除冗餘代碼，優化架構

| 任務 | 說明 |
|-----|------|
| 移除 smart_assistant.py 中的命令生成邏輯 | 不再需要「翻譯」成命令 |
| 精簡 text_message_handler.py | 只保留特殊命令和降級邏輯 |
| 統一 Function Calling 定義 | `gemini_functions.py` 和 `customers_ai_service.py` 合併 |
| 更新 CLAUDE.md | 反映新架構 |

---

## 五、成功指標

| 指標 | 目標 | 衡量方式 |
|-----|------|----------|
| 自然語言理解準確率 | > 95% | 抽樣測試 |
| 查詢回應時間 | < 3 秒 | 監控 |
| 降級率 | < 5% | 日誌統計 |
| 用戶滿意度 | 減少「格式錯誤」抱怨 | 用戶反饋 |
| 代碼行數 | 減少 30% | 程式碼統計 |

---

## 六、風險與緩解

| 風險 | 影響 | 緩解措施 |
|-----|------|----------|
| Gemini API 不穩定 | 功能不可用 | 保留傳統命令作為降級 |
| Function Calling 解析錯誤 | 操作錯誤 | 危險操作必須確認 |
| 上下文記憶錯亂 | 操作錯誤的班次 | 確認時顯示完整信息 |
| 遷移期間功能衝突 | 用戶困惑 | 漸進式切換，保留舊命令 |

---

## 七、下一步行動

1. **立即**：在沙盒中實現 `trip_query` 函數
2. **本週**：完成 P0 功能（查詢、請假、車資）
3. **下週**：開始內部 Beta 測試
4. **持續**：根據反饋調整 prompt 和邏輯
