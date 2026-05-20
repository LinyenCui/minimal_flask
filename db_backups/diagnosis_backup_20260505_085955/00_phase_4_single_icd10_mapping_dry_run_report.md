# Phase 4 單筆 ICD-10 補碼 Dry-run Report

## 本階段目的

本階段只處理 1 筆 high-confidence candidate：`diagnosis_codes.id = 76`。

- 不修改資料庫
- 不產生 UPDATE SQL
- 不 apply
- 不處理其他 7 筆 `needs_more_source`
- 不修改 `diagnosis_codes`、`official_icd10_cm_reference_staging`、任何 staging table、`drug_diagnosis_links`
- 不處理 OCR / photos / prescription

## 來源與目標

| 項目 | 值 |
| --- | --- |
| diagnosis_codes.id | 76 |
| current_name_zh | 急性腎衰竭 |
| current_icd9_code | 5849 |
| current_icd10_code | (空白) |
| candidate_icd10_code | N17.9 |
| official_name_zh | 急性腎衰竭 |
| official_name_en | Acute kidney failure, unspecified |
| use_flag | 1 |

## 正式表目前狀態

| 檢查項目 | 結果 |
| --- | --- |
| diagnosis_codes.id=76 是否存在 | 是 |
| icd10_code 是否仍為 NULL 或空白 | 是 |
| icd9_code 是否為 5849 | 是 |
| name_zh 是否為急性腎衰竭 | 是 |
| diagnosis_codes count | 198 |
| drug_diagnosis_links count | 27 |

## 官方 reference 對照

| 檢查項目 | 結果 |
| --- | --- |
| N17.9 是否存在於 official_icd10_cm_reference_staging | 是 |
| N17.9 use_flag 是否為 1 | 是 |
| 官方中文名 | 急性腎衰竭 |
| 官方英文名 | Acute kidney failure, unspecified |
| source_version | nhi_2023_icd10_cm |
| source_row_number | 24325 |

## Dry-run 結果

| 項目 | 值 |
| --- | --- |
| dry_run_status | ready_to_apply |
| reason | ok |

若後續進入 apply，只允許更新：

- `diagnosis_codes.id = 76`
- 欄位：`icd10_code`
- 新值：`N17.9`

不修改 `name_zh`、`icd9_code`、`aliases`、`description`、`usage_note`，也不修改 `drug_diagnosis_links`。

## 不處理項目

本階段不處理上一輪候選中的其他 7 筆 `needs_more_source`：

- 63 腎性貧血 → D63.1
- 71 泌尿道感染 → N39.0
- 78 慢性腎絲球腎炎 → N03.9
- 92 攝護腺炎 → N41.9
- 98 腎囊腫 → N28.1
- 109 多囊腎（顯性染色體） → Q61.2
- 133 惡性貧血 → D51.0

本報告不修改資料庫、不產生 UPDATE SQL。
