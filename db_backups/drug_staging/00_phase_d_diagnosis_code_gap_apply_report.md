# Phase D diagnosis_codes ICD-10 缺口 apply 報告

執行時間：2026-05-17 21:31

本階段依據 `00_phase_d_diagnosis_code_gap_dry_run.md` 執行，允許且僅執行指定的 `diagnosis_codes` 變更：

1. 新增 `E11.9` 一般糖尿病。
2. 更新 id `129`「高血脂」補 `E78.5`。
3. 更新 id `65`「良性攝護腺肥大」補 `N40.0`。

未印出 `DATABASE_URL`、密碼或 token。

## 執行前保護

執行資料變更前，已先建立完整備份表：

| 項目 | 結果 |
|---|---|
| 備份表名稱 | `diagnosis_codes_phase_d_apply_20260517_213120` |
| 備份筆數 | 197 |

執行前也再次確認 `diagnosis_codes.icd10_code` 中不存在：

- `E11.9`
- `E78.5`
- `N40.0`

因此本次沒有重複新增或覆蓋既有 ICD-10。

## 實際變更

| 類型 | 筆數 |
|---|---:|
| INSERT | 1 |
| UPDATE | 2 |
| DELETE | 0 |

## 最終 diagnosis_codes 狀態

| id | ICD-9 | ICD-10 | 中文名稱 | 英文名稱 | additional_codes |
|---:|---|---|---|---|---|
| 198 |  | E11.9 | 第2型糖尿病，未伴有併發症 | Type 2 diabetes mellitus without complications |  |
| 129 | 2724 | E78.5 | 高血脂 |  |  |
| 65 | 6000 | N40.0 | 良性攝護腺肥大 | Benign prostate hypertrophy |  |

### E11.9 新增列補充

新增列保留：

- `icd9_code = NULL`
- `additional_codes = NULL`

新增列另填入：

- `aliases = 第二型糖尿病;糖尿病;type 2 diabetes;diabetes mellitus`
- `is_high_frequency = TRUE`
- `is_handwritten = FALSE`
- `is_deprecated = FALSE`
- `confidence = manual_high`
- `description` 與 `usage_note`：標記此列為 Phase D 新增，用於後續人工建立 Metformin / Insulin 關聯；本階段未自動新增 link。

## 驗證結果

| 項目 | 結果 |
|---|---:|
| `diagnosis_codes` 目前總筆數 | 198 |
| `drug_items` 目前總筆數 | 152 |
| `drug_diagnosis_links` 目前總筆數 | 17 |
| `drug_items_staging` 目前總筆數 | 173 |
| `diagnosis_icd_mappings_staging` 目前總筆數 | 18 |

## 對 drug_diagnosis_links 的影響

本次沒有新增、更新或刪除任何 `drug_diagnosis_links`。

但既有 links 的顯示會受益於 `diagnosis_codes` 補碼：

- 既有 statin links 指向 id `129`「高血脂」，現在可顯示 `E78.5`。
- 既有 Tamsulosin links 指向 id `65`「良性攝護腺肥大」，現在可顯示 `N40.0`。
- Metformin / Insulin links 尚未建立；現在已有 id `198` `E11.9` 作為下一階段候選 link 目標。

## 未修改項目清單

本階段未修改：

- `drug_items`
- `drug_diagnosis_links`
- `drug_items_staging`
- `diagnosis_icd_mappings_staging`
- `diagnosis_icd10_reference_staging`
- 其他 `diagnosis_*` staging 表
- `/dx` 程式
- `/drug` 程式
- LINE Bot 路由與 webhook
- OCR / prescription 相關檔案或資料表

本階段未執行：

- 新增 `E11` 類別碼
- 新增 Metformin / Insulin links
- 修改 `drug_items`
- 修改 `drug_diagnosis_links`
- 刪除任何資料

## 回滾參考

若需回滾本次 Phase D 變更，應先人工確認目前沒有後續流程依賴 id `198` 或新補 ICD-10，再考慮：

- 刪除本次新增的 `diagnosis_codes.id = 198`
- 將 `diagnosis_codes.id = 129` 的 `icd10_code` 還原為 `NULL`
- 將 `diagnosis_codes.id = 65` 的 `icd10_code` 還原為 `NULL`

完整原始狀態可參考備份表：

`diagnosis_codes_phase_d_apply_20260517_213120`
