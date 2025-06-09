-- PostgreSQL遷移腳本：添加修改追蹤欄位
-- 為trips和completed_trips表添加修改追蹤功能所需的欄位

-- 為trips表添加modification欄位
ALTER TABLE trips ADD COLUMN IF NOT EXISTS modified_by TEXT;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS modification_reason TEXT;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS modification_time TIMESTAMP;

-- 為completed_trips表添加modification欄位  
ALTER TABLE completed_trips ADD COLUMN IF NOT EXISTS modified_by TEXT;
ALTER TABLE completed_trips ADD COLUMN IF NOT EXISTS modification_reason TEXT;
ALTER TABLE completed_trips ADD COLUMN IF NOT EXISTS modification_time TIMESTAMP;

-- 驗證添加結果
\d trips
\d completed_trips 