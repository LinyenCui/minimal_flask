# ICD ↔ 藥名關聯查詢 v1/v2 交接文件

產出日期：2026-05-18

本文件供下一個 ChatGPT 對話或後續開發者快速接手。讀完本檔後，應能理解目前 ICD ↔ 藥名查詢做到哪裡、哪些檔案被改過、正式資料表目前狀態、已驗收案例、未完成事項，以及下一階段 v3 最小可行方向。

## 1. 專案位置與分支

- 工作目錄：`/Users/linyancui/minimal_flask`
- 主要分支：`dev_line_channel`
- 已完成並 push 的 commit：
  - `b7c1ad8 Complete ICD drug bidirectional query v1`
  - `4f4849d Add read-only Flex display for ICD drug queries`

v1 / v2 界線：

- v1：ICD ↔ 藥名雙向文字查詢閉環。
  - `/dx` 可查診斷碼主結果，並顯示相關藥名。
  - `/drug` 可查藥名主結果，並顯示相關診斷碼。
  - `drug_diagnosis_links` 已建立並有第一批人工高把握關聯。

- v2：read-only Flex 顯示改善。
  - `/dx` 單筆結果可回 Flex bubble。
  - `/drug` 查到藥品時可回 Flex bubble / carousel。
  - 原文字版 fallback 仍保留。

## 2. 目前完成狀態總覽

| 項目 | 目前狀態 |
|---|---|
| `drug_items` | 152 筆正式藥名 |
| `diagnosis_codes` | 198 筆正式診斷碼 |
| `drug_diagnosis_links` | 26 筆關聯 |
| `/dx` | 診斷碼主結果 + 相關藥名 |
| `/drug` | 藥名主結果 + 相關診斷碼 |
| `/dx` 單筆 | read-only Flex bubble |
| `/dx` 多筆 / empty / error / help | 文字版 fallback |
| `/drug` 查到藥品 | read-only Flex bubble / carousel |
| `/drug` empty / error / help | 文字版 fallback |
| 文字 fallback | 仍保留，Flex 失敗時也會回文字版 |

目前 v1/v2 只做查詢與顯示，沒有做 link 維護 UI，也沒有把 OCR / prescription 資料正式入庫。

## 3. v1 已完成內容

### `/dx` 查詢流程

`/dx` 由以下檔案處理：

- route dispatch：`modules/routes/webhook.py`
- handler：`modules/handlers/diagnosis_handler.py`
- service：`modules/services/diagnosis_query_service.py`

流程：

1. `modules/routes/webhook.py` 先判斷訊息是否符合 `/dx`、`dx`、`碼` 等前綴。
2. 命中後直接進 `handle_diagnosis_message()`。
3. `DiagnosisQueryService.search(query)` 查 `diagnosis_codes`。
4. 查到的 diagnosis code 會被 `_enrich()` 補上：
   - chapters
   - components
   - notes
   - related_drugs
5. `related_drugs` 透過 `diagnosis_codes.id` join `drug_diagnosis_links` 再 join `drug_items`。
6. handler 格式化回覆。

`/dx` join 方向：

```text
diagnosis_codes.id
  → drug_diagnosis_links.diagnosis_code_id
  → drug_diagnosis_links.drug_item_id
  → drug_items.id
```

SQL 邏輯重點：

- 只讀查詢。
- 每個 diagnosis 最多顯示 5 筆相關藥名。
- 排序：
  - `is_primary DESC`
  - `confidence high > medium > low`
  - `sort_order ASC`
  - `drug_items.generic_name / brand_name ASC`

### `/drug` 查詢流程

`/drug` 由以下檔案處理：

- route dispatch：`modules/routes/webhook.py`
- handler：`modules/handlers/drug_handler.py`
- service：`modules/services/drug_query_service.py`

流程：

