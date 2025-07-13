-- PostgreSQL遷移腳本：添加乘客請假專用欄位
-- 避免與車資修改說明混淆

-- 為trips表添加乘客請假欄位
ALTER TABLE trips ADD COLUMN IF NOT EXISTS passenger_leave_reason TEXT;

-- 為completed_trips表添加乘客請假欄位（保持一致性）
ALTER TABLE completed_trips ADD COLUMN IF NOT EXISTS passenger_leave_reason TEXT;

-- 驗證添加結果
\d trips
\d completed_trips 