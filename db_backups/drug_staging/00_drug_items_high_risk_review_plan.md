# 藥品高風險項目人工 Review Decision 草案

## 本階段目的

本報告根據 `drug_items` 官方資料正確性稽核結果，針對第一批高風險 9 筆產生人工 review decision 草案。
本輪只產出 Markdown 與 CSV，不修改資料庫、不產生 UPDATE SQL、不修改 `drug_items`、不修改 `drug_diagnosis_links`。

## 來源

- `db_backups/drug_staging/00_drug_items_official_accuracy_audit_report.md`
- `db_backups/drug_staging/drug_items_official_accuracy_audit_candidates.csv`

## Review Decision 分布

| decision | 筆數 |
|---|---:|
| needs_original_photo_review | 5 |
| correct_generic_name | 3 |
| keep_current | 1 |

## 9 筆人工 Review 草案

### drug_item_id 14: IRBESARTAN 300MG + HYDROCHLORO / Aprovel 安普諾維(原廠)

| 項目 | 內容 |
|---|---|
| 目前 generic_name | IRBESARTAN 300MG + HYDROCHLORO |
| 目前 brand_name | Aprovel 安普諾維(原廠) |
| aliases | 空 |
| table_type | oral |
| item_kind | oral_drug |
| category | 口服藥 |
| supplier | 大昌華嘉 |
| manufacturer | 賽諾菲 |
| 已有 drug_diagnosis_links | yes |
| 官方來源 | NHI payment |
| 官方代碼/許可證 | AB57864100 |
| 官方中文名 | "永勝"愛必斯膜衣錠300毫克 |
| 官方英文名 | Heipo F.C. Tablets 300mg "EVEREST" |
| 官方成分 | IRBESARTAN 300 MG |
| 官方 ATC | C09CA04 |
| 稽核狀態 | likely_correct_but_missing_fields |
| 比對方式 | ingredient_match |
| 信心 | low |
| 疑似問題 | truncation; likely correct but missing fields; possible ingredient/brand mismatch |
| 建議人工決策 | needs_original_photo_review |
| 理由 | Aprovel 通常對應 irbesartan，現有 generic_name 卻含 Hydrochloro 截斷字串，且此品項已有 drug_diagnosis_links；需回原圖確認是否其實是 Co-Aprovel 或 OCR 混入下一列。 |
| 修正 generic_name 草案 | 暫不填 |
| 修正 brand_name 草案 | 暫不填 |
| alias 建議 | Aprovel; Irbesartan |
| 風險 | high |

### drug_item_id 17: Glimepiride2mg+Meformin500mg / Amaryl-M 美爾胰

| 項目 | 內容 |
|---|---|
| 目前 generic_name | Glimepiride2mg+Meformin500mg |
| 目前 brand_name | Amaryl-M 美爾胰 |
| aliases | 空 |
| table_type | oral |
| item_kind | oral_drug |
| category | 口服藥 |
| supplier | 大昌華嘉 |
| manufacturer | 賽諾菲 |
| 已有 drug_diagnosis_links | no |
| 官方來源 | NHI payment |
| 官方代碼/許可證 | A047172100 |
| 官方中文名 | 欣益糖錠 2.0 毫克 |
| 官方英文名 | Amepiride Tablets 2.0MG |
| 官方成分 | GLIMEPIRIDE 2 MG |
| 官方 ATC | A10BB12 |
| 稽核狀態 | likely_correct_but_missing_fields |
| 比對方式 | ingredient_match |
| 信心 | low |
| 疑似問題 | OCR typo; truncation; likely correct but missing fields |
| 建議人工決策 | needs_original_photo_review |
| 理由 | Meformin 疑似 Metformin 錯字，Amaryl-M 語意支持 Glimepiride + Metformin，但官方候選只穩定對到 Glimepiride 2 MG；需回原圖確認完整劑量與商品名。 |
| 修正 generic_name 草案 | Glimepiride 2mg + Metformin 500mg |
| 修正 brand_name 草案 | Amaryl-M 美爾胰 |
| alias 建議 | Glimepiride; Metformin; Amaryl-M |
| 風險 | high |

### drug_item_id 77: Valosartan80mg+Hydrochlorothia / Co- Diovan(80) 可得安穩 (諾華)