1. `modules/routes/webhook.py` 先判斷訊息是否符合 `/drug`、`drug`、`藥`、`藥名` 等前綴。
2. 命中後直接進 `handle_drug_message()`。
3. `DrugQueryService.search(query)` 查正式表 `drug_items`。
4. 每筆 drug item 會被 `_normalize_row()` 補上 `related_diagnoses`。
5. `related_diagnoses` 透過 `drug_items.id` join `drug_diagnosis_links` 再 join `diagnosis_codes`。
6. handler 格式化回覆。

`/drug` join 方向：

```text
drug_items.id
  → drug_diagnosis_links.drug_item_id
  → drug_diagnosis_links.diagnosis_code_id
  → diagnosis_codes.id
```

SQL 邏輯重點：

- 只讀查詢。
- 每個藥品最多顯示 5 筆相關診斷碼。
- 排序：
  - `is_primary DESC`
  - `confidence high > medium > low`
  - `sort_order ASC`
  - `diagnosis_codes.icd10_code ASC`
  - `diagnosis_codes.icd9_code ASC`

### 三張核心表的關係

```text
drug_items
  id
   │
   │ drug_diagnosis_links.drug_item_id
   ▼
drug_diagnosis_links
  drug_item_id
  diagnosis_code_id
   ▲
   │ drug_diagnosis_links.diagnosis_code_id
   │
diagnosis_codes
  id
```

`drug_items` 是正式藥名表，供 `/drug` 主查詢。

`diagnosis_codes` 是正式診斷碼表，供 `/dx` 主查詢。

`drug_diagnosis_links` 是雙向關聯表，讓 `/dx` 能找藥、`/drug` 能找診斷碼。

## 4. v2 已完成內容

v2 只改善 read-only 顯示，不改資料庫、不新增維護功能。

### `/dx` Flex

- `/dx` 單筆結果使用 read-only Flex bubble。
- 參考既有客戶詳情卡 label/value 風格。
- 顯示內容：
  - 診斷名稱
  - ICD-10
  - ICD-9
  - 中文名
  - 英文名若有
  - 章節 / 分類 / 備註摘要
  - 相關藥名最多 5 筆
- 相關藥名顯示：
  - `generic_name / brand_name`
  - `confidence`
  - `source_type`
  - `role_type`
- 不在 Flex 顯示過長 `note_text`；完整 note 留在文字 fallback。

`/dx` 以下情境保留文字 fallback：

- 多筆查詢結果，例如 `/dx 糖尿病`
- empty
- error
- help
- chapters
- table 結果

Flex 建立或送出失敗時，會回原文字版。

### `/drug` Flex

- `/drug` 查到藥品時使用 read-only Flex。
- 1 筆：single bubble。
- 多筆：carousel，最多 10 張 bubble，和文字版上限一致。
- 參考既有固定班次「每筆一張 bubble」風格。
- 每張 drug bubble 顯示：
  - `generic_name / brand_name`
  - `table_type`
  - `item_kind`
  - `category`
  - `supplier` 若有
  - `manufacturer` 若有
  - 相關診斷碼最多 5 筆
- 相關診斷碼顯示：
  - `ICD-10 / ICD-9 / name_zh`
  - `confidence`
  - `source_type`
  - `role_type`
- 不在 Flex 顯示過長 `note_text`；完整 note 留在文字 fallback。

`/drug` 以下情境保留文字 fallback：

- 查無資料
- help
- error

Flex 建立或送出失敗時，會回原文字版。

## 5. 修改過的主要程式檔案

