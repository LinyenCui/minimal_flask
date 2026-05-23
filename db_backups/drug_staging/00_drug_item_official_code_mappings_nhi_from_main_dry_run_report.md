# Drug Item Official Code Mappings NHI From Main Dry-run Report

## 本階段目的

本報告根據已填入 `drug_items.nhi_drug_code` 的 31 筆主健保碼，準備建立 `drug_item_official_code_mappings` 的 NHI mapping 候選。
本階段只做唯讀分析與 dry-run CSV，不建立 table、不寫資料庫、不產生 INSERT SQL。

## 來源摘要

- drug_items row count: 152
- drug_items.nhi_drug_code 已填值筆數: 31
- dry-run mapping rows: 31
- ready_to_apply: 31
- official NHI join failed: 0

## Mapping 規則

- `code_type = NHI`
- `code_value = drug_items.nhi_drug_code`
- `official_source_table = official_nhi_drug_payment_staging`
- `match_method = prescription_nhi_code`
- `confidence = high`
- `review_status = auto_accepted`
- `review_decision = approve`
- `ready_to_apply = true` 僅代表下一階段可進 apply 腳本；本階段不寫入 DB。

## Official NHI Join 結果

- join 成功: 31
- join 失敗: 0
- 同一 code_value 對應多筆 official 歷史給付列的 code 數: 22

### 同碼多歷史列

| code_value | official row count |
|---|---:|
| AA48333100 | 9 |
| AB45348100 | 11 |
| AB46766100 | 10 |
| AB57178100 | 10 |
| AB57312100 | 13 |
| AB58075100 | 9 |
| AC19420100 | 2 |
| AC57805100 | 12 |
| AC58316100 | 10 |
| AC59821100 | 7 |
| AC60134100 | 7 |
| AC61850100 | 3 |
| BA24876100 | 10 |
| BC21571100 | 11 |
| BC22889100 | 13 |
| BC24131100 | 10 |
| BC24403100 | 10 |
| BC25005100 | 10 |
| BC25446100 | 12 |
| BC25537100 | 15 |
| BC27467100 | 6 |
| KC01053216 | 3 |

## 重複與異常檢查

- 重複 code_value 數: 0
- 一個 drug_item 多個 NHI 主碼: 0

## 31 筆候選

