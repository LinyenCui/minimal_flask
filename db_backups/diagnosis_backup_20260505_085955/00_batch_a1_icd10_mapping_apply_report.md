# Batch A1 ICD-10 Mapping Apply Report

## 執行模式

- mode: apply
- 本腳本只允許更新 Batch A1 7 筆 `diagnosis_codes.icd10_code`。
- 不修改 `name_zh`、`icd9_code`、`aliases`、`description`、`usage_note`。
- 不修改 `drug_diagnosis_links`、staging tables 或 `official_icd10_cm_reference_staging`。

## 摘要

| 項目 | 值 |
| --- | --- |
| backup table name | diagnosis_codes_batch_a1_icd10_apply_backup_20260520_235703 |
| updated ids | 8, 13, 18, 19, 20, 32, 68 |
| skipped / blocked | 0 |
| diagnosis_codes count before | 198 |
| diagnosis_codes count after | 198 |
| drug_diagnosis_links count before | 27 |
| drug_diagnosis_links count after | 27 |

## before / after icd10_code

| diagnosis_codes.id | name_zh | icd9_code | before icd10_code | after icd10_code | official_name_zh | official_name_en | use_flag | status | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8 | 皮疹 | 7821 |  | R21 | 皮疹及其他非特定性皮膚出疹 | Rash and other nonspecific skin eruption | 1 | ready_to_apply | ok |
| 13 | 脂肪瘤 | 2149 |  | D17.9 | 良性脂肪瘤 | Benign lipomatous neoplasm, unspecified | 1 | ready_to_apply | ok |
| 18 | 足癬 | 1104 |  | B35.3 | 足癬 | Tinea pedis | 1 | ready_to_apply | ok |
| 19 | 汗斑 | 1110 |  | B36.0 | 變色糠疹(汗斑) | Pityriasis versicolor | 1 | ready_to_apply | ok |
| 20 | 蕁麻疹 | 7089 |  | L50.9 | 蕁麻疹 | Urticaria, unspecified | 1 | ready_to_apply | ok |
| 32 | 頸椎痛 | 7231 |  | M54.2 | 頸椎痛 | Cervicalgia | 1 | ready_to_apply | ok |
| 68 | 頻尿 | 78841 |  | R35.0 | 頻尿 | Frequency of micturition | 1 | ready_to_apply | ok |

## 備註

- 本報告由 apply 腳本產出。
- 若 validation 失敗，apply 模式會整批停止並 rollback。
- 本腳本不處理 Batch A 其他 43 筆，也不處理 Batch B/C/D。
