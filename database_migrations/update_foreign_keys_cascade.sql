-- 更新 fixed_schedules 外鍵約束為 CASCADE 更新
-- 執行日期: 2025-06-29
-- 目的: 讓修改 customers.short_name 時，所有相關表自動更新

BEGIN;

-- 檢查當前外鍵約束狀態
DO $$
DECLARE
    constraint_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO constraint_count
    FROM information_schema.table_constraints 
    WHERE table_name = 'fixed_schedules' 
    AND constraint_type = 'FOREIGN KEY'
    AND constraint_name LIKE '%point%';
    
    IF constraint_count = 0 THEN
        RAISE EXCEPTION 'fixed_schedules 表沒有地點相關的外鍵約束，請先執行 add_fixed_schedules_foreign_keys.sql';
    END IF;
    
    RAISE NOTICE '找到 % 個外鍵約束，準備更新為 CASCADE', constraint_count;
END $$;

-- 刪除舊的外鍵約束
DO $$
BEGIN
    -- 刪除 start_point 外鍵約束
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fixed_schedules_start_point_fkey'
        AND table_name = 'fixed_schedules'
    ) THEN
        ALTER TABLE fixed_schedules DROP CONSTRAINT fixed_schedules_start_point_fkey;
        RAISE NOTICE '已刪除舊的 start_point 外鍵約束';
    END IF;
    
    -- 刪除 end_point 外鍵約束
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fixed_schedules_end_point_fkey'
        AND table_name = 'fixed_schedules'
    ) THEN
        ALTER TABLE fixed_schedules DROP CONSTRAINT fixed_schedules_end_point_fkey;
        RAISE NOTICE '已刪除舊的 end_point 外鍵約束';
    END IF;
END $$;

-- 重新建立帶有 CASCADE 更新的外鍵約束
ALTER TABLE fixed_schedules 
ADD CONSTRAINT fixed_schedules_start_point_fkey 
FOREIGN KEY (start_point) REFERENCES customers(short_name) ON UPDATE CASCADE;

ALTER TABLE fixed_schedules 
ADD CONSTRAINT fixed_schedules_end_point_fkey 
FOREIGN KEY (end_point) REFERENCES customers(short_name) ON UPDATE CASCADE;

-- 驗證更新結果
SELECT 
    tc.table_name,
    kcu.column_name,
    rc.update_rule,
    rc.delete_rule
FROM 
    information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.referential_constraints AS rc ON tc.constraint_name = rc.constraint_name
WHERE constraint_type = 'FOREIGN KEY' 
    AND tc.table_name = 'fixed_schedules'
    AND kcu.column_name LIKE '%point%'
ORDER BY kcu.column_name;

-- 最終確認
SELECT 'fixed_schedules 外鍵約束已更新為 CASCADE' as status;

COMMIT; 