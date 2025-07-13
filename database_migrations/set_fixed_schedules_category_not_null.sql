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
    is_nullable TEXT;
    default_value TEXT;
BEGIN
    -- 檢查是否成功設定為 NOT NULL
    SELECT is_nullable INTO is_nullable
    FROM information_schema.columns 
    WHERE table_name = 'fixed_schedules' 
    AND column_name = 'category';
    
    -- 檢查預設值
    SELECT column_default INTO default_value
    FROM information_schema.columns 
    WHERE table_name = 'fixed_schedules' 
    AND column_name = 'category';
    
    IF is_nullable = 'NO' THEN
        RAISE NOTICE '✅ 成功：fixed_schedules.category 已設定為 NOT NULL';
    ELSE
        RAISE EXCEPTION '❌ 失敗：fixed_schedules.category 仍然可以為 NULL';
    END IF;
    
    IF default_value IS NOT NULL THEN
        RAISE NOTICE '✅ 成功：已設定預設值為 %', default_value;
    ELSE
        RAISE NOTICE '⚠️  注意：未設定預設值';
    END IF;
END $$;

-- 記錄完成資訊
INSERT INTO database_migrations (migration_name, executed_at, description) 
VALUES (
    'set_fixed_schedules_category_not_null',
    NOW(),
    '設定 fixed_schedules.category 為 NOT NULL，防止班次查詢時被過濾掉'
) ON CONFLICT (migration_name) DO NOTHING; 