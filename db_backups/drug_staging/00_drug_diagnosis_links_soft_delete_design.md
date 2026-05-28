# /藥診關聯「解除關聯 / 軟刪除」功能設計

- 日期：2026-05-28
- 狀態：**設計草案**。本輪只寫設計文件與 SQL 草案，**未執行 SQL、未寫 DB、未改程式、未 git**。
- 相關草案 SQL：`db_backups/drug_staging/alter_drug_diagnosis_links_add_soft_delete.sql`

---

## 1. 問題背景
- 既有 `/藥診關聯`（`rewrite/handlers/liff/drug_diagnosis_links.py`）已上線，可 **新增** drug_diagnosis_links（search → preview → apply，含 unique 防呆）。
- 但**缺少「解除錯誤關聯」機制**：使用者曾把 **EXFOPINE(id43) 誤連高血脂(id129)**，最後只能以一次性 **gated UPDATE（id28：129→189）** 修正。
- 此類「建錯要收回」目前無正式流程。**不建議用硬刪除 DELETE**（見第 7 節）；應採**軟刪除 / 停用（deactivate）**，保留資料與稽核、可重新啟用、查詢時只顯示啟用中。

## 2. 建議 schema（drug_diagnosis_links 新增欄位，additive）
| 欄位 | 型別 | 說明 |
|---|---|---|
| **is_active** | `boolean NOT NULL DEFAULT true` | 是否啟用；停用＝false。既有 29 筆自動為 true。 |
| **deactivated_at** | `timestamptz` | 停用時間 |
| **deactivated_by_line_user_id** | `text` | 停用操作者 LINE userId（稽核） |
| **deactivated_by_display_name** | `text` | 停用操作者顯示名稱（稽核） |
| **deactivation_reason** | `text` | 停用原因（**LIFF 必填**） |

### 是否需要 reactivated_* ？→ **建議要（且納入第一版）**
因為第一版「重新啟用」採 **re-activate**（把 is_active 改回 true）而非重新 INSERT（見第 6 節），所以需要對等的稽核欄位：
| 欄位 | 型別 | 說明 |
|---|---|---|
| **reactivated_at** | `timestamptz` | 重新啟用時間 |
| **reactivated_by_line_user_id** | `text` | 重新啟用操作者 LINE userId |
| **reactivation_reason** | `text` | 重新啟用原因 |
- 這 3 欄同屬 additive、無害，先一起加可避免日後再做一次 migration。若想極簡，也可只先加 5 個 deactivation 欄位、reactivation 欄位待 re-activate UI 上線再補（兩者皆 additive）。
- **不需** `deleted_at` / 硬刪除欄位（不採 DELETE）。

