-- ============================================================
-- Migration 006 ROLLBACK
-- ============================================================
BEGIN;

ALTER TABLE customers
    DROP COLUMN IF EXISTS dm_care_no;

COMMIT;