| 檔案 | 用途 |
|---|---|
| `modules/services/diagnosis_query_service.py` | `/dx` 查詢 service；查 `diagnosis_codes`，並用 `diagnosis_codes.id` 讀取 `related_drugs`。 |
| `modules/handlers/diagnosis_handler.py` | `/dx` handler；v1 格式化文字版；v2 單筆結果優先回 Flex，失敗 fallback 文字版。 |
| `modules/services/drug_query_service.py` | `/drug` 查詢 service；查 `drug_items`，並用 `drug_items.id` 讀取 `related_diagnoses`。 |
| `modules/handlers/drug_handler.py` | `/drug` handler；v1 格式化文字版；v2 查到藥品時優先回 Flex bubble / carousel，失敗 fallback 文字版。 |
| `modules/routes/webhook.py` | LINE webhook routing；在 rewrite/router、sandbox_handler 之前先攔截 `/dx` 與 `/drug`。 |
| `modules/views/diagnosis_flex.py` | v2 新增；read-only diagnosis detail Flex renderer。 |
| `modules/views/drug_flex.py` | v2 新增；read-only drug bubble / carousel renderer。 |

## 6. 資料表現況

### `drug_items`

- 目前正式筆數：152 筆。
- 來源 batch：`gemini_drug_cab1833de552`。
- `/drug` 主查詢資料來源。
- `drug_diagnosis_links.drug_item_id` 的 FK 目標。
- 目前只收安全升正式的藥名資料。
- `drug_items_staging` 尚有未人工處理資料，見未完成事項。

### `diagnosis_codes`

- 目前正式筆數：198 筆。
- `/dx` 主查詢資料來源。
- `drug_diagnosis_links.diagnosis_code_id` 的 FK 目標。

本輪補入或補碼：

| ICD-10 | 中文名稱 | 說明 |
|---|---|---|
| `E11.9` | 第2型糖尿病，未伴有併發症 | Phase D 新增，用於 Metformin / Insulin 關聯。 |
| `E78.5` | 高血脂 | Phase D 補到既有 id 129。 |
| `N40.0` | 良性攝護腺肥大 | Phase D 補到既有 id 65。 |

Phase D apply 前建立的備份表：

- `diagnosis_codes_phase_d_apply_20260517_213120`

### `drug_diagnosis_links`

- 目前正式筆數：26 筆。
- 用於 `/dx` 與 `/drug` 雙向關聯查詢。

核心欄位：

- `id`
- `drug_item_id`
- `diagnosis_code_id`
- `link_type`
- `role_type`
- `confidence`
- `is_primary`
- `sort_order`
- `source_type`
- `note_text`
- `created_at`
- `updated_at`

目前主要值：

- `link_type = commonly_used_for`
- `role_type = primary_treatment`
- `source_type = manual`
- `confidence = high / medium`

約束設計：

- FK：
  - `drug_item_id → drug_items(id)`
  - `diagnosis_code_id → diagnosis_codes(id)`
- Unique：
  - `drug_item_id, diagnosis_code_id, link_type, role_type`

## 7. 已建立的主要關聯

目前第一批高把握 links 包含：

| 藥品 / 成分 | 診斷碼 / 診斷 | 說明 |
|---|---|---|
| Metformin | `E11.9` 第2型糖尿病，未伴有併發症 | Phase E 新增，3 筆 Metformin 相關品項。 |
| Insulin / 胰島素 | `E11.9` 第2型糖尿病，未伴有併發症 | Phase E 新增，6 筆 Insulin 相關品項。 |
| Atorvastatin / Rosuvastatin | `E78.5` 高血脂 | Phase A seed，Phase D 後 id 129 已補 ICD-10。 |
| Tamsulosin | `N40.0` 良性攝護腺肥大 | Phase A seed，Phase D 後 id 65 已補 ICD-10。 |
| Bisoprolol / Concor | `I10` 本態性高血壓 | Phase A seed。 |
| Amlodipine / Norvasc | `I10` 本態性高血壓 | Phase A seed。 |
| Doxazosin | `I10` 本態性高血壓 | Phase A seed，confidence medium。 |
| Irbesartan / Aprovel | `I10` 本態性高血壓 | Phase A seed。 |
| Olmesartan / Olmetec | `I10` 本態性高血壓 | Phase A seed。 |
| Febuxostat / Allopurinol | 痛風 | Phase A seed。 |

補充：

