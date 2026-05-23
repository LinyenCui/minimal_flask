# Drug Item NHI Code Mapping Candidate Report

## 本階段目的

本報告唯讀分析 `prescription_nhi_drug_code_candidates`、`official_nhi_drug_payment_staging` 與 `drug_items`，產生 `drug_item_id ↔ NHI code` 候選。未修改資料庫、未建立 mapping table、未產生 apply SQL。

## 資料來源

- `prescription_nhi_drug_code_candidates`：OCR occurrence-level 健保藥品代碼候選 235 筆。
- `official_nhi_drug_payment_staging`：健保署藥品給付官方 staging，依 normalized_drug_code 選目前有效或最新有效列。
- `drug_items`：現有正式藥品概念表 152 筆。

## Prescription Candidate 統計

- total rows: 235
- unique effective_nhi_drug_code count: 33
- drug_diagnosis_links current count: 27

### review_status

| review_status | count |
|---|---:|
| auto_accepted | 119 |
| rejected | 102 |
| needs_review | 14 |
| pending | 0 |

### official_join_status

| official_join_status | count |
|---|---:|
| matched | 102 |
| corrected_matched | 17 |
| false_positive | 102 |
| no_match | 14 |

### 每張照片 occurrence count

| source_photo | count |
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

## Mapping Candidate 統計

| candidate_status | unique NHI code count |
|---|---:|
| strong_match | 32 |
| no_drug_item_match | 1 |

## 比對規則

- `strong_match` / `likely_match` 只依 official NHI 藥品名稱、成分、中文名與 `drug_items` 的 generic/brand/aliases 判斷。
- 商品名 token（例如 Temilg、Qtern）出現在 official NHI 英文名時，視為重要證據；複方藥避免只配到其中一個單方成分。
- `nearby_text` 僅保留作人工 review 參考，不作為 strong match 的主要依據，避免同一照片相鄰藥品互相污染。

## 候選分類說明

- `strong_match`：官方成分/名稱與 drug_items 的 generic/brand/alias 明確一致。
- `likely_match`：官方欄位大致一致，但仍建議人工抽查後再建立 mapping。
- `ambiguous`：多個 drug_items 可能對應，需人工選。
- `no_drug_item_match`：官方 NHI code 找不到對應 drug_items，暫不建 mapping。
- `needs_review`：候選藥品已有診斷關聯或語意風險較高，需人工 review。

## 候選摘要

