# Intent Schema 設計草案 v0.2

> 設計原則：Intent 是一等公民，不是翻譯產物
>
> **v0.2 更新**：整合生產線思維的三時間態定義，新增 QueryPlan 自動分割機制

---

## 0. 核心洞察：生產線思維的三時間態

在設計 Intent Schema 之前，必須先理解系統的核心抽象——**生產線思維**：

### 三時間態定義（資料位置導向，非日期導向）

| 時間態 | 資料表 | 本質 | 判斷依據 |
|-------|-------|------|---------|
| 🏗️ **未來態** | `fixed_schedules` | 模板倉庫（尚未匯入） | 操作：匯入、模板、固定班次 |
| ⚡ **現在態** | `trips` | 生產線（已匯入，等待執行） | **不論今天/明天/後天，只要已匯入** |
| 📦 **過去態** | `completed_trips` | 成品倉庫（已完成） | 關鍵字：昨天、已完成、車資、金額 |

### 關鍵理解

```
"明天司機5386所有班次" → 查 trips（現在態）
原因：這些班次已經匯入到生產線上，不是「未來」

時間態的核心是「數據的狀態位置」，日期只是輔助條件。
```

### 現有系統的正確設計（被埋在服務層）

系統已有正確的混合範圍分割邏輯（`date_range_query_service.py:658-670`）：

```python
# 當查詢 12/1-12/19（今天是 12/14）
if start_date < today <= end_date:
    # 自動分割：
    # 1) 12/1-12/13 → completed_trips（過去態）
    # 2) 12/14-12/19 → trips（現在態）
    # 3) 合併輸出
```

**問題**：這個智能邏輯被埋在服務層，依賴 AI 生成正確命令才能觸發。

**Intent Schema 的價值**：把這個智能邏輯提升到 Intent 層，成為系統的一等公民。

---

## 1. 設計哲學

### 為什麼需要 Intent Schema？

當前系統的問題：
```
AI 輸出: "查已完成 8/1 司機5386 診所"  ← 這是「給人看的命令」
系統理解: Regex 匹配 → 提取參數 → 執行      ← 這是「二次解析」
```

Intent Schema 的目標：
```
AI 輸出: { "action": "query", "date_range": [...], "filters": {...} }  ← 結構化意圖
系統執行: Intent 層計算 QueryPlan → Executor 直接執行                    ← 智能分割
```

### 核心原則

1. **Intent 是合約**：AI 和 Executor 之間的唯一通訊協議
2. **Intent 是不可變的**：一旦生成，不應被修改
3. **Intent 是可追蹤的**：每個 Intent 有唯一 ID，可追溯完整生命週期
4. **Intent 是可組合的**：複雜操作可由多個 Intent 組合完成
5. **Intent 層負責時間態路由**：AI 只提取參數，不決定查哪個表（v0.2 新增）

---

## 2. Intent 基礎結構

```typescript
interface Intent {
  // === 身份識別 ===
  id: string;              // 唯一識別符，格式: "int_" + nanoid(12)
  version: "1.0";          // Schema 版本，用於向後兼容

  // === 核心語意 ===
  action: Action;          // 動作類型（見下方枚舉）
  target: Target;          // 目標實體
  params: Params;          // 動作參數

  // === 上下文 ===
  context: {
    user_id: string;
    session_id: string;
    timestamp: ISO8601;
    source: "natural_language" | "button" | "quick_reply" | "command";
    raw_input: string;     // 原始用戶輸入
  };

  // === AI 判斷 ===
  confidence: number;      // 0.0 - 1.0
  reasoning?: string;      // AI 的推理過程（debug 用）
  alternatives?: Intent[]; // 其他可能的解讀（用於澄清）

  // === 狀態機 ===
  status: IntentStatus;
  requires_confirmation: boolean;
  parent_intent_id?: string;  // 如果是子意圖
}

type IntentStatus =
  | "pending"      // 等待執行
  | "confirming"   // 等待用戶確認
  | "executing"    // 執行中
  | "completed"    // 已完成
  | "failed"       // 執行失敗
  | "cancelled"    // 用戶取消
  | "clarifying";  // 需要澄清
```

---

## 3. Action 動作類型

### 3.1 查詢類動作（只讀，最安全）

