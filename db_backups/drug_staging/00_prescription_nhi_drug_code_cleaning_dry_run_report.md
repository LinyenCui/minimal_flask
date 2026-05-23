# 處方健保藥品碼候選清洗與 OCR 誤讀校正 Dry-run Report

## 本階段目的

本報告針對 regex 抽出的健保藥品碼候選做 dry-run 清洗與 OCR 誤讀校正。只讀取候選 CSV，並以唯讀 SELECT 查詢 official NHI staging；未修改原候選 CSV、未寫資料庫、未建立 table。

## 原抽取結果摘要

- occurrences：235
- unique 候選碼：66
- 原本可 exact join official NHI：33
- 原本無法 exact join official NHI：33

## Strict Regex 建議

- 建議 strict regex：`^[A-Z]{2}[0-9][0-9A-Z]{5}[0-9][0-9A-Z]$`
- 理由：本批已成功 join 的健保碼多為 10 碼、前兩碼英文字母、第 3 碼多為數字、第 9 碼多為數字。
- 這個規則可排除 `AMLODIPINE`、`BISOPROLOL`、`METFORMINE` 等純英文藥名。
- 仍需保留 review，因 OCR 會把 `0/O`、`1/I/L`、`G/6` 混淆。

## 分類統計

| classification | count |
|---|---:|
| false_positive_word | 18 |
| likely_ocr_confusion | 8 |
| needs_manual_review | 6 |
| no_official_match | 1 |
| official_match | 33 |

## False positive word 清單

| code | occurrences | reason |
|---|---:|---|
| AMLODIPINE | 14 | all-alpha token or known drug word captured by broad regex |
| BISOPROLOL | 28 | all-alpha token or known drug word captured by broad regex |
| CARDITONIN | 6 | all-alpha token or known drug word captured by broad regex |
| CARVEDILOL | 1 | all-alpha token or known drug word captured by broad regex |
| CLONAZEPAM | 1 | all-alpha token or known drug word captured by broad regex |
| CONTROLLED | 2 | all-alpha token or known drug word captured by broad regex |
| DIPHENIDOL | 8 | all-alpha token or known drug word captured by broad regex |
| FEBUXOSTAT | 6 | all-alpha token or known drug word captured by broad regex |
| FOSINOPRIL | 2 | all-alpha token or known drug word captured by broad regex |
| FUROSEMIDE | 3 | all-alpha token or known drug word captured by broad regex |
| HARNALIDGE | 6 | all-alpha token or known drug word captured by broad regex |
| IRBESARTAN | 1 | all-alpha token or known drug word captured by broad regex |
| ISOSORBIDE | 1 | all-alpha token or known drug word captured by broad regex |
| LOVASTATIN | 2 | all-alpha token or known drug word captured by broad regex |
| METFORMINE | 1 | all-alpha token or known drug word captured by broad regex |
| NIFEDIPINE | 11 | all-alpha token or known drug word captured by broad regex |
| OLMESARTAN | 6 | all-alpha token or known drug word captured by broad regex |
| TAMSULOSIN | 3 | all-alpha token or known drug word captured by broad regex |

## Likely OCR confusion 清單

| original | proposed_corrected_code | occurrences | official zh | official en | reason |
|---|---|---:|---|---|---|
| AC4D106100 | AC40106100 | 2 | 欣律錠100毫克 | SYNORID TABLETS 100MG | OCR ambiguity corrected AC4D106100 -> AC40106100 |
| AC578051D0 | AC57805100 | 2 | "生達" 立舒脂膜衣錠20毫克 | Atorva F.C. Tab. 20mg "Standard" (Atorvastatin) | OCR ambiguity corrected AC578051D0 -> AC57805100 |
| AC57805L00 | AC57805100 | 2 | "生達" 立舒脂膜衣錠20毫克 | Atorva F.C. Tab. 20mg "Standard" (Atorvastatin) | OCR ambiguity corrected AC57805L00 -> AC57805100 |
| AC58534L00 | AC58534100 | 2 | 寬樂醣膜衣錠500毫克 | Metformin F.C. Tablets 500mg "CYH" | OCR ambiguity corrected AC58534L00 -> AC58534100 |
| ACS7805100 | AC57805100 | 2 | "生達" 立舒脂膜衣錠20毫克 | Atorva F.C. Tab. 20mg "Standard" (Atorvastatin) | OCR ambiguity corrected ACS7805100 -> AC57805100 |
| BC2157L100 | BC21571100 | 4 | 脈優錠５毫克 | NORVASC TABLETS 5MG | OCR ambiguity corrected BC2157L100 -> BC21571100 |
| BC2413L100 | BC24131100 | 2 | 冠脂妥膜衣錠10毫克 | CRESTOR 10MG FILM-COATED TABLETS | OCR ambiguity corrected BC2413L100 -> BC24131100 |
| KC0L053216 | KC01053216 | 1 | 諾胰得 諾特筆 | Ryzodeg? FlexTouch? | OCR ambiguity corrected KC0L053216 -> KC01053216 |

