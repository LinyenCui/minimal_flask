# 處方匯入 Phase 1 — Schema Plan（手動輸入 candidate + review）

- 版本：v1 草案（2026-05-25）
- 對應：`00_prescription_import_liff_plugin_design.md` 的 Phase 1。
- 範圍：**只支援「手動輸入 candidate + review」**；尚不做照片 OCR apply，**不直接寫 customers / diagnosis_codes / drug_items**。
- SQL 草案：`create_prescription_import_phase1_tables.sql`（審閱用；**本輪未執行**）。
- 性質：設計/SQL 檔；**未建表、未寫 DB、未執行 SQL、未改正式表、未 git**。

---

## 1. 每張表用途

| # | 表 | 用途 | 階段 |
|---|---|---|---|
| A | `prescription_import_batches` | 一批匯入流程（manual/photo_ocr/mixed），以 status 管生命週期 | Phase 1 |
| B | `prescription_customer_candidates` | 候選病人資料（手動或 OCR） | Phase 1 |
| C | `prescription_diagnosis_candidates` | 候選診斷碼 / ICD | Phase 1 |
| D | `prescription_drug_candidates` | 候選藥品 / 健保碼 | Phase 1 |
| E | `prescription_import_review_actions` | 人工審核 / apply / rollback 的 audit trail | Phase 1 |
| F | `prescription_drug_diagnosis_link_candidates` | 候選藥↔診斷關聯 | **Phase 1 OPTIONAL / Phase 2 才啟用** |

> 全部為 staging / 流程表，與正式表分離；正式表只在日後「approved-only apply」被 additive 寫入。

---

## 2. 欄位說明（重點）

- **共通**：`id`(BIGINT identity PK)、`batch_id`、`source_type`(manual/photo_ocr)、`source_photo_id`(Phase 2 用，Phase 1 恆 NULL)、`review_status`、`review_decision`、`match_status`、`confidence`、`note`、`created_at`/`updated_at`(TIMESTAMPTZ；**無 trigger，由 app 維護 updated_at**)。
- **A batches**：`import_source`、`batch_status`(draft→reviewing→ready_to_apply→applied／cancelled)、`created_by_line_user_id`/`created_by_display_name`、`note`。
- **B customer**：`raw_name` / `proposed_name` / `proposed_short_name` / `proposed_birthday`(DATE) / `proposed_gender`(M/F/unknown) / `proposed_address`(不設 DB default「門診」) / `matched_customer_id`(→customers)。
- **C diagnosis**：`raw_icd_code` / `normalized_icd_code` / `raw_diagnosis_name` / `proposed_icd10_code` / `proposed_name_zh` / `proposed_name_en` / `matched_diagnosis_code_id`(→diagnosis_codes) / `official_match_status`。
- **D drug**：`raw_/normalized_/corrected_nhi_drug_code` + `effective_nhi_drug_code`（**STORED generated = COALESCE(corrected, normalized, raw)**）、`raw_drug_name` / `proposed_generic_name` / `proposed_brand_name`、official 欄(`official_drug_name_zh/_en`、`official_ingredient`、`official_atc_code`)、`matched_drug_item_id`(→drug_items)、`matched_official_mapping_id`(→drug_item_official_code_mappings)、`nhi_code_candidate_id`(→既有 prescription_nhi_drug_code_candidates)、`official_join_status`。
- **E review_actions**：`candidate_type`(customer/diagnosis/drug/link)、`candidate_id`(多型，無 FK)、`action`、`before_json`/`after_json`(JSONB)、`reviewer_*`、`note`、`created_at`。
- **F link（optional）**：`drug_candidate_id`、`diagnosis_candidate_id`、`matched_drug_item_id`、`matched_diagnosis_code_id`、`source_type`(same_prescription/manual)、`link_confidence`、review_*。