```typescript
type QueryAction =
  | "query_trips"           // 查詢現在態班次
  | "query_completed"       // 查詢過去態班次
  | "query_fixed"           // 查詢未來態模板
  | "query_driver"          // 查詢司機資訊
  | "query_customer"        // 查詢客戶資訊
  | "aggregate_fare"        // 統計金額
  | "get_trip_detail";      // 單一班次詳情
```

### 3.2 修改類動作（需確認）

```typescript
type MutationAction =
  | "set_leave"             // 設定請假
  | "cancel_leave"          // 取消請假（恢復準備）
  | "set_status"            // 修改狀態
  | "update_fare"           // 修改車資
  | "assign_driver"         // 指派司機
  | "update_trip";          // 修改班次資訊
```

### 3.3 創建類動作（需確認）

```typescript
type CreateAction =
  | "create_booking"        // 創建預約
  | "import_schedule"       // 匯入固定班次
  | "create_trip";          // 創建臨時班次
```

### 3.4 系統類動作

```typescript
type SystemAction =
  | "generate_report"       // 生成報表
  | "sync_database"         // 同步資料庫
  | "show_help";            // 顯示幫助
```

### 3.5 對話控制動作

```typescript
type DialogAction =
  | "confirm"               // 確認操作
  | "cancel"                // 取消操作
  | "clarify"               // 需要澄清
  | "select_option";        // 從多選項中選擇
```

---

## 4. Target 目標實體

```typescript
interface Target {
  entity: EntityType;
  temporal_state: TemporalState;
  identifiers?: Identifiers;
}

type EntityType =
  | "trip"           // 班次
  | "driver"         // 司機
  | "customer"       // 客戶
  | "schedule"       // 固定班次模板
  | "report";        // 報表

type TemporalState =
  | "past"           // 過去態 → completed_trips
  | "present"        // 現在態 → trips
  | "future"         // 未來態 → fixed_schedules
  | "auto";          // 由日期自動判斷

interface Identifiers {
  trip_id?: number;
  trip_ids?: number[];
  driver_id?: number;
  customer_id?: number;
  unique_code?: string;
}
```

---

## 5. Params 參數定義

### 5.1 日期參數（最複雜的部分）

```typescript
interface DateParams {
  // 單一日期
  date?: {
    type: "absolute" | "relative";
    value: string;           // "2025-12-14" 或 "today", "yesterday", "tomorrow"
    resolved: ISO8601Date;   // AI 解析後的標準日期
  };

  // 日期範圍
  date_range?: {
    start: ISO8601Date;
    end: ISO8601Date;
    original_input: string;  // 保留原始輸入 "7/28-8/1"
  };
}
```

### 5.2 篩選參數

```typescript
interface FilterParams {
  driver_id?: number;
  category?: "診所" | "東洋" | "臨時" | string;
  status?: "待派" | "準備" | "註銷" | "衝突" | "請假";
  location?: {
    keyword: string;
    match_in: ("start_point" | "via_point" | "end_point")[];
  };
  fare_condition?: {
    field: "meter_fare" | "extra_fare" | "total";
    operator: ">" | "<" | "=" | ">=" | "<=";
    value: number;
  };
}
```

### 5.3 請假參數

```typescript
interface LeaveParams {
  reason: string;
  allowance?: number;        // 加成調整
  apply_to: "single" | "batch";
}
```

### 5.4 車資參數

```typescript
interface FareParams {
  mode: "set" | "adjust";    // 設定模式 vs 累加模式
  meter_fare?: number;
  extra_fare?: number;
  adjustment?: number;       // 累加模式的金額
  reason?: string;
}
```

### 5.5 預約參數

```typescript
interface BookingParams {
  datetime: ISO8601DateTime;
  pickup: {
    address: string;
    landmark?: string;
  };
  destination: {
    address: string;
    landmark?: string;
  };
  via?: string;
  passenger_name?: string;
  passenger_phone?: string;
  notes?: string;
}
```

---

## 6. 完整 Intent 範例

### 範例 1：簡單查詢

用戶輸入：`8/1 司機5386 診所班次`

```json
{
  "id": "int_7kd8fJ2mNx9p",
  "version": "1.0",
  "action": "query_completed",
  "target": {
    "entity": "trip",
    "temporal_state": "past"
  },
  "params": {
    "date": {
      "type": "absolute",
      "value": "8/1",
      "resolved": "2025-08-01"
    },
    "filter": {
      "driver_id": 5386,
      "category": "診所"
    }
  },
  "context": {
    "user_id": "U1234567890",
    "session_id": "sess_abc123",
    "timestamp": "2025-12-14T10:30:00+08:00",
    "source": "natural_language",
    "raw_input": "8/1 司機5386 診所班次"
  },
  "confidence": 0.95,
  "status": "pending",
  "requires_confirmation": false
}
```

