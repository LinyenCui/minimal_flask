# ICD-REF-1 健保 ICD-10-CM 完整官方 Reference Staging Dry-run

## 1. 本階段目的

本階段只做設計與 dry-run profile，不建立 table、不寫入資料庫、不修改 `diagnosis_codes`、不修改任何既有 staging table，也不處理 ICD-10-PCS、藥品、OCR、photos 或 prescription 資料。

目標是為健保署 2023 年版 ICD-10-CM 官方完整診斷碼建立獨立 staging 流程，作為後續 diagnosis_codes 補強、候選比對與人工 review 的官方 reference 來源。

## 2. 現有 `diagnosis_icd10_reference_staging` 唯讀檢查

現有 table：`diagnosis_icd10_reference_staging`

目前狀態：

- row count：9
- import_batch_id：`rx_icd10_ref_e42ed7be09c5`
- review_status：`pending` 9 筆
- 內容來源：處方照片 / OCR 後人工整理的少量 ICD-10 reference candidates

欄位摘要：

| 欄位 | 用途 |
| --- | --- |
| raw_code / normalized_code | OCR 或抽取來源中的原始/正規化 ICD-10 |
| official_name_zh / official_name_en | 已查官方 reference 後的名稱 |
| official_source | 人工驗證來源說明 |
| confidence | OCR/人工候選可信度 |
| source_photos | 來源照片清單 |
| source_file / source_row_number | 來源候選檔與列號 |
| review_status / review_decision / reviewer | 人工 review 流程欄位 |
| import_batch_id | 小批次匯入 ID |

判斷：不建議沿用此 table 承載完整官方 ICD-10-CM。

原因：

1. 語意不同：現有表是 OCR/處方抽取出的少量候選 reference，不是完整官方 code master。
2. 欄位不合：`source_photos`、`confidence`、`review_status` 偏向人工候選審核，不適合 96k 官方 master rows。
3. 資料規模不同：現有 9 筆；官方 ICD-10-CM 約 96,802 筆。
4. 生命週期不同：官方 reference 應可整批版本化重匯；OCR candidates 應保留 review 工作流。
5. 風險控管：混表會讓後續判斷「官方完整 reference」與「處方/OCR候選」時語意混淆。

建議新增獨立 table：`official_icd10_cm_reference_staging`。

## 3. XLSX 來源檔

- 檔案：`reference_data/icd/nhi_2023_icd10_cm_pcs.xlsx`
- 修改時間：2026-05-16 06:45:45
- 大小：7,324,177 bytes
- 使用 sheet：`ICD-10-CM`
- 不使用 sheet：`ICD-10-PCS`，因為 PCS 是處置碼，不是 diagnosis code。

`ICD-10-CM` 欄位：

| 原始欄位 | 對應 staging 欄位 |
| --- | --- |
| 2023年版 ICD-10-CM | icd10_code / normalized_code |
| USE | use_flag / is_billable |
| 2023 CM英文名稱 | official_name_en |
| 2023 CM中文名稱 | official_name_zh |
| 狀態 | status |
| 修訂日期 | revision_date |

## 4. Dry-run Profile

| 項目 | 數值 |
| --- | ---: |
| 總資料列，不含 header | 96,802 |
| code 空白筆數 | 0 |
| 中文名空白筆數 | 0 |
| 英文名空白筆數 | 0 |
| code 重複 code 數 | 0 |
| 重複 rows | 0 |

### USE 分布

| USE | 筆數 | 推論 |
| --- | ---: | --- |
| 1 | 73,681 | 可使用 / billable leaf code |
| 0 | 23,121 | 分類 header / non-billable code |

### 狀態分布

| 狀態 | 筆數 |
| --- | ---: |
| 空白 | 89,900 |
| 代碼新增 | 5,698 |
| 英文名稱修改 | 1,114 |
| 中文名稱修改 | 90 |

### 修訂日期範圍

`修訂日期` 欄位多為文字型修訂註記，不是穩定日期欄位。本次 dry-run 觀察到非空值範圍：

- 最小文字值：`113.07.17修正中文名稱`
- 最大文字值：`113.11.18修正中文名稱`

建議 staging 欄位先保留 `revision_date text`，不要強制轉成 date。

### code 格式範例

`A00`, `A00.0`, `A00.1`, `A00.9`, `A01`, `A01.0`, `A01.00`, `A01.01`, `A01.02`, `A01.03`, `A01.04`, `A01.05`, `A01.09`, `A01.1`, `A01.2`, `A01.3`, `A01.4`, `A02`, `A02.0`, `A02.1`

## 5. 前 20 筆樣本

