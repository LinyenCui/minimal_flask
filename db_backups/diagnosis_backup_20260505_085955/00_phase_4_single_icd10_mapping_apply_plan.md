# Phase 4 單筆 ICD-10 補碼 Apply Plan

## 本階段目的

準備單筆 high-confidence candidate 的 approved-only apply plan，但本檔只描述計畫，不執行 apply。

目標：

| 欄位 | 值 |
| --- | --- |
| diagnosis_codes.id | 76 |
| name_zh | 急性腎衰竭 |
| current_icd9_code | 5849 |
| current_icd10_code | (空白) |
| new_icd10_code | N17.9 |
| official_name_zh | 急性腎衰竭 |
| official_name_en | Acute kidney failure, unspecified |
| use_flag | 1 |
| dry_run_status | ready_to_apply |

## Apply 前備份策略

建議 apply 前建立整張 `diagnosis_codes` 備份表，而不是只備份單筆。

建議備份表名：

`diagnosis_codes_phase_4_single_icd10_apply_backup_YYYYMMDD_HHMMSS`

原因：

1. `diagnosis_codes` 只有 198 筆，整張備份成本低。
2. 可完整保存 apply 前狀態。
3. 若未來需要比對其他欄位，整張備份較安全。

## Apply 安全條件

apply 前必須重新 SELECT 確認：

1. `diagnosis_codes.id = 76` 存在。
2. `diagnosis_codes.icd10_code` 仍為 NULL 或空字串。
3. `diagnosis_codes.icd9_code = '5849'`。
4. `diagnosis_codes.name_zh = '急性腎衰竭'`。
5. `official_icd10_cm_reference_staging.icd10_code = 'N17.9'` 存在。
6. `N17.9 use_flag = '1'`。
7. 任一條件失敗即停止，不 apply。

## Apply 範圍

若後續 apply，只允許：

- 更新 `diagnosis_codes.id = 76`
- 只更新 `diagnosis_codes.icd10_code = 'N17.9'`

不得修改：

- `name_zh`
- `icd9_code`
- `aliases`
- `description`
- `usage_note`
- `drug_diagnosis_links`
- `official_icd10_cm_reference_staging`
- `diagnosis_icd_mappings_staging`
- 任何 drug tables
- OCR / photos / prescription tables

## Rollback Plan

若 apply 後需要回滾，應依 apply 前建立的 `diagnosis_codes_phase_4_single_icd10_apply_backup_YYYYMMDD_HHMMSS` 備份表還原 id 76 的 apply 前 `icd10_code`。

本 plan 不提供可直接執行的 UPDATE SQL。

## Apply 後驗收

apply 後需確認：

1. `diagnosis_codes` count 不變，預期仍為 198。
2. `drug_diagnosis_links` count 不變，預期仍為 27。
3. `diagnosis_codes.id = 76` 的 `icd10_code = N17.9`。
4. `!dx 急性腎衰竭` 可查到主診斷結果。
5. `!dx N17.9` 可查到主診斷結果。
6. 不影響 `/dx`、`/drug`、LIFF 或 drug diagnosis links。

## 結論

目前 dry-run status：`ready_to_apply`。

可進入後續單筆 approved-only apply。

本 plan 不修改資料庫、不產生 UPDATE SQL。
