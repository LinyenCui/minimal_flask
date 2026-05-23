# TFDA ATC duplicate key 唯讀分析

產生時間：2026-05-23 08:22:08

## 本階段目的

本報告只讀取 TFDA ATC raw ZIP 與本機 DB row count，分析 `official_tfda_atc_staging_business_uniq` 對應鍵重複分布。未修改資料庫、未修改 schema、未 insert/delete/truncate。

## Raw source

| 項目 | 值 |
| --- | --- |
| raw_zip | reference_data/drug/raw/tfda_atc_20260522.zip |
| inner_file | 41_2.csv |
| source_version | official_drug_raw_20260522 |
| source_checksum | af8f9cf01b19c56b75cee1f4b709e5a1590dbeec8533536c840206b6d8b47ec3 |

## Duplicate key 統計

| metric | value |
| --- | --- |
| raw total rows | 80290 |
| unique business keys | 80027 |
| duplicate business keys count | 133 |
| duplicate rows count (rows in duplicated groups) | 396 |
| extra duplicate rows count (sum count-1) | 263 |
| max duplicate count | 18 |

Business key：`source_version + normalized_license_no + normalized_atc_code + raw_primary_or_secondary`。

## 前 20 組 duplicate keys

| count | normalized_license_no | normalized_atc_code | raw_primary_or_secondary | sample rows |
| --- | --- | --- | --- | --- |
| 18 | 衛署藥輸字第025708號 | B05BA01 | 次 | row 43387: 衛署藥輸字第025708號 / 次 / B05BA01 / amino acids / ; row 43388: 衛署藥輸字第025708號 / 次 / B05BA01 / amino acids / ; row 43389: 衛署藥輸字第025708號 / 次 / B05BA01 / amino acids /  |
| 17 | 衛署藥輸字第025902號 | B05BA01 | 次 | row 25888: 衛署藥輸字第025902號 / 次 / B05BA01 / amino acids / ; row 25889: 衛署藥輸字第025902號 / 次 / B05BA01 / amino acids / ; row 25890: 衛署藥輸字第025902號 / 次 / B05BA01 / amino acids /  |
| 15 | 衛部藥製字第058130號 | B05BA01 | 次 | row 325: 衛部藥製字第058130號 / 次 / B05BA01 / amino acids / ; row 326: 衛部藥製字第058130號 / 次 / B05BA01 / amino acids / ; row 327: 衛部藥製字第058130號 / 次 / B05BA01 / amino acids /  |
| 15 | 衛部藥輸字第027125號 | B05XB | 次 | row 33871: 衛部藥輸字第027125號 / 次 / B05XB / Amino acids / ; row 33872: 衛部藥輸字第027125號 / 次 / B05XB / Amino acids / ; row 33873: 衛部藥輸字第027125號 / 次 / B05XB / Amino acids /  |
| 8 | 衛署藥輸字第025708號 | B05BB01 | 次 | row 43386: 衛署藥輸字第025708號 / 次 / B05BB01 / electrolytes / ; row 78137: 衛署藥輸字第025708號 / 次 / B05BB01 / electrolytes / ; row 78140: 衛署藥輸字第025708號 / 次 / B05BB01 / electrolytes /  |
| 8 | 衛署藥輸字第025902號 | B05BB01 | 次 | row 25891: 衛署藥輸字第025902號 / 次 / B05BB01 / electrolytes / ; row 25892: 衛署藥輸字第025902號 / 次 / B05BB01 / electrolytes / ; row 78267: 衛署藥輸字第025902號 / 次 / B05BB01 / electrolytes /  |
| 8 | 衛部藥輸字第026993號 | B05XA | 次 | row 33712: 衛部藥輸字第026993號 / 次 / B05XA / Electrolyte solutions / ; row 33713: 衛部藥輸字第026993號 / 次 / B05XA / Electrolyte solutions / ; row 33714: 衛部藥輸字第026993號 / 次 / B05XA / Electrolyte solutions /  |
| 6 | 衛署藥輸字第025659號 | V03AX | 次 | row 43302: 衛署藥輸字第025659號 / 次 / V03AX / Other therapeutic products / ; row 43303: 衛署藥輸字第025659號 / 次 / V03AX / Other therapeutic products / ; row 43304: 衛署藥輸字第025659號 / 次 / V03AX / Other therapeutic products /  |
| 6 | 衛署藥輸字第025669號 | S01XA | 次 | row 43322: 衛署藥輸字第025669號 / 次 / S01XA / Other ophthalmologicals / ; row 43323: 衛署藥輸字第025669號 / 次 / S01XA / Other ophthalmologicals / ; row 43324: 衛署藥輸字第025669號 / 次 / S01XA / Other ophthalmologicals /  |
| 6 | 衛署藥輸字第025683號 | V03AX | 次 | row 43351: 衛署藥輸字第025683號 / 次 / V03AX / Other therapeutic products / ; row 43352: 衛署藥輸字第025683號 / 次 / V03AX / Other therapeutic products / ; row 43353: 衛署藥輸字第025683號 / 次 / V03AX / Other therapeutic products /  |
| 5 | 衛署藥製字第057277號 | B05BB01 | 次 | row 13143: 衛署藥製字第057277號 / 次 / B05BB01 / electrolytes / ; row 13145: 衛署藥製字第057277號 / 次 / B05BB01 / electrolytes / ; row 13146: 衛署藥製字第057277號 / 次 / B05BB01 / electrolytes /  |
| 5 | 衛署藥製字第057294號 | B05BB01 | 次 | row 13168: 衛署藥製字第057294號 / 次 / B05BB01 / electrolytes / ; row 22470: 衛署藥製字第057294號 / 次 / B05BB01 / electrolytes / ; row 22471: 衛署藥製字第057294號 / 次 / B05BB01 / electrolytes /  |
| 5 | 衛署藥輸字第025805號 | S01XA | 次 | row 43520: 衛署藥輸字第025805號 / 次 / S01XA / Other ophthalmologicals / ; row 43521: 衛署藥輸字第025805號 / 次 / S01XA / Other ophthalmologicals / ; row 43522: 衛署藥輸字第025805號 / 次 / S01XA / Other ophthalmologicals /  |
| 5 | 衛部藥輸字第026852號 | S01XA | 次 | row 48521: 衛部藥輸字第026852號 / 次 / S01XA / Other ophthalmologicals / ; row 48522: 衛部藥輸字第026852號 / 次 / S01XA / Other ophthalmologicals / ; row 48523: 衛部藥輸字第026852號 / 次 / S01XA / Other ophthalmologicals /  |
| 5 | 衛部藥輸字第026905號 | S01XA | 次 | row 48607: 衛部藥輸字第026905號 / 次 / S01XA / Other ophthalmologicals / ; row 48608: 衛部藥輸字第026905號 / 次 / S01XA / Other ophthalmologicals / ; row 48609: 衛部藥輸字第026905號 / 次 / S01XA / Other ophthalmologicals /  |
| 4 | 衛署藥輸字第025973號 | S01XA | 次 | row 25993: 衛署藥輸字第025973號 / 次 / S01XA / Other ophthalmologicals / ; row 25994: 衛署藥輸字第025973號 / 次 / S01XA / Other ophthalmologicals / ; row 78338: 衛署藥輸字第025973號 / 次 / S01XA / Other ophthalmologicals /  |
| 4 | 衛署藥輸字第026009號 | C05AX | 次 | row 26043: 衛署藥輸字第026009號 / 次 / C05AX / Other agents for treatment of hemorrhoids and anal fissures for topical use / ; row 26044: 衛署藥輸字第026009號 / 次 / C05AX / Other agents for treatment of hemorrhoids and anal fissures for topical use / ; row 78359: 衛署藥輸字第026009號 / 次 / C05AX / Other agents for treatment of hemorrhoids and anal fissures for topical use /  |
| 4 | 衛部菌疫輸字第001126號 | J07BB02 | 次 | row 33506: 衛部菌疫輸字第001126號 / 次 / J07BB02 / influenza, inactivated, split virus or surface antigen / ; row 33507: 衛部菌疫輸字第001126號 / 次 / J07BB02 / influenza, inactivated, split virus or surface antigen / ; row 33508: 衛部菌疫輸字第001126號 / 次 / J07BB02 / influenza, inactivated, split virus or surface antigen /  |
| 4 | 衛部藥製字第059730號 | B05Z | 次 | row 48043: 衛部藥製字第059730號 / 次 / B05Z / HEMODIALYTICS AND HEMOFILTRATES / ; row 48044: 衛部藥製字第059730號 / 次 / B05Z / HEMODIALYTICS AND HEMOFILTRATES / ; row 48045: 衛部藥製字第059730號 / 次 / B05Z / HEMODIALYTICS AND HEMOFILTRATES /  |
| 4 | 衛部藥輸字第026111號 | V03AX | 次 | row 29807: 衛部藥輸字第026111號 / 次 / V03AX / Other therapeutic products / ; row 29808: 衛部藥輸字第026111號 / 次 / V03AX / Other therapeutic products / ; row 67133: 衛部藥輸字第026111號 / 次 / V03AX / Other therapeutic products /  |