> `effective_nhi_drug_code` 用 generated STORED，避免欄位漂移；要覆寫請改 `corrected_nhi_drug_code`。若日後需手動指定任意 effective，可改為一般欄位（本檔已標明）。

---

## 3. CHECK constraint 建議（enum-like）

- `import_source ∈ {manual, photo_ocr, mixed}`；`batch_status ∈ {draft, reviewing, ready_to_apply, applied, cancelled}`
- `source_type ∈ {manual, photo_ocr}`（link 表：`{same_prescription, manual}`）
- `proposed_gender ∈ {M, F, unknown}`（NULL 允許）
- `match_status ∈ {exact_match, possible_match, no_match, blocked}`
- `review_status ∈ {pending, approved, edited, rejected, hold}`
- `review_decision`：customer `{create, link_existing, skip_existing, hold, reject}`；diagnosis `{create_diagnosis, link_existing, skip_existing, hold, reject}`；drug `{link_drug_item, backfill_nhi_code, create_mapping, skip_existing, hold, reject}`；link `{create_link, hold, reject}`（NULL＝尚未決策）
- `official_match_status` / `official_join_status ∈ {pending, matched, no_match, ambiguous}`
- `confidence` / `link_confidence ∈ {high, medium, low, unknown}`（NULL 允許）
- `candidate_type ∈ {customer, diagnosis, drug, link}`；`action ∈ {approve, edit, hold, reject, apply, rollback, create, set_decision}`

---

## 4. Index 建議

- batches：`(batch_status)`、`(created_by_line_user_id)`
- 各 candidate：`(batch_id)`、`(batch_id, review_status)`（待確認清單主查詢）、`(match_status)` 或對應 matched_id；drug 另加 `(effective_nhi_drug_code)`、`(nhi_code_candidate_id)`；diagnosis 另加 `(normalized_icd_code)`
- review_actions：`(batch_id)`、`(candidate_type, candidate_id)`、`(created_at)`
- link：`(batch_id)`、`(drug_candidate_id)`、`(diagnosis_candidate_id)`

---

## 5. FK 建議（刻意不過硬）

- **內部 staging**：`*.batch_id → prescription_import_batches(id)` NOT NULL，**ON DELETE RESTRICT**（批次以 status=cancelled 軟退場，不硬刪 → 不需 cascade）。
- **到正式表**：`matched_customer_id→customers(id)`、`matched_diagnosis_code_id→diagnosis_codes(id)`、`matched_drug_item_id→drug_items(id)`、`matched_official_mapping_id→drug_item_official_code_mappings(id)`、`nhi_code_candidate_id→prescription_nhi_drug_code_candidates(id)`：**全部 NULLABLE + ON DELETE SET NULL**（未比對到也能存；正式表列被刪不連帶刪暫存）。
- **型別對齊**：customers.id / diagnosis_codes.id = INTEGER；drug_items.id / mappings.id / prescription_nhi_drug_code_candidates.id = BIGINT（FK 欄位型別已對應，避免建立失敗）。
- **多型參照**：`review_actions.candidate_id` 刻意**不設 FK**（依 candidate_type 指不同表），完整性由 app 維護。
- **link（Phase 2）**：`drug_candidate_id`/`diagnosis_candidate_id → candidate(id)` 用 **ON DELETE CASCADE**（derived 連結資料，端點不在則連結無意義）——全檔唯一 CASCADE，已標明，若你偏好 RESTRICT/SET NULL 可調整。

---

## 6. 為什麼不放 national_id / phone / chart_no

- **scope-to-schema**：目標正式表（customers 等）不需要也不該存這些；customers 早已 drop national_id（migration 004：「個資麻煩 + 沒地方用」）。
- **隱私 / 風險最小化**：身分證、電話、病歷號屬敏感個資，從**源頭（表結構與表單）就排除**，避免暫存層意外留存或外洩；處方箋上即使有也不抽不存。
- 結果：candidate 表只承載目標表需要的最小欄位集，audit 也不會記到敏感欄。

