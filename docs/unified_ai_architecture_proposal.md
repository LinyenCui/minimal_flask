# 三時間態統一 AI 架構重構提案

> **文件日期**：2026-01-22
> **目標**：將三個時間態的資料庫操作統一為「自然語言 → AI 理解 → 執行操作」模式

---

## 一、現況問題分析

### 1.1 查詢系統入口過多（7 個！）

目前查詢功能分散在多個模組中，導致維護困難且行為不一致：

| 入口 | 位置 | 職責 |
|-----|------|------|
| `text_message_handler.py` | 主路由 | 直接處理部分查詢 |
| `handlers/query_router.py` | 處理器 | 分發查詢 |
| `core/query_router.py` | 核心 | 另一個路由器（重複！） |
| `date_range_query_service.py` | 服務 | 日期範圍查詢 |
| `trip_query_service.py` | 服務 | 班次查詢 |
| `advanced_query_processor.py` | 服務 | 進階查詢 |
| `smart_assistant.py` | AI | AI 驅動查詢 |

**問題**：同一個查詢可能走不同路徑，結果不一致。

### 1.2 修改功能分散

修改操作散落在各處，沒有統一的確認機制：

| 時間態 | 修改功能 | 位置 | 確認機制 |
|-------|---------|------|----------|
| 未來態 | 固定班次請假 | `fc_leave_handler.py` | 無 |
| 現在態 | 班次狀態修改 | `trip_status_handler.py` | 部分有 |
| 現在態 | 車資修改 | `ai_fare_service.py` | 有（對話確認） |
| 過去態 | 完成班次車資 | `completed_trip_handler.py` | 無 |
| 沙盒 | trips 修改 | `customers_ai_service.py` | ✅ 完整確認流程 |

### 1.3 「聽不懂就全輸出」問題

當前系統在 AI 無法精確理解用戶意圖時的行為：

```
用戶：「班次」
系統：[輸出所有今日班次，可能上百條]

期望行為：
系統：「請問您想查詢哪一天的班次？今天、明天，還是特定日期？」
```

### 1.4 三時間態干擾問題

沙盒的 `trips` 操作與主系統的查詢/修改功能共用同一張表，可能造成：
- 沙盒修改影響主系統查詢結果
- 狀態管理混亂（PENDING_OPERATIONS vs 對話上下文）
- 確認流程衝突

---

## 二、目標架構設計

### 2.1 核心理念

