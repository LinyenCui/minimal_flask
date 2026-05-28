-- =============================================================================
-- alter_drug_diagnosis_links_add_soft_delete.sql  （草案，尚未執行）
-- 用途：為 drug_diagnosis_links 新增「軟刪除 / 停用（deactivate）」相關欄位。
-- 設計報告：db_backups/drug_staging/00_drug_diagnosis_links_soft_delete_design.md
--
-- 安全原則（本檔嚴格遵守）：
--   * 只做 ALTER TABLE ... ADD COLUMN（additive），且 IF NOT EXISTS（可重跑）。
--   * 不改既有資料語意；既有 29 筆在 is_active 加上 NOT NULL DEFAULT true 後全部=true（仍顯示）。
--   * 不 DROP / DELETE / TRUNCATE / 不改既有 unique constraint。
--   * 不新增 / 不刪除任何 row。
--   * PostgreSQL 11+：以非揮發性 DEFAULT 新增欄位為 metadata-only（不重寫整表）。
--
-- 執行注意（本輪不執行）：
--   * 部署順序＝「先跑本 migration（additive，安全），再部署引用 is_active 的查詢/程式碼」。
--   * 先在本機 localhost dispatch_db 驗證；production(Render) 另行 gated 套用。
-- =============================================================================

BEGIN;

-- ---- 停用（軟刪除）核心欄位（對應設計報告第 2 節）----
ALTER TABLE drug_diagnosis_links
    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;

ALTER TABLE drug_diagnosis_links
    ADD COLUMN IF NOT EXISTS deactivated_at timestamptz;

ALTER TABLE drug_diagnosis_links
    ADD COLUMN IF NOT EXISTS deactivated_by_line_user_id text;

ALTER TABLE drug_diagnosis_links
    ADD COLUMN IF NOT EXISTS deactivated_by_display_name text;

ALTER TABLE drug_diagnosis_links
    ADD COLUMN IF NOT EXISTS deactivation_reason text;

-- ---- 重新啟用（re-activate）稽核欄位 ----
-- 第一版「重新啟用」採 re-activate（把 is_active 改回 true）而非重新 INSERT，
-- 以避開既有 unique constraint 並保留原 id / created_at；以下欄位記錄重新啟用稽核。
ALTER TABLE drug_diagnosis_links
    ADD COLUMN IF NOT EXISTS reactivated_at timestamptz;

ALTER TABLE drug_diagnosis_links
    ADD COLUMN IF NOT EXISTS reactivated_by_line_user_id text;

ALTER TABLE drug_diagnosis_links
    ADD COLUMN IF NOT EXISTS reactivation_reason text;

COMMIT;

-- =============================================================================
-- 本檔「不做」的事（僅於設計報告建議，留待後續另行決定）：
--   * 不建立索引（如 idx ON (is_active) 或 active-only partial unique index）——見報告第 6 節。
--   * 不調整既有 unique constraint：
--         drug_diagnosis_links_unique (drug_item_id, diagnosis_code_id, link_type, role_type)
--     第一版維持現狀；停用後「重新啟用」走 re-activate，不重新 INSERT。
--     若未來要允許停用後重新 INSERT 同一關聯，需改為 active-only partial unique index
--     （DROP 既有 unique + CREATE UNIQUE INDEX ... WHERE is_active），屬第二階段，本檔不做。
-- =============================================================================
