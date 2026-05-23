# Drug Items Official-first Ready Apply Plan

## 本階段目的

本 apply plan 只描述後續若要 apply 時的安全策略。本輪不修改資料庫、不產生 UPDATE SQL。

## 來源

- `db_backups/drug_staging/drug_items_official_first_ready_decisions.csv`

## Apply 前備份策略

- 建議先備份整張 `drug_items`。
- 備份表名可採：`drug_items_official_first_ready_backup_YYYYMMDD_HHMMSS`。
- 備份後再重新 SELECT 驗證 6 筆 current 值仍與 decisions CSV 一致。

## Apply 範圍

- 只處理 approved rows：id 4, 10, 13, 96, 123, 150。
- 不修改 id 14、17、77。
- 不修改 `drug_diagnosis_links`。
- 不修改 official staging。
- 不修改藥診關聯、OCR、prescription、diagnosis tables。

## 欄位更新原則

- `keep_current`：不做 DB 寫入。
- `add_alias_only`：只補 `aliases`，不改 `generic_name` / `brand_name`。
- `correct_generic_name`：只改 `generic_name`，`brand_name` 不改；舊 generic_name 應保留到 `aliases` 或另有查詢策略。
- 本批不直接覆蓋 `supplier`、`manufacturer`、`category`、`item_kind`。

## 預計處理清單

| id | action | current generic | proposed generic | brand_name policy | alias policy |
|---:|---|---|---|---|---|
| 4 | correct_generic_name | Dextromethorphan20mg+Pot. Cres | POTASSIUM CRESOLSULFONATE 90 MG + LYSOZYME CHLORIDE 20 MG + DEXTROMETHORPHAN HBR 20 MG | 不改 brand_name | 保留舊 generic_name、官方品名/成分到 aliases |
| 10 | correct_generic_name | Cephalaxin | CEPHALEXIN MONOHYDRATE | 不改 brand_name | 保留舊 generic_name、官方品名/成分到 aliases |
| 13 | correct_generic_name | DIMETHYL 1, 4- 7-ISOPROPYLASUL | AZULENE | 不改 brand_name | 保留舊 generic_name、官方品名/成分到 aliases |
| 96 | correct_generic_name | Bethamechol | BETHANECHOL CHLORIDE 25 MG | 不改 brand_name | 保留舊 generic_name、官方品名/成分到 aliases |
| 123 | correct_generic_name | Beniel | BENIDIPINE HYDROCHLORIDE 4 MG | 不改 brand_name | 保留舊 generic_name、官方品名/成分到 aliases |
| 150 | add_alias_only | Urea | UREA | 不改 brand_name | 只補 aliases |

## Apply 後驗收

- `drug_items` count 不變。
- `drug_diagnosis_links` count 不變。
- `/drug` 可用新 generic_name 查到修正後項目。
- 舊名稱如果仍要可查，需確認 `aliases` 或查詢策略涵蓋。
- id 14、17、77 仍維持 apply 前值。

## 不產生 SQL

本文件不包含可直接執行的 UPDATE SQL。後續若要 apply，應另建安全腳本，預設 dry-run，只有 `--apply` 才寫入。