## 整列是否完全相同

| metric | value |
| --- | --- |
| duplicate groups with identical row content | 133 |
| duplicate groups with differing row content | 0 |
| duplicate rows in identical groups | 396 |
| duplicate rows in differing groups | 0 |

所有 duplicate business key 群組在 raw ATC 欄位內容上皆為完全相同列；重複主要是 raw source 本身重複列，不是同 key 下其他欄位互相衝突。

## Source-row unique 檢查

| key | unique |
| --- | --- |
| source_version + source_checksum + source_inner_file + source_row_number | yes |

## 目前 DB 狀態

| table | exists | row_count |
| --- | --- | --- |
| official_nhi_drug_payment_staging | True | 224261 |
| official_tfda_drug_license_staging | True | 71804 |
| official_tfda_drug_ingredient_staging | True | 125902 |
| official_tfda_atc_staging | True | 0 |
| drug_items | True | 152 |
| drug_diagnosis_links | True | 27 |

## Schema 修正方案評估

### 方案 A：移除 `official_tfda_atc_staging_business_uniq`，只保留 source-row unique

建議採用。raw staging 的職責是忠實保存官方 raw rows，不應在匯入時因 business key 重複而丟棄或擋下 raw row。後續可用 view 或 curated table 依 business key 去重。

### 方案 B：保留 business key，但改為 non-unique index

可接受。這能保留查詢效能與重複分析能力，但不阻擋 raw duplicate rows。若仍需要查詢 business key，建議改成普通 index。

### 方案 C：匯入時去重

不建議。這會讓 raw staging 不再等於官方 raw data，後續追蹤 source row、稽核與重新匯入都更困難。

## 建議

建議採用方案 A 或 A+B：raw staging 只用 source-row unique 作為硬性唯一約束，business key 改為 non-unique index。下一步可修改 `create_official_tfda_atc_staging.sql`，並評估 import 腳本對已成功前三張表的重跑策略。
