-- 005_align_render_customers_schema.sql
-- ============================================================
-- 把 Render 的 customers schema 對齊本地（補 7 個欄位 + trigger）
--
-- 背景：
--   本地 dev 跑過 migration 001 + 002，加了 9 個欄位；又跑過 004
--   drop 了 national_id / insurance_type 兩個。
--   淨增 = 9 - 2 = 7 個欄位：
--     birthday / latitude / longitude / created_at / updated_at
--     gender / medical_record_no
--
--   Render 還停在原始 7 欄（id/name/address/short_name/category/
--   remarks/contact_phone）。這個 migration 一次補齊。
--
-- 跑法（Render 端 Adminer SQL editor 或 psql）：
--   貼這整個檔的 SQL 進去執行
--
-- 跑完之後 Render 跟本地的 customers schema 應該一模一樣（14 欄），
--   後續可以解除 sync_from_render.py 的 SKIP_TABLES 限制。
--
-- 日期：2026-05-08
-- ============================================================

BEGIN;

-- 1. 加 7 個欄位（IF NOT EXISTS 防重跑）
ALTER TABLE customers
    ADD COLUMN IF NOT EXISTS birthday DATE,
    ADD COLUMN IF NOT EXISTS latitude DECIMAL(10, 7),
    ADD COLUMN IF NOT EXISTS longitude DECIMAL(10, 7),
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS gender CHAR(1),
    ADD COLUMN IF NOT EXISTS medical_record_no VARCHAR(20);

-- 2. gender check constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_customers_gender'
    ) THEN
        ALTER TABLE customers
            ADD CONSTRAINT chk_customers_gender
            CHECK (gender IS NULL OR gender IN ('M', 'F'));
    END IF;
END$$;

-- 3. updated_at 自動更新 trigger（同本地 migration 001 的設定）
CREATE OR REPLACE FUNCTION update_customers_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS customers_updated_at_trigger ON customers;
CREATE TRIGGER customers_updated_at_trigger
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION update_customers_updated_at();

-- 4. 註解
COMMENT ON COLUMN customers.birthday IS '客戶生日（個人才填，機構留 NULL）。日的部分對應門診病歷層';
COMMENT ON COLUMN customers.latitude IS '緯度，預留給未來 Google Map API';
COMMENT ON COLUMN customers.longitude IS '經度，預留給未來 Google Map API';
COMMENT ON COLUMN customers.created_at IS '建立時間';
COMMENT ON COLUMN customers.updated_at IS '最近異動時間（trigger 自動更新）';
COMMENT ON COLUMN customers.gender IS '性別 M=男 F=女（個人才填）';
COMMENT ON COLUMN customers.medical_record_no IS '診所病歷號（內部 ID，例：001026）';

COMMIT;

-- ============================================================
-- 驗證（手動跑）：應看到 14 個欄位
-- ============================================================
-- SELECT column_name FROM information_schema.columns
-- WHERE table_name = 'customers' ORDER BY ordinal_position;
