-- 為 fixed_schedules 表添加外鍵約束
-- 執行日期: 2025-06-29
-- 目的: 防止 fixed_schedules 中出現無效地點，避免匯入固定班次時失敗

BEGIN;

-- 檢查現有資料是否有無效地點（應該要沒有）
DO $$
DECLARE
    invalid_count INTEGER;
BEGIN
    -- 檢查無效的 start_point
    SELECT COUNT(*) INTO invalid_count
    FROM fixed_schedules fs
    LEFT JOIN customers c ON fs.start_point = c.short_name
    WHERE fs.start_point IS NOT NULL AND c.short_name IS NULL;
    
    IF invalid_count > 0 THEN
        RAISE EXCEPTION '發現 % 個無效的 start_point，請先清理資料', invalid_count;
    END IF;
    
    -- 檢查無效的 end_point
    SELECT COUNT(*) INTO invalid_count
    FROM fixed_schedules fs
    LEFT JOIN customers c ON fs.end_point = c.short_name
    WHERE fs.end_point IS NOT NULL AND c.short_name IS NULL;
    
    IF invalid_count > 0 THEN
        RAISE EXCEPTION '發現 % 個無效的 end_point，請先清理資料', invalid_count;
    END IF;
    
    RAISE NOTICE '資料檢查通過，無無效地點';
END $$;

-- 添加外鍵約束（如果不存在）
DO $$
BEGIN
    -- 添加 start_point 外鍵約束
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fixed_schedules_start_point_fkey'
        AND table_name = 'fixed_schedules'
    ) THEN
        ALTER TABLE fixed_schedules 
        ADD CONSTRAINT fixed_schedules_start_point_fkey 
        FOREIGN KEY (start_point) REFERENCES customers(short_name);
        
        RAISE NOTICE '已添加 start_point 外鍵約束';
    ELSE
        RAISE NOTICE 'start_point 外鍵約束已存在';
    END IF;
    
    -- 添加 end_point 外鍵約束
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fixed_schedules_end_point_fkey'
        AND table_name = 'fixed_schedules'
    ) THEN
        ALTER TABLE fixed_schedules 
        ADD CONSTRAINT fixed_schedules_end_point_fkey 
        FOREIGN KEY (end_point) REFERENCES customers(short_name);
        
        RAISE NOTICE '已添加 end_point 外鍵約束';
    ELSE
        RAISE NOTICE 'end_point 外鍵約束已存在';
    END IF;
END $$;

-- 檢查並重建 ID 觸發器（如果需要）
DO $$
BEGIN
    -- 檢查觸發器是否存在
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.triggers 
        WHERE trigger_name = 'trigger_set_schedule_id'
        AND event_object_table = 'fixed_schedules'
    ) THEN
        -- 重建觸發器
        CREATE TRIGGER trigger_set_schedule_id
        BEFORE INSERT ON fixed_schedules
        FOR EACH ROW EXECUTE FUNCTION set_schedule_id();
        
        RAISE NOTICE '已重建 ID 自動設定觸發器';
    ELSE
        RAISE NOTICE 'ID 觸發器已存在';
    END IF;
END $$;

-- 最終驗證
SELECT 
    'fixed_schedules 外鍵約束修復完成' as status,
    COUNT(*) as total_constraints
FROM information_schema.table_constraints 
WHERE table_name = 'fixed_schedules' 
AND constraint_type = 'FOREIGN KEY';

COMMIT; 