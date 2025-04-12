-- 为trips表添加trip_type列
ALTER TABLE trips ADD COLUMN trip_type VARCHAR(20) DEFAULT 'fixed';

-- 为completed_trips表添加trip_type列
ALTER TABLE completed_trips ADD COLUMN trip_type VARCHAR(20) DEFAULT 'fixed';

-- 更新现有数据
-- 根据fixed_trip_id是否有值来判断是否为固定班次
UPDATE trips SET trip_type = 'fixed' WHERE fixed_trip_id IS NOT NULL;
UPDATE trips SET trip_type = 'temp' WHERE fixed_trip_id IS NULL;

-- 对于completed_trips表，目前都设为'fixed'，因为没有明确的方式区分
-- 如果需要，可以根据特定条件进行更新 