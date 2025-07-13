-- 設定 fixed_schedules.category 為 NOT NULL
-- 2024-06-18: 防止 category 為空導致班次查詢時被過濾掉的問題

-- 檢查是否有 NULL 值（應該為 0）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM fixed_schedules WHERE category IS NULL) THEN
        RAISE EXCEPTION '發現有 category 為 NULL 的記錄，請先處理這些記錄';
    END IF;
    RAISE NOTICE '✅ 檢查通過：沒有 category 為 NULL 的記錄';
END $$;

-- 設定 category 欄位為 NOT NULL
ALTER TABLE fixed_schedules 
ALTER COLUMN category SET NOT NULL;

-- 設定預設值，防止未來插入時遺漏 category
ALTER TABLE fixed_schedules 
ALTER COLUMN category SET DEFAULT '未分類';

-- 驗證修改結果
DO $$
DECLARE
    nullable_status TEXT;
    default_val TEXT;
BEGIN
    -- 檢查是否成功設定為 NOT NULL
    SELECT c.is_nullable INTO nullable_status
    FROM information_schema.columns c
    WHERE c.table_name = 'fixed_schedules' 
    AND c.column_name = 'category';
    
    -- 檢查預設值
    SELECT c.column_default INTO default_val
    FROM information_schema.columns c
    WHERE c.table_name = 'fixed_schedules' 
    AND c.column_name = 'category';
    
    IF nullable_status = 'NO' THEN
        RAISE NOTICE '✅ 成功：fixed_schedules.category 已設定為 NOT NULL';
    ELSE
        RAISE EXCEPTION '❌ 失敗：fixed_schedules.category 仍然可以為 NULL';
    END IF;
    
    IF default_val IS NOT NULL THEN
        RAISE NOTICE '✅ 成功：已設定預設值為 %', default_val;
    ELSE
        RAISE NOTICE '⚠️  注意：未設定預設值';
    END IF;
END $$; 