# Phase G /dx read-only Flex Message 報告

執行時間：2026-05-17

本階段只為 `/dx` 單筆查詢新增 read-only Flex Message 顯示。未修改資料庫資料、未修改 `/drug`、未新增 LIFF 頁面、未新增 `drug_diagnosis_links` 維護功能。

## 修改檔案

| 檔案 | 變更 |
|---|---|
| `modules/views/diagnosis_flex.py` | 新增 diagnosis 單筆 Flex renderer。 |
| `modules/handlers/diagnosis_handler.py` | 單筆 `/dx` 結果優先嘗試 Flex；失敗時回原文字版。 |

## 沿用的既有 Flex 元件 / 參考檔案

主要參考：

- `rewrite/views/customer_flex.py`
  - label/value row 風格。
  - 深藍 header。
  - `separator` 分段。
  - `mega` bubble detail card。

輔助參考：

- `rewrite/views/trip_flex.py`
  - 查詢結果用主題色、狀態/標籤突顯。
  - 單筆 detail card 與多筆 carousel 分工。

- `modules/utils/line_bot.py`
  - 既有 `reply_message()` 支援 dict 型 Flex Message。
  - 使用 `type='flex'`、`altText`、`contents` 的既有格式。

## Flex 顯示內容

`/dx` 單筆結果會產生一張 Flex bubble：

- Header：
  - 診斷中文名稱。
  - ICD-10 或 ICD-9 作副標。

- Body：
  - ICD-10
  - ICD-9
  - 中文名
  - 英文名若有
  - 高頻 / 手寫新增 / 不常用標籤
  - 章節
  - 分類
  - additional codes / components 若有
  - description / notes 摘要，最多 2 筆且截短
  - 相關藥名最多 5 筆

相關藥名顯示：

- `generic_name / brand_name`
- `confidence`
- `source_type`
- `role_type`

`note_text` 不放進 Flex，避免卡片過長；原文字 fallback 仍保留完整 note_text。

## Fallback 策略

保留原本 `/dx` 文字 fallback。

行為：

- `result.type == 'single'`
  - 先用 `render_diagnosis_detail()` 建 Flex。
  - 透過 `reply_message()` 發送。
  - 若 renderer 或 LINE Flex 送出失敗，改用原本 `_format_result()` 文字版。

- `result.type != 'single'`
  - 不強行做 carousel。
  - 直接沿用原本文字版。

因此以下情境維持文字版：

- 多筆查詢結果，例如 `/dx 糖尿病`
- table 結果
- empty 結果
- error 結果
- help / chapters

## 本地測試

測試方式：

- 使用 Flask app context 執行 read-only 查詢。
- 用 `DiagnosisQueryService.search()` 取得結果。
- 單筆結果用 `render_diagnosis_detail()` 產生 Flex。
- 用 LINE SDK `FlexContainer.from_dict()` 驗證 Flex JSON 可解析。
- 測試前後比對核心表筆數。

測試前後筆數：

| 表 | 測試前 | 測試後 |
|---|---:|---:|
| `diagnosis_codes` | 198 | 198 |
| `drug_items` | 152 | 152 |
| `drug_diagnosis_links` | 26 | 26 |

### 測試案例

| 測試 | 結果類型 | 主結果 | Flex | 相關藥名 | 結果 |
|---|---|---|---|---|---|
| `/dx I10` | `single` | 有，本態性高血壓 | Flex JSON 可解析 | Flex / text 都有 | 通過 |
| `/dx E11.9` | `single` | 有，第2型糖尿病，未伴有併發症 | Flex JSON 可解析 | Flex / text 都有 | 通過 |
| `/dx 糖尿病` | `list` | 有，2 筆 | 不嘗試 Flex | text 有相關藥名 | 通過，維持文字版 |
| `/dx 不存在XYZ` | `empty` | 無 | 不嘗試 Flex | 無 | 通過，維持文字版 |

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
- `/drug` 程式
- LINE Bot routing
- LIFF 頁面
- `drug_diagnosis_links` 維護功能

本階段未執行：

- INSERT / UPDATE / DELETE
- migration
- 新增 seed
- 新增 prescription tables
- 新增 LIFF form
- 新增 `/drug` Flex

## 結論

Phase G 已完成 `/dx` 單筆查詢 read-only Flex Message。

目前狀態：

- 精確 `/dx I10`、`/dx E11.9` 會優先走 Flex。
- 多筆 `/dx 糖尿病` 與 empty `/dx 不存在XYZ` 維持原文字版。
- 原文字 fallback 仍完整保留。
- `/drug` 完全未修改。