| drug_item_id | drug | NHI code | official name | ATC | ready |
|---:|---|---|---|---|---|
| 1 | Bisoprolol / Concor 康肯 | BC171251G0 | CONCOR 5 | C07AB07 | true |
| 5 | GLIMEPIRIDE 2MG + METFORMIN 50 / Temilg F.C.  甜蜜克 | AC60134100 | Temilg F.C. Tablets 2/500mg | A10BD02 | true |
| 6 | Glimepiride / Glimaryl 騐理蔓 | AB46766100 | GLIMARYL TABLETS 2MG (GLIMEPIRIDE) | A10BB12 | true |
| 7 | CARDITONIN S.C. TABLETS / CARDITONIN S.C. TABLETS 心康寧 | AC198951G0 | CARDITONIN S.C. TABLETS 25MG (DIPYRIDAMOLE) "VPP" | B01AC07 | true |
| 12 | Febuxostat / Fekuton/Fburic 服克痛 | AC61850100 | Fekuton Film Coated Tablets 80mg | M04AA03 | true |
| 17 | Glimepiride2mg+Meformin500mg / Amaryl-M 美爾胰 | BA24876100 | Amaryl M Film-coated Tablets 2/500mg | A10BD02 | true |
| 18 | Tamsulosin / Harnalidge D 活路利淨 | BC24403100 | Harnalidge D tablets 0.2mg | G04CA02 | true |
| 19 | Zolpidem / Stilnox10mg 使蒂諾斯(管制藥) | BC215311G0 | STILNOX FILM-COATED SCORED TABLETS 10MG | N05CF02 | true |
| 21 | Amlodipine / Norvasc 脈優 | BC21571100 | NORVASC TABLETS 5MG | C08CA01 | true |
| 24 | Atorvastatin / Lipitor 立普妥 | BC22889100 | LIPITOR FILM-COATED TABLETS 40MG | C10AA05 | true |
| 25 | Mefenamic acid / Ponstan/Ponstal 博疏痛 | AC19420100 | PONSTAL F.C. TABLETS 500MG "SINPHAR" (MEFENAMIC ACID) | M01AG01 | true |
| 33 | Allopurinol / Synorid 欣律 | AC40106100 | SYNORID TABLETS 100MG | M04AA01 | true |
| 34 | Bisoprolol / Biso 百適歐 更換普康膜衣錠(bisoprolol) | AB45348100 | BISO F.C. TABLETS 5MG | C07AB07 | true |
| 40 | Furosemide / Lasix/Rasitol 來喜妥 | AB307491G0 | RASITOL TABLETS 40MG (FUROSEMIDE) | C03CA01 | true |
| 43 | VALSARTAN 160 MGAMLODIPINE BES / EXFOPINE 安普新 | AC59821100 | Exfopine Film-Coated Tablet 5/160mg | C09DB01 | true |
| 46 | Rosuvastatin / Rosustin 優脂定 | AC58316100 | Rosustin Film Coated Tablets 5mg | C10AA07 | true |
| 47 | Pioglitazone / Glitos/Glutazone 欣促胰 | AA48333100 | Glutazone Tablets 30mg | A10BG03 | true |
| 58 | Atenolol / Ateol(Tenomin)UROSIN 壓平樂 | AB388671G0 | ATEOL F.C. TABLETS 50MG "STANDARD" (ATENOLOL) | C07AB03 | true |
| 60 | Irbesartan / Aprotan 壓利安 | AB57178100 | Aprotan F.C. Tab. 150mg "Standard" | C09CA04 | true |
| 61 | Atorvastatin / Atorva 立舒脂(立脂妥) | AC57805100 | Atorva F.C. Tab. 20mg "Standard" (Atorvastatin) | C10AA05 | true |
| 62 | Nifedipine / Adapine/Adalat 壓悅達 | AB58075100 | Adapine S.R.F.C. Tab. 30mg "Standard" | C08CA05 | true |
| 64 | Propranolol / Propranolol(Inderol) 心律 | AB091021G0 | PROPRANOLOL TABLETS 10MG | C07AA05 | true |
| 67 | Olmesartan / Olmetec 雅脈 | BC25005100 | Olmetec film coated tablets 40mg | C09CA08 | true |
| 69 | Rosuvastatin / Crestor 冠脂妥(阿斯) | BC24131100 | CRESTOR 10MG FILM-COATED TABLETS | C10AA07 | true |
| 75 | Telmisartan / MICARDIS 必康平 | BC25446100 | Twynsta Tablets 80/5mg | C09DB04 | true |
| 78 | Linagliptin / TRAJENTA 糖漸平 | BC25537100 | Trajenta 5mg Film-Coated Tablets | A10BH05 | true |
| 81 | Saxagliptin5mg+Dapagliflozin10 / Qtern 5mg/10mg 控糖穩 | BC27467100 | Qtern 5mg/10mg Film-Coated Tablets | A10BD21 | true |
| 86 | Acarbose / Acarbose 志樂恆 | AB57312100 | Acarbose F.C. Tablets 50mg "CYH" | A10BF01 | true |
| 87 | Metformin / Metformin 寬樂醣 | AC585341G0 | Metformin F.C. Tablets 500mg "CYH" | A10BA02 | true |
| 117 | Pentoxifylline / Fylin 暢循 | AC414881G0 | FYLIN RETARD F.C. TABLETS 400MG "C.H."(PENTOXIFYLLINE) | C04AD03 | true |
| 129 | Insulin degludec / Tresiba FlexTouch 諾胰保諾特筆 | KC01053216 | Ryzodeg? FlexTouch? | A10AD06 | true |

## Metformin 備註

- `drug_item 87 Metformin / Metformin 寬樂醣` 的主健保碼使用 `AC585341G0`。
- `AC58534100` 不作為 `drug_items.nhi_drug_code` 主碼；後續可另進 mapping table review 或保留為參考碼。

## Schema 草案檢查

`create_drug_item_official_code_mappings.sql` 可支援本批資料：

- `code_type = NHI` 在 check constraint 允許範圍內。
- `match_method = prescription_nhi_code` 在 check constraint 允許範圍內。
- `confidence = high` 在 check constraint 允許範圍內。
- `review_status = auto_accepted` 在 check constraint 允許範圍內。
- `review_decision = approve` 在 check constraint 允許範圍內。
- unique `(drug_item_id, code_type, code_value, official_source_version)` 可避免同一來源版本重複匯入同一 mapping。

注意：schema 草案有 `official_source_id`，但本次 CSV 依使用者指定欄位未輸出該欄。下一步 apply 腳本若要精準保留 evidence，可重新 SELECT 最新 official row 取得 `official_source_id`。

## 安全聲明

- 本階段未建立 `drug_item_official_code_mappings` table。
- 本階段未 INSERT / UPDATE / DELETE / TRUNCATE。
- 未修改 `drug_items`、official staging、`drug_diagnosis_links`。
