# Phase E 新增糖尿病 drug_diagnosis_links 報告

執行時間：2026-05-17

本階段根據 Phase D 已補齊的 `diagnosis_codes.id = 198` / `E11.9`，新增 Metformin 與 Insulin 類藥品到一般第 2 型糖尿病的高把握人工關聯。

未印出 `DATABASE_URL`、密碼或 token。

## 執行前確認

| 項目 | 結果 |
|---|---|
| `diagnosis_codes.id = 198` | 存在，`E11.9`，`第2型糖尿病，未伴有併發症` |
| `diagnosis_codes.id = 129` | 存在，`E78.5`，`高血脂` |
| `diagnosis_codes.id = 65` | 存在，`N40.0`，`良性攝護腺肥大` |
| 新增前 `drug_diagnosis_links` 筆數 | 17 |

## 實際新增結果

| 項目 | 筆數 |
|---|---:|
| Metformin 相關品項找到 | 3 |
| Metformin 成功新增 link | 3 |
| Insulin / 胰島素相關品項找到 | 6 |
| Insulin / 胰島素成功新增 link | 6 |
| skipped duplicate | 0 |
| not found | 0 |
| 實際新增總數 | 9 |
| 新增後 `drug_diagnosis_links` 筆數 | 26 |

## 新增 links 清單

| link_id | drug_item_id | generic_name | brand_name | diagnosis_code_id | ICD-10 | diagnosis_name | confidence |
|---:|---:|---|---|---:|---|---|---|
| 18 | 5 | GLIMEPIRIDE 2MG + METFORMIN 50 | Temilg F.C.  甜蜜克 | 198 | E11.9 | 第2型糖尿病，未伴有併發症 | high |
| 19 | 80 | Dapagliflozin10+Metformin1000m | Xigduo 釋多糖持續性 | 198 | E11.9 | 第2型糖尿病，未伴有併發症 | high |
| 20 | 87 | Metformin | Metformin 寬樂醣 | 198 | E11.9 | 第2型糖尿病，未伴有併發症 | high |
| 21 | 125 | INSULIN GLARGINE | TOUJEO 糖德仕 450IU | 198 | E11.9 | 第2型糖尿病，未伴有併發症 | high |
| 22 | 126 | Insulin glargine100units+lixis | Soliqua 爽胰達注射劑 | 198 | E11.9 | 第2型糖尿病，未伴有併發症 | high |
| 23 | 127 | INSULIN DEGLUDEC 300 U +/- INS | Ryzodeg FlexTouch諾胰得 諾特筆 | 198 | E11.9 | 第2型糖尿病，未伴有併發症 | high |
| 24 | 128 | Human monocomponent Insulin Bi | Actrapid 愛速基因人體胰島素 | 198 | E11.9 | 第2型糖尿病，未伴有併發症 | high |
| 25 | 129 | Insulin degludec | Tresiba FlexTouch 諾胰保諾特筆 | 198 | E11.9 | 第2型糖尿病，未伴有併發症 | high |
| 26 | 130 | Insulin Aspart : Insulin Aspar | NovoMix 30 FlexPen諾和密斯諾易筆 | 198 | E11.9 | 第2型糖尿病，未伴有併發症 | high |

每筆新增 link 使用：

- `link_type = commonly_used_for`
- `role_type = primary_treatment`
- `confidence = high`
- `source_type = manual`
- `is_primary = true`
- `note_text = Phase E: Phase D 補齊 E11.9 後建立的高把握人工關聯。`

## Statin 檢查

Atorvastatin / Rosuvastatin 已正確指向 `diagnosis_codes.id = 129` / `E78.5` / `高血脂`，本階段未重複新增。

| drug_item_id | generic_name | brand_name | link_id | diagnosis_code_id | ICD-10 | diagnosis_name |
|---:|---|---|---:|---:|---|---|
| 24 | Atorvastatin | Lipitor 立普妥 | 9 | 129 | E78.5 | 高血脂 |
| 46 | Rosuvastatin | Rosustin 優脂定 | 11 | 129 | E78.5 | 高血脂 |
| 61 | Atorvastatin | Atorva 立舒脂(立脂妥) | 10 | 129 | E78.5 | 高血脂 |
| 69 | Rosuvastatin | Crestor 冠脂妥(阿斯) | 12 | 129 | E78.5 | 高血脂 |

## Tamsulosin 檢查

Tamsulosin 已正確指向 `diagnosis_codes.id = 65` / `N40.0` / `良性攝護腺肥大`，本階段未重複新增。

| drug_item_id | generic_name | brand_name | link_id | diagnosis_code_id | ICD-10 | diagnosis_name |
|---:|---|---|---:|---:|---|---|
| 18 | Tamsulosin | Harnalidge D 活路利淨 | 13 | 65 | N40.0 | 良性攝護腺肥大 |
| 56 | Tamsulosin | Tamlosin 暢利淨 | 14 | 65 | N40.0 | 良性攝護腺肥大 |

## skipped / duplicate / not found

| 類別 | 清單 |
|---|---|
| duplicate | 無 |
| not found | 無 |
| skipped | 無 |

## 驗證筆數

| 表 | 筆數 |
|---|---:|
| `drug_diagnosis_links` | 26 |
| `drug_items` | 152 |
| `diagnosis_codes` | 198 |
| `drug_items_staging` | 173 |
| `diagnosis_icd_mappings_staging` | 18 |

## 未修改項目清單

本階段未修改：

- `drug_items`
- `diagnosis_codes`
- `/dx` 程式
- `/drug` 程式
- LINE Bot 路由與 webhook
- `drug_items_staging`
- `diagnosis_icd_mappings_staging`
- `diagnosis_icd10_reference_staging`
- OCR / prescription 相關檔案或資料表

本階段未新增：

- statin links
- Tamsulosin links
- prescription tables

## 回滾參考

若需回滾本次 Phase E 新增 links，可刪除 `link_id` 18 至 26，或依條件刪除：

```sql
DELETE FROM drug_diagnosis_links
WHERE diagnosis_code_id = 198
  AND source_type = 'manual'
  AND note_text = 'Phase E: Phase D 補齊 E11.9 後建立的高把握人工關聯。';
```
