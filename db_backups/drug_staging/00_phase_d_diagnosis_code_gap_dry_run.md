# Phase D diagnosis_codes ICD-10 缺口 dry run 報告

產出時間：2026-05-17

本報告只依目前資料庫現況做判斷，未查官方網站、未重新下載 ICD 檔、未修改任何資料庫資料、未修改 LINE Bot、未新增 `drug_diagnosis_links`。

## 查詢範圍

唯讀查詢正式表：

- `diagnosis_codes`
- `drug_diagnosis_links`
- `drug_items`

目標 ICD-10：

- `E11`
- `E11.9`
- `E78.5`
- `N40.0`

相近中文診斷關鍵字：

- 糖尿病
- 高血脂
- 高脂血症
- 良性攝護腺肥大
- 攝護腺肥大
- 攝護腺

## ICD-10 現況

| ICD-10 | diagnosis_codes 是否存在 | 判斷 |
|---|---:|---|
| E11 | 否 | 缺。若要支援一般「第二型糖尿病」類別查詢，需要新增或建立 reference；但 E11 偏類別碼，是否作正式診斷列需人工決定。 |
| E11.9 | 否 | 缺。這是 Metformin / Insulin 目前無法建立一般糖尿病 link 的主要缺口。 |
| E78.5 | 否 | 缺。現有 `高血脂` 可疑似對應，但正式 `icd10_code` 尚未補。 |
| N40.0 | 否 | 缺。現有 `良性攝護腺肥大` 可疑似對應，但正式 `icd10_code` 尚未補。 |

## 目前找到的相近 diagnosis_codes

| id | ICD-9 | ICD-10 | 中文名稱 | 英文名稱 | 判斷 |
|---:|---|---|---|---|---|
| 187 | 25060+3572 |  | 糖尿病併多發性神經病變 | Diabetes mellitus with polyneuropathy | 不是一般糖尿病。不可把它更新成 `E11` 或 `E11.9`。 |
| 129 | 2724 |  | 高血脂 |  | 可作 `E78.5` 的候選更新列，需人工確認是否以「未明示高脂血症」處理。 |
| 141 | 2722 |  | 混合性高血脂症 |  | 與高脂血症相關，但語意比 `高血脂` 更窄；不建議用 `E78.5` 覆蓋。 |
| 65 | 6000 |  | 良性攝護腺肥大 | Benign prostate hypertrophy | 可作 `N40.0` 的候選更新列，但需確認是否符合「未伴下泌尿道症狀」。 |
| 92 | 6019 |  | 攝護腺炎 | Prostatitis | 攝護腺相關但不是 BPH；不應對應 `N40.0`。 |
| 93 | 185 |  | 攝護腺癌 | Prostate cancer | 攝護腺相關但不是 BPH；不應對應 `N40.0`。 |

## Dry Run 建議

| 建議動作 | 目標 ICD-10 | 目標 diagnosis_codes | 建議中文名稱 | 建議英文名稱 | 原因 | 風險 |
|---|---|---|---|---|---|---|
| 新增 | E11.9 | 新列 | 第二型糖尿病，未伴有併發症 | Type 2 diabetes mellitus without complications | 目前沒有一般糖尿病列；Metformin / Insulin 不應連到 `糖尿病併多發性神經病變`。 | 中：正式名稱需以院內採用版本或官方 ICD 中文檔再確認。 |
| 暫不直接新增，先人工決定 | E11 | 新列或 reference | 第二型糖尿病 | Type 2 diabetes mellitus | 可提升 `/dx E11` 或「糖尿病」廣義查詢，但 E11 偏類別碼，是否放入正式 `diagnosis_codes` 需先定義表用途。 | 中：若正式表只收可申報明細碼，E11 可能不適合直接新增。 |
| 更新既有列 | E78.5 | id 129 `高血脂` | 高血脂 | Hyperlipidemia, unspecified | `高血脂` 已被 statin links 使用；補上 `E78.5` 可讓 `/drug Atorvastatin/Rosuvastatin` 顯示更完整診斷碼。 | 低至中：需確認診所「高血脂」是否等同未明示高脂血症。 |
| 不建議更新 | E78.5 | id 141 `混合性高血脂症` | 混合性高血脂症 |  | 語意較窄，較可能另有 ICD-10 對應；不應用 `E78.5` 覆蓋。 | 高：可能造成特定診斷被泛化。 |
| 更新既有列，需人工確認 | N40.0 | id 65 `良性攝護腺肥大` | 良性攝護腺肥大 | Benign prostatic hyperplasia without lower urinary tract symptoms | id 65 已被 Tamsulosin links 使用；補上 `N40.0` 可讓 `/drug Tamsulosin` 顯示更完整診斷碼。 | 中：`N40.0` 涉及是否無下泌尿道症狀，目前中文名稱未明示症狀狀態。 |
| 不建議更新 | N40.0 | id 92 `攝護腺炎`、id 93 `攝護腺癌` |  |  | 雖含「攝護腺」，但診斷類型不同。 | 高：錯誤對應會導致藥物關聯失真。 |

## 對 drug_diagnosis_links 的影響

目前既有 links 受影響如下：

| 現有診斷 | diagnosis_code_id | 目前 ICD-10 | 相關藥名 | 影響 |
|---|---:|---|---|---|
| 高血脂 | 129 |  | Atorvastatin、Rosuvastatin | 若 id 129 補 `E78.5`，既有 statin links 不需改 link，即可在 `/drug` 與 `/dx` 顯示 ICD-10。 |
| 良性攝護腺肥大 | 65 |  | Tamsulosin | 若 id 65 補 `N40.0`，既有 Tamsulosin links 不需改 link，即可顯示 ICD-10。 |
| 一般糖尿病 | 尚無合適列 |  | Metformin、Insulin | 需先新增一般糖尿病 diagnosis_codes，例如 `E11.9`；下一階段才能建立 Metformin / Insulin links。 |
| 糖尿病併多發性神經病變 | 187 |  | 目前無 Metformin / Insulin link | 不建議拿來代表一般糖尿病；不應為了 Metformin / Insulin 直接連到此列。 |

## 建議優先順序

1. 先人工確認是否將 id 129 `高血脂` 補為 `E78.5`。
2. 再人工確認是否將 id 65 `良性攝護腺肥大` 補為 `N40.0`，特別確認是否接受「未伴下泌尿道症狀」語意。
3. 新增一筆一般糖尿病 `E11.9`，作為 Metformin / Insulin 的高把握 link 目標。
4. `E11` 暫時不要直接寫入正式 `diagnosis_codes`，除非決定正式表允許收類別碼；可先作為 alias/reference 或之後另建 ICD reference 表。

## 本階段未執行的事項

- 未 INSERT、UPDATE、DELETE 任何資料庫資料。
- 未修改 `diagnosis_codes`。
- 未修改 `drug_items`。
- 未修改 `drug_diagnosis_links`。
- 未修改任何 staging 表。
- 未修改 `/dx` 或 `/drug` 程式。
- 未建立 SQL 腳本。
- 未新增 Metformin / Insulin links。

## 下一步建議

下一階段可先產生一份人工核准清單，內容只包含：

- `diagnosis_codes.id = 129` 補 `icd10_code = E78.5`
- `diagnosis_codes.id = 65` 補 `icd10_code = N40.0`
- 新增 `E11.9` 一般糖尿病診斷列
- `E11` 是否新增正式列或只作 reference 的決策

正式 apply 前建議再次備份 `diagnosis_codes`，並用單獨腳本限制只允許更新上述 id 或新增經核准的新列。