- Phase A 時 `E11.9` 尚不存在，因此 Metformin / Insulin links 暫緩。
- Phase D 補入 `E11.9` 後，Phase E 才新增糖尿病 links。

## 8. Phase A 到 Phase H 歷程

### Phase A

- 建立 `drug_diagnosis_links`。
- 加 FK：
  - `drug_item_id → drug_items(id)`
  - `diagnosis_code_id → diagnosis_codes(id)`
- 加 unique constraint：
  - `drug_item_id, diagnosis_code_id, link_type, role_type`
- 新增 17 筆 manual seed。
- 當時發現：
  - Metformin / Insulin 找得到藥，但缺一般糖尿病 `E11/E11.9`，所以未建立 link。
  - `E78.5` 不在 `diagnosis_codes`，statin 暫時連到現有 `高血脂`。
  - `N40.0` 不在 `diagnosis_codes`，Tamsulosin 暫時連到現有 `良性攝護腺肥大`。

報告：

- `db_backups/drug_staging/00_drug_diagnosis_links_phase_a_seed_report.md`

### Phase B

- 升級 `/dx`：
  - 保留診斷碼主結果。
  - 在診斷碼下方顯示 `drug_diagnosis_links` 的相關藥名。
- 只讀查詢：
  - `diagnosis_codes.id → drug_diagnosis_links → drug_items`
- 不修改資料庫資料。

### Phase C

- 升級 `/drug`：
  - 保留藥名主結果。
  - 在藥名下方顯示 `drug_diagnosis_links` 的相關診斷碼。
- 只讀查詢：
  - `drug_items.id → drug_diagnosis_links → diagnosis_codes`
- 不修改資料庫資料。

### Phase D

- 先 dry run 查 `diagnosis_codes` 缺口。
- 確認 `E11.9`、`E78.5`、`N40.0` 都缺。
- apply 時允許只修改 `diagnosis_codes` 的 3 項：
  - 新增 `E11.9`：第2型糖尿病，未伴有併發症。
  - 更新 id 129 `高血脂` 補 `E78.5`。
  - 更新 id 65 `良性攝護腺肥大` 補 `N40.0`。
- apply 前建立備份表：
  - `diagnosis_codes_phase_d_apply_20260517_213120`

Reports：

- `db_backups/drug_staging/00_phase_d_diagnosis_code_gap_dry_run.md`
- `db_backups/drug_staging/00_phase_d_diagnosis_code_gap_apply_report.md`

### Phase E

- 新增 Metformin / Insulin 到 `E11.9` 的 links。
- 實際新增 9 筆：
  - Metformin 相關 3 筆。
  - Insulin / 胰島素相關 6 筆。
- 新增後 `drug_diagnosis_links` 從 17 筆變 26 筆。
- statin 與 Tamsulosin 既有 links 已正確指向 id 129 / id 65，未重複新增。

Report：

- `db_backups/drug_staging/00_phase_e_add_diabetes_links_report.md`

### Phase F

- 做 ICD ↔ 藥名雙向查詢實機驗收。
- 10 個案例全部通過。
- 確認：
  - `/dx` 有主診斷結果。
  - `/dx` 有相關藥名。
  - `/drug` 有主藥名結果。
  - `/drug` 有相關診斷碼。
  - 沒有掉進 rewrite/router 或 sandbox_handler。
  - 查詢前後正式表與 staging 筆數一致。

Report：

- `db_backups/drug_staging/00_phase_f_bidirectional_query_acceptance_report.md`

### Phase G

- 新增 `/dx` 單筆 read-only Flex bubble。
- 多筆、empty、error、help、table 保留文字 fallback。
- Flex 建立或送出失敗時回文字版。
- 參考客戶詳情卡 label/value 風格。

Report：

- `db_backups/drug_staging/00_phase_g_dx_flex_readonly_report.md`

### Phase H

