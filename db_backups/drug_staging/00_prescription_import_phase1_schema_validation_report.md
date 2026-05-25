# 處方匯入 Phase 1 — Schema SQL 驗證報告（transaction + ROLLBACK）

- 驗證時間：2026-05-25
- 方法：在**本機** `dispatch_db` 單一 transaction 內執行 `create_prescription_import_phase1_tables.sql`（**移除嵌入的 `BEGIN;`/`COMMIT;`，改由本連線一個 transaction 控制**），交易內驗證後 **ROLLBACK**，不留下任何表。
- 工具：`db_backups/drug_staging/_phase1_ddl_validate.py`（read/validate；autocommit=False、最後 rollback）。
- 結果：**VALIDATION_PASSED = True**。**未 COMMIT、未留下任何表、未寫 production、未做資料 DML。**

---

## 1. DB target
| 項目 | 值 |
|---|---|
| host | localhost |
| port | 5432 |
| database | dispatch_db |
| user | postgres |
| 標示 | **本機開發 DB（NOT production）** |
- 腳本硬性檢查：host∈{localhost,127.0.0.1} 且 db=dispatch_db 才執行，否則中止（**不可能誤連 Render**）。密碼未輸出。

## 2. 驗證是否通過
- **通過（PASS）**。執行前 6 表皆不存在；交易內 6 表皆成功建立；rollback 後 6 表皆不存在。

## 3. 執行前/後（不留殘留）
- **PRE**（執行前，期望全 False）：6 表皆不存在 ✓
- **POST**（ROLLBACK 後，期望全 False）：6 表皆不存在 ✓ → **無殘留**

## 4. Transaction 內建立的表清單（6）
1. `prescription_import_batches` ✓
2. `prescription_customer_candidates` ✓
3. `prescription_diagnosis_candidates` ✓
4. `prescription_drug_candidates` ✓
5. `prescription_import_review_actions` ✓
6. `prescription_drug_diagnosis_link_candidates` ✓

## 5. Constraints / Indexes / Generated column 檢查摘要

### Constraints（c=CHECK, f=FK, p=PK）
| 表 | CHECK | FK | PK |
|---|---:|---:|---:|
| prescription_import_batches | 2 | 0 | 1 |
| prescription_customer_candidates | 6 | 2 | 1 |
| prescription_diagnosis_candidates | 6 | 2 | 1 |
| prescription_drug_candidates | 6 | 4 | 1 |
| prescription_import_review_actions | 2 | 1 | 1 |
| prescription_drug_diagnosis_link_candidates | 4 | 5 | 1 |

- customer 表 CHECK 已逐一確認：`source_type / proposed_gender(M/F/unknown) / match_status / review_status / review_decision / confidence` 全部存在且定義正確。
- FK 數對應設計：customer/diagnosis 各 2（batch + 1 個正式表）、drug 4（batch + drug_items + mappings + nhi_code_candidates）、review_actions 1（batch；candidate_id 多型無 FK）、link 5（batch + 2 candidate + drug_items + diagnosis_codes）。

### Indexes（含 PK index）
| 表 | index 數 |
|---|---:|
| prescription_import_batches | 3 |
| prescription_customer_candidates | 5 |
| prescription_diagnosis_candidates | 5 |
| prescription_drug_candidates | 6 |
| prescription_import_review_actions | 4 |
| prescription_drug_diagnosis_link_candidates | 4 |

### Generated column
- `prescription_drug_candidates.effective_nhi_drug_code`：`is_generated = ALWAYS`，運算式 `COALESCE(corrected_nhi_drug_code, normalized_nhi_drug_code, raw_nhi_drug_code)` ✓（STORED generated 建立成功）。

### 禁用欄位掃描
- 對 6 表掃 `national_id / phone / chart_no / contact_phone / medical_record_no`：**NONE**（無敏感欄）✓

## 6. 是否發現需調整的 SQL
- **無需調整**。DDL 在 PostgreSQL 16 可順利建立；CHECK / FK（型別已對齊 PK：customers/diagnosis_codes=integer、drug_items/mappings/nhi_cand=bigint）/ index / generated column 全數成立；rollback 乾淨。
- 備註（非缺陷）：`prescription_drug_diagnosis_link_candidates` 的 `drug_candidate_id`/`diagnosis_candidate_id` 採 `ON DELETE CASCADE`（全檔唯一 CASCADE，derived 連結資料），若偏好 RESTRICT/SET NULL 可再調，不影響建立。

## 7. 本輪未做（遵守限制）
- **未 COMMIT**（全程 transaction + ROLLBACK）、**未留下任何表**、未寫 production、未修改正式表、未做 INSERT/UPDATE/DELETE/TRUNCATE 資料 DML、未 git add/commit。
- 唯一 DDL 動作（CREATE TABLE/INDEX）皆在已回滾的交易內，對 DB 實際狀態無變更。
