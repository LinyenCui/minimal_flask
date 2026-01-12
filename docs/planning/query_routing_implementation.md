# 查詢路由重構實作報告

**實作日期**: 2026-01-06
**目標**: 統一查詢路徑，消除重複實現，所有查詢走 `date_range_query_service`

## 🎯 核心目標達成

### ✅ 已完成項目

1. **查詢路由決策器** (`modules/core/query_router.py`)
   - 純決策模組，不執行查詢
   - 返回結構化路由決策 (table, mode, handler, parsed params)
   - 支援日期解析（含跨年邏輯）
   - 支援聚合關鍵字檢測

2. **查詢路徑追蹤工具** (`tools/trace_query_routes.py`)
   - 測試 18 種查詢場景
   - 驗證關鍵測試用例
   - 所有測試通過 ✅

3. **聚合查詢支援** (`modules/services/date_range_query_service.py`)
   - 新增 `query_completed_trips_aggregation()` - SQL 級別聚合
   - 新增 `format_aggregation_summary()` - 統計摘要格式化
   - 修改 `handle_query_trips_range()` 支援 mode 參數

## 📋 路由決策規則

### 時間態判斷（以 today = 2026-01-05 為例）

| 日期條件 | 表 | 原因 |
|---------|---|------|
| end_date < today (如 12/28) | `completed_trips` | 全過去 |
| start_date = today，無「已完成」| `trips` | 今天生產線 |
| start_date = today，有「已完成」| `completed_trips` | 今天已完成 |
| start_date > today (如 1/10) | `trips` | 全未來 |

### 模式判斷

| 關鍵字 | 模式 | 行為 |
|-------|-----|------|
| 金額加總、加總、合計、總額、總和、總計、統計金額、統計 | `aggregate` | 只返回統計摘要 |
| 其他 | `list` | 返回班次列表 |

## 🔍 測試結果

```bash
$ python3 tools/trace_query_routes.py

✅ PASS | 12/28-1/3司機61553診所班次金額加總
       预期: date_range_query_service/aggregate/completed_trips
       实际: date_range_query_service/aggregate/completed_trips

✅ PASS | 12/28-1/3司機61553診所班次
       预期: date_range_query_service/list/completed_trips
       实际: date_range_query_service/list/completed_trips

✅ PASS | 12/28-1/3診所班次金額加總
       预期: date_range_query_service/aggregate/completed_trips
       实际: date_range_query_service/aggregate/completed_trips

✅ 所有关键测试通过
```

## 🔧 日期解析邏輯

### 跨年邏輯（已修復）

```python
# 當前日期: 2026-01-05

# 案例 1: 12/28-1/3
# 解析為: 2025-12-28 至 2026-01-03 ✅
# 邏輯: 當前月份 ≤ 3 且開始月份 ≥ 10 → 開始年份 = 去年
#      開始月份 > 結束月份 → 結束年份 = 開始年份 + 1

# 案例 2: 12/20-12/25
# 解析為: 2025-12-20 至 2025-12-25 ✅
# 邏輯: 當前月份 ≤ 3 且開始月份 ≥ 10 且結束月份 ≥ 10 → 兩者都是去年

# 案例 3: 1/10
# 解析為: 2026-01-10 ✅
# 邏輯: 當前年份
```

## 🚀 整合指南

### 1. 在 Handler 中使用路由決策器

```python
from modules.core.query_router import decide_query_route
from modules.services.date_range_query_service import handle_query_trips_range

def handle_user_query(message_text, user_id):
    # 步驟 1: 使用路由決策器
    route = decide_query_route(message_text)

    # 步驟 2: 檢查是否為直接查詢
    if not route.is_direct_query:
        # 無日期，走智能助手
        return handle_smart_assistant(message_text, user_id)

    # 步驟 3: 執行查詢
    result = handle_query_trips_range(
        start_date=route.parsed['start_date'],
        end_date=route.parsed['end_date'],
        driver_id=route.parsed.get('driver_id'),
        category=route.parsed.get('category'),
        location=route.parsed.get('location'),
        user_id=user_id,
        force_completed=route.parsed.get('has_completed_keyword', False),
        mode=route.mode  # "list" 或 "aggregate"
    )

    return result
```

### 2. 聚合查詢特性

**重要**: 聚合查詢與列表查詢的差異

| 特性 | 列表查詢 (mode="list") | 聚合查詢 (mode="aggregate") |
|-----|---------------------|--------------------------|
| 返回內容 | 班次列表 | 統計摘要 |
| 分頁支援 | ✅ 支援 | ❌ 不支援 |
| 保存上下文 | ✅ 保存 | ❌ 不保存 |
| SQL 查詢 | SELECT * | SELECT COUNT, SUM |
| 適用表 | trips 或 completed_trips | 只查 completed_trips |

### 3. 聚合查詢範例

**輸入**: `12/28-1/3司機61553診所班次金額加總`

**路由決策**:
```python
QueryRoute(
    is_direct_query=True,
    table="completed_trips",
    mode="aggregate",
    handler="date_range_query_service",
    parsed={
        'start_date': date(2025, 12, 28),
        'end_date': date(2026, 1, 3),
        'driver_id': 61553,
        'category': '診所'
    },
    reason="日期查询: completed_trips, aggregate"
)
```

