# Phase F ICD ↔ 藥名雙向查詢實機驗收報告

驗收時間：2026-05-17 23:03

本次驗收只執行 `/dx` 與 `/drug` 查詢流程的本地實機測試，不修改任何資料庫資料、不修改 LINE Bot 程式、不修改 staging、OCR 或 prescription tables。

## 驗收範圍

測試項目：

1. `/dx E11.9`
2. `/dx 糖尿病`
3. `/drug Metformin`
4. `/drug 胰島素`
5. `/dx E78.5`
6. `/drug Rosuvastatin`
7. `/dx N40.0`
8. `/drug Tamsulosin`
9. `/dx I10`
10. `/drug Concor`

## 路由確認

`modules/routes/webhook.py` 中 `/dx` 與 `/drug` 會先於 rewrite/router 與 rewrite/sandbox_handler 被專用 handler 攔截：

- `/dx ...` → `modules.handlers.diagnosis_handler`
- `/drug ...` → `modules.handlers.drug_handler`

本次 10 個測試訊息的 trigger 判斷皆為 `True`，沒有掉進 rewrite/router 或 rewrite/sandbox_handler。

## 查詢前後筆數確認

| 表 | 查詢前 | 查詢後 | 是否一致 |
|---|---:|---:|---|
| `diagnosis_codes` | 198 | 198 | 是 |
| `drug_items` | 152 | 152 | 是 |
| `drug_diagnosis_links` | 26 | 26 | 是 |
| `drug_items_staging` | 173 | 173 | 是 |
| `diagnosis_icd_mappings_staging` | 18 | 18 | 是 |

## 驗收結果總表

| 測試 | 主結果 | 關聯結果 | 關鍵驗收內容 | 結果 |
|---|---|---|---|---|
| `/dx E11.9` | 有 | 有相關藥名 | 出現第2型糖尿病、Metformin、Insulin | 通過 |
| `/dx 糖尿病` | 有 | 有相關藥名 | 查到第2型糖尿病，並顯示 Metformin / Insulin 類藥品 | 通過 |
| `/drug Metformin` | 有 | 有相關診斷碼 | 3 筆 Metformin 相關藥品皆顯示 `E11.9` | 通過 |
| `/drug 胰島素` | 有 | 有相關診斷碼 | 查到胰島素品項並顯示 `E11.9` | 通過 |
| `/dx E78.5` | 有 | 有相關藥名 | 高血脂顯示 Atorvastatin / Rosuvastatin | 通過 |
| `/drug Rosuvastatin` | 有 | 有相關診斷碼 | 顯示 `E78.5 / 2724 / 高血脂` | 通過 |
| `/dx N40.0` | 有 | 有相關藥名 | 良性攝護腺肥大顯示 Tamsulosin | 通過 |
| `/drug Tamsulosin` | 有 | 有相關診斷碼 | 顯示 `N40.0 / 6000 / 良性攝護腺肥大` | 通過 |
| `/dx I10` | 有 | 有相關藥名 | 本態性高血壓顯示 Bisoprolol / Amlodipine 等 | 通過 |
| `/drug Concor` | 有 | 有相關診斷碼 | 顯示 `I10 / 401.1 / 401.9 / 本態性高血壓` | 通過 |

## 個別驗收摘要

### 1. `/dx E11.9`

- 主診斷結果：`E11.9 — 第2型糖尿病，未伴有併發症`
- 相關藥名：有
- 看到的關聯藥名包含：
  - `GLIMEPIRIDE 2MG + METFORMIN 50 / Temilg F.C. 甜蜜克`
  - `Dapagliflozin10+Metformin1000m / Xigduo 釋多糖持續性`
  - `Metformin / Metformin 寬樂醣`
  - `INSULIN GLARGINE / TOUJEO 糖德仕 450IU`
  - `Insulin glargine100units+lixis / Soliqua 爽胰達注射劑`

結果：通過。

### 2. `/dx 糖尿病`

- 主診斷結果：有，找到 2 筆「糖尿病」相關診斷碼。
- `E11.9 第2型糖尿病，未伴有併發症` 下方有相關藥名。
- Metformin / Insulin 類關聯已出現。

結果：通過。

### 3. `/drug Metformin`

- 主藥名結果：有，找到 3 筆。
- 每筆皆顯示相關診斷碼：
  - `E11.9 / 第2型糖尿病，未伴有併發症`

結果：通過。Metformin 不再缺糖尿病 link。

### 4. `/drug 胰島素`

- 主藥名結果：有，找到 `Actrapid 愛速基因人體胰島素`。
- 相關診斷碼：
  - `E11.9 / 第2型糖尿病，未伴有併發症`

結果：通過。胰島素不再缺糖尿病 link。

### 5. `/dx E78.5`

- 主診斷結果：`2724 — 高血脂`
- ICD 顯示：`ICD-10: E78.5 | ICD-9: 2724`
- 相關藥名包含：
  - Atorvastatin / Lipitor
  - Atorvastatin / Atorva
  - Rosuvastatin / Rosustin
  - Rosuvastatin / Crestor

結果：通過。statin 類可對到 `E78.5`。

### 6. `/drug Rosuvastatin`

- 主藥名結果：有，找到 2 筆。
- 相關診斷碼：
  - `E78.5 / 2724 / 高血脂`

結果：通過。

### 7. `/dx N40.0`

- 主診斷結果：`6000 — 良性攝護腺肥大`
- ICD 顯示：`ICD-10: N40.0 | ICD-9: 6000`
- 相關藥名包含：
  - Tamsulosin / Harnalidge D 活路利淨
  - Tamsulosin / Tamlosin 暢利淨

結果：通過。Tamsulosin 可對到 `N40.0`。

### 8. `/drug Tamsulosin`

- 主藥名結果：有，找到 2 筆。
- 相關診斷碼：
  - `N40.0 / 6000 / 良性攝護腺肥大`

結果：通過。

### 9. `/dx I10`

- 主診斷結果：`401.1 / 401.9 — 本態性高血壓`
- ICD 顯示：`ICD-10: I10 | ICD-9: 401.1 / 401.9`
- 相關藥名包含：
  - Bisoprolol / Concor
  - Bisoprolol / Biso
  - Amlodipine / Norvasc
  - Irbesartan 相關品項

結果：通過。

### 10. `/drug Concor`

- 主藥名結果：`Concor 康肯`
- 成分：`Bisoprolol`
- 相關診斷碼：
  - `I10 / 401.1 / 401.9 / 本態性高血壓`

結果：通過。

## 驗收結論

第一版 ICD ↔ 藥名雙向關聯功能驗收通過。

已確認：

- `/dx` 有主診斷結果。
- `/dx` 有相關藥名。
- `/drug` 有主藥名結果。
- `/drug` 有相關診斷碼。
- Metformin / Insulin 已能對到 `E11.9` 糖尿病。
- statin 類已能對到 `E78.5` 高血脂。
- Tamsulosin 已能對到 `N40.0` 良性攝護腺肥大。
- I10 / Concor 雙向關聯正常。
- 沒有掉進 rewrite/router 或 rewrite/sandbox_handler。

## 未修改項目

本次驗收未修改：

- `diagnosis_codes`
- `drug_items`
- `drug_diagnosis_links`
- `drug_items_staging`
- `diagnosis_icd_mappings_staging`
- `/dx` 程式
- `/drug` 程式
- LINE Bot 路由與 webhook
- OCR / prescription 相關檔案或資料表

本次只新增此驗收報告檔案。