## 3. SQL 草案
見 `alter_drug_diagnosis_links_add_soft_delete.sql`。要點：
- 只 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`（8 欄）；包在單一交易；可重跑。
- `is_active` 用 `NOT NULL DEFAULT true` → 既有 29 筆即時為 true（PG11+ 為 metadata-only，不重寫整表）。
- **不**建索引、**不**改 unique constraint、**不** DROP/DELETE/TRUNCATE（僅於本報告第 6 節建議，留第二階段）。
- 部署：**先跑本 migration（additive、安全），再部署引用 is_active 的查詢/程式**。

## 4. /藥診關聯 LIFF 功能設計（解除關聯流程）
> 皆為設計；本輪不改 `drug_diagnosis_links.py`。沿用既有 search→preview→apply 風格，新增 deactivate 對應端點。

**(A) 查看現有關聯**：擴充既有 list（GET `/drug_diagnosis_links`）——預設**只列 is_active=true**；可選參數 `include_inactive=1` 才顯示已停用（並標示「已停用」）。每筆提供「解除關聯」動作。

**(B) 解除前 preview**：`POST /drug_diagnosis_links/deactivate/preview`
- 入：link `id`（＋必填 `reason`）。
- 出：該 link 完整資訊（藥名 / 診斷名 / link_type / role_type / created_at）、`can_deactivate`（需 `is_active=true` 才可）、**warning 文案**（見第 7 節 UI）。
- reason 空 → 擋下，回「請填寫解除原因」。

**(C) apply 解除**：`POST /drug_diagnosis_links/deactivate`
- 單一 transaction 內僅：
  ```sql
  UPDATE drug_diagnosis_links
     SET is_active = false,
         deactivated_at = now(),
         deactivated_by_line_user_id = :uid,
         deactivated_by_display_name = :name,
         deactivation_reason = :reason,
         updated_at = now()
   WHERE id = :id AND is_active = true;
  ```
- rowcount 必須 = 1，否則 rollback（見第 5 節）。
- 成功回「**已停用（解除關聯）**」，並回傳停用後資料。

**(D)（companion）重新啟用 re-activate**：`POST /drug_diagnosis_links/reactivate(/preview)`
- `UPDATE ... SET is_active=true, reactivated_at=now(), reactivated_by_*=..., reactivation_reason=:reason, updated_at=now() WHERE id=:id AND is_active=false;`（rowcount 必須=1）。
- 用於「停用後又想恢復」——**不重新 INSERT**（見第 6 節）。可與 deactivate 同版或列 v1.1。

## 5. 安全規則（deactivate / reactivate 共用）
- **不做硬刪除（DELETE）**。
- **只 UPDATE 指定 link id**；`WHERE id=? AND is_active=true`（deactivate）／`AND is_active=false`（reactivate）→ 具**冪等性**、避免重複操作或狀態錯亂。
- **單一 transaction**；**rowcount 必須 = 1**，否則 **rollback**（0 表示 id 不存在或狀態不符；>1 不可能因 id 為 PK）。
- **apply 後 verify**：再查該 id 確認 `is_active` 已切換、`deactivated_at`（或 reactivated_at）已寫入。
- **保留 `created_at` 原始紀錄**（永不更動）；`source_type`、原 link_type/role_type 一律保留。
- 沿用既有上線模式：localhost/正式環境一致的連線、liff_auth_required（記錄操作者 userId/displayName 供稽核）。
- 一次性資料更正（如先前 EXFOPINE）未來可改走此 deactivate 流程，**不再需要臨時 gated UPDATE 腳本**。

## 6. 對 unique constraint 的討論
- 現有：`drug_diagnosis_links_unique UNIQUE (drug_item_id, diagnosis_code_id, link_type, role_type)`，**不分 is_active**。
- 影響：某 link 停用後，若想**重新 INSERT 同一 (drug, diagnosis, link_type, role_type)**，會被既有 unique **擋住**（停用的 row 仍占用唯一鍵）。
- **第一版建議：不要重新 INSERT，改做 re-activate**（把該停用 row 的 is_active 改回 true）→ 完全避開 unique 衝突，且保留原 id / created_at / 稽核。
- **第二階段（未來，若真的需要重新 INSERT）**：改為 **active-only partial unique index**：
  ```sql
  -- 第二階段才做，本輪不做：
  ALTER TABLE drug_diagnosis_links DROP CONSTRAINT drug_diagnosis_links_unique;
  CREATE UNIQUE INDEX drug_diagnosis_links_active_unique
      ON drug_diagnosis_links (drug_item_id, diagnosis_code_id, link_type, role_type)
      WHERE is_active;
  ```
  → 唯一性只在「啟用中」的 row 間成立，允許多筆已停用的歷史 + 一筆啟用。需謹慎（DROP 既有 constraint + 索引切換），故**留第二階段、報告建議、不入本輪 SQL**。

## 7. UI 文案建議
- 動作名稱用「**解除關聯**」，**不要寫「刪除」**（避免讓人以為資料被清掉）。
- preview / 確認頁顯示 **warning**：「**解除後 /drug 圖卡將不再顯示此診斷**（關聯會被停用、保留紀錄，可日後重新啟用）。」
- **解除原因必填**（空白不可送出）；送出後顯示「**已停用（解除關聯）**」與停用時間/操作者。
- 列表對已停用項目標示「已停用」灰字，並提供「重新啟用」入口（若啟用 re-activate）。

## 8. 查詢修改點（顯示相關診斷碼/藥品的查詢需只顯示 is_active=true）
| 檔案 : 位置 | 現況 | 建議修改 |
|---|---|---|
| `modules/services/drug_query_service.py` `_get_related_diagnoses`（約 L188–219） | `FROM drug_diagnosis_links ddl JOIN diagnosis_codes dc ... WHERE ddl.drug_item_id = :id` | 加 `AND COALESCE(ddl.is_active, TRUE) IS TRUE` |
| `modules/services/diagnosis_query_service.py` `_get_related_drugs`（約 L218–252） | `FROM drug_diagnosis_links ddl JOIN drug_items di ... WHERE ddl.diagnosis_code_id = :id AND di.is_active IS TRUE` | 再加 `AND COALESCE(ddl.is_active, TRUE) IS TRUE` |
| `rewrite/handlers/liff/drug_diagnosis_links.py` list（約 L207–282） | 列出全部 link | 預設只列 `is_active=true`；`include_inactive` 才顯示停用並標示 |

### 欄位不存在時的相容性策略
- **首選：部署順序（migration-first）**。先套用 additive ALTER（安全、即時、預設 true），**再**部署引用 `is_active` 的查詢。PostgreSQL 無法引用尚不存在的欄位，故順序很關鍵。
- **查詢用 `COALESCE(ddl.is_active, TRUE) IS TRUE`**（等義 `ddl.is_active IS NOT FALSE`）：欄位存在但偶有 NULL（跨環境時序）時，**預設視為啟用**（不漏顯示）。因 schema 為 `NOT NULL DEFAULT true`，正常不會有 NULL，此為保險。
- **（可選）啟動期欄位偵測**：程式啟動時查 `information_schema.columns`，若 `is_active` 不存在則暫不套用 filter。可在「程式先於 migration 上線」時避免 500，但增加複雜度 → **v1 不建議**，以 migration-first 為主。
- **本機 vs production**：本機 dispatch_db 先套 ALTER 驗證；prod(Render) 之 drug_diagnosis_links 需另行 gated 套用同一 ALTER，且**與程式部署順序一致（先 schema 後程式）**。

## 9. 不建議 DELETE（硬刪除）的原因
- **不可逆、無稽核**：誰、何時、為何解除無從查；誤刪只能靠備份還原。
- **失去歷史脈絡**：created_at、source_type、原始關聯一併消失，無法追溯「曾經建過、後來解除」。
- **/drug 顯示效果相同**：停用（is_active=false）即不顯示，與刪除對使用者效果一致，但保留可追溯性與可復原性。
- **可重新啟用**：軟刪除可 re-activate；硬刪除得重新 INSERT 且可能撞 unique。
- 符合既有治理風格（additive、可回溯、gated）。

## 10. 分階段實作建議
- **Phase 1（本設計核心）**
  1. 套用 `alter_..._add_soft_delete.sql`（additive，本機先行）。
  2. 三個查詢點加 `COALESCE(is_active, TRUE) IS TRUE` filter（migration 後再部署）。
  3. `/藥診關聯` LIFF 新增「查看現有關聯 + 解除關聯（preview＋必填原因＋apply＋verify）」；re-activate 同版或 v1.1。
- **Phase 2（未來，按需）**
  - active-only partial unique index（允許停用後重新 INSERT；見第 6 節）。
  - 更完整的歷史/版本檢視、批次解除等。
- **永遠不做**：硬刪除 DELETE drug_diagnosis_links（除非極特殊且另行授權 + 備份）。

## 11. 本輪未做（遵守限制）
- 未執行 SQL、未寫 DB、未改 `rewrite/handlers/liff/drug_diagnosis_links.py` 或任何查詢程式、未 git add/commit。
- 產出：本設計報告、`alter_drug_diagnosis_links_add_soft_delete.sql`（皆草案）。