**SQL 執行**:
```sql
SELECT
    COUNT(*) as total_count,
    COUNT(CASE WHEN meter_fare IS NOT NULL OR extra_fare IS NOT NULL THEN 1 END) as filled_count,
    COUNT(CASE WHEN meter_fare IS NULL AND extra_fare IS NULL THEN 1 END) as unfilled_count,
    SUM(CASE
        WHEN meter_fare IS NULL AND extra_fare IS NULL THEN 0
        WHEN meter_fare IS NULL THEN extra_fare
        WHEN extra_fare IS NULL THEN meter_fare
        ELSE meter_fare + extra_fare
    END) as sum_amount
FROM completed_trips
WHERE date >= '2025-12-28'
  AND date <= '2026-01-03'
  AND driver_id = 61553
  AND category = '診所'
```

**輸出格式**:
```
📊 金額統計摘要
==============================

📅 統計範圍：2025-12-28 至 2026-01-03
🔍 篩選條件：司機61553 診所班次

📈 統計結果：
  • 總班次數：15 筆
  • 已填金額：12 筆
  • 未填金額：3 筆

💰 總金額：$4,250

⚠️ 提醒：有 3 筆班次尚未填寫金額
```

## 📝 關鍵設計原則

### 1. 單一路徑原則

- ✅ 所有查詢（列表、聚合）都走 `date_range_query_service`
- ❌ 不使用 `advanced_query_processor`（本次任務明確要求）
- ❌ 聚合查詢不走 `smart_assistant`

### 2. 聚合查詢不保存上下文

```python
# ✅ 正確：聚合查詢直接返回
if mode == "aggregate":
    agg_result = query_completed_trips_aggregation(...)
    text = format_aggregation_summary(...)
    return {"text": text, "quick_reply": None, "meta": meta}
    # 注意：沒有調用 context.save_query_result()

# ❌ 錯誤：聚合查詢不應該保存上下文
if mode == "aggregate":
    context.save_query_result(...)  # 不要這樣做！
```

### 3. SQL 級別聚合

- ✅ 使用 SQL 的 COUNT、SUM 函數直接計算
- ❌ 不要先 SELECT * 再在 Python 中計算
- 優點：效能更好，記憶體佔用更低

## 🎯 下一步工作

### 待整合部分

1. **text_message_handler.py** 整合
   - 找到查詢處理入口
   - 替換為 `decide_query_route()` + `handle_query_trips_range()`
   - 確保 mode 參數正確傳遞

2. **移除舊路徑**（可選，建議謹慎）
   - 確認沒有其他模組依賴 `advanced_query_processor`
   - 逐步遷移，保持向後兼容

3. **日誌驗證**
   - 確認日誌中不會出現「直接查詢解析失敗，繼續走智能助手」
   - 所有聚合查詢都有 "📊 聚合查詢模式" 日誌

### 測試建議

```python
# 回歸測試用例
test_cases = [
    # 聚合查詢
    ("12/28-1/3司機61553診所班次金額加總", "應返回統計摘要，無分頁"),
    ("12/28-1/3診所班次金額加總", "應返回統計摘要，無分頁"),

    # 列表查詢
    ("12/28-1/3司機61553診所班次", "應返回班次列表，支援分頁"),
    ("12/28-1/3診所班次", "應返回班次列表，支援分頁"),

    # 邊界情況
    ("1/5診所班次", "今天，查 trips"),
    ("1/5已完成診所班次", "今天+已完成，查 completed_trips"),
]
```

## 🐛 已修復問題

1. **日期解析錯誤**（12/20-12/25 被解析為跨年）
   - 修復前: 2025-12-20 至 2026-12-25 ❌
   - 修復後: 2025-12-20 至 2025-12-25 ✅

2. **跨年範圍解析錯誤**（7/28-8/1 被縮短）
   - 修復前: 7/28-7/31 ❌
   - 修復後: 7/28-8/1 ✅

3. **ModuleNotFoundError**（trace 工具導入問題）
   - 修復前: 導入 modules 觸發 Flask 依賴 ❌
   - 修復後: 直接加載文件，避免依賴 ✅

## 📚 相關文件

- `modules/core/query_router.py` - 路由決策器
- `modules/services/date_range_query_service.py` - 統一查詢服務
- `tools/trace_query_routes.py` - 路由追蹤工具
- `CLAUDE.md` - 專案文檔（核心原則）

## ✅ 驗收標準

- [x] 所有查詢都走 `date_range_query_service`
- [x] 聚合查詢返回統計摘要（不是列表）
- [x] 聚合查詢不保存上下文（無分頁）
- [x] 日期解析支援跨年（12/28-1/3）
- [x] 日期解析支援同月過去（12/20-12/25）
- [x] 路由追蹤工具測試通過

---

**實作狀態**: ✅ 核心功能完成，待整合到 Handler
**測試狀態**: ✅ 所有關鍵測試通過
**下一步**: 整合到 `text_message_handler.py`
