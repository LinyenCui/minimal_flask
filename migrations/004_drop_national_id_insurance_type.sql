-- 004_drop_national_id_insurance_type.sql
-- ============================================================
-- 移除 customers 表的 national_id / insurance_type 兩欄
--
-- 背景：
--   - national_id（身分證）：實際上不收（個資麻煩 + 沒地方用）
--   - insurance_type（健保身份）：99% 都健保，等於廢欄；自費 case 寫
--     remarks 即可
--
-- 影響：
--   - rewrite 程式（atomic tool / Flex view / AI skill / LIFF / scripts）
--     已全部 drop 此兩欄；舊 payload 用 _deprecated 寬容吞掉，不報錯
--   - 沒有 legacy modules/ 程式引用此兩欄（已 grep 確認）
--
-- 跑法（Render 端 psql 或 SQL Editor）：
--   1. 先備份這兩欄資料（可選）：
--      \\copy (SELECT id, short_name, national_id, insurance_type
--              FROM customers
--              WHERE national_id IS NOT NULL OR insurance_type IS NOT NULL)
--              TO 'customers_dropped_cols_backup.csv' CSV HEADER;
--   2. 跑此 migration：
--      psql $DATABASE_URL -f migrations/004_drop_national_id_insurance_type.sql
--
-- 日期：2026-05-08
-- ============================================================

BEGIN;

-- 確認欄位存在（IF EXISTS 防重跑）
ALTER TABLE customers DROP COLUMN IF EXISTS national_id;
ALTER TABLE customers DROP COLUMN IF EXISTS insurance_type;

COMMIT;

-- 驗證（手動跑）：
-- SELECT column_name FROM information_schema.columns
-- WHERE table_name = 'customers' ORDER BY ordinal_position;
