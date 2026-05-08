-- ============================================================
-- Migration 002 ROLLBACK
-- ============================================================
BEGIN;

-- 刪除 5 筆範例患者
DELETE FROM customers
WHERE medical_record_no IN ('001026', '001676', '001677', '000133', '002034');

-- 撤掉約束與索引
DROP INDEX IF EXISTS uq_customers_national_id;
ALTER TABLE customers DROP CONSTRAINT IF EXISTS chk_customers_gender;

-- 撤掉欄位
ALTER TABLE customers
    DROP COLUMN IF EXISTS insurance_type,
    DROP COLUMN IF EXISTS medical_record_no,
    DROP COLUMN IF EXISTS gender,
    DROP COLUMN IF EXISTS national_id;

COMMIT;
