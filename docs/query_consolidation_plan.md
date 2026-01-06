# 查詢功能整合計畫

> 建立日期：2026-01-06
> 狀態：Phase 1 完成，Phase 2 待執行

---

## Phase 1：已完成的修復 (2026-01-06)

### 1. 跨年日期解析修復
**檔案**：`modules/core/query_classifier.py`

**問題**：在 1 月份查詢 `12/28-1/3` 時，系統誤判為 `2026-12-28 ~ 2027-01-03`

**修復邏輯**：
```python
# 智能年份判斷（跨年邏輯）
# 1. 如果現在是1-3月，且開始月份是10-12月，說明是去年
if current_month <= 3 and start_month >= 10:
    start_year = year - 1
    if end_month >= 10:
        end_year = year - 1

# 2. 如果開始月份 > 結束月份，說明跨年
if start_month > end_month:
    end_year = start_year + 1
```

**修改位置**：
- `parse_direct_query()` 函數 (約 line 305-334)
- `determine_query_table()` 函數 (約 line 193-232)
- 單日日期解析區塊 (約 line 234-263, 351-370)

---

### 2. 聚合關鍵字誤判修復
**檔案**：`modules/core/query_classifier.py`

**問題**：`金額加總` 被 `_has_location_pattern()` 誤判為地點，導致查詢走錯路徑

**修復**：在 `_has_location_pattern()` 的排除清單中加入聚合關鍵字
```python
remove_patterns = [
    # ... 原有排除項 ...
    # 聚合關鍵字不算地點
    '金額加總', '加總', '合計', '總額', '總和', '總計', '統計金額', '統計',
]
```

---

### 3. 聚合模式路由
**檔案**：`modules/handlers/text_message_handler.py`

**新增邏輯**：檢測聚合關鍵字並路由到 `mode="aggregate"`
```python
aggregation_keywords = ['金額加總', '加總', '合計', '總額', '總和', '總計', '統計金額', '統計']
is_aggregation = any(kw in message_text for kw in aggregation_keywords)

if is_aggregation:
    result = handle_query_trips_range(
        ...,
        mode="aggregate"  # 關鍵：傳遞聚合模式
    )
```

---

### 4. 第一頁日期顯示修復
**檔案**：`modules/services/date_range_query_service.py`

**問題**：trips 表查詢結果（第一頁）不顯示日期，completed_trips（第二頁）正常

**修復**：在 `format_current_trips_range_result()` 中加入日期顯示
```python
# 原本
lines.append(f"#{item['id']} ⏰{t_str}-{item['start']}→{item['end']}|{d_str}")

# 修復後
date_str = item['date'].strftime('%m/%d') if item['date'] else ''
lines.append(f"#{item['id']} {date_str} ⏰{t_str}-{item['start']}→{item['end']}|{d_str}")
```

---

## Phase 2：查詢服務整合計畫（待執行）

### 目標
將分散的查詢邏輯統一為單一路徑，消除重複實現。

### 現況問題
目前有 5+ 個查詢相關服務，總計約 218KB：

| 檔案 | 大小 | 功能 | 處置 |
|------|------|------|------|
| `ai_fare_service.py` | 76KB | AI車資查詢 | 保留（AI專用） |
| `date_range_query_service.py` | 48KB | 日期範圍查詢 | **保留並擴展** |
| `advanced_query_processor.py` | 45KB | 複雜查詢處理 | **廢棄** |
| `trip_query_service.py` | 44KB | 班次查詢服務 | **廢棄** |
| `unified_trip_query_service.py` | 5KB | 統一查詢 | **廢棄** |

### 整合架構
```
用戶輸入
    ↓
┌─────────────────────────────────┐
│     query_router.py (已建立)     │  ← 統一入口
│  - 解析日期、司機、類別          │
│  - 決定 table (trips/completed) │
│  - 決定 mode (list/aggregate)   │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│   date_range_query_service.py   │  ← 統一執行層
│  - query_trips_range()          │
│  - query_completed_trips_range()│
│  - query_aggregation()          │
│  - format_result()              │
└─────────────────────────────────┘
```

### 整合步驟提示詞

```
請執行以下查詢服務整合：

1. 確認 query_router.py 已正確運作（使用 tools/trace_query_routes.py 測試）

2. 修改 text_message_handler.py：
   - 移除對 advanced_query_processor 的調用
   - 移除對 trip_query_service 的調用
   - 所有日期範圍查詢統一走 query_router + date_range_query_service

3. 將 advanced_query_processor.py 的必要功能合併到 date_range_query_service.py：
   - 地點篩選功能（如果需要）
   - 複雜條件組合

4. 測試所有查詢路徑：
   - 單日查詢：12/28診所班次
   - 範圍查詢：12/28-1/3診所班次
   - 聚合查詢：12/28-1/3診所班次金額加總
   - 司機篩選：12/28-1/3司機61553診所班次
   - 跨年查詢：確保日期解析正確

5. 確認無問題後，將以下檔案標記為廢棄（加入 DEPRECATED 註釋）：
   - advanced_query_processor.py
   - trip_query_service.py
   - unified_trip_query_service.py

注意事項：
- 不要在 SQL 字串中加入 Python 註釋（# 符號會導致語法錯誤）
- 保持 KISS 原則，不要過度工程化
- 每個修改都要驗證語法正確性
```

---

## 測試驗證

### Phase 1 測試命令
```bash
# 語法檢查
python3 -m py_compile modules/services/date_range_query_service.py
python3 -m py_compile modules/core/query_classifier.py

# 功能測試
python3 tools/test_aggregation.py
python3 tools/trace_query_routes.py "12/28-1/3司機61553診所班次金額加總"
```

### 預期結果
```
12/28-1/3司機61553診所班次金額加總
  ├─ 日期: 2025-12-28 ~ 2026-01-03  ✅ (跨年正確)
  ├─ 目標表: completed_trips         ✅
  ├─ 模式: aggregate                 ✅
  └─ 處理器: date_range_query_service ✅
```

---

## 相關檔案清單

### 已修改
- `modules/core/query_classifier.py`
- `modules/handlers/text_message_handler.py`
- `modules/services/date_range_query_service.py`

### 新增
- `modules/core/query_router.py`
- `tools/trace_query_routes.py`
- `tools/test_aggregation.py`
- `docs/integration_example.py`
- `docs/query_consolidation_plan.md`（本檔案）
