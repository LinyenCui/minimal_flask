-- ============================================================
-- Migration 002: customers 增加 4 個 medical 欄位 + 5 筆範例
-- ============================================================
-- 日期：2026-05-03
-- 影響：customers 表（dev 本地）
--
-- 新增欄位：
--   + national_id          VARCHAR(20)  身分證/統編
--   + gender               CHAR(1)      'M' 或 'F'
--   + medical_record_no    VARCHAR(20)  病歷號（診所內部 ID）
--   + insurance_type       VARCHAR(20)  健保/自費/低收等
--
-- 約束：
--   - national_id 唯一（除 NULL 外）
--   - gender 只能 M/F/NULL
--
-- 範例資料：5 筆診所患者（從謝智超達恩診所處方箋）
-- ============================================================

BEGIN;

-- 1. 新增 4 個欄位
ALTER TABLE customers
    ADD COLUMN national_id VARCHAR(20),
    ADD COLUMN gender CHAR(1),
    ADD COLUMN medical_record_no VARCHAR(20),
    ADD COLUMN insurance_type VARCHAR(20);

-- 2. 約束
ALTER TABLE customers
    ADD CONSTRAINT chk_customers_gender
    CHECK (gender IS NULL OR gender IN ('M', 'F'));

CREATE UNIQUE INDEX uq_customers_national_id
    ON customers (national_id)
    WHERE national_id IS NOT NULL;

-- 3. 註解
COMMENT ON COLUMN customers.national_id IS '身分證字號（個人）或統一編號（機構）';
COMMENT ON COLUMN customers.gender IS '性別 M=男 F=女（個人才填）';
COMMENT ON COLUMN customers.medical_record_no IS '診所病歷號（內部 ID，例：001026）';
COMMENT ON COLUMN customers.insurance_type IS '健保身份：健保/自費/低收/中低收 等';

-- 4. 範例插入：5 筆謝智超達恩診所患者
INSERT INTO customers (
    name, address, short_name, category, contact_phone, remarks,
    birthday, latitude, longitude,
    national_id, gender, medical_record_no, insurance_type
) VALUES
    ('黃陳玉盆',  '(待補)', '黃陳玉盆',  '診所', NULL, '範例：5/2 處方箋',
     '1951-08-23', NULL, NULL,
     'D200615801', 'F', '001026', '健保'),

    ('林佳瑋',    '(待補)', '林佳瑋',    '診所', NULL, '範例：4/28 處方箋',
     '1986-09-26', NULL, NULL,
     'D122292202', 'M', '001676', '健保'),

    ('方怡雁',    '(待補)', '方怡雁',    '診所', NULL, '範例：4/28 處方箋',
     '1992-08-01', NULL, NULL,
     'R223939618', 'F', '001677', '健保'),

    ('謝家成',    '(待補)', '謝家成',    '診所', NULL, '範例：4/28 處方箋',
     '1937-02-17', NULL, NULL,
     'D101180038', 'M', '000133', '健保'),

    ('曾紀淑美',  '(待補)', '曾紀淑美',  '診所', NULL, '範例：5/1 處方箋',
     '1956-02-13', NULL, NULL,
     'L220814691', 'F', '002034', '健保');

COMMIT;

-- ============================================================
-- 驗證查詢（可手動跑）
-- ============================================================
-- SELECT id, short_name, name, gender, birthday, medical_record_no, insurance_type
-- FROM customers
-- WHERE medical_record_no IS NOT NULL
-- ORDER BY medical_record_no;
