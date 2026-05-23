# Prescription NHI Drug Code Candidates Import Dry-run Report

## 本階段目的

本報告把 regex occurrence-level candidates 合併 cleaning candidates，轉成 `prescription_nhi_drug_code_candidates` staging 欄位 preview。預設 dry-run 不連 DB、不建立 table、不寫 DB。

## Input

- regex occurrence CSV: `/Users/linyancui/minimal_flask/db_backups/drug_staging/prescription_nhi_drug_code_regex_candidates.csv`
- cleaning unique-code CSV: `/Users/linyancui/minimal_flask/db_backups/drug_staging/prescription_nhi_drug_code_cleaning_candidates.csv`
- regex occurrence rows: 235
- unique code rows: 66
- regex unique normalized codes: 66
- cleaning unique normalized codes: 66
- preview occurrence rows: 235
- import_batch_id: `prescription_nhi_occurrence_20260523_105005`

## Review Status 統計（occurrence-level）

| review_status | occurrence_count |
|---|---:|
| auto_accepted | 119 |
| rejected | 102 |
| needs_review | 14 |
| pending | 0 |

## Official Join Status 統計（occurrence-level）

| official_join_status | occurrence_count |
|---|---:|
| matched | 102 |
| corrected_matched | 17 |
| false_positive | 102 |
| no_match | 14 |

## 每張照片 occurrence count

| source_photo | occurrence_count |
|---|---:|
| IMG_7202.JPG | 5 |
| IMG_7203.jpeg | 13 |
| IMG_7282.jpeg | 3 |
| IMG_7283.JPG | 1 |
| IMG_7284.JPG | 8 |
| IMG_7285.JPG | 10 |
| IMG_7290.jpeg | 15 |
| IMG_7364.jpeg | 8 |
| IMG_7367.JPG | 10 |
| IMG_7391.jpeg | 9 |
| IMG_7394.jpeg | 10 |
| IMG_7396.JPG | 10 |
| IMG_7397.JPG | 7 |
| IMG_7461.JPG | 1 |
| IMG_7462.JPG | 6 |
| IMG_7464.jpeg | 12 |
| IMG_7508.JPG | 3 |
| IMG_7509.JPG | 6 |
| IMG_7510.jpeg | 12 |
| IMG_7562.JPG | 3 |
| IMG_7564.jpeg | 8 |
| IMG_7624.jpeg | 6 |
| IMG_7627.JPG | 6 |
| IMG_7655.JPG | 6 |
| IMG_7656.JPG | 4 |
| IMG_7658.jpeg | 17 |
| IMG_7660.JPG | 6 |
| IMG_7670.JPG | 7 |
| IMG_7675.JPG | 14 |
| IMG_7721.jpeg | 9 |

## 欄位完整性

- missing source_photo: 0
- missing source_row_number: 0
- missing source_column: 0
- missing cleaning lookup: 0
- source_photo_page_or_index：原 OCR CSV 未提供，preview 先留空。
- raw_dosage_text / raw_frequency_text / raw_days_text：原 regex candidates 未拆出結構化欄位，preview 先留空。
- official_atc_code：cleaning candidates 未輸出 ATC，preview 先留空。

## 前 20 筆 Preview

