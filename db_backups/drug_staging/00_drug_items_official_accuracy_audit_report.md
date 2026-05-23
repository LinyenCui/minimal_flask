# drug_items 官方資料正確性稽核報告

產生時間：2026-05-23 08:44:19

## 本階段目的

本階段只做唯讀分析，比對現有 `drug_items` 與官方 raw staging，找出可能輸入錯誤、OCR 缺字、商品名/學名拆分錯誤、規格單位缺失、重複或需要人工 review 的項目。本報告不修改資料庫、不產生 UPDATE SQL。

## 為什麼先稽核既有 drug_items

目前 `drug_items` 來源是處方/藥品照片 OCR 與 Gemini 標準化，不是原始電子表格。若直接補官方欄位，可能把 OCR 缺字或錯字固化到正式表。因此先產生 review candidates，再由人工確認。

## drug_items schema

| column | type | nullable | default |
| --- | --- | --- | --- |
| id | bigint | NO | nextval('drug_items_id_seq'::regclass) |
| seq_no | text | NO |  |
| table_type | text | NO |  |
| supplier | text | YES |  |
| manufacturer | text | YES |  |
| generic_name | text | NO |  |
| brand_name | text | NO |  |
| aliases | text | YES |  |
| is_high_frequency | boolean | NO | false |
| highlight_color | text | YES |  |
| highlight_meaning | text | YES |  |
| handwritten_note | text | YES |  |
| note_confidence | text | NO | 'none'::text |
| note_type | text | NO | 'none'::text |
| item_kind | text | NO |  |
| category | text | YES |  |
| needs_manual_check | boolean | NO | false |
| source_photo | text | YES |  |
| source_version | text | NO |  |
| staging_import_batch_id | text | NO |  |
| staging_row_id | bigint | NO |  |
| is_active | boolean | NO | true |
| created_at | timestamp with time zone | NO | now() |
| updated_at | timestamp with time zone | NO | now() |

## seq_no / table_type 分布

| seq_no | table_type | count |
| --- | --- | --- |
| 注射-10 | injection | 1 |
| 注射-11 | injection | 1 |
| 注射-12 | injection | 1 |
| 注射-13 | injection | 1 |
| 注射-14 | injection | 1 |
| 注射-15 | injection | 1 |
| 注射-16 | injection | 1 |
| 注射-17 | injection | 1 |
| 注射-18 | injection | 1 |
| 注射-19 | injection | 1 |
| 注射-2 | injection | 1 |
| 注射-20 | injection | 1 |
| 注射-21 | injection | 1 |
| 注射-22 | injection | 1 |
| 注射-23 | injection | 1 |
| 注射-24 | injection | 1 |
| 注射-25 | injection | 1 |
| 注射-3 | injection | 1 |
| 注射-4 | injection | 1 |
| 注射-5 | injection | 1 |
| 注射-6 | injection | 1 |
| 注射-7 | injection | 1 |
| 注射-9 | injection | 1 |
| 1 | oral | 1 |
| 10 | oral | 1 |
| 100 | oral | 1 |
| 101 | oral | 1 |
| 102 | oral | 1 |
| 103 | oral | 1 |
| 105 | oral | 1 |
| 106 | oral | 1 |
| 107 | oral | 1 |
| 108 | oral | 1 |
| 109 | oral | 1 |
| 11 | oral | 1 |
| 110 | oral | 1 |
| 111 | oral | 1 |
| 113 | oral | 1 |
| 114 | oral | 1 |
| 115 | oral | 1 |
| 116 | oral | 1 |
| 117 | oral | 1 |
| 118 | oral | 1 |
| 119 | oral | 1 |
| 12 | oral | 1 |
| 120 | oral | 1 |
| 121 | oral | 1 |
| 122 | oral | 1 |
| 123 | oral | 1 |
| 124 | oral | 1 |
| 125 | oral | 1 |
| 126 | oral | 1 |
| 127 | oral | 1 |
| 128 | oral | 1 |
| 13 | oral | 1 |
| 132 | oral | 1 |
| 134 | oral | 1 |
| 135 | oral | 1 |
| 14 | oral | 1 |
| 15 | oral | 1 |
| 16 | oral | 1 |
| 17 | oral | 1 |
| 18 | oral | 1 |
| 19 | oral | 1 |
| 2 | oral | 1 |
| 20 | oral | 1 |
| 21 | oral | 1 |
| 22 | oral | 1 |
| 23 | oral | 1 |
| 24 | oral | 1 |
| 25 | oral | 1 |
| 26 | oral | 1 |
| 27 | oral | 1 |
| 28 | oral | 1 |
| 29 | oral | 1 |
| 30 | oral | 1 |
| 31 | oral | 1 |
| 32 | oral | 1 |
| 33 | oral | 1 |
| 34 | oral | 1 |

