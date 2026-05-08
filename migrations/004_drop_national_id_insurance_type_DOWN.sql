-- 004_drop_national_id_insurance_type_DOWN.sql
-- ============================================================
-- 反向（rollback）：把 national_id / insurance_type 加回去
--
-- ⚠️ 加回欄位後資料是 NULL — 需要從備份 CSV restore 才能補回原本資料
-- ============================================================

BEGIN;

ALTER TABLE customers ADD COLUMN IF NOT EXISTS national_id VARCHAR(20);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS insurance_type VARCHAR(50);

COMMIT;

-- 還原資料（如果有 customers_dropped_cols_backup.csv）：
-- \\copy customers_restore (id, short_name, national_id, insurance_type)
--   FROM 'customers_dropped_cols_backup.csv' CSV HEADER;
-- UPDATE customers c SET
--   national_id = r.national_id,
--   insurance_type = r.insurance_type
-- FROM customers_restore r
-- WHERE c.id = r.id;