### 範例 2：請假操作（需確認）

用戶輸入：`明天公園南路請假`

```json
{
  "id": "int_9mP2kL5nQr8s",
  "version": "1.0",
  "action": "set_leave",
  "target": {
    "entity": "trip",
    "temporal_state": "present"
  },
  "params": {
    "date": {
      "type": "relative",
      "value": "tomorrow",
      "resolved": "2025-12-15"
    },
    "filter": {
      "location": {
        "keyword": "公園南路",
        "match_in": ["start_point", "via_point", "end_point"]
      }
    },
    "leave": {
      "reason": "乘客請假",
      "allowance": 0,
      "apply_to": "single"
    }
  },
  "confidence": 0.85,
  "status": "confirming",
  "requires_confirmation": true,
  "reasoning": "用戶提到地點但未指定具體班次，需查詢後確認"
}
```

### 範例 3：需要澄清

用戶輸入：`明天久保田`

```json
{
  "id": "int_4xY7wZ1vBt6u",
  "version": "1.0",
  "action": "clarify",
  "target": {
    "entity": "trip",
    "temporal_state": "present"
  },
  "params": {
    "date": {
      "type": "relative",
      "value": "tomorrow",
      "resolved": "2025-12-15"
    },
    "filter": {
      "location": {
        "keyword": "久保田",
        "match_in": ["start_point", "via_point", "end_point"]
      }
    }
  },
  "confidence": 0.4,
  "status": "clarifying",
  "requires_confirmation": false,
  "alternatives": [
    {
      "action": "set_leave",
      "description": "設定請假"
    },
    {
      "action": "get_trip_detail",
      "description": "查看班次詳情"
    },
    {
      "action": "set_status",
      "params": { "status": "註銷" },
      "description": "註銷班次"
    }
  ],
  "reasoning": "用戶只提供日期和地點，意圖不明確"
}
```

### 範例 4：車資修改

用戶輸入：`修改#2014車資280加成-50`

```json
{
  "id": "int_6pQ9rS3tUv2w",
  "version": "1.0",
  "action": "update_fare",
  "target": {
    "entity": "trip",
    "temporal_state": "past",
    "identifiers": {
      "trip_id": 2014
    }
  },
  "params": {
    "fare": {
      "mode": "set",
      "meter_fare": 280,
      "extra_fare": -50,
      "reason": "車資調整"
    }
  },
  "confidence": 0.98,
  "status": "confirming",
  "requires_confirmation": true
}
```

---

## 7. 時間態自動判斷邏輯

這是系統最關鍵的邏輯，必須在 Intent 層統一處理：

```typescript
function resolveTemporalState(
  date: ResolvedDate,
  today: Date,
  hints: string[]  // 從用戶輸入提取的關鍵字
): TemporalState {

  // 規則 1：過去日期 → 過去態
  if (date < today) {
    return "past";
  }

  // 規則 2：未來日期 → 現在態（已匯入的未來班次在 trips 表）
  if (date > today) {
    return "present";
  }

  // 規則 3：今天日期 → 看關鍵字
  const pastHints = ["已完成", "金額", "收入", "車資", "統計"];
  if (hints.some(h => pastHints.includes(h))) {
    return "past";
  }

  return "present";
}
```

---

## 8. Intent 狀態機

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
                    ▼                                         │
┌─────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐ │
│ pending │───▶│confirming│───▶│ executing │───▶│completed │ │
└─────────┘    └──────────┘    └───────────┘    └──────────┘ │
     │              │                │                        │
     │              │                │          ┌──────────┐  │
     │              ▼                └─────────▶│  failed  │  │
     │         ┌──────────┐                     └──────────┘  │
     │         │cancelled │                                   │
     │         └──────────┘                                   │
     │                                                        │
     │         ┌───────────┐                                  │
     └────────▶│ clarifying│──────────────────────────────────┘
               └───────────┘
                    │
                    ▼
               用戶選擇後
               生成新 Intent
