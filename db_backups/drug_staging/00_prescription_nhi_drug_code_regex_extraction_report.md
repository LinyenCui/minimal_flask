# 處方 OCR 健保藥品代碼 Regex 抽取報告

## 本階段目的

本階段只從既有 OCR CSV 文字欄位用 regex 抽出健保藥品代碼候選，並以唯讀 SELECT join `official_nhi_drug_payment_staging.normalized_drug_code` 驗證。未重新 OCR、未讀圖片內容、未寫資料庫、未建立 table。

## OCR CSV 來源

| source_csv | row count | columns | 可能含健保碼欄位 |
|---|---:|---|---|
| `/Users/linyancui/zhensuo/workbench/prescription_photos/ocr_raw/prescription_examples_raw.csv` | 30 | source_filename, working_filename, patient_name_detected, visit_date_detected, diagnosis_codes_raw, diagnosis_names_raw, drug_names_raw, generic_names_raw, brand_names_raw, dosage_raw, days_raw, notes_raw, ocr_confidence, needs_manual_review, review_reason | diagnosis_codes_raw, diagnosis_names_raw, drug_names_raw, generic_names_raw, brand_names_raw, dosage_raw, days_raw, notes_raw |
| `/Users/linyancui/zhensuo/workbench/prescription_photos/ocr_raw/prescription_examples_gemini.csv` | 30 | source_filename, patient_name_detected, visit_date_detected, diagnosis_codes_raw, diagnosis_names_raw, drug_names_raw, generic_names_raw, brand_names_raw, dosage_raw, days_raw, notes_raw, ocr_confidence, needs_manual_review, review_reason | diagnosis_codes_raw, diagnosis_names_raw, drug_names_raw, generic_names_raw, brand_names_raw, dosage_raw, days_raw, notes_raw |

## Regex

- 初步抽取：`[A-Z]{1,2}[A-Z0-9][0-9A-Z]{6,8}`
- 本批保留長度 10 的候選，並標準化為大寫英數。
- 若可在官方 NHI staging exact join，confidence 調為 high；否則保留 medium/low 供人工 review。

## 統計

- 抽出總候選 occurrences：235
- unique 健保碼數：66
- 可 join 官方 NHI 的 unique 碼數：33
- 無法 join 官方 NHI 的 unique 碼數：33
- DB target：`localhost:5432/dispatch_db` user `postgres`

## 每張照片抽到幾個碼

| source_photo | occurrences | unique codes |
|---|---:|---:|
| `IMG_7202.JPG` | 5 | 5 |
| `IMG_7203.jpeg` | 13 | 7 |
| `IMG_7282.jpeg` | 3 | 3 |
| `IMG_7283.JPG` | 1 | 1 |
| `IMG_7284.JPG` | 8 | 5 |
| `IMG_7285.JPG` | 10 | 5 |
| `IMG_7290.jpeg` | 15 | 6 |
| `IMG_7364.jpeg` | 8 | 5 |
| `IMG_7367.JPG` | 10 | 5 |
| `IMG_7391.jpeg` | 9 | 3 |
| `IMG_7394.jpeg` | 10 | 6 |
| `IMG_7396.JPG` | 10 | 8 |
| `IMG_7397.JPG` | 7 | 4 |
| `IMG_7461.JPG` | 1 | 1 |
| `IMG_7462.JPG` | 6 | 3 |
| `IMG_7464.jpeg` | 12 | 6 |
| `IMG_7508.JPG` | 3 | 3 |
| `IMG_7509.JPG` | 6 | 4 |
| `IMG_7510.jpeg` | 12 | 6 |
| `IMG_7562.JPG` | 3 | 1 |
| `IMG_7564.jpeg` | 8 | 6 |
| `IMG_7624.jpeg` | 6 | 5 |
| `IMG_7627.JPG` | 6 | 4 |
| `IMG_7655.JPG` | 6 | 5 |
| `IMG_7656.JPG` | 4 | 2 |
| `IMG_7658.jpeg` | 17 | 8 |
| `IMG_7660.JPG` | 6 | 4 |
| `IMG_7670.JPG` | 7 | 4 |
| `IMG_7675.JPG` | 14 | 7 |
| `IMG_7721.jpeg` | 9 | 6 |

## 官方 NHI join 成功碼

