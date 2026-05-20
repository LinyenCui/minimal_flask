# Batch A1 ICD-10 Mapping Dry-run Report

## 本階段目的

本階段只處理 Batch A 第一小批 7 筆 high-confidence candidates，僅做 decision / dry-run，不修改資料庫、不產生 UPDATE SQL、不 apply。

本階段不處理：

- Batch A 其他 43 筆
- Batch B / C / D
- OCR / photos / prescription
- `/dx`、`/drug`、LIFF

## 來源候選

| id | name_zh | ICD-9 | candidate ICD-10 |
| --- | --- | --- | --- |
| 8 | 皮疹 | 7821 | R21 |
| 13 | 脂肪瘤 | 2149 | D17.9 |
| 18 | 足癬 | 1104 | B35.3 |
| 19 | 汗斑 | 1110 | B36.0 |
| 20 | 蕁麻疹 | 7089 | L50.9 |
| 32 | 頸椎痛 | 7231 | M54.2 |
| 68 | 頻尿 | 78841 | R35.0 |

## Dry-run 檢查摘要

| 項目 | 值 |
| --- | --- |
| 本批候選數 | 7 |
| ready_to_apply | 7 |
| blocked | 0 |
| diagnosis_codes count | 198 |
| drug_diagnosis_links count | 27 |

## 每筆正式表狀態與官方 reference 對照

| id | name_zh | ICD-9 | current ICD-10 | candidate ICD-10 | official_name_zh | official_name_en | USE | dry_run_status | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8 | 皮疹 | 7821 | (空白) | R21 | 皮疹及其他非特定性皮膚出疹 | Rash and other nonspecific skin eruption | 1 | ready_to_apply | ok |
| 13 | 脂肪瘤 | 2149 | (空白) | D17.9 | 良性脂肪瘤 | Benign lipomatous neoplasm, unspecified | 1 | ready_to_apply | ok |
| 18 | 足癬 | 1104 | (空白) | B35.3 | 足癬 | Tinea pedis | 1 | ready_to_apply | ok |
| 19 | 汗斑 | 1110 | (空白) | B36.0 | 變色糠疹(汗斑) | Pityriasis versicolor | 1 | ready_to_apply | ok |
| 20 | 蕁麻疹 | 7089 | (空白) | L50.9 | 蕁麻疹 | Urticaria, unspecified | 1 | ready_to_apply | ok |
| 32 | 頸椎痛 | 7231 | (空白) | M54.2 | 頸椎痛 | Cervicalgia | 1 | ready_to_apply | ok |
| 68 | 頻尿 | 78841 | (空白) | R35.0 | 頻尿 | Frequency of micturition | 1 | ready_to_apply | ok |

## Apply 範圍說明

若後續進入 apply，只允許更新這 7 筆 `diagnosis_codes.icd10_code`：

| diagnosis_codes.id | new icd10_code |
| --- | --- |
| 8 | R21 |
| 13 | D17.9 |
| 18 | B35.3 |
| 19 | B36.0 |
| 20 | L50.9 |
| 32 | M54.2 |
| 68 | R35.0 |

不得修改 `name_zh`、`icd9_code`、`aliases`、`description`、`usage_note`，不得修改 `drug_diagnosis_links` 或 official reference staging。

本報告不修改資料庫、不產生 UPDATE SQL。