| 項目 | 內容 |
|---|---|
| 目前 generic_name | Valosartan80mg+Hydrochlorothia |
| 目前 brand_name | Co- Diovan(80) 可得安穩 (諾華) |
| aliases | 空 |
| table_type | oral |
| item_kind | oral_drug |
| category | 口服藥 |
| supplier | 裕利 |
| manufacturer | 諾華 |
| 已有 drug_diagnosis_links | no |
| 官方來源 | TFDA ATC |
| 官方代碼/許可證 | 衛署藥製字第048990號 |
| 官方中文名 | 空 |
| 官方英文名 | losartan |
| 官方成分 | 空 |
| 官方 ATC | C09CA01 |
| 稽核狀態 | likely_correct_but_missing_fields |
| 比對方式 | contains_match |
| 信心 | low |
| 疑似問題 | OCR typo; truncation; likely correct but missing fields |
| 建議人工決策 | needs_original_photo_review |
| 理由 | Valosartan 疑似 Valsartan，Hydrochlorothia 明顯截斷；Co-Diovan(80) 支持 Valsartan + Hydrochlorothiazide，但官方候選來源異常對到 losartan/ATC，需回原圖與官方品名確認。 |
| 修正 generic_name 草案 | Valsartan 80mg + Hydrochlorothiazide |
| 修正 brand_name 草案 | Co-Diovan(80) 可得安穩 (諾華) |
| alias 建議 | Co-Diovan; Valsartan; Hydrochlorothiazide |
| 風險 | high |

### drug_item_id 4: Dextromethorphan20mg+Pot. Cres / Noncough(Medicon-A) 諾咳

| 項目 | 內容 |
|---|---|
| 目前 generic_name | Dextromethorphan20mg+Pot. Cres |
| 目前 brand_name | Noncough(Medicon-A) 諾咳 |
| aliases | 空 |
| table_type | oral |
| item_kind | oral_drug |
| category | 口服藥 |
| supplier | 信東 |
| manufacturer | 信東 |
| 已有 drug_diagnosis_links | no |
| 官方來源 | NHI payment |
| 官方代碼/許可證 | A021758100 |
| 官方中文名 | 滅咳康複合膠囊 |
| 官方英文名 | MEDICON-A CAPSULES |
| 官方成分 | POTASSIUM CRESOLSULFONATE 90 MG+LYSOZYME CHLORIDE 20 MG+DEXTROMETHORPHAN HBR 20 MG |
| 官方 ATC | R05FA01 |
| 稽核狀態 | likely_correct |
| 比對方式 | brand_match |
| 信心 | high |
| 疑似問題 | truncation; likely correct official brand match |
| 建議人工決策 | needs_original_photo_review |
| 理由 | Medicon-A/諾咳 與官方品名高度一致，但 generic_name 只列 Dextromethorphan + Pot. Cres 並截斷，官方成分還包含 Lysozyme Chloride；修正前應回原圖確認完整成分。 |
| 修正 generic_name 草案 | Dextromethorphan HBr 20mg + Potassium Cresolsulfonate 90mg + Lysozyme Chloride 20mg |
| 修正 brand_name 草案 | Noncough(Medicon-A) 諾咳 |
| alias 建議 | Medicon-A; Noncough; 諾咳 |
| 風險 | medium |

### drug_item_id 10: Cephalaxin / Keflex 賜福力欣

| 項目 | 內容 |
|---|---|
| 目前 generic_name | Cephalaxin |
| 目前 brand_name | Keflex 賜福力欣 |
| aliases | 空 |
| table_type | oral |
| item_kind | oral_drug |
| category | 口服藥 |
| supplier | 信東 |
| manufacturer | 信東 |
| 已有 drug_diagnosis_links | no |
| 官方來源 | TFDA license |
| 官方代碼/許可證 | 衛署藥輸字第015885號 |
| 官方中文名 | 賜福力欣 |
| 官方英文名 | CEPHALEXIN MONOHYDRATE "OPOS" |
| 官方成分 | CEPHALEXIN MONOHYDRATE |
| 官方 ATC | 空 |
| 稽核狀態 | likely_correct |
| 比對方式 | brand_match |
| 信心 | high |
| 疑似問題 | OCR typo |
| 建議人工決策 | correct_generic_name |
| 理由 | 品牌 Keflex/賜福力欣 與官方中文品名一致，Cephalaxin 高度疑似 Cephalexin 拼字錯誤；可列入第一批 generic_name 修正候選。 |
| 修正 generic_name 草案 | Cephalexin |
| 修正 brand_name 草案 | Keflex 賜福力欣 |
| alias 建議 | Cephalexin; Keflex; 賜福力欣 |
| 風險 | medium |

### drug_item_id 13: DIMETHYL 1, 4- 7-ISOPROPYLASUL / Azulene 安如寧

