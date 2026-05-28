# drug_diagnosis_links soft-delete SQL — 本機 Transaction-Rollback 驗證報告

- 日期：2026-05-29
- 對象 SQL：`db_backups/drug_staging/alter_drug_diagnosis_links_add_soft_delete.sql`
- 方法：在**單一 transaction** 內執行該 SQL 的 ALTER 語句並逐項驗證，**最後一律 ROLLBACK**（PostgreSQL DDL 屬交易性，rollback 後不留任何 schema 變更）。為自行控制交易，已**剝除檔內 `BEGIN;`/`COMMIT;`**，全程**從未 COMMIT**。
- 驗證腳本：`db_backups/drug_staging/_validate_soft_delete_rollback.py`（唯讀/交易內測試用）。
- **本輪未 COMMIT、未寫 production、未改正式資料、未 INSERT/UPDATE/DELETE/TRUNCATE、未 git add/commit。**

---

## 1. DB target（不輸出密碼）
| 項目 | 值 |
|---|---|
| host | **localhost** |
| port | **5432** |
| database | **dispatch_db** |
| user | postgres |
| 連線守門 | 非 `localhost:5432/dispatch_db` 即 REFUSE；**未連 Render / production** |

## 2. 驗證結論
- **VALIDATION：✅ PASS（notes: none）**
- **是否需要修 SQL：否**。SQL 草案語法正確、可在本機執行、rollback 後無殘留；既有 unique constraint 不受影響。

## 3. SQL 安全前置掃描
- 可執行語句 **8 條**，**全部為 `ALTER TABLE ... ADD COLUMN`**。
- 掃描確認**無** `DROP / DELETE / TRUNCATE / INSERT / UPDATE / GRANT / CREATE`（註解中的說明字樣已先剝除，不影響判定）。

## 4. 執行前（PRE，新連線）
- drug_diagnosis_links **row count = 29**。
- 目前欄位（12）：`id, drug_item_id, diagnosis_code_id, link_type, role_type, confidence, is_primary, sort_order, source_type, note_text, created_at, updated_at`。
- 8 個目標欄位**尚未存在**：`is_active / deactivated_at / deactivated_by_line_user_id / deactivated_by_display_name / deactivation_reason / reactivated_at / reactivated_by_line_user_id / reactivation_reason` → 皆 ✅ 不存在。

## 5. Transaction 內驗證（執行 ALTER 後、ROLLBACK 前）
| 檢查項 | 結果 |
|---|---|
| 8 個欄位皆存在 | ✅（missing = []） |
| `is_active` 型別/可空/預設 | ✅ `boolean` / `NOT NULL`（is_nullable=NO）/ `DEFAULT true` |
| 既有 row count 不變 | ✅ 29 → 29 |
| 既有 29 筆 `is_active` 皆 true | ✅（`is_active IS NOT TRUE` 的列數 = 0） |
| unique constraint 未變 | ✅ 仍為 `drug_diagnosis_links_unique UNIQUE (drug_item_id, diagnosis_code_id, link_type, role_type)` |
| 無 DROP/DELETE/TRUNCATE | ✅（語句全為 ADD COLUMN） |
| 未動 drug_items / diagnosis_codes / customers | ✅（ALTER 對象只有 drug_diagnosis_links） |

## 6. ROLLBACK 後（POST，新連線，確認無殘留）
| 檢查項 | 結果 |
|---|---|
| 8 個目標欄位皆**不存在** | ✅（target_present = []） |
| row count 不變 | ✅ 29 |
| 欄位清單與 PRE 完全相同 | ✅（post cols == pre cols，仍 12 欄） |
| unique constraint 與 PRE 相同 | ✅（無變更） |

## 7. Row count 對照
| 階段 | count |
|---|---|
| before（PRE） | **29** |
| in-transaction（ALTER 後） | **29** |
| after rollback（POST） | **29** |

→ 全程未增減任何 row。

## 8. 結論與建議
- SQL 草案**通過 rollback 驗證**：可安全地以 additive ALTER 套用，且若需取消，rollback 不留殘留。
- **不需修改 SQL**。
- 正式套用時建議：先在本機以**非 rollback**（真正 COMMIT）執行一次（仍 additive、安全），再依設計報告調整三個查詢點與 LIFF；**production(Render) 另行 gated 套用**（先 schema 後程式）。本輪皆未做。

## 9. 本輪未做（遵守限制）
- 未 COMMIT（交易已 ROLLBACK）；本機 drug_diagnosis_links schema **無任何變更**（仍 12 欄、29 列）。
- 未連 / 未寫 production；未改正式資料；未 INSERT/UPDATE/DELETE/TRUNCATE；未 git add/commit。
- 產出：本驗證報告（+ 驗證腳本 `_validate_soft_delete_rollback.py`，untracked）。