## drug_items 總覽

| 項目 | 數量 |
| --- | --- |
| 總筆數 | 152 |
| generic_name 空值 | 0 |
| brand_name 空值 | 0 |
| supplier 空值 | 0 |
| manufacturer 空值 | 0 |
| aliases 空值 | 152 |

### table_type 分布

| table_type | count |
| --- | --- |
| oral | 124 |
| injection | 23 |
| topical | 5 |

### item_kind 分布

| item_kind | count |
| --- | --- |
| oral_drug | 124 |
| injection_drug | 23 |
| topical_drug | 5 |

### category 分布

| category | count |
| --- | --- |
| 口服藥 | 124 |
| 注射藥 | 23 |
| 外用藥 | 5 |

## match status 統計

| audit_status | count |
| --- | --- |
| likely_correct | 118 |
| likely_correct_but_missing_fields | 32 |
| ambiguous_multiple_candidates | 2 |

| match_method | count |
| --- | --- |
| ingredient_match | 73 |
| exact_normalized_match | 44 |
| brand_match | 28 |
| contains_match | 5 |
| ambiguous_contains_match | 2 |

| confidence | count |
| --- | --- |
| high | 118 |
| low | 27 |
| medium | 7 |

## 高風險 OCR/缺字疑似清單 Top 10

| id | generic_name | brand_name | status | method | reason | action |
| --- | --- | --- | --- | --- | --- | --- |
| 14 | IRBESARTAN 300MG + HYDROCHLORO | Aprovel 安普諾維(原廠) | likely_correct_but_missing_fields | ingredient_match | `IRBESARTAN 300MG + HYDROCHLORO` contains/contained by official `IRBESARTAN 300 MG`; candidates=30; risk=疑似 OCR/截斷字串 | 人工抽查後納入官方欄位補強候選 |
| 96 | Bethamechol | Wecoli 胃可麗 | ambiguous_multiple_candidates | ambiguous_contains_match | short term `Wecoli` matched 30 official candidates | 人工選定正確官方候選；不可自動套用 |
| 123 | Beniel | Beniel 保你爾膜衣錠 | ambiguous_multiple_candidates | ambiguous_contains_match | short term `Beniel` matched 27 official candidates | 人工選定正確官方候選；不可自動套用 |
| 4 | Dextromethorphan20mg+Pot. Cres | Noncough(Medicon-A) 諾咳 | likely_correct | brand_match | `Medicon-A` exact matched official en: `MEDICON-A CAPSULES`; risk=疑似 OCR/截斷字串 | 低優先；可後續補官方代碼欄位設計 |
| 10 | Cephalaxin | Keflex 賜福力欣 | likely_correct | brand_match | `賜福力欣` exact matched official zh: `賜福力欣`; risk=疑似 OCR/截斷字串 | 低優先；可後續補官方代碼欄位設計 |
| 13 | DIMETHYL 1, 4- 7-ISOPROPYLASUL | Azulene 安如寧 | likely_correct | ingredient_match | `Azulene` exact matched official ingredient: `AZULENE`; risk=疑似 OCR/截斷字串 | 低優先；可後續補官方代碼欄位設計 |
| 17 | Glimepiride2mg+Meformin500mg | Amaryl-M 美爾胰 | likely_correct_but_missing_fields | ingredient_match | `Glimepiride2mg+Meformin500mg` contains/contained by official `GLIMEPIRIDE 2 MG`; candidates=30; risk=疑似 OCR/截斷字串 | 人工抽查後納入官方欄位補強候選 |
| 77 | Valosartan80mg+Hydrochlorothia | Co- Diovan(80) 可得安穩 (諾華) | likely_correct_but_missing_fields | contains_match | `Valosartan80mg+Hydrochlorothia` contains/contained by official `losartan`; candidates=30; risk=疑似 OCR/截斷字串 | 人工抽查後納入官方欄位補強候選 |
| 150 | Urea | U/Sinpharderm cream 杏化 | likely_correct | ingredient_match | `Urea` exact matched official ingredient: `UREA`; risk=名稱很短 | 低優先；可後續補官方代碼欄位設計 |