| photo | row | column | raw | normalized | corrected | effective | join_status | review_status | official zh | official en |
|---|---:|---|---|---|---|---|---|---|---|---|
| IMG_7202.JPG | 1 | drug_names_raw | BC25537100 | BC25537100 |  | BC25537100 | matched | auto_accepted | 糖漸平膜衣錠 5毫克 | Trajenta 5mg Film-Coated Tablets |
| IMG_7202.JPG | 1 | drug_names_raw | BC22889100 | BC22889100 |  | BC22889100 | matched | auto_accepted | 立普妥　膜衣錠４０毫克 | LIPITOR FILM-COATED TABLETS 40MG |
| IMG_7202.JPG | 1 | drug_names_raw | BC21571100 | BC21571100 |  | BC21571100 | matched | auto_accepted | 脈優錠５毫克 | NORVASC TABLETS 5MG |
| IMG_7202.JPG | 1 | drug_names_raw | AB46766100 | AB46766100 |  | AB46766100 | matched | auto_accepted | "信東" 革理蔓錠２毫克 | GLIMARYL TABLETS 2MG (GLIMEPIRIDE) |
| IMG_7203.jpeg | 2 | drug_names_raw | AB230371GO | AB230371GO |  |  | no_match | needs_review |  |  |
| IMG_7203.jpeg | 2 | drug_names_raw | BISOPROLOL | BISOPROLOL |  |  | false_positive | rejected |  |  |
| IMG_7203.jpeg | 2 | drug_names_raw | BC25446100 | BC25446100 |  | BC25446100 | matched | auto_accepted | 倍必康平錠80/5毫克 | Twynsta Tablets 80/5mg |
| IMG_7203.jpeg | 2 | drug_names_raw | AB230371GO | AB230371GO |  |  | no_match | needs_review |  |  |
| IMG_7203.jpeg | 2 | drug_names_raw | AB45348100 | AB45348100 |  | AB45348100 | matched | auto_accepted | 百適歐膜衣錠５公絲 | BISO F.C. TABLETS 5MG |
| IMG_7203.jpeg | 2 | drug_names_raw | AC484721GO | AC484721GO |  |  | no_match | needs_review |  |  |
| IMG_7203.jpeg | 2 | generic_names_raw | BISOPROLOL | BISOPROLOL |  |  | false_positive | rejected |  |  |
| IMG_7203.jpeg | 2 | brand_names_raw | AB230371GO | AB230371GO |  |  | no_match | needs_review |  |  |
| IMG_7282.jpeg | 3 | drug_names_raw | AC61850100 | AC61850100 |  | AC61850100 | matched | auto_accepted | 服克痛膜衣錠80毫克 | Fekuton Film Coated Tablets 80mg |
| IMG_7282.jpeg | 3 | drug_names_raw | AC57805100 | AC57805100 |  | AC57805100 | matched | auto_accepted | "生達" 立舒脂膜衣錠20毫克 | Atorva F.C. Tab. 20mg "Standard" (Atorvastatin) |
| IMG_7284.JPG | 5 | drug_names_raw | AB091021G0 | AB091021G0 |  | AB091021G0 | matched | auto_accepted | "生達"心律錠10毫克 | PROPRANOLOL TABLETS 10MG |
| IMG_7284.JPG | 5 | drug_names_raw | BISOPROLOL | BISOPROLOL |  |  | false_positive | rejected |  |  |
| IMG_7284.JPG | 5 | drug_names_raw | AC57805100 | AC57805100 |  | AC57805100 | matched | auto_accepted | "生達" 立舒脂膜衣錠20毫克 | Atorva F.C. Tab. 20mg "Standard" (Atorvastatin) |
| IMG_7284.JPG | 5 | drug_names_raw | AC415191G0 | AC415191G0 |  | AC415191G0 | matched | auto_accepted | "強生" 福安源錠０．２５公絲（氟二氮平） | FLUPINE TABLETS 0.25MG (FLUDIAZEPAM) "JOHNSON" |
| IMG_7284.JPG | 5 | drug_names_raw | BC171251G0 | BC171251G0 |  | BC171251G0 | matched | auto_accepted | 康肯５毫克 | CONCOR 5 |
| IMG_7284.JPG | 5 | generic_names_raw | BISOPROLOL | BISOPROLOL |  |  | false_positive | rejected |  |  |

## 不寫 DB 說明

本輪沒有連線資料庫、沒有建立 table、沒有 INSERT/UPDATE/DELETE/TRUNCATE。`--apply` 尚未實作。

## 下一步 apply 前檢查清單

1. 確認 occurrence-level source unique 欄位可滿足 schema：source_csv/source_row_number/source_column/raw_nhi_drug_code/import_batch_id。
2. 對 `auto_accepted` 抽樣確認 raw OCR 值、corrected 值與 official NHI snapshot 是否合理。
3. 對 `needs_review` 先人工確認是否為 OCR 誤讀或舊碼。
4. 做 DB preflight：確認 `prescription_nhi_drug_code_candidates` 不存在或 schema 相容。
5. apply 前再檢查 official NHI staging row count 與 source version。
