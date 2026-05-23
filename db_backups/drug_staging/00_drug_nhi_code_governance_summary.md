# 藥品健保碼資料治理階段總結

## 1. 本階段完成範圍

本階段完成藥品健保碼從官方資料、處方照片 OCR 候選、正式 `drug_items` 主碼，到官方 code mapping table 的第一輪資料治理閉環。

本文件只整理目前狀態，不代表後續自動更新規則；正式資料仍以 review / dry-run / apply 的分階段流程處理。

## 2. 官方藥品資料 staging

目前本機資料庫已匯入四張官方 / 準官方 raw staging table：

| table | row count | 用途 |
|---|---:|---|
| `official_nhi_drug_payment_staging` | 224,261 | 健保署藥品給付資料；提供健保藥品代碼、藥名、成分、ATC、價格與有效日期等。 |
| `official_tfda_drug_license_staging` | 71,804 | 食藥署藥品許可證資料；提供許可證、品名、劑型、申請商、製造商等。 |
| `official_tfda_drug_ingredient_staging` | 125,902 | 食藥署成分資料；可用許可證字號 join license。 |
| `official_tfda_atc_staging` | 80,290 | 食藥署 ATC 資料；可用許可證字號 / ATC 輔助分類。 |

使用原則：

- raw staging 保留官方原始欄位與 normalized 欄位。
- 不直接用 raw staging 覆蓋正式 `drug_items`。
- 所有正式欄位更新先走 candidate / review / dry-run / apply。

## 3. 處方照片健保碼候選

處方照片中每列藥品左側可見健保藥品代碼，例如 `AC415191G0`、`AC58316100`。先前 Gemini / OCR 藥名流程未把這些健保碼結構化保存，因此本階段建立了專項流程。

目前已建立並匯入：

- table：`prescription_nhi_drug_code_candidates`
- row count：235 occurrence-level rows

統計：

| status | count |
|---|---:|
| `auto_accepted` | 119 |
| `rejected` | 102 |
| `needs_review` | 14 |

官方 join 狀態：

| official_join_status | count |
|---|---:|
| `matched` | 102 |
| `corrected_matched` | 17 |
| `false_positive` | 102 |
| `no_match` | 14 |

設計重點：

- 每一筆 regex occurrence 都保留 source CSV / source photo / row / column / match index。
- 保留 raw OCR code、normalized code、corrected code、effective code。
- 能明確 join official NHI 的候選可 `auto_accepted`。
- false positive，例如英文藥名誤抓，標 `rejected`。
- no_match / needs_manual_review 保留給後續人工確認。

## 4. drug_items 主表健保碼欄位

`drug_items` 是正式藥品查詢主表，目前 row count：152。

本階段已新增主健保碼欄位：

- `nhi_drug_code`
- `nhi_drug_code_source`
- `nhi_drug_code_confidence`
- `nhi_drug_code_verified_at`
- `nhi_drug_code_note`

目前已填入主要健保碼：31 筆。

未填主要健保碼：121 筆。

更新原則：

- 只更新 NHI code 相關欄位。
- 不修改 `generic_name`、`brand_name`、`aliases`。
- 不修改 `drug_diagnosis_links`。
- 不更新 `updated_at`。
- source 採用 check constraint 允許值，目前本批為 `prescription_ocr`。

### Metformin 主碼決策

`drug_item 87`：

- generic_name：`Metformin`
- brand_name：`Metformin 寬樂醣`
- 主健保碼：`AC585341G0`

決策說明：

- 使用者確認「寬樂醣膜衣錠500毫克」主健保碼為 `AC585341G0`。
- `AC58534100` 不作為 `drug_items.nhi_drug_code` 主碼。
- `AC58534100` 後續可保留到 `drug_item_official_code_mappings` review，作為其他碼 / 歷史碼 / 參考碼候選。

## 5. /drug 圖卡顯示

`/drug` 與 `!drug` 查詢目前已可在 Flex 圖卡顯示主健保碼。

顯示格式：

```text
健保碼：ACxxxx
```

實作原則：

- 只做顯示。
- 只有 `drug_items.nhi_drug_code` 非 NULL / 非空字串時才顯示。
- 未填健保碼的 121 筆藥品，不顯示空白健保碼列。
- 未把 `nhi_drug_code` 加入搜尋條件。

目前行為：

- `/drug Metformin` 可看到 `AC585341G0`。
- `/drug Bisoprolol` 可看到對應主健保碼。
- `/drug Atorvastatin` 可看到對應主健保碼。
- 無健保碼的藥品圖卡不顯示健保碼列。

