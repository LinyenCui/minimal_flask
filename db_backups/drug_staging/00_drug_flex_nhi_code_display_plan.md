# /drug Flex 顯示健保藥品代碼計畫

## 本階段目的

本報告只做唯讀分析與修改計畫，準備在 `/drug` 查詢與 Flex 圖卡中顯示 `drug_items.nhi_drug_code`。
本階段不修改程式、不寫資料庫、不執行 migration、不 git add/commit。

## 相關檔案

| 檔案 | 角色 |
|---|---|
| `modules/routes/webhook.py` | LINE webhook 文字訊息入口；在主 rewrite/router 之前先攔截 `/drug` / `!drug` 類查詢。 |
| `modules/handlers/drug_handler.py` | `/drug` 指令判斷、query extraction、呼叫 service、回覆文字 fallback 或 Flex。 |
| `modules/services/drug_query_service.py` | 查詢正式表 `drug_items`，組成每筆藥品 dict，並查 `drug_diagnosis_links` 關聯診斷碼。 |
| `modules/views/drug_flex.py` | 建立 read-only Flex bubble / carousel。 |

## /drug 指令入口

`modules/routes/webhook.py` 在文字訊息處理時，先呼叫：

- `modules.handlers.drug_handler.is_drug_trigger(original_message_text)`
- 命中後呼叫 `handle_drug_message(event)` 並 `continue`

目前 `/drug` 入口在 rewrite/router 與 sandbox_handler 之前處理，因此 `/drug`、`!drug` 可以先進藥名查詢，不會掉到主線派班/記帳路由。

`modules/handlers/drug_handler.py` 的 `PREFIXES` 目前包含：

- `藥名 ` / `藥名`
- `/藥名 ` / `/藥名`
- `/drug ` / `/drug`
- `drug ` / `drug`
- `藥 ` / `藥`
- `!drug`
- `！drug`

## drug_items 查詢流程

`DrugQueryService.search(query_text)` 流程：

1. 讀取 `drug_items` 實際欄位：`_get_drug_items_columns()`。
2. 從 `SEARCH_CANDIDATE_COLUMNS` 中選出可搜尋欄位。
3. `_query_rows(query, columns, search_columns)` 組 SELECT 欄位與查詢條件。
4. 查詢 `drug_items`，以 exact / prefix / fuzzy 條件排序，`LIMIT 11`。
5. 只回前 10 筆，逐筆呼叫 `_normalize_row(row)`。
6. `_normalize_row()` 會再查 `_get_related_diagnoses(drug_id)`，join `drug_diagnosis_links` + `diagnosis_codes`，每筆藥最多 5 個相關診斷碼。

目前 SELECT 欄位來源：

- `CORE_COLUMNS`
- `OPTIONAL_DISPLAY_COLUMNS`

目前 `CORE_COLUMNS`：

- `id`
- `seq_no`
- `table_type`
- `item_kind`
- `generic_name`
- `brand_name`
- `aliases`

目前 `OPTIONAL_DISPLAY_COLUMNS`：

- `normalized_name`
- `raw_name`
- `original_name`
- `source_name`
- `spec`
- `specification`
- `strength`
- `dosage`
- `dose`
- `unit`
- `category`
- `supplier`
- `manufacturer`
- `source`
- `source_photo`
- `source_version`

## Flex bubble / carousel 產生位置

`modules/handlers/drug_handler.py` 的 `_reply_result()`：

- 先產生文字 fallback：`_format_result(result)`。
- 若結果不是 list 或沒有 items，直接回文字。
- 若有 items，呼叫 `render_drug_results(items)`。
- Flex 發送失敗時回文字 fallback。

`modules/views/drug_flex.py`：

- `render_drug_results(items)`：一筆回單張 bubble，多筆回 carousel，最多 10 張。
- `render_drug_bubble(item)`：每個藥品一張 read-only bubble。

## 目前圖卡顯示欄位

目前 `render_drug_bubble(item)` 顯示：

1. Header
   - title：`brand_name` 優先，其次 `generic_name` / `raw_name` / `藥品 #id`
   - subtitle：`drug_items #id`
2. Body
   - `成分`：`generic_name`
   - `藥名`：`brand_name`，若與 generic 不同
   - `類型`：`table_type / item_kind`
   - `分類`：`category`
   - `供應商`：`supplier`
   - `製造商`：`manufacturer`
   - `相關診斷碼`：最多 5 筆 `related_diagnoses`

目前文字 fallback `_format_list()` 也沒有顯示健保碼。

## nhi_drug_code 是否已被查出

目前沒有。

理由：