## 校正後可 join 的碼

| original | corrected | official zh | official en | ingredient |
|---|---|---|---|---|
| AC4D106100 | AC40106100 | 欣律錠100毫克 | SYNORID TABLETS 100MG | ALLOPURINOL 100 MG |
| AC578051D0 | AC57805100 | "生達" 立舒脂膜衣錠20毫克 | Atorva F.C. Tab. 20mg "Standard" (Atorvastatin) | ATORVASTATIN (CALCIUM) 20 MG |
| AC57805L00 | AC57805100 | "生達" 立舒脂膜衣錠20毫克 | Atorva F.C. Tab. 20mg "Standard" (Atorvastatin) | ATORVASTATIN (CALCIUM) 20 MG |
| AC58534L00 | AC58534100 | 寬樂醣膜衣錠500毫克 | Metformin F.C. Tablets 500mg "CYH" | METFORMIN HCL 500 MG |
| ACS7805100 | AC57805100 | "生達" 立舒脂膜衣錠20毫克 | Atorva F.C. Tab. 20mg "Standard" (Atorvastatin) | ATORVASTATIN (CALCIUM) 20 MG |
| BC2157L100 | BC21571100 | 脈優錠５毫克 | NORVASC TABLETS 5MG | AMLODIPINE (BESYLATE) 5 MG |
| BC2413L100 | BC24131100 | 冠脂妥膜衣錠10毫克 | CRESTOR 10MG FILM-COATED TABLETS | ROSUVASTATIN CALCIUM 10 MG |
| KC0L053216 | KC01053216 | 諾胰得 諾特筆 | Ryzodeg? FlexTouch? | insulin degludec 70 U/ML (UNIT+INSULIN ASPART 30 U/ML (UNIT/ML) |

## 仍無法 join 的碼

| code | classification | occurrences | source_photos | reason |
|---|---|---:|---|---|
| AB230371GO | needs_manual_review | 3 | IMG_7203.jpeg | does not satisfy strict NHI code pattern and no conservative correction matched official NHI |
| AC414881GO | needs_manual_review | 2 | IMG_7464.jpeg | does not satisfy strict NHI code pattern and no conservative correction matched official NHI |
| AC484721GO | needs_manual_review | 1 | IMG_7203.jpeg | does not satisfy strict NHI code pattern and no conservative correction matched official NHI |
| AC585341GD | needs_manual_review | 1 | IMG_7660.JPG | does not satisfy strict NHI code pattern and no conservative correction matched official NHI |
| AC585341GO | needs_manual_review | 1 | IMG_7655.JPG | does not satisfy strict NHI code pattern and no conservative correction matched official NHI |
| BC171251GO | needs_manual_review | 4 | IMG_7397.JPG; IMG_7464.jpeg; IMG_7510.jpeg; IMG_7675.JPG | does not satisfy strict NHI code pattern and no conservative correction matched official NHI |
| SC21571100 | no_official_match | 2 | IMG_7670.JPG | strict format but no exact official NHI match and no conservative OCR correction matched |

## 下一步人工 review 建議

1. 先排除 `false_positive_word`，這些多為藥名被 broad regex 誤抓。
2. 對 `likely_ocr_confusion` 使用原始照片或 OCR nearby_text 人工確認校正碼。
3. 對 `no_official_match` 與 `needs_manual_review` 檢查是否為舊碼、OCR 錯碼或非健保藥品碼。
4. 人工確認後再建立 staging import，不要直接寫入 `drug_items` 或 `aliases`。

## 輸出

- `db_backups/drug_staging/prescription_nhi_drug_code_cleaning_candidates.csv`
