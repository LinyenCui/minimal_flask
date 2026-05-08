-- ============================================================
-- Migration 001: customers 表增加 5 個欄位
-- ============================================================
-- 日期：2026-05-03
-- 影響：customers 表
-- 範圍：本地 dev DB only (Render 不動)
--
-- 變更：
--   + birthday      DATE             nullable
--   + latitude      DECIMAL(10,7)    nullable  -- 緯度，精度約 1 公分
--   + longitude     DECIMAL(10,7)    nullable
--   + created_at    TIMESTAMP        NOT NULL DEFAULT NOW()
--   + updated_at    TIMESTAMP        NOT NULL DEFAULT NOW() (含 auto-update trigger)
--
-- 既有資料處理：
--   birthday / latitude / longitude → 全部 NULL (待手動補)
--   created_at / updated_at → 全部填入 migration 執行時刻
--                            (歷史資料無真實建立時間，這是已知妥協)
--
-- 回滾方式：執行 001_add_customer_fields_DOWN.sql
-- ============================================================

BEGIN;

-- 1. 新增 5 個欄位
ALTER TABLE customers
    ADD COLUMN birthday DATE,
    ADD COLUMN latitude DECIMAL(10, 7),
    ADD COLUMN longitude DECIMAL(10, 7),
    ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- 2. 加註欄位註解（之後 \d+ customers 看得到）
COMMENT ON COLUMN customers.birthday IS '客戶生日（個人才填，機構留 NULL）。日的部分對應門診病歷層';
COMMENT ON COLUMN customers.latitude IS '緯度，預留給未來 Google Map API';
COMMENT ON COLUMN customers.longitude IS '經度，預留給未來 Google Map API';
COMMENT ON COLUMN customers.created_at IS '建立時間（migration 後既有資料統一填 migration 執行時刻）';
COMMENT ON COLUMN customers.updated_at IS '最近異動時間（trigger 自動更新）';

-- 3. updated_at 自動更新 trigger
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

-- 4. 為座標查詢準備索引（可選，當未來地圖 API 上線時用）
-- 暫時 commented out，實際引入 google map 時再啟用
-- CREATE INDEX idx_customers_coords ON customers (latitude, longitude)
--     WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

COMMIT;

-- ============================================================
-- 驗證查詢（手動跑）
-- ============================================================
-- \d+ customers
-- SELECT COUNT(*),
--        COUNT(birthday) AS has_birthday,
--        COUNT(latitude) AS has_coords
-- FROM customers;