```
┌─────────────────────────────────────────────────────────────┐
│                    用戶自然語言輸入                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   統一 AI 意圖理解層                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  查詢意圖   │  │  修改意圖   │  │  追問/澄清  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   時間態路由決策層                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   未來態    │  │   現在態    │  │   過去態    │         │
│  │fixed_schedules│ │   trips    │  │completed_trips│        │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   統一確認執行層                              │
│  草稿生成 → 用戶預覽 → 確認/取消 → 執行/放棄               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 「追問優先」原則

**新規則**：當 AI 無法確定以下任一項時，必須追問而非猜測：

| 類別 | 必須確認項目 | 追問範例 |
|-----|-------------|---------|
| 查詢 | 日期範圍 | 「請問您想查詢哪一天的班次？」 |
| 查詢 | 目標對象（司機/乘客） | 「請問您想查詢哪位司機的班次？」 |
| 修改 | 操作類型 | 「請問您想修改車資還是班次狀態？」 |
| 修改 | 目標班次 | 「請問您想修改哪一班？請提供班次編號。」 |
| 修改 | 新值 | 「請問錶價要改成多少？」 |

### 2.3 三時間態 Function Calling 定義

統一使用 Gemini Function Calling，每個時間態定義專屬工具：

```python
UNIFIED_TOOLS = [
    # ========== 查詢工具 ==========
    {
        "name": "query_future_schedules",
        "description": "查詢固定班次模板（未來態）",
        "parameters": {
            "customer_name": {"type": "string", "description": "客戶名稱"},
            "day_of_week": {"type": "string", "description": "星期幾"},
            "driver_id": {"type": "string", "description": "司機編號"}
        }
    },
    {
        "name": "query_current_trips",
        "description": "查詢現在態班次（含今天及未來已匯入）",
        "parameters": {
            "date": {"type": "string", "description": "日期，必填"},
            "driver_id": {"type": "string", "description": "司機編號"},
            "category": {"type": "string", "description": "類別：診所/東洋"}
        }
    },
    {
        "name": "query_completed_trips",
        "description": "查詢過去態班次（已完成）",
        "parameters": {
            "date_start": {"type": "string", "description": "起始日期，必填"},
            "date_end": {"type": "string", "description": "結束日期"},
            "driver_id": {"type": "string", "description": "司機編號"}
        }
    },

    # ========== 修改工具 ==========
    {
        "name": "update_fixed_schedule",
        "description": "修改固定班次模板",
        "parameters": {
            "schedule_id": {"type": "integer", "description": "固定班次ID，必填"},
            "field": {"type": "string", "description": "要修改的欄位"},
            "new_value": {"type": "string", "description": "新值"}
        }
    },
    {
        "name": "update_trip",
        "description": "修改現在態班次",
        "parameters": {
            "trip_id": {"type": "integer", "description": "班次ID，必填"},
            "meter_fare": {"type": "number", "description": "錶價"},
            "allowance": {"type": "number", "description": "加成"},
            "status": {"type": "string", "description": "狀態"},
            "driver_id": {"type": "string", "description": "司機編號"}
        }
    },
    {
        "name": "update_completed_trip",
        "description": "修改過去態班次",
        "parameters": {
            "completed_trip_id": {"type": "integer", "description": "已完成班次ID，必填"},
            "meter_fare": {"type": "number", "description": "錶價"},
            "allowance": {"type": "number", "description": "加成"}
        }
    },

    # ========== 追問工具 ==========
    {
        "name": "clarify_intent",
        "description": "當無法確定用戶意圖時，生成追問問題",
        "parameters": {
            "missing_info": {"type": "array", "description": "缺失的資訊列表"},
            "clarification_question": {"type": "string", "description": "追問問題"}
        }
    }
]
```

---

## 三、實施方案

### 3.1 第一階段：統一查詢入口

**目標**：將 7 個查詢入口收斂為 1 個

**步驟**：

1. 創建 `modules/core/unified_query_service.py`
   - 整合 `date_range_query_service.py` 邏輯
   - 整合 `trip_query_service.py` 邏輯
   - 整合 `advanced_query_processor.py` 邏輯

2. 修改 `text_message_handler.py`
   - 移除直接查詢邏輯
   - 所有查詢路由到統一服務

3. 刪除冗餘模組
   - `handlers/query_router.py`（與 `core/query_router.py` 重複）

**預期結果**：
```
用戶輸入 → text_message_handler → unified_query_service → 結果
```

### 3.2 第二階段：統一修改入口

**目標**：所有修改操作走相同確認流程

**步驟**：

1. 創建 `modules/core/unified_mutation_service.py`
   - 抽取沙盒的確認機制（`PENDING_OPERATIONS`）
   - 統一 Draft → Confirm → Execute 流程

2. 定義統一狀態機
   ```python
   class MutationState:
       IDLE = "idle"           # 無操作
       DRAFTING = "drafting"   # AI 草稿中
       PENDING = "pending"     # 等待確認
       EXECUTING = "executing" # 執行中
   ```

3. 遷移現有修改功能
   - `trip_status_handler.py` → 使用統一服務
   - `ai_fare_service.py` → 使用統一服務
   - `fc_leave_handler.py` → 使用統一服務

### 3.3 第三階段：實現追問機制

**目標**：AI 聽不懂時追問，而非盲目輸出

**步驟**：

1. 修改 AI System Prompt
   ```
   當用戶輸入缺少以下必要資訊時，你必須使用 clarify_intent 工具追問：
   - 查詢：缺少日期範圍
   - 修改：缺少目標 ID 或新值
   絕對不要猜測或使用預設值。
   ```

2. 實現追問對話管理
   ```python
   class ClarificationContext:
       user_id: str
       original_intent: str
       missing_fields: List[str]
       collected_answers: Dict[str, Any]
       expires_at: datetime
   ```

3. 追問回應處理
   - 用戶回應後，補充缺失資訊
   - 資訊完整後，執行原意圖

### 3.4 第四階段：時間態隔離

**目標**：防止不同時間態操作互相干擾

**方案**：

1. **命名空間隔離**
   ```python
   # 每個時間態使用獨立的狀態 key
   FUTURE_STATE_KEY = "future_{user_id}"
   PRESENT_STATE_KEY = "present_{user_id}"
   PAST_STATE_KEY = "past_{user_id}"
   ```

2. **操作鎖定機制**
   ```python
   # 同一用戶同一時間只能有一個活躍的修改操作
   if has_active_mutation(user_id):
       return "您有一個進行中的操作，請先完成或取消"
   ```

3. **明確的時間態指示**
   - 查詢結果明確標示來源表
   - 修改確認時顯示目標時間態

---

## 四、檔案結構調整

### 4.1 新增檔案

```
modules/
├── core/
│   ├── unified_query_service.py     # 統一查詢服務
│   ├── unified_mutation_service.py  # 統一修改服務
│   ├── clarification_manager.py     # 追問對話管理
│   ├── time_state_router.py         # 時間態路由
│   └── gemini_tools_v2.py           # 新版 Function Calling 定義
```

### 4.2 待刪除/整併檔案

```
# 整併到 unified_query_service.py
- handlers/query_router.py           # 刪除（與 core 重複）
- services/trip_query_service.py     # 整併
- services/advanced_query_processor.py # 整併