## 有 drug_diagnosis_links 的高風險藥品

| id | generic_name | brand_name | status | reason | action |
| --- | --- | --- | --- | --- | --- |
| 14 | IRBESARTAN 300MG + HYDROCHLORO | Aprovel 安普諾維(原廠) | likely_correct_but_missing_fields | `IRBESARTAN 300MG + HYDROCHLORO` contains/contained by official `IRBESARTAN 300 MG`; candidates=30; risk=疑似 OCR/截斷字串 | 人工抽查後納入官方欄位補強候選 |

## 最適合人工 review 的前 20 筆

| id | generic_name | brand_name | status | confidence | official_source | official_code_or_license | reason | action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 14 | IRBESARTAN 300MG + HYDROCHLORO | Aprovel 安普諾維(原廠) | likely_correct_but_missing_fields | low | NHI payment | AB57864100 | `IRBESARTAN 300MG + HYDROCHLORO` contains/contained by official `IRBESARTAN 300 MG`; candidates=30; risk=疑似 OCR/截斷字串 | 人工抽查後納入官方欄位補強候選 |
| 96 | Bethamechol | Wecoli 胃可麗 | ambiguous_multiple_candidates | low | NHI payment | AC37225100 | short term `Wecoli` matched 30 official candidates | 人工選定正確官方候選；不可自動套用 |
| 123 | Beniel | Beniel 保你爾膜衣錠 | ambiguous_multiple_candidates | low | NHI payment | A056633100 | short term `Beniel` matched 27 official candidates | 人工選定正確官方候選；不可自動套用 |
| 4 | Dextromethorphan20mg+Pot. Cres | Noncough(Medicon-A) 諾咳 | likely_correct | high | NHI payment | A021758100 | `Medicon-A` exact matched official en: `MEDICON-A CAPSULES`; risk=疑似 OCR/截斷字串 | 低優先；可後續補官方代碼欄位設計 |
| 10 | Cephalaxin | Keflex 賜福力欣 | likely_correct | high | TFDA license | 衛署藥輸字第015885號 | `賜福力欣` exact matched official zh: `賜福力欣`; risk=疑似 OCR/截斷字串 | 低優先；可後續補官方代碼欄位設計 |
| 13 | DIMETHYL 1, 4- 7-ISOPROPYLASUL | Azulene 安如寧 | likely_correct | high | TFDA license | 衛署藥輸字第015277號 | `Azulene` exact matched official ingredient: `AZULENE`; risk=疑似 OCR/截斷字串 | 低優先；可後續補官方代碼欄位設計 |
| 17 | Glimepiride2mg+Meformin500mg | Amaryl-M 美爾胰 | likely_correct_but_missing_fields | low | NHI payment | A047172100 | `Glimepiride2mg+Meformin500mg` contains/contained by official `GLIMEPIRIDE 2 MG`; candidates=30; risk=疑似 OCR/截斷字串 | 人工抽查後納入官方欄位補強候選 |
| 77 | Valosartan80mg+Hydrochlorothia | Co- Diovan(80) 可得安穩 (諾華) | likely_correct_but_missing_fields | low | TFDA ATC | 衛署藥製字第048990號 | `Valosartan80mg+Hydrochlorothia` contains/contained by official `losartan`; candidates=30; risk=疑似 OCR/截斷字串 | 人工抽查後納入官方欄位補強候選 |
| 150 | Urea | U/Sinpharderm cream 杏化 | likely_correct | high | TFDA license | 衛部藥製字第060928號 | `Urea` exact matched official ingredient: `UREA`; risk=名稱很短 | 低優先；可後續補官方代碼欄位設計 |

## 疑似重複 drug_items

