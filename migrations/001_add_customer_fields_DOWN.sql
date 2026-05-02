-- ============================================================
-- Migration 001 ROLLBACK：撤銷 5 個欄位
-- ============================================================
-- 用途：如果 migration 跑完後想還原
-- 警告：會清掉所有 birthday / latitude / longitude / 時間戳資料

BEGIN;

DROP TRIGGER IF EXISTS customers_updated_at_trigger ON customers;
DROP FUNCTION IF EXISTS update_customers_updated_at();

ALTER TABLE customers
    DROP COLUMN IF EXISTS birthday,
    DROP COLUMN IF EXISTS latitude,
    DROP COLUMN IF EXISTS longitude,
    DROP COLUMN IF EXISTS created_at,
    DROP COLUMN IF EXISTS updated_at;

COMMIT;