---

## 7. 如何支援 manual input

- 手動建批次（`import_source='manual'`）→ 表單逐筆新增 candidate（`source_type='manual'`、`source_photo_id=NULL`）。
- 表單欄位即 `proposed_*`（病人 name/short_name/birthday/gender/address；診斷 icd/name；藥品 nhi_code/drug_name/generic/brand）；`raw_*` 可存使用者原始輸入。
- 入庫後系統自動唯讀 match 回填 `match_status`/`matched_*_id`、`official_*_status`；reviewer 在待確認清單設 `review_status`/`review_decision`，每步寫 `review_actions`。
- CHECK 限制 enum，但允許 `proposed_*` 留空（暫存可保存、不擋）。

---

## 8. 如何支援未來 photo OCR 預填

- OCR job 解析照片後，以 `source_type='photo_ocr'` 寫入相同 candidate 表，並填 `raw_*`（OCR 原讀）、`proposed_*`（正規化）、`confidence`、`note`。
- `source_photo_id` 已預留（Phase 2 建 `prescription_import_photos` 後再加 FK；Phase 1 先當 nullable BIGINT、恆 NULL）。
- 因 OCR 與 manual 寫入**同一組表 + 同一 review/apply 流程**，UI 與 apply 完全共用，只靠 `source_type` 區分。

---

## 9. 如何與正式表對接（approved-only apply 時）

| candidate | 對接正式表 | 對接方式 |
|---|---|---|
| customer | `customers` | `create`＝additive INSERT（不覆蓋）；`link_existing`＝沿用 matched_customer_id；`skip_existing`＝不寫 |
| diagnosis | `diagnosis_codes` | `link_existing`＝用 matched id；`create_diagnosis`＝additive 新增（補缺 ICD，沿用 id198 教訓） |
| drug | `drug_items` | `link_drug_item`＝對應；`backfill_nhi_code`＝回填 `nhi_drug_code` 五欄（不覆蓋既有正確碼） |
| drug↔official | `drug_item_official_code_mappings` | `create_mapping`＝建立對應（matched_official_mapping_id 供參） |
| drug↔diagnosis | `drug_diagnosis_links` | 由 F link 候選 `create_link`（Phase 2） |
| 既有抽取層 | `prescription_nhi_drug_code_candidates` | drug candidate 以 `nhi_code_candidate_id` FK 指回**原始健保碼抽取層**（沿用、不重抽；保留來源溯源） |

> 對接全部在**未來的 apply 階段**才發生；本 Phase 只建表 + 存 candidate + review。

---

## 10. apply 流程（不在本階段實作）

- 寫正式表一律走：**dry-run（預覽將執行動作 + 欄位驗證 + 重複/缺漏/blocker）→ backup（`*_backup_<ts> AS TABLE`）→ 單一交易 apply（只 INSERT/backfill/建連結，失敗整批 rollback）→ verify（count 正確、既有未變、抽樣正常）**。
- 只處理 `review_status=approved` 的 candidate；apply/rollback 寫 `review_actions`。
- **production 另行同步**（preflight/backup/gated apply/verify，重用 `render_tier1_sync_apply.py` 模式）。
- 本 Phase 1 **不含** apply executor，僅到「產生 dry-run 預覽」為止。

---

## 表清單（本檔建立）
`prescription_import_batches`、`prescription_customer_candidates`、`prescription_diagnosis_candidates`、`prescription_drug_candidates`、`prescription_import_review_actions`、`prescription_drug_diagnosis_link_candidates`（F：optional/Phase 2）。

## 本輪未做（遵守限制）
- 未執行 SQL、未連 DB 寫入、未建表、未改 customers/drug_items/diagnosis_codes、未 git add/commit。
- SQL 檔僅含 CREATE TABLE/INDEX IF NOT EXISTS 與 COMMENT；無 DROP/DELETE/TRUNCATE、無 trigger、無 production 邏輯。
