-- ============================================================
-- 007: completed_trips / trips 常用查詢索引
--
-- 背景：completed_trips 原本只有 pkey(id) 與 unique_code 唯一索引，
--       過去態查詢（依 date、category+date 篩選）全靠 seq scan；
--       trips 也缺 date 索引（排程掃描 / 日期查詢高頻用到）。
--
-- 可重複執行（IF NOT EXISTS）。
-- Render 部署：在 Adminer 對 prod DB 手動執行本檔全部內容。
-- ============================================================

CREATE INDEX IF NOT EXISTS ix_completed_trips_date
    ON completed_trips (date);

CREATE INDEX IF NOT EXISTS ix_completed_trips_category_date
    ON completed_trips (category, date);

CREATE INDEX IF NOT EXISTS ix_trips_date
    ON trips (date);
