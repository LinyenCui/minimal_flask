-- 007 DOWN：移除 completed_trips / trips 查詢索引
DROP INDEX IF EXISTS ix_completed_trips_date;
DROP INDEX IF EXISTS ix_completed_trips_category_date;
DROP INDEX IF EXISTS ix_trips_date;