- 新增 `/drug` read-only Flex bubble / carousel。
- 1 筆結果：bubble。
- 多筆結果：carousel，最多 10 張。
- empty、help、error 保留文字 fallback。
- Flex 建立或送出失敗時回文字版。
- 參考固定班次每筆一張 carousel 風格。

Report：

- `db_backups/drug_staging/00_phase_h_drug_flex_readonly_report.md`

## 9. 驗收案例

Phase F 通過的 10 個案例：

- `/dx E11.9`
- `/dx 糖尿病`
- `/drug Metformin`
- `/drug 胰島素`
- `/dx E78.5`
- `/drug Rosuvastatin`
- `/dx N40.0`
- `/drug Tamsulosin`
- `/dx I10`
- `/drug Concor`

驗收確認：

- `/dx` 有主診斷結果。
- `/dx` 有相關藥名。
- `/drug` 有主藥名結果。
- `/drug` 有相關診斷碼。
- Metformin / Insulin 不再缺糖尿病 link。
- statin 類能對到 `E78.5`。
- Tamsulosin 能對到 `N40.0`。
- I10 / Concor 雙向關聯正常。
- 沒有掉進 rewrite/router 或 sandbox_handler。
- 查詢前後正式表與 staging 筆數一致。

Phase G 補充驗收：

- `/dx I10`：單筆，Flex JSON 可解析，有相關藥名。
- `/dx E11.9`：單筆，Flex JSON 可解析，有 Metformin / Insulin 相關藥名。
- `/dx 糖尿病`：多筆，維持文字版，有相關藥名。
- `/dx 不存在XYZ`：empty，維持文字版。

Phase H 補充驗收：

- `/drug Concor`：1 筆，Flex bubble 可解析，有 I10 相關診斷碼。
- `/drug Metformin`：3 筆，Flex carousel 可解析，有 E11.9 相關診斷碼。
- `/drug 胰島素`：1 筆，Flex bubble 可解析，有 E11.9 相關診斷碼。
- `/drug 不存在XYZ`：empty，維持文字版。

## 10. 已完成收尾文件

已完成或應參考的文件：

- `db_backups/drug_staging/00_icd_drug_link_v1_completion_summary.md`
  - v1 完成範圍、資料表、驗收與下一步建議。

- `db_backups/drug_staging/00_liff_flex_ui_reference_inventory.md`
  - 既有 LIFF / Flex / LINE UI 盤點。
  - 目前可能尚未 commit，但它是 v3 LIFF 維護表單的重要參考。

- `db_backups/drug_staging/00_icd_drug_link_v1_v2_handoff_for_next_chat.md`
  - 本檔。
  - 建議下一個 ChatGPT 對話先讀本檔，再讀細部 Phase reports。

## 11. 未完成事項

### `drug_items_staging` 剩餘 manual check

- `drug_items_staging`：173 筆。
- `drug_items`：152 筆。
- `needs_manual_check` 約 20 筆。
- 尚未做：
  - approve
  - duplicate
  - ignore
  - consumable 是否升正式
  - suspected_shift 是否修正

目前不應把剩餘 staging 直接升正式。

### prescription tables 尚未建立

目前未見正式 prescription tables：

- `prescription_examples`
- `prescription_items`
- `prescription_diagnoses`
- `prescription_photos`

處方資料模型尚未設計完成，不應在 v3 link 維護同時處理。

### OCR 樣本尚未入庫

- 處方 OCR 目前仍停在 workbench / report / CSV 層。
- 尚未轉成正式 prescription records。
- 尚未轉成 `source_type = prescription_sample` 的第二批 `drug_diagnosis_links`。
- OCR 結果仍應視為 evidence，不應直接自動寫正式 links。

### `drug_diagnosis_links` 維護 UI 尚未做

尚未有：

- 新增 link 的 LIFF 管理介面。
- 編輯 link 的 LIFF 管理介面。
- 停用 / 刪除 link 的審核流程。
- link review history。
- link source evidence viewer。

