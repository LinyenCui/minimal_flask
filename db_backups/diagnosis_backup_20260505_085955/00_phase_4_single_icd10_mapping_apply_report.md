# Phase 4 Single ICD-10 Mapping Apply Report

## 執行模式

- mode: apply
- 本腳本只允許更新 `diagnosis_codes.id=76` 的 `icd10_code`。
- 不修改 `name_zh`、`icd9_code`、`aliases`、`description`、`usage_note`。
- 不修改 `drug_diagnosis_links` 或 staging tables。

## 摘要

| 項目 | 值 |
| --- | --- |
| backup table name | diagnosis_codes_phase_4_single_icd10_apply_backup_20260520_213150 |
| updated id | 76 |
| skipped / blocked | 0 |
| diagnosis_codes count before | 198 |
| diagnosis_codes count after | 198 |
| drug_diagnosis_links count before | 27 |
| drug_diagnosis_links count after | 27 |

## before / after icd10_code

| diagnosis_codes.id | name_zh | icd9_code | before icd10_code | after icd10_code | official_name_zh | official_name_en | use_flag | status | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 76 | 急性腎衰竭 | 5849 |  | N17.9 | 急性腎衰竭 | Acute kidney failure, unspecified | 1 | ready_to_apply | ok |

## 備註

- 本報告由 apply 腳本產出。
- 若 validation 失敗，apply 模式會整批停止並 rollback。
- 本腳本不處理其他 needs_more_source 候選。