| source row | code | USE | 英文名 | 中文名 | 狀態 | 修訂日期 |
| ---: | --- | --- | --- | --- | --- | --- |
| 2 | A00 | 0 | Cholera | 霍亂 |  |  |
| 3 | A00.0 | 1 | Cholera due to Vibrio cholerae 01, biovar cholerae | 血清型01 cholerae霍亂弧菌所致之霍亂 |  |  |
| 4 | A00.1 | 1 | Cholera due to Vibrio cholerae 01, biovar eltor | 血清型01 eltor霍亂弧菌所致之霍亂 |  |  |
| 5 | A00.9 | 1 | Cholera, unspecified | 霍亂 |  |  |
| 6 | A01 | 0 | Typhoid and paratyphoid fevers | 傷寒及副傷寒 |  |  |
| 7 | A01.0 | 0 | Typhoid fever | 傷寒 |  |  |
| 8 | A01.00 | 1 | Typhoid fever, unspecified | 傷寒 |  |  |
| 9 | A01.01 | 1 | Typhoid meningitis | 傷寒腦膜炎 |  |  |
| 10 | A01.02 | 1 | Typhoid fever with heart involvement | 傷寒伴有侵及心臟 |  |  |
| 11 | A01.03 | 1 | Typhoid pneumonia | 傷寒肺炎 |  |  |
| 12 | A01.04 | 1 | Typhoid arthritis | 傷寒關節炎 |  |  |
| 13 | A01.05 | 1 | Typhoid osteomyelitis | 傷寒骨髓炎 |  |  |
| 14 | A01.09 | 1 | Typhoid fever with other complications | 傷寒熱伴有其他併發症 |  |  |
| 15 | A01.1 | 1 | Paratyphoid fever A | A型副傷寒 |  |  |
| 16 | A01.2 | 1 | Paratyphoid fever B | B型副傷寒 |  |  |
| 17 | A01.3 | 1 | Paratyphoid fever C | C型副傷寒 |  |  |
| 18 | A01.4 | 1 | Paratyphoid fever, unspecified | 副傷寒 |  |  |
| 19 | A02 | 0 | Other salmonella infections | 其他沙門感染 |  |  |
| 20 | A02.0 | 1 | Salmonella enteritis | 沙門桿菌腸炎 |  |  |
| 21 | A02.1 | 1 | Salmonella sepsis | 沙門桿菌敗血症 |  |  |

## 6. 指定 code 是否存在

| code | 是否存在 | source row | USE | 英文名 | 中文名 | 狀態 |
| --- | --- | ---: | --- | --- | --- | --- |
| A00 | 是 | 2 | 0 | Cholera | 霍亂 |  |
| E11.9 | 是 | 4316 | 1 | Type 2 diabetes mellitus without complications | 第二型糖尿病，未伴有併發症 |  |
| M10.9 | 是 | 16697 | 1 | Gout, unspecified | 痛風 |  |
| N10 | 是 | 24276 | 1 | Acute pyelonephritis | 急性腎盂腎炎 | 英文名稱修改 |
| E78.1 | 是 | 4852 | 1 | Pure hyperglyceridemia | 純高三酸甘油酯血症 |  |
| E78.2 | 是 | 4853 | 1 | Mixed hyperlipidemia | 混合型高血脂症 |  |
| L21.9 | 是 | 14777 | 1 | Seborrheic dermatitis, unspecified | 脂漏性皮膚炎 |  |

## 7. 新 staging table 設計摘要

建議 table：`official_icd10_cm_reference_staging`

設計重點：

- 一張獨立官方 reference staging，不混入 OCR candidate staging。
- 唯一鍵建議：`source_version + icd10_code`。
- 保留 `source_file`、`source_sheet`、`source_row_number`、`source_version`、`import_batch_id`。
- `is_billable` 從 `USE = '1'` 推導。
- `is_active` 預設 true；若後續匯入 deletion sheet 或歷史版本再另行判斷。
- `revision_date` 先存 text，避免健保欄位文字格式造成錯誤轉型。
- `source_checksum` 對單列來源資料取 hash，用來檢查未來版本異動。

## 8. 風險與安全原則

1. 不可把 ICD-10-PCS 匯入 diagnosis reference，PCS 是處置碼。
2. 不可直接用完整官方 reference 覆蓋 `diagnosis_codes`。
3. 後續仍應走 official reference staging → candidate generation → human review → approved-only apply。
4. `USE=0` 應保留在官方 reference 中，但對正式診斷碼補強時需小心，通常不可直接當 billable diagnosis 使用。
5. 健保中文名與診所既有中文名可能有語意差異，例如「純高三酸甘油酯血症」與診所「純高甘油脂血症」，後續需 review。

## 9. 本階段輸出

- Dry-run report：`00_icd10_cm_official_reference_staging_dry_run.md`
- Create table 草案：`create_official_icd10_cm_reference_staging.sql`
- Import 腳本草案：`import_official_icd10_cm_reference_staging.py`

本階段沒有建立 table，沒有寫入資料庫。
