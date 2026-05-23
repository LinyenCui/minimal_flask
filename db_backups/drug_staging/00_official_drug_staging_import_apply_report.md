# 官方藥品 staging import apply report

產生時間：2026-05-23 08:30:40
import_batch_id：`official_drug_staging_20260523_083037`

## 匯入結果

| dataset | source_file | sha256 | table | inserted_rows | final_table_rows | status |
| --- | --- | --- | --- | --- | --- | --- |
| TFDA ATC | reference_data/drug/raw/tfda_atc_20260522.zip | af8f9cf01b19c56b75cee1f4b709e5a1590dbeec8533536c840206b6d8b47ec3 | official_tfda_atc_staging | 80290 | 80290 | inserted |

## 正式表筆數檢查

| table | before | after |
| --- | --- | --- |
| drug_items | 152 | 152 |
| drug_diagnosis_links | 27 | 27 |

本次只建立/寫入 official drug raw staging tables。未修改 `drug_items`，未修改 `drug_diagnosis_links`，未修改 diagnosis 相關資料表。