```

### 狀態轉換規則

| 當前狀態 | 觸發事件 | 下一狀態 |
|---------|---------|---------|
| pending | confidence >= 0.8 且 requires_confirmation = false | executing |
| pending | confidence >= 0.8 且 requires_confirmation = true | confirming |
| pending | confidence < 0.5 | clarifying |
| pending | 0.5 <= confidence < 0.8 | confirming |
| confirming | 用戶確認 | executing |
| confirming | 用戶取消 | cancelled |
| clarifying | 用戶選擇選項 | pending (新 Intent) |
| executing | 執行成功 | completed |
| executing | 執行失敗 | failed |

---

## 9. 需確認的操作矩陣

| Action | 單一目標 | 批量目標 | 涉及金額 |
|--------|---------|---------|---------|
| query_* | ❌ | ❌ | ❌ |
| get_trip_detail | ❌ | - | ❌ |
| set_leave | ✅ | ✅✅ | ✅✅ |
| cancel_leave | ✅ | ✅✅ | ❌ |
| set_status | ✅ | ✅✅ | ❌ |
| update_fare | ✅ | - | ✅✅ |
| assign_driver | ✅ | ✅ | ❌ |
| create_booking | ✅ | - | ❌ |
| import_schedule | ✅ | - | ❌ |
| generate_report | ❌ | - | ❌ |

- ❌ = 不需確認
- ✅ = 需要確認
- ✅✅ = 強制確認（顯示詳細摘要）

---

## 10. 錯誤處理 Schema

```typescript
interface IntentError {
  intent_id: string;
  error_type: ErrorType;
  message: string;
  recoverable: boolean;
  suggestions?: string[];
}

type ErrorType =
  | "INVALID_DATE"          // 日期格式錯誤
  | "ENTITY_NOT_FOUND"      // 找不到目標
  | "AMBIGUOUS_TARGET"      // 目標不明確
  | "PERMISSION_DENIED"     // 無權限
  | "BUSINESS_RULE_VIOLATION" // 違反業務規則
  | "DATABASE_ERROR"        // 資料庫錯誤
  | "AI_CONFIDENCE_LOW";    // AI 信心度過低
```

---

## 11. 與現有系統的整合路徑

### 階段 1：雙軌並行（推薦起點）

```
用戶輸入
    │
    ▼
┌─────────────┐
│   路由器     │
└─────────────┘
    │
    ├──────────────────────────────┐
    ▼                              ▼
┌─────────────┐              ┌─────────────┐
│ Intent 管道 │              │ Legacy 管道  │
│ (新系統)    │              │ (現有系統)   │
└─────────────┘              └─────────────┘
    │                              │
    │ 只處理查詢類                  │ 處理所有命令
    │                              │
    └──────────────┬───────────────┘
                   ▼
              統一回應
```

### 階段 2：Intent 優先

當 Intent 管道穩定後，逐步擴大覆蓋範圍：
- 查詢類 → 請假類 → 車資類 → 創建類

### 階段 3：Legacy 降級

Legacy 管道最終只處理：
- AI 失敗時的 fallback
- 專家用戶的精確命令
- 系統維護操作

---

## 12. 下一步行動

### 立即可做

1. **定義 Intent Schema 的 Python 實現**
   - 使用 Pydantic 或 dataclass
   - 添加驗證邏輯

2. **實現 Intent 路由器**
   - 判斷走 Intent 管道還是 Legacy 管道
   - 初期只路由查詢類

3. **修改 AI Prompt**
   - 輸出 JSON 而非文字命令
   - 使用 Function Calling 強制結構化

### 需要討論

1. **Intent ID 的生成策略**
   - nanoid？UUID？遞增 ID？

2. **Intent 持久化**
   - 是否需要存入資料庫？
   - 用於審計追蹤？

3. **多意圖處理**
   - 用戶輸入：「明天5386請假，然後查他這週的班次」
   - 拆分為兩個 Intent？還是 Intent 鏈？

---

## 附錄 A：與現有 IntentExecutor 的對比

| 項目 | 現有 IntentExecutor | 本設計 |
|-----|---------------------|--------|
| Action 類型 | 6 個 | 15+ 個，有明確分類 |
| 參數結構 | Dict[str, Any] | 強類型 Params |
| 時間態處理 | 分散在各處 | 統一的 Target.temporal_state |
| 狀態管理 | 無 | 完整狀態機 |
| 確認機制 | 硬編碼 | 聲明式規則 |
| 錯誤處理 | try/except | 結構化 IntentError |
| 可追蹤性 | 無 | Intent ID + 完整上下文 |

---

*草案版本：v0.1*
*日期：2025-12-14*
*狀態：待討論*