| 項目 | 內容 |
|---|---|
| 目前 generic_name | DIMETHYL 1, 4- 7-ISOPROPYLASUL |
| 目前 brand_name | Azulene 安如寧 |
| aliases | 空 |
| table_type | oral |
| item_kind | oral_drug |
| category | 口服藥 |
| supplier | 大道 |
| manufacturer | 世達 |
| 已有 drug_diagnosis_links | no |
| 官方來源 | TFDA license |
| 官方代碼/許可證 | 衛署藥輸字第015277號 |
| 官方中文名 | 愛胃寧錠 |
| 官方英文名 | AZUKURENIN TABLETS |
| 官方成分 | AZULENE |
| 官方 ATC | 空 |
| 稽核狀態 | likely_correct |
| 比對方式 | ingredient_match |
| 信心 | high |
| 疑似問題 | truncation; possible OCR typo |
| 建議人工決策 | needs_original_photo_review |
| 理由 | Azulene/安如寧 與官方成分 AZULENE 對得上，但現有 generic_name 是截斷化學名，不宜未看原圖就覆蓋成分欄位。 |
| 修正 generic_name 草案 | Azulene |
| 修正 brand_name 草案 | Azulene 安如寧 |
| alias 建議 | Azulene; 安如寧; AZUKURENIN |
| 風險 | medium |

### drug_item_id 96: Bethamechol / Wecoli 胃可麗

| 項目 | 內容 |
|---|---|
| 目前 generic_name | Bethamechol |
| 目前 brand_name | Wecoli 胃可麗 |
| aliases | 空 |
| table_type | oral |
| item_kind | oral_drug |
| category | 口服藥 |
| supplier | 強生 |
| manufacturer | 應元 |
| 已有 drug_diagnosis_links | no |
| 官方來源 | NHI payment |
| 官方代碼/許可證 | AC37225100 |
| 官方中文名 | "應元"胃可麗錠２５毫克（氯化月尿酯膽生僉） |
| 官方英文名 | WECOLI TABLETS 25MG (BETHANECHOL CHLORIDE) "YY" |
| 官方成分 | BETHANECHOL CHLORIDE 25 MG |
| 官方 ATC | N07AB02 |
| 稽核狀態 | ambiguous_multiple_candidates |
| 比對方式 | ambiguous_contains_match |
| 信心 | low |
| 疑似問題 | OCR typo; ambiguous multiple candidates |
| 建議人工決策 | correct_generic_name |
| 理由 | Wecoli/胃可麗 對到官方 WECOLI TABLETS 25MG，Bethamechol 高度疑似 Bethanechol 拼字錯誤；雖有多候選，這筆官方品名與成分足以作為修正草案。 |
| 修正 generic_name 草案 | Bethanechol chloride |
| 修正 brand_name 草案 | Wecoli 胃可麗 |
| alias 建議 | Bethanechol; Wecoli; 胃可麗 |
| 風險 | medium |

### drug_item_id 123: Beniel / Beniel 保你爾膜衣錠

| 項目 | 內容 |
|---|---|
| 目前 generic_name | Beniel |
| 目前 brand_name | Beniel 保你爾膜衣錠 |
| aliases | 空 |
| table_type | oral |
| item_kind | oral_drug |
| category | 口服藥 |
| supplier | 健喬信元 |
| manufacturer | 健喬信元 |
| 已有 drug_diagnosis_links | no |
| 官方來源 | NHI payment |
| 官方代碼/許可證 | A056633100 |
| 官方中文名 | 保你爾膜衣錠4毫克 |
| 官方英文名 | Beniel F.C. Tablets 4mg |
| 官方成分 | BENIDIPINE HYDROCHLORIDE 4 MG |
| 官方 ATC | C08CA15 |
| 稽核狀態 | ambiguous_multiple_candidates |
| 比對方式 | ambiguous_contains_match |
| 信心 | low |
| 疑似問題 | ambiguous multiple candidates; generic/brand split issue |
| 建議人工決策 | correct_generic_name |
| 理由 | Beniel 是商品名，不像學名；官方候選顯示成分為 Benidipine Hydrochloride 4 MG，建議把 generic_name 修為成分名並保留 Beniel 作 brand/alias。 |
| 修正 generic_name 草案 | Benidipine hydrochloride 4mg |
| 修正 brand_name 草案 | Beniel 保你爾膜衣錠 |
| alias 建議 | Beniel; 保你爾; Benidipine |
| 風險 | medium |

### drug_item_id 150: Urea / U/Sinpharderm cream 杏化

