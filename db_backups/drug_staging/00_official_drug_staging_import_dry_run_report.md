# 官方藥品 staging import dry-run report

產生時間：2026-05-23 08:27:57
import_batch_id：`official_drug_staging_20260523_082757`

## 本階段行為

本次為 dry-run：只讀 manifest 與 raw files，驗證 sha256，統計 row count，未連資料庫、未建立 table、未寫入資料。

## manifest verification / target tables

| dataset | source_file | target_table | estimated_insert_count | sha256_match | sha256 |
| --- | --- | --- | --- | --- | --- |
| TFDA ATC | reference_data/drug/raw/tfda_atc_20260522.zip | official_tfda_atc_staging | 80290 | yes | af8f9cf01b19c56b75cee1f4b709e5a1590dbeec8533536c840206b6d8b47ec3 |

## 預計匯入策略

- 只有執行 `--apply` 才會讀取 `.env` / `DATABASE_URL`。
- apply 時只會建立/寫入四張 official drug raw staging tables。
- apply 時會先檢查同一 `source_version + source_checksum` 是否已存在；若存在則停止，避免重複匯入。
- 不會修改 `drug_items`、`drug_diagnosis_links` 或 diagnosis 相關資料表。
