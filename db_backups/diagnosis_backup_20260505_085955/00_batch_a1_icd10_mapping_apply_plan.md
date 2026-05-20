# Batch A1 ICD-10 Mapping Apply Plan

## 本階段目的

準備 Batch A 第一小批 7 筆 high-confidence candidates 的 apply plan。本檔只描述計畫，不執行 apply。

## Apply 前備份策略

建議 apply 前建立整張 `diagnosis_codes` 備份表。

建議備份表名：

`diagnosis_codes_batch_a1_icd10_apply_backup_YYYYMMDD_HHMMSS`

原因：

1. `diagnosis_codes` 目前約 198 筆，整張備份成本低。
2. 可完整保存 apply 前狀態。
3. 若 apply 後需回滾或比較，整張備份較安全。

## Apply 安全條件

apply 前必須逐筆重新 SELECT 確認：

1. `diagnosis_codes.id` 存在。
2. `diagnosis_codes.icd10_code` 仍為 NULL 或空字串。
3. `diagnosis_codes.icd9_code` 與 decision CSV 一致。
4. `diagnosis_codes.name_zh` 與 decision CSV 一致。
5. `candidate_icd10_code` 存在於 `official_icd10_cm_reference_staging`。
6. 官方 `use_flag = '1'`。
7. 任一筆失敗，整批停止，不 apply。

## Apply 範圍

若後續 apply，只允許更新這 7 筆 `diagnosis_codes.icd10_code`：

| id | name_zh | ICD-9 | new ICD-10 | official_name_zh |
| --- | --- | --- | --- | --- |
| 8 | 皮疹 | 7821 | R21 | 皮疹及其他非特定性皮膚出疹 |
| 13 | 脂肪瘤 | 2149 | D17.9 | 良性脂肪瘤 |
| 18 | 足癬 | 1104 | B35.3 | 足癬 |
| 19 | 汗斑 | 1110 | B36.0 | 變色糠疹(汗斑) |
| 20 | 蕁麻疹 | 7089 | L50.9 | 蕁麻疹 |
| 32 | 頸椎痛 | 7231 | M54.2 | 頸椎痛 |
| 68 | 頻尿 | 78841 | R35.0 | 頻尿 |

不得修改：

- `name_zh`
- `icd9_code`
- `aliases`
- `description`
- `usage_note`
- `drug_diagnosis_links`
- `official_icd10_cm_reference_staging`
- `diagnosis_icd_mappings_staging`
- OCR / photos / prescription tables
- `/dx`、`/drug`、LIFF

## Apply 後驗收

apply 後需確認：

1. `diagnosis_codes` count 不變，預期仍為 198。
2. `drug_diagnosis_links` count 不變，預期仍為 27。
3. 7 筆 `icd10_code` 更新為：

| id | expected icd10_code |
| --- | --- |
| 8 | R21 |
| 13 | D17.9 |
| 18 | B35.3 |
| 19 | B36.0 |
| 20 | L50.9 |
| 32 | M54.2 |
| 68 | R35.0 |

4. 查詢驗收：
   - `!dx R21`
   - `!dx D17.9`
   - `!dx B35.3`
   - `!dx B36.0`
   - `!dx L50.9`
   - `!dx M54.2`
   - `!dx R35.0`

## Dry-run 結論

- ready_to_apply：7
- blocked：0

本批 7 筆全部 ready_to_apply，可進入後續 approved-only apply。

本 plan 不修改資料庫、不產生 UPDATE SQL。
