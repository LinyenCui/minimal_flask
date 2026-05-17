# ICD ↔ 藥名關聯 v1 完成交接總結

產出時間：2026-05-17

本文件用來記錄 ICD ↔ 藥名雙向查詢 v1 已完成範圍、資料表狀態、驗收結果與下一階段建議，避免後續接手時重複盤點或忘記目前進度。

## 1. v1 完成範圍

已完成第一版 ICD ↔ 藥名關聯功能：

- 建立正式 `drug_items` 表，並從 `drug_items_staging` 安全升正式 152 筆。
- 建立 `drug_diagnosis_links` 關聯表。
- 建立第一批高把握人工 seed links。
- 補齊會直接影響藥名關聯的診斷碼 ICD-10 缺口：
  - `E11.9`：第2型糖尿病，未伴有併發症
  - `E78.5`：高血脂
  - `N40.0`：良性攝護腺肥大
- 新增 Metformin / Insulin 類藥品到 `E11.9` 的高把握關聯。
- `/dx` 已可顯示「主診斷結果 + 相關藥名」。
- `/drug` 已可顯示「主藥名結果 + 相關診斷碼」。
- 完成 10 個雙向查詢驗收案例。

## 2. 修改過的程式檔案

v1 查詢功能相關修改：

- `modules/services/diagnosis_query_service.py`
  - 在診斷碼查詢結果中加入 `related_drugs`。
  - 透過 `drug_diagnosis_links JOIN drug_items` 查詢最多 5 筆相關藥名。

- `modules/handlers/diagnosis_handler.py`
  - `/dx` 回覆格式加入「相關藥名」段落。
  - 保留原本診斷碼主結果格式。

- `modules/services/drug_query_service.py`
  - 在藥名查詢結果中加入 `related_diagnoses`。
  - 透過 `drug_diagnosis_links JOIN diagnosis_codes` 查詢最多 5 筆相關診斷碼。

- `modules/handlers/drug_handler.py`
  - `/drug` 回覆格式加入「相關診斷碼」段落。
  - 保留原本藥名主結果格式。

路由現況：

- `/dx ...` 會先進 `modules.handlers.diagnosis_handler`。
- `/drug ...` 會先進 `modules.handlers.drug_handler`。
- 驗收確認沒有掉進 rewrite/router 或 rewrite/sandbox_handler。

## 3. 新增 / 修改過的資料表

### 新增正式表

- `drug_items`
  - 正式藥名查詢表。
  - 由 `drug_items_staging` 中符合安全規則的資料升正式。

- `drug_diagnosis_links`
  - 藥名與診斷碼關聯表。
  - 用於 `/dx` 顯示相關藥名、`/drug` 顯示相關診斷碼。
  - 主要欄位包含：
    - `drug_item_id`
    - `diagnosis_code_id`
    - `link_type`
    - `role_type`
    - `confidence`
    - `is_primary`
    - `sort_order`
    - `source_type`
    - `note_text`

### 修改正式表

- `diagnosis_codes`
  - 新增 1 筆：
    - id `198`，`E11.9`，`第2型糖尿病，未伴有併發症`
  - 更新 2 筆：
    - id `129`，`高血脂`，補 `icd10_code = E78.5`
    - id `65`，`良性攝護腺肥大`，補 `icd10_code = N40.0`

### staging 表

- `drug_items_staging`
  - 已建立並匯入 Gemini OCR 標準化藥名資料。
  - 本階段未刪除、未清空。

- `diagnosis_icd_mappings_staging`
  - ICD 官方補強候選 staging。
  - 本階段未修改。

## 4. 目前正式表筆數

依 Phase F 驗收結果：

| 表 | 筆數 |
|---|---:|
| `diagnosis_codes` | 198 |
| `drug_items` | 152 |
| `drug_diagnosis_links` | 26 |
| `drug_items_staging` | 173 |
| `diagnosis_icd_mappings_staging` | 18 |

## 5. 目前 seed / link 筆數

`drug_diagnosis_links` 目前共 26 筆。

來源分兩階段：

- Phase A：第一批人工高把握 seed links，共 17 筆。
  - 高血壓：Bisoprolol / Concor、Amlodipine / Norvasc、Irbesartan、Olmesartan 等。
  - 高血脂：Atorvastatin、Rosuvastatin。
  - 良性攝護腺肥大：Tamsulosin。
  - 痛風：Febuxostat、Allopurinol。

- Phase E：糖尿病 links，共 9 筆。
  - Metformin 相關 3 筆。
  - Insulin / 胰島素相關 6 筆。
  - 全部指向 `diagnosis_codes.id = 198` / `E11.9`。

## 6. 通過的 10 個驗收案例

Phase F 驗收 10 個案例全部通過：

| 測試 | 驗收結果 |
|---|---|
| `/dx E11.9` | 有主診斷結果，有 Metformin / Insulin 相關藥名 |
| `/dx 糖尿病` | 有主診斷結果，有 `E11.9` 與相關藥名 |
| `/drug Metformin` | 有主藥名結果，有 `E11.9` 相關診斷碼 |
| `/drug 胰島素` | 有主藥名結果，有 `E11.9` 相關診斷碼 |
| `/dx E78.5` | 有高血脂主診斷，有 Atorvastatin / Rosuvastatin |
| `/drug Rosuvastatin` | 有主藥名結果，有 `E78.5 / 高血脂` |
| `/dx N40.0` | 有良性攝護腺肥大主診斷，有 Tamsulosin |
| `/drug Tamsulosin` | 有主藥名結果，有 `N40.0 / 良性攝護腺肥大` |
| `/dx I10` | 有本態性高血壓主診斷，有 Bisoprolol / Amlodipine 等 |
| `/drug Concor` | 有主藥名結果，有 `I10 / 本態性高血壓` |

驗收報告：

- `db_backups/drug_staging/00_phase_f_bidirectional_query_acceptance_report.md`

## 7. 明確未做事項

以下事項尚未完成，後續不要誤以為已做：

- prescription tables 尚未建立。
- OCR 樣本尚未正式入庫。
- `drug_items_staging` 剩餘 `needs_manual_check=yes` 的 20 筆尚未處理。
- 第二批 `drug_diagnosis_links` 尚未擴充。
- 尚未用處方 OCR 結果建立正式 prescription records。
- 尚未建立 `drug_diagnosis_links` 的大型自動配對流程。
- 尚未建立人工審核 UI 或後台。
- 尚未對所有藥品建立完整適應症關聯。

## 8. 下一階段建議

下一階段先不要急著擴功能。建議順序：

1. 先 commit / 備份目前 v1 成果。
   - 包含程式修改、schema/report 檔案、目前資料庫狀態摘要。
   - 避免後續改動時無法回到 v1 可用狀態。

2. 再處理 `drug_items_staging` 剩下 manual check 的 20 筆。
   - 先人工確認缺漏、錯位、耗材或重複問題。
   - 確認後再決定是否升正式 `drug_items`。

3. 再考慮處方 OCR 樣本如何進 `prescription_*` 或作為第二批 `drug_diagnosis_links` 來源。
   - 先設計 prescription schema。
   - 再決定 OCR 結果是只做 evidence、還是正式處方紀錄。
   - 不建議直接把 OCR 文字自動轉成正式 links。

## 目前最重要結論

ICD ↔ 藥名雙向查詢 v1 已可用，且已通過基本實機驗收。

目前應先穩定保存 v1，再進入人工清理與第二批資料治理；不要在尚未備份或 commit 的狀態下繼續擴大功能面。