# 整併到 unified_mutation_service.py
- services/ai_fare_service.py        # 整併（部分）
```

---

## 五、遷移風險與對策

### 5.1 風險評估

| 風險 | 等級 | 對策 |
|-----|------|------|
| 現有功能中斷 | 高 | 保留舊路徑，新舊並行 |
| AI 追問過度 | 中 | 設定合理的追問閾值 |
| 性能下降 | 低 | 統一入口反而減少重複查詢 |
| 用戶學習成本 | 低 | 行為更一致，易於理解 |

### 5.2 漸進式遷移策略

```
第 1 週：統一查詢入口（不改變現有行為）
第 2 週：統一修改入口（沙盒模式）
第 3 週：啟用追問機制（可配置開關）
第 4 週：時間態隔離（全面啟用）
```

### 5.3 回滾機制

```python
# 功能開關配置
FEATURE_FLAGS = {
    "use_unified_query": True,      # 統一查詢
    "use_unified_mutation": True,   # 統一修改
    "enable_clarification": True,   # 追問機制
    "strict_time_state": True,      # 嚴格時間態隔離
}
```

---

## 六、驗收標準

### 6.1 查詢功能

- [ ] 「班次」（無日期）→ 追問日期，而非輸出全部
- [ ] 「今天班次」→ 精確查詢今日 trips
- [ ] 「昨天班次」→ 精確查詢 completed_trips
- [ ] 「下週一班次」→ 精確查詢 trips（未來已匯入）

### 6.2 修改功能

- [ ] 所有修改操作都經過「草稿 → 確認 → 執行」流程
- [ ] 確認訊息清楚顯示修改內容和目標時間態
- [ ] 「取消」能正確放棄操作
- [ ] 「確認」能正確執行並回報結果

### 6.3 追問機制

- [ ] 缺少日期 → 追問日期
- [ ] 缺少目標 ID → 追問 ID
- [ ] 缺少修改值 → 追問值
- [ ] 追問後用戶回應能正確補充資訊

### 6.4 時間態隔離

- [ ] 過去態修改不影響現在態查詢
- [ ] 現在態修改有獨立的確認流程
- [ ] 未來態修改（固定班次）有獨立的確認流程

---

## 七、總結

本提案的核心是將分散的查詢和修改功能統一到 AI 驅動的架構下，實現：

1. **一個入口**：所有自然語言輸入走統一的 AI 理解層
2. **追問優先**：聽不懂就問，而非盲目輸出
3. **確認機制**：所有修改操作都需用戶確認
4. **時間態隔離**：三個時間態操作互不干擾

這樣的架構將大幅提升用戶體驗，同時降低維護成本。

---

## 附錄：參考沙盒實現

`customers_ai_service.py` 中的關鍵模式：

```python
# 確認流程
PENDING_OPERATIONS = {}

def _confirm_pending_operation(user_id):
    if user_id in PENDING_OPERATIONS:
        op = PENDING_OPERATIONS.pop(user_id)
        return op['execute_fn']()  # 執行預存的操作
    return None

def _cancel_pending_operation(user_id):
    if user_id in PENDING_OPERATIONS:
        PENDING_OPERATIONS.pop(user_id)
        return "操作已取消"
    return None

# 工具執行
def _tool_trip_update(kwargs):
    trip_id = kwargs.get('trip_id')
    updates = {}
    if kwargs.get('meter_fare'):
        updates['meter_fare'] = kwargs.get('meter_fare')  # 直接使用欄位名
    # ... 構建 SQL 並執行
```

這個模式應該推廣到所有三個時間態的操作中。