目前 links 都是人工高把握 seed，但缺後續管理工具。

## 12. 下一階段建議

建議下一階段是 v3：

## v3：`drug_diagnosis_links` 維護 LIFF

最小可行範圍：

1. LIFF 頁面列出現有 `drug_diagnosis_links`。
2. 可搜尋 `drug_items`。
3. 可搜尋 `diagnosis_codes`。
4. 可新增一筆 link。
5. 欄位包含：
   - `drug_item_id`
   - `diagnosis_code_id`
   - `link_type`
   - `role_type`
   - `confidence`
   - `is_primary`
   - `sort_order`
   - `source_type`
   - `note_text`
6. 寫入前有確認畫面。
7. 寫入後可立即用 `/dx` 或 `/drug` 查到。

建議 v3 借用既有 LIFF 模式：

- dispatcher：`/liff/customer/form?form=...`
- auth：`@liff_auth_required`
- URL round-trip：`rewrite/utils/liff_url.py`
- preview / confirm / apply：參考 `templates/liff/import_form.html`
- 後端 JSON API：參考 `rewrite/handlers/liff/import_form.py`
- Flex / Quick Reply LIFF 入口：參考 `rewrite/views/import_flex.py`

v3 不要同時做：

- OCR 入庫。
- prescription tables。
- 大量自動配對。
- `drug_items_staging` 清理。
- 改派班記帳主線。
- 重構 `/dx` / `/drug` 查詢核心。

理由：

- v1/v2 已形成穩定查詢閉環。
- v3 應專注在人工 link 維護，不要把資料治理、OCR、處方 schema 與 UI 管理混在同一批。

## 13. 下一個對話建議開場指令

可直接貼到下一個 ChatGPT 對話：

```text
請先讀取：
/Users/linyancui/minimal_flask/db_backups/drug_staging/00_icd_drug_link_v1_v2_handoff_for_next_chat.md

請不要先修改程式或資料庫。
請先唯讀確認目前 repo、branch、最近 commit、/dx、/drug、drug_diagnosis_links schema、LIFF dispatcher。

目前狀態：
- v1 已完成 ICD ↔ 藥名雙向文字查詢閉環。
- v2 已完成 read-only Flex 顯示。
- 下一階段想做 v3：drug_diagnosis_links 維護 LIFF。

請先只提出 v3 最小實作計畫：
1. 需要新增哪些 LIFF endpoint / template / view
2. 如何搜尋 drug_items 與 diagnosis_codes
3. 如何 preview / confirm / apply 新增 link
4. 如何避免修改 drug_items、diagnosis_codes、staging、OCR、prescription tables
5. 如何測試新增後 /dx 與 /drug 能立即查到

限制：
- 不要使用 git add -A
- 不要碰 OCR / prescription tables
- 不要大量自動配對
- 不要改派班記帳主線
- 先只做 plan，不要直接實作
```

## 14. Git 注意事項

- 不要使用 `git add -A`。
- 目前 repo 仍有不少 untracked backup / staging / reference / scripts。
- 之後 commit 要精準指定檔案。
- v1 / v2 已經 push。
- 若要整理未追蹤檔案，請另開 docs / cleanup commit，不要混入 v3 功能。

已知 v1 / v2 commits：

```text
b7c1ad8 Complete ICD drug bidirectional query v1
4f4849d Add read-only Flex display for ICD drug queries
```

建議未來 commit 分界：

- v3 plan / docs：只收 planning docs。
- v3 LIFF implementation：只收 LIFF endpoints、template、view、tests。
- staging cleanup：另開 commit。
- OCR / prescription schema：另開 commit。

## 最後提醒

目前 v1/v2 的定位很清楚：

- v1 是功能閉環。
- v2 是顯示改善。
- v3 才應該進入人工維護 UI。

下一步不要急著擴功能，先確保下一個對話或開發者能完整理解本檔，並以最小範圍推進 `drug_diagnosis_links` 維護 LIFF。
