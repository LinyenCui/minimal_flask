-- ====================================================================
-- Render 資料庫維護腳本
--
-- 功能:
-- 1. 清理舊的班次紀錄，減小資料庫體積。
-- 2. 重設序列計數器，防止 ID 無限增長。
--
-- 如何使用:
-- 1. 手動執行: 複製此文件內容，在資料庫管理工具中執行。
-- 2. 自動執行: 將指令設定到 Render 的 Cron Job 中，定期執行。
--
-- 注意: 請在系統離峰時段執行此腳本。
-- ====================================================================

-- 步驟 1: 清理一個月前的 `completed_trips` 紀錄
-- --------------------------------------------------------------------

DO $$
BEGIN
    RAISE NOTICE '[Step 1/4] Deleting records from completed_trips older than 1 month...';
    DELETE FROM completed_trips WHERE date < NOW() - INTERVAL '1 month';
    RAISE NOTICE 'Deletion from completed_trips complete.';
END;
$$;


-- 步驟 2: 清理 `trips` 紀錄 (請根據需求二選一)
-- --------------------------------------------------------------------

DO $$
BEGIN
    RAISE NOTICE '[Step 2/4] Deleting records from trips...';

    -- 選項 A: (預設啟用) 只刪除一周前的 trips 紀錄
    -- -----------------------------------------------------------
    DELETE FROM trips WHERE date < NOW() - INTERVAL '1 week';
    RAISE NOTICE 'Deleted trips older than 1 week.';

    -- 選項 B: (預設禁用) 刪除所有的 trips 紀錄
    -- -----------------------------------------------------------
    -- 如果您想刪除所有 trips (例如在重新匯入固定班次之前)，
    -- 請將上面那行 DELETE 註解掉 (在前面加上 --)，並取消下面這行的註解。
    --
    -- TRUNCATE TABLE trips RESTART IDENTITY CASCADE;
    -- RAISE NOTICE 'Truncated all records from trips.';

END;
$$;


-- 步驟 3: 校準 `completed_trips` 的序列計數器
-- --------------------------------------------------------------------
-- 這會將序列的下一個值，設定為當前資料表中的最大 ID。 
-- 如果資料表為空，則重設為 1。

DO $$
BEGIN
    RAISE NOTICE '[Step 3/4] Calibrating sequence for completed_trips...';
    PERFORM setval('completed_trips_id_seq', COALESCE((SELECT MAX(id) FROM completed_trips), 1), true);
    RAISE NOTICE 'Sequence for completed_trips calibrated.';
END;
$$;


-- 步驟 4: 校準 `trips` 的序列計數器
-- --------------------------------------------------------------------
-- trips 表的 ID 欄位是 trip_id，序列名稱通常是 trips_trip_id_seq

DO $$
BEGIN
    RAISE NOTICE '[Step 4/4] Calibrating sequence for trips...';
    PERFORM setval('trips_trip_id_seq', COALESCE((SELECT MAX(trip_id) FROM trips), 1), true);
    RAISE NOTICE 'Sequence for trips calibrated.';
END;
$$;


-- ====================================================================
-- 執行完畢
-- ====================================================================