| NHI code | official name | ingredient | candidate drug_item | status | confidence | reason |
|---|---|---|---|---|---|---|
| AA48333100 | GLUTAZONE TABLETS 30MG | PIOGLITAZONE 30 MG | 47 Pioglitazone / Glitos/Glutazone 欣促胰 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: glutazone; official to… |
| AB091021G0 | PROPRANOLOL TABLETS 10MG | PROPRANOLOL HCL 10 MG | 64 Propranolol / Propranolol(Inderol) 心律 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: propranolol; official … |
| AB307491G0 | RASITOL TABLETS 40MG (FUROSEMIDE) | FUROSEMIDE 40 MG | 40 Furosemide / Lasix/Rasitol 來喜妥 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: rasitol; official toke… |
| AB388671G0 | ATEOL F.C. TABLETS 50MG "STANDARD" (ATENOLOL) | ATENOLOL 50 MG | 58 Atenolol / Ateol(Tenomin)UROSIN 壓平樂 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: ateol; official token … |
| AB45348100 | BISO F.C. TABLETS 5MG | BISOPROLOL FUMARATE 5 MG | 34 Bisoprolol / Biso 百適歐 更換普康膜衣錠(bisoprolol) | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: biso; official token h… |
| AB46766100 | GLIMARYL TABLETS 2MG (GLIMEPIRIDE) | GLIMEPIRIDE 2 MG | 6 Glimepiride / Glimaryl 騐理蔓 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: glimaryl; official tok… |
| AB57178100 | APROTAN F.C. TAB. 150MG "STANDARD" | IRBESARTAN 150 MG | 60 Irbesartan / Aprotan 壓利安 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: aprotan; official toke… |
| AB57312100 | ACARBOSE F.C. TABLETS 50MG "CYH" | ACARBOSE 50 MG | 86 Acarbose / Acarbose 志樂恆 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: acarbose; official tok… |
| AB58075100 | ADAPINE S.R.F.C. TAB. 30MG "STANDARD" | NIFEDIPINE 30 MG | 62 Nifedipine / Adapine/Adalat 壓悅達 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: adapine; official toke… |
| AC19420100 | PONSTAL F.C. TABLETS 500MG "SINPHAR" (MEFENAMIC ACID) | MEFENAMIC ACID 500 MG | 25 Mefenamic acid / Ponstan/Ponstal 博疏痛 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: ponstal; official toke… |
| AC198951G0 | CARDITONIN S.C. TABLETS 25MG (DIPYRIDAMOLE) "VPP" | DIPYRIDAMOLE 25 MG | 7 CARDITONIN S.C. TABLETS / CARDITONIN S.C. TABLETS 心康寧 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: carditonin; official t… |
| AC40106100 | SYNORID TABLETS 100MG | ALLOPURINOL 100 MG | 33 Allopurinol / Synorid 欣律 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: synorid; official toke… |
| AC414881G0 | FYLIN RETARD F.C. TABLETS 400MG "C.H."(PENTOXIFYLLINE) | PENTOXIFYLLINE 400 MG | 117 Pentoxifylline / Fylin 暢循 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: fylin; official token … |
| AC57805100 | ATORVA F.C. TAB. 20MG "STANDARD" (ATORVASTATIN) | ATORVASTATIN (CALCIUM) 20 MG | 61 Atorvastatin / Atorva 立舒脂(立脂妥) | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: atorva; official token… |
| AC58316100 | ROSUSTIN FILM COATED TABLETS 5MG | ROSUVASTATIN CALCIUM 5 MG | 46 Rosuvastatin / Rosustin 優脂定 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: rosustin; official tok… |
| AC58534100 | METFORMIN F.C. TABLETS 500MG "CYH" | METFORMIN HCL 500 MG | 87 Metformin / Metformin 寬樂醣 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: metformin; official to… |
| AC585341G0 | METFORMIN F.C. TABLETS 500MG "CYH" | METFORMIN HCL 500 MG | 87 Metformin / Metformin 寬樂醣 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: metformin; official to… |
| AC59821100 | EXFOPINE FILM-COATED TABLET 5/160MG | VALSARTAN 160 MG+AMLODIPINE BESYLATE 5 MG | 43 VALSARTAN 160 MGAMLODIPINE BES / EXFOPINE 安普新 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: exfopine; official tok… |
| AC60134100 | TEMILG F.C. TABLETS 2/500MG | GLIMEPIRIDE 2 MG+METFORMIN HCL 500 MG | 5 GLIMEPIRIDE 2MG + METFORMIN 50 / Temilg F.C.  甜蜜克 | strong_match | high | official brand token hits: temilg; official token hits: glimepiride, metformin; official Chinese te… |
| AC61850100 | FEKUTON FILM COATED TABLETS 80MG | FEBUXOSTAT 80 MG | 12 Febuxostat / Fekuton/Fburic 服克痛 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: fekuton; official toke… |
| BA24876100 | AMARYL M FILM-COATED TABLETS 2/500MG | GLIMEPIRIDE 2 MG+METFORMIN HCL 500 MG | 17 Glimepiride2mg+Meformin500mg / Amaryl-M 美爾胰 | strong_match | high | official brand token hits: amaryl; official token hits: glimepiride2mg; official Chinese term hits:… |
| BC171251G0 | CONCOR 5 | BISOPROLOL FUMARATE 5 MG | 1 Bisoprolol / Concor 康肯 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: concor; official token… |
| BC215311G0 | STILNOX FILM-COATED SCORED TABLETS 10MG | ZOLPIDEM TARTRATE 10 MG | 19 Zolpidem / Stilnox10mg 使蒂諾斯(管制藥) | strong_match | high | generic_name appears in official ingredient/name; official token hits: zolpidem; official Chinese t… |
| BC21571100 | NORVASC TABLETS 5MG | AMLODIPINE (BESYLATE) 5 MG | 21 Amlodipine / Norvasc 脈優 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: norvasc; official toke… |
| BC22889100 | LIPITOR FILM-COATED TABLETS 40MG | ATORVASTATIN (CALCIUM) 40 MG | 24 Atorvastatin / Lipitor 立普妥 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: lipitor; official toke… |
| BC24131100 | CRESTOR 10MG FILM-COATED TABLETS | ROSUVASTATIN CALCIUM 10 MG | 69 Rosuvastatin / Crestor 冠脂妥(阿斯) | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: crestor; official toke… |
| BC24403100 | HARNALIDGE D TABLETS 0.2MG | TAMSULOSIN HCL .2 MG | 18 Tamsulosin / Harnalidge D 活路利淨 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: harnalidge; official t… |
| BC25005100 | OLMETEC FILM COATED TABLETS 40MG | OLMESARTAN MEDOXOMIL 40 MG | 67 Olmesartan / Olmetec 雅脈 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: olmetec; official toke… |
| BC25446100 | TWYNSTA TABLETS 80/5MG | TELMISARTAN 80 MG+AMLODIPINE (BESYLATE) 5 MG | 75 Telmisartan / MICARDIS 必康平 | strong_match | high | generic_name appears in official ingredient/name; official token hits: telmisartan; official Chines… |
| BC25537100 | TRAJENTA 5MG FILM-COATED TABLETS | LINAGLIPTIN 5 MG | 78 Linagliptin / TRAJENTA 糖漸平 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: trajenta; official tok… |
| BC27467100 | QTERN 5MG/10MG FILM-COATED TABLETS | DAPAGLIFLOZIN 10 MG+SAXAGLIPTIN 5 MG | 81 Saxagliptin5mg+Dapagliflozin10 / Qtern 5mg/10mg 控糖穩 | strong_match | high | official brand token hits: 10mg, qtern; official token hits: dapagliflozin10, saxagliptin5mg; offic… |
| KC01053216 | RYZODEG? FLEXTOUCH? | INSULIN DEGLUDEC 70 U/ML (UNIT+INSULIN ASPART 30 U/ML (UNIT… | 129 Insulin degludec / Tresiba FlexTouch 諾胰保諾特筆 | strong_match | high | generic_name appears in official ingredient/name; official brand token hits: flextouch; official to… |
| AC415191G0 | FLUPINE TABLETS 0.25MG (FLUDIAZEPAM) "JOHNSON" | FLUDIAZEPAM 250 MCG |  | no_drug_item_match | low | No drug_items generic/brand/alias matched official NHI name or ingredient. |

## 高風險與注意事項

- NHI official 是歷史給付列，同一 code 可能有多筆；本報告優先選目前有效或最新有效列。
- OCR nearby_text 有助於人工判斷，但不可單獨作為正式 mapping 依據。
- `no_drug_item_match` 不代表 NHI code 錯誤，可能代表目前 `drug_items` 尚未建立該藥品概念。
- 後續應採 staging → review → approved-only apply，建立 `drug_item_official_code_mappings`，不要直接把健保碼塞入 `drug_items.aliases`。

## 下一步建議

1. 先人工 review `strong_match` 與 `likely_match`，產生 approved mapping decisions CSV。
2. 對 `ambiguous` 與 `needs_review` 回看原照片或 nearby OCR text。
3. 對 `no_drug_item_match` 判斷是否需新增 drug_items 或只保留處方 occurrence reference。
4. 再建立 `drug_item_official_code_mappings` apply 腳本，只寫 approved mappings。

## 安全聲明

本報告不修改資料庫、不修改 `drug_items`、不修改 `drug_diagnosis_links`、不修改 official staging、不建立 mapping table、不產生 UPDATE SQL。
