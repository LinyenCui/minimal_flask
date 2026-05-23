# Drug Items 主要健保藥品代碼欄位 Schema Plan

## 本階段目的

本文件只設計 `drug_items` 新增主要健保藥品代碼欄位的 schema。  
本輪不修改資料庫、不執行 `ALTER TABLE`、不更新 `drug_items`、不修改 `drug_diagnosis_links`、不修改 `/drug` Flex。

## 現況

`drug_items` 目前共有 152 筆。

目前欄位：

| column | type | nullable |
|---|---|---|
| id | bigint | NO |
| seq_no | text | NO |
| table_type | text | NO |
| supplier | text | YES |
| manufacturer | text | YES |
| generic_name | text | NO |
| brand_name | text | NO |
| aliases | text | YES |
| is_high_frequency | boolean | NO |
| highlight_color | text | YES |
| highlight_meaning | text | YES |
| handwritten_note | text | YES |
| note_confidence | text | NO |
| note_type | text | NO |
| item_kind | text | NO |
| category | text | YES |
| needs_manual_check | boolean | NO |
| source_photo | text | YES |
| source_version | text | NO |
| staging_import_batch_id | text | NO |
| staging_row_id | bigint | NO |
| is_active | boolean | NO |
| created_at | timestamptz | NO |
| updated_at | timestamptz | NO |

目前沒有 `nhi_drug_code`、`drug_code` 或其他健保碼相關欄位。

已完成的前置資料：

- `official_nhi_drug_payment_staging` 已匯入健保署藥品給付資料。
- `prescription_nhi_drug_code_candidates` 已匯入 235 筆 OCR occurrence-level 健保藥品代碼候選。
- `drug_item_nhi_code_mapping_candidates.csv` 已產生 33 個 unique effective NHI code 候選。
- 其中 32 個為 `strong_match` 到現有 `drug_items`。
- 1 個 `AC415191G0` 找不到現有 `drug_items` 對應。

## 建議新增欄位

| column | type | nullable | purpose |
|---|---|---|---|
| nhi_drug_code | varchar(20) | YES | 主要健保藥品代碼，供 `/drug` 圖卡、藥局識別、日常查詢使用 |
| nhi_drug_code_source | varchar(50) | YES | 來源，例如 `prescription_ocr`、`official_nhi`、`manual`、`migrated` |
| nhi_drug_code_confidence | varchar(20) | YES | 可信度：`high`、`medium`、`low` |
| nhi_drug_code_verified_at | timestamptz | YES | 最後驗證時間 |
| nhi_drug_code_note | text | YES | 備註，例如 OCR corrected、來源照片、review batch |

欄位都允許 `NULL`。原因是目前不是每個 `drug_item` 都已經確認主要健保碼，且部分藥品可能不是健保給付藥品或仍需人工 review。

## 約束與 Index 建議

初期不建議對 `nhi_drug_code` 設 `UNIQUE`。

理由：

- 同一健保碼可能在資料治理過渡期暫時對到多個概念候選。
- 有些現有 `drug_items` 是複方、劑量或商品名概念，後續可能需要拆分或合併。
- 健保資料有歷史給付列，正式主碼欄位只代表目前主要識別碼，不代表完整代碼關係。
- 若未來確認 `drug_items` 概念一碼一品且治理穩定，再考慮加 partial unique constraint。

建議建立普通 index：

- `idx_drug_items_nhi_drug_code`
- `idx_drug_items_nhi_drug_code_source`

建議 CHECK constraint：

- `nhi_drug_code_confidence IN ('high', 'medium', 'low')`
- `nhi_drug_code_source IN ('prescription_ocr', 'official_nhi', 'manual', 'migrated')`

## 與 drug_item_official_code_mappings 的關係

`drug_items.nhi_drug_code` 是主表上的「主要健保碼」，用途是日常顯示、快速查詢、藥局識別與 `/drug` 圖卡。

`drug_item_official_code_mappings` 則應保存完整官方碼關係：

- NHI code
- TFDA license
- ATC code
- 歷史碼
- 多來源比對結果
- review 狀態
- confidence
- official source table / source id

建議分工：

- `drug_items.nhi_drug_code`：一個主要碼，便於查詢與 UI 顯示。
- `drug_item_official_code_mappings`：多碼、多來源、歷史碼與審核紀錄。

未來 `/drug` 圖卡可優先顯示 `drug_items.nhi_drug_code`。若需要詳細資訊，LIFF 或詳細頁再顯示 mapping table 的完整清單。

## Apply 流程建議

### Phase 1：ALTER TABLE

1. 確認 branch 為 `dev_line_channel`。
2. 確認 DB 為本機 `localhost:5432/dispatch_db`。
3. 備份 `drug_items`。
4. 執行 `alter_drug_items_add_nhi_drug_code.sql`。
5. 驗證新增欄位與 index/check constraints。
6. 不更新任何資料列。

### Phase 2：32 筆 strong_match dry-run

1. 讀取 `drug_item_nhi_code_mapping_candidates.csv`。
2. 只處理 `candidate_status = strong_match`。
3. 重新確認每個 `candidate_drug_item_id` 存在。
4. 確認 `nhi_drug_code` 目前為 `NULL`，避免覆蓋人工資料。
5. 產出 dry-run report。
6. 不產生一鍵 UPDATE SQL。

### Phase 3：approved-only apply

1. 使用人工 decision CSV。
2. Apply 前備份整張 `drug_items`。
3. 只更新：
   - `nhi_drug_code`
   - `nhi_drug_code_source`
   - `nhi_drug_code_confidence`
   - `nhi_drug_code_verified_at`
   - `nhi_drug_code_note`
4. 不修改：
   - `generic_name`
   - `brand_name`
   - `aliases`
   - `drug_diagnosis_links`
   - official staging
   - prescription staging
5. Apply 後驗收：
   - `drug_items` count 不變
   - `drug_diagnosis_links` count 不變
   - 32 筆 strong_match 的 `nhi_drug_code` 已填入
   - `/drug` 查詢不受影響

## 安全原則

- 不直接把健保碼塞進 `aliases`。
- 不從 OCR occurrence 直接覆蓋主表，必須走 candidate → review → approved-only apply。
- `prescription_nhi_drug_code_candidates` 保留來源照片與 OCR occurrence。
- `official_nhi_drug_payment_staging` 保留官方歷史給付列。
- `drug_items.nhi_drug_code` 只保存目前人工核准的主要碼。

