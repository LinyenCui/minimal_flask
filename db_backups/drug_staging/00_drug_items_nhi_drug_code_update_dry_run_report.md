# Drug Items NHI Drug Code Update Dry-run Report

## 本階段目的

本報告只針對 `drug_item_nhi_code_mapping_candidates.csv` 中 `candidate_status = strong_match` 的 32 筆，檢查是否可用來更新 `drug_items.nhi_drug_code` 相關欄位。
本階段不更新資料庫、不產生可直接執行的 UPDATE SQL。

## 前置狀態

- drug_items count: 152
- drug_diagnosis_links count: 27
- strong_match candidates: 32
- ready_to_apply: 31
- 已新增欄位：`nhi_drug_code`、`nhi_drug_code_source`、`nhi_drug_code_confidence`、`nhi_drug_code_verified_at`、`nhi_drug_code_note`

## Source 值驗證

`drug_items_nhi_drug_code_source_chk` 允許值：`prescription_ocr`、`official_nhi`、`manual`、`migrated`。

| proposed_source | ready_to_apply count |
|---|---:|
| prescription_ocr | 31 |

31 筆 `ready_to_apply` 的 `proposed_source` 皆在允許清單內。

## Metformin 主碼人工決策

使用者確認：drug_item 87 `Metformin / Metformin 寬樂醣` 的主健保碼為 `AC585341G0`。

- `AC585341G0`：納入本批 `ready_to_apply`。`proposed_source` 採保守值 `prescription_ocr`；官方確認資訊寫入 note / reason，不放入 source enum。
- `AC58534100`：不作為 `drug_items.nhi_drug_code` 主碼，後續可保留到 `drug_item_official_code_mappings` review。
- note：使用者確認「寬樂醣膜衣錠500毫克」主健保碼為 AC585341G0；此碼已可對官方 NHI staging；AC58534100 不作為 drug_items 主碼，後續保留到 mapping table review。

## dry_run_status 統計

| dry_run_status | count |
|---|---:|
| ready_to_apply | 31 |
| keep_for_mapping_table_review | 1 |
| needs_review_multiple_codes_for_drug_item | 0 |

## 32 筆 dry-run 明細

