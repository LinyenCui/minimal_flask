# Phase H /drug read-only Flex Message 報告

執行時間：2026-05-17

本階段只為 `/drug` 查詢新增 read-only Flex Message 顯示。未修改資料庫資料、未修改 `/dx`、未新增 LIFF 頁面、未新增或修改 `drug_diagnosis_links` 維護功能。

## 修改檔案

| 檔案 | 變更 |
|---|---|
| `modules/views/drug_flex.py` | 新增 drug item Flex bubble / carousel renderer。 |
| `modules/handlers/drug_handler.py` | `/drug` 查到資料時優先嘗試 Flex；失敗時回原文字版。 |

## 沿用的既有 Flex 元件 / 參考檔案

主要參考：

- `rewrite/views/fixed_schedule_flex.py`
  - 每筆一張 bubble。
  - 多筆結果回 carousel。
  - label/value row。
  - purple header 主題。
  - `kilo` bubble size。

輔助參考：

- `rewrite/views/customer_flex.py`
  - `_row(label, value)` 的資料卡風格。
  - separator 分段。

- `modules/utils/line_bot.py`
  - 既有 `reply_message()` 支援 dict 型 Flex Message。
  - 使用 `type='flex'`、`altText`、`contents` 的既有格式。

## Flex 顯示內容

`/drug` 查到資料時會產生：

- 1 筆：single bubble。
- 多筆：carousel，最多 10 張 bubble，對齊目前文字版最多 10 筆結果。

每張 drug bubble 顯示：

- `generic_name`
- `brand_name`
- `table_type`
- `item_kind`
- `category`
- `supplier` 若有
- `manufacturer` 若有
- 相關診斷碼最多 5 筆

相關診斷碼顯示：

- `ICD-10 / ICD-9 / name_zh`
- `confidence`
- `source_type`
- `role_type`

`note_text` 不放進 Flex，避免卡片過長；原文字 fallback 仍保留完整 note_text。

## Fallback 策略

保留原本 `/drug` 文字 fallback。

行為：

- `result.type == 'list'` 且有 `items`
  - 先用 `render_drug_results()` 建立 Flex。
  - 透過 `reply_message()` 發送。
  - 若 renderer 或 LINE Flex 送出失敗，改用原本 `_format_result()` 文字版。

- 以下情境維持文字版：
  - 查無資料
  - help
  - error
  - 無 items 的異常 list

## 本地測試

測試方式：

- 使用 Flask app context 執行 read-only 查詢。
- 用 `DrugQueryService.search()` 取得結果。
- list 結果用 `render_drug_results()` 產生 Flex。
- 用 LINE SDK `FlexContainer.from_dict()` 驗證 Flex JSON 可解析。
- 測試前後比對核心表筆數。

測試前後筆數：

| 表 | 測試前 | 測試後 |
|---|---:|---:|
| `diagnosis_codes` | 198 | 198 |
| `drug_items` | 152 | 152 |
| `drug_diagnosis_links` | 26 | 26 |

### 測試案例

| 測試 | 結果類型 | 主藥名結果 | Flex | Flex container | 相關診斷碼 | 結果 |
|---|---|---|---|---|---|---|
| `/drug Concor` | `list` | 有，1 筆 | 可解析 | `bubble` | Flex / text 都有 I10 | 通過 |
| `/drug Metformin` | `list` | 有，3 筆 | 可解析 | `carousel` | Flex / text 都有 E11.9 | 通過 |
| `/drug 胰島素` | `list` | 有，1 筆 | 可解析 | `bubble` | Flex / text 都有 E11.9 | 通過 |
| `/drug 不存在XYZ` | `empty` | 無 | 不嘗試 Flex | 無 | 無 | 通過，維持文字版 |

備註：

- 測試時載入 Flask app 會啟動既有 scheduler；本次 log 顯示需要更新的班次為 0，沒有資料變更。
- 未印出完整 `DATABASE_URL`、密碼或 token；系統 log 僅顯示既有遮罩後資訊。

## 未修改項目清單

本階段未修改：

- `drug_items`
- `diagnosis_codes`
- `drug_diagnosis_links`
- `drug_items_staging`
- `diagnosis_icd_mappings_staging`
- OCR 相關檔案或流程
- prescription tables
- `/dx` 程式
- LINE Bot routing
- LIFF 頁面
- `drug_diagnosis_links` 維護功能

本階段未執行：

- INSERT / UPDATE / DELETE
- migration
- 新增 seed
- 新增 prescription tables
- 新增 LIFF form
- 修改 `/dx` Flex

## 結論

Phase H 已完成 `/drug` read-only Flex Message。

目前狀態：

- `/drug Concor`、`/drug 胰島素` 這類單筆結果會回 bubble。
- `/drug Metformin` 這類多筆結果會回 carousel。
- `/drug 不存在XYZ` 維持原文字版。
- 原文字 fallback 仍完整保留。
- `/dx` 完全未修改。