## 6. drug_item_official_code_mappings

已建立正式 mapping table：

- table：`drug_item_official_code_mappings`
- row count：31
- code_type distribution：`NHI = 31`
- review_status distribution：`auto_accepted = 31`

本批匯入來源：

- `drug_items.nhi_drug_code` 的 31 筆主碼
- join `official_nhi_drug_payment_staging.normalized_drug_code`
- 全部 official NHI join 成功

mapping 規則：

- `code_type = NHI`
- `official_source_table = official_nhi_drug_payment_staging`
- `match_method = prescription_nhi_code`
- `confidence = high`
- `review_status = auto_accepted`
- `review_decision = approve`
- `is_primary = true`
- `is_active = true`

重要邊界：

- `drug_item_official_code_mappings` 是藥品與官方代碼的 mapping table。
- 它不等同 `drug_diagnosis_links`。
- `drug_diagnosis_links` 是藥品與診斷碼的臨床關聯表，目前 row count：27。
- NHI / TFDA / ATC 代碼不應混入 `drug_diagnosis_links`。

## 7. 尚未處理 / 待辦

### 7.1 Metformin 其他碼

- `AC58534100` 不作為 `drug_items` 主碼。
- 後續可進 `drug_item_official_code_mappings` review，判斷是否保留為歷史碼 / 其他碼 / 參考碼。

### 7.2 無對應 drug_items 的官方碼

處方健保碼抽取中有：

- `AC415191G0`
- official：FLUDIAZEPAM / FLUPINE 類資料
- 目前找不到對應 `drug_items`

建議後續人工確認：

- 是否為診所現用藥但尚未建立 drug_item。
- 是否 OCR / 照片來源需再檢查。
- 是否應新增 drug_items 或只保留在 prescription candidate。

### 7.3 尚無主健保碼的 drug_items

目前：

- `drug_items` total：152
- 已有 `nhi_drug_code`：31
- 尚無 `nhi_drug_code`：121

建議後續流程：

1. 使用 official NHI / TFDA staging 做候選比對。
2. 產出 candidate CSV。
3. 人工 review。
4. approved-only dry-run。
5. apply 前備份。
6. 只更新 NHI code 欄位或 mapping table。

### 7.4 prescription needs_review

`prescription_nhi_drug_code_candidates` 仍有：

- `needs_review`：14 筆
- `no_match`：14 筆

建議後續人工 review：

- 回看 OCR 原文與原始照片。
- 判斷是否為 OCR 誤讀。
- 若可校正並 join official NHI，再進 auto_accepted / approved 流程。

### 7.5 新處方照片 ingestion 流程

目前已處理的是既有 OCR CSV，不是重新 OCR 圖片。

未來若要處理新處方照片，建議流程：

1. 圖片 inventory。
2. OCR / Gemini extraction。
3. regex 抽健保碼 occurrence。
4. OCR 誤讀清洗。
5. join official NHI。
6. 匯入 `prescription_nhi_drug_code_candidates` staging。
7. 產生 drug_items mapping candidates。
8. 人工 review。
9. approved-only apply。

### 7.6 /drug 健保碼搜尋

目前 `/drug` 圖卡已顯示健保碼，但尚未把健保碼加入搜尋條件。

未做原因：

- 本階段只做顯示，不改查詢行為。
- 若要支援 `/drug AC58316100`，需要另開需求，把 `nhi_drug_code` 加入 search columns，並測試排序與既有藥名查詢是否受影響。

## 8. 安全原則

本階段所有正式寫入都遵守：

- 先 dry-run。
- 再 apply。
- apply 前檢查本機 DB target。
- apply 前確認不是 Render production DB。
- 不使用 `git add -A`。
- 不混入 main 分支。
- 不直接覆蓋藥名、診斷碼、關聯診斷資料。
- 健保碼與官方資料採 staging / mapping / review 流程管理。

## 9. 建議下一步

建議下一階段優先順序：

1. commit 這一批健保碼治理文件與程式變更，精準指定檔案。
2. 針對 `AC58534100` 建立 Metformin 其他碼 review。
3. 處理 `AC415191G0` 無對應 drug_items 問題。
4. 對剩餘 121 筆 drug_items 建立 official NHI / TFDA 比對候選。
5. 規劃 `/drug <健保碼>` 搜尋，但不要和本階段混在同一 commit。
