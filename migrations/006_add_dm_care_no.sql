-- ============================================================
-- Migration 006: customers 增加 dm_care_no（糖尿病共同照護網代號）
-- ============================================================
-- 日期：2026-05-16
-- 影響：customers 表（本地 dev + Render prod 都跑這份）
--
-- 新增欄位：
--   + dm_care_no  VARCHAR(10)  糖尿病共同照護網代號，可 NULL
--
-- 說明：診所內部自行記錄的編號，約 4 位數（VARCHAR 保留前導 0、
--       給點 buffer），純記錄查詢用，不做唯一約束 / CHECK。
--
-- 用 IF NOT EXISTS 防重跑，本地與 Render 跑同一份即可（單欄不需
-- 像 005 另寫對齊版）。
--
-- 跑法：
--   本地：venv/bin/python -c 套用（見 commit 說明）或 psql
--   Render：Adminer SQL editor / psql 貼整份執行
-- ============================================================

BEGIN;

ALTER TABLE customers
    ADD COLUMN IF NOT EXISTS dm_care_no VARCHAR(10);

COMMENT ON COLUMN customers.dm_care_no IS
    '糖尿病共同照護網代號（診所內部自行編號，約 4 位數，可 NULL，純記錄查詢用）';

COMMIT;

-- ============================================================
-- 驗證（手動跑）：
-- SELECT column_name, data_type, character_maximum_length, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'customers' AND column_name = 'dm_care_no';
-- ============================================================
