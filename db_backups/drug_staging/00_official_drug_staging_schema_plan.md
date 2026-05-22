# 官方藥品 raw staging schema 設計草案

產生日期：2026-05-22

## 本階段目的

本階段根據 `reference_data/drug/raw/` 的 raw profiling 結果，設計四張官方/準官方藥品 raw staging table 草案與後續匯入策略。這些檔案只作為 schema plan，不建立 table、不匯入資料、不寫資料庫、不修改 `drug_items`、不修改 `drug_diagnosis_links`，也不處理 OCR 或 prescription。

## 來源資料

| dataset | raw file | profiling rows | profiling columns | 用途 |
| --- | --- | ---: | ---: | --- |
| NHI drug payment | `reference_data/drug/raw/nhi_drug_payment_20260522.csv` | 224,261 | 20 | 健保給付、價格、有效期間、ATC 與藥品代號 |
| TFDA license | `reference_data/drug/raw/tfda_drug_license_20260522.zip` / `36_2.csv` | 71,804 | 28 | 許可證、中文/英文品名、劑型、申請商、製造廠、狀態 |
| TFDA ingredient | `reference_data/drug/raw/tfda_drug_ingredient_20260522.zip` / `43_2.csv` | 125,902 | 7 | 許可證對成分、含量、單位 |
| TFDA ATC | `reference_data/drug/raw/tfda_atc_20260522.zip` / `41_2.csv` | 80,290 | 5 | 許可證對 ATC code |

## 設計總原則

1. staging 盡量保留官方 raw 欄位，但用穩定 snake_case 欄名保存，避免在 SQL 中直接使用中文欄名。
2. 每張表都保留 `raw_*` 欄位與 `normalized_*` 輔助欄位。
3. 每張表都加 source metadata：`source_file`, `source_url`, `source_version`, `import_batch_id`, `source_checksum`, `source_row_number`, `imported_at`。
4. 不直接修改或覆蓋 `drug_items`。
5. 不直接建立 `drug_items_official_match_candidates`；等 raw staging 匯入與驗收穩定後再設計候選比對表。
6. 不在此階段處理 OCR、prescription、照片樣本。

## 四張 staging table

### official_nhi_drug_payment_staging

用途：保存健保藥品給付資料的歷史列，包括藥品代號、藥名、成分、規格、支付價、有效起迄日、藥商、製造廠、劑型、ATC 與給付規定連結。

重點欄位：
- `raw_drug_code` / `normalized_drug_code`
- `raw_drug_name_en`, `raw_drug_name_zh`
- `raw_ingredient`
- `raw_spec_amount`, `raw_spec_unit`
- `raw_payment_price`
- `raw_effective_start_date`, `raw_effective_end_date`
- `raw_supplier`, `raw_manufacturer_name`
- `raw_dosage_form`
- `raw_atc_code` / `normalized_atc_code`
- `raw_drug_code_url`
- `parsed_tfda_license_id`, `normalized_license_no`

### official_tfda_drug_license_staging

用途：保存 TFDA 藥品許可證主檔，包括許可證字號、中文/英文品名、劑型、申請商、製造商、註銷狀態與有效日期。

重點欄位：
- `raw_license_no` / `normalized_license_no`
- `raw_product_name_zh`, `raw_product_name_en`
- `raw_dosage_form`
- `raw_main_ingredient_summary`
- `raw_applicant_name`
- `raw_manufacturer_name`
- `raw_cancel_status`, `raw_cancel_date`, `raw_valid_until`
- `is_cancelled`, `is_active_license`

### official_tfda_drug_ingredient_staging

用途：保存 TFDA 許可證對成分明細。此表通常會是一張許可證對多筆成分。

重點欄位：
- `raw_license_no` / `normalized_license_no`
- `raw_ingredient_name` / `normalized_ingredient_name`
- `raw_ingredient_code` / `normalized_ingredient_code`
- `raw_amount`, `raw_amount_unit`
- `normalized_amount`, `normalized_amount_unit`

### official_tfda_atc_staging

用途：保存 TFDA 許可證對 ATC code 的準官方橋接資料。此表可能一張許可證對多筆 ATC，並含主/次項。

重點欄位：
- `raw_license_no` / `normalized_license_no`
- `raw_primary_or_secondary`
- `raw_atc_code` / `normalized_atc_code`
- `raw_atc_name_en`, `raw_atc_name_zh`
- `is_primary_atc`

## keys 與 unique constraints 建議

### NHI drug payment

`藥品代號` 不適合單獨當唯一鍵。profiling 顯示整份歷史給付檔有 224,261 rows，但 `藥品代號` 只有 45,044 個 unique value，原因是同一藥品會因支付價與有效起迄日出現多筆歷史列。

建議：
- source row 唯一鍵：`source_version + source_checksum + source_row_number`
- business unique：`source_version + normalized_drug_code + raw_effective_start_date + raw_effective_end_date + raw_payment_price`
- 後續若要取得「目前有效」資料，應依 `effective_start_date` / `effective_end_date` 另做 view 或 curated table，不應在 raw staging 直接刪舊列。