- `drug_items` DB schema 已有 `nhi_drug_code`、`nhi_drug_code_source`、`nhi_drug_code_confidence`、`nhi_drug_code_verified_at`、`nhi_drug_code_note`。
- 本機 DB 目前 `drug_items` 共有 152 筆，其中 31 筆 `nhi_drug_code IS NOT NULL`。
- 但 `modules/services/drug_query_service.py` 的 `CORE_COLUMNS` / `OPTIONAL_DISPLAY_COLUMNS` 未包含 `nhi_drug_code`。
- `_normalize_row()` 也沒有把 `nhi_drug_code` 放進 item dict。
- `modules/views/drug_flex.py` 目前沒有讀取或顯示 `nhi_drug_code`。

因此 `/drug` 目前查得到藥品，但圖卡拿不到健保碼欄位。

## 建議修改點

### 1. Service 補查欄位

檔案：`modules/services/drug_query_service.py`

建議把以下欄位加入 SELECT 候選，位置可放在 `CORE_COLUMNS` 或 `OPTIONAL_DISPLAY_COLUMNS`：

- `nhi_drug_code`
- 可選：`nhi_drug_code_source`
- 可選：`nhi_drug_code_confidence`

最小需求只要 `nhi_drug_code`。

建議在 `_normalize_row()` 增加：

```python
'nhi_drug_code': row.get('nhi_drug_code'),
```

若未來需要 debug 或管理頁再顯示來源，可另外傳：

```python
'nhi_drug_code_source': row.get('nhi_drug_code_source'),
'nhi_drug_code_confidence': row.get('nhi_drug_code_confidence'),
```

但 v1 圖卡顯示只建議顯示主碼，不顯示 source/confidence，避免卡片太雜。

### 2. Flex 顯示健保碼

檔案：`modules/views/drug_flex.py`

建議在 `render_drug_bubble()` 中，`成分` / `藥名` 後方、`類型` separator 前加入：

```python
if item.get("nhi_drug_code"):
    body.append(_row("健保碼", _short(item["nhi_drug_code"], 32), value_color=PRIMARY, value_weight="bold"))
```

顯示格式：

- `健保碼：ACxxxx`

若 `nhi_drug_code` 為 NULL / 空字串，不顯示此列。

### 3. 文字 fallback 可同步顯示

檔案：`modules/handlers/drug_handler.py`

雖然使用者本輪重點是 Flex 圖卡，但建議同步在文字 fallback 的每個 item 加：

```python
if item.get('nhi_drug_code'):
    lines.append(f"   健保碼：{item['nhi_drug_code']}")
```

位置建議在成分/藥名後、類型前。

這樣 Flex 發送失敗時，文字 fallback 也能保留健保碼。

## 建議圖卡位置

建議位置：

1. `成分`
2. `藥名`
3. `健保碼`
4. separator
5. `類型` / `分類`
6. `供應商` / `製造商`
7. `相關診斷碼`

原因：健保碼是藥局識別主欄位，應放在主藥名資訊下方，不應埋在來源或備註區。

## NULL 顯示規則

- `nhi_drug_code` 有值：顯示 `健保碼：<code>`。
- `nhi_drug_code` 為 NULL 或空字串：不顯示健保碼列。
- 不建議顯示 `尚無健保碼`，避免圖卡噪音。

## 風險與注意事項

1. `nhi_drug_code` 目前只有 31 / 152 筆有值，很多藥品圖卡不會顯示健保碼，這是預期行為。
2. 不要把 `nhi_drug_code` 加入搜尋欄位，除非另行設計；本次只是顯示，避免改變 `/drug` 查詢行為。
3. 若要讓 `/drug AC58316100` 也能查到藥品，需要另開需求，把 `nhi_drug_code` 加入 `SEARCH_CANDIDATE_COLUMNS`，並測試健保碼查詢排序。
4. Flex bubble 是 `kilo` size，新增一列健保碼通常安全，但名稱很長的藥品仍需注意卡片高度。
5. 目前 `drug_items.nhi_drug_code` 是主碼；其他候選碼/歷史碼未來應放 `drug_item_official_code_mappings`，不要在 Flex 主卡一次顯示全部。

## 最小實作計畫

1. 修改 `modules/services/drug_query_service.py`
   - 將 `nhi_drug_code` 加入 SELECT 欄位。
   - 在 `_normalize_row()` 回傳 `nhi_drug_code`。

2. 修改 `modules/views/drug_flex.py`
   - 在藥名主資訊區顯示 `健保碼` row。
   - 僅在有值時顯示。

3. 可選修改 `modules/handlers/drug_handler.py`
   - 文字 fallback 同步顯示健保碼。

4. 測試案例
   - `/drug Rosuvastatin`：應看到有健保碼的藥品圖卡。
   - `/drug Metformin`：`Metformin 寬樂醣` 應顯示 `AC585341G0`。
   - `/drug Linagliptin`：應顯示 `BC25537100`。
   - `/drug 不存在XYZ`：維持文字查無資料。
   - 沒有健保碼的 drug_item：圖卡不顯示健保碼列。

## 本階段未做事項

- 未修改程式。
- 未寫資料庫。
- 未修改 `drug_items`。
- 未修改 `drug_diagnosis_links`。
- 未修改 official staging。
- 未 git add/commit。