| drug_item_id | drug | proposed_nhi_code | source | official name | status | reason |
|---:|---|---|---|---|---|---|
| 47 | Pioglitazone / Glitos/Glutazone 欣促胰 | AA48333100 | prescription_ocr | GLUTAZONE TABLETS 30MG | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 64 | Propranolol / Propranolol(Inderol) 心律 | AB091021G0 | prescription_ocr | PROPRANOLOL TABLETS 10MG | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 40 | Furosemide / Lasix/Rasitol 來喜妥 | AB307491G0 | prescription_ocr | RASITOL TABLETS 40MG (FUROSEMIDE) | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 58 | Atenolol / Ateol(Tenomin)UROSIN 壓平樂 | AB388671G0 | prescription_ocr | ATEOL F.C. TABLETS 50MG "STANDARD" (ATENOLOL) | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 34 | Bisoprolol / Biso 百適歐 更換普康膜衣錠(bisoprolol) | AB45348100 | prescription_ocr | BISO F.C. TABLETS 5MG | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 6 | Glimepiride / Glimaryl 騐理蔓 | AB46766100 | prescription_ocr | GLIMARYL TABLETS 2MG (GLIMEPIRIDE) | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 60 | Irbesartan / Aprotan 壓利安 | AB57178100 | prescription_ocr | APROTAN F.C. TAB. 150MG "STANDARD" | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 86 | Acarbose / Acarbose 志樂恆 | AB57312100 | prescription_ocr | ACARBOSE F.C. TABLETS 50MG "CYH" | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 62 | Nifedipine / Adapine/Adalat 壓悅達 | AB58075100 | prescription_ocr | ADAPINE S.R.F.C. TAB. 30MG "STANDARD" | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 25 | Mefenamic acid / Ponstan/Ponstal 博疏痛 | AC19420100 | prescription_ocr | PONSTAL F.C. TABLETS 500MG "SINPHAR" (MEFENAMIC ACID) | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 7 | CARDITONIN S.C. TABLETS / CARDITONIN S.C. TABLETS 心康寧 | AC198951G0 | prescription_ocr | CARDITONIN S.C. TABLETS 25MG (DIPYRIDAMOLE) "VPP" | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 33 | Allopurinol / Synorid 欣律 | AC40106100 | prescription_ocr | SYNORID TABLETS 100MG | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 117 | Pentoxifylline / Fylin 暢循 | AC414881G0 | prescription_ocr | FYLIN RETARD F.C. TABLETS 400MG "C.H."(PENTOXIFYLLINE) | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 61 | Atorvastatin / Atorva 立舒脂(立脂妥) | AC57805100 | prescription_ocr | ATORVA F.C. TAB. 20MG "STANDARD" (ATORVASTATIN) | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 46 | Rosuvastatin / Rosustin 優脂定 | AC58316100 | prescription_ocr | ROSUSTIN FILM COATED TABLETS 5MG | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 87 | Metformin / Metformin 寬樂醣 | AC58534100 | prescription_ocr | METFORMIN F.C. TABLETS 500MG "CYH" | keep_for_mapping_table_review | 不作為 drug_items 主碼；使用者確認主碼為 AC585341G0，本碼後續保留到 drug_item_official_code_mappings review。 |
| 87 | Metformin / Metformin 寬樂醣 | AC585341G0 | prescription_ocr | METFORMIN F.C. TABLETS 500MG "CYH" | ready_to_apply | 使用者確認「寬樂醣膜衣錠500毫克」主健保碼為 AC585341G0；此碼已可對官方 NHI staging；AC58534100 不作為 drug_items 主碼，後續保留到 mapping table review。 |
| 43 | VALSARTAN 160 MGAMLODIPINE BES / EXFOPINE 安普新 | AC59821100 | prescription_ocr | EXFOPINE FILM-COATED TABLET 5/160MG | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 5 | GLIMEPIRIDE 2MG + METFORMIN 50 / Temilg F.C.  甜蜜克 | AC60134100 | prescription_ocr | TEMILG F.C. TABLETS 2/500MG | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 12 | Febuxostat / Fekuton/Fburic 服克痛 | AC61850100 | prescription_ocr | FEKUTON FILM COATED TABLETS 80MG | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 17 | Glimepiride2mg+Meformin500mg / Amaryl-M 美爾胰 | BA24876100 | prescription_ocr | AMARYL M FILM-COATED TABLETS 2/500MG | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 1 | Bisoprolol / Concor 康肯 | BC171251G0 | prescription_ocr | CONCOR 5 | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 19 | Zolpidem / Stilnox10mg 使蒂諾斯(管制藥) | BC215311G0 | prescription_ocr | STILNOX FILM-COATED SCORED TABLETS 10MG | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 21 | Amlodipine / Norvasc 脈優 | BC21571100 | prescription_ocr | NORVASC TABLETS 5MG | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 24 | Atorvastatin / Lipitor 立普妥 | BC22889100 | prescription_ocr | LIPITOR FILM-COATED TABLETS 40MG | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 69 | Rosuvastatin / Crestor 冠脂妥(阿斯) | BC24131100 | prescription_ocr | CRESTOR 10MG FILM-COATED TABLETS | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 18 | Tamsulosin / Harnalidge D 活路利淨 | BC24403100 | prescription_ocr | HARNALIDGE D TABLETS 0.2MG | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 67 | Olmesartan / Olmetec 雅脈 | BC25005100 | prescription_ocr | OLMETEC FILM COATED TABLETS 40MG | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 75 | Telmisartan / MICARDIS 必康平 | BC25446100 | prescription_ocr | TWYNSTA TABLETS 80/5MG | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 78 | Linagliptin / TRAJENTA 糖漸平 | BC25537100 | prescription_ocr | TRAJENTA 5MG FILM-COATED TABLETS | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 81 | Saxagliptin5mg+Dapagliflozin10 / Qtern 5mg/10mg 控糖穩 | BC27467100 | prescription_ocr | QTERN 5MG/10MG FILM-COATED TABLETS | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |
| 129 | Insulin degludec / Tresiba FlexTouch 諾胰保諾特筆 | KC01053216 | prescription_ocr | RYZODEG? FLEXTOUCH? | ready_to_apply | single strong_match candidate and current nhi_drug_code is NULL |

## Apply 原則建議

- 只處理 `ready_to_apply` 31 筆。
- `keep_for_mapping_table_review` 不更新 `drug_items.nhi_drug_code`，後續進 mapping table review。
- Apply 前備份整張 `drug_items`。
- 只更新 NHI code 相關 5 欄。
- 不修改 `generic_name`、`brand_name`、`aliases`。
- 不修改 `drug_diagnosis_links`。