| 項目 | 內容 |
|---|---|
| 目前 generic_name | Urea |
| 目前 brand_name | U/Sinpharderm cream 杏化 |
| aliases | 空 |
| table_type | topical |
| item_kind | topical_drug |
| category | 外用藥 |
| supplier | 杏輝 |
| manufacturer | 杏輝 |
| 已有 drug_diagnosis_links | no |
| 官方來源 | TFDA license |
| 官方代碼/許可證 | 衛部藥製字第060928號 |
| 官方中文名 | 芙澤適乳膏 |
| 官方英文名 | Soficome Cream |
| 官方成分 | UREA |
| 官方 ATC | 空 |
| 稽核狀態 | likely_correct |
| 比對方式 | ingredient_match |
| 信心 | high |
| 疑似問題 | short name; likely correct but missing fields |
| 建議人工決策 | keep_current |
| 理由 | Urea 與官方成分 UREA 一致；名稱短但外用藥情境合理，先保留現值，後續只需補官方 reference 欄位或 alias。 |
| 修正 generic_name 草案 | 暫不填 |
| 修正 brand_name 草案 | 暫不填 |
| alias 建議 | Urea; Soficome; Sinpharderm cream |
| 風險 | low |

## 需要回原始照片確認

以下項目不建議只依官方候選直接改值，應先回照片或原始 OCR 表確認：

- id 14: IRBESARTAN 300MG + HYDROCHLORO / Aprovel 安普諾維(原廠)。原因：Aprovel 通常對應 irbesartan，現有 generic_name 卻含 Hydrochloro 截斷字串，且此品項已有 drug_diagnosis_links；需回原圖確認是否其實是 Co-Aprovel 或 OCR 混入下一列。
- id 17: Glimepiride2mg+Meformin500mg / Amaryl-M 美爾胰。原因：Meformin 疑似 Metformin 錯字，Amaryl-M 語意支持 Glimepiride + Metformin，但官方候選只穩定對到 Glimepiride 2 MG；需回原圖確認完整劑量與商品名。
- id 77: Valosartan80mg+Hydrochlorothia / Co- Diovan(80) 可得安穩 (諾華)。原因：Valosartan 疑似 Valsartan，Hydrochlorothia 明顯截斷；Co-Diovan(80) 支持 Valsartan + Hydrochlorothiazide，但官方候選來源異常對到 losartan/ATC，需回原圖與官方品名確認。
- id 4: Dextromethorphan20mg+Pot. Cres / Noncough(Medicon-A) 諾咳。原因：Medicon-A/諾咳 與官方品名高度一致，但 generic_name 只列 Dextromethorphan + Pot. Cres 並截斷，官方成分還包含 Lysozyme Chloride；修正前應回原圖確認完整成分。
- id 13: DIMETHYL 1, 4- 7-ISOPROPYLASUL / Azulene 安如寧。原因：Azulene/安如寧 與官方成分 AZULENE 對得上，但現有 generic_name 是截斷化學名，不宜未看原圖就覆蓋成分欄位。

## 可能可直接修正 generic_name 的候選

- id 10: `Cephalaxin` -> `Cephalexin`。理由：品牌 Keflex/賜福力欣 與官方中文品名一致，Cephalaxin 高度疑似 Cephalexin 拼字錯誤；可列入第一批 generic_name 修正候選。
- id 96: `Bethamechol` -> `Bethanechol chloride`。理由：Wecoli/胃可麗 對到官方 WECOLI TABLETS 25MG，Bethamechol 高度疑似 Bethanechol 拼字錯誤；雖有多候選，這筆官方品名與成分足以作為修正草案。
- id 123: `Beniel` -> `Benidipine hydrochloride 4mg`。理由：Beniel 是商品名，不像學名；官方候選顯示成分為 Benidipine Hydrochloride 4 MG，建議把 generic_name 修為成分名並保留 Beniel 作 brand/alias。

## 已有 drug_diagnosis_links 的項目

- id 14: IRBESARTAN 300MG + HYDROCHLORO / Aprovel 安普諾維(原廠)。此筆已被關聯查詢使用，任何名稱修正都應先確認不影響 `/dx`、`/drug` 顯示語意。

## 安全原則

- 本報告不修改資料庫。
- 本報告不產生 UPDATE SQL。
- `correct_generic_name` 僅表示適合進入人工修正候選，不代表已可自動 apply。
- `needs_original_photo_review` 需回原圖或原始 Gemini/OCR 資料確認後，再建立正式 decision。

## 建議下一步

1. 先人工查看 id 14、17、77、4、13 的原始照片或 OCR 來源，確認是否為截斷或跨列混入。
2. 對 id 10、96、123 另建立小批次正式修正 decision，但仍先做 dry-run，不直接更新。
3. id 150 暫時保留，後續若設計 official drug reference 欄位時再補官方來源與 alias。