已另輸出 `db_backups/drug_staging/drug_items_possible_duplicates.csv`，共 17 組疑似重複。

| id1 | id2 | name1 | name2 | reason | risk |
| --- | --- | --- | --- | --- | --- |
| 1 | 34 | Bisoprolol / Concor 康肯 | Bisoprolol / Biso 百適歐 更換普康膜衣錠(bisoprolol) | same normalized generic_name | high |
| 2 | 30 | Doxazosin / Dophilin 道福寧 | Doxazosin / Doxaben XL 可迅持續錠 | same normalized generic_name | high |
| 5 | 17 | GLIMEPIRIDE 2MG + METFORMIN 50 / Temilg F.C.  甜蜜克 | Glimepiride2mg+Meformin500mg / Amaryl-M 美爾胰 | very similar generic_name | high |
| 11 | 60 | IRBESARTAN / IRBEPROVEL(APROVEL) 伊必特(台廠) | Irbesartan / Aprotan 壓利安 | same normalized generic_name | high |
| 12 | 59 | Febuxostat / Fekuton/Fburic 服克痛 | Febuxostat / Feburic/Febuton 達理痛 | same normalized generic_name | high |
| 18 | 56 | Tamsulosin / Harnalidge D 活路利淨 | Tamsulosin / Tamlosin 暢利淨 | same normalized generic_name | high |
| 24 | 61 | Atorvastatin / Lipitor 立普妥 | Atorvastatin / Atorva 立舒脂(立脂妥) | same normalized generic_name | high |
| 29 | 140 | PROCHLORPERAZINE / Novamin 諾安命 | Prochlorperazine / Novamin 2ml Inj. | same normalized generic_name | medium |
| 31 | 35 | Acetylcysteine / Actein 愛克痰 | Acetylcysteine / Actein Effervescent 愛克痰發泡錠 | same normalized generic_name | medium |
| 32 | 68 | Carvedilol / Syntrend(CARDILO) 心全 6.25/Dilatrend 12.5) | Carvedilol / Dilatrend 達利全 | same normalized generic_name | medium |
| 40 | 137 | Furosemide / Lasix/Rasitol 來喜妥 | Furosemide / Lasix/Fursemide 2ml Inj.扶如泄民 | same normalized generic_name | medium |
| 45 | 108 | Benzbromarone / Beenrone 勉治 | Benzbromarone / Nogout 杏定痛 | same normalized generic_name | medium |
| 46 | 69 | Rosuvastatin / Rosustin 優脂定 | Rosuvastatin / Crestor 冠脂妥(阿斯) | same normalized generic_name | high |
| 48 | 67 | Olmesartan / Olmesardin 妥得降 | Olmesartan / Olmetec 雅脈 | same normalized generic_name | high |
| 91 | 143 | Metoclopramide / Primperan(Chiaoweigen) 佐胃健 | METOCLOPRAMIDE 10 MG / METOCLOPRAMIDE 美托拉麥注射液 | very similar generic_name | medium |
| 122 | 141 | DIPHENIDOL / DIPHENIDOL 敵芬尼朵 | DIPHENIDOL / KPHADOL INJECTION (DIPHENIDOL) 敵芬尼朵 | same normalized generic_name | medium |
| 148 | 149 | BETAMETHASONE (17-VALERATE) 1 / Sinbeta derm cream 杏貝他健乳1000g/BT | BETAMETHASONE (17-VALERATE) 1 / Betaderm Cream(B-Gencin) 貝他健乳膏 | same normalized generic_name | medium |

## 下一步建議

1. 先人工 review `possible_ocr_typo`、`ambiguous_multiple_candidates`、以及 reason 內含疑似 OCR/截斷的項目。
2. 對 `likely_correct_but_missing_fields` 設計官方欄位補強候選，不直接 update `drug_items`。
3. 疑似重複清單需人工判斷：同學名不同商品可能不是重複，不可自動合併。
4. 若需要修正 OCR 名稱，應回原圖或原始 Gemini CSV 佐證後再建立人工 decision CSV。

## 明確限制

本報告不修改資料庫、不產生 UPDATE SQL、不修改 `drug_items`、不修改 `drug_diagnosis_links`、不修改 official staging tables。