| code | occurrences | official_match_count | official_drug_name_zh | official_drug_name_en | official_ingredient | official_atc_code | effective_start | effective_end |
|---|---:|---:|---|---|---|---|---|---|
| AA48333100 | 2 | 9 | 欣促胰錠30毫克 | Glutazone Tablets 30mg | PIOGLITAZONE 30 MG | A10BG03 | 2025-04-01 | 2910-12-31 |
| AB091021G0 | 2 | 1 | "生達"心律錠10毫克 | PROPRANOLOL TABLETS 10MG | PROPRANOLOL HCL 10 MG | C07AA05 | 2013-12-01 | 2910-12-31 |
| AB307491G0 | 2 | 1 | 來喜妥錠４０毫克（服樂泄麥） | RASITOL TABLETS 40MG (FUROSEMIDE) | FUROSEMIDE 40 MG | C03CA01 | 2012-02-01 | 2910-12-31 |
| AB388671G0 | 3 | 1 | "生達"壓平樂膜衣錠５０毫克（阿廷諾） | ATEOL F.C. TABLETS 50MG "STANDARD" (ATENOLOL) | ATENOLOL 50 MG | C07AB03 | 2012-12-01 | 2910-12-31 |
| AB45348100 | 1 | 11 | 百適歐膜衣錠５公絲 | BISO F.C. TABLETS 5MG | BISOPROLOL FUMARATE 5 MG | C07AB07 | 2026-04-01 | 2910-12-31 |
| AB46766100 | 1 | 10 | "信東" 革理蔓錠２毫克 | GLIMARYL TABLETS 2MG (GLIMEPIRIDE) | GLIMEPIRIDE 2 MG | A10BB12 | 2026-04-01 | 2910-12-31 |
| AB57178100 | 1 | 10 | "生達"壓立安膜衣錠150毫克 | Aprotan F.C. Tab. 150mg "Standard" | IRBESARTAN 150 MG | C09CA04 | 2024-04-01 | 2910-12-31 |
| AB57312100 | 3 | 13 | 志樂恆膜衣錠50毫克 | Acarbose F.C. Tablets 50mg "CYH" | ACARBOSE 50 MG | A10BF01 | 2026-04-01 | 2910-12-31 |
| AB58075100 | 4 | 9 | "生達"壓悅達持續性藥效錠30毫克 | Adapine S.R.F.C. Tab. 30mg "Standard" | NIFEDIPINE 30 MG | C08CA05 | 2026-04-01 | 2910-12-31 |
| AC19420100 | 2 | 2 | "杏輝" 痛疏達膜衣錠500毫克（每非那） | PONSTAL F.C. TABLETS 500MG "SINPHAR" (MEFENAMIC ACID) | MEFENAMIC ACID 500 MG | M01AG01 | 2011-12-01 | 2910-12-31 |
| AC198951G0 | 1 | 1 | "榮民"心康寧糖衣錠25毫克(待匹力達) | CARDITONIN S.C. TABLETS 25MG (DIPYRIDAMOLE) "VPP" | DIPYRIDAMOLE 25 MG | B01AC07 | 2014-08-01 | 2910-12-31 |
| AC40106100 | 2 | 1 | 欣律錠100毫克 | SYNORID TABLETS 100MG | ALLOPURINOL 100 MG | M04AA01 | 2012-02-01 | 2910-12-31 |
| AC414881G0 | 4 | 1 | "正和"暢循持續性膜衣錠400毫克（配妥西菲林） | FYLIN RETARD F.C. TABLETS 400MG "C.H."(PENTOXIFYLLINE) | PENTOXIFYLLINE 400 MG | C04AD03 | 2019-02-01 | 2910-12-31 |
| AC415191G0 | 6 | 1 | "強生" 福安源錠０．２５公絲（氟二氮平） | FLUPINE TABLETS 0.25MG (FLUDIAZEPAM) "JOHNSON" | FLUDIAZEPAM 250 MCG | N05BA17 | 2022-01-01 | 2910-12-31 |
| AC57805100 | 9 | 12 | "生達" 立舒脂膜衣錠20毫克 | Atorva F.C. Tab. 20mg "Standard" (Atorvastatin) | ATORVASTATIN (CALCIUM) 20 MG | C10AA05 | 2026-04-01 | 2910-12-31 |
| AC58316100 | 2 | 10 | 優脂定膜衣錠5毫克 | Rosustin Film Coated Tablets 5mg | ROSUVASTATIN CALCIUM 5 MG | C10AA07 | 2025-04-01 | 2910-12-31 |
| AC58534100 | 2 | 1 | 寬樂醣膜衣錠500毫克 | Metformin F.C. Tablets 500mg "CYH" | METFORMIN HCL 500 MG | A10BA02 | 2015-08-01 | 2910-12-31 |
| AC585341G0 | 6 | 1 | 寬樂醣膜衣錠500毫克 | Metformin F.C. Tablets 500mg "CYH" | METFORMIN HCL 500 MG | A10BA02 | 2015-12-01 | 2910-12-31 |
| AC59821100 | 2 | 7 | 安普新膜衣錠5/160毫克 | Exfopine Film-Coated Tablet 5/160mg | VALSARTAN 160 MG+AMLODIPINE BESYLATE 5 MG | C09DB01 | 2025-09-01 | 2910-12-31 |
| AC60134100 | 10 | 7 | 甜蜜克膜衣錠2/500毫克 | Temilg F.C. Tablets 2/500mg | GLIMEPIRIDE 2 MG+METFORMIN HCL 500 MG | A10BD02 | 2026-04-01 | 2910-12-31 |
| AC61850100 | 7 | 3 | 服克痛膜衣錠80毫克 | Fekuton Film Coated Tablets 80mg | Febuxostat 80 MG | M04AA03 | 2026-04-01 | 2910-12-31 |
| BA24876100 | 1 | 10 | 美爾胰膜衣錠 2/500 毫克 | Amaryl M Film-coated Tablets 2/500mg | GLIMEPIRIDE 2 MG+METFORMIN HCL 500 MG | A10BD02 | 2026-04-01 | 2910-12-31 |
| BC171251G0 | 3 | 1 | 康肯５毫克 | CONCOR 5 | BISOPROLOL FUMARATE 5 MG | C07AB07 | 2023-04-01 | 2910-12-31 |
| BC215311G0 | 1 | 1 | 使蒂諾斯膜衣錠１０毫克 | STILNOX FILM-COATED SCORED TABLETS 10MG | ZOLPIDEM TARTRATE 10 MG | N05CF02 | 2019-06-01 | 2910-12-31 |
| BC21571100 | 11 | 11 | 脈優錠５毫克 | NORVASC TABLETS 5MG | AMLODIPINE (BESYLATE) 5 MG | C08CA01 | 2025-04-01 | 2910-12-31 |
| BC22889100 | 4 | 13 | 立普妥　膜衣錠４０毫克 | LIPITOR FILM-COATED TABLETS 40MG | ATORVASTATIN (CALCIUM) 40 MG | C10AA05 | 2026-04-01 | 2910-12-31 |
| BC24131100 | 3 | 10 | 冠脂妥膜衣錠10毫克 | CRESTOR 10MG FILM-COATED TABLETS | ROSUVASTATIN CALCIUM 10 MG | C10AA07 | 2026-04-01 | 2910-12-31 |
| BC24403100 | 1 | 10 | 活路利淨D 持續釋放口溶錠0.2毫克 | Harnalidge D tablets 0.2mg | TAMSULOSIN HCL .2 MG | G04CA02 | 2024-04-01 | 2910-12-31 |
| BC25005100 | 2 | 10 | 德國第一三共雅脈 膜衣錠 40 毫克 | Olmetec film coated tablets 40mg | OLMESARTAN MEDOXOMIL 40 MG | C09CA08 | 2024-04-01 | 2910-12-31 |
| BC25446100 | 1 | 12 | 倍必康平錠80/5毫克 | Twynsta Tablets 80/5mg | TELMISARTAN 80 MG+AMLODIPINE (BESYLATE) 5 MG | C09DB04 | 2025-04-01 | 2910-12-31 |
| BC25537100 | 1 | 15 | 糖漸平膜衣錠 5毫克 | Trajenta 5mg Film-Coated Tablets | LINAGLIPTIN 5 MG | A10BH05 | 2025-06-01 | 2910-12-31 |
| BC27467100 | 1 | 6 | 控糖穩膜衣錠5毫克/10毫克 | Qtern 5mg/10mg Film-Coated Tablets | DAPAGLIFLOZIN 10 MG+SAXAGLIPTIN 5 MG | A10BD21 | 2026-04-01 | 2910-12-31 |
| KC01053216 | 1 | 3 | 諾胰得 諾特筆 | Ryzodeg? FlexTouch? | insulin degludec 70 U/ML (UNIT+INSULIN ASPART 30 U/ML (UNIT/ML) | A10AD06 | 2025-04-01 | 2910-12-31 |

## 無法 join 官方 NHI 的碼

| code | occurrences | first source_photo | first nearby_text |
|---|---:|---|---|
| AB230371GO | 3 | IMG_7203.jpeg | TWYNSTA TABLETS 80/5; AB230371GO CARDOLOL TABLETS 10M; BISO F.C TABLETS 5 M; FAL |
| AC414881GO | 2 | IMG_7464.jpeg | xPEITAON S.C. TABLETS; Fili-ZF : METFORMIN HCL; AC414881GO BYLIN RETARD F.C. TA; AC58316100 ROSUSTIN FILM |
| AC484721GO | 1 | IMG_7203.jpeg | L TABLETS 10M; AB45348100 BISO F.C TABLETS 5 M; AC484721GO FALLEP TABLETS 2MG(? |
| AC4D106100 | 2 | IMG_7564.jpeg | 4100 Temilg F.C. Tablels; HE10:38: GLIMEPIRIDE; AC4D106100 Synorid TABLETS 100M; AB57178100 APROTAN F.C. T |
| AC578051D0 | 2 | IMG_7627.JPG | d; FYLIN RETARD F.C. TA; APEITAON S.C. TABLETS; AC578051D0 ATORVA F.C.; IRD6 :ATORVASTATIN (CALCIUM); BC21 |
| AC57805L00 | 2 | IMG_7670.JPG | L00 METROPMIN F.C. TABLE; #LD-3M:METFORMIN HCL; AC57805L00 ATORVA F.C. TAB. |
| AC585341GD | 1 | IMG_7660.JPG | F.C. TAB. 20M; AB58075100 DOXABEN XL TABLETS 4; AC585341GD EXED 3TP: METFORMIN HCL; METFUNNIN r.C. IAOLD A |
| AC585341GO | 1 | IMG_7655.JPG | 0-819: ASPIRIN; BC21571100 NORVASC TABLETS 5MG; AC585341GO METFORMINE.C.; TABLE; ATORYA F.C.; TAB. |
| AC58534L00 | 2 | IMG_7670.JPG | RD 6N :ASPIRIN; SC21571100 NORVASC TABLETS 5MG; AC58534L00 METROPMIN F.C. TABLE; #LD-3M:METFORMIN HCL; AC5 |
| ACS7805100 | 2 | IMG_7721.jpeg | BLE; NORVASC TABLETS 5MG; ATEOL F.C. TABLETS 5; ACS7805100 ATORVA E.C. TAB. 2000; AC585341G0 METFORMIN F.C |
| AMLODIPINE | 14 | IMG_7397.JPG | 1213 M109; BIBL: 0006 7454:02 P577; FX.LD-Z19 : AMLODIPINE (BESYLATE) |
| BC171251GO | 4 | IMG_7397.JPG | icosu 5mg(dulcolax); ATORYA F.C.; TAB.; Coated; BC171251GO CONCOR 5 |
| BC2157L100 | 4 | IMG_7394.jpeg | 251G0 CONCOR 5; EL10 :217 :BISOPROLOL FUMARATE; BC2157L100 NORYASC TABLETS 5MG; xMicosu 5mg (dulcolax); AT |
| BC2413L100 | 2 | IMG_7285.JPG | M; ONGLYZA 5MG; BC21571100 NORVASC TABLETS SMG; BC2413L100 CRESTOR LOMO FILM-CO; xSena( sennoside) 12mg; A |
| BISOPROLOL | 28 | IMG_7203.jpeg | ETS 10M; BISO E.C TABLETS 5 M 1.00 QD; FX/O-ZM: BISOPROLOL FUMARATE; BC25446100 TWYNSTA TABLETS 80/5; WONT |
| CARDITONIN | 6 | IMG_7367.JPG | CARDITONIN S.C. TABL; Fekuton Film Coated; FYLIN RETARD F. |
| CARVEDILOL | 1 | IMG_7461.JPG | CARVEDILOL, SAXAGLIPTIN, VALSARTAN, PENTOXIFYLLINE, LEVOTH |
| CLONAZEPAM | 1 | IMG_7290.jpeg | IDE, ATORVASTATIN (CALCIUM), ZOLPIDEM TARTRATE, CLONAZEPAM |
| CONTROLLED | 2 | IMG_7203.jpeg | pidogrel Sandoz 7, TWYNSTA TABLETS 80/5, SORDUR CONTROLLED-RE, CARDOLOL TABLETS 10M, BISO F.C TABLETS 5 M, |
| DIPHENIDOL | 8 | IMG_7658.jpeg | ARATE; FX10-Z*M : OLMESARTAN MEDOXOMIL; FX BM : DIPHENIDOL HCL |
| FEBUXOSTAT | 6 | IMG_7282.jpeg | Febuxostat, ATORVASTATIN (CALCIUM) |
| FOSINOPRIL | 2 | IMG_7627.JPG | FOSINOPRIL SODIUM, ASPIRIN, AMLODIPINE (BESYLATE), METFORM |
| FUROSEMIDE | 3 | IMG_7364.jpeg | N HCL; E*laB: ATORVASTATIN (CALCIUM); FRID-ZAF: FUROSEMIDE |
| HARNALIDGE | 6 | IMG_7290.jpeg | ADAPINE S.R.F.C. TAB; DIOVAN FILM-COATED T; Harnalidge D tablets; WECOLI TABLETS 25MG; STILNOX FILM-CO |
| IRBESARTAN | 1 | IMG_7564.jpeg | GLIMEPIRIDE, ALLOPURINOL, IRBESARTAN, DAPAGLIFLOZIN, ATENOLOL, ROSUVASTATIN CALCIUM |
| ISOSORBIDE | 1 | IMG_7203.jpeg | CLOPIDOGREL, TELMISARTAN, ISOSORBIDE 5-MONONITRATE, TRAMADOL HCL, PROPRANOLOL HCL, B |
| KC0L053216 | 1 | IMG_7510.jpeg | eg? FlexTouch?; BC25005100 OLMETEC FILM COATED; KC0L053216 Ryzodeg? FlexTouch? |
| LOVASTATIN | 2 | IMG_7658.jpeg | UMARATE, INDOMETHACIN, AZULENE, DIPHENIDOL HCL, LOVASTATIN, OLMESARTAN MEDOXOMIL |
| METFORMINE | 1 | IMG_7655.JPG | RIN; BC21571100 NORVASC TABLETS 5MG; AC585341GO METFORMINE.C.; TABLE; ATORYA F.C.; TAB. |
| NIFEDIPINE | 11 | IMG_7290.jpeg | APINE S.R.E.C. TAB 1.00 BID x28 56.0; FELD 2fM: NIFEDIPINE; DIOVAN FILM-COATED T 1.00; BC24403100 Harnalid |
| OLMESARTAN | 6 | IMG_7510.jpeg | IPINE; BC25005100 OLMETEC FILM COATED; Fel ZAF: OLMESARTAN MEDOXOMIL; BC171251GO CONCOR 5; E2 ta IBM : BIS |
| SC21571100 | 2 | IMG_7670.JPG | ; BOKEY ENTERIC-MICROE 1,00 QD; RD 6N :ASPIRIN; SC21571100 NORVASC TABLETS 5MG; AC58534L00 METROPMIN F.C. |
| TAMSULOSIN | 3 | IMG_7290.jpeg | M: 110 E785 F39; EN 2600: 110 E785 E39; F10:29: TAMSULOSIN HCL |

## 風險點

- OCR 可能誤讀 `0/O`、`1/I/L`、`G/6`，例如 `BC171251GO` 需人工確認是否應為 `BC171251G0`。
- 健保碼與藥名同列關係目前仍是文字片段，尚未可靠切成每列藥品。
- 同照片多列順序未必可靠，尤其 OCR 可能將上下列混在同一欄位。
- official NHI table 是給付資料，後續需留意有效起迄日與歷史列。
- 無法 join 的碼可能是 OCR 錯誤、舊碼、或抽到非健保藥品碼。

## 下一步建議

1. 先人工 review `prescription_nhi_drug_code_regex_candidates.csv`，尤其無法 join 的碼與 OCR 常見誤讀。
2. 對可 join 的碼產生 prescription row-level review report，列出 official NHI 品名/成分/規格。
3. 人工確認後，再匯入 `prescription_nhi_drug_code_candidates` staging。
4. 後續再產生 `drug_items` 對 `drug_item_official_code_mappings` 的候選，不要直接寫 `drug_items.aliases`。

## 輸出

- `db_backups/drug_staging/prescription_nhi_drug_code_regex_candidates.csv`

## 安全聲明

本報告未重新 OCR、未讀圖片內容、未寫資料庫、未建立 table、未修改 `drug_items` / official staging / `drug_diagnosis_links`。
