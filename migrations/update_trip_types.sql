-- 确保trip_type列存在
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'trips' 
        AND column_name = 'trip_type'
    ) THEN 
        ALTER TABLE trips ADD COLUMN trip_type VARCHAR(20) DEFAULT 'fixed';
    END IF;

    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'completed_trips' 
        AND column_name = 'trip_type'
    ) THEN 
        ALTER TABLE completed_trips ADD COLUMN trip_type VARCHAR(20) DEFAULT 'fixed';
    END IF;
END $$;

-- 更新trips表中的记录
-- 有fixed_trip_id的记录设为'fixed'
UPDATE trips 
SET trip_type = 'fixed' 
WHERE fixed_trip_id IS NOT NULL 
  AND (trip_type IS NULL OR trip_type = '');

-- 没有fixed_trip_id的记录设为'temp'
UPDATE trips 
SET trip_type = 'temp' 
WHERE fixed_trip_id IS NULL 
  AND (trip_type IS NULL OR trip_type = '');

-- 更新completed_trips表中的记录
-- 根据unique_code判断是否是临时班次
-- unique_code以"T_"开头的是临时班次
UPDATE completed_trips 
SET trip_type = 'temp' 
WHERE unique_code LIKE 'T\\_%' 
  AND (trip_type IS NULL OR trip_type = '');

-- 其他记录都设为固定班次
UPDATE completed_trips 
SET trip_type = 'fixed' 
WHERE unique_code NOT LIKE 'T\\_%' 
  AND (trip_type IS NULL OR trip_type = ''); 