### TFDA license

`許可證字號` 是重要 join key，但 profiling 顯示 raw 檔中 `許可證字號` 有重複，可能和歷史、異動或資料列粒度有關，因此 raw staging 不建議只用 `normalized_license_no` 當唯一鍵。

建議：
- source row 唯一鍵：`source_version + source_checksum + source_inner_file + source_row_number`
- business unique 草案：`source_version + normalized_license_no + source_row_number`
- 後續可另外建立去重後 current license view。

### TFDA ingredient

同一許可證可有多筆成分，`normalized_license_no` 不能唯一。

建議：
- source row 唯一鍵：`source_version + source_checksum + source_inner_file + source_row_number`
- business unique 草案：`source_version + normalized_license_no + normalized_ingredient_code + raw_amount_description + raw_amount + raw_amount_unit + source_row_number`

### TFDA ATC

同一許可證可有主/次多筆 ATC。

建議：
- source row 唯一鍵：`source_version + source_checksum + source_inner_file + source_row_number`
- business unique 草案：`source_version + normalized_license_no + normalized_atc_code + raw_primary_or_secondary`

## NHI licId 解析可行性

NHI `藥品代碼超連結` 範例包含：

```text
https://lmspiq.fda.gov.tw/web/DRPIQ/DRPIQ1000Result?licId=02015924
```

這個 `licId` 看起來是 TFDA 查詢系統使用的許可證識別碼，但它不是原始 `許可證字號` 的中文全字串。建議 staging 先保存：

- `raw_drug_code_url`
- `parsed_tfda_license_id`
- `normalized_license_no`

後續需用 TFDA license 的 `通關簽審文件編號`、許可證字號規則或 TFDA lookup 規則驗證是否能穩定轉換，不應直接假設 `licId` 等同許可證字號。

## TFDA join 策略

TFDA 三份資料可先以 `normalized_license_no` 做內部 join：

```text
official_tfda_drug_license_staging.normalized_license_no
  -> official_tfda_drug_ingredient_staging.normalized_license_no
  -> official_tfda_atc_staging.normalized_license_no
```

這是後續建立官方藥品 reference 的核心骨架。license 提供品名/劑型/廠商，ingredient 補成分與含量，ATC 補藥理治療分類。

## 對現有 drug_items 的比對欄位

未來可用以下欄位對現有 `drug_items` 做候選比對：

| 來源 | 欄位 | 可用性 |
| --- | --- | --- |
| NHI | `normalized_drug_code` | 若 `drug_items` 未存健保碼，暫無法 direct match |
| NHI | `raw_drug_name_zh`, `raw_drug_name_en` | 可對 `brand_name`, `generic_name`, `aliases` 做候選 |
| NHI | `raw_ingredient`, `raw_spec_amount`, `raw_spec_unit` | 可補強學名、規格、含量 |
| NHI | `raw_supplier`, `raw_manufacturer_name` | 可對 supplier / manufacturer |
| NHI | `raw_dosage_form`, `raw_atc_code` | 可補劑型與 ATC |
| TFDA license | `raw_product_name_zh`, `raw_product_name_en` | 可對 brand/generic/aliases |
| TFDA license | `raw_applicant_name`, `raw_manufacturer_name` | 可對 supplier/manufacturer |
| TFDA ingredient | `raw_ingredient_name`, `raw_amount`, `raw_amount_unit` | 可補成分與規格 |
| TFDA ATC | `raw_atc_code` | 可補分類 |

## 匯入策略草案

1. 先建立 raw staging table，匯入時不寫 `drug_items`。
2. 每個 raw file 產生一個 `import_batch_id`，保存 source checksum 與 source row number。
3. 匯入腳本預設 dry-run；只有 `--apply` 才建表/匯入。
4. 匯入前重新計算 sha256，必須與 manifest 一致。
5. 匯入後驗證 row count、欄位 non-null 分布、source row 唯一性、主要 key 重複狀況。
6. 再設計 read-only profile / matching candidate report。
7. 最後才設計 `drug_items_official_match_candidates`，由人工 review 決定是否補資料。

## 風險點

- `藥品代號` 是健保歷史給付列的藥品識別，但不能唯一代表整份 raw row。
- NHI `licId` 是否能穩定對 TFDA `許可證字號` 仍需驗證。
- TFDA `許可證字號` 在 license raw 中有重複，需理解資料列粒度後再做 current view。
- TFDA ingredient / ATC 都是一對多資料，不應合併成單一字串後直接覆蓋正式藥品表。
- 中文品名、英文品名、成分與規格的模糊比對可能誤配，尤其商品名、學名、規格差異很常見。
- 支付價與有效日期是歷史資料，需要明確定義 current effective row。

## 本階段未做事項

- 未建立 table。
- 未匯入資料。
- 未修改 `drug_items`。
- 未修改 `drug_diagnosis_links`。
- 未建立 `drug_items_official_match_candidates`。
- 未處理 OCR / photos / prescription。
- 未 git add / commit。
